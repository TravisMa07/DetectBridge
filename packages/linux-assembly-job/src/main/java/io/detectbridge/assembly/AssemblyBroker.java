package io.detectbridge.assembly;

import io.detectbridge.detection.Contracts;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.admin.ConfigEntry;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.config.ConfigResource;

public final class AssemblyBroker {
  public static final String INPUT = "detectbridge.assembly.input.v1";
  public static final String OUTPUT = "detectbridge.assembly.results.v1";
  public static final String QUARANTINE = "detectbridge.assembly.quarantine.v1";
  public static final String MANIFEST = "detectbridge.assembly.manifests.v1";
  public static final String DIAGNOSTIC = "detectbridge.assembly.diagnostics.v1";
  public static final String RECEIPT = "detectbridge.assembly.receipts.v1";
  public static final List<String> TOPICS = List.of(INPUT, OUTPUT, MANIFEST, DIAGNOSTIC, QUARANTINE, RECEIPT);
  public static final Map<String,String> ROUTES = Map.of("event",OUTPUT,"manifest",MANIFEST,"diagnostic",DIAGNOSTIC,"quarantine",QUARANTINE,"receipt",RECEIPT);
  /** Mutable fault injection policy cannot change source/destination identity. */
  public static void verifyIdentities(String bootstrap, String cluster, Map<String,String> ids) throws Exception {
    Contracts.check(ids.keySet().equals(new java.util.HashSet<>(TOPICS)), "assembly_topic_scope");
    try (Admin admin = Admin.create(properties(bootstrap))) {
      Contracts.check(cluster.equals(admin.describeCluster().clusterId().get(15, TimeUnit.SECONDS)), "assembly_cluster_changed");
      var topics = admin.describeTopics(TOPICS).allTopicNames().get(15,TimeUnit.SECONDS);
      for(String name : TOPICS) Contracts.check(topics.get(name).partitions().size()==1
          && ids.get(name).equals(topics.get(name).topicId().toString()), "assembly_topic_changed");
    }
  }
  public static final Map<String, String> TOPIC_CONFIG =
      Map.of(
          "retention.ms",
          "-1",
          "retention.bytes",
          "-1",
          "min.insync.replicas",
          "1",
          "cleanup.policy",
          "delete",
          "max.message.bytes",
          "2097152");

  private AssemblyBroker() {}

  public static Properties properties(String bootstrap) {
    Properties p = new Properties();
    p.put("bootstrap.servers", bootstrap);
    p.put("request.timeout.ms", "10000");
    p.put("default.api.timeout.ms", "15000");
    p.put("client.id", "detectbridge-assembly-v1");
    return p;
  }

  public static Properties producerProperties(String bootstrap) {
    Properties p = properties(bootstrap);
    p.put("key.serializer", "org.apache.kafka.common.serialization.ByteArraySerializer");
    p.put("value.serializer", "org.apache.kafka.common.serialization.ByteArraySerializer");
    p.put("enable.idempotence", "true");
    p.put("acks", "all");
    p.put("max.in.flight.requests.per.connection", "1");
    p.put("delivery.timeout.ms", "30000");
    p.put("max.block.ms", "15000");
    p.put("buffer.memory", "8388608");
    p.put("max.request.size", "2097152");
    p.put("batch.size", "16384");
    return p;
  }

  public static Map<String, Object> describe(String bootstrap, boolean create, String group)
      throws Exception {
    return describe(bootstrap, create, group, TOPICS);
  }

