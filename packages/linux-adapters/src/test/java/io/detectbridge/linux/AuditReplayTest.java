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
