package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.security.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;

/** Bounded local helper. Explicit consumer seeks never imply a committed offset. */
public final class LifecycleTool {
  public static Properties consumer(String bootstrap,String group) {
    Properties p=Broker.properties(bootstrap);p.put("group.id",group);p.put("enable.auto.commit","false");p.put("auto.offset.reset","none");p.put("key.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");p.put("value.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");p.put("max.poll.records","1");p.put("fetch.max.bytes","8388608");p.put("max.partition.fetch.bytes","4194304");return p;
  }
  public static Properties producer(String bootstrap) {Properties p=Broker.properties(bootstrap);p.put("key.serializer","org.apache.kafka.common.serialization.ByteArraySerializer");p.put("value.serializer","org.apache.kafka.common.serialization.ByteArraySerializer");p.put("acks","all");p.put("enable.idempotence","true");p.put("max.request.size","4194304");p.put("max.block.ms","15000");p.put("delivery.timeout.ms","30000");p.put("request.timeout.ms","10000");return p;}
  public static JsonNode inspect(String bootstrap,Collection<String> names)throws Exception {
    try(Admin admin=Admin.create(Broker.properties(bootstrap));var consumer=new KafkaConsumer<byte[],byte[]>(consumer(bootstrap,"detectbridge-lifecycle-inspect"))) {
      var descriptions=admin.describeTopics(names).allTopicNames().get(15,TimeUnit.SECONDS);var parts=names.stream().map(n->new TopicPartition(n,0)).toList();var starts=consumer.beginningOffsets(parts,Duration.ofSeconds(15));var ends=consumer.endOffsets(parts,Duration.ofSeconds(15));var topics=new TreeMap<String,Object>();
      for(String name:names){var d=descriptions.get(name);check(d.partitions().size()==1,"lifecycle_topic_topology");topics.put(name,Map.of("id",d.topicId().toString(),"partitions",1,"earliest",starts.get(new TopicPartition(name,0)),"end",ends.get(new TopicPartition(name,0))));}
      return value(Map.of("cluster_id",admin.describeCluster().clusterId().get(15,TimeUnit.SECONDS),"topics",topics));
    }
  }
  public static void verifyBroker(JsonNode config)throws Exception {
    List<String> names=new ArrayList<>();config.get("topics").forEach(t->names.add(t.get("name").asString()));JsonNode state=inspect(config.get("bootstrap").asString(),names);
    check(state.get("cluster_id").equals(config.get("cluster_id")),"lifecycle_cluster_changed");for(JsonNode topic:config.get("topics"))check(state.at("/topics/"+topic.get("name").asString()+"/id").equals(topic.get("id")),"lifecycle_topic_changed");
  }
  static void verifyPinned(JsonNode observed,String cluster,String topic,String topicId) {
    check(observed.path("cluster_id").asString().equals(cluster)&&observed.at("/topics/"+topic+"/id").asString().equals(topicId),"lifecycle_destination");
  }
  static void pinned(String bootstrap,String cluster,String topic,String topicId)throws Exception {verifyPinned(inspect(bootstrap,List.of(topic)),cluster,topic,topicId);}
  static Object run(String[] a)throws Exception {
    check(a.length>0,"lifecycle_arguments");String command=a[0];
    if(command.equals("keygen")){check(a.length==3,"lifecycle_arguments");LifecycleCrypto.generate(Path.of(a[1]),Path.of(a[2]));byte[] pub=read(Path.of(a[2]),64);return Map.of("public_key",Base64.getEncoder().encodeToString(pub),"key_sha256",Json.sha(pub));}
    if(command.equals("sign")){check(a.length==6,"lifecycle_arguments");String domain=a[1].replace("detectbridge.p15b.","").replace("/1","");PrivateKey key=LifecycleCrypto.privateKey(Path.of(a[2]));PublicKey pub=LifecycleCrypto.publicKey(Base64.getEncoder().encodeToString(read(Path.of(a[3]),64)));JsonNode signed=LifecycleCrypto.sign(domain,parse(read(Path.of(a[4]),512*1024),512*1024),key,pub);write(Path.of(a[5]),bytes(signed));sync(Path.of(a[5]).toAbsolutePath().getParent());return Map.of("sha256",hash(signed),"bytes",bytes(signed).length);}
    if(command.equals("verify")){check(a.length==4,"lifecycle_arguments");String domain=a[1].replace("detectbridge.p15b.","").replace("/1","");PublicKey pub=LifecycleCrypto.publicKey(Base64.getEncoder().encodeToString(read(Path.of(a[2]),64)));byte[] wire=read(Path.of(a[3]),512*1024);try{JsonNode wrapper=parse(wire,512*1024);JsonNode payload=LifecycleCrypto.verify(domain,wrapper,pub);return Map.of("verified",true,"payload",payload,"payload_sha256",hash(payload));}catch(IllegalArgumentException|java.security.SignatureException invalid){return Map.of("verified",false,"category","signature_invalid");}}
    if(command.equals("inspect")||command.equals("create")) {
      check(a.length==3,"lifecycle_arguments");JsonNode request=parse(read(Path.of(a[2]),RECORD),RECORD);List<String> names=new ArrayList<>();request.propertyNames().forEach(names::add);check(!names.isEmpty()&&names.size()<=20,"lifecycle_topic_count");
      if(command.equals("create"))try(Admin admin=Admin.create(Broker.properties(a[1]))){List<NewTopic> topics=new ArrayList<>();for(String name:names){check(name.matches("[A-Za-z0-9._-]{1,128}")&&request.get(name).isIntegralNumber(),"lifecycle_topic_request");topics.add(new NewTopic(name,1,(short)1).configs(Map.of("cleanup.policy","delete","retention.ms","-1","retention.bytes","-1","max.message.bytes",request.get(name).asString(),"min.insync.replicas","1")));}try{admin.createTopics(topics).all().get(15,TimeUnit.SECONDS);}catch(java.util.concurrent.ExecutionException e){if(!(e.getCause() instanceof org.apache.kafka.common.errors.TopicExistsException))throw e;}}
      return inspect(a[1],names);
    }
    if(command.equals("send")){check(a.length==7,"lifecycle_arguments");JsonNode before=inspect(a[1],List.of(a[3]));check(before.get("cluster_id").asString().equals(a[2])&&before.at("/topics/"+a[3]+"/id").asString().equals(a[4]),"lifecycle_destination");byte[] body=read(Path.of(a[6]),4*MIB);try(var producer=new KafkaProducer<byte[],byte[]>(producer(a[1]))){var metadata=producer.send(new ProducerRecord<byte[],byte[]>(a[3],0,a[5].getBytes(java.nio.charset.StandardCharsets.UTF_8),body)).get(35,TimeUnit.SECONDS);JsonNode after=inspect(a[1],List.of(a[3]));check(after.get("cluster_id").equals(before.get("cluster_id"))&&after.at("/topics/"+a[3]+"/id").equals(before.at("/topics/"+a[3]+"/id")),"lifecycle_destination");return Map.of("topic",a[3],"partition",0,"offset",metadata.offset(),"value_sha256",Json.sha(body));}}
    if(command.equals("commit")){check(a.length==7,"lifecycle_arguments");long next=Long.parseLong(a[6]);check(next>=0,"lifecycle_offset");pinned(a[1],a[3],a[4],a[5]);try(var consumer=new KafkaConsumer<byte[],byte[]>(consumer(a[1],a[2]))){consumer.commitSync(Map.of(new TopicPartition(a[4],0),new OffsetAndMetadata(next)),Duration.ofSeconds(15));}pinned(a[1],a[3],a[4],a[5]);return Map.of("next_offset",next,"cluster_id",a[3],"topic_id",a[5]);}
    if(command.equals("drain")){check(a.length==9,"lifecycle_arguments");long start=Long.parseLong(a[6]);int limit=Integer.parseInt(a[7]);check(start>=0&&limit>0&&limit<=128,"lifecycle_drain_limit");Path out=safe(Path.of(a[8]));privatePath(out,true);pinned(a[1],a[3],a[4],a[5]);var records=new ArrayList<Object>();long next=start;try(var consumer=new KafkaConsumer<byte[],byte[]>(consumer(a[1],a[2]))){TopicPartition part=new TopicPartition(a[4],0);consumer.assign(List.of(part));long earliest=consumer.beginningOffsets(List.of(part)).get(part),end=consumer.endOffsets(List.of(part)).get(part);check(start>=earliest&&start<=end,"lifecycle_preservation_gap");consumer.seek(part,start);long deadline=System.nanoTime()+Duration.ofSeconds(5).toNanos();while(records.size()<limit&&next<end&&System.nanoTime()<deadline){for(var row:consumer.poll(Duration.ofMillis(200))){byte[] body=row.value();check(body!=null&&body.length<=4*MIB,"lifecycle_drain_value");String name=String.format("%020d.value",row.offset());write(out.resolve(name),body);records.add(Map.of("topic",row.topic(),"partition",row.partition(),"offset",row.offset(),"value_sha256",Json.sha(body),"value_file",name,"key_base64",Base64.getEncoder().encodeToString(row.key()==null?new byte[0]:row.key())));}next=consumer.position(part);}sync(out);}pinned(a[1],a[3],a[4],a[5]);return Map.of("records",records,"next_offset",next,"cluster_id",a[3],"topic_id",a[5]);}
    throw new IllegalArgumentException("lifecycle_arguments");
  }
  static JsonNode failure(String[] args,Throwable failure) {
    String operation=args.length>0&&Set.of("keygen","sign","verify","inspect","create","send","commit","drain").contains(args[0])?args[0]:"unknown";
    Set<String> safeCategories=Set.of("lifecycle_arguments","lifecycle_topic_topology","lifecycle_topic_count","lifecycle_topic_request","lifecycle_destination","lifecycle_offset","lifecycle_drain_limit","lifecycle_preservation_gap","lifecycle_drain_value","lifecycle_private_path","lifecycle_private_owner","lifecycle_private_mode","lifecycle_private_link","lifecycle_symlink","lifecycle_regular_file","lifecycle_file_limit","lifecycle_path","lifecycle_input_limit","lifecycle_invalid_json","lifecycle_integer_syntax","lifecycle_signature_domain","lifecycle_base64","lifecycle_key_encoding","lifecycle_public_key_encoding","lifecycle_signing_key","lifecycle_invalid_signature","lifecycle_signature_size","lifecycle_immutable_conflict","lifecycle_store_entries","lifecycle_storage_exhausted","lifecycle_worker_key_pair","lifecycle_artifact_mismatch","lifecycle_binding","lifecycle_authority_key","lifecycle_worker_key","lifecycle_schema_control","lifecycle_schema_artifact","lifecycle_schema_ack","lifecycle_schema_output","lifecycle_schema_worker-config","lifecycle_schema_state","lifecycle_schema_manifest");
    Throwable root=failure;String internal="unclassified";Set<Throwable> seen=Collections.newSetFromMap(new IdentityHashMap<>());
    for(int depth=0;root!=null&&depth<16&&seen.add(root);depth++){String message=root.getMessage();if(message!=null&&safeCategories.contains(message))internal=message;Throwable next=root.getCause();if(next==null||seen.contains(next))break;root=next;}
    if(root==null)root=failure;
    var result=object();result.put("category","lifecycle_helper_failed");result.put("operation",operation);result.put("exception_class",safeClass(failure.getClass().getName()));result.put("cause_class",safeClass(root.getClass().getName()));result.put("internal_category",internal);
    var frames=result.putArray("frames");for(StackTraceElement frame:Arrays.stream(root.getStackTrace()).limit(4).toList()){var item=frames.addObject();item.put("class",safeClass(frame.getClassName()));item.put("method",frame.getMethodName().matches("[A-Za-z_$<>][A-Za-z0-9_$<>]{0,63}")?frame.getMethodName():"unknown");item.put("line",frame.getLineNumber());}
    return result;
  }
  static String safeClass(String name){return name.matches("[A-Za-z_$][A-Za-z0-9_$.]{0,159}")?name:"java.lang.Throwable";}
  public static void main(String[] args){try{System.out.println(new String(bytes(value(run(args))),java.nio.charset.StandardCharsets.UTF_8));}catch(Exception failure){System.err.println(new String(bytes(failure(args,failure)),java.nio.charset.StandardCharsets.UTF_8));System.exit(1);}}

}
