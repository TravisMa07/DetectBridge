package io.detectbridge.integration;

import static io.detectbridge.integration.LifecycleSupport.*;
import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class LifecycleTest {
  static Path repository=Path.of(System.getProperty("repository.root"));
  static final String AUTH="715b0000-0000-4000-8000-000000000010",DEPLOY="715b0000-0000-4000-8000-000000000011",WORKER="715b0000-0000-4000-8000-000000000020",INC="715b0000-0000-4000-8000-000000000030";
  Path temp;Process service;ObjectNode config;KeyPair authority,worker;LifecycleWorker runtime;JsonNode ma,mb;
  JsonNode load(String file)throws Exception{return parse(read(repository.resolve(file),4*MIB),4*MIB);}
  @BeforeEach void setup()throws Exception {
    temp=Files.createTempDirectory(repository.resolve("packages/lifecycle-job/build"),"c");Files.setPosixFilePermissions(temp,PosixFilePermissions.fromString("rwx------"));
    authority=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();worker=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();write(temp.resolve("private.der"),worker.getPrivate().getEncoded());mkdir(temp.resolve("store"));mkdir(temp.resolve("state"));
    ma=load("packages/lifecycle-job/build/fixtures/a.manifest.json");mb=load("packages/lifecycle-job/build/fixtures/b.manifest.json");
    config=object();config.put("version","1.0.0");config.put("deployment_id",DEPLOY);config.put("authority_id",AUTH);config.put("worker_id",WORKER);config.put("incarnation",INC);config.put("authority_public_key",Base64.getEncoder().encodeToString(authority.getPublic().getEncoded()));config.put("authority_key_sha256",Json.sha(authority.getPublic().getEncoded()));config.put("worker_public_key",Base64.getEncoder().encodeToString(worker.getPublic().getEncoded()));config.put("worker_key_sha256",Json.sha(worker.getPublic().getEncoded()));config.put("private_key_path",temp.resolve("private.der").toString());config.put("bootstrap","synthetic:9092");config.put("cluster_id","synthetic-cluster");config.put("consumer_group","synthetic-worker");config.put("flink_project","detectbridge-p15b-test");config.put("producer_sha256",PRODUCER);config.put("runtime_sha256","a".repeat(64));config.put("image","flink@sha256:"+"b".repeat(64));config.set("compatibility_sha256",ma.get("compatibility_sha256"));config.put("evidence_registry_sha256",LocalEvidence.emptyHash());config.put("store_root",temp.resolve("store").toString());config.put("state_root",temp.resolve("state").toString());
    config.set("validator",value(Map.of("version","1.0.0","artifact_sha256","c".repeat(64),"image_id","sha256:"+"d".repeat(64),"base_image",load("contracts/lifecycle-runtime/v1/common.schema.json").at("/$defs/validator/properties/base_image/const"))));config.put("validator_socket_path","/validation/compiler.sock");
    config.set("limits",load("contracts/lifecycle-runtime/v1/common.schema.json").at("/$defs/limits/const"));ObjectNode topics=config.putObject("topics");for(String role:List.of("input","control","artifact","ack","output"))topics.set(role,value(Map.of("name","detectbridge.test."+role,"id","synthetic-"+role,"partition",0)));
    config.put("runtime_binding_sha256",hash(commonBinding(config)));config.put("worker_checkpoint_binding_sha256",hash(workerBinding(config)));LifecycleSupport.config(config);
    service=new ProcessBuilder("uv","run","--locked","python",repository.resolve("packages/lifecycle-job/src/test/python/compiler_service.py").toString(),temp.resolve("s").toString()).directory(repository.toFile()).redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD).start();long deadline=System.nanoTime()+java.time.Duration.ofSeconds(5).toNanos();while(!Files.exists(temp.resolve("s.ready"))&&service.isAlive()&&System.nanoTime()<deadline)Thread.sleep(10);assertTrue(Files.exists(temp.resolve("s.ready")),"real compiler test service starts");
    runtime=new LifecycleWorker(config,Clock.fixed(Instant.parse("2026-11-19T12:00:00Z"),ZoneOffset.UTC),new LifecycleFiles(config,new LifecycleValidator(config,temp.resolve("s"))));
  }
  @AfterEach void cleanup()throws Exception {if(runtime!=null)runtime.close();if(service!=null){service.destroy();service.waitFor();}if(temp!=null)try(var paths=Files.walk(temp)){for(Path p:paths.sorted(Comparator.reverseOrder()).toList())Files.deleteIfExists(p);}}
  void install(String phase)throws Exception {
    JsonNode manifest=phase.equals("a")?ma:mb;installBundle(manifest,read(repository.resolve("packages/lifecycle-job/build/fixtures/"+phase+".plan.json"),4*MIB));
  }
  void installBundle(JsonNode manifest,byte[] plan)throws Exception {for(String member:List.of("manifest.json","plan.json")){byte[] body=member.equals("manifest.json")?bytes(manifest):plan;for(int index=0;index<(body.length+262143)/262144;index++){byte[] chunk=Arrays.copyOfRange(body,index*262144,Math.min(body.length,(index+1)*262144));ObjectNode p=object();p.put("version","1.0.0");p.put("authority_id",AUTH);p.put("deployment_id",DEPLOY);p.set("runtime_binding_sha256",config.get("runtime_binding_sha256"));p.set("bundle_sha256",manifest.get("bundle_sha256"));p.put("member",member);p.put("member_sha256",Json.sha(body));p.put("member_bytes",body.length);p.put("chunk_index",index);p.put("chunk_count",(body.length+262143)/262144);p.put("chunk_sha256",Json.sha(chunk));p.put("data_base64",Base64.getEncoder().encodeToString(chunk));runtime.artifact(bytes(LifecycleCrypto.sign("artifact",p,authority.getPrivate(),authority.getPublic())),runtime.artifactNext+1);}}
  }
  JsonNode control(String phase,long revision,String action)throws Exception {
    JsonNode manifest=phase.equals("a")?ma:mb;ObjectNode proposal=object();proposal.put("version","1.0.0");proposal.put("authority_id",AUTH);proposal.put("deployment_id",DEPLOY);proposal.put("request_id",UUID.randomUUID().toString());proposal.put("revision",revision);if(revision==1)proposal.putNull("previous_sha256");else proposal.put("previous_sha256","e".repeat(64));proposal.put("action",action);proposal.set("bundle_sha256",manifest.get("bundle_sha256"));proposal.set("compatibility_sha256",manifest.get("compatibility_sha256"));proposal.set("participants",value(List.of(Map.of("worker_id",WORKER,"incarnation",INC))));
    ObjectNode p=object();p.put("version","1.0.0");p.put("deployment_id",DEPLOY);p.put("authority_id",AUTH);p.set("proposal",proposal);p.put("proposal_sha256",hash(proposal));p.put("revision",revision);if(revision==1)p.putNull("previous_control_sha256");else p.put("previous_control_sha256",hash(runtime.files.control(revision-1)));p.set("runtime_binding_sha256",config.get("runtime_binding_sha256"));p.set("registrations",value(List.of(Map.of("worker_id",WORKER,"incarnation",INC,"public_key",config.get("worker_public_key"),"input_topic",config.at("/topics/input/name"),"input_topic_id",config.at("/topics/input/id"),"assigned_runs",List.of("715b0000-0000-4000-8000-000000000101","715b0000-0000-4000-8000-000000000102","715b0000-0000-4000-8000-000000000103")))));return LifecycleCrypto.sign("control",p,authority.getPrivate(),authority.getPublic());
  }
  JsonNode alice(String run)throws Exception {ObjectNode row=((ObjectNode)load("contracts/lifecycle-runtime/v1/fixtures/source-cases.json").at("/cases/0/admissions/0")).deepCopy();((ObjectNode)row.get("context")).put("run_id",run);return row;}
  List<JsonNode> event(JsonNode row,long checkpoint)throws Exception {runtime.raw(bytes(row),runtime.rawNext);runtime.pump();runtime.snapshot(checkpoint);runtime.completed(checkpoint);List<JsonNode> result=new ArrayList<>();runtime.release(d->{if(d.role().equals("output")){JsonNode output=parse(d.bytes(),4*MIB);if(output.get("kind").asString().equals("tagged"))result.add(output);}});return result;}
  @Test void applyingBChangesActualSourceOutcome()throws Exception {
    install("a");install("b");runtime.control(bytes(control("a",1,"activate")),1);
    JsonNode first=event(alice("715b0000-0000-4000-8000-000000000101"),1).get(0);assertEquals(1,first.at("/document/counts/matched").asInt());
    runtime.control(bytes(control("b",2,"activate")),2);JsonNode second=event(alice("715b0000-0000-4000-8000-000000000102"),2).get(0);assertEquals(0,second.at("/document/counts/matched").asInt());assertEquals(1,second.at("/document/counts/unmatched").asInt());assertNotEquals(first.get("output_id"),second.get("output_id"));
    runtime.control(bytes(control("a",3,"rollback")),3);JsonNode third=event(alice("715b0000-0000-4000-8000-000000000103"),3).get(0);assertEquals(1,third.at("/document/counts/matched").asInt());assertNotEquals(first.get("output_id"),third.get("output_id"));
  }
  @Test void signatureDomainAndTamperFailClosed()throws Exception {install("a");JsonNode signed=control("a",1,"activate");assertThrows(Exception.class,()->LifecycleCrypto.verify("ack",signed,authority.getPublic()));((ObjectNode)signed.get("payload")).put("revision",2);assertThrows(Exception.class,()->runtime.control(bytes(signed),1));assertEquals(0,runtime.observed);}
  @Test void existingPublishedObjectIsForcedOnRetry()throws Exception {Path p=temp.resolve("durable");publish(p,new byte[]{1,2});publish(p,new byte[]{1,2});assertArrayEquals(new byte[]{1,2},read(p,3));assertThrows(Exception.class,()->publish(p,new byte[]{3}));}
  @Test void checkpointAbortDoesNotLeakOldAckIntoRestoredCheckpoint()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);runtime.raw(bytes(alice("715b0000-0000-4000-8000-000000000101")),0);runtime.pump();
    runtime.snapshot(1);byte[] second=runtime.snapshot(2);runtime.aborted(1);runtime.close();runtime=null;
    runtime=new LifecycleWorker(config,Clock.systemUTC(),new LifecycleFiles(config,new LifecycleValidator(config,temp.resolve("s"))));runtime.restore(second);List<JsonNode> outputs=new ArrayList<>();runtime.release(d->outputs.add(parse(d.bytes(),4*MIB)));
    List<Long> ackCheckpoints=outputs.stream().filter(d->d.has("payload")).map(d->d.at("/payload/checkpoint_id").asLong()).toList();assertEquals(List.of(2L),ackCheckpoints);
    assertEquals(1,outputs.stream().filter(d->d.path("kind").asString().equals("tagged")).count());
  }
  @Test void afterSnapshotFaultObservesRealCandidateAndAbortRemovesItsAck()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);runtime.raw(bytes(alice("715b0000-0000-4000-8000-000000000101")),0);runtime.pump();
    List<String> observed=new ArrayList<>();LifecycleHooks hook=new LifecycleHooks(){public void afterSnapshot(long checkpoint,JsonNode selection,String snapshotSha256)throws Exception {
      assertEquals(1,checkpoint);assertEquals(1,selection.get("revision").asLong());assertTrue(runtime.candidates.containsKey(checkpoint),"real durable candidate exists before fault");
      JsonNode inventory=parse(read(temp.resolve("store/inventory").resolve(INC).resolve("00000000000000000001.json"),4*MIB),4*MIB);assertEquals(inventory.get("snapshot_sha256").asString(),snapshotSha256);assertEquals(1,inventory.get("durable_ack_candidates").size());
      observed.add(snapshotSha256);throw new java.io.IOException("qualification_snapshot_created_unconfirmed");
    }};
    assertThrows(java.io.IOException.class,()->LifecycleSource.snapshotSplit(WORKER,runtime,1,hook));assertEquals(1,observed.size());assertTrue(observed.get(0).matches("[a-f0-9]{64}"));
    runtime.aborted(1);assertFalse(runtime.candidates.containsKey(1L));LifecycleSource.WorkerSplit split=LifecycleSource.snapshotSplit(WORKER,runtime,2,LifecycleHooks.NONE);assertNotEquals(observed.get(0),Json.sha(split.snapshot()));
    runtime.close();runtime=new LifecycleWorker(config,Clock.systemUTC(),new LifecycleFiles(config,new LifecycleValidator(config,temp.resolve("s"))));runtime.restore(split.snapshot());List<JsonNode> emitted=new ArrayList<>();runtime.release(d->emitted.add(parse(d.bytes(),4*MIB)));assertEquals(List.of(2L),emitted.stream().filter(d->d.has("payload")).map(d->d.at("/payload/checkpoint_id").asLong()).toList());assertEquals(1,emitted.stream().filter(d->d.path("kind").asString().equals("tagged")).count());
  }
  @Test void oldAIntentAndNewBIntentRetainTheirOwnSelectionAcrossRestore()throws Exception {
    install("a");install("b");runtime.control(bytes(control("a",1,"activate")),1);runtime.raw(bytes(alice("715b0000-0000-4000-8000-000000000101")),0);runtime.pump();runtime.snapshot(1);
    runtime.control(bytes(control("b",2,"activate")),2);runtime.raw(bytes(alice("715b0000-0000-4000-8000-000000000102")),1);runtime.pump();byte[] checkpoint=runtime.snapshot(2);runtime.aborted(1);runtime.close();runtime=null;
    runtime=new LifecycleWorker(config,Clock.systemUTC(),new LifecycleFiles(config,new LifecycleValidator(config,temp.resolve("s"))));runtime.restore(checkpoint);List<JsonNode> tagged=new ArrayList<>();runtime.release(d->{if(d.role().equals("output")){JsonNode value=parse(d.bytes(),4*MIB);if(value.get("kind").asString().equals("tagged"))tagged.add(value);}});
    assertEquals(2,tagged.size());assertEquals(1,tagged.get(0).at("/document/counts/matched").asInt());assertEquals(1,tagged.get(0).get("revision").asLong());assertEquals(0,tagged.get(1).at("/document/counts/matched").asInt());assertEquals(2,tagged.get(1).get("revision").asLong());
  }
  @Test void pendingBUpdatesOwnershipWithoutRelabelingPriorA()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);runtime.raw(bytes(alice("715b0000-0000-4000-8000-000000000101")),0);
    ObjectNode signed=(ObjectNode)control("b",2,"activate"),payload=(ObjectNode)signed.get("payload");((ObjectNode)payload.at("/registrations/0")).set("assigned_runs",value(List.of("715b0000-0000-4000-8000-000000000102")));signed=(ObjectNode)LifecycleCrypto.sign("control",payload,authority.getPrivate(),authority.getPublic());runtime.control(bytes(signed),2);runtime.pump();
    assertEquals(1,runtime.machine.pendingInputs());assertEquals(0,runtime.machine.pendingOutputs());assertEquals(1,runtime.machine.selection().get("revision").asLong());assertTrue(runtime.ready);
  }
  @Test void opaqueFractionReachesOriginalCanonicalBoundaryWithoutProtocolRejection()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);ObjectNode tagged=(ObjectNode)event(alice("715b0000-0000-4000-8000-000000000101"),1).get(0);ObjectNode original=(ObjectNode)tagged.get("document");((ObjectNode)original.at("/event/source_fields")).put("synthetic_fraction",1.25);
    new io.detectbridge.detection.Contracts().require("integration","tagged-event",original);JsonNode decoded=parse(Json.bytes(tagged),4*MIB);require("output",decoded);assertEquals(1.25,decoded.at("/document/event/source_fields/synthetic_fraction").asDouble());assertThrows(IllegalArgumentException.class,()->hash(original));
  }
  @Test void changingConsumerGroupCannotAdoptRetainedWorkerStore()throws Exception {
    runtime.close();runtime=null;ObjectNode changed=config.deepCopy();changed.put("consumer_group","other-group");assertThrows(Exception.class,()->new LifecycleFiles(changed));
  }

  @Test void signedSelfConsistentForgedAstDoesNotReplacePriorValidatedA()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);assertEquals(1,event(alice("715b0000-0000-4000-8000-000000000101"),1).get(0).at("/document/counts/matched").asInt());
    ObjectNode bad=((ObjectNode)load("packages/lifecycle-job/build/fixtures/b.plan.json")).deepCopy();JsonNode good=load("packages/lifecycle-job/build/fixtures/a.plan.json");((ObjectNode)bad.at("/rules/0")).set("expression",good.at("/rules/0/expression"));assertNotEquals(bad.at("/rules/0/yaml"),good.at("/rules/0/yaml"));bad.remove("bundle_sha256");bad.put("bundle_sha256",hash(bad));byte[] forged=bytes(bad);
    ObjectNode manifest=((ObjectNode)mb).deepCopy();ObjectNode reference=(ObjectNode)manifest.get("plan");reference.put("sha256",Json.sha(forged));reference.put("bytes",forged.length);reference.set("bundle_sha256",bad.get("bundle_sha256"));((ObjectNode)manifest.at("/members/0")).put("sha256",Json.sha(forged));((ObjectNode)manifest.at("/members/0")).put("bytes",forged.length);manifest.remove("bundle_sha256");manifest.put("bundle_sha256",hash(manifest));mb=manifest;
    boolean rejected=false;try{installBundle(manifest,forged);}catch(IllegalArgumentException compilerMismatch){rejected=true;}
    runtime.control(bytes(control("b",2,"activate")),2);JsonNode retained=event(alice("715b0000-0000-4000-8000-000000000102"),2).get(0);assertEquals(1,retained.get("revision").asLong(),"forged AST must not replace prior A");assertEquals(1,retained.at("/document/counts/matched").asInt());assertTrue(rejected,"worker independently rejects compiler mismatch");
  }

  @Test void survivingRenameRetriesForceBothFileAndParent()throws Exception {
    Path target=temp.resolve("surviving");assertThrows(java.io.IOException.class,()->publish(target,new byte[]{7},path->{throw new java.io.IOException("injected_parent_force");}));assertTrue(Files.exists(target));List<Path> forced=new ArrayList<>();publish(target,new byte[]{7},forced::add);assertEquals(List.of(target,target.getParent()),forced);
  }
  @Test void workerCompilerRejectsWrongNonceAndNeverCachesIt()throws Exception {
    Path socket=temp.resolve("q"),proof=temp.resolve("fresh");mkdir(proof);try(var server=java.nio.channels.ServerSocketChannel.open(java.net.StandardProtocolFamily.UNIX)){server.bind(java.net.UnixDomainSocketAddress.of(socket));Files.setPosixFilePermissions(socket,PosixFilePermissions.fromString("rw-------"));
      Thread responder=new Thread(()->{try(var channel=server.accept()){java.nio.ByteBuffer length=java.nio.ByteBuffer.allocate(4);while(length.hasRemaining())channel.read(length);length.flip();java.nio.ByteBuffer body=java.nio.ByteBuffer.allocate(length.getInt());while(body.hasRemaining())channel.read(body);ObjectNode request=(ObjectNode)parse(body.array(),8*MIB);request.remove("plan_base64");request.put("nonce",UUID.randomUUID().toString());request.put("passed",true);request.put("category","ok");byte[] response=bytes(request);java.nio.ByteBuffer frame=java.nio.ByteBuffer.allocate(4+response.length).putInt(response.length).put(response);frame.flip();while(frame.hasRemaining())channel.write(frame);}catch(Exception failure){throw new RuntimeException(failure);}});responder.start();assertThrows(LifecycleValidator.Unavailable.class,()->new LifecycleValidator(config,socket).verify(read(repository.resolve("packages/lifecycle-job/build/fixtures/a.plan.json"),4*MIB),proof));responder.join();try(var files=Files.list(proof.resolve("validation-proofs"))){assertEquals(0,files.count());}
    }
  }
  @Test void corruptProofTriggersRealCompilerRevalidation()throws Exception {
    install("a");Path proofs=temp.resolve("store/validation-proofs");Path original;try(var entries=Files.list(proofs)){original=entries.filter(p->p.toString().endsWith(".json")).findFirst().orElseThrow();}Files.writeString(original,"corrupt",StandardOpenOption.TRUNCATE_EXISTING);assertNotNull(runtime.files.bundle(ma.get("bundle_sha256").asString()));try(var entries=Files.list(proofs)){assertEquals(1,entries.filter(p->p.getFileName().toString().startsWith(".invalid-")).count());}
  }
  @Test void splitSerializerRejectsForeignVersionAndPreservesActualSnapshot()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);byte[] snapshot=runtime.snapshot(1);LifecycleSource source=new LifecycleSource(config);var serializer=source.getSplitSerializer();byte[] encoded=serializer.serialize(new LifecycleSource.WorkerSplit(WORKER,snapshot));assertArrayEquals(snapshot,serializer.deserialize(1,encoded).snapshot());assertThrows(Exception.class,()->serializer.deserialize(2,encoded));assertThrows(Exception.class,()->serializer.deserialize(1,new byte[]{0,0,0}));
  }

  @Test void interruptedOwnedPartialIsNotAuthoritativeAndCanRecover()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);runtime.close();runtime=null;Path partial=temp.resolve("store/controls/.partial-"+UUID.randomUUID());write(partial,new byte[]{1,2,3});try(var reopened=new LifecycleFiles(config,new LifecycleValidator(config,temp.resolve("s")))){assertEquals(1,reopened.controls.size());assertFalse(Files.exists(partial));}
  }

  @Test void helperRejectsIgnoredDerSuffixBeforeSignatureVerification()throws Exception {
    Path publicFile=temp.resolve("authority.der"),message=temp.resolve("signed.json");write(publicFile,authority.getPublic().getEncoded());write(message,bytes(control("a",1,"activate")));Object ok=LifecycleTool.run(new String[]{"verify","control",publicFile.toString(),message.toString()});assertEquals(Boolean.TRUE,((Map<?,?>)ok).get("verified"));
    byte[] canonical=authority.getPublic().getEncoded(),changed=Arrays.copyOf(canonical,canonical.length+1);changed[changed.length-1]=0;Files.write(publicFile,changed,StandardOpenOption.TRUNCATE_EXISTING);assertThrows(IllegalArgumentException.class,()->LifecycleTool.run(new String[]{"verify","control",publicFile.toString(),message.toString()}));assertThrows(IllegalArgumentException.class,()->LifecycleCrypto.publicKey(Base64.getEncoder().encodeToString(changed)));
  }

  JsonNode signUnchecked(String domain,JsonNode payload)throws Exception {
    var signature=Signature.getInstance("Ed25519");signature.initSign(authority.getPrivate());signature.update(("detectbridge.p15b."+domain+"/1\0").getBytes(java.nio.charset.StandardCharsets.UTF_8));signature.update(bytes(payload));return value(Map.of("version","1.0.0","key_sha256",Json.sha(authority.getPublic().getEncoded()),"payload",payload,"signature",Base64.getEncoder().encodeToString(signature.sign())));
  }
  ObjectNode chunkPayload(JsonNode manifest,String member,byte[] whole,int index,byte[] chunk)throws Exception {
    ObjectNode p=object();p.put("version","1.0.0");p.put("authority_id",AUTH);p.put("deployment_id",DEPLOY);p.set("runtime_binding_sha256",config.get("runtime_binding_sha256"));p.set("bundle_sha256",manifest.get("bundle_sha256"));p.put("member",member);p.put("member_sha256",Json.sha(whole));p.put("member_bytes",whole.length);p.put("chunk_index",index);p.put("chunk_count",(whole.length+262143)/262144);p.put("chunk_sha256",Json.sha(chunk));p.put("data_base64",Base64.getEncoder().encodeToString(chunk));return p;
  }
  ObjectNode manifestFor(JsonNode original,byte[] plan)throws Exception {
    ObjectNode m=((ObjectNode)original).deepCopy();((ObjectNode)m.get("plan")).put("sha256",Json.sha(plan));((ObjectNode)m.get("plan")).put("bytes",plan.length);((ObjectNode)m.at("/members/0")).put("sha256",Json.sha(plan));((ObjectNode)m.at("/members/0")).put("bytes",plan.length);m.remove("bundle_sha256");m.put("bundle_sha256",hash(m));return m;
  }
  @Test void exactIntegerControlSyntaxRejectsBooleanFractionAndOverflow()throws Exception {
    JsonNode baseline=control("a",1,"activate");ObjectNode p=((ObjectNode)baseline.get("payload")).deepCopy();p.put("revision",true);ObjectNode bool=p;assertThrows(Exception.class,()->runtime.files.observe(bytes(signUnchecked("control",bool))));
    p=((ObjectNode)baseline.get("payload")).deepCopy();p.put("revision",1.5);ObjectNode fraction=p;JsonNode outer=baseline.deepCopy();((ObjectNode)outer).set("payload",fraction);assertThrows(Exception.class,()->require("control",outer));
    p=((ObjectNode)baseline.get("payload")).deepCopy();p.put("revision",new java.math.BigInteger("9223372036854775808"));p.put("previous_control_sha256","e".repeat(64));ObjectNode overflow=p;assertThrows(Exception.class,()->runtime.files.observe(bytes(signUnchecked("control",overflow))));
    p=((ObjectNode)baseline.get("payload")).deepCopy();p.put("revision",Long.MAX_VALUE);p.put("previous_control_sha256","e".repeat(64));require("control",signUnchecked("control",p));assertEquals(0,runtime.files.controls.size());
  }
  ObjectNode participantPayload(int count)throws Exception {
    ObjectNode p=((ObjectNode)control("a",1,"activate").get("payload")).deepCopy();var registrations=Json.MAPPER.createArrayNode();var participants=Json.MAPPER.createArrayNode();for(int i=1;i<=count;i++){String id=String.format("715b0000-0000-4000-8000-%012d",i);KeyPair key=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();JsonNode pair=value(Map.of("worker_id",id,"incarnation",INC));participants.add(pair);registrations.add(value(Map.of("worker_id",id,"incarnation",INC,"public_key",Base64.getEncoder().encodeToString(key.getPublic().getEncoded()),"input_topic","test.input."+i,"input_topic_id","synthetic-"+i,"assigned_runs",List.of())));}p.set("registrations",registrations);((ObjectNode)p.get("proposal")).set("participants",participants);p.put("proposal_sha256",hash(p.get("proposal")));return p;
  }
  @Test void participantBoundsAndDuplicateWorkersEnforced()throws Exception {
    require("control",signUnchecked("control",participantPayload(1)));runtime.files.observe(bytes(signUnchecked("control",participantPayload(16))));assertEquals(1,runtime.files.controls.size());
    assertThrows(Exception.class,()->require("control",signUnchecked("control",participantPayload(0))));assertThrows(Exception.class,()->require("control",signUnchecked("control",participantPayload(17))));
  }
  @Test void duplicateWorkerWithDifferentKeyCannotEvadePairUniqueness()throws Exception {
    ObjectNode p=participantPayload(2);((ObjectNode)p.at("/registrations/1")).set("worker_id",p.at("/registrations/0/worker_id"));((ObjectNode)p.at("/proposal/participants/1")).set("worker_id",p.at("/registrations/0/worker_id"));((ObjectNode)p.at("/registrations/1")).put("incarnation","715b0000-0000-4000-8000-000000000031");((ObjectNode)p.at("/proposal/participants/1")).put("incarnation","715b0000-0000-4000-8000-000000000031");p.put("proposal_sha256",hash(p.get("proposal")));assertThrows(Exception.class,()->runtime.files.observe(bytes(signUnchecked("control",p))));assertEquals(0,runtime.files.controls.size());
  }
  @Test void controlGapWrongPredecessorAndUnpublishedRollbackPreserveA()throws Exception {
    install("a");JsonNode first=control("a",1,"activate");runtime.control(bytes(first),1);ObjectNode next=((ObjectNode)control("b",2,"activate").get("payload")).deepCopy();ObjectNode gap=next.deepCopy();gap.put("revision",3);assertThrows(Exception.class,()->runtime.control(bytes(signUnchecked("control",gap)),2));ObjectNode previous=next.deepCopy();previous.put("previous_control_sha256","f".repeat(64));assertThrows(Exception.class,()->runtime.control(bytes(signUnchecked("control",previous)),2));
    JsonNode never=control("b",2,"rollback");assertThrows(Exception.class,()->runtime.control(bytes(never),2));assertThrows(Exception.class,()->runtime.control(bytes(control("b",2,"membership")),2));assertEquals(1,runtime.observed);assertEquals(1,runtime.machine.selection().get("revision").asLong());
    runtime.control(bytes(signUnchecked("control",next)),2);runtime.control(bytes(first),3);assertEquals(2,runtime.observed);assertEquals(2,runtime.files.controls.size());
  }
  @Test void reversedAndDuplicateChunksPreserveExactOriginalMember()throws Exception {
    byte[] plan=read(repository.resolve("packages/lifecycle-job/build/fixtures/a.plan.json"),4*MIB);byte[] padded=new byte[262144+plan.length];Arrays.fill(padded,0,262144,(byte)' ');System.arraycopy(plan,0,padded,262144,plan.length);ObjectNode m=manifestFor(ma,padded);byte[] manifest=bytes(m);runtime.files.chunk(bytes(signUnchecked("artifact",chunkPayload(m,"manifest.json",manifest,0,manifest))));
    ObjectNode last=chunkPayload(m,"plan.json",padded,1,plan);byte[] signed=bytes(signUnchecked("artifact",last));runtime.files.chunk(signed);runtime.files.chunk(signed);
    byte[] altered=plan.clone();altered[0]=' ';ObjectNode conflict=chunkPayload(m,"plan.json",padded,1,altered);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",conflict))));assertNull(runtime.files.bundle(m.get("bundle_sha256").asString()));
    runtime.files.chunk(bytes(signUnchecked("artifact",chunkPayload(m,"plan.json",padded,0,Arrays.copyOf(padded,262144)))));assertArrayEquals(padded,runtime.files.plan(m.get("bundle_sha256").asString()));runtime.files.chunk(signed);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",conflict))));
  }
  @Test void chunkShapeBoundsRejectInvalidCountIndexLengthEncodingAndCap()throws Exception {
    byte[] plan=read(repository.resolve("packages/lifecycle-job/build/fixtures/a.plan.json"),4*MIB);ObjectNode base=chunkPayload(ma,"plan.json",plan,0,plan);ObjectNode count=base.deepCopy();count.put("chunk_count",2);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",count))));ObjectNode index=base.deepCopy();index.put("chunk_index",1);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",index))));ObjectNode maximum=base.deepCopy();maximum.put("member_bytes",4194305);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",maximum))));ObjectNode invalid=base.deepCopy();invalid.put("data_base64","not?base64");assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",invalid))));
    byte[] shortData=new byte[262143];ObjectNode shortNonfinal=chunkPayload(ma,"plan.json",new byte[262145],0,shortData);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",shortNonfinal))));ObjectNode tooMany=base.deepCopy();tooMany.put("chunk_count",17);assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",tooMany))));assertTrue(runtime.files.controls.isEmpty());
  }
  @Test void sharedBindingPreventsCrossClusterControlAndArtifactTransplant()throws Exception {
    ObjectNode changed=config.deepCopy();changed.put("cluster_id","other-cluster");assertNotEquals(config.get("runtime_binding_sha256").asString(),hash(commonBinding(changed)));ObjectNode p=((ObjectNode)control("a",1,"activate").get("payload")).deepCopy();p.put("runtime_binding_sha256",hash(commonBinding(changed)));assertThrows(Exception.class,()->runtime.files.observe(bytes(signUnchecked("control",p))));byte[] plan=read(repository.resolve("packages/lifecycle-job/build/fixtures/a.plan.json"),4*MIB);ObjectNode chunk=chunkPayload(ma,"plan.json",plan,0,plan);chunk.put("runtime_binding_sha256",hash(commonBinding(changed)));assertThrows(Exception.class,()->runtime.files.chunk(bytes(signUnchecked("artifact",chunk))));assertTrue(runtime.files.controls.isEmpty());
  }

  @Test void malformedForeignRunContextStillUsesOriginalQuarantine()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);JsonNode malformed=value(Map.of("version","1.0.0","kind","control","context",Map.of("run_id","715b0000-0000-4000-8000-000000000999")));assertTrue(runtime.canAdmit(bytes(malformed)));runtime.raw(bytes(malformed),0);runtime.pump();assertEquals(0,runtime.machine.pendingInputs());runtime.snapshot(1);runtime.completed(1);List<JsonNode> outputs=new ArrayList<>();runtime.release(delivery->{if(delivery.role().equals("output"))outputs.add(parse(delivery.bytes(),4*MIB));});assertEquals(1,outputs.size());assertEquals("quarantine",outputs.get(0).get("kind").asString());assertEquals("invalid_integration_input",outputs.get(0).at("/document/category").asString());assertEquals(1,runtime.rawNext);
  }

  @Test void malformedWindowsContextCannotPoisonOwnershipBacklog()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);ObjectNode row=(ObjectNode)alice("715b0000-0000-4000-8000-000000000999");((ObjectNode)row.get("context")).remove("parser");runtime.raw(bytes(row),0);runtime.pump();assertEquals(0,runtime.machine.pendingInputs());runtime.snapshot(1);runtime.completed(1);List<JsonNode> outputs=new ArrayList<>();runtime.release(delivery->{if(delivery.role().equals("output"))outputs.add(parse(delivery.bytes(),4*MIB));});assertEquals(1,outputs.size());assertEquals("quarantine",outputs.get(0).get("kind").asString());assertEquals("invalid_integration_input",outputs.get(0).at("/document/category").asString());
  }
  @Test void validUnownedSourceProposalRemainsUnevaluatedAndUncommitted()throws Exception {
    install("a");runtime.control(bytes(control("a",1,"activate")),1);runtime.raw(bytes(alice("715b0000-0000-4000-8000-000000000999")),0);JsonNode before=runtime.machine.coreState();runtime.pump();assertEquals(1,runtime.machine.pendingInputs());assertEquals(0,runtime.machine.pendingOutputs());assertEquals(before,runtime.machine.coreState());
  }

  @Test void helperFailureDiagnosticsIdentifyFixedOperationWithoutRawMessages()throws Exception {
    String secret="SECRET source body \n forged_operation";var cause=new IllegalArgumentException("lifecycle_private_owner");var failed=new java.io.IOException(secret,cause);JsonNode diagnostic=LifecycleTool.failure(new String[]{"drain"},failed);assertEquals("drain",diagnostic.get("operation").asString());assertEquals("java.lang.IllegalArgumentException",diagnostic.get("cause_class").asString());assertEquals("lifecycle_private_owner",diagnostic.get("internal_category").asString());assertTrue(diagnostic.get("frames").size()<=4);assertFalse(new String(bytes(diagnostic)).contains(secret));assertTrue(bytes(diagnostic).length<4096);
    JsonNode untrusted=LifecycleTool.failure(new String[]{secret},new IllegalArgumentException(secret));assertEquals("unknown",untrusted.get("operation").asString());assertEquals("unclassified",untrusted.get("internal_category").asString());assertFalse(new String(bytes(untrusted)).contains("SECRET"));
  }

  @Test void effectiveUidMatchesActualOwnedFilesystem()throws Exception {assertEquals(((Number)Files.getAttribute(temp,"unix:uid")).longValue(),currentUid());privatePath(temp,true);assertDoesNotThrow(()->LifecycleTool.failure(new String[]{"drain"},new java.io.IOException()));}
  @Test void drainAndCommitRequireExplicitPinnedKafkaNamespace()throws Exception {
    assertThrows(IllegalArgumentException.class,()->LifecycleTool.run(new String[]{"drain","unused","group","topic","0","1",temp.toString()}));assertThrows(IllegalArgumentException.class,()->LifecycleTool.run(new String[]{"commit","unused","group","topic","0"}));
    JsonNode observed=value(Map.of("cluster_id","cluster-a","topics",Map.of("topic-a",Map.of("id","topic-id-a"))));assertDoesNotThrow(()->LifecycleTool.verifyPinned(observed,"cluster-a","topic-a","topic-id-a"));assertThrows(IllegalArgumentException.class,()->LifecycleTool.verifyPinned(observed,"cluster-b","topic-a","topic-id-a"));assertThrows(IllegalArgumentException.class,()->LifecycleTool.verifyPinned(observed,"cluster-a","topic-a","topic-id-b"));
  }

}
