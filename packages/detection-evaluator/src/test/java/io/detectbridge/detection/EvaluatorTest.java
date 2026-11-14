package io.detectbridge.detection;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class EvaluatorTest {
  static final Path ROOT = Path.of(System.getProperty("repository.root"));
  static final Path FIX = ROOT.resolve("contracts/detection/v1/fixtures");

  static JsonNode read(Path p) throws Exception {
    return Json.read(Files.readAllBytes(p));
  }

  static JsonNode string(String... parts) {
    List<Object> tokens = new ArrayList<>();
    for (String p : parts) {
      if (p.equals("*") || p.equals("?"))
        tokens.add(Map.of("kind", p.equals("*") ? "star" : "any", "text", ""));
      else
        p.codePoints()
            .forEach(
                c ->
                    tokens.add(
                        Map.of("kind", "literal", "text", new String(Character.toChars(c)))));
    }
    return Json.MAPPER.valueToTree(
        Map.of("op", "string", "field", "process.command_line", "tokens", tokens));
  }

  @Test
  void globSemanticsIndependent() {
    assertTrue(
        Evaluator.glob(
            string("cMd", "*", ".EXE").get("tokens"), "CMD /c.EXE", new Evaluator.Budget()));
    assertFalse(Evaluator.glob(string("cmd").get("tokens"), "prefixcmd", new Evaluator.Budget()));
    assertTrue(Evaluator.glob(string("?").get("tokens"), "😀", new Evaluator.Budget()));
    assertFalse(Evaluator.glob(string("?", "?").get("tokens"), "😀", new Evaluator.Budget()));
    assertTrue(Evaluator.glob(string("Ä").get("tokens"), "ä", new Evaluator.Budget()));
    assertFalse(Evaluator.glob(string("SS").get("tokens"), "ß", new Evaluator.Budget()));
    assertFalse(Evaluator.glob(string("é").get("tokens"), "e\u0301", new Evaluator.Budget()));
    assertTrue(Evaluator.glob(string("𐐀").get("tokens"), "𐐨", new Evaluator.Budget()));
    assertTrue(Evaluator.glob(string("").get("tokens"), "", new Evaluator.Budget()));
  }

  @Test
  void missingNegationTypesAndArrays() {
    JsonNode predicate = string("a"), empty = Json.read("{}".getBytes());
    assertFalse(Evaluator.matches(predicate, empty, new Evaluator.Budget()));
    JsonNode not = Json.MAPPER.valueToTree(Map.of("op", "not", "arg", predicate));
    assertTrue(Evaluator.matches(not, empty, new Evaluator.Budget()));
    assertTrue(
        Evaluator.predicate(
            predicate, Json.MAPPER.valueToTree(List.of("b", "A")), new Evaluator.Budget()));
    assertFalse(
        Evaluator.predicate(predicate, Json.MAPPER.valueToTree(List.of()), new Evaluator.Budget()));
    JsonNode integer =
        Json.MAPPER.valueToTree(
            Map.of("op", "integer", "field", "process.pid", "value", Long.MAX_VALUE));
    assertTrue(
        Evaluator.predicate(
            integer, Json.MAPPER.valueToTree(Long.MAX_VALUE), new Evaluator.Budget()));
    assertFalse(
        Evaluator.predicate(
            integer,
            Json.MAPPER.valueToTree(String.valueOf(Long.MAX_VALUE)),
            new Evaluator.Budget()));
    assertFalse(
        Evaluator.predicate(integer, Json.MAPPER.valueToTree(true), new Evaluator.Budget()));
    assertThrows(
        IllegalArgumentException.class,
        () ->
            Evaluator.glob(
                string("x", "*").get("tokens"), "y".repeat(1000001), new Evaluator.Budget()));
  }

  static Map<String, Object> location(byte[] b) {
    return Map.of(
        "cluster_id",
        "test",
        "topic_id",
        "test",
        "topic",
        "test",
        "partition",
        0,
        "offset",
        0,
        "value_sha256",
        Json.sha(b));
  }

  @Test
  void compiledFixtures() throws Exception {
    Evaluator evaluator =
        new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/plan.json")));
    for (var c : read(FIX.resolve("cases.json"))) {
      byte[] bytes = Files.readAllBytes(FIX.resolve(c.get("event").asString()));
      JsonNode result = evaluator.evaluate(bytes, location(bytes));
      assertEquals(
          1,
          result.get("counts").get(c.get("expected").asString()).asInt(),
          c.get("rationale").asString());
      assertEquals(result, evaluator.evaluate(bytes, location(bytes)));
    }
  }

  @Test
  void qualityReplayAndInvalidInputs() throws Exception {
    Evaluator evaluator =
        new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/plan.json")));
    ObjectNode event = (ObjectNode) read(FIX.resolve("positive.event.json"));
    byte[] original = Json.bytes(event);
    String id = evaluator.evaluate(original, location(original)).get("result_id").asString();
    ((ObjectNode) event.get("detectbridge")).put("run_id", "00000000-0000-4000-8000-000000000002");
    byte[] replay = Json.bytes(event);
    assertNotEquals(id, evaluator.evaluate(replay, location(replay)).get("result_id").asString());
    ((ObjectNode) event.get("detectbridge").get("quality")).put("eligibility", "undetermined");
    byte[] quality = Json.bytes(event);
    assertEquals(
        1,
        evaluator
            .evaluate(quality, location(quality))
            .get("counts")
            .get("quality_skipped")
            .asInt());
    ((ObjectNode) event.get("process")).putNull("executable");
    assertThrows(
        IllegalArgumentException.class,
        () -> evaluator.evaluate(Json.bytes(event), location(original)));
    assertThrows(IllegalArgumentException.class, () -> Json.read("{\"a\":1,\"a\":2}".getBytes()));
    assertThrows(
        IllegalArgumentException.class,
        () -> evaluator.evaluate(new byte[] {(byte) 0xff}, location(original)));
  }

  @Test
  void bundleTamperAndVersion() throws Exception {
    ObjectNode p =
        (ObjectNode)
            Json.MAPPER.readTree(Files.readAllBytes(ROOT.resolve(".cache/detection/plan.json")));
    p.put("version", "2.0.0");
    assertThrows(IllegalArgumentException.class, () -> new Evaluator(Json.bytes(p)));
    p.put("version", "1.0.0");
    p.put("bundle_sha256", "0".repeat(64));
    assertThrows(IllegalArgumentException.class, () -> new Evaluator(Json.bytes(p)));
  }

  @Test
  void checkpointBindingRejectsChangedPlanGroupOrTopic() {
    Map<String, String> topics = Map.of("input", "uuid-a", "output", "uuid-b");
    String fingerprint = BundleBinding.fingerprint("bundle-a", "cluster-a", "group-a", topics);
    assertDoesNotThrow(() -> BundleBinding.requireRestored(fingerprint, List.of(fingerprint)));
    for (String changed :
        List.of(
            BundleBinding.fingerprint("bundle-b", "cluster-a", "group-a", topics),
            BundleBinding.fingerprint("bundle-a", "cluster-b", "group-a", topics),
            BundleBinding.fingerprint("bundle-a", "cluster-a", "group-b", topics),
            BundleBinding.fingerprint(
                "bundle-a",
                "cluster-a",
                "group-a",
                Map.of("input", "new-uuid", "output", "uuid-b"))))
      assertThrows(
          IllegalArgumentException.class,
          () -> BundleBinding.requireRestored(changed, List.of(fingerprint)));
    assertThrows(
        IllegalArgumentException.class,
        () -> BundleBinding.requireRestored(fingerprint, List.of()));
    assertThrows(
        IllegalArgumentException.class,
        () -> BundleBinding.requireRestored(fingerprint, List.of(fingerprint, fingerprint)));
  }

  @Test
  void normalizedEvidenceAndConfigurationAreNotNonmatches() throws Exception {
    Evaluator evaluator =
        new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/plan.json")));
    ObjectNode original = (ObjectNode) read(FIX.resolve("positive.event.json"));
    ObjectNode unknown = original.deepCopy();
    ((ObjectNode) unknown.get("detectbridge").get("source_contract")).put("id", "unknown-source");
    byte[] unknownBytes = Json.bytes(unknown);
    assertEquals(
        1,
        evaluator
            .evaluate(unknownBytes, location(unknownBytes))
            .get("counts")
            .get("configuration_blocked")
            .asInt());
    for (String mutation : List.of("identity", "digest", "time", "classification", "quality")) {
      ObjectNode e = original.deepCopy();
      switch (mutation) {
        case "identity":
          ((ObjectNode) e.get("event")).put("id", "sha256:" + "0".repeat(64));
          break;
        case "digest":
          ((ObjectNode) e.get("detectbridge").get("evidence").get(0).get("evidence"))
              .put("sha256", "0".repeat(64));
          break;
        case "time":
          ((ObjectNode) e.get("detectbridge").get("time"))
              .put("source_utc", "2020-01-01T00:00:00Z");
          break;
        case "classification":
          ((ObjectNode) e.get("event")).put("kind", "alert");
          break;
        case "quality":
          ((ObjectNode) e.get("detectbridge").get("quality")).put("integrity", "insufficient");
          break;
      }
      assertThrows(
          IllegalArgumentException.class,
          () -> evaluator.evaluate(Json.bytes(e), location(Json.bytes(e))),
          mutation);
    }
  }

  @Test
  void independentP03IdentityVectors() throws Exception {
    for (var vector : read(ROOT.resolve("contracts/v1/identity-vectors.json"))) {
      byte[] literal =
          vector.get("canonical_utf8").asString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
      assertEquals(vector.get("expected_id").asString(), "sha256:" + Json.sha(literal));
      assertEquals(vector.get("expected_id").asString(), Json.identity(Json.read(literal)));
    }
  }
}
