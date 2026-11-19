package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;

class ManagedStatusTest {
  @TempDir Path temporary;
  ManagedStoreTest fixture() {var fixture=new ManagedStoreTest();fixture.temporary=temporary;return fixture;}
  @Test void fixedBudgetAndBlockerCountersContainNoPrivateContent()throws Exception {
    var fixture=fixture();Path archive=fixture.legacy();fixture.enable(archive);
    try(var store=new ManagedStore(archive,false,ManagedStoreTest.IMPLEMENTATION)) {
      Map<String,Object> result=store.progress();long used=store.managedBytes(),cap=store.config.at("/limits/archive_bytes").asLong();
      assertEquals(used,result.get("archive_bytes_used"));assertEquals(used,result.get("managed_bytes"));assertEquals(cap,result.get("archive_bytes_cap"));
      assertEquals(cap-ManagedFormat.HEADROOM-used,result.get("ordinary_headroom_bytes"));assertEquals(cap-ManagedFormat.CONTROL-used,result.get("maintenance_headroom_bytes"));
      assertEquals(store.config.at("/limits/reserve_bytes").asLong(),result.get("reserve_bytes"));assertTrue(((Long)result.get("free_bytes"))>=0);
      assertEquals(0L,result.get("holds_count"));assertEquals(0L,result.get("pending_cleanup_count"));assertEquals(0L,result.get("fingerprint_count"));assertEquals(6L,result.get("live_rows"));assertEquals(0L,result.get("retirement_sequence"));
      String serialized=new String(bytes(result),java.nio.charset.StandardCharsets.UTF_8);assertFalse(serialized.contains(temporary.toString()));assertFalse(serialized.contains("reason"));assertFalse(serialized.contains("private-body"));
    }
  }
  @Test void retirementChangesFloorButNeverRollsBackDurableHead()throws Exception {
    var fixture=fixture();Path archive=fixture.legacy();fixture.retiredPrefix(archive,fixture.enable(archive));
    try(var store=new ManagedStore(archive,false,ManagedStoreTest.IMPLEMENTATION);var broker=new MockConsumer<byte[],byte[]>(OffsetResetStrategy.EARLIEST)) {
      Map<TopicPartition,Long> beginnings=new HashMap<>(),ends=new HashMap<>();Map<TopicPartition,OffsetAndMetadata> committed=new HashMap<>();
      for(String topic:Main.TOPICS){var partition=new TopicPartition(topic,0);beginnings.put(partition,0L);ends.put(partition,topic.equals(Main.INPUT)?10L:0L);if(topic.equals(Main.INPUT))committed.put(partition,new OffsetAndMetadata(5L));}
      broker.assign(beginnings.keySet());broker.updateBeginningOffsets(beginnings);broker.updateEndOffsets(ends);broker.commitSync(committed);
      JsonNode result=JSON.valueToTree(ManagedMain.status(store,broker));JsonNode input=result.get("partitions").get(Main.INPUT);
      assertEquals(4L,input.get("retained_floor").asLong());assertEquals(6L,input.get("durable_next").asLong());assertEquals(5L,input.get("committed_next").asLong());assertEquals(0L,input.get("earliest").asLong());assertEquals(10L,input.get("end").asLong());assertEquals(4L,input.get("lag").asLong());
      assertTrue(result.get("partitions").get(Main.TOPICS.stream().filter(t->!t.equals(Main.INPUT)).findFirst().orElseThrow()).get("committed_next").isNull());
      assertEquals(ManagedStoreTest.MANAGED,store.registration.get("managed_id").asString());assertEquals(store.registration.get("group").asString(),ManagedMain.properties(store).getProperty("group.id"));
      assertEquals(6L,result.get("durable_next").get(Main.INPUT).asLong());assertEquals(4L,result.get("retained_floor").get(Main.INPUT).asLong());assertEquals(1L,result.get("retirement_sequence").asLong());assertEquals(2L,result.get("live_rows").asLong());
      assertEquals(beginnings.keySet(),broker.assignment());assertTrue(broker.subscription().isEmpty());assertEquals(5L,broker.committed(Set.of(new TopicPartition(Main.INPUT,0))).get(new TopicPartition(Main.INPUT,0)).offset());
    }
  }
}
