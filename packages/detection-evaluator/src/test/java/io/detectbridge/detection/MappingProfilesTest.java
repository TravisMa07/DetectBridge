package io.detectbridge.detection;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.node.ArrayNode;

class MappingProfilesTest {
  static final Path ROOT = Path.of(System.getProperty("repository.root"));

  static ObjectNode plan() throws Exception {
    return (ObjectNode) Json.MAPPER.readTree(Files.readAllBytes(ROOT.resolve(".cache/detection/mapped-plan.json")));
  }

  static void rehash(ObjectNode node, String field) {
    node.remove(field);
    node.put(field, Json.sha(Json.bytes(Contracts.canonical(node))));
  }

  @Test
  void legacyAndMappedResultsUseTheirOwnContracts() throws Exception {
    byte[] event = Files.readAllBytes(ROOT.resolve("contracts/detection/v1/fixtures/positive.event.json"));
    for (String filename : List.of("plan.json", "mapped-plan.json")) {
      Evaluator evaluator = new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/" + filename)));
      if (filename.equals("mapped-plan.json"))
        assertThrows(IllegalArgumentException.class, evaluator::requireLegacyDeployment);
      else assertDoesNotThrow(evaluator::requireLegacyDeployment);
      JsonNode result = evaluator.evaluate(event, EvaluatorTest.location(event));
      boolean mapped = filename.equals("mapped-plan.json");
      assertEquals(mapped ? "2.0.0" : "1.0.0", result.get("version").asString());
      assertEquals(mapped ? "detectbridge-java/2.0.0" : "detectbridge-java/1.0.0",
          result.get("evaluator").asString());
      assertEquals(1, result.get("counts").get("matched").asInt());
      assertEquals(mapped, result.has("mapping_sha256"));
      assertEquals(result, evaluator.evaluate(event, EvaluatorTest.location(event)));
    }
  }

  @Test
  void sparseSourceCapabilitiesBlockOnlyUsedFields() throws Exception {
    Evaluator evaluator = new Evaluator(Json.bytes(plan()));
    byte[] linux = Files.readAllBytes(ROOT.resolve("contracts/v1/examples/linux-audit-execution.event.json"));
    assertEquals(1, evaluator.evaluate(linux, EvaluatorTest.location(linux))
        .get("counts").get("configuration_blocked").asInt());
    ObjectNode p = plan();
    JsonNode image = p.get("rules").get(0).get("expression").get("args").get(0);
    ((ObjectNode) p.get("rules").get(0)).set("expression", image);
    rehash(p, "bundle_sha256");
    // Compiled AST is trusted compiler output; the hash is integrity, not compiler authentication.
    JsonNode result = new Evaluator(Json.bytes(p)).evaluate(linux, EvaluatorTest.location(linux));
    assertEquals(1, result.get("counts").get("unmatched").asInt());
  }

  @Test
  void nestedTamperingFailsEvenWithValidOuterHash() throws Exception {
    for (String mutation : List.of("source_hash", "source_version", "alias", "target", "type",
        "transform", "capability", "source_path", "duplicate_profile", "missing_profile",
        "candidate_revision", "candidate_lineage", "mapping_hash", "version")) {
      ObjectNode p = plan();
      ObjectNode profile = (ObjectNode) p.get("mapping_profiles").get(0);
      ObjectNode field = (ObjectNode) profile.get("fields").get(0);
      boolean updateProfileHash = true;
      switch (mutation) {
        case "source_hash" -> ((ObjectNode) profile.get("source")).put("sha256", "0".repeat(64));
        case "source_version" -> ((ObjectNode) profile.get("source")).put("version", "9.0.0");
        case "alias" -> field.put("alias", "Unknown");
        case "target" -> field.put("target", "process.command_line");
        case "type" -> field.put("type", "integer");
        case "transform" -> field.put("transform", "untrusted-code/1.0.0");
        case "capability" -> field.put("capability", "conditional");
        case "source_path" -> field.put("source_path", "/unknown");
        case "duplicate_profile" -> ((ArrayNode) p.get("mapping_profiles")).add(profile.deepCopy());
        case "missing_profile" -> ((ArrayNode) p.get("mapping_profiles")).remove(0);
        case "candidate_revision" -> ((ObjectNode) p.get("rules").get(0).get("provenance"))
            .put("revision", "0".repeat(64));
        case "candidate_lineage" -> ((ObjectNode) p.get("rules").get(0).get("provenance"))
            .put("original_sha256", "0".repeat(64));
        case "mapping_hash" -> { profile.put("sha256", "0".repeat(64)); updateProfileHash = false; }
        case "version" -> p.put("version", "3.0.0");
      }
      if (updateProfileHash) rehash(profile, "sha256");
      rehash(p, "bundle_sha256");
      assertThrows(IllegalArgumentException.class, () -> new Evaluator(Json.bytes(p)), mutation);
    }
  }

  @Test
  void changedMappingIsAnIncompatibleCheckpointBundle() throws Exception {
    ObjectNode original = plan(), changed = plan();
    ObjectNode profile = (ObjectNode) changed.get("mapping_profiles").get(0);
    profile.put("id", "another-immutable-mapping-revision");
    rehash(profile, "sha256"); rehash(changed, "bundle_sha256");
    Evaluator a = new Evaluator(Json.bytes(original)), b = new Evaluator(Json.bytes(changed));
    String before = BundleBinding.fingerprint(a.bundle(), "cluster", "group", Map.of("input", "id"));
    String after = BundleBinding.fingerprint(b.bundle(), "cluster", "group", Map.of("input", "id"));
    assertThrows(IllegalArgumentException.class, () -> BundleBinding.requireRestored(after, List.of(before)));
  }
}
