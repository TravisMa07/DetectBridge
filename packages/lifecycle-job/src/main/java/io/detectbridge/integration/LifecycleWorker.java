package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Json;
import io.detectbridge.linux.Assembler;
import java.nio.file.*;
import java.time.Clock;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

/** Task-thread lifecycle state owner. Kafka receipt is not application or durability. */
public final class LifecycleWorker implements AutoCloseable {
  public static class Delivery implements java.io.Serializable {
    public String role,key; public byte[] value;
    public Delivery(){}
    public Delivery(String role,String key,byte[] bytes){this.role=role;this.key=key;this.value=bytes.clone();}
    public String role(){return role;}public String key(){return key;}public byte[] bytes(){return value.clone();}
  }
  @FunctionalInterface public interface Emit {void emit(Delivery delivery)throws Exception;}
  final JsonNode config;final Clock clock;final LifecycleFiles files;final LocalEvidence evidence;
  LifecycleMachine machine;JsonNode current;long observed;long rawNext,controlNext,artifactNext;
  final ArrayDeque<Delivery> notices=new ArrayDeque<>();final Set<String> noticeIds=new HashSet<>();
  final TreeMap<Long,JsonNode> candidates=new TreeMap<>();final TreeSet<Long> completed=new TreeSet<>();
  long conflictRevision=-1;boolean restored,ready;Set<String> assigned=Set.of();
  public LifecycleWorker(JsonNode config,Clock clock)throws Exception {
    this.config=config.deepCopy();this.clock=clock;LifecycleSupport.config(config);files=new LifecycleFiles(config);
    evidence=LocalEvidence.open(Path.of("/opt/detectbridge/objects"),Path.of("/opt/detectbridge/object-registration.json"),config.get("evidence_registry_sha256").asString());
  }
  // Explicit resolver constructor for synthetic source/semantic unit cases, not a deployment hook.
  LifecycleWorker(JsonNode config,Clock clock,LifecycleFiles files)throws Exception {this.config=config.deepCopy();this.clock=clock;this.files=files;this.evidence=null;}
  JsonNode source(){return value(Map.of("cluster_id",config.get("cluster_id"),"topic_id",config.at("/topics/input/id"),"topic",config.at("/topics/input/name")));}
  LifecycleMachine.Resolver resolver(){return evidence==null?LifecycleMachine::inline:evidence::resolve;}
  public void control(byte[] wire,long next)throws Exception {
    check(notices.size()<126,"lifecycle_notice_exhausted");JsonNode p=files.observe(wire);long revision=p.get("revision").asLong();
    if(revision>observed){check(revision==observed+1,"lifecycle_observed_gap");current=p;observed=revision;notice("observed",null,"ok");}if(revision==observed)applyLatest();
    controlNext=next;
  }
  public void artifact(byte[] wire,long next)throws Exception {files.chunk(wire);artifactNext=next;applyLatest();}
  void applyLatest()throws Exception {
    if(current==null)return;JsonNode registration=null;for(JsonNode r:current.get("registrations"))if(r.get("worker_id").equals(config.get("worker_id")))registration=r;
    ready=false;assigned=Set.of();
    if(registration==null||!registration.get("incarnation").equals(config.get("incarnation"))||!registration.get("public_key").equals(config.get("worker_public_key")))return;
    check(registration.get("input_topic").equals(config.at("/topics/input/name"))&&registration.get("input_topic_id").equals(config.at("/topics/input/id")),"lifecycle_registration_input");
    TreeSet<String> runs=new TreeSet<>();registration.get("assigned_runs").forEach(r->runs.add(r.asString()));assigned=Set.copyOf(runs);if(machine!=null)machine.assign(assigned);
    String target=current.at("/proposal/bundle_sha256").asString();JsonNode manifest=files.bundle(target);
    if(manifest==null){ready=machine!=null&&machine.selection().get("origin_incarnation").equals(config.get("incarnation"));if(Files.exists(files.root.resolve("failed-transfers").resolve(target)))notice("rejected",null,"application_failed");return;}
    if(machine!=null&&machine.selection().get("revision").asLong()==observed){machine.select(machine.selection(),new io.detectbridge.detection.Evaluator(files.plan(target)),assigned);ready=true;return;}
    ObjectNode selection=object();selection.set("revision",current.get("revision"));selection.put("command_sha256",hash(current));selection.put("bundle_sha256",target);selection.set("plan_sha256",manifest.at("/plan/sha256"));selection.set("compatibility_sha256",manifest.get("compatibility_sha256"));selection.set("origin_incarnation",config.get("incarnation"));
    var evaluator=new io.detectbridge.detection.Evaluator(files.plan(target));
    if(machine==null)machine=new LifecycleMachine(clock,Assembler.Limits.defaults(),config.get("worker_checkpoint_binding_sha256").asString(),source(),resolver(),evaluator,config,selection);
    machine.select(selection,evaluator,assigned);ready=true;notice("applied",null,"ok");
  }
  void notice(String phase,Long checkpoint,String category)throws Exception {if(current==null)return;JsonNode ack=LifecycleProtocol.ack(config,current,machine==null?null:machine.selection(),phase,checkpoint,category);byte[] signed=bytes(ack);String id=ack.at("/payload/ack_id").asString();reserve(files.root,signed.length,512L*MIB);publish(files.root.resolve("notices").resolve(id.substring(7)+".json"),signed);if(!noticeIds.add(id))return;notices.add(new Delivery("ack",id,signed));}
  public boolean canAdmit(byte[] wire) {
    if(!ready||machine==null||wire!=null&&wire.length>2*MIB||!machine.canAdmit(wire==null?0:wire.length))return false;
    return true;
  }
  public void raw(byte[] wire,long offset)throws Exception {check(offset==rawNext&&canAdmit(wire),"lifecycle_raw_not_ready");machine.enqueue(LifecycleMachine.wire(wire,config.get("cluster_id").asString(),config.at("/topics/input/id").asString(),config.at("/topics/input/name").asString(),offset));rawNext=offset+1;}
  public void pump()throws Exception {if(ready&&machine!=null)machine.pump();}
  public void rejected(String role,long offset,byte[] key,byte[] value,String category)throws Exception {files.rejection(config.at("/topics/"+role+"/name").asString(),offset,key,value,category,observed);if(category.equals("lifecycle_compiler_mismatch")){files.retainRejectedTransfer();if(current!=null&&Files.exists(files.root.resolve("failed-transfers").resolve(current.at("/proposal/bundle_sha256").asString())))notice("rejected",null,"application_failed");}if(category.equals("lifecycle_control_conflict")){conflictRevision=observed;notice("rejected",null,"application_failed");}if(role.equals("control"))controlNext=offset+1;else artifactNext=offset+1;}
  JsonNode cursor(String role,long next){return value(Map.of("cluster_id",config.get("cluster_id"),"topic",config.at("/topics/"+role),"next_offset",next));}
  public byte[] snapshot(long checkpoint)throws Exception {
    checkpointReserve();if(evidence!=null)evidence.verify();
    ObjectNode state=object();state.put("version","1.0.0");for(String key:List.of("deployment_id","worker_id","runtime_binding_sha256","worker_checkpoint_binding_sha256"))state.set(key,config.get(key));state.put("checkpoint_id",checkpoint);
    state.set("raw_cursor",cursor("input",rawNext));state.set("control_cursor",cursor("control",controlNext));state.set("artifact_cursor",cursor("artifact",artifactNext));state.set("observed_head",files.observedHead(observed));state.set("rejection_head",files.rejectionHead());
    if(machine==null){state.putNull("selection");state.set("core",object());state.set("provenance",Json.MAPPER.createArrayNode());}
    else {state.set("selection",machine.selection());state.set("core",machine.coreSnapshot(checkpoint));state.set("provenance",machine.provenance());}
    if(ready&&machine!=null&&observed>conflictRevision){JsonNode selected=files.control(machine.selection().get("revision").asLong());JsonNode ack=LifecycleProtocol.ack(config,selected,machine.selection(),"durable",checkpoint,"ok");candidates.put(checkpoint,ack);}
    check(candidates.size()<=2,"lifecycle_checkpoint_ack_limit");ArrayNode acks=state.putArray("durable_ack_candidates");if(candidates.containsKey(checkpoint))acks.add(value(Map.of("checkpoint_id",checkpoint,"ack",candidates.get(checkpoint))));
    TreeSet<String> refs=new TreeSet<>();if(machine!=null){refs.add(machine.selection().get("bundle_sha256").asString());for(JsonNode item:machine.provenance())refs.add(item.at("/selection/bundle_sha256").asString());}state.set("artifact_references",value(refs));state.put("sha256",hash(state));require("state",state);byte[] data=bytes(state);check(data.length<=STATE_BYTES,"lifecycle_state_limit");inventory(checkpoint,state,data);return data;
  }
  void checkpointReserve()throws Exception {Path root=safe(Path.of(config.get("state_root").asString()));privatePath(root,true);long count;try(var entries=Files.walk(root)){count=entries.limit(65537).count();}check(count<=65536,"lifecycle_checkpoint_entries");reserve(root,192L*MIB,1024L*MIB);}
  void inventory(long checkpoint,JsonNode state,byte[] data)throws Exception {
    Path base=Path.of(config.get("store_root").asString()).resolve("inventory");if(!Files.exists(base))mkdir(base);Path dir=base.resolve(config.get("incarnation").asString());if(!Files.exists(dir))mkdir(dir);
    // Advisory inventory is bounded by observed checkpoint history and never used to restore state.
    ObjectNode info=object();info.put("version","1.0.0");info.put("checkpoint_id",checkpoint);info.put("snapshot_sha256",Json.sha(data));info.set("selection",state.get("selection"));info.set("observed_head",state.get("observed_head"));info.set("raw_cursor",state.get("raw_cursor"));info.set("control_cursor",state.get("control_cursor"));info.set("artifact_cursor",state.get("artifact_cursor"));info.set("rejection_head",state.get("rejection_head"));if(!files.rejections.isEmpty())info.set("rejection_last",files.rejections.get(files.rejections.size()-1));if(machine!=null)info.set("machine",machine.inventory(checkpoint,bytes(state.get("core"))));info.set("provenance",state.get("provenance"));info.set("durable_ack_candidates",state.get("durable_ack_candidates"));
    reserve(files.root,bytes(info).length,512L*MIB);publish(dir.resolve(String.format("%020d.json",checkpoint)),bytes(info));
  }
  public void completed(long id){completed.add(id);}
  public void aborted(long id){candidates.remove(id);completed.remove(id);if(machine!=null)machine.abort(id);}
  public void release(Emit emit)throws Exception {release(emit,false);}
  public void release(Emit emit,boolean holdData)throws Exception {
    if(restored&&machine!=null&&!holdData){machine.releaseRestored(intent->emit.emit(new Delivery("output",intent.key(),bytes(intent.document()))));restored=false;}
    for(long id:new ArrayList<>(completed)){if(machine!=null&&!holdData)machine.complete(id,intent->emit.emit(new Delivery("output",intent.key(),bytes(intent.document()))));JsonNode ack=candidates.get(id);if(ack!=null){emit.emit(new Delivery("ack",ack.at("/payload/ack_id").asString(),bytes(ack)));candidates.remove(id);}if(!holdData)completed.remove(id);}
    if(holdData&&!completed.isEmpty()){long latest=completed.last();completed.removeIf(id->id<latest);}
    while(!notices.isEmpty()){emit.emit(notices.peek());notices.remove();}
  }
  public void restore(byte[] data)throws Exception {
    JsonNode state=parse(data,STATE_BYTES);require("state",state);ObjectNode body=((ObjectNode)state).deepCopy();String expected=body.remove("sha256").asString();check(hash(body).equals(expected),"lifecycle_state_integrity");
    for(String key:List.of("deployment_id","worker_id","runtime_binding_sha256","worker_checkpoint_binding_sha256"))check(state.get(key).equals(config.get(key)),"lifecycle_restore_binding");
    for(String role:List.of("input","control","artifact")){String field=role.equals("input")?"raw_cursor":role+"_cursor";check(state.at("/"+field+"/cluster_id").equals(config.get("cluster_id"))&&state.at("/"+field+"/topic").equals(config.at("/topics/"+role)),"lifecycle_restore_source");}
    observed=state.at("/observed_head/revision").asLong();check(hash(state.get("observed_head")).equals(hash(files.observedHead(observed))),"lifecycle_restore_head");files.verifyRejectionHead(state.get("rejection_head"));for(int i=0;i<state.at("/rejection_head/count").asInt();i++){JsonNode location=files.rejections.get(i).get("location");if(location.path("category").asString().equals("lifecycle_control_conflict"))conflictRevision=Math.max(conflictRevision,location.path("observed_revision").asLong());}current=observed==0?null:files.control(observed);
    rawNext=state.at("/raw_cursor/next_offset").asLong();controlNext=state.at("/control_cursor/next_offset").asLong();artifactNext=state.at("/artifact_cursor/next_offset").asLong();
    for(JsonNode ref:state.get("artifact_references"))check(files.bundle(ref.asString())!=null,"lifecycle_restore_artifact");
    if(!state.get("selection").isNull()){JsonNode selection=state.get("selection");JsonNode control=files.control(selection.get("revision").asLong());check(hash(control).equals(selection.get("command_sha256").asString())&&control.at("/proposal/bundle_sha256").equals(selection.get("bundle_sha256")),"lifecycle_restore_selection");var evaluator=new io.detectbridge.detection.Evaluator(files.plan(selection.get("bundle_sha256").asString()));machine=LifecycleMachine.restore(clock,Assembler.Limits.defaults(),config.get("worker_checkpoint_binding_sha256").asString(),source(),resolver(),evaluator,bytes(state.get("core")),config,selection);check(machine.receivedNext()==rawNext&&machine.provenance().equals(state.get("provenance")),"lifecycle_restore_provenance");}
    else check(state.get("core").isEmpty()&&state.get("provenance").isEmpty()&&rawNext==0,"lifecycle_restore_empty");
    for(JsonNode item:state.get("durable_ack_candidates")){long id=item.get("checkpoint_id").asLong();JsonNode ack=item.get("ack"),p=ack.get("payload");JsonNode control=files.control(p.get("revision").asLong());JsonNode registration=null;for(JsonNode r:control.get("registrations"))if(r.get("worker_id").equals(config.get("worker_id"))&&r.get("incarnation").equals(p.get("incarnation")))registration=r;check(registration!=null,"lifecycle_restore_ack_key");LifecycleCrypto.verify("ack",ack,LifecycleCrypto.publicKey(registration.get("public_key").asString()));check(id<=state.get("checkpoint_id").asLong()&&p.get("checkpoint_id").asLong()==id&&p.get("phase").asString().equals("durable")&&p.get("worker_id").equals(config.get("worker_id"))&&p.get("command_sha256").asString().equals(hash(control)),"lifecycle_restore_ack");candidates.put(id,ack);completed.add(id);}
    restored=true;ready=false;assigned=Set.of();
    // Application of a current-incarnation command occurs only when its control is replayed.
  }
  public void close()throws Exception {files.close();}
}
