package io.detectbridge.integration;

import static io.detectbridge.integration.LifecycleSupport.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import org.junit.jupiter.api.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Injected transport/publication mechanics only; none of these cases proves Kafka acceptance. */
class LifecycleBatchProducerTest {
  Path base,root;ObjectNode request;int opened,sends,verified;
  final String cluster="test-cluster",topic="test.input",topicId="test-topic-id",run="715b0000-0000-4000-8000-000000000206";
  @BeforeEach void setup()throws Exception {base=Files.createTempDirectory(Path.of("build"),"batch-");root=base.resolve(UUID.randomUUID().toString());mkdir(root);for(String name:List.of("values","attempts","acknowledgments","receipts"))mkdir(root.resolve(name));prepare(3,1);}
  @AfterEach void cleanup()throws Exception {try(var files=Files.walk(base)){for(Path path:files.sorted(Comparator.reverseOrder()).toList())Files.delete(path);}}
  void prepare(int count,int size)throws Exception {
    opened=0;sends=0;verified=0;
    try(var files=Files.list(root.resolve("values"))){for(Path p:files.toList())Files.delete(p);}request=object();request.put("version","1.0.0");request.put("operation_id",root.getFileName().toString());request.put("worker_id","71500000-0000-4000-8000-000000000021");request.put("incarnation","71500000-0000-4000-8000-000000000030");request.put("command_sha256","a".repeat(64));request.put("cluster_id",cluster);request.put("topic",topic);request.put("topic_id",topicId);var records=request.putArray("records");
    for(int index=0;index<count;index++){byte[] value=new byte[size];Arrays.fill(value,(byte)(index%100));String name=String.format("%020d.value",index);write(root.resolve("values").resolve(name),value);records.add(value(Map.of("index",index,"run_id",run,"key_base64",Base64.getEncoder().encodeToString(run.getBytes(java.nio.charset.StandardCharsets.UTF_8)),"value_file",name,"value_bytes",size,"value_sha256",io.detectbridge.transport.Json.sha(value))));}saveRequest();
  }
  String saveRequest()throws Exception {Path path=root.resolve("request.json");Files.deleteIfExists(path);write(path,bytes(request));return hash(request);}
  LifecycleBatchProducer.Transport transport(){return new LifecycleBatchProducer.Transport(){public void verify(){verified++;}public LifecycleBatchProducer.Accepted send(byte[] key,byte[] value){return new LifecycleBatchProducer.Accepted(topic,0,10+2L*sends++,1000+sends);}};}
  JsonNode execute()throws Exception {return execute(()->transport(),LifecycleBatchProducer::publishMetadata);}
  JsonNode execute(LifecycleBatchProducer.Factory factory,LifecycleBatchProducer.Publication publication)throws Exception {return LifecycleBatchProducer.run(root,io.detectbridge.transport.Json.sha(read(root.resolve("request.json"),65536)),cluster,topic,topicId,()->{opened++;return factory.open();},publication);}
  long files(String directory)throws Exception {try(var files=Files.list(root.resolve(directory))){return files.count();}}
  void rejectedBeforeTransport() {assertThrows(Exception.class,()->execute());assertEquals(0,opened);assertEquals(0,sends);}
  @Test void orderedMechanicsForcesAttemptRawAckReceiptBeforeNextSend()throws Exception {
    List<String> order=new ArrayList<>();JsonNode summary=execute(()->new LifecycleBatchProducer.Transport(){public void verify(){order.add("pin");}public LifecycleBatchProducer.Accepted send(byte[] k,byte[] v){order.add("send");return new LifecycleBatchProducer.Accepted(topic,0,sends++, -1);}},(path,data)->{order.add(path.getParent().getFileName().toString());publish(path,data);});
    assertEquals(List.of("pin","attempts","send","acknowledgments","pin","receipts","pin","attempts","send","acknowledgments","pin","receipts","pin","attempts","send","acknowledgments","pin","receipts"),order);assertEquals(3,summary.get("completed").asInt());assertEquals(Set.of("version","operation_id","request_sha256","completed","receipt_sha256"),new HashSet<>(summary.propertyNames()));
    for(int i=0;i<3;i++){String name=String.format("%020d.json",i);JsonNode ack=parse(read(root.resolve("acknowledgments").resolve(name),4096),4096),receipt=parse(read(root.resolve("receipts").resolve(name),4096),4096);assertEquals(hash(ack),receipt.get("acknowledgment_sha256").asString());assertEquals(hash(receipt),summary.get("receipt_sha256").get(i).asString());}
  }
  @Test void maximumCountAndGappedIncreasingOffsetsAreAdmissibleMechanics()throws Exception {prepare(128,1);JsonNode summary=execute();assertEquals(128,summary.get("completed").asInt());assertEquals(256,verified);assertEquals(128,files("receipts"));}
  @Test void countAndClosedFieldsRejectBeforeEffects()throws Exception {for(int count:new int[]{0,129}){prepare(count,1);rejectedBeforeTransport();}prepare(1,1);request.put("extra",true);saveRequest();rejectedBeforeTransport();}
  @Test void booleanFractionOverflowAndDuplicateIndexReject()throws Exception {for(JsonNode bad:List.of(value(true),value(0.5),parse("9223372036854775808".getBytes(),64),value(1))){prepare(1,1);((ObjectNode)request.at("/records/0")).set("index",bad);Files.delete(root.resolve("request.json"));write(root.resolve("request.json"),io.detectbridge.transport.Json.bytes(request));rejectedBeforeTransport();}}
  @Test void exactValueAndAggregateBoundsThenPlusOneReject()throws Exception {prepare(4,2*MIB);assertEquals(4,execute().get("completed").asInt());for(String directory:List.of("attempts","acknowledgments","receipts"))try(var files=Files.list(root.resolve(directory))){for(Path p:files.toList())Files.delete(p);}prepare(5,2*MIB);Path last=root.resolve("values/00000000000000000004.value");Files.write(last,new byte[]{4},StandardOpenOption.TRUNCATE_EXISTING);((ObjectNode)request.at("/records/4")).put("value_bytes",1).put("value_sha256",io.detectbridge.transport.Json.sha(new byte[]{4}));saveRequest();rejectedBeforeTransport();prepare(1,2*MIB+1);rejectedBeforeTransport();}
  @Test void lateInvalidValuePrevalidationPreventsEvenFirstAttempt()throws Exception {Files.write(root.resolve("values/00000000000000000002.value"),new byte[]{44},StandardOpenOption.TRUNCATE_EXISTING);rejectedBeforeTransport();assertEquals(0,files("attempts"));}
  @Test void privateModeHardLinkSymlinkAndUnexpectedValueReject()throws Exception {
    Path first=root.resolve("values/00000000000000000000.value");Files.setPosixFilePermissions(first,PosixFilePermissions.fromString("rw-r--r--"));rejectedBeforeTransport();Files.setPosixFilePermissions(first,PosixFilePermissions.fromString("rw-------"));Files.createLink(base.resolve("linked"),first);rejectedBeforeTransport();Files.delete(base.resolve("linked"));Files.delete(first);Files.createSymbolicLink(first,root.resolve("values/00000000000000000001.value"));rejectedBeforeTransport();Files.delete(first);write(first,new byte[]{0});write(root.resolve("values/extra"),new byte[]{1});rejectedBeforeTransport();
  }
  @Test void existingAttemptOrPartialAlwaysRefusesReplay()throws Exception {write(root.resolve("attempts/.partial-"+UUID.randomUUID()),new byte[]{1});rejectedBeforeTransport();}
  @Test void sendFailureRetainsCertifiedPrefixAndOneUncertainAttempt()throws Exception {
    assertThrows(java.io.IOException.class,()->execute(()->new LifecycleBatchProducer.Transport(){public void verify(){}public LifecycleBatchProducer.Accepted send(byte[] k,byte[] v)throws Exception {if(sends++==1)throw new java.io.IOException("injected_send");return new LifecycleBatchProducer.Accepted(topic,0,5,-1);}},LifecycleSupport::publish));assertEquals(2,files("attempts"));assertEquals(1,files("acknowledgments"));assertEquals(1,files("receipts"));assertThrows(Exception.class,()->execute());assertEquals(1,opened);
  }
  @Test void postSendNamespaceFailurePreservesRawAckWithoutReceipt()throws Exception {
    assertThrows(java.io.IOException.class,()->execute(()->new LifecycleBatchProducer.Transport(){public void verify()throws Exception {if(++verified==2)throw new java.io.IOException("injected_scope");}public LifecycleBatchProducer.Accepted send(byte[] k,byte[] v){sends++;return new LifecycleBatchProducer.Accepted(topic,0,7,-1);}},LifecycleSupport::publish));assertEquals(1,sends);assertEquals(1,files("attempts"));assertEquals(1,files("acknowledgments"));assertEquals(0,files("receipts"));
  }
  @Test void failedAttemptForceNeverInvokesSend()throws Exception {assertThrows(java.io.IOException.class,()->execute(()->transport(),(p,b)->{throw new java.io.IOException("injected_force");}));assertEquals(0,sends);}
  @Test void receiptPublicationFailureCannotStartNextAttempt()throws Exception {assertThrows(java.io.IOException.class,()->execute(()->transport(),(p,b)->{publish(p,b);if(p.getParent().endsWith("receipts"))throw new java.io.IOException("injected_receipt_force");}));assertEquals(1,sends);assertEquals(1,files("attempts"));assertEquals(1,files("acknowledgments"));assertEquals(1,files("receipts"));}
  @Test void mutationAfterPrevalidationIsRejectedBeforeItsAttempt()throws Exception {assertThrows(Exception.class,()->execute(()->{Files.write(root.resolve("values/00000000000000000000.value"),new byte[]{9},StandardOpenOption.TRUNCATE_EXISTING);return transport();},LifecycleSupport::publish));assertEquals(0,sends);assertEquals(0,files("attempts"));}
  @Test void noncanonicalRequestAndChangedScopeRejectBeforeEffects()throws Exception {Files.writeString(root.resolve("request.json"),new String(bytes(request))+"\n",StandardOpenOption.TRUNCATE_EXISTING);assertThrows(Exception.class,()->LifecycleBatchProducer.run(root,io.detectbridge.transport.Json.sha(Files.readAllBytes(root.resolve("request.json"))),cluster,topic,topicId,()->{opened++;return transport();},LifecycleSupport::publish));assertEquals(0,opened);saveRequest();assertThrows(Exception.class,()->LifecycleBatchProducer.run(root,hash(request),"other",topic,topicId,()->{opened++;return transport();},LifecycleSupport::publish));assertEquals(0,opened);}
  @Test void interruptedRealPartialWriteRemainsPrivateAndCannotAuthorizeSend()throws Exception {
    assertThrows(java.io.IOException.class,()->execute(()->transport(),(path,data)->LifecycleBatchProducer.publishMetadata(path,data,new LifecycleBatchProducer.PublicationOps(){public void write(Path partial,byte[] value)throws Exception {LifecycleSupport.write(partial,Arrays.copyOf(value,7));throw new java.io.IOException("injected_short_write");}})));
    assertEquals(0,sends);Path partial;try(var files=Files.list(root.resolve("attempts"))){partial=files.findFirst().orElseThrow();}assertTrue(partial.getFileName().toString().matches("\\.partial-[a-f0-9-]{36}"));privatePath(partial,false);assertEquals(7,Files.size(partial));assertFalse(Files.exists(root.resolve("attempts/00000000000000000000.json")));assertThrows(Exception.class,()->execute());assertEquals(1,opened);
  }
  @Test void failedAtomicRenameRetainsForcedRealPartialBeforeAnySend()throws Exception {
    assertThrows(java.io.IOException.class,()->execute(()->transport(),(path,data)->LifecycleBatchProducer.publishMetadata(path,data,new LifecycleBatchProducer.PublicationOps(){public void move(Path partial,Path target)throws Exception {assertTrue(Files.size(partial)>0);privatePath(partial,false);throw new java.io.IOException("injected_rename");}})));
    assertEquals(0,sends);assertEquals(1,files("attempts"));assertEquals(0,files("acknowledgments"));assertEquals(0,files("receipts"));assertThrows(Exception.class,()->execute());
  }
  @Test void failedParentForceRetainsRenamedAckAndNeverCreatesReceiptOrNextAttempt()throws Exception {
    assertThrows(java.io.IOException.class,()->execute(()->transport(),(path,data)->LifecycleBatchProducer.publishMetadata(path,data,new LifecycleBatchProducer.PublicationOps(){public void force(Path p)throws Exception {if(p.equals(root.resolve("acknowledgments").toAbsolutePath()))throw new java.io.IOException("injected_parent_force");sync(p);}})));
    assertEquals(1,sends);assertEquals(1,files("attempts"));assertEquals(1,files("acknowledgments"));assertEquals(0,files("receipts"));assertTrue(Files.isRegularFile(root.resolve("acknowledgments/00000000000000000000.json")));assertThrows(Exception.class,()->execute());
  }
}
