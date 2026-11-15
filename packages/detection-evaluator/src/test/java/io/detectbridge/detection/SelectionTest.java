package io.detectbridge.detection;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

class SelectionTest {
  static final Path ROOT = Path.of(System.getProperty("repository.root"));
  static ObjectNode plan() throws Exception {
    return (ObjectNode) Json.MAPPER.readTree(Files.readAllBytes(ROOT.resolve(".cache/detection/selection-plan.json")));
  }
  static ObjectNode event() throws Exception {
    ObjectNode e = (ObjectNode) EvaluatorTest.read(ROOT.resolve("contracts/detection/v1/fixtures/positive.event.json"));
    ((ObjectNode) e.get("process")).put("executable", "x");
    return e;
  }
  static void rehash(ObjectNode p) {
    p.remove("bundle_sha256"); p.put("bundle_sha256", Json.sha(Json.bytes(Contracts.canonical(p))));
  }
  static JsonNode compare(Evaluator evaluator, ObjectNode event, int budget) {
    byte[] bytes = Json.bytes(event);
    JsonNode exhaustive = evaluator.evaluate(bytes, EvaluatorTest.location(bytes), false, budget);
    JsonNode selected = evaluator.evaluate(bytes, EvaluatorTest.location(bytes), true, budget);
    assertEquals(exhaustive, selected);
    assertEquals(4, selected.get("counts").propertyStream().mapToInt(p -> p.getValue().asInt()).sum());
    assertEquals(selected.get("matched").size(), selected.get("counts").get("matched").asInt());
    return selected;
  }

  @Test void independentSharedBudgetAndGateOracle() throws Exception {
    Evaluator evaluator = new Evaluator(Json.bytes(plan()));
    for (var expected : EvaluatorTest.read(ROOT.resolve("contracts/detection/v2/fixtures/selection-expectations.json"))) {
      JsonNode result = compare(evaluator, event(), expected.get("budget").asInt());
      for (String outcome : Evaluator.OUTCOMES)
        assertEquals(expected.get(outcome).asInt(), result.get("counts").get(outcome).asInt(), expected.get("rationale").asString());
      var diagnostics = result.get("diagnostics");
      if (expected.get("budget").asInt() == 7) {
        assertEquals("70000000-0000-4000-8000-000000000011", result.get("matched").get(0).get("id").asString());
        assertEquals("70000000-0000-4000-8000-000000000013", diagnostics.get(0).get("rule_id").asString());
        assertEquals("70000000-0000-4000-8000-000000000014", diagnostics.get(1).get("rule_id").asString());
      }
    }
  }

  @Test void serializedRuleOrderSurvivesSelection() throws Exception {
    ObjectNode p = plan();
    ArrayNode reversed = Json.MAPPER.createArrayNode();
    for (int i = p.get("rules").size() - 1; i >= 0; i--) reversed.add(p.get("rules").get(i));
    p.set("rules", reversed); rehash(p);
    JsonNode result = compare(new Evaluator(Json.bytes(p)), event(), 7);
    assertEquals("70000000-0000-4000-8000-000000000014", result.get("matched").get(0).get("id").asString());
    assertEquals("70000000-0000-4000-8000-000000000013", result.get("diagnostics").get(0).get("rule_id").asString());
    assertEquals("70000000-0000-4000-8000-000000000011", result.get("diagnostics").get(1).get("rule_id").asString());
  }

  @Test void unknownQualityAndInvalidInputsNeverDisappear() throws Exception {
    Evaluator evaluator = new Evaluator(Json.bytes(plan()));
    ObjectNode e = event();
    ((ObjectNode) e.get("detectbridge").get("source_contract")).put("id", "unknown");
    assertEquals(4, compare(evaluator, e, 0).get("counts").get("configuration_blocked").asInt());
    e = event(); ((ObjectNode) e.get("detectbridge").get("quality")).put("eligibility", "undetermined");
    var result = compare(evaluator, e, 0);
    assertEquals(2, result.get("counts").get("quality_skipped").asInt());
    assertEquals(1, result.get("counts").get("configuration_blocked").asInt());
    ((ObjectNode) e.get("process")).putNull("executable");
    byte[] invalid = Json.bytes(e);
    assertThrows(IllegalArgumentException.class, () -> evaluator.evaluate(invalid, EvaluatorTest.location(invalid)));
    assertThrows(IllegalArgumentException.class, () -> evaluator.evaluateExhaustive(invalid, EvaluatorTest.location(invalid)));
  }

  @Test void everySourceProfileAndReplayUsesTheSamePolicy() throws Exception {
    Evaluator evaluator = new Evaluator(Json.bytes(plan()));
    for (String profile : List.of("windows-security-4688", "windows-sysmon-process", "linux-audit-execution", "openssh-authentication")) {
      ObjectNode e = (ObjectNode) EvaluatorTest.read(ROOT.resolve("contracts/v1/examples/" + profile + ".event.json"));
      // Independent predicates require x; source values otherwise remain original synthetic data.
      for (int budget : List.of(0, 7, 1_000_000)) compare(evaluator, e, budget);
      ((ObjectNode) e.get("detectbridge")).put("run_id", "00000000-0000-4000-8000-000000000002");
      compare(evaluator, e, 1_000_000);
    }
  }

  @Test void omittedAndMissingLogsourceDimensionsAreExact() throws Exception {
    ObjectNode p = plan();
    ((ObjectNode) p.get("rules").get(1)).set("logsource", Json.MAPPER.createObjectNode());
    rehash(p);
    byte[] bytes = Json.bytes(event());
    JsonNode result = new Evaluator(Json.bytes(p)).evaluate(bytes, EvaluatorTest.location(bytes));
    assertEquals(3, result.get("counts").get("matched").asInt());
    ((ObjectNode) p.get("rules").get(1).get("logsource")).put("service", "not-present");
    rehash(p);
    assertEquals(1, compare(new Evaluator(Json.bytes(p)), event(), 8).get("counts").get("inapplicable").asInt());
  }
  @Test void noCallerSuppliedIndexAndNoLegacyOrPolicyBindingAdoption() throws Exception {
    ObjectNode p = plan();
    p.set("selection", Json.MAPPER.createObjectNode()); rehash(p);
    assertThrows(IllegalArgumentException.class, () -> new Evaluator(Json.bytes(p)));
    Evaluator evaluator = new Evaluator(Json.bytes(plan()));
    var topics = Map.of("detectbridge.detection.input.v2", "topic-id");
    String mapped = BundleBinding.fingerprint(evaluator.bundle(), evaluator.semanticVersion() + "/" + Evaluator.SELECTION_VERSION,
        "cluster", "group", topics);
    String legacy = BundleBinding.fingerprint(evaluator.bundle(), "cluster", "group", topics);
    String changed = BundleBinding.fingerprint(evaluator.bundle(), evaluator.semanticVersion() + "/source-index/2.0.0",
        "cluster", "group", topics);
    for (String incompatible : List.of(legacy, changed))
      assertThrows(IllegalArgumentException.class, () -> BundleBinding.requireRestored(mapped, List.of(incompatible)));
  }

}
