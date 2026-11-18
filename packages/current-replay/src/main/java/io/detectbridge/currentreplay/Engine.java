package io.detectbridge.currentreplay;

import io.detectbridge.integration.Machine;
import io.detectbridge.detection.Evaluator;
import io.detectbridge.linux.Assembler;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

/** Explicit offline clock over the original bounded machine; output never reaches a live sink. */
final class Engine {
  static final int MIB=1048576;
  static final class Time extends Clock {
    long now;
    public ZoneId getZone(){return ZoneOffset.UTC;}public Clock withZone(ZoneId zone){check(zone.equals(ZoneOffset.UTC),"clock_zone");return this;}
    public Instant instant(){return Instant.ofEpochMilli(now);}public long millis(){return now;}
  }
  static void check(boolean valid,String reason){if(!valid)throw new IllegalArgumentException("current_"+reason);}
  static JsonNode canonical(JsonNode value) {
    if(value.isObject()){ObjectNode out=Json.MAPPER.createObjectNode();value.propertyNames().stream().sorted().forEach(k->out.set(k,canonical(value.get(k))));return out;}
    if(value.isArray()){ArrayNode out=Json.MAPPER.createArrayNode();value.forEach(v->out.add(canonical(v)));return out;}
    return value;
  }
  static int integer(JsonNode node,int minimum,int maximum) {
    check(node!=null&&node.isIntegralNumber()&&node.canConvertToLong(),"integer");long n=node.asLong();check(n>=minimum&&n<=maximum,"integer_bounds");return (int)n;
  }
  static void originalSchema(JsonNode row)throws Exception {
    var method=Class.forName("io.detectbridge.integration.Schemas").getDeclaredMethod("require",String.class,JsonNode.class);method.setAccessible(true);method.invoke(null,"input",row);
  }
  static Machine.Resolver resolver(Path objects,Path work)throws Exception {
    Bootstrap.safe(objects);var entries=new ArrayList<Object>();long total=0;
    try(var files=Files.list(objects)){for(Path file:files.sorted().toList()) {
      String digest=file.getFileName().toString();check(digest.matches("[a-f0-9]{64}"),"object_name");
      byte[] bytes=Bootstrap.read(file,32*MIB);check(Json.sha(bytes).equals(digest),"object_integrity");total+=bytes.length;
      check(total<=64L*MIB&&entries.size()<128,"object_limit");entries.add(Map.of("sha256",digest,"size_bytes",bytes.length));
    }}
    JsonNode registration=Json.MAPPER.valueToTree(Map.of("version","1.0.0","objects",entries));
    Path manifest=work.resolve("registration.json");Files.write(manifest,Json.bytes(canonical(registration)),StandardOpenOption.CREATE_NEW);
    Class<?> type=Class.forName("io.detectbridge.integration.LocalEvidence");var open=type.getDeclaredMethod("open",Path.class,Path.class,String.class);open.setAccessible(true);
    Object registry=open.invoke(null,objects,manifest,Machine.hash(registration));var resolve=type.getDeclaredMethod("resolve",JsonNode.class);resolve.setAccessible(true);
    return raw->{try{return (byte[])resolve.invoke(registry,raw);}catch(java.lang.reflect.InvocationTargetException failure){if(failure.getCause() instanceof Exception cause)throw cause;throw failure;}};
  }
  static void execute(Path source,Path output)throws Exception {
    JsonNode input=Machine.parseState(Bootstrap.read(source,32*MIB)),request=input.get("request");
    String run=input.get("run_id").asString(),original=input.get("original_run_id").asString(),requestHash=input.get("request_sha256").asString();
    check(UUID.fromString(run).toString().equals(run)&&!UUID.fromString(run).equals(UUID.fromString(original)),"run_identity");
    check(Machine.hash(request).equals(requestHash)&&request.path("mode").asString().equals("current"),"request_integrity");
    check(request.path("engine_profile").asString().equals("p13-runtime-51a984de/1.0.0")&&request.get("enrichment").isArray()&&request.get("enrichment").isEmpty(),"profile");
    check(request.path("source_policy").asString().equals("preserve-original-context/1.0.0")&&request.path("schedule_policy").asString().equals("explicit-offline-clock/1.0.0"),"policy");
    byte[] plan=Bootstrap.read(Path.of(input.get("plan").asString()),4*MIB);check(Json.sha(plan).equals(request.get("plan_sha256").asString()),"plan_integrity");
    Evaluator evaluator=new Evaluator(plan);JsonNode l=request.get("assembler_limits");
    Assembler.Limits limits=new Assembler.Limits(integer(l.get("members"),1,256),integer(l.get("group_bytes"),1,1048576),integer(l.get("open_groups"),1,1024),integer(l.get("pending_bytes"),13,33554432),integer(l.get("age_ms"),1,30000),integer(l.get("runs"),1,16),integer(l.get("closed_keys"),1,100000),integer(l.get("closed_bytes"),1,33554432));
    Bootstrap.safe(output);Files.createDirectory(output);
    Machine.Resolver resolver=resolver(Path.of(input.get("objects").asString()),output.getParent());
    Time time=new Time();String binding=Machine.hash(Json.MAPPER.valueToTree(List.of("detectbridge.current.machine/1",run,requestHash)));
    JsonNode wireSource=Json.MAPPER.valueToTree(Map.of("cluster_id","current-policy-local","topic_id","current-policy-local","topic","detectbridge.current.local"));
    Machine machine=new Machine(time,limits,binding,wireSource,resolver,evaluator);
    var rows=new HashMap<String,JsonNode>();var occurrences=new HashSet<String>();
    for(JsonNode entry:input.get("inputs")) {
      JsonNode row=entry.get("value");originalSchema(row);
      check(row.path("kind").asString().equals("record")||row.path("kind").asString().equals("windows_record"),"source_admission");
      check(row.at("/context/run_id").asString().equals(original),"original_run");
      check(occurrences.add(row.at("/raw/record_id").asString()),"duplicate_occurrence");
      String key=Machine.hash(entry.get("reference"));check(rows.put(key,row)==null,"duplicate_reference");
    }
    check(!rows.isEmpty()&&rows.size()<=256,"input_limit");
    JsonNode schedule=request.get("schedule");check(schedule.isArray()&&schedule.size()>=2&&schedule.size()<=512,"schedule_limit");
    long previous=-1,offset=0,checkpoint=0,total=0;var seen=new HashSet<String>();
    for(int i=0;i<schedule.size();i++) {
      JsonNode step=schedule.get(i);int at=integer(step.get("at_ms"),0,86400000);check(at>=previous,"schedule_order");time.now=at;previous=at;
      String action=step.get("action").asString();
      if(action.equals("input")) {
        String key=Machine.hash(step.get("input"));check(rows.containsKey(key)&&seen.add(key),"selected_input");
        ObjectNode row=((ObjectNode)rows.get(key)).deepCopy();ObjectNode context=(ObjectNode)row.get("context");context.put("run_id",run);
        context.set("receipt",Json.MAPPER.valueToTree(Map.of("received",time.instant().toString())));
        machine.enqueue(Machine.wire(Json.bytes(canonical(row)),"current-policy-local","current-policy-local","detectbridge.current.local",offset++));
      }else {
        check(step.get("input").isNull(),"control_input");
        if(action.equals("end")) {
          check(i==schedule.size()-1&&seen.size()==rows.size(),"end_scope");
          String control=UUID.nameUUIDFromBytes(Json.bytes(canonical(Json.MAPPER.valueToTree(List.of("detectbridge.current.end/1",run,requestHash,i))))).toString();
          JsonNode end=Json.MAPPER.valueToTree(Map.of("version","1.0.0","kind","run_end","run_id",run,"control_id",control,"provenance",List.of("explicit current-policy offline schedule")));
          machine.enqueue(Machine.wire(Json.bytes(canonical(end)),"current-policy-local","current-policy-local","detectbridge.current.local",offset++));
        }else check(action.equals("tick"),"schedule_action");
      }
      ArrayNode outputs=Json.MAPPER.createArrayNode();int operations=0;
      do {
        while(machine.pump()){check(++operations<=2048,"transition_work_limit");}
        machine.snapshot(checkpoint);machine.complete(checkpoint++,intent->{
          if(!intent.kind().equals("receipt")) {
            check(Set.of("tagged","detection","processing","manifest","preservation").contains(intent.kind()),"unexpected_output");
            check(outputs.size()<128,"transition_output_limit");outputs.add(Json.MAPPER.valueToTree(Map.of("kind",intent.kind(),"value",intent.document())));
          }
        });
        check(++operations<=2048,"transition_backlog");
      }while(machine.pendingInputs()!=0||machine.nextDeadline()<=time.now);
      byte[] state=machine.snapshot(checkpoint++);check(state.length<=16*MIB,"state_limit");
      machine=Machine.restore(time,limits,binding,wireSource,resolver,evaluator,state);
      if(i==schedule.size()-1)check(action.equals("end")&&machine.groupCount()==0&&machine.pendingInputs()==0&&machine.pendingOutputs()==0&&machine.coreState().at("/runs/"+run).asString().equals("ended"),"completion");
      byte[] value=Json.bytes(canonical(Json.MAPPER.valueToTree(Map.of("state",Machine.parseState(state),"outputs",outputs))));
      check(value.length<=24*MIB,"transition_limit");total+=value.length;check(total<=128L*MIB,"total_output_limit");
      Files.write(output.resolve(String.format(Locale.ROOT,"%06d.json",i)),value,StandardOpenOption.CREATE_NEW);
    }
  }
}
