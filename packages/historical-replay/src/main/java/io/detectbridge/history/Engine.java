package io.detectbridge.history;

import io.detectbridge.detection.*;
import io.detectbridge.linux.*;
import io.detectbridge.transport.Json;
import io.detectbridge.windows.WindowsAdapter;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

/** Single supported producer profile; no live regrouping or executable fallback. */
final class Engine {
  private static final int MIB=1048576;
  private static final Clock CLOCK=Clock.fixed(Instant.EPOCH,ZoneOffset.UTC);
  private final JsonNode input;
  private final IntegrationOutputs integration;
  private final Path objects;
  private final Object registry;
  private final java.lang.reflect.Method evidenceMethod;
  Engine(JsonNode input,Path work)throws Exception {
    this.input=input;objects=Path.of(input.get("objects").asString());Bootstrap.safe(objects);
    Path plan=Path.of(input.get("plan").asString());Bootstrap.safe(plan);
    byte[] bytes=bounded(plan,4*MIB);
    check(Json.sha(bytes).equals(input.get("plan_sha256").asString()),"plan_integrity");
    integration=new IntegrationOutputs(new Evaluator(bytes),IntegrationOutputs.RUNTIME_PIPELINE);
    var hashes=new TreeSet<String>();for(JsonNode row:input.get("inputs"))if(row.at("/raw/evidence").has("reference"))hashes.add(row.at("/raw/evidence/reference/object_sha256").asString());
    var entries=new ArrayList<Object>();
    for(String digest:hashes){check(digest.matches("[a-f0-9]{64}"),"object_identity");Path file=objects.resolve(digest);byte[] original=bounded(file,32*MIB);check(Json.sha(original).equals(digest),"object_integrity");entries.add(Map.of("sha256",digest,"size_bytes",original.length));}
    JsonNode registration=Json.MAPPER.valueToTree(Map.of("version","1.0.0","objects",entries));
    Path manifest=work.resolve("registration.json");Bootstrap.safe(manifest);Files.write(manifest,Json.bytes(canonical(registration)),StandardOpenOption.CREATE_NEW);
    Class<?> type=Class.forName("io.detectbridge.integration.LocalEvidence");
    var open=type.getDeclaredMethod("open",Path.class,Path.class,String.class);open.setAccessible(true);
    registry=open.invoke(null,objects,manifest,hash(registration));
    evidenceMethod=type.getDeclaredMethod("resolve",JsonNode.class);evidenceMethod.setAccessible(true);
  }
  static void check(boolean valid,String reason){if(!valid)throw new IllegalArgumentException(reason);}
  static byte[] bounded(Path path,int cap)throws Exception {
    Bootstrap.safe(path);check(Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)&&Files.size(path)<=cap,"file_limit");
    try(var in=Files.newInputStream(path,LinkOption.NOFOLLOW_LINKS)){byte[] b=in.readNBytes(cap+1);check(b.length<=cap,"file_limit");return b;}
  }
  static JsonNode canonical(JsonNode value) {
    if(value.isObject()){ObjectNode result=Json.MAPPER.createObjectNode();value.propertyNames().stream().sorted().forEach(k->result.set(k,canonical(value.get(k))));return result;}
    if(value.isArray()){ArrayNode result=Json.MAPPER.createArrayNode();value.forEach(v->result.add(canonical(v)));return result;}
    return value;
  }
  static String hash(JsonNode value){return Json.sha(Json.bytes(canonical(value)));}
  static void execute(Path request,Path output)throws Exception {
    JsonNode input=Json.MAPPER.readTree(bounded(request,32*MIB));
    Engine engine=new Engine(input,output.toAbsolutePath().getParent());
    String original=input.get("original_run_id").asString(),run=input.get("run_id").asString();
    UUID.fromString(original);check(original.equals(run)||UUID.fromString(run).toString().equals(run),"run_id");
    JsonNode reproduced=engine.process(original);
    check(logical(reproduced.get("outputs")).equals(logical(input.get("original_outputs"))),"historical_original_outputs_mismatch");
    JsonNode result=original.equals(run)?reproduced:engine.process(run);
    byte[] b=Json.bytes(canonical(result));check(b.length<=32*MIB,"executor_output_limit");
    Bootstrap.safe(output);Files.write(output,b,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
  }
  static Set<String> logical(JsonNode outputs) {
    var result=new TreeSet<String>();var identities=new HashMap<String,String>();
    for(JsonNode output:outputs) {
      String kind=output.get("kind").asString();JsonNode value=output.get("value");
      String field=switch(kind){case "tagged"->"processing_id";case "detection"->"detection_id";case "processing"->"diagnostic_id";case "manifest"->"manifest_id";case "preservation"->"preservation_id";default->throw new IllegalArgumentException("output_kind");};
      String body=canonical(output).toString(),key=kind+"/"+value.get(field).asString();
      String old=identities.putIfAbsent(key,body);check(old==null||old.equals(body),"conflicting_output");result.add(body);
    }
    return result;
  }
  byte[] resolveRaw(JsonNode raw)throws Exception {
    try{return (byte[])evidenceMethod.invoke(registry,raw);}
    catch(java.lang.reflect.InvocationTargetException failure){if(failure.getCause() instanceof Exception cause)throw cause;throw failure;}
  }
  Boundary.Input resolve(JsonNode row)throws Exception {
    check(row.path("kind").asString().equals("record"),"linux_record_unit");
    return Boundary.resolve(row.get("raw"),row.get("context"),e->resolveRaw(row.get("raw")));
  }
  static void runtimeSchema(String kind,JsonNode document) {
    try{var method=Class.forName("io.detectbridge.integration.Schemas").getDeclaredMethod("require",String.class,JsonNode.class);method.setAccessible(true);method.invoke(null,kind,document);}
    catch(ReflectiveOperationException failure){throw new IllegalArgumentException("historical_runtime_schema",failure);}
  }
  List<JsonNode> rows(String run) throws Exception {
    var result=new ArrayList<JsonNode>();var ids=new HashSet<String>();
    for(JsonNode original:input.get("inputs")) {
      runtimeSchema("input",original);ObjectNode row=((ObjectNode)original).deepCopy();
      check(row.at("/context/run_id").asString().equals(input.get("original_run_id").asString()),"original_run_binding");
      check(ids.add(row.at("/raw/record_id").asString()),"duplicate_occurrence");
      ((ObjectNode)row.get("context")).put("run_id",run);result.add(row);
    }
    check(!result.isEmpty()&&result.size()<=256,"unit_inputs");return result;
  }
  static ObjectNode key(Boundary.Input in) {
    Audit.Record record=Audit.parse(in.bytes());JsonNode ctx=in.context();
    ObjectNode k=Json.MAPPER.createObjectNode();k.set("run_id",ctx.get("run_id"));k.set("source",ctx.get("source"));k.set("host_id",ctx.at("/host_binding/host_id"));k.set("generation",ctx.at("/source_generation/id"));k.put("audit_timestamp",record.timestamp());k.put("audit_serial",record.serial());return k;
  }
  static JsonNode preservation(JsonNode diagnostic,String adapter,JsonNode source) {
    return Json.MAPPER.valueToTree(Map.of("version","1.0.0","preservation_id",IntegrationOutputs.identity("detectbridge.p13.preservation/1",adapter,source,diagnostic),"adapter",adapter,"source",source,"run_id",diagnostic.get("run_id"),"diagnostic",diagnostic));
  }
  static String kind(JsonNode n) {
    if(n.has("processing_id")&&n.has("event"))return "tagged";
    if(n.has("detection_id"))return "detection";
    if(n.has("diagnostic_id"))return "processing";
    if(n.has("manifest_id"))return "manifest";
    if(n.has("preservation_id"))return "preservation";
    throw new IllegalArgumentException("unsupported_output");
  }
  JsonNode process(String run)throws Exception {
    List<JsonNode> rows=rows(run),nativeOutputs=new ArrayList<>();JsonNode windowsContext=null;
    String type=input.get("kind").asString();
    if(type.equals("windows")) {
      check(rows.size()==1&&rows.get(0).path("kind").asString().equals("windows_record"),"windows_unit");
      JsonNode row=rows.get(0);windowsContext=row.get("context");
      var adapted=new WindowsAdapter().adapt(row.get("raw"),r->{try{return resolveRaw(r);}catch(Exception failure){throw new java.io.IOException("historical_evidence_unavailable",failure);}},windowsContext);
      if(adapted.diagnostic()!=null)nativeOutputs.add(preservation(adapted.diagnostic(),"windows",row.at("/raw/source")));
      else nativeOutputs.add(adapted.event());
    }else if(type.equals("authentication")) {
      check(rows.size()==1&&rows.get(0).path("kind").asString().equals("record"),"authentication_unit");
      JsonNode row=rows.get(0);check(row.at("/context/parser/id").asString().equals("openssh-password"),"authentication_parser");
      nativeOutputs.add(OpenSsh.adapt(resolve(row)));
    }else if(type.equals("audit"))nativeOutputs.addAll(group(rows,run));
    else if(type.equals("audit_preservation")) {
      check(rows.size()==1,"preservation_unit");JsonNode row=rows.get(0);
      var in=resolve(row);
      Assembler core=new Assembler(CLOCK,Assembler.Limits.defaults());ObjectNode state=(ObjectNode)Json.MAPPER.readTree(core.snapshot());
      if(!input.path("anchor").isNull()) {
        JsonNode anchor=input.get("anchor");validateManifest(anchor);
        check(anchor.at("/key/run_id").asString().equals(input.get("original_run_id").asString()),"anchor_run");
        ObjectNode k=((ObjectNode)anchor.get("key")).deepCopy();k.put("run_id",run);check(k.equals(key(in)),"late_scope");
        for(JsonNode m:anchor.get("members"))check(!m.get("record_id").equals(in.raw().get("record_id")),"late_original_member");
        ObjectNode closed=((ObjectNode)state.get("closed")).putObject(hash(k));closed.set("key",k);closed.set("manifest_id",anchor.get("manifest_id"));if(anchor.has("event_id"))closed.set("event_id",anchor.get("event_id"));
      }
      if(!input.path("control").isNull()) {
        JsonNode control=input.get("control");runtimeSchema("input",control);check(control.path("kind").asString().equals("run_end")&&control.path("run_id").asString().equals(input.get("original_run_id").asString()),"control_binding");
        ((ObjectNode)state.get("runs")).put(run,"ended");
      }
      core=Assembler.restore(CLOCK,Assembler.Limits.defaults(),Json.bytes(state));nativeOutputs.addAll(core.prepare(in).outputs());
      check(nativeOutputs.size()==1&&nativeOutputs.get(0).path("kind").asString().equals("preservation"),"preservation_disposition");
    }else throw new IllegalArgumentException("unsupported_unit");
    var projected=Json.MAPPER.createArrayNode();
    for(JsonNode doc:nativeOutputs) {
      if(doc.has("@timestamp")) {
        JsonNode manifest=nativeOutputs.stream().filter(n->n.has("manifest_id")).findFirst().orElse(null);
        JsonNode p=windowsContext==null?integration.process(doc,manifest):integration.process(doc,manifest,windowsContext);
        add(projected,p.get("tagged"));p.get("detections").forEach(n->add(projected,n));p.get("diagnostics").forEach(n->add(projected,n));
      }else if(doc.has("manifest_id")||doc.has("preservation_id")){if(doc.has("preservation_id"))runtimeSchema("preservation",doc);add(projected,doc);}
      else add(projected,preservation(doc,"linux",doc.get("source")));
    }
    check(projected.size()<=106,"output_count");
    return Json.MAPPER.valueToTree(Map.of("native",nativeOutputs,"outputs",projected));
  }
  static void add(ArrayNode out,JsonNode value){out.add(Json.MAPPER.valueToTree(Map.of("kind",kind(value),"value",value)));}
  static void validateManifest(JsonNode manifest)throws Exception {
    var schema=Boundary.class.getDeclaredMethod("schema",String.class,JsonNode.class);schema.setAccessible(true);schema.invoke(null,"urn:detectbridge:linux:1.0.0:manifest",manifest);
    ObjectNode body=((ObjectNode)manifest).deepCopy();body.remove("manifest_id");check(manifest.get("manifest_id").asString().equals("sha256:"+hash(body)),"manifest_integrity");
  }
  List<JsonNode> group(List<JsonNode> rows,String run)throws Exception {
    JsonNode original=input.get("original_outputs").valueStream().filter(n->n.path("kind").asString().equals("manifest")).map(n->n.get("value")).findFirst().orElseThrow();validateManifest(original);
    check(original.at("/key/run_id").asString().equals(input.get("original_run_id").asString())&&original.get("members").size()==rows.size(),"manifest_membership");
    Assembler core=new Assembler(CLOCK,Assembler.Limits.defaults());
    ObjectNode expectedKey=((ObjectNode)original.get("key")).deepCopy();expectedKey.put("run_id",run);
    ObjectNode state=(ObjectNode)Json.MAPPER.readTree(core.snapshot());
    ((ObjectNode)state.get("runs")).put(run,"active");
    ObjectNode group=((ObjectNode)state.get("groups")).putObject(hash(expectedKey));
    group.set("key",expectedKey);group.set("context",rows.get(0).get("context"));group.put("opened",0L);
    ArrayNode members=group.putArray("members");long size=0;
    var reference=Boundary.class.getDeclaredMethod("referenceMember",JsonNode.class,JsonNode.class);reference.setAccessible(true);
    var configuration=Boundary.class.getDeclaredMethod("configuration",JsonNode.class);configuration.setAccessible(true);
    for(int i=0;i<rows.size();i++) {
      JsonNode origin=input.get("inputs").get(i),row=rows.get(i);
      check(row.path("kind").asString().equals("record")&&row.at("/context/parser/id").asString().equals("linux-audit"),"audit_parser");
      check(original.get("members").get(i).equals(reference.invoke(null,origin.get("raw"),origin.get("context"))),"original_member_binding");
      Boundary.Input in=resolve(row);
      check(key(in).equals(expectedKey),"audit_scope");
      ObjectNode member=members.addObject();member.set("raw",in.raw());member.set("context",in.context());member.put("bytes_base64",Base64.getEncoder().encodeToString(in.bytes()));size+=in.bytes().length;
      ((ObjectNode)state.get("receipts")).put(run+"/"+in.raw().get("record_id").asString(),hash(Json.MAPPER.valueToTree(List.of(in.raw(),configuration.invoke(null,in.context())))));
    }
    group.put("bytes",size);
    core=Assembler.restore(CLOCK,Assembler.Limits.defaults(),Json.bytes(state));
    var close=Assembler.class.getDeclaredMethod("close",ObjectNode.class,List.class,String.class,String.class);close.setAccessible(true);
    List<JsonNode> result=new ArrayList<>();close.invoke(core,state,result,hash(expectedKey),original.get("closure").asString());
    Assembler.restore(CLOCK,Assembler.Limits.defaults(),Json.bytes(state));return result;
  }
}
