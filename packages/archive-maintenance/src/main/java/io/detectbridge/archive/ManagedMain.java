package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Opt-in managed archive CLI; unchanged v1 encodings and pinned processing stay separate. */
public final class ManagedMain {
  static String implementation()throws Exception{return Main.implementation();}
  static Store.Hook hook(){return Main.hook();}
  static JsonNode parsed(byte[] value){return Main.parsed(value);}
  static String sourceIdentity(JsonNode value){return Main.sourceIdentity(value);}
  static String fingerprint(JsonNode value){return Main.fingerprint(value);}
  static void verifyBroker(JsonNode config)throws Exception {Main.verifyBroker(config);}
  static Properties properties(ManagedStore store){Properties properties=Main.properties(store.config);properties.put("group.id",store.registration.get("group").asString());return properties;}
  static String category(ManagedStore s,String topic,byte[] value,List<JsonNode> pending)throws IOException {
    if(!topic.equals(Main.INPUT))return "derived";
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
    String retiredIdentity=hash(identity);
    for(String prior:s.fingerprints.getOrDefault(retiredIdentity,Set.of()))if(!prior.equals(content))conflict[0]=true;
    s.forEachRow(Main.INPUT,compare);for(JsonNode row:pending)compare.accept(row);return conflict[0]?"semantic_conflict":"source";
  }
  static JsonNode wire(ManagedStore s,ConsumerRecord<byte[],byte[]> r,List<JsonNode> pending)throws IOException {
    check(r.value()==null||r.value().length<=2*MIB,"wire_value_limit");var headers=new ArrayList<Object>();for(var h:r.headers()){check(headers.size()<128,"header_limit");var m=new TreeMap<String,Object>();m.put("name",h.key());m.put("value",b64(h.value()));headers.add(m);}
    var m=new TreeMap<String,Object>();JsonNode t=s.topic(r.topic());m.put("version","1.0.0");m.put("id",Store.wireId(s.config.get("cluster").asString(),t.get("id").asString(),r.offset()));m.put("topic",r.topic());m.put("topic_id",t.get("id").asString());m.put("partition",r.partition());m.put("offset",r.offset());m.put("timestamp",r.timestamp());m.put("timestamp_type",r.timestampType().toString());m.put("key",b64(r.key()));m.put("value",b64(r.value()));m.put("headers",headers);m.put("dependencies",s.config.get("objects"));m.put("category",category(s,r.topic(),r.value(),pending));JsonNode n=JSON.valueToTree(m);s.verifyWire(n,t);return n;
  }
  public static long reconcile(long durable,Long committed,long earliest,long end)throws IOException {
    check(committed==null||committed<=durable,"committed_ahead_of_archive");check(durable>=earliest&&durable<=end,"preservation_gap");return durable;
  }
  static Map<String,Object> status(ManagedStore s,Consumer<byte[],byte[]> c)throws Exception {
    var parts=new HashSet<TopicPartition>();for(String n:Main.TOPICS)parts.add(new TopicPartition(n,0));var starts=c.beginningOffsets(parts);var ends=c.endOffsets(parts);var commits=c.committed(parts);var positions=new TreeMap<String,Object>();
    for(var p:parts){long durable=s.prefix(p.topic()).next();var committed=commits.get(p);var m=new TreeMap<String,Object>();m.put("retained_floor",s.floors.get(p.topic()).next());m.put("durable_next",durable);m.put("committed_next",committed==null?null:committed.offset());m.put("earliest",starts.get(p));m.put("end",ends.get(p));m.put("lag",Math.max(0,ends.get(p)-durable));positions.put(p.topic(),m);}
    var result=new TreeMap<String,Object>(s.progress());result.put("partitions",positions);return result;
  }
  static Object consume(ManagedStore s,boolean drain)throws Exception {
    check(implementation().equals(s.registration.get("implementation_sha256").asString()),"implementation_changed");verifyBroker(s.config);
    for(String sha:Store.strings(s.config.get("objects")))s.object(sha);
    try(var c=new KafkaConsumer<byte[],byte[]>(properties(s))) {
      var parts=new HashSet<TopicPartition>();for(String n:Main.TOPICS)parts.add(new TopicPartition(n,0));Map<TopicPartition,Long> target=c.endOffsets(parts);AtomicLong epoch=new AtomicLong();
      c.subscribe(Main.TOPICS,new ConsumerRebalanceListener(){
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
  static void enable(Path stage,Path destination,JsonNode supplied,String kind,String sourceScope)throws Exception {
    ObjectNode registration=((ObjectNode)supplied).deepCopy();JsonNode config=Store.metadata(stage.resolve("archive.json"),"configuration");
    registration.put("archive_binding_sha256",hash(config));registration.put("implementation_sha256",implementation());registration.put("group","detectbridge-archive-managed-v1-"+registration.get("managed_id").asString());
    check(registration.get("destination").asString().equals(destination.toString()),"managed_destination");
    ObjectNode origin=registration.putObject("origin");origin.put("kind",kind);if(sourceScope==null)origin.putNull("source_scope_sha256");else origin.put("source_scope_sha256",sourceScope);
    ManagedFormat.require("registration",registration);Path maintenance=stage.resolve("maintenance");Files.createDirectory(maintenance);Files.createDirectory(maintenance.resolve("holds"));Files.createDirectory(maintenance.resolve("retirements"));Files.createDirectory(stage.resolve("imports"));
    ManagedFormat.metadata(maintenance.resolve("registration.json"),"registration",registration);
    ObjectNode holds=JSON.createObjectNode();holds.put("version","1.0.0");holds.set("managed_id",registration.get("managed_id"));holds.put("revision",0);holds.putNull("previous_sha256");holds.put("reason","explicit managed initialization");holds.putArray("holds");
    Path initial=maintenance.resolve("holds/00000000000000000000");Files.createDirectory(initial);ManagedFormat.metadata(initial.resolve("holds.json"),"holds",holds);
    Store.write(maintenance.resolve("holds/head.json"),ndjson(ManagedFormat.head("holds",registration.get("managed_id").asString(),0,hash(holds))));Store.write(maintenance.resolve("retirements/head.json"),ndjson(ManagedFormat.head("retirements",registration.get("managed_id").asString(),0,null)));
    ManagedImport.syncTree(stage);try(var verified=new ManagedStore(stage,false,implementation())){check(verified.managedBytes()<=config.at("/limits/archive_bytes").asLong()-ManagedFormat.HEADROOM,"managed_admission_budget");}
  }
  static Path destination(Path value)throws IOException {Path root=value.toAbsolutePath().normalize();Store.safeAncestors(root);check(!Files.exists(root,LinkOption.NOFOLLOW_LINKS)&&Files.isDirectory(root.getParent(),LinkOption.NOFOLLOW_LINKS),"managed_destination_exists");return root;}
  static Map<String,Object> cloneArchive(Path source,Path target,JsonNode registration,String operation)throws Exception {
    return ManagedInitialization.cloneLegacy(source,target,registration,operation);
  }
  static Map<String,Object> initialize(Path target,String bootstrap,Path request,Path registry,JsonNode registration,String operation)throws Exception {
    return ManagedInitialization.fresh(target,bootstrap,request,registry,registration,operation);
  }
  static void run(String[] args)throws Exception {
    check(args.length>=2,"usage");String command=args[0];Path root=Path.of(args[1]);Object result;
    if(command.equals("init")){check(args.length==7,"usage");result=initialize(root,args[2],Path.of(args[3]),Path.of(args[4]),read(Store.bounded(Path.of(args[5]),MIB),MIB),args[6]);}
    else if(command.equals("clone")){check(args.length==5,"usage");result=cloneArchive(Path.of(args[2]),root,read(Store.bounded(Path.of(args[3]),MIB),MIB),args[4]);}
    else try(var store=new ManagedStore(root,!Set.of("inspect","object","wire","plan","plan-import","export-import").contains(command),implementation())) {
      check(store.root.toString().equals(store.registration.get("destination").asString()),"managed_destination");
      switch(command) {
        case "inspect" -> {check(args.length==2||args.length==3&&args[2].equals("--broker"),"usage");if(args.length==3){verifyBroker(store.config);try(var consumer=new KafkaConsumer<byte[],byte[]>(properties(store))){result=status(store,consumer);}}else result=store.progress();}
        case "object" -> {check(args.length==4,"usage");byte[] bytes=store.object(args[2]);Main.writeOutput(Path.of(args[3]),bytes);result=Map.of("sha256",Json.sha(bytes),"bytes",bytes.length);}
        case "wire" -> {check(args.length==5,"usage");long offset=Long.parseLong(args[3]);check(offset>=store.floors.get(args[2]).next(),"archive_retired");final JsonNode[] found={null};store.forEachRow(args[2],row->{if(row.get("offset").asLong()==offset)found[0]=row;});check(found[0]!=null,"wire_not_found");Main.writeOutput(Path.of(args[4]),ndjson(found[0]));result=Map.of("id",found[0].get("id"),"category",found[0].get("category"));}
        case "plan" -> {check(args.length==5,"usage");JsonNode plan=ManagedPlanner.plan(store,read(Store.bounded(Path.of(args[2]),16*MIB),16*MIB),read(Store.bounded(Path.of(args[3]),16*MIB),16*MIB));Main.writeOutput(Path.of(args[4]),ndjson(plan));result=Map.of("plan_sha256",hash(plan));}
        case "plan-import" -> {check(args.length==5,"usage");JsonNode plan=ManagedImport.retirementPlan(store,read(Store.bounded(Path.of(args[2]),16*MIB),16*MIB),read(Store.bounded(Path.of(args[3]),16*MIB),16*MIB));Main.writeOutput(Path.of(args[4]),ndjson(plan));result=Map.of("plan_sha256",hash(plan));}
        case "retire" -> {check(args.length==5,"usage");JsonNode plan=read(Store.bounded(Path.of(args[2]),16*MIB),16*MIB);result=new ManagedMutation(store,args[4],hook()).retire(plan,read(Store.bounded(Path.of(args[3]),16*MIB),16*MIB));}
        case "holds" -> {check(args.length==4,"usage");JsonNode next=read(Store.bounded(Path.of(args[2]),16*MIB),16*MIB);new ManagedMutation(store,args[3],hook()).holds(next);result=Map.of("revision",store.holds.get("revision"));}
        case "recover" -> {check(args.length==3,"usage");new ManagedMutation(store,args[2],hook()).recover();result=store.progress();}
        case "drain","run" -> {check(args.length==3,"usage");store.operation(args[2],hook());new ManagedMutation(store,args[2],hook()).recover();result=consume(store,command.equals("drain"));}
        case "import" -> {check(args.length==7,"usage");result=ManagedImport.importClosure(store,read(Store.bounded(Path.of(args[2]),16*MIB),16*MIB),Path.of(args[3]),Path.of(args[4]),Path.of(args[5]),UUID.fromString(args[6]),hook());}
        case "export-import" -> {check(args.length==6,"usage");result=ManagedImport.exportClosure(store,args[2],Path.of(args[3]),Path.of(args[4]),Path.of(args[5]));}
        default -> throw new Failure("usage");
      }
    }
    System.out.println(new String(bytes(Map.of("status","ok","result",result)),java.nio.charset.StandardCharsets.UTF_8));
  }
  public static void main(String[] args) {
    try{run(args);}catch(Exception failure){String category="managed_operation_failed";for(Throwable cause=failure;cause!=null;cause=cause.getCause())if(cause instanceof Failure typed){category=typed.category;break;}System.out.println(new String(bytes(Map.of("status","blocked","category",category,"failure_class",failure.getClass().getName())),java.nio.charset.StandardCharsets.UTF_8));System.exit(1);}
  }
}
