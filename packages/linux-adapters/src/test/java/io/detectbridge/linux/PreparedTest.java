package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import java.util.*;
import org.junit.jupiter.api.Test;

class PreparedTest {
  @Test void detachedPreparationDoesNotAdmitAndDrainsOneOriginalGroupAtATime() throws Exception {
    Time time = new Time(); Assembler a = new Assembler(time, Assembler.Limits.defaults());
    var first = input(line(COMPLETE.get(0)), 0, context(false));
    byte[] empty = a.snapshot(); var admission = a.prepare(first);
    assertArrayEquals(empty, a.snapshot()); assertTrue(admission.consumed());
    a = Assembler.restore(time, Assembler.Limits.defaults(), admission.nextSnapshot());
    var second = input(line(COMPLETE.get(0)).replace(":7)", ":8)"), 1, context(false));
    admission = a.prepare(second); a = Assembler.restore(time, Assembler.Limits.defaults(), admission.nextSnapshot());
    byte[] before = a.snapshot(); time.millis += 30000;
    var closure = a.prepareTick(); assertFalse(closure.consumed()); assertEquals(2, closure.outputs().size());
    assertArrayEquals(before, a.snapshot());
    assertEquals("timeout", closure.outputs().get(1).get("closure").asString());
    a = Assembler.restore(time, Assembler.Limits.defaults(), closure.nextSnapshot());
    closure = a.prepareTick(); assertFalse(closure.consumed()); assertEquals(2, closure.outputs().size());
    a = Assembler.restore(time, Assembler.Limits.defaults(), closure.nextSnapshot());
    assertTrue(a.prepareTick().consumed()); assertEquals(Long.MAX_VALUE, a.nextDeadline());
    assertEquals("late_evidence", a.prepare(input(line(COMPLETE.get(0)), 20, context(false))).outputs().get(0).get("code").asString());
  }
  @Test void preparedEndClosesGroupsBeforeMarkingRunEndedAndRetryIsIdempotent() throws Exception {
    Time time = new Time(); Assembler a = new Assembler(time, Assembler.Limits.defaults());
    var record = input(line(COMPLETE.get(0)), 0, context(false));
    var proposed = a.prepare(record); a = Assembler.restore(time, Assembler.Limits.defaults(), proposed.nextSnapshot());
    assertTrue(a.prepare(record).outputs().isEmpty());
    proposed = a.prepareEnd(RUN); assertFalse(proposed.consumed());
    assertEquals("dataset_end", proposed.outputs().get(1).get("closure").asString());
    a = Assembler.restore(time, Assembler.Limits.defaults(), proposed.nextSnapshot());
    proposed = a.prepareEnd(RUN); assertTrue(proposed.consumed());
    a = Assembler.restore(time, Assembler.Limits.defaults(), proposed.nextSnapshot());
    assertEquals("after_dataset_end", a.prepare(input(line("EOE").replace(":7)", ":9)"), 5, context(false))).outputs().get(0).get("code").asString());
  }
}
