package io.detectbridge.linux;

import static io.detectbridge.linux.Fixtures.*;
import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;

class AuditReplayTest {
  @TempDir Path directory;

  Path plan(String name) {
    return Path.of(System.getProperty("repository.root"), ".cache/linux-adapters/plans/" + name + ".json");
  }
  String row(Boundary.Input input) {
    return new String(Json.bytes(Json.MAPPER.valueToTree(Map.of("raw", input.raw(), "context", input.context()))), StandardCharsets.UTF_8) + "\n";
  }
  List<JsonNode> read(Path output) throws Exception {
    List<JsonNode> result = new ArrayList<>();
    for (String line : Files.readAllLines(output)) result.add(Json.read(line.getBytes(StandardCharsets.UTF_8)));
    return result;
  }
  String complete(String run) throws Exception {
    var context = context(false); context.put("run_id", run); StringBuilder rows = new StringBuilder();
    for (int i = 0; i < COMPLETE.size(); i++) rows.append(row(input(line(COMPLETE.get(i)), i, context)));
    rows.append(row(input(line("EOE"), 5, context))); return rows.toString();
  }
  @Test void actualEvaluatorAndImmutableLateMembershipWithIncompleteDatasetEnd() throws Exception {
    Path input = directory.resolve("input"), output = directory.resolve("output");
    var other = context(false); other.put("run_id", RUN2);
    Files.writeString(input, complete(RUN) + row(input(line("EOE"), 6, context(false)))
        + row(input(line(COMPLETE.get(0)), 0, other)));
    assertEquals(8, AuditReplay.replay(input, output, plan("image-match")));
    var published = read(output);
    var originals = published.stream().filter(n -> n.path("kind").asString().equals("input")).toList();
    assertEquals(8, originals.size());
    assertEquals(input(line(COMPLETE.get(0)), 0, context(false)).raw(), originals.get(0).get("raw"));
    var events = published.stream().filter(n -> n.path("kind").asString().equals("event")).toList();
    assertEquals(2, events.size());
    assertEquals(1, events.get(0).at("/evaluation/counts/matched").asInt());
    assertEquals(1, events.get(1).at("/evaluation/counts/quality_skipped").asInt());
    var manifests = published.stream().filter(n -> n.path("kind").asString().equals("manifest")).toList();
    assertEquals(2, manifests.size());
    assertEquals("source_boundary", manifests.get(0).at("/document/closure").asString());
    assertEquals("dataset_end", manifests.get(1).at("/document/closure").asString());
    assertFalse(manifests.get(1).at("/document/eligible").asBoolean());
    var late = published.stream().filter(n -> n.path("kind").asString().equals("preservation")).findFirst().orElseThrow();
    assertEquals("late_evidence", late.at("/document/code").asString());
    assertEquals(manifests.get(0).at("/document/manifest_id"), late.at("/document/original_manifest_id"));
  }
  @Test void replayRunsPreserveEvidenceIdentityAndIndependentNonmatchBlockedResults() throws Exception {
    Path input = directory.resolve("input"), output = directory.resolve("output");
    Files.writeString(input, complete(RUN) + complete(RUN2));
    for (var pair : List.of(List.of("image-nonmatch", "unmatched"), List.of("command-blocked", "configuration_blocked"))) {
      assertEquals(12, AuditReplay.replay(input, output, plan(pair.get(0))));
      var events = read(output).stream().filter(n -> n.path("kind").asString().equals("event")).toList();
      assertEquals(2, events.size());
      assertEquals(events.get(0).at("/document/event/id"), events.get(1).at("/document/event/id"));
      assertEquals(events.get(0).at("/document/detectbridge/evidence"), events.get(1).at("/document/detectbridge/evidence"));
      assertEquals(RUN, events.get(0).at("/evaluation/run_id").asString());
      assertEquals(RUN2, events.get(1).at("/evaluation/run_id").asString());
      for (var event : events) assertEquals(1, event.at("/evaluation/counts/" + pair.get(1)).asInt());
    }
  }
  @Test void auditReceiptClocksDoNotChangeSemanticIdentityOrContent() throws Exception {
    var processor = new io.detectbridge.detection.IntegrationOutputs(new io.detectbridge.detection.Evaluator(Files.readAllBytes(plan("image-match"))));
    JsonNode first = null, firstManifest = null;
    for (String received : List.of("2026-01-01T00:00:02Z", "2026-01-01T00:00:03Z")) {
      var context = context(false); context.set("receipt", Json.MAPPER.valueToTree(Map.of("received", received)));
      var assembler = new Assembler(new Time(), Assembler.Limits.defaults()); var sink = new Sink();
      Fixtures.complete(assembler, sink, context, 0); assembler.accept(input(line("EOE"), 5, context), sink);
      var event = sink.events().get(0); var manifest = sink.manifests().get(0);
      var integration = processor.process(event, manifest); processor.verify(integration, manifest);
      assertEquals(event, integration.at("/tagged/event"));
      if (first == null) { first = integration; firstManifest = manifest; }
      else {
        assertNotEquals(firstManifest.get("manifest_id"), manifest.get("manifest_id"));
        assertEquals(first.at("/tagged/processing_id"), integration.at("/tagged/processing_id"));
        assertEquals(first.at("/detections/0/detection_id"), integration.at("/detections/0/detection_id"));
        assertEquals(io.detectbridge.detection.IntegrationOutputs.contentHash(first), io.detectbridge.detection.IntegrationOutputs.contentHash(integration));
      }
    }
  }
  @Test void integratedAuditConsumerRequiresExactManifestAndPreservesLateEvidence() throws Exception {
    Path input = directory.resolve("integrated-input"), output = directory.resolve("integrated-output");
    var incomplete = context(false); incomplete.put("run_id", RUN2);
    Files.writeString(input, complete(RUN) + row(input(line("EOE"), 6, context(false)))
        + row(input(line("EOE"), 7, incomplete)));
    for (String name : List.of("image-match", "image-nonmatch", "command-blocked")) {
      AuditReplay.replay(input, output, plan(name), true);
      var published = read(output);
      var events = published.stream().filter(n -> n.has("integration")).toList(); assertEquals(2, events.size());
      var manifests = published.stream().filter(n -> n.path("kind").asString().equals("manifest")).map(n -> n.get("document")).toList();
      var evaluator = new io.detectbridge.detection.Evaluator(Files.readAllBytes(plan(name)));
      var processor = new io.detectbridge.detection.IntegrationOutputs(evaluator);
      for (int i = 0; i < 2; i++) {
        var integration = events.get(i).get("integration"); var event = events.get(i).get("document"); var manifest = manifests.get(i);
        String expected = name.equals("command-blocked") ? "configuration_blocked" : i == 1 ? "quality_skipped" : name.equals("image-match") ? "matched" : "unmatched";
        for (String outcome : io.detectbridge.detection.Evaluator.OUTCOMES)
          assertEquals(outcome.equals(expected) ? 1 : 0, integration.at("/tagged/counts/" + outcome).asInt());
        assertEquals(event, integration.at("/tagged/event"));
        assertEquals(manifest.get("manifest_id"), integration.at("/tagged/manifest/manifest_id"));
        processor.verify(integration, manifest);
        assertThrows(IllegalArgumentException.class, () -> processor.process(event, null));
        var tampered = ((tools.jackson.databind.node.ObjectNode) manifest).deepCopy(); tampered.put("policy", "tampered");
        var policyTamper = tampered;
        assertThrows(IllegalArgumentException.class, () -> processor.process(event, policyTamper));
        var changedEligibility = ((tools.jackson.databind.node.ObjectNode) manifest).deepCopy();
        changedEligibility.put("eligible", !manifest.get("eligible").asBoolean());
        changedEligibility.remove("manifest_id"); changedEligibility.put("manifest_id", "sha256:" + Boundary.hash(changedEligibility));
        assertThrows(IllegalArgumentException.class, () -> processor.process(event, changedEligibility));
        // Rehashing a modified member still cannot bind it to this event.
        tampered = ((tools.jackson.databind.node.ObjectNode) manifest).deepCopy();
        ((tools.jackson.databind.node.ObjectNode) tampered.at("/members/0")).put("evidence_sha256", "0".repeat(64));
        tampered.remove("manifest_id"); tampered.put("manifest_id", "sha256:" + Boundary.hash(tampered));
        var memberTamper = tampered;
        assertThrows(IllegalArgumentException.class, () -> processor.process(event, memberTamper));
      }
      var late = published.stream().filter(n -> n.path("kind").asString().equals("preservation")).findFirst().orElseThrow();
      assertFalse(late.has("integration")); assertEquals(manifests.get(0).get("manifest_id"), late.at("/document/original_manifest_id"));
    }
  }
  @Test void malformedOversizedReferencedOrAliasedInputsNeverReplacePriorPublication() throws Exception {
    Path input = directory.resolve("input"), output = directory.resolve("output");
    Files.writeString(output, "prior-reviewed-publication\n"); byte[] previous = Files.readAllBytes(output);
    var supplied = input(line(COMPLETE.get(0)), 0, context(false));
    var reference = supplied.raw(); ((tools.jackson.databind.node.ObjectNode) reference.get("evidence")).remove("inline");
    ((tools.jackson.databind.node.ObjectNode) reference.get("evidence")).set("reference", Json.MAPPER.valueToTree(Map.of(
        "uri", "urn:sha256:" + "a".repeat(64), "object_sha256", "a".repeat(64))));
    for (String invalid : List.of(complete(RUN) + "{\"broken\":true}\n", "x".repeat(Json.MAX_VALUE + 1),
        row(new Boundary.Input(reference, supplied.context(), supplied.bytes())))) {
      Files.writeString(input, invalid);
      assertThrows(IllegalArgumentException.class, () -> AuditReplay.replay(input, output, plan("image-match")));
      assertArrayEquals(previous, Files.readAllBytes(output));
      try (var files = Files.list(directory)) { assertEquals(2, files.count()); }
    }
    assertThrows(IllegalArgumentException.class, () -> AuditReplay.replay(input, input, plan("image-match")));
    assertThrows(IllegalArgumentException.class, () -> AuditReplay.replay(input, plan("image-match"), plan("image-match")));
  }
}
