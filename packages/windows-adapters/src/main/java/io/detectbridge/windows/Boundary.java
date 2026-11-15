package io.detectbridge.windows;

import static io.detectbridge.detection.Contracts.*;

import com.networknt.schema.*;
import io.detectbridge.transport.EnvelopeValidator;
import io.detectbridge.transport.Json;
import io.detectbridge.detection.Normalized;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Module-local validation of the frozen adapter context; no new shared interface. */
final class Boundary {
  private final Schema rawSchema;
  Boundary() {
    Map<String, String> resources = new HashMap<>();
    for (String name : List.of("common", "raw-record")) {
      try (var in = Boundary.class.getResourceAsStream("/v1/" + name + ".schema.json")) {
        String text = new String(Objects.requireNonNull(in).readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        resources.put(Json.MAPPER.readTree(text).get("$id").asString(), text);
      } catch (java.io.IOException ex) { throw new IllegalStateException("schema_load_failure"); }
    }
    rawSchema = SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,
        b -> b.schemas(resources)).getSchema(SchemaLocation.of("urn:detectbridge:contracts:1.0.0:raw-record"));
  }
  static void keys(JsonNode n, Set<String> required, Set<String> optional) {
    check(n.isObject(), "context_object");
    Set<String> found = new HashSet<>();
    for (var p : n.properties()) found.add(p.getKey());
    check(found.containsAll(required), "context_required");
    found.removeAll(required); found.removeAll(optional);
    check(found.isEmpty(), "context_unknown_member");
  }
  static void text(JsonNode n) { check(n.isString() && !n.asString().isEmpty(), "context_string"); }
  static void provenance(JsonNode n) {
    check(n.isArray() && !n.isEmpty() && n.size() <= 32, "context_provenance");
    for (var v : n) text(v);
  }
  static void digest(JsonNode n) { check(n.isString() && n.asString().matches("[a-f0-9]{64}"), "context_digest"); }
  static void timestamp(JsonNode n) {
    text(n);
    check(WindowsAdapter.utc(n.asString()), "context_timestamp");
  }
  void raw(JsonNode raw) {
    Normalized.unicode(raw);
    check(rawSchema.validate(raw, c -> c.executionConfig(e -> e.formatAssertionsEnabled(true))).isEmpty(), "raw_schema");
    check(EnvelopeValidator.recordIdentity(raw).equals(raw.get("record_id").asString()), "raw_identity");
    timestamp(raw.get("first_observed"));
    if (raw.path("cursor").has("position")) check(raw.get("cursor").get("position").isIntegralNumber(), "raw_cursor_type");
  }
  static String hash(JsonNode n) { return Json.sha(Json.bytes(canonical(n))); }
  static JsonNode resource(String file) {
    try (var in = Boundary.class.getResourceAsStream("/" + file)) {
      return Json.read(Objects.requireNonNull(in).readAllBytes());
    } catch (java.io.IOException ex) { throw new IllegalStateException("profile_load_failure"); }
  }
  String context(JsonNode raw, JsonNode c) {
    Normalized.unicode(c);
    check(Json.bytes(c).length <= Json.MAX_VALUE, "context_limit");
    keys(c, Set.of("version", "run_id", "source", "first_observed", "source_contract", "mapping_profile", "parser"),
        Set.of("source_generation", "host_binding", "receipt"));
    check(c.path("version").asString().equals("1.0.0"), "context_version");
    text(c.get("run_id"));
    check(UUID.fromString(c.get("run_id").asString()).toString().equals(c.get("run_id").asString()), "context_run");
    check(c.get("source").equals(raw.get("source")) && c.get("first_observed").equals(raw.get("first_observed")), "context_origin");
    keys(c.get("parser"), Set.of("id", "version"), Set.of());
    check(c.get("parser").equals(Json.MAPPER.valueToTree(Map.of("id", "windows-xml", "version", "1.0.0"))), "context_parser");
    var s = c.get("source_contract");
    keys(s, Set.of("id", "version", "sha256", "snapshot"), Set.of());
    String family = switch (s.path("id").asString()) {
      case "windows-security-4688-xml" -> "security";
      case "windows-sysmon-process-xml" -> "sysmon";
      default -> throw new IllegalArgumentException("context_source");
    };
    JsonNode expected = resource(family + ".source.json"), mapping = resource(family + ".mapping.json");
    check(s.get("snapshot").equals(expected) && s.path("id").equals(expected.get("id"))
        && s.path("version").equals(expected.get("version")) && s.path("sha256").asString().equals(hash(expected)), "context_source_snapshot");
    var m = c.get("mapping_profile");
    keys(m, Set.of("id", "version", "sha256", "declaration"), Set.of());
    check(m.get("declaration").equals(mapping) && m.path("id").equals(mapping.get("id"))
        && m.path("version").equals(mapping.get("version")) && m.path("sha256").equals(mapping.get("sha256")), "context_mapping");
    if (c.has("host_binding")) {
      var h = c.get("host_binding");
      keys(h, Set.of("host_id", "computer", "source", "revision", "sha256", "provenance", "kind"), Set.of());
      for (String k : List.of("host_id", "computer", "revision")) text(h.get(k));
      check(h.get("source").equals(raw.get("source")), "binding_source");
      check(Set.of("reviewed", "synthetic").contains(h.path("kind").asString()), "binding_kind");
      provenance(h.get("provenance")); digest(h.get("sha256"));
      var unhashed = ((tools.jackson.databind.node.ObjectNode) h).deepCopy(); unhashed.remove("sha256");
      check(hash(unhashed).equals(h.get("sha256").asString()), "binding_hash");
    }
    if (c.has("source_generation")) {
      var g = c.get("source_generation");
      keys(g, Set.of("id", "provenance"), Set.of("command_line_capture"));
      text(g.get("id")); provenance(g.get("provenance"));
      if (g.has("command_line_capture")) check(Set.of("enabled", "disabled", "unknown").contains(g.path("command_line_capture").asString()), "capture_configuration");
    }
    if (c.has("receipt")) {
      keys(c.get("receipt"), Set.of(), Set.of("received", "processed"));
      for (var p : c.get("receipt").properties()) timestamp(p.getValue());
    }
    return family;
  }
}