  public static Map<String, Object> describe(String bootstrap, boolean create, String group,
      List<String> topicNames) throws Exception {
    try (Admin admin = Admin.create(properties(bootstrap))) {
      if (create) {
        var existing = admin.listTopics().names().get(15, TimeUnit.SECONDS);
        List<NewTopic> topics = new ArrayList<>();
        for (String name : topicNames)
          if (!existing.contains(name))
            topics.add(new NewTopic(name, 1, (short) 1).configs(TOPIC_CONFIG));
        if (!topics.isEmpty()) admin.createTopics(topics).all().get(15, TimeUnit.SECONDS);
      }
      var descriptions = admin.describeTopics(topicNames).allTopicNames().get(15, TimeUnit.SECONDS);
      Map<String, Object> topics = new LinkedHashMap<>();
      for (String name : topicNames) {
        var topic = descriptions.get(name);
        if (topic.partitions().size() != 1 || topic.partitions().get(0).replicas().size() != 1)
          throw new IllegalStateException("topic_topology_mismatch");
        var resource = new ConfigResource(ConfigResource.Type.TOPIC, name);
        var config =
            admin.describeConfigs(List.of(resource)).all().get(15, TimeUnit.SECONDS).get(resource);
        Map<String, String> settings = new LinkedHashMap<>();
        for (var entry : TOPIC_CONFIG.entrySet()) {
          ConfigEntry actual = config.get(entry.getKey());
          if (actual == null || !entry.getValue().equals(actual.value()))
            throw new IllegalStateException("topic_config_mismatch");
          settings.put(entry.getKey(), actual.value());
        }
        topics.put(
            name,
            Map.of(
                "id",
                topic.topicId().toString(),
                "partitions",
                1,
                "replicas",
                1,
                "config",
                settings));
      }
      Map<String, Object> result = new LinkedHashMap<>();
      result.put("cluster_id", admin.describeCluster().clusterId().get(15, TimeUnit.SECONDS));
      result.put("topics", topics);
      Map<TopicPartition, org.apache.kafka.clients.admin.OffsetSpec> request =
          new LinkedHashMap<>();
      for (String name : topicNames)
        request.put(
            new TopicPartition(name, 0), org.apache.kafka.clients.admin.OffsetSpec.latest());
      var offsets = admin.listOffsets(request).all().get(15, TimeUnit.SECONDS);
      Map<String, Long> ends = new LinkedHashMap<>();
      for (String name : topicNames) ends.put(name, offsets.get(new TopicPartition(name, 0)).offset());
      result.put("end_offsets", ends);
      if (group != null) {
        var committed =
            admin
                .listConsumerGroupOffsets(group)
                .partitionsToOffsetAndMetadata()
                .get(15, TimeUnit.SECONDS);
        var offset = committed.get(new TopicPartition(topicNames.get(0), 0));
        result.put("committed_input_offset", offset == null ? 0 : offset.offset());
      }
      return result;
    }
  }

  public static long groupOffset(String bootstrap, String group) throws Exception {
    return groupOffset(bootstrap, group, INPUT);
  }

  public static long groupOffset(String bootstrap, String group, String input) throws Exception {
    try (Admin admin = Admin.create(properties(bootstrap))) {
      var values =
          admin
              .listConsumerGroupOffsets(group)
              .partitionsToOffsetAndMetadata()
              .get(15, TimeUnit.SECONDS);
      var offset = values.get(new TopicPartition(input, 0));
      return offset == null ? 0 : offset.offset();
    }
  }

  @SuppressWarnings("unchecked")
  public static void verify(String bootstrap, String cluster, Map<String, String> ids)
      throws Exception {
    verify(bootstrap, cluster, ids, TOPICS);
  }

  @SuppressWarnings("unchecked")
  public static void verify(String bootstrap, String cluster, Map<String, String> ids,
      List<String> topicNames) throws Exception {
    Contracts.check(ids.keySet().equals(new java.util.HashSet<>(topicNames)), "topic_boundary_mismatch");
    Map<String, Object> current = describe(bootstrap, false, null, topicNames);
    if (!cluster.equals(current.get("cluster_id")))
      throw new IllegalStateException("cluster_changed");
    Map<String, Object> topics = (Map<String, Object>) current.get("topics");
    for (String name : topicNames)
      if (!ids.get(name).equals(((Map<String, Object>) topics.get(name)).get("id")))
        throw new IllegalStateException("topic_recreated");
  }
}
