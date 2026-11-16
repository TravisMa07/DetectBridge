package io.detectbridge.assembly;

import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.linux.Assembler;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class MachineTest {
  static final String BINDING = "a".repeat(64);
  static final JsonNode SOURCE = Json.MAPPER.valueToTree(Map.of("cluster_id","synthetic","topic_id","input-id","topic","input"));
  static JsonNode cases() throws Exception { return Json.read(Files.readAllBytes(Path.of(System.getProperty("repository.root"),".cache/linux-assembly/cases.json"))); }
  static class Time extends Clock {
    long millis=1000;
    public ZoneId getZone(){return ZoneOffset.UTC;} public Clock withZone(ZoneId zone){return this;}
    public Instant instant(){return Instant.ofEpochMilli(millis);} public long millis(){return millis;}
  }
  static Machine machine(Time time) { return new Machine(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline); }
  static void add(Machine m, JsonNode row, long offset) throws Exception {
    m.enqueue(Machine.wire(Json.bytes(row),"synthetic","input-id","input",offset));
    while(m.pump()) {}
  }
  static JsonNode uniqueAuth(JsonNode original,int position) {
    ObjectNode copy=(ObjectNode)original.deepCopy(); ObjectNode raw=(ObjectNode)copy.get("raw");
    ((ObjectNode)raw.get("cursor")).put("value","auth-occurrence-"+position);
    raw.put("record_id",Json.identity(List.of(raw.at("/source/namespace").asString(),raw.at("/source/instance").asString(),List.of("native",raw.at("/cursor/value").asString()))));return copy;
  }
  @Test void authRetriesAndRunEndUseTheSameBoundedLifecycle() throws Exception {
    Machine m=machine(new Time());JsonNode auth=cases().get("auth");add(m,auth,0);add(m,auth,1);
    JsonNode end=Json.MAPPER.valueToTree(Map.of("version","1.0.0","kind","run_end","run_id",auth.at("/context/run_id").asString(),
        "control_id","00000000-0000-4000-8000-000000000001","provenance",List.of("synthetic:end")));
    add(m,end,2);add(m,uniqueAuth(auth,9),3);List<Machine.Intent> output=new ArrayList<>();m.snapshot(1);m.complete(1,output::add);
    assertEquals(1,output.stream().filter(i->i.kind().equals("event")).count());
    assertEquals("after_dataset_end",output.stream().filter(i->i.kind().equals("diagnostic")).findFirst().orElseThrow().document().get("code").asString());
  }
  @Test void noPublicationBeforeCheckpointAndExactMembershipSurvivesRestoredPrefix() throws Exception {
    Time time=new Time(); Machine m=machine(time);JsonNode cases=cases();long offset=0;
    for(JsonNode row:cases.get("complete")) add(m,row,offset++);
    List<Machine.Intent> emitted=new ArrayList<>();m.complete(0,emitted::add);assertTrue(emitted.isEmpty());
    byte[] durable=m.snapshot(1);
    JsonNode manifestReference=m.inventory(1,durable).get("outbox").valueStream().filter(i->i.get("kind").asString().equals("manifest")).findFirst().orElseThrow();
    assertEquals(cases.at("/complete/0/context/run_id"),manifestReference.get("run_id"));
    assertEquals(cases.at("/expected/member_ids"),Json.MAPPER.valueToTree(manifestReference.get("members").valueStream().map(i->i.get("record_id").asString()).sorted().toList()));
    add(m,cases.get("auth"),offset);
    m.complete(1,emitted::add);assertEquals(8,emitted.size());assertEquals(2,m.pendingOutputs());
    var event=emitted.stream().filter(i->i.kind().equals("event")).findFirst().orElseThrow().document();
    assertEquals(cases.at("/expected/event_id"),event.at("/event/id"));
    assertEquals("eligible",event.at("/detectbridge/quality/eligibility").asString());
    assertEquals(cases.at("/expected/args"),event.at("/process/args"));
    assertEquals(cases.at("/expected/member_ids"),Json.MAPPER.valueToTree(
        event.at("/detectbridge/evidence").valueStream().map(v->v.get("record_id").asString()).sorted().toList()));
    Machine restored=Machine.restore(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,durable);
    List<Machine.Intent> repeated=new ArrayList<>();restored.releaseRestored(repeated::add);
    assertEquals(emitted.size(),repeated.size());
    for(int i=0;i<emitted.size();i++){assertEquals(emitted.get(i).sequence(),repeated.get(i).sequence());assertEquals(emitted.get(i).kind(),repeated.get(i).kind());assertEquals(emitted.get(i).key(),repeated.get(i).key());assertArrayEquals(Json.bytes(emitted.get(i).document()),Json.bytes(repeated.get(i).document()));}assertEquals(0,restored.pendingOutputs());
  }
  @Test void partialPublicationDoesNotRetireDurableIntentsAndAbortedSealDoesNotRelease() throws Exception {
    Time time=new Time();Machine m=machine(time);add(m,cases().get("auth"),0);byte[] durable=m.snapshot(1);
    m.abort(1);List<Machine.Intent> values=new ArrayList<>();m.complete(1,values::add);assertTrue(values.isEmpty());
    m.snapshot(2);assertThrows(java.io.IOException.class,()->m.complete(2,i->{values.add(i);throw new java.io.IOException();}));
    assertEquals(2,m.pendingOutputs());Machine restored=Machine.restore(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,durable);
    restored.releaseRestored(values::add);assertArrayEquals(Json.bytes(values.get(0).document()),Json.bytes(values.get(1).document()));assertEquals(0,restored.pendingOutputs());
  }
  @Test void timeoutAcrossRestoreIsImmutableAndLateEvidenceCannotReopen() throws Exception {
    Time time=new Time();Machine m=machine(time);var rows=cases().get("complete");add(m,rows.get(0),0);byte[] durable=m.snapshot(1);
    time.millis+=30000;m=Machine.restore(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,durable);
    List<Machine.Intent> output=new ArrayList<>();m.releaseRestored(output::add);assertTrue(m.pump());
    add(m,rows.get(5),1);m.snapshot(2);m.complete(2,output::add);
    var manifest=output.stream().filter(i->i.kind().equals("manifest")).findFirst().orElseThrow().document();
    assertEquals("timeout",manifest.get("closure").asString());assertFalse(manifest.get("eligible").asBoolean());
    var late=output.stream().filter(i->i.kind().equals("diagnostic")).findFirst().orElseThrow().document();
    assertEquals("late_evidence",late.get("code").asString());assertEquals(manifest.get("manifest_id"),late.get("original_manifest_id"));
  }
  @Test void corruptBindingsStateAndQueueExhaustionFailWithoutRetirement() throws Exception {
    Time time=new Time();Machine m=machine(time);var auth=cases().get("auth");add(m,auth,0);byte[] durable=m.snapshot(1);
    assertThrows(IllegalArgumentException.class,()->Machine.restore(time,Assembler.Limits.defaults(),"b".repeat(64),SOURCE,Machine::inline,durable));
    ObjectNode corrupt=(ObjectNode)Machine.parseState(durable);corrupt.put("next_sequence",999);
    assertThrows(IllegalArgumentException.class,()->Machine.restore(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,Json.bytes(corrupt)));
    Machine queued=machine(time);
    for(int i=0;i<64;i++)queued.enqueue(Machine.wire(Json.bytes(uniqueAuth(auth,i)),"synthetic","input-id","input",i));
    byte[] before=queued.snapshot(1);
    assertThrows(IllegalArgumentException.class,()->queued.enqueue(Machine.wire(Json.bytes(auth),"synthetic","input-id","input",64)));
    assertArrayEquals(before,queued.snapshot(2));assertEquals(64,queued.pendingInputs());
    List<Machine.Intent> emitted=new ArrayList<>();for(int i=0;i<64;i++)queued.pump();
    assertEquals(64,queued.pendingOutputs());assertEquals(32,queued.pendingInputs());
    queued.snapshot(3);queued.complete(3,emitted::add);while(queued.pump()){};assertEquals(0,queued.pendingInputs());
  }
  @Test void serializedByteCapsStopBeforeCountCapsAndDrainAfterCompletion() throws Exception {
    Time time=new Time();Machine queued=machine(time);byte[] bytes=new byte[1024*1024];
    for(int i=0;i<5;i++)queued.enqueue(Machine.wire(bytes,"synthetic","input-id","input",i));
    byte[] before=queued.snapshot(1);
    assertThrows(IllegalArgumentException.class,()->queued.enqueue(Machine.wire(bytes,"synthetic","input-id","input",5)));
    assertArrayEquals(before,queued.snapshot(2));assertTrue(queued.inboxBytes()<=Machine.QUEUE_BYTES);
    Machine outputs=machine(time);var auth=cases().get("auth");
    String body="<38>1 2026-01-01T00:00:00Z lab sshd 7 - [lab a=\""+"x".repeat(380000)+"\"] Accepted password for alice from 192.0.2.1 port 2222 ssh2\n";
    for(int i=0;i<12;i++) {
      ObjectNode row=(ObjectNode)uniqueAuth(auth,i);ObjectNode evidence=(ObjectNode)row.at("/raw/evidence");
      evidence.put("inline",body);evidence.put("sha256",Json.sha(body.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
      outputs.enqueue(Machine.wire(Json.bytes(row),"synthetic","input-id","input",i));
    }
    while(outputs.pump()){}
    assertTrue(outputs.pendingOutputs()>0 && outputs.pendingOutputs()<64);assertTrue(outputs.pendingInputs()>0);
    assertTrue(outputs.outboxBytes()<=Machine.QUEUE_BYTES);outputs.snapshot(1);outputs.complete(1,i->{});
    while(outputs.pump()){};assertEquals(0,outputs.pendingInputs());
  }
  @Test void invalidInputProducesOnlyBoundedOriginalHashLocationQuarantine() throws Exception {
    Machine m=machine(new Time());byte[] bytes="private-body-sentinel".getBytes(java.nio.charset.StandardCharsets.UTF_8);
    m.enqueue(Machine.wire(bytes,"synthetic","input-id","input",0));assertTrue(m.pump());List<Machine.Intent> output=new ArrayList<>();m.snapshot(1);m.complete(1,output::add);
    assertEquals(1,output.size());assertEquals("quarantine",output.get(0).kind());
    assertEquals(Json.sha(bytes),output.get(0).document().at("/input/value_sha256").asString());
    assertFalse(new String(Json.bytes(output.get(0).document()),java.nio.charset.StandardCharsets.UTF_8).contains("private-body-sentinel"));
  }
}
