package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.PublicKey;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Worker-local immutable control/rejection history and bounded authenticated transfer. */
public final class LifecycleFiles implements AutoCloseable {
  final Path root;final JsonNode config;final PublicKey authority;final LifecycleValidator validator;final FileChannel channel;final FileLock lock;
  final List<JsonNode> controls=new ArrayList<>();final List<JsonNode> rejections=new ArrayList<>();
  final Map<String,String> runOwners=new TreeMap<>();final Set<String> incarnations=new TreeSet<>();
  public LifecycleFiles(JsonNode config)throws Exception {this(config,new LifecycleValidator(config));}
  LifecycleFiles(JsonNode config,LifecycleValidator validator)throws Exception {
    this.validator=validator;this.config=config.deepCopy();root=safe(Path.of(config.get("store_root").asString()));privatePath(root,true);authority=LifecycleCrypto.publicKey(config.get("authority_public_key").asString());
    Path lp=root.resolve(".lock");if(!Files.exists(lp))write(lp,new byte[0]);privatePath(lp,false);channel=FileChannel.open(lp,StandardOpenOption.WRITE);FileLock acquired;try{acquired=channel.tryLock();check(acquired!=null,"lifecycle_store_locked");}catch(Exception failure){channel.close();throw failure;}lock=acquired;
    try {
      used(root);try(var entries=Files.walk(root)){var iterator=entries.iterator();while(iterator.hasNext()){Path item=iterator.next();if(item.getFileName().toString().matches("\\.partial-[a-f0-9-]{36}")){privatePath(item,false);Files.delete(item);sync(item.getParent());}}}
      for(String folder:List.of("controls","rejections","bundles","transfer","inventory","probes","notices","validation-proofs","failed-transfers"))if(!Files.exists(root.resolve(folder)))mkdir(root.resolve(folder));
      Set<String> names=new TreeSet<>();try(var files=Files.list(root)){files.forEach(p->names.add(p.getFileName().toString()));}check(names.equals(Set.of(".lock","binding.json","controls","rejections","bundles","transfer","inventory","probes","notices","validation-proofs","failed-transfers"))||names.equals(Set.of(".lock","controls","rejections","bundles","transfer","inventory","probes","notices","validation-proofs","failed-transfers")),"lifecycle_store_contents");
      publish(root.resolve("binding.json"),bytes(value(Map.of("version","1.0.0","worker_checkpoint_binding_sha256",config.get("worker_checkpoint_binding_sha256"),"consumer_group",config.get("consumer_group"),"bootstrap",config.get("bootstrap"),"flink_project",config.get("flink_project"),"private_key_path",config.get("private_key_path"),"store_root",config.get("store_root"),"state_root",config.get("state_root")))));
      reserve(root,0,512L*MIB);
      try(var files=Files.list(root.resolve("controls"))){for(Path file:files.sorted().toList()){check(file.getFileName().toString().equals(String.format("%020d.json",controls.size()+1)),"lifecycle_control_gap");JsonNode wrapper=parse(read(file,RECORD),RECORD);validateControl(wrapper,controls.size()+1);controls.add(wrapper);}}
      try(var files=Files.list(root.resolve("rejections"))){for(Path file:files.sorted().toList()){check(file.getFileName().toString().equals(String.format("%020d.json",rejections.size()+1)),"lifecycle_rejection_gap");JsonNode wrapped=parse(read(file,RECORD),RECORD);check(wrapped.size()==2&&wrapped.has("value")&&wrapped.get("sha256").asString().equals(hash(wrapped.get("value"))),"lifecycle_rejection_integrity");JsonNode record=wrapped.get("value");check(record.path("previous_sha256").equals(rejections.isEmpty()?Json.MAPPER.nullNode():value(hash(rejections.get(rejections.size()-1)))) ,"lifecycle_rejection_chain");rejections.add(record);check(rejections.size()<=4096,"lifecycle_rejections_exhausted");}}
      try(var files=Files.list(root.resolve("bundles"))){var all=files.toList();check(all.size()<=64,"lifecycle_bundle_limit");for(Path dir:all)bundle(dir.getFileName().toString());}
      sync(root.resolve("controls"));sync(root.resolve("rejections"));sync(root);
    }catch(Exception failure){close();throw failure;}
  }
  void validateControl(JsonNode wrapper,long expected)throws Exception {
    JsonNode p=LifecycleCrypto.verify("control",wrapper,authority);check(p.get("authority_id").equals(config.get("authority_id"))&&p.get("deployment_id").equals(config.get("deployment_id"))&&p.get("runtime_binding_sha256").equals(config.get("runtime_binding_sha256")),"lifecycle_control_scope");
    check(p.get("revision").asLong()==expected&&p.get("previous_control_sha256").equals(controls.isEmpty()?Json.MAPPER.nullNode():value(hash(controls.get(controls.size()-1).get("payload")))),"lifecycle_control_order");
    JsonNode proposal=p.get("proposal");check(controls.stream().noneMatch(c->c.at("/payload/proposal/request_id").equals(proposal.get("request_id"))),"lifecycle_proposal_reuse");check(hash(proposal).equals(p.get("proposal_sha256").asString())&&proposal.get("deployment_id").equals(p.get("deployment_id"))&&proposal.get("authority_id").equals(p.get("authority_id"))&&proposal.get("compatibility_sha256").equals(config.get("compatibility_sha256")),"lifecycle_proposal_scope");
    Set<String> workers=new TreeSet<>(),keys=new TreeSet<>(),topics=new TreeSet<>();String previous="";List<JsonNode> pairs=new ArrayList<>();Map<String,String> proposedOwners=new TreeMap<>(runOwners);Set<String> proposedInc=new TreeSet<>(incarnations);
    for(JsonNode r:p.get("registrations")) {
      String worker=r.get("worker_id").asString(),key=r.get("public_key").asString();check(worker.compareTo(previous)>0&&workers.add(worker)&&keys.add(key)&&topics.add(r.get("input_topic").asString()+"/"+r.get("input_topic_id").asString()),"lifecycle_registration_order");previous=worker;LifecycleCrypto.publicKey(key);
      proposedInc.add(worker+"/"+r.get("incarnation").asString());pairs.add(value(Map.of("worker_id",r.get("worker_id"),"incarnation",r.get("incarnation"))));
      String runPrevious="";for(JsonNode run:r.get("assigned_runs")){String id=run.asString();check(id.compareTo(runPrevious)>0,"lifecycle_run_order");runPrevious=id;check(!proposedOwners.containsKey(id)||proposedOwners.get(id).equals(worker),"lifecycle_run_reassignment");proposedOwners.put(id,worker);}
    }
    check(value(pairs).equals(proposal.get("participants"))&&proposedOwners.size()<=256&&proposedInc.size()<=256,"lifecycle_registration_membership");
    for(String worker:proposedOwners.values()){long count=proposedOwners.values().stream().filter(worker::equals).count();check(count<=16,"lifecycle_run_exhausted");}
    String action=proposal.get("action").asString(),target=proposal.get("bundle_sha256").asString();if(action.equals("rollback"))check(controls.stream().anyMatch(c->c.at("/payload/proposal/bundle_sha256").asString().equals(target)),"lifecycle_rollback_target");
    if(action.equals("membership"))check(!controls.isEmpty()&&controls.get(controls.size()-1).at("/payload/proposal/bundle_sha256").asString().equals(target),"lifecycle_membership_target");
    runOwners.clear();runOwners.putAll(proposedOwners);incarnations.clear();incarnations.addAll(proposedInc);
  }
  public JsonNode observe(byte[] wire)throws Exception {
    check(wire.length<=RECORD,"lifecycle_control_limit");JsonNode wrapper=parse(wire,RECORD);JsonNode p=LifecycleCrypto.verify("control",wrapper,authority);long revision=p.get("revision").asLong();
    if(revision<=controls.size()){check(Arrays.equals(bytes(wrapper),bytes(controls.get((int)revision-1))),"lifecycle_control_conflict");return controls.get((int)revision-1).get("payload").deepCopy();}
    check(controls.size()<4096,"lifecycle_controls_exhausted");Map<String,String> oldOwners=new TreeMap<>(runOwners);Set<String> oldIncarnations=new TreeSet<>(incarnations);
    try{validateControl(wrapper,controls.size()+1);reserve(root,RECORD,512L*MIB);publish(root.resolve("controls").resolve(String.format("%020d.json",revision)),bytes(wrapper));controls.add(wrapper);return p;}
    catch(Exception failed){runOwners.clear();runOwners.putAll(oldOwners);incarnations.clear();incarnations.addAll(oldIncarnations);throw failed;}
  }
  public JsonNode observedHead(long revision) {if(revision==0)return value(new LinkedHashMap<String,Object>(){{put("revision",0);put("command_sha256",null);put("journal_sha256",null);}});JsonNode wrapper=controls.get(Math.toIntExact(revision)-1);return value(Map.of("revision",revision,"command_sha256",hash(wrapper.get("payload")),"journal_sha256",hash(wrapper)));}
  public JsonNode control(long revision){check(revision>0&&revision<=controls.size(),"lifecycle_control_missing");return controls.get((int)revision-1).get("payload").deepCopy();}
  public void rejection(String topic,long offset,byte[] key,byte[] wire,String category,long observedRevision)throws Exception {
    ObjectNode location=object();location.set("cluster_id",config.get("cluster_id"));location.put("topic",topic);location.put("partition",0);location.put("offset",offset);location.put("key_sha256",Json.sha(key==null?new byte[0]:key));location.put("value_sha256",Json.sha(wire==null?new byte[0]:wire));location.put("value_bytes",wire==null?0:wire.length);location.put("category",category);location.put("observed_revision",observedRevision);
    for(JsonNode old:rejections)if(old.get("location").path("topic").asString().equals(topic)&&old.get("location").path("offset").asLong()==offset){check(old.get("location").equals(location),"lifecycle_rejection_conflict");return;}
    check(rejections.size()<4096,"lifecycle_rejections_exhausted");ObjectNode record=object();record.set("location",location);if(rejections.isEmpty())record.putNull("previous_sha256");else record.put("previous_sha256",hash(rejections.get(rejections.size()-1)));JsonNode wrapped=value(Map.of("value",record,"sha256",hash(record)));reserve(root,RECORD,512L*MIB);publish(root.resolve("rejections").resolve(String.format("%020d.json",rejections.size()+1)),bytes(wrapped));rejections.add(record);
  }
  public JsonNode rejectionHead(){ObjectNode n=object();n.put("count",rejections.size());if(rejections.isEmpty())n.putNull("sha256");else n.put("sha256",hash(rejections.get(rejections.size()-1)));return n;}
  public void verifyRejectionHead(JsonNode head){int count=head.get("count").asInt();check(count>=0&&count<=rejections.size()&&head.get("sha256").equals(count==0?Json.MAPPER.nullNode():value(hash(rejections.get(count-1)))),"lifecycle_rejection_prefix");}
  public void chunk(byte[] wire)throws Exception {
    check(wire.length<=512*1024,"lifecycle_artifact_limit");JsonNode wrapper=parse(wire,512*1024),p=LifecycleCrypto.verify("artifact",wrapper,authority);
    check(p.get("authority_id").equals(config.get("authority_id"))&&p.get("deployment_id").equals(config.get("deployment_id"))&&p.get("runtime_binding_sha256").equals(config.get("runtime_binding_sha256")),"lifecycle_artifact_scope");
    String bundle=p.get("bundle_sha256").asString();check(!Files.exists(root.resolve("failed-transfers").resolve(bundle)),"lifecycle_compiler_mismatch");Path installed=root.resolve("bundles").resolve(bundle);
    String member=p.get("member").asString();int count=p.get("chunk_count").asInt(),index=p.get("chunk_index").asInt(),length=p.get("member_bytes").asInt();byte[] data=LifecycleCrypto.decode(p.get("data_base64").asString(),262144);
    check(count==(length+262143)/262144&&index<count&&data.length==Math.min(262144,length-index*262144)&&Json.sha(data).equals(p.get("chunk_sha256").asString()),"lifecycle_chunk_integrity");
    if(Files.exists(installed)){bundle(bundle);byte[] existing=read(installed.resolve(member),4*MIB);check(existing.length==length&&Json.sha(existing).equals(p.get("member_sha256").asString())&&Arrays.equals(Arrays.copyOfRange(existing,index*262144,index*262144+data.length),data),"lifecycle_installed_chunk_conflict");return;}
    Path transfers=root.resolve("transfer");try(var dirs=Files.list(transfers)){for(Path d:dirs.toList())check(d.getFileName().toString().equals(bundle),"lifecycle_transfer_busy");}
    Path transfer=transfers.resolve(bundle);if(!Files.exists(transfer)){reserve(root,8L*MIB,512L*MIB);mkdir(transfer);mkdir(transfer.resolve("data"));sync(transfers);}
    Path file=transfer.resolve("data").resolve(member),proof=transfer.resolve(member+"."+index+".json");
    if(Files.exists(proof)){JsonNode saved=parse(read(proof,RECORD),RECORD);ObjectNode header=((ObjectNode)wrapper).deepCopy();((ObjectNode)header.get("payload")).remove("data_base64");check(saved.equals(header),"lifecycle_chunk_conflict");byte[] old=range(file,index*262144,data.length);check(Arrays.equals(old,data),"lifecycle_chunk_conflict");}
    else {
      reserve(root,data.length+RECORD,512L*MIB);try(var out=FileChannel.open(file,Set.of(StandardOpenOption.CREATE,StandardOpenOption.WRITE),PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")))){out.position(index*262144L);var buffer=java.nio.ByteBuffer.wrap(data);while(buffer.hasRemaining())out.write(buffer);out.force(true);}sync(file.getParent());ObjectNode header=((ObjectNode)wrapper).deepCopy();((ObjectNode)header.get("payload")).remove("data_base64");publish(proof,bytes(header));
    }
    boolean complete=true;for(String name:List.of("manifest.json","plan.json")){Path zero=transfer.resolve(name+".0.json");if(!Files.exists(zero)){complete=false;continue;}JsonNode first=parse(read(zero,RECORD),RECORD).get("payload");for(int i=0;i<first.get("chunk_count").asInt();i++){Path item=transfer.resolve(name+"."+i+".json");if(!Files.exists(item)){complete=false;continue;}ObjectNode signed=(ObjectNode)parse(read(item,RECORD),RECORD);ObjectNode body=(ObjectNode)signed.get("payload");int size=Math.min(262144,first.get("member_bytes").asInt()-i*262144);body.put("data_base64",Base64.getEncoder().encodeToString(range(transfer.resolve("data").resolve(name),i*262144,size)));LifecycleCrypto.verify("artifact",signed,authority);check(body.get("member_sha256").equals(first.get("member_sha256"))&&body.get("member_bytes").equals(first.get("member_bytes"))&&body.get("chunk_index").asInt()==i,"lifecycle_chunk_metadata");}}
    if(complete){for(String name:List.of("manifest.json","plan.json")){JsonNode first=parse(read(transfer.resolve(name+".0.json"),RECORD),RECORD).get("payload");byte[] body=read(transfer.resolve("data").resolve(name),4*MIB);check(body.length==first.get("member_bytes").asInt()&&Json.sha(body).equals(first.get("member_sha256").asString()),"lifecycle_member_integrity");}verifyBundleDirectory(transfer.resolve("data"),bundle);try(var dirs=Files.list(root.resolve("bundles"))){check(dirs.count()<64,"lifecycle_bundle_limit");}Files.move(transfer.resolve("data"),installed,StandardCopyOption.ATOMIC_MOVE);sync(installed.getParent());try(var files=Files.list(transfer)){for(Path item:files.toList())Files.delete(item);}Files.delete(transfer);sync(transfers);}
  }
  public void retainRejectedTransfer()throws Exception {
    Path transfer=root.resolve("transfer");try(var entries=Files.list(transfer)){for(Path active:entries.toList()){Path retained=root.resolve("failed-transfers").resolve(active.getFileName());check(!Files.exists(retained),"lifecycle_failed_transfer_conflict");Files.move(active,retained,StandardCopyOption.ATOMIC_MOVE);sync(retained.getParent());sync(transfer);}}
  }
  private byte[] range(Path file,int offset,int length)throws IOException {byte[] all=read(file,4*MIB);check(offset>=0&&length>0&&offset<=all.length-length,"lifecycle_chunk_range");return Arrays.copyOfRange(all,offset,offset+length);}
  JsonNode verifyBundleDirectory(Path dir,String expected)throws Exception {
    Set<String> names=new HashSet<>();try(var files=Files.list(dir)){files.forEach(p->names.add(p.getFileName().toString()));}check(names.equals(Set.of("manifest.json","plan.json")),"lifecycle_bundle_contents");JsonNode manifest=parse(read(dir.resolve("manifest.json"),RECORD),RECORD);require("manifest",manifest);ObjectNode pre=((ObjectNode)manifest).deepCopy();pre.remove("bundle_sha256");check(hash(pre).equals(expected)&&manifest.get("bundle_sha256").asString().equals(expected),"lifecycle_bundle_hash");
    byte[] planBytes=read(dir.resolve("plan.json"),4*MIB);JsonNode plan=parse(planBytes,4*MIB);io.detectbridge.detection.Evaluator evaluator;try{evaluator=new io.detectbridge.detection.Evaluator(planBytes);evaluator.requireMappedDeployment();}catch(IllegalArgumentException invalid){throw new IllegalArgumentException("lifecycle_invalid_bundle");}
    check(manifest.at("/plan/sha256").asString().equals(Json.sha(planBytes))&&manifest.at("/plan/bytes").asInt()==planBytes.length&&manifest.at("/plan/bundle_sha256").asString().equals(evaluator.bundle())&&manifest.get("members").size()==1&&manifest.at("/members/0/sha256").equals(manifest.at("/plan/sha256"))&&manifest.at("/members/0/bytes").equals(manifest.at("/plan/bytes")),"lifecycle_bundle_plan");
    check(hash(manifest.get("profile")).equals(manifest.get("compatibility_sha256").asString())&&manifest.get("compatibility_sha256").equals(config.get("compatibility_sha256"))&&hash(plan.get("sources")).equals(manifest.at("/profile/source_sha256").asString())&&hash(plan.get("mapping_profiles")).equals(manifest.at("/profile/mappings_sha256").asString()),"lifecycle_bundle_profile");validator.verify(planBytes,root);return manifest;
  }
  public JsonNode bundle(String sha)throws Exception {check(sha.matches("[a-f0-9]{64}"),"lifecycle_bundle_name");Path dir=root.resolve("bundles").resolve(sha);if(!Files.exists(dir))return null;return verifyBundleDirectory(dir,sha);}
  public byte[] plan(String sha)throws Exception {check(bundle(sha)!=null,"lifecycle_artifact_missing");return read(root.resolve("bundles").resolve(sha).resolve("plan.json"),4*MIB);}
  public void close()throws IOException {if(lock!=null&&lock.isValid())lock.release();channel.close();}
}
