package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

class ManagedGraphTest {
  @TempDir Path temporary;
  ObjectNode receipt(){ObjectNode doc=JSON.createObjectNode();doc.put("version","1.0.0").put("id","sha256:"+"b".repeat(64)).put("kind","input_receipt").put("action","record");doc.putObject("input").put("cluster_id","cluster").put("topic_id","topic").put("topic",Main.INPUT).put("partition",0).put("offset",9007199254740993L).put("value_sha256","c".repeat(64));return doc;}
  JsonNode wire(JsonNode doc,String topic){ObjectNode row=JSON.createObjectNode();row.put("id","sha256:"+"d".repeat(64)).put("topic",topic).put("category","derived").put("value",b64(bytes(doc)));return row;}
  ObjectNode tagged()throws Exception {
    ObjectNode event=(ObjectNode)JSON.readTree(Files.readAllBytes(Path.of(System.getProperty("repository.root"),"packages/linux-adapters/contracts/openssh-authentication-p12a.contract-example.event.json")));
    ObjectNode doc=JSON.createObjectNode();doc.put("version","1.1.0").put("processing_id","sha256:"+"a".repeat(64));doc.set("event",event);doc.putNull("manifest");doc.putArray("matches");doc.putArray("tags").add("coverage:unmatched");ObjectNode counts=doc.putObject("counts");for(String name:List.of("matched","unmatched","inapplicable","configuration_blocked","quality_skipped","evaluation_error"))counts.put(name,name.equals("unmatched")?1:0);
    ObjectNode attribution=doc.putObject("attribution");attribution.put("pipeline","p13-runtime/1.0.0").put("bundle_sha256","b".repeat(64));ObjectNode source=(ObjectNode)event.at("/detectbridge/source_contract").deepCopy();source.putNull("sha256");attribution.set("source_contract",source);attribution.putNull("mapping_profile");attribution.set("processing",event.at("/detectbridge/processing"));attribution.put("compiler","detectbridge/2.0.0").put("evaluator","detectbridge-java/2.0.0").put("mapping_version","source-mappings/1.0.0").put("selector","source-index/1.0.0").put("mapping_sha256","c".repeat(64));attribution.putObject("enrichment").put("id","coverage-and-rule-metadata").put("version","1.0.0").put("sha256","d".repeat(64));attribution.putArray("external_inputs");attribution.set("source",event.at("/detectbridge/source"));attribution.putNull("context_sha256");return doc;
  }
  @Test void declaredObservationalFieldsAreDataButArbitraryExtensionsAreUnknown()throws Exception {
    ObjectNode tagged=tagged();assertTrue(ManagedGraph.known("detectbridge.tagged-events.v1",tagged));
    ObjectNode event=(ObjectNode)tagged.get("event");event.putObject("source_fields").putObject("references").put("record_id","observational-data-only");ManagedPlanner.Graph graph=ManagedPlanner.graph(wire(tagged,"detectbridge.tagged-events.v1"));assertFalse(graph.unknown);assertFalse(graph.identities.contains(ManagedPlanner.token("observational-data-only")));
    ((ObjectNode)event.get("detectbridge")).putObject("extensions").putObject("future.context").putObject("references").put("manifest","unrecognized-reference");assertFalse(ManagedGraph.known("detectbridge.tagged-events.v1",tagged));assertTrue(ManagedPlanner.graph(wire(tagged,"detectbridge.tagged-events.v1")).unknown);
  }
  @Test void exactReceiptAndVersionedControlsAreKnownButOpenWindowsContextsAreNot()throws Exception {
    String topic="detectbridge.integration.receipts.v1";ObjectNode receipt=receipt();assertTrue(ManagedGraph.known(topic,receipt));
    ManagedPlanner.Graph graph=ManagedPlanner.graph(wire(receipt,topic));assertFalse(graph.unknown);assertTrue(graph.identities.contains(ManagedPlanner.token(Store.wireId("cluster","topic",9007199254740993L))));
    ObjectNode control=JSON.createObjectNode();control.put("version","1.0.0").put("kind","run_end").put("run_id","00000000-0000-4000-8000-000000000101").put("control_id","00000000-0000-4000-8000-000000000201").putArray("provenance").add("original synthetic fixture, Apache-2.0");assertTrue(ManagedGraph.known(Main.INPUT,control));control.put("version","99.0.0");assertFalse(ManagedGraph.known(Main.INPUT,control));
    var input=JSON.createObjectNode();input.put("version","1.0.0").put("kind","windows_record");input.set("raw",JSON.readTree(Files.readAllBytes(Path.of(System.getProperty("repository.root"),"contracts/v1/examples/windows-security-4688.raw.json"))));input.putObject("context").put("run_id","00000000-0000-4000-8000-000000000101");assertFalse(ManagedGraph.known(Main.INPUT,input));
  }
  @Test void recognitionRejectsNonintegralAndOutOfRangeCountersWithoutThrowing()throws Exception {
    ObjectNode doc=receipt(),input=(ObjectNode)doc.get("input");String topic="detectbridge.integration.receipts.v1";
    input.put("offset",Long.MAX_VALUE);assertTrue(ManagedGraph.known(topic,doc));input.put("offset",4.0);assertFalse(ManagedGraph.known(topic,doc));input.put("offset",true);assertFalse(ManagedGraph.known(topic,doc));input.put("offset",new java.math.BigInteger("9223372036854775808"));assertFalse(ManagedGraph.known(topic,doc));
    ObjectNode tagged=tagged();((ObjectNode)tagged.get("event")).putObject("source_fields").put("observed_fraction",0.5);assertFalse(ManagedGraph.known("detectbridge.tagged-events.v1",tagged));assertFalse(ManagedGraph.known(topic,null));
  }
  @Test void registeredSchemasHaveOnlyLocalPresentReferencesAndNoFallbackLoader()throws Exception {
    assertEquals(15,ManagedGraph.RESOURCES.size());assertEquals(15,ManagedGraph.DOCUMENTS.size());
    Map<String,String> changed=new TreeMap<>(ManagedGraph.DOCUMENTS);String id="urn:detectbridge:integration-runtime:1.0.0:receipt";
    for(String ref:List.of("https://example.invalid/remote.schema.json","file:///tmp/foreign.schema.json","urn:detectbridge:unregistered:1.0.0:thing",id+"#/$defs/missing")) {
      ObjectNode schema=(ObjectNode)JSON.readTree(ManagedGraph.DOCUMENTS.get(id));schema.put("$ref",ref);changed.put(id,new String(bytes(schema),java.nio.charset.StandardCharsets.UTF_8));assertThrows(IllegalArgumentException.class,()->ManagedGraph.registry(changed));
    }
    var registry=ManagedGraph.registry(ManagedGraph.DOCUMENTS);assertThrows(RuntimeException.class,()->registry.getSchema(com.networknt.schema.SchemaLocation.of("https://example.invalid/never-fetch")));
  }
  @Test void supportedVersionForeignNestedReferenceAndFutureVersionAreUnknown()throws Exception {
    ObjectNode receipt=receipt();((ObjectNode)receipt.get("input")).putObject("future_reference").put("manifest","older-evidence");assertFalse(ManagedGraph.known("detectbridge.integration.receipts.v1",receipt));assertTrue(ManagedPlanner.graph(wire(receipt,"detectbridge.integration.receipts.v1")).unknown);
    ObjectNode future=JSON.createObjectNode();future.put("version","99.0.0").put("processing_id","sha256:"+"a".repeat(64));assertTrue(ManagedPlanner.graph(wire(future,"detectbridge.processing-diagnostics.v1")).unknown);
  }
  void append(ManagedPlannerTest fixture,Path root,String name,JsonNode document)throws Exception {
    JsonNode config=fixture.fixture.fixture().at("/legacy/configuration"),topic=null;for(JsonNode t:config.get("topics"))if(t.get("name").asString().equals(name))topic=t;assertNotNull(topic);
    ObjectNode row=(ObjectNode)wire(document,name);row.put("version","1.0.0").put("topic_id",topic.get("id").asString()).put("partition",0).put("offset",0).put("timestamp",100).put("timestamp_type","CreateTime");row.put("id",Store.wireId(config.get("cluster").asString(),topic.get("id").asString(),0));row.putNull("key");row.putArray("headers");row.set("dependencies",config.get("objects"));byte[] plain=ndjson(row),zipped=compress(plain);
    ObjectNode meta=JSON.createObjectNode();meta.put("version","1.0.0").put("codec",CODEC).put("binding_sha256",hash(config)).put("topic_id",topic.get("id").asString()).put("partition",0).put("first",0).put("next",1);meta.putNull("previous");meta.set("dependencies",config.get("objects"));meta.set("payload",JSON.valueToTree(Store.payloadMeta(plain,zipped,1)));
    Path dir=root.resolve("segments").resolve(topic.get("id").asString()).resolve("0/0");Files.createDirectories(dir);Store.write(dir.resolve("records.ndjson.gz"),zipped);Store.write(dir.resolve("segment.json"),ndjson(meta));Store.writeChecksum(dir.resolve("segment.json"),ndjson(meta));
  }
  void partialBlockedAllAllowed(String topic,ObjectNode doc)throws Exception {
    var fixture=new ManagedPlannerTest();fixture.temporary=temporary;Path root=fixture.prepare();append(fixture,root,topic,doc);
    try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      fixture.reject("managed_unknown_graph_blocker",store,fixture.request(4,100),fixture.catalog(store));
      ObjectNode full=fixture.request(6,200);((ArrayNode)full.get("targets")).addObject().put("topic",topic).put("next",1);assertNotNull(ManagedPlanner.plan(store,full,fixture.catalog(store)));
      ((ArrayNode)store.holds.get("holds")).addObject().put("scope","all");fixture.reject("managed_hold_blocker",store,full,fixture.catalog(store));
    }
  }
  @Test void futureV99DerivedGraphCannotPermitPartialRetirement()throws Exception {ObjectNode future=JSON.createObjectNode();future.put("version","99.0.0").put("processing_id","sha256:"+"a".repeat(64));partialBlockedAllAllowed("detectbridge.processing-diagnostics.v1",future);}
  @Test void supportedVersionForeignNestedReferenceCannotPermitPartialRetirement()throws Exception {ObjectNode doc=receipt();((ObjectNode)doc.get("input")).putObject("future_reference").put("manifest","older-evidence");partialBlockedAllAllowed("detectbridge.integration.receipts.v1",doc);}  @Test void arbitraryNormalizedExtensionCannotPermitPartialRetirement()throws Exception {ObjectNode doc=tagged();((ObjectNode)doc.at("/event/detectbridge")).putObject("extensions").putObject("future.context").put("reference","unknown");partialBlockedAllAllowed("detectbridge.tagged-events.v1",doc);}

}
