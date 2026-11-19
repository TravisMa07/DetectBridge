package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class ManagedImportTest {
  @TempDir Path temporary;
  Path run,cache,index,archive;
  ObjectNode metadata;
  void setup()throws Exception {
    temporary=temporary.toRealPath();
    var baseline=new ManagedStoreTest();baseline.temporary=temporary;
    archive=baseline.legacy();baseline.enable(archive);
    run=Files.createDirectory(temporary.resolve("source-run"));cache=Files.createDirectory(temporary.resolve("source-cache"));index=Files.createDirectory(temporary.resolve("source-index"));
    metadata=JSON.createObjectNode();metadata.put("version","1.0.0");metadata.put("managed_id",ManagedStoreTest.MANAGED);metadata.put("run_id","00000000-0000-4000-8000-000000000053");
    byte[] manifest="{\"speed\":1.5}\n".getBytes(java.nio.charset.StandardCharsets.UTF_8);
    Store.write(run.resolve("manifest.json"),manifest);metadata.put("manifest_sha256",io.detectbridge.transport.Json.sha(manifest));metadata.put("p05_manifest_sha256","b".repeat(64));metadata.put("reviewed_catalog_sha256","c".repeat(64));metadata.put("record_count",0);metadata.put("envelope_count",1);metadata.put("segment_count",1);
    var files=metadata.putArray("files");var f=files.addObject();f.put("kind","original");f.put("role","manifest");f.put("path","run/manifest.json");f.put("sha256",io.detectbridge.transport.Json.sha(manifest));f.put("length",manifest.length);identity();
  }
  void identity(){metadata.put("id",hash(List.of("detectbridge.archive.p05-import/1",ManagedStoreTest.MANAGED,metadata.get("run_id").asString(),metadata.get("manifest_sha256").asString(),metadata.get("files"))));}
  @Test void opaqueManifestRoundTripsAndIdenticalRetryVerifies()throws Exception {
    setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      var operation=UUID.randomUUID();assertEquals(metadata,ManagedImport.importClosure(store,metadata,run,cache,index,operation,p->{}));
      assertEquals(metadata,ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{}));
      Path restored=temporary.resolve("restored"),objects=temporary.resolve("cache"),derived=temporary.resolve("index");
      ManagedImport.exportClosure(store,metadata.get("id").asString(),restored,objects,derived);
      assertArrayEquals(Files.readAllBytes(run.resolve("manifest.json")),Files.readAllBytes(restored.resolve("manifest.json")));
      assertThrows(Failure.class,()->ManagedImport.exportClosure(store,metadata.get("id").asString(),restored,objects,derived));
    }
  }
  @Test void changedSourceFailsBeforePublication()throws Exception {
    setup();Files.writeString(run.resolve("manifest.json"),"changed");try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      assertThrows(Failure.class,()->ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{}));
      assertFalse(Files.exists(archive.resolve("imports").resolve(metadata.get("id").asString())));
    }
  }
  @Test void traversalAndSymlinkSourcesAreRejected()throws Exception {
    setup();((ObjectNode)metadata.get("files").get(0)).put("path","run/../manifest.json");identity();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      assertThrows(Failure.class,()->ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{}));
    }
  }
  @Test void symlinkedSourceAndExportOverlapAreRejected()throws Exception {
    setup();Path manifest=run.resolve("manifest.json"),saved=temporary.resolve("original.json");Files.move(manifest,saved);Files.createSymbolicLink(manifest,saved);
    try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      assertThrows(Failure.class,()->ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{}));
      Files.delete(manifest);Files.move(saved,manifest);ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});
      assertThrows(Failure.class,()->ManagedImport.exportClosure(store,metadata.get("id").asString(),temporary.resolve("new"),temporary.resolve("new/cache"),temporary.resolve("new-index")));
    }
  }
  @Test void ownedInterruptedPublicationResumesButForeignFileIsNeverRemoved()throws Exception {
    setup();UUID operation=UUID.randomUUID();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      assertThrows(java.io.IOException.class,()->ManagedImport.importClosure(store,metadata,run,cache,index,operation,p->{if(p.equals("before_import_publication"))throw new java.io.IOException("crash");}));
      Path partial=archive.resolve("imports/.partial-"+operation);ManagedImport.verifyPartial(store,partial);
      Files.writeString(partial.resolve("foreign"),"never remove");assertThrows(Failure.class,()->ManagedImport.importClosure(store,metadata,run,cache,index,operation,p->{}));assertTrue(Files.exists(partial.resolve("foreign")));
      Files.delete(partial.resolve("foreign"));assertEquals(metadata,ManagedImport.importClosure(store,metadata,run,cache,index,operation,p->{}));
    }
  }
  @Test void everyOwnedPublicationBoundaryResumesTheIdenticalClosure()throws Exception {
    Path cases=temporary;int number=0;
    for(String phase:List.of("after_import_owner","after_import_payload","after_import_object","before_import_publication","after_import_publication","after_import_directory_sync")) {
      temporary=Files.createDirectory(cases.resolve("case-"+(number++)));setup();byte[] original=Files.readAllBytes(run.resolve("manifest.json"));UUID operation=UUID.randomUUID();
      try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
        assertThrows(java.io.IOException.class,()->ManagedImport.importClosure(store,metadata,run,cache,index,operation,p->{if(p.equals(phase))throw new java.io.IOException("crash");}),phase);
        assertEquals(metadata,ManagedImport.importClosure(store,metadata,run,cache,index,operation,p->{}),phase);
        assertEquals(metadata,ManagedImport.verifyClosure(store,metadata.get("id").asString()));
        assertFalse(Files.exists(archive.resolve("imports/.partial-"+operation)));assertArrayEquals(original,Files.readAllBytes(run.resolve("manifest.json")));
      }
    }
  }
  @Test void corruptImportedObjectCannotExport()throws Exception {
    setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});
      Path object=archive.resolve("imports").resolve(metadata.get("id").asString()).resolve("objects").resolve(metadata.get("manifest_sha256").asString()).resolve("bytes.ndjson.gz");Files.write(object,new byte[]{1});
      assertThrows(Failure.class,()->ManagedImport.exportClosure(store,metadata.get("id").asString(),temporary.resolve("r"),temporary.resolve("c"),temporary.resolve("i")));
      assertFalse(Files.exists(temporary.resolve("r")));
    }
  }
  ObjectNode catalog(ManagedStore store){var catalog=JSON.createObjectNode();catalog.put("version","1.0.0");catalog.set("destination",store.registration.get("catalog_destination"));catalog.putArray("pins");return catalog;}
  ObjectNode request(){var request=JSON.createObjectNode();request.put("operation_id",UUID.randomUUID().toString());request.put("cutoff_ms",0);request.put("reason","explicit whole original P05 import retirement");request.putArray("imports").add(metadata.get("id").asString());return request;}
  @Test void wholeImportDryPlanPinsExactClosureAndLeavesAllKafkaHeadsUnchanged()throws Exception {
    setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});JsonNode plan=ManagedImport.retirementPlan(store,request(),catalog(store));
      assertEquals("import",plan.get("kind").asString());assertEquals(9,plan.get("observed").size());assertTrue(plan.get("targets").isEmpty());assertTrue(plan.get("candidates").isEmpty());
      assertEquals(hash(metadata),plan.at("/imports/0/metadata_sha256").asString());assertEquals(metadata.get("id"),plan.at("/imports/0/id"));assertEquals(0,plan.get("cutoff_ms").asLong());
      assertTrue(store.retiredImports.isEmpty());assertEquals(metadata,ManagedImport.verifyClosure(store,metadata.get("id").asString()));
      assertThrows(Failure.class,()->ManagedImport.cleanupRetired(store,archive.resolve("imports").resolve(metadata.get("id").asString()),plan.at("/imports/0"),p->{}));
    }
  }
  @Test void importRunObjectAndAllHoldsAndCatalogReferencesBlockTheDryPlan()throws Exception {
    setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});JsonNode originalHolds=store.holds;
      for(String scope:List.of("all","import","run","object")) {
        ObjectNode holds=((ObjectNode)originalHolds).deepCopy();var hold=holds.withArray("holds").addObject();hold.put("scope",scope);if(scope.equals("import"))hold.put("subject",metadata.get("id").asString());else if(scope.equals("run"))hold.put("subject",metadata.get("run_id").asString());else if(scope.equals("object"))hold.put("subject",metadata.get("manifest_sha256").asString());
        store.holds=holds;assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog(store)),scope);
      }
      store.holds=originalHolds;ObjectNode catalog=catalog(store);var selection=JSON.createObjectNode();selection.put("archive_binding_sha256",store.binding);selection.set("import_id",metadata.get("id"));catalog.withArray("pins").addObject().put("selection_sha256",hash(selection)).set("selection",selection);
      assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog));
      ObjectNode invalid=request();invalid.withArray("imports").add(metadata.get("id").asString());assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,invalid,catalog(store)));
    }
  }
  @Test void everyRetiredCleanupInterruptionRemainsVerifiableAndResumable()throws Exception {
    Path cases=temporary;int number=0;
    for(int failureAt=1;failureAt<=8;failureAt++) {
      temporary=Files.createDirectory(cases.resolve("retirement-"+(number++)));setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
        ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});JsonNode target=ManagedImport.retirementPlan(store,request(),catalog(store)).at("/imports/0");String id=metadata.get("id").asString();Path directory=archive.resolve("imports").resolve(id);store.retiredImports.add(id);
        int[] calls={0};int stop=failureAt;
        try{ManagedImport.cleanupRetired(store,directory,target,p->{if(++calls[0]==stop)throw new java.io.IOException("crash");});}catch(java.io.IOException injected){assertEquals("crash",injected.getMessage());}
        ManagedImport.validateRetired(store,directory,target);ManagedImport.cleanupRetired(store,directory,target,p->{});assertFalse(Files.exists(directory));assertArrayEquals("{\"speed\":1.5}\n".getBytes(java.nio.charset.StandardCharsets.UTF_8),Files.readAllBytes(run.resolve("manifest.json")));
      }
    }
  }
  @Test void retiredCleanupNeverRemovesForeignFilesOrMissingAuthority()throws Exception {
    setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});JsonNode target=ManagedImport.retirementPlan(store,request(),catalog(store)).at("/imports/0");String id=metadata.get("id").asString();Path directory=archive.resolve("imports").resolve(id);store.retiredImports.add(id);
      Path foreign=directory.resolve("objects/foreign");Files.createDirectory(foreign);assertThrows(Failure.class,()->ManagedImport.cleanupRetired(store,directory,target,p->{}));assertTrue(Files.exists(foreign));Files.delete(foreign);
      Files.delete(directory.resolve("import.json"));assertThrows(Failure.class,()->ManagedImport.validateRetired(store,directory,target));assertTrue(Files.exists(directory.resolve("objects")));
    }
  }

  void appendRetainedDerived(String topic,JsonNode doc)throws Exception {
    var planner=new ManagedPlannerTest();planner.temporary=temporary;planner.fixture=new ManagedStoreTest();planner.fixture.temporary=temporary;
    new ManagedGraphTest().append(planner,archive,topic,doc);
  }
  @Test void retainedFutureWireGraphReferencingImportBlocksWholeImportRetirement()throws Exception {
    setup();ObjectNode future=JSON.createObjectNode();future.put("version","99.0.0").put("processing_id","sha256:"+"e".repeat(64));future.putObject("future_reference").set("import",metadata.get("id"));appendRetainedDerived("detectbridge.processing-diagnostics.v1",future);
    try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});
      assertEquals("managed_unknown_graph_blocker",assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog(store))).category);
      assertEquals(metadata,ManagedImport.verifyClosure(store,metadata.get("id").asString()));assertEquals(0,store.retirementSequence);assertTrue(store.retiredImports.isEmpty());
    }
  }
  @Test void supportedVersionUnknownNestedWireReferenceAlsoBlocksImportRetirement()throws Exception {
    setup();ObjectNode receipt=new ManagedGraphTest().receipt();((ObjectNode)receipt.get("input")).putObject("future_reference").set("run",metadata.get("run_id"));appendRetainedDerived("detectbridge.integration.receipts.v1",receipt);
    try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});
      assertEquals("managed_unknown_graph_blocker",assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog(store))).category);assertEquals(metadata,ManagedImport.verifyClosure(store,metadata.get("id").asString()));
    }
  }
  @Test void recognizedRetainedWireReferencingOriginalRunBlocksImportRetirement()throws Exception {
    setup();ObjectNode tagged=new ManagedGraphTest().tagged();((ObjectNode)tagged.at("/event/detectbridge")).set("run_id",metadata.get("run_id"));assertTrue(ManagedGraph.known("detectbridge.tagged-events.v1",tagged));appendRetainedDerived("detectbridge.tagged-events.v1",tagged);
    try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});
      assertEquals("managed_retained_identity_blocker",assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog(store))).category);assertEquals(metadata,ManagedImport.verifyClosure(store,metadata.get("id").asString()));
    }
  }

  @Test void importRetirementRetainedGraphScanHonorsFiniteBudgets()throws Exception {
    setup();try(var store=new ManagedStore(archive,true,ManagedStoreTest.IMPLEMENTATION)) {
      ManagedImport.importClosure(store,metadata,run,cache,index,UUID.randomUUID(),p->{});ObjectNode limits=(ObjectNode)store.registration.get("limits");limits.put("scan_rows",1);
      assertEquals("managed_scan_budget",assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog(store))).category);limits.put("scan_rows",65536);limits.put("identity_tokens",1);
      assertEquals("managed_identity_budget",assertThrows(Failure.class,()->ManagedImport.retirementPlan(store,request(),catalog(store))).category);assertEquals(metadata,ManagedImport.verifyClosure(store,metadata.get("id").asString()));assertEquals(0,store.retirementSequence);
    }
  }

}
