package io.detectbridge.integration;

import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.detection.*;
import io.detectbridge.linux.Assembler;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class MachineTest {
  static final Path ROOT=Path.of(System.getProperty("repository.root"));
  static final String BINDING="a".repeat(64);
  static final JsonNode SOURCE=Json.MAPPER.valueToTree(Map.of("cluster_id","synthetic","topic_id","input-id","topic","input"));
  static JsonNode read(String path) throws Exception {return Json.read(Files.readAllBytes(ROOT.resolve(path)));}
  static JsonNode cases() throws Exception {return read(".cache/integration/cases.json");}
  static Evaluator evaluator() throws Exception {return new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/integration/plan.json")));}
  static class Time extends Clock {
    long millis=1000;
    public ZoneId getZone(){return ZoneOffset.UTC;}public Clock withZone(ZoneId zone){return this;}
    public Instant instant(){return Instant.ofEpochMilli(millis);}public long millis(){return millis;}
  }
  static Machine machine(Time clock) throws Exception {return new Machine(clock,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,evaluator());}
  static void add(Machine machine, JsonNode row, long offset) throws Exception {
    machine.enqueue(Machine.wire(Json.bytes(row),"synthetic","input-id","input",offset));while(machine.pump()){}
  }
  static List<Machine.Intent> release(Machine machine,long checkpoint) throws Exception {
    List<Machine.Intent> output=new ArrayList<>();machine.snapshot(checkpoint);machine.complete(checkpoint,output::add);return output;
  }
  static JsonNode tagged(List<Machine.Intent> output) {return output.stream().filter(i->i.kind().equals("tagged")).findFirst().orElseThrow().document();}
  static JsonNode end(JsonNode row) {return Json.MAPPER.valueToTree(Map.of("version","1.0.0","kind","run_end","run_id",row.at("/context/run_id"),"control_id","00000000-0000-4000-8000-000000000001","provenance",List.of("synthetic end")));}
  @Test void actualAdaptersProjectAllSixLiteralOutcomesWithExactAttribution() throws Exception {
    var expected=read("contracts/integration-runtime/v1/fixtures/expectations.json");var cases=cases();
    for(String scenario:List.of("windows","sysmon","windows_skipped","windows_budget","auth","audit","audit_skipped")) {
      Machine machine=machine(new Time());long offset=0;
      if(scenario.equals("audit"))for(var row:cases.get("complete"))add(machine,row,offset++);
      else if(scenario.equals("audit_skipped"))add(machine,cases.at("/complete/5"),offset++);
      else add(machine,cases.get(scenario),offset++);
      var output=release(machine,1);var tag=tagged(output);
      assertEquals(expected.get(scenario.equals("sysmon")?"windows":scenario),tag.get("counts"),scenario);
      assertEquals("1.1.0",tag.get("version").asString());assertEquals(IntegrationOutputs.RUNTIME_PIPELINE,tag.at("/attribution/pipeline").asString());
      assertEquals(tag.at("/counts/matched").asInt(),output.stream().filter(i->i.kind().equals("detection")).count());
      assertEquals(offset,output.stream().filter(i->i.kind().equals("receipt")).count());
      assertTrue(output.stream().filter(i->i.kind().equals("processing")).count()<=3);
      if(scenario.equals("audit")) {
        assertEquals(cases.at("/expected/event_id"),tag.at("/event/event/id"));assertEquals(cases.at("/expected/args"),tag.at("/event/process/args"));
        var manifest=output.stream().filter(i->i.kind().equals("manifest")).findFirst().orElseThrow().document();
        assertEquals(manifest.get("manifest_id"),tag.at("/manifest/manifest_id"));
        assertEquals(cases.at("/expected/member_ids"),Json.MAPPER.valueToTree(manifest.get("members").valueStream().map(m->m.get("record_id").asString()).sorted().toList()));
      }
      for(var intent:output)if(intent.kind().equals("processing")) {
        var diagnostic=intent.document();String name=diagnostic.get("category").asString();
        if(name.equals("configuration_blocked"))assertEquals(expected.get("audit_blocked_bits"),diagnostic.at("/rule_set/bits"));
        if(scenario.equals("audit_skipped")&&name.equals("quality_skipped"))assertEquals(expected.get("audit_skipped_bits"),diagnostic.at("/rule_set/bits"));
        if(name.equals("evaluation_error"))assertEquals(expected.get("windows_error_bits"),diagnostic.at("/rule_set/bits"));
      }
    }
  }
  @Test void checkpointPrefixesAbortAndPartialEmissionPreserveStableDerivedIntents() throws Exception {
    Time time=new Time();Machine machine=machine(time);add(machine,cases().get("windows"),0);
    List<Machine.Intent> output=new ArrayList<>();machine.complete(0,output::add);assertTrue(output.isEmpty());
    byte[] durable=machine.snapshot(1);machine.abort(1);machine.complete(1,output::add);assertTrue(output.isEmpty());
    machine.snapshot(2);assertThrows(java.io.IOException.class,()->machine.complete(2,i->{output.add(i);throw new java.io.IOException();}));
    assertEquals(3,machine.pendingOutputs());
    Machine restored=Machine.restore(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,evaluator(),durable);
    List<Machine.Intent> repeated=new ArrayList<>();restored.releaseRestored(repeated::add);
    assertEquals(3,repeated.size());assertEquals(output.get(0).sequence(),repeated.get(0).sequence());assertEquals(output.get(0).key(),repeated.get(0).key());assertEquals(output.get(0).kind(),repeated.get(0).kind());
    assertArrayEquals(Json.bytes(Contracts.canonical(output.get(0).document())),Json.bytes(Contracts.canonical(repeated.get(0).document())));
    add(restored,cases().get("windows"),1);assertEquals(1,release(restored,3).size());
    assertThrows(IllegalArgumentException.class,()->Machine.restore(time,Assembler.Limits.defaults(),"b".repeat(64),SOURCE,Machine::inline,evaluator(),durable));
  }
  @Test void windowsDedupRunEndConflictAndSourcePreservationRemainDistinct() throws Exception {
    Machine machine=machine(new Time());var row=cases().get("windows");add(machine,row,0);add(machine,row,1);add(machine,end(row),2);
    var after=((ObjectNode)cases().get("sysmon")).deepCopy();add(machine,after,3);add(machine,cases().get("windows_preserved"),4);
    var output=release(machine,1);assertEquals(1,output.stream().filter(i->i.kind().equals("tagged")).count());
    assertEquals(2,output.stream().filter(i->i.kind().equals("preservation")).count());
    assertEquals(5,output.stream().filter(i->i.kind().equals("receipt")).count());
    var conflict=((ObjectNode)row).deepCopy();((ObjectNode)conflict.at("/context/host_binding")).put("revision","changed");
    var host=(ObjectNode)conflict.at("/context/host_binding");host.remove("sha256");host.put("sha256",Machine.hash(host));
    machine.enqueue(Machine.wire(Json.bytes(conflict),"synthetic","input-id","input",5));
    assertThrows(IllegalArgumentException.class,machine::pump);assertEquals(1,machine.pendingInputs());
  }
  @Test void absoluteAuditDeadlineAndImmutableLateLinksSurviveRestore() throws Exception {
    Time time=new Time();Machine machine=machine(time);var rows=cases().get("complete");add(machine,rows.get(0),0);byte[] durable=machine.snapshot(1);
    time.millis+=30000;machine=Machine.restore(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,evaluator(),durable);machine.releaseRestored(i->{});
    assertTrue(machine.pump());add(machine,rows.get(5),1);var output=release(machine,2);
    var manifest=output.stream().filter(i->i.kind().equals("manifest")).findFirst().orElseThrow().document();
    assertEquals("timeout",manifest.get("closure").asString());assertFalse(manifest.get("eligible").asBoolean());
    var late=output.stream().filter(i->i.kind().equals("preservation")).findFirst().orElseThrow().document().get("diagnostic");
    assertEquals("late_evidence",late.get("code").asString());assertEquals(manifest.get("manifest_id"),late.get("original_manifest_id"));
  }
  @Test void resolverIoAndProjectionOverflowDoNotConsumeInputOrCommitProposals() throws Exception {
    Time time=new Time();Machine io=new Machine(time,Assembler.Limits.defaults(),BINDING,SOURCE,r->{throw new java.io.IOException("unavailable");},evaluator());
    io.enqueue(Machine.wire(Json.bytes(cases().get("windows")),"synthetic","input-id","input",0));
    byte[] before=io.snapshot(1);assertThrows(java.io.IOException.class,io::pump);assertArrayEquals(before,io.snapshot(2));
    ObjectNode plan=(ObjectNode)read(".cache/integration/plan.json");var notices=((ObjectNode)plan.at("/rules/0/provenance")).putArray("notices");for(int i=0;i<16;i++)notices.add("😀".repeat(4096));
    plan.remove("bundle_sha256");plan.put("bundle_sha256",Machine.hash(plan));
    Machine huge=new Machine(time,Assembler.Limits.defaults(),BINDING,SOURCE,Machine::inline,new Evaluator(Json.bytes(plan)));
    huge.enqueue(Machine.wire(Json.bytes(cases().get("windows")),"synthetic","input-id","input",0));before=huge.snapshot(1);
    assertThrows(IllegalArgumentException.class,huge::pump);assertArrayEquals(before,huge.snapshot(2));
  }
  @Test void queueAndWindowsKnowledgeExhaustionRetainBacklogWithoutPartialAdmission() throws Exception {
    Machine queued=machine(new Time());byte[] value="null".getBytes();
    for(int i=0;i<128;i++)queued.enqueue(Machine.wire(value,"synthetic","input-id","input",i));
    assertThrows(IllegalArgumentException.class,()->queued.enqueue(Machine.wire(value,"synthetic","input-id","input",128)));
    for(int i=0;i<128;i++)assertTrue(queued.pump());assertEquals(128,queued.pendingOutputs());
    queued.enqueue(Machine.wire(value,"synthetic","input-id","input",128));byte[] before=queued.snapshot(1);
    assertFalse(queued.pump());assertArrayEquals(before,queued.snapshot(2));release(queued,3);assertTrue(queued.pump());assertEquals(0,queued.pendingInputs());
    var limits=new Assembler.Limits(256,1048576,1024,33554432,30000,16,1,33554432);
    Machine bounded=new Machine(new Time(),limits,BINDING,SOURCE,Machine::inline,evaluator());
    add(bounded,cases().get("windows"),0);bounded.enqueue(Machine.wire(Json.bytes(cases().get("sysmon")),"synthetic","input-id","input",1));before=bounded.snapshot(1);
    assertThrows(IllegalArgumentException.class,bounded::pump);assertArrayEquals(before,bounded.snapshot(2));assertEquals(1,bounded.pendingInputs());
  }
  @Test void replayIsolationAndInvalidInputAccounting() throws Exception {
    List<JsonNode> tags=new ArrayList<>();
    for(String run:List.of("00000000-0000-4000-8000-000000000012","00000000-0000-4000-8000-000000000013")) {
      var row=((ObjectNode)cases().get("windows")).deepCopy();((ObjectNode)row.get("context")).put("run_id",run);
      Machine machine=machine(new Time());add(machine,row,0);tags.add(tagged(release(machine,1)));
    }
    assertEquals(tags.get(0).at("/event/event/id"),tags.get(1).at("/event/event/id"));assertNotEquals(tags.get(0).get("processing_id"),tags.get(1).get("processing_id"));
    Machine invalid=machine(new Time());byte[] bad="private-original".getBytes();invalid.enqueue(Machine.wire(bad,"synthetic","input-id","input",0));invalid.pump();var output=release(invalid,1);
    assertEquals(1,output.size());assertEquals("quarantine",output.get(0).kind());assertEquals(Json.sha(bad),output.get(0).document().at("/input/value_sha256").asString());assertFalse(output.get(0).document().toString().contains("private-original"));
  }
}
