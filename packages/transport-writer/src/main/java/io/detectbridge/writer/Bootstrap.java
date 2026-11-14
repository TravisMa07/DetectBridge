package io.detectbridge.writer;

import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.config.ConfigResource;
import tools.jackson.databind.JsonNode;

/** Explicit, rerunnable administration; runtime has none of these credentials. */
public final class Bootstrap {
  public static Map<String, Object> field(String type) {
    return Map.of("type", type);
  }

  public static Map<String, Object> properties() {
    Map<String, Object> fields = new TreeMap<>();
    for (String name :
        List.of(
            "contract_version",
            "pipeline_id",
            "input_sha256",
            "content_sha256",
            "kind",
            "run_id",
            "dataset_id",
            "record_id",
            "time_projection_reason",
            "reason",
            "input_topic")) fields.put(name, field("keyword"));
    for (String name : List.of("sequence", "record_count", "dataset_count", "input_offset"))
      fields.put(name, field("long"));
    fields.put("first_observed", Map.of("type", "keyword", "index", false, "doc_values", false));
    fields.put(
        "effective_time",
        Map.of("type", "date_nanos", "format", "strict_date_optional_time_nanos"));
    fields.put(
        "source",
        Map.of(
            "type",
            "object",
            "dynamic",
            "strict",
            "properties",
            Map.of("namespace", field("keyword"), "instance", field("keyword"))));
    fields.put(
        "evidence",
        Map.of(
            "type",
            "object",
            "dynamic",
            "strict",
            "properties",
            Map.of(
                "sha256",
                field("keyword"),
                "encoding",
                field("keyword"),
                "media_type",
                field("keyword"),
                "inline_present",
                field("boolean"),
                "reference",
                Map.of("type", "object", "enabled", false))));
    for (String name : List.of("cursor", "timing", "diagnostic"))
      fields.put(name, Map.of("type", "object", "enabled", false));
    fields.put(
        "first_input",
        Map.of(
            "type",
            "object",
            "dynamic",
            "strict",
            "properties",
            Map.of(
                "cluster_id",
                field("keyword"),
                "topic_id",
                field("keyword"),
                "topic",
                field("keyword"),
                "partition",
                field("integer"),
                "offset",
                field("long"))));
    return fields;
  }

  public static Map<String, Object> template(String index) {
    return Map.of(
        "index_patterns",
        List.of(index),
        "priority",
        100,
        "version",
        1,
        "composed_of",
        List.of(),
        "_meta",
        Map.of("detectbridge", "writer:1.0.0"),
        "template",
        Map.of(
            "settings",
            Map.of(
                "index",
                Map.of(
                    "number_of_shards",
                    "1",
                    "number_of_replicas",
                    "0",
                    "refresh_interval",
                    "1s",
                    "translog",
                    Map.of("durability", "request"),
                    "default_pipeline",
                    "_none",
                    "final_pipeline",
                    "_none")),
            "mappings",
            Map.of(
                "dynamic",
                "strict",
                "_meta",
                Map.of("detectbridge", "writer:1.0.0"),
                "properties",
                properties())));
  }

  public static Map<String, Object> aliases() {
    return Map.of(
        "actions",
        List.of(
            Map.of(
                "add",
                Map.of(
                    "index",
                    Projection.REPLAY,
                    "alias",
                    "detectbridge-records-v1",
                    "filter",
                    Map.of("term", Map.of("kind", "record")))),
            Map.of(
                "add",
                Map.of(
                    "index",
                    Projection.REPLAY,
                    "alias",
                    "detectbridge-controls-v1",
                    "filter",
                    Map.of("terms", Map.of("kind", List.of("dataset_end", "run_end")))))));
  }

