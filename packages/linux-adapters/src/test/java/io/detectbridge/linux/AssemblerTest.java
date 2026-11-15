package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import io.detectbridge.transport.Json;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class AssemblerTest {
  @Test void completeMembershipIdentityAndLateLinksAreImmutable() throws Exception {
    Time time = new Time(); Sink sink = new Sink(); ObjectNode c = context(false);
    Assembler a = new Assembler(time, Assembler.Limits.defaults()); complete(a, sink, c, 0);
    assertTrue(sink.outputs.isEmpty()); a.accept(input(line("EOE"), 5, c), sink);
    JsonNode e = sink.events().get(0), m = sink.manifests().get(0);
    assertEquals("eligible", e.at("/detectbridge/quality/eligibility").asString());
    assertEquals(List.of("whoami", "", "whoami"), Json.MAPPER.convertValue(e.at("/process/args"), List.class));
    assertFalse(e.has("file")); assertFalse(e.get("process").has("command_line"));
    assertEquals(6, m.get("members").size()); assertTrue(m.get("eligible").asBoolean());
    assertEquals("sha256:45c509e3f82ee0b547bffd5b241b0f6f18bf55a81646572f673524276f3dd12f", e.at("/event/id").asString());
    assertEquals("sha256:d844c75430581095cf915d0f6ccd412a21b181e79d9c525293e9bf38178ee119", m.at("/members/0/record_id").asString());
    assertEquals("4554fb95fca6d5ed7e8f3ba562cf89bf8cec09586c526e0f6e228d59f8a5006f", m.at("/members/0/evidence_sha256").asString());
    assertEquals(42, e.at("/process/pid").asInt());
    assertEquals(FIRST, e.at("/detectbridge/time/first_observed").asString());
    assertEquals("1767225600.001", m.at("/key/audit_timestamp").asString());
    byte[] before = Json.bytes(m);
    a.accept(input(line("PATH item=3 name=\"late\""), 6, c), sink);
    assertEquals(1, sink.events().size()); assertArrayEquals(before, Json.bytes(m));
    assertEquals(m.get("manifest_id"), sink.diagnostics().get(0).get("original_manifest_id"));
    assertEquals("late_evidence", sink.diagnostics().get(0).get("code").asString());
    byte[] state = a.snapshot(); a.accept(input(line("PATH item=3 name=\"late\""), 6, c), sink);
    assertArrayEquals(state, a.snapshot()); assertEquals(1, sink.diagnostics().size());
  }
  @Test void retryIsIdempotentButDistinctOccurrencesConflict() throws Exception {
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults()); ObjectNode c = context(false);
    complete(a, sink, c, 0); byte[] state = a.snapshot();
    a.accept(input(line(COMPLETE.get(1)), 1, c), sink); assertArrayEquals(state, a.snapshot());
    a.accept(input(line(COMPLETE.get(1)), 7, c), sink); a.accept(input(line("EOE"), 8, c), sink);
    assertEquals(7, sink.manifests().get(0).get("members").size());
    assertFalse(sink.manifests().get(0).get("eligible").asBoolean());
    assertEquals("skipped", sink.events().get(0).at("/detectbridge/quality/eligibility").asString());
    assertThrows(IllegalArgumentException.class, () -> a.accept(input(line("EOE"), 1, c), sink));
  }
  @Test void reorderAndAllScopeDimensionsRemainIndependent() throws Exception {
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    List<ObjectNode> contexts = new ArrayList<>();
    for (String dimension : List.of("original", "host", "run", "generation", "instance")) {
      ObjectNode c = context(false);
      switch (dimension) {
        case "host" -> ((ObjectNode)c.get("host_binding")).put("host_id", "host-b");
        case "run" -> c.put("run_id", RUN2);
        case "generation" -> ((ObjectNode)c.get("source_generation")).put("id", "boot-b");
        case "instance" -> ((ObjectNode)c.get("source")).put("instance", "b");
      }
      bind(c);
      contexts.add(c);
    }
    for (int i : List.of(4, 2, 0, 3, 1)) for (int j = 0; j < contexts.size(); j++)
      a.accept(input(line(COMPLETE.get(i)), 100 * j + i, contexts.get(j)), sink);
    assertEquals(5, Json.MAPPER.readTree(a.snapshot()).get("groups").size());
    for (int j = 0; j < contexts.size(); j++) a.accept(input(line("EOE"), 100*j+5, contexts.get(j)), sink);
    assertEquals(5, sink.events().size());
    assertTrue(sink.manifests().stream().allMatch(m -> m.get("eligible").asBoolean()));
  }
  @Test void missingScopeIsSeparateAndEarlyEoeNeverReopens() throws Exception {
    for (String missing : List.of("host_binding", "source_generation")) {
      Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults()); ObjectNode c = context(false); c.remove(missing);
      a.accept(input(line("EOE"), 0, c), sink); a.accept(input(line("EOE"), 1, c), sink);
      assertEquals(2, sink.diagnostics().size()); assertTrue(sink.events().isEmpty());
      assertEquals(0, Json.MAPPER.readTree(a.snapshot()).get("groups").size());
      assertEquals("identity_missing", sink.diagnostics().get(0).get("code").asString());
    }
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults()); ObjectNode c = context(false);
    a.accept(input(line("EOE"), 9, c), sink); complete(a, sink, c, 0);
    assertEquals(1, sink.manifests().size()); assertFalse(sink.manifests().get(0).get("eligible").asBoolean());
    assertEquals(5, sink.diagnostics().size());
  }
  @Test void closureDoesNotProveQualityAndDeadlineIsAbsolute() throws Exception {
    for (String closure : List.of("timeout", "dataset_end", "source_boundary")) {
      for (boolean full : List.of(true, false)) {
        Time time = new Time(); Sink sink = new Sink(); ObjectNode c = context(false);
        Assembler a = new Assembler(time, Assembler.Limits.defaults());
        a.accept(input(line(COMPLETE.get(0)), 0, c), sink); time.millis += 29999;
        if (full) for (int i = 1; i < COMPLETE.size(); i++) a.accept(input(line(COMPLETE.get(i)), i, c), sink);
        if (closure.equals("timeout")) { a.tick(sink); assertTrue(sink.outputs.isEmpty()); time.millis++; a.tick(sink); }
        if (closure.equals("dataset_end")) a.end(RUN, sink);
        if (closure.equals("source_boundary")) a.boundary(RUN, "original-synthetic", "a", "host-a", "boot-a", sink);
        assertEquals(closure, sink.manifests().get(0).get("closure").asString());
        assertEquals(full, sink.manifests().get(0).get("eligible").asBoolean());
      }
    }
  }
  @Test void persistenceFailureAndPartialStateRoundTripRetainAccounting() throws Exception {
    Time time = new Time(); Sink sink = new Sink(); ObjectNode c = context(false);
    Assembler a = new Assembler(time, Assembler.Limits.defaults());
    complete(a, sink, c, 0); byte[] before = a.snapshot(); sink.fail = true;
    assertThrows(java.io.IOException.class, () -> a.accept(input(line("EOE"), 5, c), sink));
    assertArrayEquals(before, a.snapshot()); assertTrue(sink.outputs.isEmpty()); sink.fail = false;
    Assembler reloaded = Assembler.restore(time, Assembler.Limits.defaults(), before);
    reloaded.accept(input(line("EOE"), 5, c), sink);
    Assembler restored = Assembler.restore(time, Assembler.Limits.defaults(), reloaded.snapshot());
    restored.accept(input(line(COMPLETE.get(0)), 0, c), sink);
    restored.accept(input(line("EOE"), 6, c), sink);
    assertEquals(1, sink.events().size()); assertEquals("late_evidence", sink.diagnostics().get(0).get("code").asString());
    ObjectNode corrupt = (ObjectNode) Json.MAPPER.readTree(before); corrupt.put("version", "9.0.0");
    assertThrows(IllegalArgumentException.class, () -> Assembler.restore(time, Assembler.Limits.defaults(), Json.bytes(corrupt)));
    Assembler.Limits smaller = new Assembler.Limits(255,1048576,1024,33554432,30000,16,100000,33554432);
    assertThrows(IllegalArgumentException.class, () -> Assembler.restore(time, smaller, before));
  }
  @Test void pressureClosesIncompleteAndClosedKnowledgeBackpressures() throws Exception {
    ObjectNode c = context(false); Sink sink = new Sink();
    Assembler a = new Assembler(new Time(), new Assembler.Limits(1,1048576,1,33554432,30000,16,1,33554432));
    a.accept(input(line(COMPLETE.get(0)), 0, c), sink); a.accept(input(line(COMPLETE.get(1)), 1, c), sink);
    assertEquals("resource_limit", sink.manifests().get(0).get("closure").asString());
    assertEquals(1, sink.manifests().get(0).get("members").size()); assertEquals(1, sink.diagnostics().size());
    assertFalse(sink.manifests().get(0).get("eligible").asBoolean());
    byte[] before = a.snapshot(); int count = sink.outputs.size();
    assertThrows(IllegalArgumentException.class, () -> a.accept(input(line("EOE").replace(":7)", ":8)"), 2, c), sink));
    assertArrayEquals(before, a.snapshot()); assertEquals(count, sink.outputs.size());
  }
  @Test void contextDifferencesAreConflictsAndObservationDoesNotChangeAttribution() throws Exception {
    Sink sink = new Sink(); ObjectNode c = context(false); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    complete(a, sink, c, 0); ObjectNode other = c.deepCopy();
    other.put("first_observed", "2026-01-01T00:00:02Z");
    ((ObjectNode)other.get("host_binding")).put("revision", "changed-binding");
    bind(other);
    a.accept(input(line("EOE"), 5, other), sink);
    assertFalse(sink.manifests().get(0).get("eligible").asBoolean());
    assertEquals(FIRST, sink.events().get(0).at("/event/created").asString());
  }
  @Test void sameRetainedEvidenceInSeparateRunsKeepsP03IdentityAndSeparateOutputs() throws Exception {
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    ObjectNode first = context(false), second = context(false); second.put("run_id", RUN2);
    for (int i = 0; i < COMPLETE.size(); i++) {
      a.accept(input(line(COMPLETE.get(i)), i, first), sink);
      a.accept(input(line(COMPLETE.get(i)), i, second), sink);
    }
    a.accept(input(line("EOE"), 5, first), sink); a.accept(input(line("EOE"), 5, second), sink);
    assertEquals(2, sink.events().size());
    assertEquals(sink.events().get(0).at("/event/id"), sink.events().get(1).at("/event/id"));
    assertNotEquals(sink.events().get(0).at("/detectbridge/run_id"), sink.events().get(1).at("/detectbridge/run_id"));
    assertNotEquals(sink.manifests().get(0).get("manifest_id"), sink.manifests().get(1).get("manifest_id"));
  }

}
