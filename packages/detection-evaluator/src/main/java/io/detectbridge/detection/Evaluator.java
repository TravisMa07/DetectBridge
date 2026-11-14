package io.detectbridge.detection;

import static io.detectbridge.detection.Contracts.*;

import io.detectbridge.transport.Json;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Immutable compiled bundle. Per-event budget is local; no Python or dynamic code. */
public final class Evaluator {
  public static final String VERSION = "detectbridge-java/1.0.0";
  public static final List<String> OUTCOMES =
      List.of(
          "matched",
          "unmatched",
          "inapplicable",
          "configuration_blocked",
          "quality_skipped",
          "evaluation_error");
  private final Contracts contracts = new Contracts();
  private final Normalized normalized = new Normalized(contracts);
  private final JsonNode plan;
  private final Map<String, JsonNode> sources = new HashMap<>();

  public Evaluator(byte[] bytes) {
    check(bytes != null && bytes.length <= 4 * 1024 * 1024, "bundle_size_limit");
    try {
      StandardCharsets.UTF_8
          .newDecoder()
          .onMalformedInput(CodingErrorAction.REPORT)
          .decode(ByteBuffer.wrap(bytes));
      plan = Json.MAPPER.readTree(bytes);
      Normalized.unicode(plan);
      contracts.require("detection", "plan", plan);
      ObjectNode unhashed = ((ObjectNode) plan).deepCopy();
      unhashed.remove("bundle_sha256");
      check(Json.sha(Json.bytes(canonical(unhashed))).equals(bundle()), "bundle_hash_mismatch");
      for (var s : plan.get("sources")) {
        normalized.source(s);
        check(
            sources.put(s.get("id").asString() + "/" + s.get("version").asString(), s) == null,
            "duplicate_source");
      }
      check(!sources.isEmpty(), "source_required");
      Set<String> ids = new HashSet<>();
      int total = 0;
      for (var r : plan.get("rules")) {
        check(ids.add(r.get("id").asString()), "duplicate_rule");
        byte[] yaml = r.get("yaml").asString().getBytes(StandardCharsets.UTF_8);
        check(
            yaml.length <= 262144 && Json.sha(yaml).equals(r.get("revision").asString()),
            "rule_revision_mismatch");
        int count = validateNode(r.get("expression"), 1);
        total += count;
        check(count <= 4096 && total <= 65536, "node_limit");
      }
    } catch (IllegalArgumentException e) {
      throw new IllegalArgumentException("invalid_bundle");
    } catch (Exception e) {
      throw new IllegalArgumentException("invalid_bundle");
    }
  }

  public String bundle() {
    return plan.get("bundle_sha256").asString();
  }

  private int validateNode(JsonNode n, int depth) {
    check(depth <= 32, "depth_limit");
    int count = 1;
    switch (n.get("op").asString()) {
      case "and", "or":
        for (var a : n.get("args")) count += validateNode(a, depth + 1);
        break;
      case "not":
        count += validateNode(n.get("arg"), depth + 1);
        break;
      case "integer":
        check(
            n.get("value").isIntegralNumber() && n.get("value").canConvertToLong(),
            "integer_required");
        break;
      case "string":
        for (var t : n.get("tokens")) {
          int length =
              t.get("text").asString().codePointCount(0, t.get("text").asString().length());
          check(length == (t.get("kind").asString().equals("literal") ? 1 : 0), "invalid_token");
        }
        break;
      default:
        throw new IllegalArgumentException("unsupported_operator");
    }
    return count;
  }

  static final class Budget {
    int left = 1_000_000;

    void tick() {
      if (--left < 0) throw new IllegalArgumentException("evaluation_budget");
    }
  }

  static int fold(int c) {
    return Character.toLowerCase(Character.toUpperCase(c));
  }