  static Map<String, Object> kafka(JsonNode pending, boolean initialize) throws Exception {
    String cluster = pending.get("kafka_cluster_id").asString();
    Map<String, Object> topics = new TreeMap<>();
    try (Admin admin = Admin.create(Broker.properties("kafka:9092"))) {
      if (!cluster.equals(admin.describeCluster().clusterId().get(15, TimeUnit.SECONDS)))
        throw new IllegalStateException("kafka_cluster_changed");
      if (initialize
          && !admin.listTopics().names().get(15, TimeUnit.SECONDS).contains(Projection.FAILURES))
        admin
            .createTopics(
                List.of(
                    new NewTopic(Projection.FAILURES, 1, (short) 1).configs(Broker.TOPIC_CONFIG)))
            .all()
            .get(15, TimeUnit.SECONDS);
      List<String> names = new ArrayList<>(Projection.TOPICS);
      names.add(Broker.INPUT);
      var described = admin.describeTopics(names).allTopicNames().get(15, TimeUnit.SECONDS);
      for (String name : names) {
        var t = described.get(name);
        if (t.partitions().size() != 1 || t.partitions().get(0).replicas().size() != 1)
          throw new IllegalStateException("topic_topology_changed");
        var resource = new ConfigResource(ConfigResource.Type.TOPIC, name);
        var config =
            admin.describeConfigs(List.of(resource)).all().get(15, TimeUnit.SECONDS).get(resource);
        for (var item : Broker.TOPIC_CONFIG.entrySet())
          if (!item.getValue().equals(config.get(item.getKey()).value()))
            throw new IllegalStateException("topic_policy_changed");
        var old = pending.get("source_topics").get(name);
        if (old != null && !old.get("id").asString().equals(t.topicId().toString()))
          throw new IllegalStateException("topic_recreated");
        topics.put(name, Map.of("id", t.topicId().toString()));
      }
      if (initialize) {
        String group = pending.get("consumer_group").asString();
        try {
          var members =
              admin
                  .describeConsumerGroups(List.of(group))
                  .all()
                  .get(15, TimeUnit.SECONDS)
                  .get(group)
                  .members();
          if (!members.isEmpty()) throw new IllegalStateException("writer_group_active");
        } catch (java.util.concurrent.ExecutionException ex) {
          if (!(ex.getCause() instanceof org.apache.kafka.common.errors.GroupIdNotFoundException))
            throw ex;
        }
        var existing =
            admin
                .listConsumerGroupOffsets(group)
                .partitionsToOffsetAndMetadata()
                .get(15, TimeUnit.SECONDS);
        Map<TopicPartition, OffsetSpec> request = new HashMap<>();
        for (String name : Projection.TOPICS)
          request.put(new TopicPartition(name, 0), OffsetSpec.earliest());
        var offsets = admin.listOffsets(request).all().get(15, TimeUnit.SECONDS);
        Map<TopicPartition, OffsetAndMetadata> initial = new HashMap<>();
        for (var part : request.keySet())
          if (!existing.containsKey(part))
            initial.put(part, new OffsetAndMetadata(offsets.get(part).offset()));
        if (!initial.isEmpty() && !existing.isEmpty())
          throw new IllegalStateException("partial_group_offsets_require_review");
        if (!initial.isEmpty())
          admin.alterConsumerGroupOffsets(group, initial).all().get(15, TimeUnit.SECONDS);
      }
    }
    return topics;
  }

  private static Set<String> strings(JsonNode values) {
    Set<String> result = new TreeSet<>();
    if (values == null || !values.isArray()) return result;
    for (var value : values) result.add(value.asString());
    return result;
  }

  static boolean roleMatches(JsonNode found, Map<String, Object> expected) {
    var desired = Json.MAPPER.valueToTree(expected);
    if (!strings(found.path("cluster_permissions"))
            .equals(strings(desired.get("cluster_permissions")))
        || found.path("tenant_permissions").size() != 0) return false;
    var actual = found.path("index_permissions");
    if (actual.size() != 1) return false;
    var permission = actual.get(0);
    var wanted = desired.get("index_permissions").get(0);
    if (!strings(permission.path("index_patterns")).equals(strings(wanted.get("index_patterns")))
        || !strings(permission.path("allowed_actions"))
            .equals(strings(wanted.get("allowed_actions")))) return false;
    return permission.path("dls").asString("").isEmpty()
        && permission.path("fls").size() == 0
        && permission.path("masked_fields").size() == 0;
  }

