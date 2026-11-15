package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import io.detectbridge.transport.Json;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class ResourceTest {
  @Test void originalBytesPendingOverheadAndOpenGroupPressurePreserveEveryOccurrence() throws Exception {
    for (String kind : List.of("bytes", "pending", "groups")) {
      int groupBytes = kind.equals("bytes") ? line(COMPLETE.get(0)).getBytes(java.nio.charset.StandardCharsets.UTF_8).length : 1048576;
      int pendingBytes = kind.equals("pending") ? 13 : 33554432;
      Assembler a = new Assembler(new Time(), new Assembler.Limits(256,groupBytes,1,pendingBytes,30000,16,100000,33554432));
      Sink sink = new Sink(); ObjectNode c = context(false);
      a.accept(input(line(COMPLETE.get(0)), 0, c), sink);
      String second = kind.equals("groups") ? line(COMPLETE.get(1)).replace(":7)", ":8)") : line(COMPLETE.get(1));
      a.accept(input(second, 1, c), sink); a.end(RUN, sink);
      Set<String> accounted = new HashSet<>();
      for (JsonNode m : sink.manifests()) for (JsonNode member : m.get("members")) accounted.add(member.get("record_id").asString());
      for (JsonNode d : sink.diagnostics()) accounted.add(d.at("/member/record_id").asString());
      assertEquals(Set.of(input(line(COMPLETE.get(0)), 0, c).raw().get("record_id").asString(),
          input(second, 1, c).raw().get("record_id").asString()), accounted);
      assertTrue(sink.manifests().stream().anyMatch(m -> m.get("closure").asString().equals("resource_limit")));
      assertTrue(sink.manifests().stream().noneMatch(m -> m.get("eligible").asBoolean()));
    }
  }
  @Test void closedByteAndActiveRunBoundsStopAdmissionWithoutEviction() throws Exception {
    Sink sink = new Sink(); ObjectNode c = context(false);
    Assembler tiny = new Assembler(new Time(), new Assembler.Limits(256,1048576,1024,33554432,30000,16,100000,32));
    byte[] before = tiny.snapshot();
    assertThrows(IllegalArgumentException.class, () -> tiny.accept(input(line("EOE"), 0, c), sink));
    assertArrayEquals(before, tiny.snapshot()); assertTrue(sink.outputs.isEmpty());
    Assembler a = new Assembler(new Time(), new Assembler.Limits(256,1048576,1024,33554432,30000,1,100000,33554432));
    a.accept(input(line(COMPLETE.get(0)), 0, c), sink); ObjectNode other = c.deepCopy(); other.put("run_id", RUN2);
    byte[] active = a.snapshot();
    assertThrows(IllegalArgumentException.class, () -> a.accept(input(line(COMPLETE.get(0)), 0, other), sink));
    assertArrayEquals(active, a.snapshot());
    a.end(RUN, sink); a.accept(input(line("EOE"), 0, other), sink);
    assertEquals(2, Json.MAPPER.readTree(a.snapshot()).get("runs").size());
    a.accept(input(line(COMPLETE.get(1)), 1, c), sink);
    assertEquals("late_evidence", sink.diagnostics().get(0).get("code").asString());
    a.accept(input(line("EOE").replace(":7)", ":8)"), 2, c), sink);
    assertEquals("after_dataset_end", sink.diagnostics().get(1).get("code").asString());
  }
  @Test void timeoutAfterRestoreUsesOriginalAbsoluteAge() throws Exception {
    Time time = new Time(); Sink sink = new Sink(); Assembler a = new Assembler(time, Assembler.Limits.defaults());
    a.accept(input(line(COMPLETE.get(0)), 0, context(false)), sink); time.millis += 30000;
    a = Assembler.restore(time, Assembler.Limits.defaults(), a.snapshot()); a.tick(sink);
    assertEquals("timeout", sink.manifests().get(0).get("closure").asString());
    assertFalse(sink.manifests().get(0).get("eligible").asBoolean());
  }
  @Test void largeRecordStateRoundTripAndOversizedEventPreserveReferences() throws Exception {
    String payload = line("UNKNOWN data=" + "a".repeat(800000));
    Sink sink = new Sink(); Time time = new Time();
    Assembler a = new Assembler(time, Assembler.Limits.defaults());
    Boundary.Input large = input(payload, 0, context(false)); a.accept(large, sink);
    // Base64 state exceeds the 1 MiB event-reader string limit, exercising the state reader.
    a = Assembler.restore(time, Assembler.Limits.defaults(), a.snapshot());
    a.accept(input(line("EOE"), 1, context(false)), sink);
    assertTrue(sink.events().isEmpty()); assertEquals(1, sink.manifests().size());
    JsonNode manifest = sink.manifests().get(0);
    assertEquals(2, manifest.get("members").size()); assertFalse(manifest.get("eligible").asBoolean());
    assertTrue(manifest.get("findings").toString().contains("output_limit"));
    assertEquals(large.raw().at("/evidence/sha256"), manifest.at("/members/0/evidence_sha256"));
    assertEquals("raw_inline", manifest.at("/members/0/retention").asString());
    assertFalse(manifest.get("members").get(0).has("reference"));
    assertTrue(Json.bytes(manifest).length <= 1048576);
  }

}
