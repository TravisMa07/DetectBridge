package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class StoreTest {
  @TempDir Path temp;
  @BeforeEach void canonicalTemp()throws Exception {temp=temp.toRealPath();}
  final byte[] original=HexFormat.of().parseHex("410d0a0ac3a90a5a");
  JsonNode config(byte[] object) {
    String id="00000000-0000-4000-8000-000000000001";var ts=new ArrayList<Object>();int i=0;
    for(String name:Main.TOPICS)ts.add(Map.of("name",name,"id","topic-"+(i++),"partition",0,"start",0));
    return JSON.valueToTree(Map.of("version","1.0.0","archive_id",id,"cluster","cluster-A","bootstrap","kafka:9092","group","detectbridge-archive-v1-"+id,"implementation_sha256","0".repeat(64),"limits",Main.LIMITS,"topics",ts,"objects",List.of(Json.sha(object)),"provenance",List.of(Json.sha(object))));
  }
  Store store()throws Exception {Path root=temp.resolve("archive");Store.create(root,config(original));Store s=new Store(root,true);s.putObject(Json.sha(original),original);return s;}
  JsonNode wire(Store s,String name,long offset,byte[] value)throws Exception {
    var m=new TreeMap<String,Object>();m.put("version","1.0.0");m.put("topic",name);m.put("topic_id",s.topic(name).get("id").asString());m.put("partition",0);m.put("offset",offset);m.put("timestamp",Long.MIN_VALUE);m.put("timestamp_type","NoTimestampType");m.put("id",Store.wireId("cluster-A",s.topic(name).get("id").asString(),offset));m.put("key",null);m.put("value",b64(value));m.put("headers",List.of(Map.of("name","x","value","AA=="),Map.of("name","x","value","AQ==")));m.put("dependencies",s.config.get("objects"));m.put("category","opaque");return JSON.valueToTree(m);
  }
  @Test void independentCanonicalIdentityAndByteRanges()throws Exception {
    JsonNode v=read(Files.readAllBytes(Path.of(System.getProperty("repository.root"),"contracts/archive/v1/fixtures/vectors.json")),MIB);
    assertEquals(v.get("canonical_utf8_hex").asString(),HexFormat.of().formatHex(bytes(v.get("canonical_value"))));assertEquals(v.get("canonical_sha256").asString(),hash(v.get("canonical_value")));
    assertEquals(v.get("wire_id").asString(),Store.wireId("cluster-A","topic-A",9007199254740993L));
    try(Store s=store()){assertArrayEquals(original,s.object(v.get("original_sha256").asString()));for(JsonNode r:v.get("ranges")){int off=r.get(0).asInt(),len=r.get(1).asInt();byte[] expected=Arrays.copyOfRange(original,off,off+len);assertArrayEquals(expected,s.range(Json.sha(original),off,len,Json.sha(expected)));}}
  }
  @Test void exactNullEmptyAndDistinctOffsetsSurviveRestart()throws Exception {
    Path root;try(Store s=store()){root=s.root;List<JsonNode> rows=List.of(wire(s,Main.INPUT,0,null),wire(s,Main.INPUT,1,new byte[0]),wire(s,Main.INPUT,2,original),wire(s,Main.INPUT,3,original));s.commitSegment(Main.INPUT,0,4,rows);assertArrayEquals(bytes(rows),bytes(s.readSegment(Main.INPUT,0)));assertNotEquals(rows.get(2).get("id"),rows.get(3).get("id"));}
    try(Store s=new Store(root,true)){assertEquals(4,s.prefix(Main.INPUT).next());assertEquals(0,s.prefix(Main.TOPICS.get(1)).next());assertFalse((boolean)s.progress().get("historical_ready"));}
  }
  @Test void legitimateEmptyBrokerIntervalsRemainExplicitAndResumable()throws Exception {
    Path root;try(Store s=store()){root=s.root;s.commitSegment(Main.INPUT,0,3,List.of());s.commitSegment(Main.INPUT,3,4,List.of(wire(s,Main.INPUT,3,original)));}
    try(Store s=new Store(root,true)){assertEquals(4,s.prefix(Main.INPUT).next());assertTrue(s.readSegment(Main.INPUT,0).isEmpty());assertEquals(1,s.readSegment(Main.INPUT,3).size());}
  }
  @Test void exactRetryVerifiesWithoutOverwriteButChangedWireFails()throws Exception {
    try(Store s=store()){var row=wire(s,Main.INPUT,0,original);s.commitSegment(Main.INPUT,0,1,List.of(row));long size=s.managedBytes();s.commitSegment(Main.INPUT,0,1,List.of(row));assertEquals(size,s.managedBytes());var changed=(ObjectNode)row.deepCopy();changed.put("value",b64(new byte[]{4}));assertThrows(Failure.class,()->s.commitSegment(Main.INPUT,0,1,List.of(changed)));assertArrayEquals(bytes(List.of(row)),bytes(s.readSegment(Main.INPUT,0)));}
  }
  @Test void everyPublicationInterruptionRecoversCommittedDirectoryOnly()throws Exception {
    int number=0;for(String phase:List.of("during_payload","before_payload_sync","after_payload","during_metadata","before_metadata_sync","after_metadata","before_rename","after_rename","after_directory_sync")) {
      Path root=temp.resolve("fault-"+(number++));Store.create(root,config(original));try(Store s=new Store(root,true)){s.putObject(Json.sha(original),original);}
      try(Store s=new Store(root,true,p->{if(p.equals(phase))throw new Failure("injected_"+phase);})){JsonNode row=wire(s,Main.INPUT,0,original);assertThrows(Failure.class,()->s.commitSegment(Main.INPUT,0,1,List.of(row)));}
      try(Store s=new Store(root,true)){boolean published=phase.equals("after_rename")||phase.equals("after_directory_sync");assertEquals(published?1:0,s.prefix(Main.INPUT).next());s.commitSegment(Main.INPUT,0,1,List.of(wire(s,Main.INPUT,0,original)));assertEquals(1,s.prefix(Main.INPUT).next());}
    }
  }
  @Test void corruptionMissingObjectAndMetadataChainNeverReset()throws Exception {
    Path root;try(Store s=store()){root=s.root;s.commitSegment(Main.INPUT,0,1,List.of(wire(s,Main.INPUT,0,original)));}
    Path payload=root.resolve("segments/topic-0/0/0/records.ndjson.gz");byte[] b=Files.readAllBytes(payload);b[b.length/2]^=1;Files.write(payload,b);assertThrows(Failure.class,()->new Store(root,true));
    Files.write(payload,new byte[]{1});assertThrows(Failure.class,()->new Store(root,false));
  }
  @Test void tailMetadataCorruptionCannotAdvanceDurableCoverage()throws Exception {
    Path root;try(Store s=store()){root=s.root;s.commitSegment(Main.INPUT,0,1,List.of(wire(s,Main.INPUT,0,original)));}
    Path path=root.resolve("segments/topic-0/0/0/segment.json");ObjectNode metadata=(ObjectNode)read(Files.readAllBytes(path),MIB);
    metadata.put("next",2);Files.write(path,ndjson(metadata));
    assertThrows(Failure.class,()->new Store(root,true));
  }
  @Test void gzipRejectsFooterTrailingConcatenationAndInflationBounds()throws Exception {
    byte[] good=compress(original);assertArrayEquals(original,decompress(good,original.length));assertThrows(Failure.class,()->decompress(good,original.length-1));
    byte[] tail=good.clone();tail[tail.length-8]^=1;assertThrows(Failure.class,()->decompress(tail,100));
    assertThrows(Failure.class,()->decompress(Arrays.copyOf(good,good.length-1),100));
    byte[] joined=new byte[2*good.length];System.arraycopy(good,0,joined,0,good.length);System.arraycopy(good,0,joined,good.length,good.length);assertThrows(Failure.class,()->decompress(joined,100));
    assertThrows(Failure.class,()->decompress(Arrays.copyOf(good,good.length+1),100));
  }
  @Test void schemaAndFramingRejectInvalidIntegersUnicodeAndUnknownFields()throws Exception {
    assertThrows(Failure.class,()->read("{\"a\":1,\"a\":2}".getBytes(),100));assertThrows(Failure.class,()->read("{}{}".getBytes(),100));assertThrows(Failure.class,()->read(new byte[]{(byte)255},100));assertThrows(Failure.class,()->read("\"\\ud800\"".getBytes(),100));
    try(Store s=store()){var n=(ObjectNode)wire(s,Main.INPUT,0,original);n.put("offset",1.0);assertThrows(Failure.class,()->require("wire",n));n.put("offset",0);n.put("extra",true);assertThrows(Failure.class,()->require("wire",n));}
    assertThrows(Failure.class,()->rows("{}".getBytes(),"chunk",1));assertThrows(Failure.class,()->rows("\n".getBytes(),"chunk",1));
  }
  @Test void exactChunkBoundaryEmptyObjectAndOversizeHashReject()throws Exception {
    byte[] full=new byte[MIB+1];Arrays.fill(full,(byte)42);Path root=temp.resolve("large");Store.create(root,config(full));try(Store s=new Store(root,true)){s.putObject(Json.sha(full),full);assertArrayEquals(full,s.object(Json.sha(full)));assertThrows(Failure.class,()->s.putObject(Json.sha(full),new byte[]{1}));assertThrows(Failure.class,()->s.range(Json.sha(full),full.length,1,Json.sha(new byte[]{1})));}
    root=temp.resolve("empty");Store.create(root,config(new byte[0]));try(Store s=new Store(root,true)){s.putObject(Json.sha(new byte[0]),new byte[0]);assertArrayEquals(new byte[0],s.object(Json.sha(new byte[0])));}
  }
  @Test void writerLockSymlinkUnknownFilesAndUnsafeTopicIdsReject()throws Exception {
    try(Store s=store()){assertThrows(Failure.class,()->new Store(s.root,true));Files.writeString(s.root.resolve("unknown"),"x");assertThrows(Failure.class,()->new Store(s.root,false));}
    var c=(ObjectNode)config(original);((ObjectNode)c.get("topics").get(0)).put("id","../../escape");assertThrows(Failure.class,()->Store.validateConfig(c));
    Path root=temp.resolve("linkroot");Files.createSymbolicLink(root,temp.resolve("archive"));assertThrows(Failure.class,()->new Store(root,false));
  }
  @Test void finiteBudgetAndDiskReserveAndSegmentEdges()throws Exception {
    try(Store s=store()){assertThrows(Failure.class,()->s.reserve(2147483648L));var limits=(ObjectNode)s.config.get("limits");limits.put("segment_rows",1);assertThrows(Failure.class,()->s.commitSegment(Main.INPUT,0,2,List.of(wire(s,Main.INPUT,0,original),wire(s,Main.INPUT,1,original))));}
  }
  @Test void offsetsNeverAdvanceAheadOrSkipMissingHistory()throws Exception {
    assertEquals(5,Main.reconcile(5,3L,0,6));assertEquals(5,Main.reconcile(5,null,0,6));assertThrows(Failure.class,()->Main.reconcile(5,6L,0,8));assertThrows(Failure.class,()->Main.reconcile(5,5L,6,9));assertThrows(Failure.class,()->Main.reconcile(5,5L,0,4));
  }
  @Test void unknownPartialContentsAreRetainedAndRangeOverflowNeverWraps()throws Exception {
    Path root;try(Store s=store()) {
      root=s.root;
      String value="{\"kind\":\"record\",\"raw\":{\"record_id\":\"r\",\"evidence\":{\"sha256\":\""+Json.sha(original)+"\",\"reference\":{\"object_sha256\":\""+Json.sha(original)+"\",\"byte_range\":{\"offset\":18446744073709551616,\"length\":8}}}},\"context\":{\"run_id\":\"r\"}}";
      assertThrows(Failure.class,()->Main.category(s,Main.INPUT,value.getBytes(java.nio.charset.StandardCharsets.UTF_8),List.of()));
    }
    Path partial=Files.createDirectory(root.resolve(".partial-unknown"));Path unknown=partial.resolve("retained-evidence");Files.write(unknown,original);
    assertThrows(Failure.class,()->new Store(root,true));assertArrayEquals(original,Files.readAllBytes(unknown));
  }
  @Test void sourceReferenceBacklogAndSemanticConflictPreserveBytes()throws Exception {
    try(Store s=store()){
      var raw=Map.of("record_id","record-A","evidence",Map.of("sha256",Json.sha(original),"reference",Map.of("object_sha256",Json.sha(original),"byte_range",Map.of("offset",0,"length",original.length))));
      byte[] value=bytes(Map.of("kind","record","raw",raw,"context",Map.of("run_id","run-A","receipt","first")));
      assertEquals("source",Main.category(s,Main.INPUT,value,List.of()));JsonNode row=wire(s,Main.INPUT,0,value);s.commitSegment(Main.INPUT,0,1,List.of(row));
      byte[] retry=bytes(Map.of("kind","record","raw",raw,"context",Map.of("run_id","run-A","receipt","second")));assertEquals("source",Main.category(s,Main.INPUT,retry,List.of()));
      byte[] conflict=bytes(Map.of("kind","record","raw",raw,"context",Map.of("run_id","run-A","host","changed")));assertEquals("semantic_conflict",Main.category(s,Main.INPUT,conflict,List.of()));
      Files.delete(s.root.resolve("objects").resolve(Json.sha(original)).resolve("bytes.ndjson.gz"));assertThrows(Failure.class,()->Main.category(s,Main.INPUT,value,List.of()));
    }
  }
}
