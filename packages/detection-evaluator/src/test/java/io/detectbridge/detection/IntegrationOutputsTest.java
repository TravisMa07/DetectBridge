package io.detectbridge.detection;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class IntegrationOutputsTest {
  static final Path ROOT = Path.of(System.getProperty("repository.root"));
  static JsonNode fixture(String name) throws Exception {
    return Json.read(Files.readAllBytes(ROOT.resolve("contracts/integration/v1/fixtures/" + name + ".json")));
  }
  @Test void literalIndependentIdentityVectors() throws Exception {
    for (var vector : fixture("identity-vectors")) {
      List<Object> parts = new ArrayList<>(); var preimage = vector.get("preimage");
      for (int i = 1; i < preimage.size(); i++) parts.add(preimage.get(i));
      assertEquals(vector.get("expected").asString(), IntegrationOutputs.identity(preimage.get(0).asString(), parts.toArray()));
    }
  }
  @Test void literalBudgetCountsMembershipAndMatches() throws Exception {
    var evaluator = new Evaluator(Json.bytes(SelectionTest.plan()));
    var expected = fixture("expectations");
    var compact = evaluator.compact(Json.bytes(SelectionTest.event()), true, 7);
    assertEquals(expected.get("counts"), compact.get("counts"));
    assertEquals(expected.get("matched_ids").get(0), compact.at("/matched/0/id"));
    assertEquals(1, compact.get("matched").size());
    for (var diagnostic : compact.get("diagnostics"))
      assertEquals(expected.get(diagnostic.get("category").asString() + "_bits"), diagnostic.at("/rule_set/bits"));
    var event = SelectionTest.event();
    for (var mapping : evaluator.planSnapshot().get("mapping_profiles"))
      if (mapping.at("/source/id").equals(event.at("/detectbridge/source_contract/id")))
        ((ObjectNode) event.at("/detectbridge/processing")).put("mapping", mapping.get("id").asString() + "/" + mapping.get("version").asString());
    var outputs = new IntegrationOutputs(evaluator).outputs(event, null, compact);
    assertEquals(1, outputs.get("detections").size()); assertEquals(2, outputs.get("diagnostics").size());
    assertEquals(compact.get("counts"), outputs.at("/tagged/counts"));
  }
  @Test void deterministicContentReplayVersionAndTamper() throws Exception {
    // Use actual parser-backed source/profile snapshots so mapping versions are truthful.
    JsonNode plan = Json.read(Files.readAllBytes(ROOT.resolve(".cache/detection/mapped-plan.json")));
    var evaluator = new Evaluator(Json.bytes(plan));
    var processor = new IntegrationOutputs(evaluator);
    ObjectNode event = (ObjectNode) Json.read(Files.readAllBytes(ROOT.resolve("contracts/detection/v1/fixtures/positive.event.json")));
    // P09 normalizer names do not claim this mapping profile. Bind the explicit P10 test mapping.
    var mapping = plan.get("mapping_profiles").get(0);
    for (var m : plan.get("mapping_profiles")) if (m.at("/source/id").equals(event.at("/detectbridge/source_contract/id"))) mapping = m;
    ((ObjectNode) event.at("/detectbridge/processing")).put("mapping", mapping.get("id").asString() + "/" + mapping.get("version").asString());
    var original = processor.process(event, null); processor.verify(original, null);
    assertEquals(0, original.at("/tagged/attribution/external_inputs").size());
    assertEquals(event.at("/detectbridge/processing"), original.at("/tagged/attribution/processing"));
    assertEquals(plan.get("compiler"), original.at("/tagged/attribution/compiler"));
    assertEquals(plan.get("evaluator"), original.at("/tagged/attribution/evaluator"));
    assertEquals(evaluator.bundle(), original.at("/tagged/attribution/bundle_sha256").asString());
    ObjectNode receipt = event.deepCopy();
    ((ObjectNode) receipt.get("event")).put("ingested", "2026-01-02T00:00:00Z");
    ((ObjectNode) receipt.at("/detectbridge/time")).put("processed", "2026-01-02T00:00:01Z");
    var received = processor.process(receipt, null);
    assertEquals(receipt, received.at("/tagged/event"));
    assertEquals(original.at("/tagged/processing_id"), received.at("/tagged/processing_id"));
    assertEquals(IntegrationOutputs.contentHash(original), IntegrationOutputs.contentHash(received));
    processor.verify(received, null);
    assertEquals(original, processor.process(event, null));
    ObjectNode replay = event.deepCopy(); ((ObjectNode) replay.get("detectbridge")).put("run_id", "00000000-0000-4000-8000-000000000002");
    var rerun = processor.process(replay, null);
    assertEquals(original.at("/tagged/event/event/id"), rerun.at("/tagged/event/event/id"));
    assertNotEquals(original.at("/tagged/processing_id"), rerun.at("/tagged/processing_id"));
    assertNotEquals(original.at("/detections/0/detection_id"), rerun.at("/detections/0/detection_id"));
    ObjectNode changedVersion = event.deepCopy(); ((ObjectNode) changedVersion.at("/detectbridge/processing")).put("parser", "test-parser/2.0.0");
    assertNotEquals(original.at("/tagged/processing_id"), processor.process(changedVersion, null).at("/tagged/processing_id"));
    for (String pointer : List.of("/tagged/attribution/compiler", "/tagged/version", "/detections/0/detection_id", "/tagged/counts/matched")) {
      ObjectNode tampered = ((ObjectNode) original).deepCopy();
      int slash = pointer.lastIndexOf('/'); ((ObjectNode) tampered.at(pointer.substring(0, slash))).put(pointer.substring(slash + 1), "tampered");
      assertThrows(IllegalArgumentException.class, () -> processor.verify(tampered, null));
    }
    ObjectNode broken = event.deepCopy(); ((ObjectNode) broken.get("process")).putNull("executable");
    assertThrows(IllegalArgumentException.class, () -> processor.process(broken, null));
    assertThrows(IllegalArgumentException.class, () -> new IntegrationOutputs(new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/plan.json")))));
  }
  @Test void oversizeEventsAndRuleMetadataFailVisibly() throws Exception {
    var plan = MappingProfilesTest.plan();
    var notices = ((ObjectNode) plan.at("/rules/0/provenance")).putArray("notices");
    for (int i = 0; i < 16; i++) notices.add("😀".repeat(4096));
    SelectionTest.rehash(plan);
    var processor = new IntegrationOutputs(new Evaluator(Json.bytes(plan)));
    ObjectNode event = (ObjectNode) Json.read(Files.readAllBytes(ROOT.resolve("contracts/detection/v1/fixtures/positive.event.json")));
    for (var mapping : plan.get("mapping_profiles"))
      if (mapping.at("/source/id").equals(event.at("/detectbridge/source_contract/id")))
        ((ObjectNode) event.at("/detectbridge/processing")).put("mapping", mapping.get("id").asString() + "/" + mapping.get("version").asString());
    assertEquals("integration_document_limit", assertThrows(IllegalArgumentException.class, () -> processor.process(event, null)).getMessage());
    ((ObjectNode) event.get("source_fields")).put("oversize", "x".repeat(1024 * 1024));
    assertEquals("integration_event_limit", assertThrows(IllegalArgumentException.class, () -> processor.process(event, null)).getMessage());
  }
  @Test void maximumRuleCountUsesOneBoundedMembershipGroup() throws Exception {
    ObjectNode plan = SelectionTest.plan(); var rules = plan.putArray("rules");
    JsonNode template = SelectionTest.plan().get("rules").get(0);
    for (int i = 0; i < 100; i++) {
      ObjectNode rule = ((ObjectNode) template).deepCopy();
      String id = String.format(Locale.ROOT, "80000000-0000-4000-8000-%012d", i);
      rule.put("id", id); ((ObjectNode) rule.get("provenance")).put("rule_id", id); rules.add(rule);
    }
    SelectionTest.rehash(plan); var evaluator = new Evaluator(Json.bytes(plan));
    ObjectNode event = SelectionTest.event(); ((ObjectNode) event.at("/detectbridge/source_contract")).put("id", "unknown");
    var compact = evaluator.evaluateCompact(Json.bytes(event));
    assertEquals(100, compact.at("/counts/configuration_blocked").asInt());
    assertEquals(1, compact.get("diagnostics").size());
    assertEquals("fffffffffffffffffffffffff", compact.at("/diagnostics/0/rule_set/bits").asString());
    assertTrue(Json.bytes(compact).length < 1024);
  }
}
