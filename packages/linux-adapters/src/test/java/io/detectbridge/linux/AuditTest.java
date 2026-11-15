package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;

class AuditTest {
  static Audit.Record parse(String record) { return Audit.parse(line(record).getBytes(StandardCharsets.UTF_8)); }
  static Audit.Assessment assess(List<String> records) { return Audit.assess(records.stream().map(AuditTest::parse).toList()); }
  @Test void exactTimeAndAllTokenOccurrencesSurvive() {
    var record = parse("PATH item=0 name=\"x\" name=78");
    assertEquals("1767225600.001", record.timestamp()); assertEquals("7", record.serial());
    assertEquals(List.of(new Audit.Token("item", "0"), new Audit.Token("name", "\"x\""), new Audit.Token("name", "78")), record.tokens());
    var assessment = assess(COMPLETE); assertTrue(assessment.eligible());
    assertEquals(List.of("whoami", "", "whoami"), assessment.args());
    assertEquals(5, assessment.fields().get("audit_records").size());
    assertEquals(2, assessment.fields().get("paths").size());
    assertEquals("/usr/bin/whoami", assessment.fields().get("exe").asString());
    assertEquals(assessment.fields().get("arguments"), io.detectbridge.transport.Json.MAPPER.valueToTree(assessment.args()));
    assertEquals("/usr/bin/whoami", assessment.process().get("executable"));
    assertFalse(assessment.process().containsKey("command_line"));
  }
  @Test void hexAndFragmentsJoinByPositionBeforeUnicodeDecode() {
    List<String> records = new ArrayList<>(COMPLETE);
    records.set(1, "EXECVE argc=2 a0=77686F616D69 a1_len=8 a1[1]=6364 a1[0]=6162");
    assertEquals(List.of("whoami", "abcd"), assess(records).args()); assertTrue(assess(records).eligible());
    records.set(1, "EXECVE argc=1 a0_len=8 a0[1]=9880 a0[0]=F09F");
    assertEquals(List.of("😀"), assess(records).args()); assertTrue(assess(records).eligible());
    records.set(1, "EXECVE argc=1 a0_len=4 a0[1]=\"cd\" a0[0]=\"ab\"");
    assertEquals(List.of("abcd"), assess(records).args()); assertTrue(assess(records).eligible());
  }
  @Test void supportedExecutionPairsAreExplicitAndUnknownsStayUnsupported() {
    for (String pair : List.of("c000003e/59", "c000003e/322", "40000003/11", "40000003/358", "c00000b7/221", "c00000b7/281")) {
      List<String> records = new ArrayList<>(COMPLETE); String[] p = pair.split("/");
      records.set(0, records.get(0).replace("c000003e", p[0]).replace("syscall=59", "syscall=" + p[1]));
      assertTrue(assess(records).eligible(), pair);
    }
    for (String change : List.of("arch=deadbeef", "syscall=0", "syscall=1073742344", "success=no", "exit=-1")) {
      List<String> records = new ArrayList<>(COMPLETE); String name = change.split("=")[0];
      records.set(0, records.get(0).replaceAll(name + "=[^ ]+", change)); assertFalse(assess(records).eligible(), change);
    }
  }
  @Test void independentCountConflictAndEncodingFailuresSkip() {
    for (String args : List.of("argc=3 a0=\"x\" a2=\"z\"", "argc=1 a0=\"x\" a0=\"x\"",
        "argc=1 a0_len=4 a0[0]=6162 a0[1]=6364", "argc=1 a0_len=4 a0[1]=6162",
        "argc=1 a0=FF", "argc=1 a0=00", "argc=1 a0=6", "argc=1 a0=\"x\" a0[0]=78",
        "argc=1 a0_len=2 a0[0]=78 a0[0]=78", "argc=1 a0_len=2 a0[0]=\"x\" a0[1]=78",
        "argc=0 a1_len=2", "argc=4097")) {
      List<String> records = new ArrayList<>(COMPLETE); records.set(1, "EXECVE " + args);
      assertFalse(assess(records).eligible(), args);
    }
    for (String extra : List.of("EXECVE a0=\"whoami\"", "CWD cwd=\"/tmp\"", "PATH item=0 name=\"/x\"", "UNKNOWN x=1")) {
      List<String> records = new ArrayList<>(COMPLETE); records.add(extra); assertFalse(assess(records).eligible(), extra);
    }
    List<String> sparse = new ArrayList<>(COMPLETE); sparse.set(4, "PATH item=2 name=\"/x\"");
    assertFalse(assess(sparse).eligible());
    for (int i = 0; i < COMPLETE.size(); i++) {
      List<String> missing = new ArrayList<>(COMPLETE); missing.remove(i); assertFalse(assess(missing).eligible());
    }
  }
  @Test void malformedFramingAndHeaderDoNotCreateRecords() {
    for (String text : List.of("garbage", "type=EOE msg=audit(1.1234567890:7):\n", line("EOE") + line("EOE"),
        "type=CWD msg=audit(1.001:7): cwd=\"unterminated\n", "type=EOE msg=audit(999999999999999999999.1:7):\n"))
      assertThrows(IllegalArgumentException.class, () -> Audit.parse(text.getBytes(StandardCharsets.UTF_8)), text);
  }
  @Test void proctitleRetainsNulSeparatedBytesWithoutBecomingCommandLine() {
    List<String> records = new ArrayList<>(COMPLETE); records.add("PROCTITLE proctitle=61006200");
    var result = assess(records); assertTrue(result.eligible());
    assertEquals("YQBiAA==", result.fields().get("proctitle_bytes_base64").asString());
    assertEquals(List.of("whoami", "", "whoami"), result.args());
    assertFalse(result.process().containsKey("command_line"));
    records.add("PROCTITLE proctitle=6300"); assertFalse(assess(records).eligible());
  }

  @Test void missingAndConflictingRequiredSlotsHaveDifferentFindings() {
    List<String> missing = new ArrayList<>(COMPLETE);
    missing.set(0, missing.get(0).replace(" pid=42", ""));
    assertEquals(List.of("required_slot_missing"), assess(missing).findings());
    List<String> conflicting = new ArrayList<>(COMPLETE);
    conflicting.set(0, conflicting.get(0) + " pid=43");
    assertEquals(List.of("slot_conflict"), assess(conflicting).findings());
  }

}
