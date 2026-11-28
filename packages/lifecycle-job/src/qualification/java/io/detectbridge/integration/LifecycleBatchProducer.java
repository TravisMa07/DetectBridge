package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.math.BigInteger;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.producer.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Qualification-only bounded admission transport. Receipts never establish worker processing. */
public final class LifecycleBatchProducer {
  record Accepted(String topic,int partition,long offset,long timestamp) {}
  interface Transport extends AutoCloseable {void verify()throws Exception;Accepted send(byte[] key,byte[] value)throws Exception;default void close()throws Exception {}}
  @FunctionalInterface interface Factory {Transport open()throws Exception;}
  @FunctionalInterface interface Publication {void publish(Path path,byte[] value)throws Exception;}
  interface PublicationOps {
    default void write(Path path,byte[] value)throws Exception {LifecycleSupport.write(path,value);}
    default void move(Path source,Path target)throws Exception {Files.move(source,target,StandardCopyOption.ATOMIC_MOVE);}
    default void force(Path path)throws Exception {sync(path);}
  }
  /** Retain an interrupted owned temporary as evidence; never treat it as a receipt. */
  static void publishMetadata(Path target,byte[] value)throws Exception {publishMetadata(target,value,new PublicationOps(){});}
  static void publishMetadata(Path target,byte[] value,PublicationOps operations)throws Exception {
    target=safe(target);privatePath(target.getParent(),true);check(value.length<=4096&&!Files.exists(target,LinkOption.NOFOLLOW_LINKS),"lifecycle_batch_metadata");
    Path partial=target.getParent().resolve(".partial-"+UUID.randomUUID());
    operations.write(partial,value);operations.force(partial);operations.move(partial,target);operations.force(target.getParent());
  }
  static final Set<String> REQUEST=Set.of("version","operation_id","worker_id","incarnation","command_sha256","cluster_id","topic","topic_id","records");
  static final Set<String> RECORD_KEYS=Set.of("index","run_id","key_base64","value_file","value_bytes","value_sha256");
  static void closed(JsonNode node,Set<String> keys) {check(node!=null&&node.isObject()&&new HashSet<>(node.propertyNames()).equals(keys),"lifecycle_batch_shape");}
  static String text(JsonNode node) {check(node!=null&&node.isString(),"lifecycle_batch_type");return node.asString();}
  static String uuid(JsonNode node) {String id=text(node);check(UUID.fromString(id).toString().equals(id),"lifecycle_batch_uuid");return id;}
  static long integer(JsonNode node,long min,long max) {check(node!=null&&node.isIntegralNumber(),"lifecycle_batch_integer");BigInteger n=new BigInteger(node.asString());check(n.compareTo(BigInteger.valueOf(min))>=0&&n.compareTo(BigInteger.valueOf(max))<=0,"lifecycle_batch_integer");return n.longValueExact();}
  static void names(Path directory,Set<String> expected)throws Exception {privatePath(directory,true);Set<String> observed=new HashSet<>();try(var files=Files.list(directory)){var iterator=files.iterator();while(iterator.hasNext()){Path p=iterator.next();check(observed.size()<129,"lifecycle_batch_contents");observed.add(p.getFileName().toString());}}check(observed.equals(expected),"lifecycle_batch_contents");}
  static byte[] input(Path root,JsonNode record)throws Exception {Path file=root.resolve("values").resolve(text(record.get("value_file")));privatePath(file,false);byte[] data=read(file,2*MIB);check(data.length==integer(record.get("value_bytes"),1,2*MIB)&&Json.sha(data).equals(text(record.get("value_sha256"))),"lifecycle_batch_value");return data;}
  static JsonNode validate(Path root,String requestHash,String cluster,String topic,String topicId)throws Exception {
    root=safe(root);privatePath(root,true);names(root,Set.of("request.json","values","attempts","acknowledgments","receipts"));
    for(String folder:List.of("attempts","acknowledgments","receipts"))names(root.resolve(folder),Set.of());
    Path file=root.resolve("request.json");privatePath(file,false);byte[] raw=read(file,RECORD);check(requestHash.matches("[a-f0-9]{64}")&&Json.sha(raw).equals(requestHash),"lifecycle_batch_request_hash");JsonNode request=parse(raw,RECORD);closed(request,REQUEST);check(Arrays.equals(raw,bytes(request)),"lifecycle_batch_canonical");
    check(text(request.get("version")).equals("1.0.0")&&uuid(request.get("operation_id")).equals(root.getFileName().toString()),"lifecycle_batch_operation");uuid(request.get("worker_id"));uuid(request.get("incarnation"));check(text(request.get("command_sha256")).matches("[a-f0-9]{64}"),"lifecycle_batch_command");
    check(text(request.get("cluster_id")).equals(cluster)&&cluster.length()<=128&&!cluster.isEmpty()&&text(request.get("topic")).equals(topic)&&topic.matches("[A-Za-z0-9._-]{1,128}")&&text(request.get("topic_id")).equals(topicId)&&!topicId.isEmpty()&&topicId.length()<=128,"lifecycle_batch_scope");
    JsonNode records=request.get("records");check(records.isArray()&&records.size()>=1&&records.size()<=128,"lifecycle_batch_count");Set<String> values=new HashSet<>();long total=0;int index=0;
    for(JsonNode record:records){closed(record,RECORD_KEYS);check(integer(record.get("index"),0,127)==index,"lifecycle_batch_index");String run=uuid(record.get("run_id")),name=String.format("%020d.value",index++);check(text(record.get("value_file")).equals(name),"lifecycle_batch_filename");values.add(name);String encoded=text(record.get("key_base64"));check(encoded.length()<=344,"lifecycle_batch_key");byte[] key=Base64.getDecoder().decode(encoded);check(key.length<=256&&Base64.getEncoder().encodeToString(key).equals(encoded)&&Arrays.equals(key,run.getBytes(StandardCharsets.UTF_8)),"lifecycle_batch_key");check(text(record.get("value_sha256")).matches("[a-f0-9]{64}"),"lifecycle_batch_value");total=Math.addExact(total,integer(record.get("value_bytes"),1,2*MIB));check(total<=8L*MIB,"lifecycle_batch_aggregate");input(root,record);}
    names(root.resolve("values"),values);return request;
  }
  static void metadata(Path path,JsonNode value,Publication publication)throws Exception {byte[] data=bytes(value);check(data.length<=4096&&!Files.exists(path,LinkOption.NOFOLLOW_LINKS),"lifecycle_batch_metadata");publication.publish(path,data);}
  static JsonNode run(Path root,String requestHash,String cluster,String topic,String topicId,Factory factory,Publication publication)throws Exception {
    root=safe(root);privatePath(root,true);Path requestFile=root.resolve("request.json");privatePath(requestFile,false);
    try(var file=FileChannel.open(requestFile,StandardOpenOption.WRITE);var lock=file.tryLock()) {
      check(lock!=null,"lifecycle_batch_locked");JsonNode request=validate(root,requestHash,cluster,topic,topicId);List<String> hashes=new ArrayList<>();long previous=-1;
      try(Transport transport=factory.open()) {for(JsonNode record:request.get("records")) {
        int index=(int)integer(record.get("index"),0,127);byte[] body=input(root,record),key=Base64.getDecoder().decode(text(record.get("key_base64")));String name=String.format("%020d.json",index);
        transport.verify();ObjectNode attempt=object();attempt.put("version","1.0.0");attempt.set("operation_id",request.get("operation_id"));attempt.put("request_sha256",requestHash);attempt.put("index",index);attempt.put("cluster_id",cluster);attempt.put("topic",topic);attempt.put("topic_id",topicId);attempt.put("partition",0);attempt.put("key_sha256",Json.sha(key));attempt.put("value_sha256",Json.sha(body));attempt.put("value_bytes",body.length);
        metadata(root.resolve("attempts").resolve(name),attempt,publication);Accepted accepted=transport.send(key,body);
        check(accepted.topic().equals(topic)&&accepted.partition()==0&&accepted.offset()>=0&&accepted.timestamp()>=-1,"lifecycle_batch_ack");
        ObjectNode ack=object();for(String field:List.of("version","operation_id","request_sha256","index","topic","partition","key_sha256","value_sha256"))ack.set(field,attempt.get(field));ack.put("offset",accepted.offset());ack.put("broker_timestamp",accepted.timestamp());metadata(root.resolve("acknowledgments").resolve(name),ack,publication);
        check(accepted.offset()>previous,"lifecycle_batch_offset");transport.verify();ObjectNode receipt=attempt.deepCopy();receipt.put("offset",accepted.offset());receipt.put("broker_timestamp",accepted.timestamp());receipt.put("acknowledgment_sha256",hash(ack));metadata(root.resolve("receipts").resolve(name),receipt,publication);hashes.add(hash(receipt));previous=accepted.offset();
      }}
      JsonNode summary=value(Map.of("version","1.0.0","operation_id",request.get("operation_id"),"request_sha256",requestHash,"completed",hashes.size(),"receipt_sha256",hashes));check(bytes(summary).length<=RECORD,"lifecycle_batch_summary");return summary;
    }
  }
  static final class KafkaTransport implements Transport {
    final Admin admin;final KafkaProducer<byte[],byte[]> producer;final String cluster,topic,topicId;
    KafkaTransport(String bootstrap,String cluster,String topic,String topicId){this.cluster=cluster;this.topic=topic;this.topicId=topicId;admin=Admin.create(Broker.properties(bootstrap));KafkaProducer<byte[],byte[]> opened;try{opened=new KafkaProducer<>(LifecycleTool.producer(bootstrap));}catch(RuntimeException failure){admin.close();throw failure;}producer=opened;}
    public void verify()throws Exception {String actual=admin.describeCluster().clusterId().get(15,TimeUnit.SECONDS);var info=admin.describeTopics(List.of(topic)).allTopicNames().get(15,TimeUnit.SECONDS).get(topic);check(actual.equals(cluster)&&info!=null&&info.name().equals(topic)&&info.topicId().toString().equals(topicId)&&info.partitions().size()==1&&info.partitions().get(0).partition()==0,"lifecycle_batch_namespace");}
    public Accepted send(byte[] key,byte[] body)throws Exception {var ack=producer.send(new ProducerRecord<byte[],byte[]>(topic,0,key,body)).get(35,TimeUnit.SECONDS);return new Accepted(ack.topic(),ack.partition(),ack.offset(),ack.timestamp());}
    public void close(){try{producer.close(java.time.Duration.ofSeconds(15));}finally{admin.close(java.time.Duration.ofSeconds(15));}}
  }
  public static void main(String[] args) {
    try {check(args.length==8,"lifecycle_batch_arguments");codeSource(LifecycleBatchProducer.class,args[0]);codeSource(LifecycleSupport.class,args[1]);codeSource(Schemas.class,PRODUCER);check(LifecycleBatchProducer.class.getClassLoader()==LifecycleSupport.class.getClassLoader()&&LifecycleSupport.class.getClassLoader()==Schemas.class.getClassLoader(),"lifecycle_batch_classloader");JsonNode summary=run(Path.of(args[6]),args[7],args[3],args[4],args[5],()->new KafkaTransport(args[2],args[3],args[4],args[5]),LifecycleBatchProducer::publishMetadata);System.out.println(new String(bytes(summary),StandardCharsets.UTF_8));}
    catch(Exception failure){System.err.println(new String(bytes(value(Map.of("category","lifecycle_qualification_batch_failed","exception_class",LifecycleTool.safeClass(failure.getClass().getName())))),StandardCharsets.UTF_8));System.exit(1);}
  }
}
