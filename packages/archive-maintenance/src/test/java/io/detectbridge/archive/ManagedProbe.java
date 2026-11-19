package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.header.internals.RecordHeaders;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Synthetic executable probe. Excluded from the managed artifact and never a recovery source. */
public final class ManagedProbe {
  static Object fixture(Path input,Path root)throws Exception {
    JsonNode fixture=read(Store.bounded(input,16*MIB),16*MIB).get("legacy");
    check(!Files.exists(root,LinkOption.NOFOLLOW_LINKS),"probe_destination_exists");Files.createDirectory(root);
    JsonNode config=fixture.get("configuration");Store.write(root.resolve("archive.json"),ndjson(config));Store.writeChecksum(root.resolve("archive.json"),ndjson(config));Store.write(root.resolve(".lock"),new byte[0]);Files.createDirectory(root.resolve("objects"));Files.createDirectory(root.resolve("segments"));
    for(JsonNode object:fixture.get("objects")) {
      Path directory=root.resolve("objects").resolve(object.at("/metadata/sha256").asString());Files.createDirectory(directory);
      Store.write(directory.resolve("object.json"),ndjson(object.get("metadata")));Store.writeChecksum(directory.resolve("object.json"),ndjson(object.get("metadata")));Store.write(directory.resolve("bytes.ndjson.gz"),HexFormat.of().parseHex(object.get("gzip_hex").asString()));Store.sync(directory);
    }
    for(JsonNode segment:fixture.get("segments")) {
      Path directory=root.resolve("segments").resolve(segment.at("/metadata/topic_id").asString()).resolve("0").resolve(segment.at("/metadata/first").asString());Files.createDirectories(directory);
      Store.write(directory.resolve("segment.json"),ndjson(segment.get("metadata")));Store.writeChecksum(directory.resolve("segment.json"),ndjson(segment.get("metadata")));Store.write(directory.resolve("records.ndjson.gz"),HexFormat.of().parseHex(segment.get("gzip_hex").asString()));Store.sync(directory);
    }
    ManagedImport.syncTree(root);try(var verified=new Store(root,false)){return Map.of("binding_sha256",verified.binding,"next",verified.prefix(Main.INPUT).next());}
  }
  static Object kafka(String[] args)throws Exception {
    String action=args[1],bootstrap=args[2];
    if(action.equals("publish")) {
      JsonNode rows=read(Store.bounded(Path.of(args[3]),16*MIB),16*MIB);var acknowledgements=new ArrayList<Object>();
      try(var producer=new KafkaProducer<byte[],byte[]>(Broker.producerProperties(bootstrap))) {
        for(JsonNode row:rows) {
          byte[] key=decode(row.get("key")),value=decode(row.get("value"));var headers=new RecordHeaders();for(JsonNode header:row.get("headers"))headers.add(header.get("name").asString(),decode(header.get("value")));
          var record=new ProducerRecord<byte[],byte[]>(row.get("topic").asString(),0,1234567890L,key,value,headers);var sent=producer.send(record).get(35,TimeUnit.SECONDS);
          var ack=new TreeMap<String,Object>();ack.put("topic",sent.topic());ack.put("offset",sent.offset());ack.put("value_sha256",value==null?null:Json.sha(value));acknowledgements.add(ack);
        }
      }
      return acknowledgements;
    }
    try(var admin=Admin.create(Broker.properties(bootstrap))) {
      if(action.equals("init")) {
        var existing=admin.listTopics().names().get(15,TimeUnit.SECONDS);var topics=new ArrayList<NewTopic>();for(String name:Main.TOPICS)if(!existing.contains(name))topics.add(new NewTopic(name,1,(short)1).configs(Broker.TOPIC_CONFIG));if(!topics.isEmpty())admin.createTopics(topics).all().get(20,TimeUnit.SECONDS);return Map.of("created",topics.size());
      }
      check(action.equals("offsets"),"probe_usage");var committed=admin.listConsumerGroupOffsets(args[3]).partitionsToOffsetAndMetadata().get(15,TimeUnit.SECONDS);var offsets=new TreeMap<String,Object>();for(String name:Main.TOPICS){var value=committed.get(new TopicPartition(name,0));offsets.put(name,value==null?null:value.offset());}return offsets;
    }
  }
  static Object lease(String[] args)throws Exception {
    Path marker=Path.of(args[2]),release=Path.of(args[3]);
    try(var reader=new ManagedStore(Path.of(args[1]),false,ManagedMain.implementation())) {
      Store.write(marker,ndjson(Map.of("status","leased","managed_id",reader.managed)));Store.sync(marker.getParent());long deadline=System.nanoTime()+Duration.ofSeconds(45).toNanos();
      while(!Files.exists(release,LinkOption.NOFOLLOW_LINKS)&&System.nanoTime()<deadline)Thread.sleep(50);
      check(Files.isRegularFile(release,LinkOption.NOFOLLOW_LINKS),"probe_release_timeout");return Map.of("released",true);
    }
  }
  static void diagnostic(Path directory,String kind,Throwable error,Map<String,Object> observed)throws Exception {
    var text=new StringWriter();error.printStackTrace(new PrintWriter(text));var record=new TreeMap<String,Object>(observed);
    record.put("kind",kind);record.put("failure_class",error.getClass().getName());record.put("message",Objects.toString(error.getMessage(),""));record.put("stack",text.toString());
    Store.write(directory.resolve(kind+".json"),ndjson(record));Store.sync(directory);
  }
  static Object brokerDrain(String[] args)throws Exception {
    try(var store=new ManagedStore(Path.of(args[1]),true,ManagedMain.implementation())) {
      store.operation(args[2],ManagedMain.hook());new ManagedMutation(store,args[2],ManagedMain.hook()).recover();
      try{return ManagedMain.consume(store,true);}
      catch(Exception failure){diagnostic(Path.of(args[3]),"broker-drain-error",failure,Map.of("injected",false));throw failure;}
    }
  }
  static Object appendWire(String[] args)throws Exception {
    JsonNode row=read(Store.bounded(Path.of(args[2]),ROW),ROW);
    try(var store=new ManagedStore(Path.of(args[1]),true,ManagedMain.implementation())) {
      store.operation(args[3],ManagedMain.hook());String topic=row.get("topic").asString();long first=store.prefix(topic).next();
      check(row.get("offset").asLong()==first,"probe_append_offset");long next=Math.addExact(first,1);
      store.commitSegment(topic,first,next,List.of(row));return Map.of("next",next,"wire_sha256",Json.sha(ndjson(row)));
    }
  }
  static Path faultArchive(Path packet,Path parent)throws Exception {
    Files.createDirectory(parent);Path legacy=parent.resolve("legacy");fixture(packet,legacy);
    Path root=parent.resolve("archive"),catalog=parent.resolve("catalog"),control=parent.resolve("control");Files.createDirectory(catalog);Files.createDirectory(control);
    for(String name:List.of("artifacts","pins","runs"))Files.createDirectory(catalog.resolve(name));
    JsonNode binding=JSON.valueToTree(Map.of("version","1.0.0","destination",catalog.toString(),"limits",Map.of("storage_bytes",512L*MIB,"reserve_bytes",128L*MIB)));
    Store.write(catalog.resolve("catalog.json"),ndjson(binding));Store.writeChecksum(catalog.resolve("catalog.json"),ndjson(binding));Store.write(catalog.resolve(".lock"),new byte[0]);
    ObjectNode registration=JSON.createObjectNode();String managed=UUID.randomUUID().toString();registration.put("version","1.0.0");registration.put("profile","archive-managed/1.0.0");registration.put("managed_id",managed);registration.put("archive_binding_sha256","0".repeat(64));registration.put("implementation_sha256",ManagedMain.implementation());registration.put("group","detectbridge-archive-managed-v1-"+managed);registration.put("destination",root.toString());registration.put("catalog_destination",catalog.toString());registration.put("control_destination",control.toString());
    ObjectNode limits=registration.putObject("limits");limits.put("maintenance_reserve_bytes",64L*MIB);limits.put("control_bytes",32L*MIB);limits.put("metadata_bytes",16L*MIB);limits.put("plan_segments",256);limits.put("scan_rows",65536);limits.put("identity_tokens",262144);limits.put("source_fingerprints",131072);registration.putObject("origin").put("kind","fresh").putNull("source_scope_sha256");
    ManagedMain.cloneArchive(legacy,root,registration,UUID.randomUUID().toString());return root;
  }
  static List<JsonNode> faultRows(JsonNode fixture)throws Exception {
    byte[] opaque=new byte[MIB];new Random(14).nextBytes(opaque);var rows=new ArrayList<JsonNode>();
    for(long offset=6;offset<8;offset++) {
      ObjectNode row=(ObjectNode)fixture.at("/legacy/segments/0/rows/0").deepCopy();row.put("offset",offset);row.put("category","opaque");row.put("value",b64(opaque));
      row.put("id","sha256:"+hash(List.of("detectbridge.archive.wire/1",fixture.at("/legacy/configuration/cluster").asString(),row.get("topic_id").asString(),"0",Long.toString(offset))));rows.add(row);
    }
    // Force the second payload half to need new tmpfs pages after the filler reaches ENOSPC.
    var raw=new ByteArrayOutputStream();for(JsonNode row:rows)raw.write(ndjson(row));check(compress(raw.toByteArray()).length>16*4096,"probe_fault_payload_too_small");return rows;
  }
  static boolean space(IOException error){return Objects.toString(error.getMessage(),"").toLowerCase(Locale.ROOT).contains("no space left");}
  static Object storage(String[] args)throws Exception {
    Path packet=Path.of(args[1]),diagnostics=Path.of(args[2]),fault=Path.of("/fault");Store.safeAncestors(diagnostics);
    var fs=Files.getFileStore(fault);check(fs.type().equals("tmpfs")&&fs.getTotalSpace()==192L*MIB,"probe_fault_filesystem_binding");
    JsonNode input=read(Store.bounded(packet,16*MIB),16*MIB);List<JsonNode> rows=faultRows(input);String inputHash=Json.sha(bytes(rows));var outcomes=new ArrayList<Object>();
    for(String kind:List.of("full","eio")) {
      Path root=faultArchive(packet,fault.resolve(kind));String operation=UUID.randomUUID().toString();Path filler=fault.resolve("owned-filler.bin");IOException[] fillError={null};boolean[] fired={false};long[] fillBytes={0};
      Store.Hook hook=phase->{
        if(kind.equals("full")&&phase.equals("during_payload")) {
          fired[0]=true;byte[] block=new byte[MIB];
          try(var output=Files.newOutputStream(filler,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
            while(fillBytes[0]<=192L*MIB){output.write(block);fillBytes[0]+=block.length;}
          }catch(IOException full){if(!space(full))throw full;fillError[0]=full;}
          check(fillError[0]!=null,"probe_full_filesystem_not_reached");
        }
        if(kind.equals("eio")&&phase.equals("before_metadata_sync")){fired[0]=true;throw new IOException("injected EIO before metadata sync");}
      };
      IOException actual;
      try(var store=new ManagedStore(root,true,ManagedMain.implementation())) {
        store.operation(operation,hook);
        try{store.commitSegment(Main.INPUT,6,8,rows);throw new Failure("probe_required_storage_failure_missing");}
        catch(IOException failed){actual=failed;}
      }
      diagnostic(diagnostics,kind+"-archive-write",actual,Map.of("injected",kind.equals("eio"),"input_sha256",inputHash,"filler_bytes",fillBytes[0]));
      check(fired[0]&&!(actual instanceof Failure),"probe_unrelated_storage_failure");
      check(Arrays.stream(actual.getStackTrace()).anyMatch(frame->frame.getClassName().equals("io.detectbridge.archive.ManagedPending")&&frame.getMethodName().equals("write")),"probe_failure_not_archive_write");
      if(kind.equals("full"))check(space(actual)&&actual!=fillError[0],"probe_archive_enospc_missing");else check(actual.getMessage().equals("injected EIO before metadata sync"),"probe_injected_eio_missing");
      try(var store=new ManagedStore(root,true,ManagedMain.implementation())) {
        check(store.prefix(Main.INPUT).next()==6&&!Files.exists(root.resolve("segments/topic-0/0/6")),"probe_failed_write_published");
        store.operation(operation,p->{});
        if(kind.equals("full")) {
          try{store.commitSegment(Main.INPUT,6,8,rows);throw new Failure("probe_full_admission_not_blocked");}
          catch(Failure blocked){check(blocked.category.equals("disk_reserve"),"probe_wrong_admission_failure");}
          diagnostic(diagnostics,"full-filler",fillError[0],Map.of("injected",false,"filler_bytes",fillBytes[0]));Files.delete(filler);Store.sync(fault);
        }
        store.commitSegment(Main.INPUT,6,8,rows);check(store.prefix(Main.INPUT).next()==8,"probe_retry_head");
        check(Json.sha(bytes(store.readSegment(Main.INPUT,6))).equals(inputHash),"probe_retry_payload");
        JsonNode metadata=Store.metadata(root.resolve("segments/topic-0/0/6/segment.json"),"segment");check(metadata.get("previous").asString().equals(input.at("/legacy/segments/2/metadata_sha256").asString()),"probe_retry_original_anchor");
        check(Arrays.equals(store.object(input.at("/legacy/objects/0/metadata/sha256").asString()),HexFormat.of().parseHex("410d0a0ac3a90a5a")),"probe_retry_original_object");
      }
      outcomes.add(Map.of("case",kind.equals("full")?"actual_tmpfs_archive_payload_enospc_reserve_refusal_and_same_operation_retry":"injected_metadata_sync_eio_and_same_operation_retry","failure_class",actual.getClass().getName(),"before_next",6,"after_next",8,"input_sha256",inputHash));
    }
    return Map.of("cases",outcomes,"filesystem_bytes",192L*MIB,"reserve_bytes",128L*MIB,"physical_disk_loss_qualified",false);
  }
  public static void main(String[] args) {
    try {
      Object result=switch(args[0]){case "fixture" -> fixture(Path.of(args[1]),Path.of(args[2]));case "kafka" -> kafka(args);case "lease" -> lease(args);case "storage-faults" -> storage(args);case "broker-drain" -> brokerDrain(args);case "append-wire" -> appendWire(args);default -> throw new Failure("probe_usage");};
      System.out.println(new String(bytes(Map.of("status","ok","result",result)),java.nio.charset.StandardCharsets.UTF_8));
    } catch(Exception failure) {
      String category=failure instanceof Failure typed?typed.category:"probe_failed";
      System.out.println(new String(bytes(Map.of("status","blocked","category",category,"failure_class",failure.getClass().getName())),java.nio.charset.StandardCharsets.UTF_8));System.exit(1);
    }
  }
}
