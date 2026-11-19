package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

class ManagedStoreTest {
  @TempDir Path temporary;
  static final String MANAGED="00000000-0000-4000-8000-000000000051",IMPLEMENTATION="a".repeat(64);
  JsonNode fixture()throws Exception {return JSON.readTree(Files.readAllBytes(Path.of(System.getProperty("repository.root"),"contracts/archive-maintenance/v1/fixtures/expectations.json")));}
  Path legacy()throws Exception {
    Path root=temporary.toRealPath().resolve("archive");Files.createDirectory(root);JsonNode f=fixture().get("legacy");
    Store.write(root.resolve("archive.json"),ndjson(f.get("configuration")));Store.writeChecksum(root.resolve("archive.json"),ndjson(f.get("configuration")));Store.write(root.resolve(".lock"),new byte[0]);
    Files.createDirectory(root.resolve("objects"));Files.createDirectory(root.resolve("segments"));
    for(JsonNode object:f.get("objects")) {
      Path directory=root.resolve("objects").resolve(object.at("/metadata/sha256").asString());Files.createDirectory(directory);
      Store.write(directory.resolve("object.json"),ndjson(object.get("metadata")));Store.writeChecksum(directory.resolve("object.json"),ndjson(object.get("metadata")));Store.write(directory.resolve("bytes.ndjson.gz"),HexFormat.of().parseHex(object.get("gzip_hex").asString()));
    }
    for(JsonNode segment:f.get("segments")) {
      Path directory=root.resolve("segments/topic-0/0").resolve(segment.at("/metadata/first").asString());Files.createDirectories(directory);
      Store.write(directory.resolve("segment.json"),ndjson(segment.get("metadata")));Store.writeChecksum(directory.resolve("segment.json"),ndjson(segment.get("metadata")));Store.write(directory.resolve("records.ndjson.gz"),HexFormat.of().parseHex(segment.get("gzip_hex").asString()));
    }
    return root;
  }
  JsonNode enable(Path root)throws Exception {
    Path maintenance=root.resolve("maintenance");Files.createDirectory(maintenance);Files.createDirectory(maintenance.resolve("holds"));Files.createDirectory(maintenance.resolve("retirements"));Files.createDirectory(root.resolve("imports"));
    ObjectNode r=JSON.createObjectNode();r.put("version","1.0.0");r.put("profile","archive-managed/1.0.0");r.put("managed_id",MANAGED);r.put("archive_binding_sha256",hash(fixture().at("/legacy/configuration")));r.put("implementation_sha256",IMPLEMENTATION);r.put("destination",root.toString());r.put("catalog_destination",temporary.toRealPath().resolve("catalog").toString());r.put("control_destination",temporary.toRealPath().resolve("control").toString());r.put("group","detectbridge-archive-managed-v1-"+MANAGED);
    ObjectNode limits=r.putObject("limits");limits.put("maintenance_reserve_bytes",64L*MIB);limits.put("control_bytes",32L*MIB);limits.put("metadata_bytes",16*MIB);limits.put("plan_segments",256);limits.put("scan_rows",65536);limits.put("identity_tokens",262144);limits.put("source_fingerprints",131072);r.putObject("origin").put("kind","clone").put("source_scope_sha256",hash("original legacy fixture source"));
    ManagedFormat.metadata(maintenance.resolve("registration.json"),"registration",r);
    ObjectNode holds=JSON.createObjectNode();holds.put("version","1.0.0");holds.put("managed_id",MANAGED);holds.put("revision",0);holds.putNull("previous_sha256");holds.put("reason","initial synthetic fixture");holds.putArray("holds");Path h=maintenance.resolve("holds/00000000000000000000");Files.createDirectory(h);ManagedFormat.metadata(h.resolve("holds.json"),"holds",holds);
    Store.write(maintenance.resolve("holds/head.json"),ndjson(ManagedFormat.head("holds",MANAGED,0,hash(holds))));Store.write(maintenance.resolve("retirements/head.json"),ndjson(ManagedFormat.head("retirements",MANAGED,0,null)));return holds;
  }
  void retiredPrefix(Path root,JsonNode holds)throws Exception {
    JsonNode f=fixture();ObjectNode plan=JSON.createObjectNode();plan.put("version","1.0.0");plan.put("managed_id",MANAGED);plan.put("archive_binding_sha256",hash(f.at("/legacy/configuration")));plan.put("operation_id","00000000-0000-4000-8000-000000000052");plan.put("kind","segments");plan.put("cutoff_ms",100);plan.put("reason","retire original first four fixture rows");plan.putNull("previous_retirement_sha256");plan.put("holds_sha256",hash(holds));plan.put("catalog_sha256","b".repeat(64));
    ArrayNode observed=plan.putArray("observed");int index=0;
    for(JsonNode t:f.at("/legacy/configuration/topics")) {
      ObjectNode value=observed.addObject();value.set("topic",t.get("name"));value.put("floor",0);value.putNull("floor_sha256");value.put("next",index==0?6:0);
      if(index++==0)value.put("head_sha256",f.at("/legacy/segments/2/metadata_sha256").asString());else value.putNull("head_sha256");
    }
    String topic=f.at("/legacy/configuration/topics/0/name").asString();plan.putArray("targets").addObject().put("topic",topic).put("next",4);plan.putArray("imports");ArrayNode candidates=plan.putArray("candidates");
    for(int i=0;i<2;i++) {
      JsonNode source=f.at("/legacy/segments").get(i);ObjectNode candidate=candidates.addObject();candidate.put("topic",topic);candidate.set("segment",source.get("metadata"));candidate.set("segment_sha256",source.get("metadata_sha256"));candidate.put("unknown_graph",false);candidate.putArray("fingerprints");var identities=new TreeSet<String>();
      // Build the input checkpoint from the literal fixture, never the new linker/planner.
      for(JsonNode wire:source.get("rows")) {
        JsonNode value=JSON.readTree(Base64.getDecoder().decode(wire.get("value").asString()));
        for(String field:List.of("run_id","control_id"))identities.add(hash(List.of("detectbridge.archive.link/1",value.get(field).asString())));
      }
      ArrayNode ids=candidate.putArray("identities");identities.forEach(ids::add);
    }
    ObjectNode record=JSON.createObjectNode();record.put("version","1.0.0");record.put("managed_id",MANAGED);record.put("sequence",1);record.put("id","sha256:"+hash(List.of("detectbridge.archive.retirement/1",MANAGED,plan.get("operation_id").asString(),hash(plan))));record.put("plan_sha256",hash(plan));record.putNull("previous_sha256");
    Path directory=root.resolve("maintenance/retirements/00000000000000000001");Files.createDirectory(directory);ManagedFormat.metadata(directory.resolve("plan.json"),"plan",plan);ManagedFormat.metadata(directory.resolve("retirement.json"),"retirement",record);
    Path head=directory.getParent().resolve("head.json");Files.delete(head);Store.write(head,ndjson(ManagedFormat.head("retirements",MANAGED,1,hash(record))));
    for(int first:List.of(0,2))Store.deletePartial(root.resolve("segments/topic-0/0").resolve(Integer.toString(first)));
  }
  @Test void optInReaderKeepsLegacyBytesAndRejectsAConcurrentWriter()throws Exception {
    Path root=legacy();String topic=fixture().at("/legacy/configuration/topics/0/name").asString();
    try(var original=new Store(root,false)){assertEquals(6,original.prefix(topic).next());}
    enable(root);assertThrows(Failure.class,()->new Store(root,false));
    try(var reader=new ManagedStore(root,false,IMPLEMENTATION)) {
      assertEquals(6,reader.prefix(topic).next());assertEquals(0,reader.floors.get(topic).next());
      assertEquals(2,reader.readSegment(topic,4).size());
      assertThrows(Failure.class,()->new ManagedStore(root,true,IMPLEMENTATION));
      assertArrayEquals(HexFormat.of().parseHex("410d0a0ac3a90a5a"),reader.object("7fd00bc5aff71e505699ae16069b5578c19eb18b34d7f5542bd56d120404e572"));
    }
  }
  @Test void committedAnchorPreservesRetainedFloorAndHead()throws Exception {
    Path root=legacy();JsonNode holds=enable(root);retiredPrefix(root,holds);String topic=fixture().at("/legacy/configuration/topics/0/name").asString();
    try(var reader=new ManagedStore(root,false,IMPLEMENTATION)) {
      assertEquals(4,reader.floors.get(topic).next());assertEquals(6,reader.prefix(topic).next());
      assertEquals(fixture().at("/retirement_expected/previous_sha256").asString(),reader.floors.get(topic).previous());
      assertEquals(2,reader.readSegment(topic,4).size());Failure retired=assertThrows(Failure.class,()->reader.readSegment(topic,2));assertEquals("archive_retired",retired.category);
    }
  }
  void replace(Path path,String kind,JsonNode value)throws Exception {
    Files.delete(path);Files.delete(Store.checksumPath(path));ManagedFormat.metadata(path,kind,value);
  }
  void replacePlan(Path root,ObjectNode plan)throws Exception {
    Path entry=root.resolve("maintenance/retirements/00000000000000000001");replace(entry.resolve("plan.json"),"plan",plan);
    ObjectNode record=(ObjectNode)ManagedFormat.metadata(entry.resolve("retirement.json"),"retirement");record.put("plan_sha256",hash(plan));record.put("id","sha256:"+hash(List.of("detectbridge.archive.retirement/1",MANAGED,plan.get("operation_id").asString(),hash(plan))));replace(entry.resolve("retirement.json"),"retirement",record);
    Path head=entry.getParent().resolve("head.json");Files.delete(head);Store.write(head,ndjson(ManagedFormat.head("retirements",MANAGED,1,hash(record))));
  }
  @Test void committedLastRecordCannotDisappearBehindItsHead()throws Exception {
    Path root=legacy();retiredPrefix(root,enable(root));Store.deletePartial(root.resolve("maintenance/retirements/00000000000000000001"));
    Failure failure=assertThrows(Failure.class,()->new ManagedStore(root,false,IMPLEMENTATION));assertEquals("managed_retirement_head_missing",failure.category);
  }
  @Test void readerRecoversVisibleFloorFromAValidRecordWithoutChangingStaleHead()throws Exception {
    Path root=legacy();retiredPrefix(root,enable(root));Path head=root.resolve("maintenance/retirements/head.json");Files.delete(head);byte[] stale=ndjson(ManagedFormat.head("retirements",MANAGED,0,null));Store.write(head,stale);
    try(var reader=new ManagedStore(root,false,IMPLEMENTATION)){assertTrue(reader.retirementHeadStale);assertEquals(4,reader.floors.get(Main.INPUT).next());}
    assertArrayEquals(stale,Files.readAllBytes(head));
  }
  @Test void compensatedAnchorCorruptionStillFails()throws Exception {
    Path root=legacy();retiredPrefix(root,enable(root));ObjectNode plan=(ObjectNode)ManagedFormat.metadata(root.resolve("maintenance/retirements/00000000000000000001/plan.json"),"plan");
    ObjectNode meta=(ObjectNode)plan.at("/candidates/0/segment");meta.put("previous","c".repeat(64));((ObjectNode)plan.at("/candidates/0")).put("segment_sha256",hash(meta));replacePlan(root,plan);
    Failure failure=assertThrows(Failure.class,()->new ManagedStore(root,false,IMPLEMENTATION));assertEquals("managed_anchor_chain",failure.category);
  }
  @Test void observedHeadMustBeAnActualOriginalBoundary()throws Exception {
    Path root=legacy();retiredPrefix(root,enable(root));ObjectNode plan=(ObjectNode)ManagedFormat.metadata(root.resolve("maintenance/retirements/00000000000000000001/plan.json"),"plan");
    ((ObjectNode)plan.at("/observed/0")).put("next",4);replacePlan(root,plan);
    assertThrows(Failure.class,()->new ManagedStore(root,false,IMPLEMENTATION));
  }
  @Test void interruptedGarbageIsReadOnlyAndForeignFilesAreNotOwned()throws Exception {
    Path root=legacy();retiredPrefix(root,enable(root));Path garbage=root.resolve("segments/topic-0/0/0");Files.createDirectory(garbage);byte[] original=ndjson(fixture().at("/legacy/segments/0/metadata"));Store.write(garbage.resolve("segment.json"),original);
    try(var reader=new ManagedStore(root,false,IMPLEMENTATION)){assertEquals(4,reader.floors.get(Main.INPUT).next());}
    assertArrayEquals(original,Files.readAllBytes(garbage.resolve("segment.json")));Store.write(garbage.resolve("foreign-evidence.txt"),new byte[]{1});
    Failure failure=assertThrows(Failure.class,()->new ManagedStore(root,false,IMPLEMENTATION));assertEquals("unsafe_retired_segment",failure.category);assertTrue(Files.exists(garbage.resolve("foreign-evidence.txt")));
  }

}
