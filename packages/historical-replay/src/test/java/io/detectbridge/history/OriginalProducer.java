package io.detectbridge.history;

import io.detectbridge.integration.Machine;
import io.detectbridge.detection.Evaluator;
import io.detectbridge.linux.Assembler;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Qualification only: the unchanged accepted producer generates archival observations.
 * Independent literal counts/fields/membership are checked separately in Python. */
public final class OriginalProducer {
  static class Time extends Clock {
    long now=1000;public ZoneId getZone(){return ZoneOffset.UTC;}public Clock withZone(ZoneId z){return this;}
    public Instant instant(){return Instant.ofEpochMilli(now);}public long millis(){return now;}
  }
  static void send(Machine machine,JsonNode row,long offset)throws Exception {
    machine.enqueue(Machine.wire(Json.bytes(row),"synthetic","input-id","input",offset));while(machine.pump()){}
  }
  static List<Object> release(Machine machine,long checkpoint)throws Exception {
    var result=new ArrayList<Object>();machine.snapshot(checkpoint);machine.complete(checkpoint,i->{if(!i.kind().equals("receipt"))result.add(Map.of("kind",i.kind(),"value",i.document()));});return result;
  }
  static Machine.Resolver resolver(Path objects,Path work)throws Exception {
    var entries=new ArrayList<Object>();
    try(var files=Files.list(objects)){for(Path p:files.sorted().toList())entries.add(Map.of("sha256",p.getFileName().toString(),"size_bytes",Files.size(p)));}
    JsonNode registration=Json.MAPPER.valueToTree(Map.of("version","1.0.0","objects",entries));
    Path manifest=work.resolve("producer-registration.json");Files.write(manifest,Json.bytes(registration),StandardOpenOption.CREATE_NEW);
    var hash=Machine.class.getDeclaredMethod("hash",JsonNode.class);hash.setAccessible(true);
    Class<?> type=Class.forName("io.detectbridge.integration.LocalEvidence");var open=type.getDeclaredMethod("open",Path.class,Path.class,String.class);open.setAccessible(true);
    Object registry=open.invoke(null,objects,manifest,hash.invoke(null,registration));var resolve=type.getDeclaredMethod("resolve",JsonNode.class);resolve.setAccessible(true);
    return raw->{try{return (byte[])resolve.invoke(registry,raw);}catch(java.lang.reflect.InvocationTargetException failure){if(failure.getCause() instanceof Exception cause)throw cause;throw failure;}};
  }
  public static void main(String[] args)throws Exception {
    JsonNode packet=Json.MAPPER.readTree(Files.readAllBytes(Path.of(args[0])));byte[] plan=Files.readAllBytes(Path.of(args[1]));var units=new ArrayList<Object>();
    Path work=Path.of(args[2]).toAbsolutePath().getParent(),objects=args.length>3?Path.of(args[3]):work.resolve("producer-objects");if(!Files.exists(objects))Files.createDirectory(objects);Machine.Resolver resolver=resolver(objects,work);
    for(JsonNode c:packet.get("cases")) {
      String id=c.get("id").asString();Time clock=new Time();Machine machine=new Machine(clock,id.equals("audit_resource")?new Assembler.Limits(2,512,2,32768,30000,2,4,65536):Assembler.Limits.defaults(),"a".repeat(64),Json.MAPPER.valueToTree(Map.of("cluster_id","synthetic","topic_id","input-id","topic","input")),resolver,new Evaluator(plan));
      var rows=new ArrayList<JsonNode>();for(JsonNode label:c.get("inputs"))rows.add(packet.at("/inputs/"+label.asString()+"/value"));
      JsonNode anchor=null;long offset=0;
      if(id.equals("late")) {
        for(int i=0;i<5;i++)send(machine,packet.at("/inputs/audit_"+i+"/value"),offset++);
        clock.now+=30001;while(machine.pump()){}
        JsonNode previous=Json.MAPPER.valueToTree(release(machine,1));anchor=previous.valueStream().filter(o->o.path("kind").asString().equals("manifest")).findFirst().orElseThrow().get("value");
      }
      for(JsonNode row:rows)send(machine,row,offset++);
      List<JsonNode> extraInputs=new ArrayList<>();
      if(id.equals("audit_resource")){JsonNode trigger=packet.at("/inputs/resource_trigger/value");send(machine,trigger,offset++);extraInputs.add(trigger);}
      if(id.equals("audit_dataset_end")){JsonNode end=Json.MAPPER.valueToTree(Map.of("version","1.0.0","kind","run_end","run_id",rows.get(0).at("/context/run_id"),"control_id","00000000-0000-4000-8000-0000000000ee","provenance",List.of("original synthetic dataset-end boundary")));send(machine,end,offset++);extraInputs.add(end);}
      if(id.equals("audit_timeout")||id.equals("audit_incomplete")){clock.now+=30001;while(machine.pump()){}}
      var unit=new TreeMap<String,Object>();unit.put("label",id);unit.put("kind",id.startsWith("audit_")?"audit":id.equals("late")?"audit_preservation":id.startsWith("auth")?"authentication":"windows");unit.put("inputs",rows);List<Object> observed=release(machine,id.equals("late")?2:1),mainOutputs=new ArrayList<>(),extraOutputs=new ArrayList<>();
      for(Object o:observed){JsonNode doc=Json.MAPPER.valueToTree(o);if(id.equals("audit_resource")&&doc.path("kind").asString().equals("preservation"))extraOutputs.add(o);else mainOutputs.add(o);}
      unit.put("original_outputs",mainOutputs);unit.put("extra_inputs",extraInputs);unit.put("extra_outputs",extraOutputs);unit.put("anchor",anchor);unit.put("control",null);units.add(unit);
    }
    Files.write(Path.of(args[2]),Json.bytes(units),StandardOpenOption.CREATE_NEW);
  }
}