  static Object normalizedMapping(JsonNode value) {
    if (value.isObject()) {
      Map<String, Object> out = new TreeMap<>();
      for (var item : value.properties()) {
        if (item.getKey().equals("type") && item.getValue().asString("").equals("object")) continue;
        out.put(item.getKey(), normalizedMapping(item.getValue()));
      }
      return out;
    }
    if (value.isArray()) {
      List<Object> out = new ArrayList<>();
      for (var item : value) out.add(normalizedMapping(item));
      return out;
    }
    return Projection.canonical(value);
  }

  public static Map<String, Object> provision(JsonNode pending, Path directory) throws Exception {
    boolean audit = pending.has("indices");
    var sourceTopics = kafka(pending, !audit);
    try (var admin =
        new SearchClient(
            java.net.URI.create("https://opensearch:9200"),
            SearchClient.tls(
                directory.resolve("ca.pem"),
                directory.resolve("admin.p12"),
                directory.resolve("keystore-password")),
            null,
            20)) {
      if (audit) admin.verify(pending);
      String role = "detectbridge_writer_v1";
      Map<String, Object> expectedRole =
          Map.of(
              "cluster_permissions",
              List.of("cluster:monitor/main", "indices:data/write/bulk"),
              "index_permissions",
              List.of(
                  Map.of(
                      "index_patterns",
                      List.of(Projection.REPLAY, Projection.DIAGNOSTICS),
                      "allowed_actions",
                      List.of(
                          "indices:data/write/bulk*",
                          "indices:data/write/index*",
                          "indices:data/read/get*",
                          "indices:admin/get",
                          "indices:admin/mappings/get"))),
              "tenant_permissions",
              List.of());
      var current = admin.request("GET", "/_plugins/_security/api/roles/" + role, null);
      if (current.status() != 404 && current.status() != 200)
        throw new IllegalStateException("security_read_failed");
      if (current.status() == 200) {
        var found = current.body().get(role);
        if (!roleMatches(found, expectedRole)) throw new IllegalStateException("writer_role_drift");
      } else {
        if (audit) throw new IllegalStateException("writer_role_missing");
        admin.json("PUT", "/_plugins/_security/api/roles/" + role, expectedRole);
      }
      var user = admin.request("GET", "/_plugins/_security/api/internalusers/" + role, null);
      if (user.status() == 404 && audit) throw new IllegalStateException("writer_user_missing");
      if (user.status() == 404)
        admin.json(
            "PUT",
            "/_plugins/_security/api/internalusers/" + role,
            Map.of(
                "password",
                Files.readString(directory.resolve("writer-password")).strip(),
                "backend_roles",
                List.of(role)));
      else if (user.status() != 200
          || !Projection.hash(user.body().path(role).path("backend_roles"))
              .equals(Projection.hash(List.of(role)))
          || user.body().path(role).path("opendistro_security_roles").size() != 0)
        throw new IllegalStateException("writer_user_drift");
      var mapping = admin.request("GET", "/_plugins/_security/api/rolesmapping/" + role, null);
      if (mapping.status() == 404 && audit)
        throw new IllegalStateException("writer_mapping_missing");
      if (mapping.status() == 404)
        admin.json(
            "PUT",
            "/_plugins/_security/api/rolesmapping/" + role,
            Map.of("backend_roles", List.of(role), "users", List.of(), "hosts", List.of()));
      else if (mapping.status() != 200
          || !Projection.hash(mapping.body().path(role).path("backend_roles"))
              .equals(Projection.hash(List.of(role)))
          || mapping.body().path(role).path("users").size() != 0
          || mapping.body().path(role).path("hosts").size() != 0
          || mapping.body().path(role).path("and_backend_roles").size() != 0)
        throw new IllegalStateException("writer_role_mapping_drift");
      for (String index : List.of(Projection.REPLAY, Projection.DIAGNOSTICS)) {
        String name = "/_index_template/" + index;
        var old = admin.request("GET", name, null);
        var expected = template(index);
        if (old.status() == 404 && audit) throw new IllegalStateException("template_missing");
        if (old.status() == 404) admin.json("PUT", name, expected);
        else if (old.status() == 200) {
          var value = old.body().path("index_templates").get(0).get("index_template");
          Set<String> keys = new TreeSet<>();
          for (var field : value.properties()) keys.add(field.getKey());
          if (!keys.equals(expected.keySet())) throw new IllegalStateException("template_drift");
          for (String key : expected.keySet())
            if (!Projection.hash(normalizedMapping(value.path(key)))
                .equals(
                    Projection.hash(normalizedMapping(Json.MAPPER.valueToTree(expected.get(key))))))
              throw new IllegalStateException("template_drift");
        } else throw new IllegalStateException("template_read_failed");
        var existing = admin.request("GET", "/" + index, null);
        if (existing.status() == 404 && audit) throw new IllegalStateException("index_missing");
        if (existing.status() == 404) admin.json("PUT", "/" + index, Map.of());
        else if (existing.status() != 200) throw new IllegalStateException("index_read_failed");
      }
      // Aliases are administrative convenience views. Refuse conflicting existing definitions.
      for (String alias : List.of("detectbridge-records-v1", "detectbridge-controls-v1")) {
        var old = admin.request("GET", "/_alias/" + alias, null);
        if (old.status() == 200) {
          var expected =
              Json.MAPPER
                  .valueToTree(aliases())
                  .get("actions")
                  .get(alias.contains("records") ? 0 : 1)
                  .get("add")
                  .get("filter");
          var aliasValue = old.body().path(Projection.REPLAY).path("aliases").path(alias);
          for (var field : aliasValue.properties())
            if (!Set.of("filter", "is_hidden", "is_write_index").contains(field.getKey()))
              throw new IllegalStateException("alias_drift");
          if (aliasValue.path("is_hidden").asBoolean(false)
              || aliasValue.path("is_write_index").asBoolean(false))
            throw new IllegalStateException("alias_drift");
          if (old.body().size() != 1
              || !Projection.hash(
                      old.body().path(Projection.REPLAY).path("aliases").path(alias).path("filter"))
                  .equals(Projection.hash(expected)))
            throw new IllegalStateException("alias_drift");
        } else if (old.status() != 404 || audit)
          throw new IllegalStateException("alias_read_failed");
      }
      if (!audit) admin.json("POST", "/_aliases", aliases());
      Map<String, Object> indices = new TreeMap<>();
      var prints = admin.fingerprints();
      for (String name : prints.keySet()) {
        var value = admin.json("GET", "/" + name, null).get(name);
        if (!Projection.hash(normalizedMapping(value.get("mappings")))
            .equals(
                Projection.hash(
                    normalizedMapping(
                        Json.MAPPER.valueToTree(
                            ((Map<?, ?>) template(name).get("template")).get("mappings"))))))
          throw new IllegalStateException("index_mapping_drift");
        var settings = SearchClient.managedSettings(value);
        for (var desired :
            Map.of(
                    "number_of_shards",
                    "1",
                    "number_of_replicas",
                    "0",
                    "refresh_interval",
                    "1s",
                    "translog_durability",
                    "request",
                    "default_pipeline",
                    "_none",
                    "final_pipeline",
                    "_none")
                .entrySet())
          if (!desired.getValue().equals(settings.get(desired.getKey())))
            throw new IllegalStateException("index_settings_drift");
        indices.put(
            name,
            Map.of(
                "uuid",
                value.get("settings").get("index").get("uuid").asString(),
                "fingerprint",
                prints.get(name)));
      }
      Map<String, Object> result = new TreeMap<>();
      for (var item : pending.properties())
        result.put(item.getKey(), Projection.canonical(item.getValue()));
      result.put("source_topics", sourceTopics);
      result.put("indices", indices);
      result.put(
          "opensearch_cluster_id", admin.json("GET", "/", null).get("cluster_uuid").asString());
      result.put(
          "template_sha256",
          Projection.hash(
              List.of(template(Projection.REPLAY), template(Projection.DIAGNOSTICS), aliases())));
      return result;
    }
  }
}
