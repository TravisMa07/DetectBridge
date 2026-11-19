package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

class ManagedPlannerTest {
  @TempDir Path temporary;
  ManagedStoreTest fixture;
  Path prepare()throws Exception {fixture=new ManagedStoreTest();fixture.temporary=temporary;Path root=fixture.legacy();fixture.enable(root);return root;}
  ObjectNode request(long next,long cutoff) {
    ObjectNode r=JSON.createObjectNode();r.put("operation_id","00000000-0000-4000-8000-000000000052").put("cutoff_ms",cutoff).put("reason","original synthetic retirement");r.putArray("targets").addObject().put("topic",Main.INPUT).put("next",next);return r;
  }
  ObjectNode catalog(ManagedStore store) {ObjectNode c=JSON.createObjectNode();c.put("version","1.0.0");c.set("destination",store.registration.get("catalog_destination"));c.putArray("pins");return c;}
  void reject(String category,ManagedStore store,JsonNode request,JsonNode catalog) {assertEquals(category,assertThrows(Failure.class,()->ManagedPlanner.plan(store,request,catalog)).category);}
  @Test void dryPlanPinsOriginalCompletePrefixAndIsDeterministicWithoutMutation()throws Exception {
    Path root=prepare();byte[] original=Files.readAllBytes(root.resolve("segments/topic-0/0/0/records.ndjson.gz"));
    try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      JsonNode catalog=catalog(store),plan=ManagedPlanner.plan(store,request(4,100),catalog);
      assertEquals(2,plan.get("candidates").size());assertEquals(4,plan.at("/targets/0/next").asLong());assertEquals(9,plan.get("observed").size());
      assertEquals(fixture.fixture().at("/retirement_expected/previous_sha256").asString(),plan.at("/candidates/1/segment_sha256").asString());
      assertEquals(6,plan.get("observed").valueStream().filter(o->o.get("topic").asString().equals(Main.INPUT)).findFirst().orElseThrow().get("next").asLong());
      assertEquals(hash(store.holds),plan.get("holds_sha256").asString());assertEquals(hash(catalog),plan.get("catalog_sha256").asString());
      assertEquals(plan,ManagedPlanner.plan(store,request(4,100),catalog));ManagedFormat.require("plan",plan);
      assertTrue(plan.at("/candidates/0/identities").valueStream().anyMatch(i->i.asString().equals("9566ce83507ca7c2fefe6d113f7682a199e9110e398010f9703fb5724a048604")));
      assertEquals(0,store.floors.get(Main.INPUT).next());assertArrayEquals(original,Files.readAllBytes(root.resolve("segments/topic-0/0/0/records.ndjson.gz")));
    }
  }
  @Test void cutoffIsInclusiveAndTargetsCannotSplitSegments()throws Exception {
    Path root=prepare();try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      JsonNode catalog=catalog(store);assertNotNull(ManagedPlanner.plan(store,request(4,100),catalog));
      reject("managed_cutoff_timestamp",store,request(4,99),catalog);reject("managed_target_not_boundary",store,request(3,100),catalog);reject("managed_target",store,request(8,100),catalog);
      ObjectNode fractional=request(4,100);fractional.put("cutoff_ms",1.5);reject("integer_invalid",store,fractional,catalog);
    }
  }
  @Test void retainedSameRunBlocksDespiteDistinctControlIdentities()throws Exception {
    Path root=prepare();try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      reject("managed_retained_identity_blocker",store,request(2,100),catalog(store));
    }
  }
  @Test void everySealedReferencePositionIsProtectedAndPinCorruptionFailsClosed()throws Exception {
    Path root=prepare();try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      for(String position:List.of("inputs","outputs","anchor","control")) {
        ObjectNode c=catalog(store),selection=JSON.createObjectNode();selection.put("archive_binding_sha256",store.binding);selection.putObject("request").putObject(position).put("topic",Main.INPUT).put("offset",2);
        ((ArrayNode)c.get("pins")).addObject().put("selection_sha256",hash(selection)).set("selection",selection);reject("managed_pin_blocker",store,request(4,100),c);
        ((ObjectNode)c.at("/pins/0")).put("selection_sha256","b".repeat(64));reject("managed_catalog_pin",store,request(4,100),c);
      }
      ObjectNode c=catalog(store);c.put("destination",temporary.resolve("foreign").toString());reject("managed_catalog_snapshot",store,request(4,100),c);
    }
  }
  @Test void holdsApplyAllRangeRunAndRegisteredObjectScopes()throws Exception {
    Path root=prepare();try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      for(String scope:List.of("all","range","run","object")) {
        ArrayNode holds=(ArrayNode)store.holds.get("holds");holds.removeAll();ObjectNode h=holds.addObject();h.put("scope",scope).put("topic",Main.INPUT).put("first",0).put("next",2);
        h.put("subject",scope.equals("object")?store.config.get("objects").get(0).asString():"00000000-0000-4000-8000-000000000101");
        reject("managed_hold_blocker",store,request(4,100),catalog(store));
      }
    }
  }
  JsonNode wire(JsonNode document,String topic,String category) {ObjectNode wire=JSON.createObjectNode();wire.put("id","sha256:"+"a".repeat(64)).put("topic",topic).put("category",category).put("value",b64(bytes(document)));return wire;}
  @Test void sourceFingerprintPreservesLegacyReceiptExclusionAndExactContext()throws Exception {
    ObjectNode doc=JSON.createObjectNode();doc.put("kind","record");doc.putObject("raw").put("record_id","record");doc.putObject("context").put("run_id","run").put("host_id","host").putObject("receipt").put("time",1);
    ManagedPlanner.Graph original=ManagedPlanner.graph(wire(doc,Main.INPUT,"source"));
    assertTrue(original.fingerprints.contains(hash("run/record")+"/"+Main.fingerprint(doc)));
    ((ObjectNode)doc.at("/context/receipt")).put("time",99);assertEquals(original.fingerprints,ManagedPlanner.graph(wire(doc,Main.INPUT,"source")).fingerprints);
    ((ObjectNode)doc.get("context")).put("host_id","changed");assertNotEquals(original.fingerprints,ManagedPlanner.graph(wire(doc,Main.INPUT,"source")).fingerprints);
  }
  @Test void everyLegacyComparableRawContextSurvivesRetirementEvenWhenSourceIsInvalidOrConflicting()throws Exception {
    ObjectNode doc=JSON.createObjectNode();doc.put("kind","future-kind");doc.putObject("raw").put("record_id","record");doc.putObject("context").put("run_id","run");
    String expected=hash("run/record")+"/"+Main.fingerprint(doc);
    for(String category:List.of("invalid_source","semantic_conflict","opaque")) {
      ManagedPlanner.Graph graph=ManagedPlanner.graph(wire(doc,Main.INPUT,category));
      assertTrue(graph.fingerprints.contains(expected));assertTrue(graph.unknown);
    }
    ((ObjectNode)doc.get("raw")).put("unsupported_fraction",0.5);
    ObjectNode bad=(ObjectNode)wire(JSON.createObjectNode(),Main.INPUT,"invalid_source");bad.put("value",b64(io.detectbridge.transport.Json.bytes(doc)));
    assertTrue(ManagedPlanner.graph(bad).fingerprints.contains(hash("run/record")+"/"+hash(List.of("detectbridge.archive.invalid-fingerprint/1","run/record"))));
  }
  @Test void derivedRawContextNeverManufacturesRetiredSourceFingerprints()throws Exception {
    ObjectNode doc=JSON.createObjectNode();doc.put("version","99.0.0").put("processing_id","sha256:"+"e".repeat(64));doc.putObject("raw").put("record_id","source-record");doc.putObject("context").put("run_id","source-run");String expected=hash("source-run/source-record")+"/"+Main.fingerprint(doc);
    for(String topic:List.of("detectbridge.tagged-events.v1","detectbridge.processing-diagnostics.v1","detectbridge.integration.preservation.v1")) {
      var derived=ManagedPlanner.graph(wire(doc,topic,"derived"));assertTrue(derived.unknown);assertTrue(derived.fingerprints.isEmpty(),"derived raw/context is not a prior input occurrence");
    }
    for(String category:List.of("source","invalid_source","semantic_conflict","opaque"))assertTrue(ManagedPlanner.graph(wire(doc,Main.INPUT,category)).fingerprints.contains(expected),"every legacy-comparable INPUT raw/context remains protected");
  }
  @Test void graphFindsLateAndNestedEvidenceLinksWithoutTreatingHostRuleIdsAsEvidence()throws Exception {
    ObjectNode doc=JSON.createObjectNode();doc.put("preservation_id","preservation").put("run_id","run");doc.putObject("diagnostic").put("original_manifest_id","old-manifest").put("record_id","record").put("host_id","ordinary-host");doc.putObject("rule").put("id","ordinary-rule");
    ManagedPlanner.Graph graph=ManagedPlanner.graph(wire(doc,"detectbridge.integration.preservation.v1","derived"));
    for(String id:List.of("preservation","run","old-manifest","record"))assertTrue(graph.identities.contains(ManagedPlanner.token(id)));
    for(String id:List.of("ordinary-rule","ordinary-host"))assertFalse(graph.identities.contains(ManagedPlanner.token(id)));
    assertTrue(graph.unknown); // Minimal unversioned diagnostic has no closed-contract proof.
    doc.putObject("references").put("future_identity","unknown");assertTrue(ManagedPlanner.graph(wire(doc,"detectbridge.integration.preservation.v1","derived")).unknown);
    assertTrue(ManagedPlanner.graph(wire(doc,"detectbridge.integration.quarantine.v1","derived")).unknown);
  }
  @Test void unknownRootGraphExtensionIsNeverTreatedAsARecognizedProjection()throws Exception {
    ObjectNode doc=JSON.createObjectNode();doc.put("processing_id","processing").put("version","1.1.0");doc.putObject("future_graph").put("reference","unrecognized");
    assertTrue(ManagedPlanner.graph(wire(doc,"detectbridge.processing-diagnostics.v1","derived")).unknown);
  }
  @Test void retainedReceiptReferencesTheOriginalKafkaWireIdentity()throws Exception {
    ObjectNode receipt=JSON.createObjectNode();receipt.put("id","receipt").put("kind","input_receipt");receipt.putObject("input").put("cluster_id","cluster").put("topic_id","topic").put("partition",0).put("offset",9007199254740993L);
    ManagedPlanner.Graph graph=ManagedPlanner.graph(wire(receipt,"detectbridge.integration.receipts.v1","derived"));
    assertTrue(graph.identities.contains(ManagedPlanner.token(Store.wireId("cluster","topic",9007199254740993L))));assertTrue(graph.unknown); // Unversioned minimal receipt remains linked but unknown.
  }
  void rewrite(Path root,int changed,java.util.function.Consumer<ArrayNode> change)throws Exception {
    String previous=null;int index=0;
    for(JsonNode source:fixture.fixture().at("/legacy/segments")) {
      ObjectNode meta=(ObjectNode)source.get("metadata").deepCopy();ArrayNode rows=(ArrayNode)source.get("rows").deepCopy();if(index++==changed)change.accept(rows);
      java.io.ByteArrayOutputStream raw=new java.io.ByteArrayOutputStream();for(JsonNode row:rows)raw.write(ndjson(row));byte[] bytes=raw.toByteArray(),zipped=compress(bytes);
      if(previous==null)meta.putNull("previous");else meta.put("previous",previous);meta.set("payload",JSON.valueToTree(Store.payloadMeta(bytes,zipped,rows.size())));
      Path directory=root.resolve("segments/topic-0/0/"+meta.get("first").asString());Files.write(directory.resolve("records.ndjson.gz"),zipped);Files.write(directory.resolve("segment.json"),ndjson(meta));Files.write(directory.resolve("segment.sha256"),(io.detectbridge.transport.Json.sha(ndjson(meta))+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));previous=hash(meta);
    }
  }
  @Test void unknownGraphsOnlyPermitTheEntireRetainedPopulationWithoutAnyHoldOrPin()throws Exception {
    Path root=prepare();rewrite(root,2,rows->((ObjectNode)rows.get(0)).put("category","opaque"));
    try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      ObjectNode catalog=catalog(store);reject("managed_unknown_graph_blocker",store,request(4,100),catalog);
      assertNotNull(ManagedPlanner.plan(store,request(6,200),catalog));
      ((ArrayNode)store.holds.get("holds")).addObject().put("scope","import").put("subject","unrelated");
      reject("managed_unknown_graph_blocker",store,request(6,200),catalog);
      ((ArrayNode)store.holds.get("holds")).removeAll();
      ObjectNode selection=JSON.createObjectNode();selection.put("archive_binding_sha256",store.binding);selection.putObject("anchor").put("topic",Main.INPUT).put("offset",99);
      ((ArrayNode)catalog.get("pins")).addObject().put("selection_sha256",hash(selection)).set("selection",selection);
      reject("managed_unknown_graph_blocker",store,request(6,200),catalog);
    }
  }
  @Test void unknownKafkaTimestampFailsButEmptyIntervalsNeedNoInventedTimestamp()throws Exception {
    Path root=prepare();rewrite(root,0,rows->((ObjectNode)rows.get(0)).put("timestamp",-1));
    try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)){reject("managed_cutoff_timestamp",store,request(4,100),catalog(store));}
    rewrite(root,0,ArrayNode::removeAll);
    try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      JsonNode plan=ManagedPlanner.plan(store,request(2,0),catalog(store));assertEquals(0,plan.at("/candidates/0/segment/payload/rows").asInt());assertTrue(plan.at("/candidates/0/identities").isEmpty());
    }
  }
  @Test void boundedScanAndSegmentBudgetsFailWithoutReturningPartialPlans()throws Exception {
    Path root=prepare();try(var store=new ManagedStore(root,false,ManagedStoreTest.IMPLEMENTATION)) {
      ObjectNode limits=(ObjectNode)store.registration.get("limits");limits.put("scan_rows",1);reject("managed_scan_budget",store,request(4,100),catalog(store));
      limits.put("scan_rows",65536);limits.put("plan_segments",1);reject("managed_plan_segment_budget",store,request(4,100),catalog(store));
      limits.put("plan_segments",256);limits.put("identity_tokens",1);reject("managed_identity_budget",store,request(4,100),catalog(store));
    }
  }
}
