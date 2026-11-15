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
  @Test void noPublicationBeforeCheckpointAndExactMembershipSurvivesRestoredPrefix() throws Exception {
    Time time=new Time(); Machine m=machine(time);JsonNode cases=cases();long offset=0;
    for(JsonNode row:cases.get("complete")) add(m,row,offset++);
    List<Machine.Intent> emitted=new ArrayList<>();m.complete(0,emitted::add);assertTrue(emitted.isEmpty());
    byte[] durable=m.snapshot(1);add(m,cases.get("auth"),offset);
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
    for(int i=0;i<64;i++)queued.enqueue(Machine.wire(Json.bytes(auth),"synthetic","input-id","input",i));
    byte[] before=queued.snapshot(1);
    assertThrows(IllegalArgumentException.class,()->queued.enqueue(Machine.wire(Json.bytes(auth),"synthetic","input-id","input",64)));
    assertArrayEquals(before,queued.snapshot(2));assertEquals(64,queued.pendingInputs());
    List<Machine.Intent> emitted=new ArrayList<>();for(int i=0;i<64;i++)queued.pump();
    assertEquals(64,queued.pendingOutputs());assertEquals(32,queued.pendingInputs());
    queued.snapshot(3);queued.complete(3,emitted::add);while(queued.pump()){};assertEquals(0,queued.pendingInputs());
  }
  @Test void invalidInputProducesOnlyBoundedOriginalHashLocationQuarantine() throws Exception {
    Machine m=machine(new Time());byte[] bytes="private-body-sentinel".getBytes(java.nio.charset.StandardCharsets.UTF_8);
    m.enqueue(Machine.wire(bytes,"synthetic","input-id","input",0));assertTrue(m.pump());List<Machine.Intent> output=new ArrayList<>();m.snapshot(1);m.complete(1,output::add);
    assertEquals(1,output.size());assertEquals("quarantine",output.get(0).kind());
    assertEquals(Json.sha(bytes),output.get(0).document().at("/input/value_sha256").asString());
    assertFalse(new String(Json.bytes(output.get(0).document()),java.nio.charset.StandardCharsets.UTF_8).contains("private-body-sentinel"));
  }
}
