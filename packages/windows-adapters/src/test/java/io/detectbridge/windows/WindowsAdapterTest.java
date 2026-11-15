package io.detectbridge.windows;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class WindowsAdapterTest {
  @TempDir Path temp;
  static final Path ROOT = Path.of(System.getProperty("repository.root"));
  static final String OBSERVED = "2026-11-12T12:00:01.123456789123Z";
  static String fixture(String family) throws IOException {
    return Files.readString(ROOT.resolve("packages/windows-adapters/fixtures/" + family + ".xml"));
  }
  static ObjectNode raw(String text) {
    var raw = Json.MAPPER.createObjectNode();
    raw.put("contract_version", "1.0.0");
    raw.set("source", Json.MAPPER.valueToTree(Map.of("namespace", "synthetic-p11", "instance", "synthetic-origin")));
    raw.set("cursor", Json.MAPPER.valueToTree(Map.of("kind", "native", "value", "synthetic-cursor-0")));
    raw.put("first_observed", OBSERVED);
    raw.set("evidence", Json.MAPPER.valueToTree(Map.of("sha256", Json.sha(text.getBytes(StandardCharsets.UTF_8)), "media_type", "application/xml", "encoding", "utf-8", "inline", text)));
    raw.put("record_id", EnvelopeValidator.recordIdentity(raw));
    return raw;
  }
  static ObjectNode context(JsonNode raw, String family, boolean binding) {
    var source = Boundary.resource(family + ".source.json");
    var mapping = Boundary.resource(family + ".mapping.json");
    var c = Json.MAPPER.createObjectNode();
    c.put("version", "1.0.0"); c.put("run_id", "00000000-0000-4000-8000-000000000001");
    c.set("source", raw.get("source")); c.set("first_observed", raw.get("first_observed"));
    c.set("source_contract", Json.MAPPER.valueToTree(Map.of("id", source.get("id"), "version", "1.0.0", "sha256", Boundary.hash(source), "snapshot", source)));
    c.set("mapping_profile", Json.MAPPER.valueToTree(Map.of("id", mapping.get("id"), "version", "1.0.0", "sha256", mapping.get("sha256"), "declaration", mapping)));
    c.set("parser", Json.MAPPER.valueToTree(Map.of("id", "windows-xml", "version", "1.0.0")));
    if (binding) {
      var h = Json.MAPPER.valueToTree(new TreeMap<>(Map.of("host_id", "synthetic-host-id", "computer", "SYNTHETIC-HOST", "source", raw.get("source"),
          "revision", "synthetic-1", "provenance", List.of("original synthetic fixture"), "kind", "synthetic")));
      ((ObjectNode) h).put("sha256", Boundary.hash(h)); c.set("host_binding", h);
    }
    return c;
  }
  WindowsAdapter.Result adapt(String text, String family, boolean binding) throws IOException {
    var r = raw(text); return new WindowsAdapter().adapt(r, EvidenceResolver.local(temp), context(r, family, binding));
  }
  static boolean has(JsonNode event, String code) {
    for (var d : event.at("/detectbridge/quality/diagnostics")) if (d.get("code").asString().equals(code)) return true;
    return false;
  }
  @Test void securityLiteralFieldsAndIdentity() throws Exception {
    var raw = raw(fixture("security")); var c = context(raw, "security", true);
    var e = new WindowsAdapter().adapt(raw, EvidenceResolver.local(temp), c).event();
    assertEquals(16, e.at("/process/pid").asInt()); assertEquals(32, e.at("/process/parent/pid").asInt());
    assertEquals("Alice", e.at("/user/name").asString()); assertEquals("LAB", e.at("/user/domain").asString());
    assertEquals("Bob", e.at("/source_fields/TargetUserName").asString());
    assertEquals("synthetic.exe \"α 😀\"", e.at("/process/command_line").asString());
    assertTrue(e.at("/process/args").isMissingNode());
    assertEquals("2026-11-12T12:00:00.123456789123Z", e.get("@timestamp").asString());
    assertEquals(raw.get("evidence"), e.at("/detectbridge/evidence/0/evidence"));
    assertEquals(raw.get("first_observed"), e.at("/detectbridge/time/first_observed"));
    c.put("run_id", "00000000-0000-4000-8000-000000000002");
    var replay = new WindowsAdapter().adapt(raw, EvidenceResolver.local(temp), c).event();
    assertEquals(e.at("/event/id"), replay.at("/event/id"));
    assertNotEquals(e.at("/detectbridge/run_id"), replay.at("/detectbridge/run_id"));
    assertEquals("eligible", e.at("/detectbridge/quality/eligibility").asString());
  }
  @Test void sysmonLiteralFields() throws Exception {
    var e = adapt(fixture("sysmon"), "sysmon", true).event();
    assertEquals(42, e.at("/process/pid").asInt()); assertEquals(12, e.at("/process/parent/pid").asInt());
    assertEquals("Alice", e.at("/user/name").asString()); assertEquals("LAB", e.at("/user/domain").asString());
    assertEquals("C:\\work\\", e.at("/process/working_directory").asString());
    assertEquals("{00000000-0000-4000-8000-000000000010}", e.at("/process/entity_id").asString());
    assertEquals("{00000000-0000-4000-8000-000000000011}", e.at("/process/parent/entity_id").asString());
    assertEquals("2026-11-12T12:00:00.123456789123Z", e.get("@timestamp").asString());
    assertEquals("2026-11-12 12:00:00.123456789123", e.at("/detectbridge/time/source_value").asString());
  }
  @ParameterizedTest @ValueSource(strings={"-1", "0xGG", "0x8000000000000000", "16", "0x", " 0x10"})
  void invalidHexPid(String pid) throws Exception {
    var e = adapt(fixture("security").replace("0x10", pid), "security", true).event();
    assertTrue(has(e, "extraction_failed")); assertTrue(e.at("/process/pid").isMissingNode());
    assertEquals("skipped", e.at("/detectbridge/quality/eligibility").asString());
  }
  @ParameterizedTest @ValueSource(strings={"-1", "0x10", "9223372036854775808", "1.0", "+1"})
  void invalidDecimalPid(String pid) throws Exception {
    var e = adapt(fixture("sysmon").replace(">42<", ">"+pid+"<"), "sysmon", true).event();
    assertTrue(has(e, "extraction_failed"));
  }
  @Test void integerBoundaryAndAccountFailure() throws Exception {
    assertEquals(Long.MAX_VALUE, adapt(fixture("security").replace("0x10", "0x7fffffffffffffff"), "security", true).event().at("/process/pid").asLong());
    assertEquals(0, adapt(fixture("sysmon").replace(">42<", ">0<"), "sysmon", true).event().at("/process/pid").asLong());
    assertTrue(has(adapt(fixture("sysmon").replace("LAB\\Alice", "LAB\\\\Alice"), "sysmon", true).event(), "extraction_failed"));
  }
  @Test void identityAndOptionalCapture() throws Exception {
    assertTrue(has(adapt(fixture("security"), "security", false).event(), "identity_missing"));
    String absent = fixture("security").replaceAll("<Data Name=\"CommandLine\">.*?</Data>", "");
    assertTrue(has(adapt(absent, "security", true).event(), "legitimately_absent"));
    var r = raw(absent); var c = context(r, "security", true);
    c.set("source_generation", Json.MAPPER.valueToTree(Map.of("id", "synthetic-capture", "provenance", List.of("synthetic disabled-capture case"), "command_line_capture", "disabled")));
    var e = new WindowsAdapter().adapt(r, EvidenceResolver.local(temp), c).event();
    assertTrue(has(e, "capture_unavailable")); assertFalse(has(e, "extraction_failed"));
    assertEquals("eligible", e.at("/detectbridge/quality/eligibility").asString());
  }
  @Test void fallbackTimesAndPrecision() throws Exception {
    String xml = fixture("security");
    var bad = adapt(xml.replace("2026-11-12T12:00:00.123456789123Z", "2026-02-30T12:00:00Z"), "security", true).event();
    assertEquals(OBSERVED, bad.get("@timestamp").asString()); assertTrue(has(bad, "timestamp_unparseable"));
    var local = adapt(xml.replace(".123456789123Z", ".123456789123"), "security", true).event();
    assertTrue(has(local, "timestamp_timezone_ambiguous"));
    var missing = adapt(xml.replaceAll("<TimeCreated[^>]*/>", ""), "security", true).event();
    assertTrue(has(missing, "timestamp_missing"));
  }
  @ParameterizedTest @ValueSource(strings={"Microsoft-Windows-Other", "<Version>3</Version>", "<EventID>4689</EventID>", "<Channel>Other</Channel>"})
  void unsupported(String replacement) throws Exception {
    String x = fixture("security");
    if (replacement.startsWith("<Version")) x=x.replace("<Version>2</Version>", replacement);
    else if (replacement.startsWith("<EventID")) x=x.replace("<EventID>4688</EventID>", replacement);
    else if (replacement.startsWith("<Channel")) x=x.replace("<Channel>Security</Channel>", replacement);
    else x=x.replace("Microsoft-Windows-Security-Auditing", replacement);
    var r=adapt(x,"security",true); assertNull(r.event()); assertEquals("unsupported_source",r.diagnostic().get("code").asString());
  }
  @Test void hostileXmlAndBounds() throws Exception {
    String base = fixture("security");
    List<String> bad = List.of("<!DOCTYPE Event [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>" + base,
        base.replace("Alice", "&unknown;"), base.replace("</EventData>", "<Data Name=\"NewProcessId\">0x1</Data></EventData>"),
        base.replace("</System>", "<Version>2</Version></System>"), base.replace(WindowsXml.NS,"urn:foreign"),
        base.replace("</System>", "</System>\n"), base.replace("Alice", "x".repeat(65537)),
        base.replace("Alice", "😀".repeat(16385)), base.replace("</EventData>", "<x>".repeat(33)+"</x>".repeat(33)+"</EventData>"),
        base.replace("</EventData>", "<Data Name=\"nested\"><x/></Data></EventData>"), "x".repeat(1024*1024+1));
    for (String x : bad) { var r=adapt(x,"security",true); assertNull(r.event()); assertEquals("extraction_failed", r.diagnostic().get("code").asString()); }
    var e=adapt(base.replace("Alice", "x".repeat(65536)), "security", true).event(); assertEquals(65536,e.at("/user/name").asString().length());
    assertNotNull(adapt(base.replace("Alice", "😀".repeat(16384)), "security", true).event());
  }
  @Test void systemDataCannotShadowEventDataFields() throws Exception {
    String xml = fixture("security").replace("</System>", "<Data Name=\"NewProcessName\">system-only</Data></System>");
    var event = adapt(xml, "security", true).event();
    assertNotNull(event);
    assertEquals("C:\\synthetic.exe", event.at("/process/executable").asString());
    assertEquals("system-only", event.at("/source_fields/windows_system/values/Data").asString());
    assertEquals("NewProcessName", event.at("/source_fields/windows_system/attributes/Data/Name").asString());
  }
  @Test void contractUuidCaseIsPreservedWithoutNormalization() throws Exception {
    var r = raw(fixture("security"));
    var c = context(r, "security", true);
    String run = "ABCDEFAB-1234-4ABC-8DEF-ABCDEFABCDEF";
    c.put("run_id", run);
    var event = new WindowsAdapter().adapt(r, EvidenceResolver.local(temp), c).event();
    assertEquals(run, event.at("/detectbridge/run_id").asString());
    c.put("run_id", "a-1-4-8-1");
    assertThrows(IllegalArgumentException.class, () -> new WindowsAdapter().adapt(r, EvidenceResolver.local(temp), c));
  }
  @Test void contextTamperRejectedBeforeParsing() throws Exception {
    var r=raw(fixture("security")); var c=context(r,"security",true);
    c.put("version","2.0.0"); assertThrows(IllegalArgumentException.class,()->new WindowsAdapter().adapt(r,EvidenceResolver.local(temp),c));
    c.put("version","1.0.0"); ((ObjectNode)c.get("mapping_profile")).put("sha256","0".repeat(64));
    assertThrows(IllegalArgumentException.class,()->new WindowsAdapter().adapt(r,EvidenceResolver.local(temp),c));
  }
  @Test void evidenceIntegrityAndIo() throws Exception {
    String x=fixture("security"); byte[] bytes=x.getBytes(StandardCharsets.UTF_8);
    String hash=Json.sha(bytes); Files.write(temp.resolve(hash),bytes);
    var r=raw(x); ((ObjectNode)r.get("evidence")).remove("inline");
    ((ObjectNode)r.get("evidence")).set("reference",Json.MAPPER.valueToTree(Map.of("uri","urn:sha256:"+hash,"object_sha256",hash,"byte_range",Map.of("offset",0,"length",bytes.length))));
    assertArrayEquals(bytes,EvidenceResolver.local(temp).resolve(r));
    var c=context(r,"security",true);
    Files.writeString(temp.resolve(hash),"tampered");
    assertEquals("evidence_integrity",new WindowsAdapter().adapt(r,EvidenceResolver.local(temp),c).diagnostic().get("reason").asString());
    Files.delete(temp.resolve(hash)); assertThrows(IOException.class,()->new WindowsAdapter().adapt(r,EvidenceResolver.local(temp),c));
    Files.write(temp.resolve(hash),bytes);
    ((ObjectNode)r.at("/evidence/reference/byte_range")).put("length",Long.MAX_VALUE);
    assertThrows(EvidenceResolver.IntegrityFailure.class,()->EvidenceResolver.local(temp).resolve(r));
  }
  @Test void evidenceRepresentationAndUriSpellingDoNotChangeDecodedXml() throws Exception {
    String xml = fixture("security");
    byte[] bytes = xml.getBytes(StandardCharsets.UTF_8);
    var baseline = adapt(xml, "security", true).event();
    var encoded = raw(xml);
    ((ObjectNode) encoded.get("evidence")).put("encoding", "base64");
    ((ObjectNode) encoded.get("evidence")).put("inline", Base64.getEncoder().encodeToString(bytes));
    var event = new WindowsAdapter().adapt(encoded, EvidenceResolver.local(temp), context(encoded, "security", true)).event();
    assertNotNull(event);
    assertEquals(baseline.at("/event/id"), event.at("/event/id"));
    assertEquals(baseline.get("process"), event.get("process"));
    assertEquals(encoded.get("evidence"), event.at("/detectbridge/evidence/0/evidence"));
    String hash = Json.sha(bytes);
    Files.write(temp.resolve(hash), bytes);
    for (String uri : List.of("https://example.com/evidence", "HTTPS://example.com/evidence",
        "hTtPs://example.com/evidence", "s3://bucket/evidence", "S3://bucket/evidence",
        "file:///evidence", "FILE:///evidence", "fIlE:///evidence")) {
      var referenced = encoded.deepCopy();
      ((ObjectNode) referenced.get("evidence")).remove("inline");
      ((ObjectNode) referenced.get("evidence")).set("reference", Json.MAPPER.valueToTree(Map.of("uri", uri, "object_sha256", hash)));
      var result = new WindowsAdapter().adapt(referenced, EvidenceResolver.local(temp), context(referenced, "security", true)).event();
      assertNotNull(result, uri);
      assertEquals(baseline.at("/event/id"), result.at("/event/id"));
      assertEquals(baseline.get("process"), result.get("process"));
      assertEquals(referenced.get("evidence"), result.at("/detectbridge/evidence/0/evidence"));
    }
    byte[] invalid = new byte[]{(byte) 0xff};
    ((ObjectNode) encoded.get("evidence")).put("inline", Base64.getEncoder().encodeToString(invalid));
    ((ObjectNode) encoded.get("evidence")).put("sha256", Json.sha(invalid));
    var rejected = new WindowsAdapter().adapt(encoded, EvidenceResolver.local(temp), context(encoded, "security", true));
    assertNull(rejected.event());
    assertEquals("extraction_failed", rejected.diagnostic().get("code").asString());
  }
  @Test void atomicInterruptedAndSuccessfulPublication() throws Exception {
    var r=raw(fixture("security")); var c=context(r,"security",true);
    var input=temp.resolve("input"); var output=temp.resolve("output");
    Files.write(input,Json.bytes(Map.of("raw",r,"context",c))); Files.writeString(output,"previous");
    assertThrows(IOException.class,()->Offline.run(input,output,EvidenceResolver.local(temp),null,()->{throw new IOException("synthetic interruption");}));
    assertEquals("previous",Files.readString(output));
    assertEquals(1,Offline.run(input,output,EvidenceResolver.local(temp),null));
    var published=Json.read(Files.readAllBytes(output)); assertEquals(c,published.get("context")); assertEquals(r,published.get("raw")); assertTrue(published.has("event"));
    Files.writeString(input,"\ninvalid"); var old=Files.readAllBytes(output);
    assertThrows(IllegalArgumentException.class,()->Offline.run(input,output,EvidenceResolver.local(temp),null)); assertArrayEquals(old,Files.readAllBytes(output));
  }
  @Test void independentFullNormalizedFixtures() throws Exception {
    for (String family : List.of("security", "sysmon")) {
      var expected=Boundary.resource(family+".expected.json");
      assertEquals(expected,Json.read(Json.bytes(adapt(fixture(family),family,true).event())));
      new io.detectbridge.detection.Normalized(new io.detectbridge.detection.Contracts()).validate(expected,Boundary.resource(family+".source.json"));
    }
  }
  @Test void fieldAndElementNodeBoundaries() throws Exception {
    String base=fixture("security");StringBuilder fields=new StringBuilder();
    for(int i=0;i<248;i++) fields.append("<Data Name=\"synthetic-").append(i).append("\">value</Data>");
    assertNotNull(adapt(base.replace("</EventData>",fields+"</EventData>"),"security",true).event());
    fields.append("<Data Name=\"overflow\">value</Data>");
    assertTrue(adapt(base.replace("</EventData>",fields+"</EventData>"),"security",true).preserved());
    StringBuilder nodes=new StringBuilder();
    for(int i=0;i<4079;i++) nodes.append("<Synthetic").append(i).append("/>");
    assertNotNull(adapt(base.replace("</System>",nodes+"</System>"),"security",true).event());
    nodes.append("<Overflow/>");
    assertTrue(adapt(base.replace("</System>",nodes+"</System>"),"security",true).preserved());
  }
  @Test void bindingMismatchAndCaptureConflictRemainSkipped() throws Exception {
    var mismatch=adapt(fixture("security").replace("SYNTHETIC-HOST","DIFFERENT"),"security",true).event();
    assertTrue(has(mismatch,"identity_missing")); assertTrue(mismatch.at("/host/id").isMissingNode());
    var r=raw(fixture("security"));var c=context(r,"security",true);
    c.set("source_generation",Json.MAPPER.valueToTree(Map.of("id","synthetic-capture","provenance",List.of("synthetic contradiction"),"command_line_capture","disabled")));
    assertTrue(has(new WindowsAdapter().adapt(r,EvidenceResolver.local(temp),c).event(),"conflicting"));
  }
  @Test void exactLfRangeCursorAndHashChecks() throws Exception {
    byte[] first=fixture("security").getBytes(StandardCharsets.UTF_8);
    byte[] object=(fixture("security")+fixture("sysmon")).getBytes(StandardCharsets.UTF_8);
    String hash=Json.sha(object);Files.write(temp.resolve(hash),object);
    var r=raw(fixture("sysmon"));
    r.set("cursor",Json.MAPPER.valueToTree(Map.of("kind","dataset","artifact_sha256",hash,"position",1)));
    r.put("record_id",EnvelopeValidator.recordIdentity(r));
    var e=(ObjectNode)r.get("evidence");e.remove("inline");
    e.set("reference",Json.MAPPER.valueToTree(Map.of("uri","urn:sha256:"+hash,"object_sha256",hash,"byte_range",Map.of("offset",first.length,"length",object.length-first.length))));
    assertArrayEquals(fixture("sysmon").getBytes(StandardCharsets.UTF_8),EvidenceResolver.local(temp).resolve(r));
    ((ObjectNode)r.get("cursor")).put("position",0);
    assertThrows(EvidenceResolver.IntegrityFailure.class,()->EvidenceResolver.local(temp).resolve(r));
    ((ObjectNode)r.get("cursor")).put("position",1);
    ((ObjectNode)r.at("/evidence/reference/byte_range")).put("offset",first.length+1);
    assertThrows(EvidenceResolver.IntegrityFailure.class,()->EvidenceResolver.local(temp).resolve(r));
    ((ObjectNode)r.at("/evidence/reference/byte_range")).put("offset",first.length);
    e.put("sha256","0".repeat(64));
    assertThrows(EvidenceResolver.IntegrityFailure.class,()->EvidenceResolver.local(temp).resolve(r));
  }
  @Test void invalidUtf8AndBoundedPreservation() throws Exception {
    var r=raw(fixture("security"));var c=context(r,"security",true);
    byte[] invalid={(byte)0xc3,(byte)0x28};((ObjectNode)r.get("evidence")).put("sha256",Json.sha(invalid));
    var failure=new WindowsAdapter().adapt(r,ignored->invalid,c);
    assertTrue(failure.preserved());assertTrue(Json.bytes(failure.diagnostic()).length<1024);
    assertFalse(failure.diagnostic().has("evidence"));
  }

  @Test void hardProcessInterruptionCannotPublishPartialOutput() throws Exception {
    var r=raw(fixture("security"));var c=context(r,"security",true);
    Path input=temp.resolve("crash-input"), output=temp.resolve("crash-output");
    byte[] row=Json.bytes(Map.of("raw",r,"context",c));
    try(var stream=Files.newOutputStream(input)) {
      for(int i=0;i<2000;i++){stream.write(row);stream.write('\n');}
    }
    Files.writeString(output,"previous-complete-output");
    var child=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),
        "-cp",System.getProperty("windows.test.classpath"),Offline.class.getName(),input.toString(),output.toString(),temp.toString())
        .redirectOutput(temp.resolve("child-stdout").toFile()).redirectError(temp.resolve("child-stderr").toFile()).start();
    try {
      long deadline=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(5);
      boolean staging=false;
      while(System.nanoTime()<deadline && child.isAlive()) {
        try(var paths=Files.list(temp)) {staging=paths.anyMatch(p->p.getFileName().toString().startsWith(".windows-"));}
        if(staging) break;
        Thread.sleep(10);
      }
      assertTrue(staging,"Real runner must reach staging before interruption");
      child.destroyForcibly();assertTrue(child.waitFor(5,java.util.concurrent.TimeUnit.SECONDS));
      assertEquals("previous-complete-output",Files.readString(output));
    } finally {if(child.isAlive()){child.destroyForcibly();child.waitFor();}}
  }

}
