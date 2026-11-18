package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Value-free CLI. Runs only against an explicitly frozen private broker/root. */
public final class Main {
  public static final String INPUT="detectbridge.integration.input.v1";
  public static final List<String> TOPICS=List.of(INPUT,"detectbridge.tagged-events.v1","detectbridge.detections.v1",
      "detectbridge.processing-diagnostics.v1","detectbridge.integration.manifests.v1","detectbridge.integration.preservation.v1",
      "detectbridge.integration.quarantine.v1","detectbridge.integration.receipts.v1","detectbridge.integration.writer-failures.v1");
  public static final Map<String,Long> LIMITS=Map.of("archive_bytes",2147483648L,"reserve_bytes",134217728L,"object_bytes",33554432L,"segment_bytes",16777216L,"segment_rows",256L);
  static String implementation()throws Exception {return Json.sha(Files.readAllBytes(Path.of(Main.class.getProtectionDomain().getCodeSource().getLocation().toURI())));}
  static Store.Hook hook(){return phase->{
    if(phase.equals(System.getenv("DETECTBRIDGE_ARCHIVE_CRASH")))Runtime.getRuntime().halt(86);
    if(phase.equals("after_directory_sync")&&"true".equals(System.getenv("DETECTBRIDGE_ARCHIVE_PAUSE"))) {
      Path marker=Path.of("/work/pause.marker");
      if(!Files.exists(marker)) {Store.write(marker,new byte[]{1});try{Thread.sleep(12000);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new Failure("interrupted");}}
    }
  };}
  static Properties properties(JsonNode c) {
    var p=Broker.properties(c.get("bootstrap").asString());p.put("group.id",c.get("group").asString());p.put("enable.auto.commit","false");p.put("auto.offset.reset","none");
    p.put("key.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");p.put("value.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");
    p.put("session.timeout.ms","6000");p.put("heartbeat.interval.ms","1500");p.put("max.poll.records","4");p.put("fetch.max.bytes","16777216");p.put("max.partition.fetch.bytes","4194304");p.put("max.poll.interval.ms","300000");return p;
  }
  static JsonNode topicState(String bootstrap)throws Exception {
    try(Admin a=Admin.create(Broker.properties(bootstrap))) {
      var descriptions=a.describeTopics(TOPICS).allTopicNames().get(15,TimeUnit.SECONDS);var topics=new TreeMap<String,Object>();
      for(String name:TOPICS){var t=descriptions.get(name);check(t.partitions().size()==1,"topic_topology");topics.put(name,t.topicId().toString());}
      return JSON.valueToTree(Map.of("cluster",a.describeCluster().clusterId().get(15,TimeUnit.SECONDS),"topics",topics));
    }
  }
  static void verifyBroker(JsonNode c)throws Exception {
    JsonNode state=topicState(c.get("bootstrap").asString());check(state.get("cluster").equals(c.get("cluster")),"cluster_changed");for(JsonNode t:c.get("topics"))check(state.get("topics").get(t.get("name").asString()).equals(t.get("id")),"topic_changed");
  }
  static Map<String,Object> initialize(Path root,String bootstrap,Path request,Path registry)throws Exception {
    JsonNode r=read(Store.bounded(request,MIB),MIB);check(r.isObject()&&r.has("starts")&&r.has("provenance")&&r.has("limits")&&r.size()==3,"init_request");
    var objects=new TreeSet<String>();long total=0;
    check(Files.isDirectory(registry,LinkOption.NOFOLLOW_LINKS),"registry_missing");Store.safeAncestors(registry.toAbsolutePath());
    try(var files=Files.list(registry)) {for(Path p:files.toList()){String hash=p.getFileName().toString();byte[] b=Store.bounded(p,OBJECT);total+=b.length;check(hash.matches("[a-f0-9]{64}")&&Json.sha(b).equals(hash)&&objects.size()<128&&total<=64L*MIB,"registry_invalid");objects.add(hash);}}
    check(r.get("starts").size()==9,"starts_required");JsonNode state=topicState(bootstrap);var topics=new ArrayList<Object>();
    for(String name:TOPICS){JsonNode start=r.get("starts").get(name);check(start!=null&&start.isIntegralNumber()&&start.canConvertToLong()&&start.asLong()>=0,"starts_required");topics.add(Map.of("name",name,"id",state.get("topics").get(name).asString(),"partition",0,"start",start.asLong()));}
    String id=UUID.randomUUID().toString();JsonNode c=JSON.valueToTree(Map.of("version","1.0.0","archive_id",id,"cluster",state.get("cluster"),"bootstrap",bootstrap,"group","detectbridge-archive-v1-"+id,"implementation_sha256",implementation(),"limits",r.get("limits"),"topics",topics,"objects",objects,"provenance",r.get("provenance")));
    Store.validateConfig(c);Store.create(root,c);try(var store=new Store(root,true,hook())){register(store,registry);return store.progress();}
  }
  static void register(Store store,Path registry)throws IOException {for(String sha:Store.strings(store.config.get("objects")))store.putObject(sha,Store.bounded(registry.resolve(sha),OBJECT));}
  static JsonNode parsed(byte[] value) {
    if(value==null||value.length>2*MIB)return null;
    try{return read(value,2*MIB);}catch(IOException e){return null;}
  }
  static String sourceIdentity(JsonNode doc) {return doc.at("/context/run_id").asString("")+"/"+doc.at("/raw/record_id").asString("");}
  static String fingerprint(JsonNode doc) {
    ObjectNode context=((ObjectNode)doc.get("context")).deepCopy();context.remove("receipt");return hash(List.of(doc.get("raw"),context));
  }
  static String category(Store s,String topic,byte[] value,List<JsonNode> pending)throws IOException {
    if(!topic.equals(INPUT))return "derived";
    JsonNode doc=parsed(value);if(doc==null||!doc.isObject())return "opaque";
    String kind=doc.path("kind").asString("");
    if(Set.of("run_end","source_boundary").contains(kind))return "control";
    if(!Set.of("record","windows_record").contains(kind))return "invalid_source";
    if(!doc.path("raw").isObject()||!doc.path("context").isObject()||!doc.at("/raw/record_id").isTextual()||!doc.at("/raw/evidence/sha256").isTextual())return "invalid_source";
    JsonNode evidence=doc.at("/raw/evidence");String expected=evidence.get("sha256").asString();check(expected.matches("[0-9a-f]{64}"),"source_evidence_hash");
    if(evidence.has("reference")) {
      JsonNode ref=evidence.get("reference");check(ref.path("object_sha256").isTextual(),"source_reference_invalid");String sha=ref.get("object_sha256").asString();check(Store.strings(s.config.get("objects")).contains(sha),"missing_registered_evidence");
      if(ref.has("byte_range")) {JsonNode range=ref.get("byte_range");check(range.path("offset").isIntegralNumber()&&range.get("offset").canConvertToLong()&&range.path("length").isIntegralNumber()&&range.get("length").canConvertToInt(),"source_range_invalid");s.range(sha,range.get("offset").asLong(),range.get("length").asInt(),expected);}
      else check(Json.sha(s.object(sha)).equals(expected),"source_evidence_hash");
    } else if(evidence.has("inline")) {
      byte[] raw;
      if(evidence.path("encoding").asString("").equals("base64"))raw=decode(evidence.get("inline"));
      else {check(evidence.path("encoding").asString("").equals("utf-8")&&evidence.get("inline").isTextual(),"source_inline_invalid");raw=evidence.get("inline").asString().getBytes(java.nio.charset.StandardCharsets.UTF_8);}
      check(raw!=null&&Json.sha(raw).equals(expected),"source_evidence_hash");
    } else return "invalid_source";
    final boolean[] conflict={false};String identity=sourceIdentity(doc),content;
    try{content=fingerprint(doc);}catch(IllegalArgumentException e){return "invalid_source";}
    Store.RowAction compare=row->{JsonNode previous=parsed(decode(row.get("value")));if(previous!=null&&previous.path("raw").isObject()&&previous.path("context").isObject()&&sourceIdentity(previous).equals(identity)){try{if(!fingerprint(previous).equals(content))conflict[0]=true;}catch(IllegalArgumentException e){conflict[0]=true;}}};
    s.forEachRow(INPUT,compare);for(JsonNode row:pending)compare.accept(row);return conflict[0]?"semantic_conflict":"source";
  }
  static JsonNode wire(Store s,ConsumerRecord<byte[],byte[]> r,List<JsonNode> pending)throws IOException {
    check(r.value()==null||r.value().length<=2*MIB,"wire_value_limit");var headers=new ArrayList<Object>();for(var h:r.headers()){check(headers.size()<128,"header_limit");var m=new TreeMap<String,Object>();m.put("name",h.key());m.put("value",b64(h.value()));headers.add(m);}
    var m=new TreeMap<String,Object>();JsonNode t=s.topic(r.topic());m.put("version","1.0.0");m.put("id",Store.wireId(s.config.get("cluster").asString(),t.get("id").asString(),r.offset()));m.put("topic",r.topic());m.put("topic_id",t.get("id").asString());m.put("partition",r.partition());m.put("offset",r.offset());m.put("timestamp",r.timestamp());m.put("timestamp_type",r.timestampType().toString());m.put("key",b64(r.key()));m.put("value",b64(r.value()));m.put("headers",headers);m.put("dependencies",s.config.get("objects"));m.put("category",category(s,r.topic(),r.value(),pending));JsonNode n=JSON.valueToTree(m);s.verifyWire(n,t);return n;
  }
  public static long reconcile(long durable,Long committed,long earliest,long end)throws IOException {
    check(committed==null||committed<=durable,"committed_ahead_of_archive");check(durable>=earliest&&durable<=end,"preservation_gap");return durable;
  }
  static Map<String,Object> status(Store s,KafkaConsumer<byte[],byte[]> c)throws Exception {
    var parts=new HashSet<TopicPartition>();for(String n:TOPICS)parts.add(new TopicPartition(n,0));var starts=c.beginningOffsets(parts);var ends=c.endOffsets(parts);var commits=c.committed(parts);var positions=new TreeMap<String,Object>();
    for(var p:parts){long durable=s.prefix(p.topic()).next();var committed=commits.get(p);var m=new TreeMap<String,Object>();m.put("durable_next",durable);m.put("committed_next",committed==null?null:committed.offset());m.put("earliest",starts.get(p));m.put("end",ends.get(p));m.put("lag",Math.max(0,ends.get(p)-durable));positions.put(p.topic(),m);}
    var result=new TreeMap<String,Object>(s.progress());result.put("partitions",positions);return result;
  }
  static Object consume(Store s,boolean drain)throws Exception {
    check(implementation().equals(s.config.get("implementation_sha256").asString()),"implementation_changed");verifyBroker(s.config);
    for(String sha:Store.strings(s.config.get("objects")))s.object(sha);
    try(var c=new KafkaConsumer<byte[],byte[]>(properties(s.config))) {
      var parts=new HashSet<TopicPartition>();for(String n:TOPICS)parts.add(new TopicPartition(n,0));Map<TopicPartition,Long> target=c.endOffsets(parts);AtomicLong epoch=new AtomicLong();
      c.subscribe(TOPICS,new ConsumerRebalanceListener(){
        @Override public void onPartitionsRevoked(Collection<TopicPartition> ps){epoch.incrementAndGet();}
        @Override public void onPartitionsLost(Collection<TopicPartition> ps){epoch.incrementAndGet();}
        @Override public void onPartitionsAssigned(Collection<TopicPartition> ps){epoch.incrementAndGet();try{var earliest=c.beginningOffsets(ps);var end=c.endOffsets(ps);var committed=c.committed(new HashSet<>(ps));for(var p:ps){var off=committed.get(p);c.seek(p,reconcile(s.prefix(p.topic()).next(),off==null?null:off.offset(),earliest.get(p),end.get(p)));}}catch(IOException e){throw new RuntimeException(e);}}
      });
      long deadline=System.nanoTime()+Duration.ofMinutes(3).toNanos();
      while(true) {
        check(!drain||System.nanoTime()<deadline,"archive_drain_timeout");
        var records=c.poll(Duration.ofMillis(500));long generation=epoch.get();verifyBroker(s.config);
        for(var part:records.partitions()) {
          long first=s.prefix(part.topic()).next();var rs=new ArrayList<JsonNode>();long size=0;
          for(var r:records.records(part)) {
            JsonNode row=wire(s,r,rs);long rowBytes=ndjson(row).length;
            if(!rs.isEmpty()&&(rs.size()>=s.config.at("/limits/segment_rows").asLong()||size+rowBytes>s.config.at("/limits/segment_bytes").asLong())) {s.commitSegment(part.topic(),first,r.offset(),rs);first=r.offset();rs=new ArrayList<>();size=0;}
            rs.add(row);size+=rowBytes;
          }
          if(!rs.isEmpty())s.commitSegment(part.topic(),first,c.position(part),rs);
        }
        // Control batches can advance a broker position without an application record.
        // Retain that observed empty interval explicitly rather than inventing records.
        for(var part:c.assignment())if(records.records(part).isEmpty()) {
          long first=s.prefix(part.topic()).next(),next=c.position(part);
          if(next>first)s.commitSegment(part.topic(),first,next,List.of());
        }
        verifyBroker(s.config);check(generation==epoch.get(),"assignment_changed");
        var commit=new HashMap<TopicPartition,OffsetAndMetadata>();for(var p:c.assignment())commit.put(p,new OffsetAndMetadata(s.prefix(p.topic()).next()));
        if(!commit.isEmpty()){if(records.count()>0)hook().at("before_kafka_commit");try{c.commitSync(commit);}catch(org.apache.kafka.common.KafkaException e){throw new Failure("kafka_commit_failed");}if(records.count()>0)hook().at("after_kafka_commit");}
        Object progress=status(s,c);s.advisory(progress);
        if(drain&&c.assignment().containsAll(parts)){boolean done=true;for(var p:parts)if(s.prefix(p.topic()).next()<target.get(p))done=false;if(done)return progress;}
      }
    }
  }
  static void run(String[] args)throws Exception {
    check(args.length>=2,"usage");String command=args[0];Path root=Path.of(args[1]);Object result;
    if(command.equals("init")){check(args.length==5,"usage");result=initialize(root,args[2],Path.of(args[3]),Path.of(args[4]));}
    else try(var s=new Store(root,!command.equals("inspect")&&!command.equals("wire")&&!command.equals("object"),hook())) {
      switch(command) {
        case "register" -> {check(args.length==3,"usage");register(s,Path.of(args[2]));result=s.progress();}
        case "drain","run" -> result=consume(s,command.equals("drain"));
        case "inspect" -> {if(args.length==3&&args[2].equals("--broker")){verifyBroker(s.config);try(var c=new KafkaConsumer<byte[],byte[]>(properties(s.config))){result=status(s,c);}}else result=s.progress();}
        case "object" -> {check(args.length==4,"usage");byte[] b=s.object(args[2]);Path out=Path.of(args[3]);writeOutput(out,b);result=Map.of("sha256",Json.sha(b),"bytes",b.length);}
        case "wire" -> {check(args.length==5,"usage");long offset=Long.parseLong(args[3]);final JsonNode[] found={null};s.forEachRow(args[2],row->{if(row.get("offset").asLong()==offset)found[0]=row;});check(found[0]!=null,"wire_not_found");writeOutput(Path.of(args[4]),ndjson(found[0]));result=Map.of("id",found[0].get("id"),"category",found[0].get("category"));}
        default -> throw new Failure("usage");
      }
    }
    System.out.println(new String(bytes(Map.of("status","ok","result",result)),java.nio.charset.StandardCharsets.UTF_8));
  }
  static void writeOutput(Path path,byte[] b)throws IOException {Store.safeAncestors(path.toAbsolutePath());check(!Files.exists(path,LinkOption.NOFOLLOW_LINKS),"output_exists");Store.write(path,b);Store.sync(path.toAbsolutePath().getParent());}
  public static void main(String[] args) {
    try{run(args);}catch(Exception e){String category="archive_operation_failed";for(Throwable cause=e;cause!=null;cause=cause.getCause())if(cause instanceof Failure f){category=f.category;break;}System.out.println(new String(bytes(Map.of("status","blocked","category",category,"failure_class",e.getClass().getName())),java.nio.charset.StandardCharsets.UTF_8));System.exit(1);}
  }
}