  static boolean glob(JsonNode tokens, String value, Budget budget) {
    int[] input = value.codePoints().toArray();
    boolean[] prev = new boolean[input.length + 1];
    prev[0] = true;
    for (var token : tokens) {
      boolean[] next = new boolean[input.length + 1];
      String kind = token.get("kind").asString();
      budget.tick();
      next[0] = kind.equals("star") && prev[0];
      for (int i = 1; i <= input.length; i++) {
        budget.tick();
        next[i] =
            switch (kind) {
              case "star" -> prev[i] || next[i - 1];
              case "any" -> prev[i - 1];
              default ->
                  prev[i - 1]
                      && fold(input[i - 1]) == fold(token.get("text").asString().codePointAt(0));
            };
      }
      prev = next;
    }
    return prev[input.length];
  }

  static boolean predicate(JsonNode n, JsonNode value, Budget budget) {
    budget.tick();
    if (value.isArray()) {
      for (var v : value) if (predicate(n, v, budget)) return true;
      return false;
    }
    if (n.get("op").asString().equals("integer"))
      return value.isIntegralNumber()
          && value.bigIntegerValue().equals(n.get("value").bigIntegerValue());
    return value.isString() && glob(n.get("tokens"), value.asString(), budget);
  }

  static boolean matches(JsonNode n, JsonNode event, Budget budget) {
    budget.tick();
    switch (n.get("op").asString()) {
      case "and":
        for (var a : n.get("args")) if (!matches(a, event, budget)) return false;
        return true;
      case "or":
        for (var a : n.get("args")) if (matches(a, event, budget)) return true;
        return false;
      case "not":
        return !matches(n.get("arg"), event, budget);
      default:
        return predicate(n, field(event, n.get("field").asString()), budget);
    }
  }

  public JsonNode evaluate(byte[] bytes, Map<String, Object> location) {
    JsonNode event = Json.read(bytes),
        db = event.path("detectbridge"),
        sc = db.path("source_contract");
    JsonNode source = sources.get(sc.path("id").asString() + "/" + sc.path("version").asString());
    normalized.validate(event, source);
    Map<String, Integer> counts = new LinkedHashMap<>();
    OUTCOMES.forEach(k -> counts.put(k, 0));
    List<Object> matched = new ArrayList<>(), diagnostics = new ArrayList<>();
    Budget budget = new Budget();
    for (var rule : plan.get("rules")) {
      String outcome;
      if (source == null) outcome = "configuration_blocked";
      else {
        boolean applicable = true;
        for (var p : rule.get("logsource").properties())
          if (!source.get("sigma").path(p.getKey()).equals(p.getValue())) applicable = false;
        if (!applicable) outcome = "inapplicable";
        else if (!db.get("quality").get("eligibility").asString().equals("eligible"))
          outcome = "quality_skipped";
        else
          try {
            outcome = matches(rule.get("expression"), event, budget) ? "matched" : "unmatched";
          } catch (IllegalArgumentException e) {
            outcome = "evaluation_error";
          }
      }
      counts.put(outcome, counts.get(outcome) + 1);
      if (outcome.equals("matched"))
        matched.add(
            Map.of("id", rule.get("id").asString(), "revision", rule.get("revision").asString()));
      if (List.of("configuration_blocked", "quality_skipped", "evaluation_error").contains(outcome))
        diagnostics.add(
            Map.of("rule_id", rule.get("id").asString(), "category", outcome, "pointer", ""));
    }
    String id = event.get("event").get("id").asString(), run = db.get("run_id").asString();
    Map<String, Object> output = new LinkedHashMap<>();
    output.put("version", "1.0.0");
    output.put("result_id", Json.identity(List.of(id, run, bundle())));
    output.put("event_id", id);
    output.put("run_id", run);
    output.put("bundle_sha256", bundle());
    output.put("evaluator", VERSION);
    output.put("compiler", "detectbridge/1.0.0");
    output.put("mapping_version", "fixture/1.0.0");
    output.put("input", location);
    output.put("matched", matched);
    output.put("counts", counts);
    output.put("diagnostics", diagnostics);
    JsonNode result = Json.MAPPER.valueToTree(output);
    contracts.require("detection", "result", result);
    return result;
  }
}
