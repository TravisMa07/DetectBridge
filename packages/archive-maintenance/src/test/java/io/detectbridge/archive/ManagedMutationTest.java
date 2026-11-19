package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class ManagedMutationTest {
  @TempDir Path temporary;
  final String operation="00000000-0000-4000-8000-000000000060";
  ManagedStoreTest fixture() {var fixture=new ManagedStoreTest();fixture.temporary=temporary;return fixture;}
  @Test void noCleanupBeforeAuthorityAndRecoveredHeadAreDurable()throws Exception {
    var fixture=fixture();Path root=fixture.legacy();fixture.retiredPrefix(root,fixture.enable(root));
    Path path=root.resolve("segments/topic-0/0/0");Files.createDirectory(path);Store.write(path.resolve("records.ndjson.gz"),new byte[]{1,2,3});
    Path head=root.resolve("maintenance/retirements/head.json");Files.delete(head);byte[] stale=ndjson(ManagedFormat.head("retirements",ManagedStoreTest.MANAGED,0,null));Store.write(head,stale);
    byte[] retained=Files.readAllBytes(root.resolve("segments/topic-0/0/4/records.ndjson.gz"));
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      var phases=new ArrayList<String>();
      var interrupted=new ManagedMutation(store,operation,phase->{phases.add(phase);if(phase.equals("before_head_publication"))throw new Failure("injected_before_head");});
      assertThrows(Failure.class,interrupted::recover);assertTrue(phases.contains("after_authority_sync"));assertTrue(Files.exists(path.resolve("records.ndjson.gz")));assertArrayEquals(stale,Files.readAllBytes(head));
    }
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      var phases=new ArrayList<String>();new ManagedMutation(store,operation,phases::add).recover();
      assertTrue(phases.indexOf("after_authority_sync")<phases.indexOf("after_head_directory_sync"));
      assertTrue(phases.indexOf("after_head_directory_sync")<phases.indexOf("before_retired_cleanup"));assertFalse(Files.exists(path));assertEquals(1,ManagedFormat.head(head,"retirements",ManagedStoreTest.MANAGED).get("sequence").asLong());
    }
    assertArrayEquals(retained,Files.readAllBytes(root.resolve("segments/topic-0/0/4/records.ndjson.gz")));
  }
  @Test void malformedHoldScopeFailsBeforePublication()throws Exception {
    var fixture=fixture();Path root=fixture.legacy();fixture.enable(root);
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      ObjectNode next=((ObjectNode)store.holds).deepCopy();next.put("revision",1);next.put("previous_sha256",hash(store.holds));
      ObjectNode hold=next.withArray("holds").addObject();hold.put("id",operation);hold.put("scope","all");hold.putNull("topic");hold.putNull("first");hold.putNull("next");hold.put("subject","unrelated");
      Failure failure=assertThrows(Failure.class,()->new ManagedMutation(store,operation,p->{}).holds(next));assertEquals("managed_hold_scope",failure.category);assertFalse(Files.exists(root.resolve("maintenance/holds/00000000000000000001")));
    }
  }
  @Test void comparedHoldRevisionAndIdenticalRetry()throws Exception {
    var fixture=fixture();Path root=fixture.legacy();fixture.enable(root);ObjectNode next;
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      next=((ObjectNode)store.holds).deepCopy();next.put("revision",1);next.put("previous_sha256",hash(store.holds));next.put("reason","explicit hold transition");
      new ManagedMutation(store,operation,p->{}).holds(next);
    }
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      var mutation=new ManagedMutation(store,operation,p->{});mutation.holds(next);ObjectNode conflicting=next.deepCopy();conflicting.put("reason","conflicting revision");assertThrows(Failure.class,()->mutation.holds(conflicting));assertEquals(next,store.holds);
    }
  }
  @Test void foreignPartialCannotBecomeRecoveryOwnership()throws Exception {
    var fixture=fixture();Path root=fixture.legacy();fixture.enable(root);Path partial=root.resolve("maintenance/retirements/.partial-"+operation);Files.createDirectory(partial);Store.write(partial.resolve("foreign.bin"),new byte[]{1});
    assertThrows(Failure.class,()->new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION));assertArrayEquals(new byte[]{1},Files.readAllBytes(partial.resolve("foreign.bin")));
  }  @Test void actualRetirementPublicationRetryAndAllCommittedCrashWindows()throws Exception {
    var cases=List.of("during_retirement_plan","before_retirement_plan_sync","during_retirement_plan_checksum","before_retirement_plan_checksum_sync","during_retirement_record","before_retirement_record_sync","during_retirement_record_checksum","before_retirement_record_checksum_sync","after_retirement_plan","before_retirement_publication","after_retirement_publication","after_retirement_directory_sync","before_head_publication","after_head_publication","after_head_directory_sync","during_retired_cleanup");
    for(int index=0;index<cases.size();index++) {
      Path scenario=temporary.resolve("case"+index);Files.createDirectory(scenario);var fixture=new ManagedStoreTest();fixture.temporary=scenario;
      Path root=fixture.legacy();fixture.enable(root);var helper=new ManagedPlannerTest();JsonNode plan,catalog;
      try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
        catalog=helper.catalog(store);ObjectNode request=helper.request(4,100);request.put("operation_id",operation);plan=ManagedPlanner.plan(store,request,catalog);
        String phase=cases.get(index);final boolean[] fired={false};
        Failure failure=assertThrows(Failure.class,()->new ManagedMutation(store,operation,p->{if(p.equals(phase)&&!fired[0]){fired[0]=true;throw new Failure("injected_crash");}}).retire(plan,catalog));assertEquals("injected_crash",failure.category);assertTrue(fired[0]);
      }
      try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
        boolean committed=Set.of("after_retirement_publication","after_retirement_directory_sync","before_head_publication","after_head_publication","after_head_directory_sync","during_retired_cleanup").contains(cases.get(index));assertEquals(committed?4:0,store.floors.get(Main.INPUT).next());assertEquals(6,store.prefix(Main.INPUT).next());
        new ManagedMutation(store,operation,p->{}).retire(plan,catalog);assertEquals(4,store.floors.get(Main.INPUT).next());assertFalse(Files.exists(root.resolve("segments/topic-0/0/0")));assertFalse(Files.exists(root.resolve("segments/topic-0/0/2")));assertEquals(2,store.readSegment(Main.INPUT,4).size());
        new ManagedMutation(store,operation,p->{}).retire(plan,catalog);assertEquals(1,store.retirementSequence);
        ObjectNode conflicting=((ObjectNode)plan).deepCopy();conflicting.put("reason","conflicting retry");assertThrows(Failure.class,()->new ManagedMutation(store,operation,p->{}).retire(conflicting,catalog));
      }
    }
  }
  @Test void changedHoldRevisionMakesPreviouslyFrozenPlanStale()throws Exception {
    var fixture=fixture();Path root=fixture.legacy();fixture.enable(root);var helper=new ManagedPlannerTest();
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      JsonNode catalog=helper.catalog(store);ObjectNode request=helper.request(4,100);request.put("operation_id",operation);JsonNode plan=ManagedPlanner.plan(store,request,catalog);
      ObjectNode holds=((ObjectNode)store.holds).deepCopy();holds.put("revision",1);holds.put("previous_sha256",hash(store.holds));holds.put("reason","new explicit revision");new ManagedMutation(store,operation,p->{}).holds(holds);
      Failure failure=assertThrows(Failure.class,()->new ManagedMutation(store,operation,p->{}).retire(plan,catalog));assertEquals("managed_stale_plan",failure.category);assertEquals(0,store.floors.get(Main.INPUT).next());assertTrue(Files.exists(root.resolve("segments/topic-0/0/0/records.ndjson.gz")));
    }
  }
  @Test void canonicalPlanRoundTripKeepsExactIntegersAndCanBeApplied()throws Exception {
    var fixture=fixture();Path root=fixture.legacy();fixture.enable(root);var helper=new ManagedPlannerTest();
    try(var store=new ManagedStore(root,true,ManagedStoreTest.IMPLEMENTATION)) {
      ObjectNode request=helper.request(4,100);request.put("operation_id",operation);JsonNode catalog=helper.catalog(store),memory=ManagedPlanner.plan(store,request,catalog);
      JsonNode persisted=read(ndjson(memory),16*MIB);assertEquals(hash(memory),hash(persisted));assertArrayEquals(ndjson(memory),ndjson(persisted));
      new ManagedMutation(store,operation,p->{}).retire(persisted,catalog);assertEquals(4,store.floors.get(Main.INPUT).next());
    }
  }

}
