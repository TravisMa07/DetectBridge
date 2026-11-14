package io.detectbridge.writer;

import com.networknt.schema.*;
import io.detectbridge.transport.EnvelopeValidator;
import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Pure metadata projection. No evidence retrieval or payload copies. */
public final class Projection {
  public static final String OUTPUT = "detectbridge.replay.output.v1";
  public static final String QUARANTINE = "detectbridge.replay.quarantine.v1";
  public static final String FAILURES = "detectbridge.opensearch.writer-failures.v1";
  public static final String REPLAY = "detectbridge-replay-v1";
  public static final String DIAGNOSTICS = "detectbridge-diagnostics-v1";
  public static final List<String> TOPICS = List.of(OUTPUT, QUARANTINE, FAILURES);
  private final EnvelopeValidator envelopes = new EnvelopeValidator();
  private final Map<String, Schema> schemas = new HashMap<>();
  private final JsonNode config;

  public record Location(
      String cluster_id, String topic_id, String topic, int partition, long offset) {}

  public record Document(String index, String id, Map<String, Object> body) {}

  public static final class Invalid extends RuntimeException {
    public final String category;

    public Invalid(String category) {
      super(category);
      this.category = category;
    }
  }

  public Projection(JsonNode config) {
    this.config = config;
    for (String name :
        List.of(
            "transport/v1/quarantine",
            "writer/v1/failure",
            "writer/v1/projection",
            "writer/v1/configuration")) {
      try (var in = Projection.class.getResourceAsStream("/" + name + ".schema.json")) {
        String text = new String(Objects.requireNonNull(in).readAllBytes(), StandardCharsets.UTF_8);
        // All writer schemas are self-contained. No network resolver is installed.
        JsonNode schema = Json.MAPPER.readTree(text);
        rejectRefs(schema);
        var registry =
            SchemaRegistry.withDefaultDialect(
                SpecificationVersion.DRAFT_2020_12,
                builder -> builder.schemas(Map.of(schema.get("$id").asString(), text)));
        schemas.put(
            name.substring(name.lastIndexOf('/') + 1),
            registry.getSchema(SchemaLocation.of(schema.get("$id").asString())));
      } catch (Exception ex) {
        throw new IllegalStateException("schema_load_failure");
      }
    }
  }

  private static void rejectRefs(JsonNode node) {
    if (node.isObject())
      for (var item : node.properties()) {
        if (item.getKey().equals("$ref") || item.getKey().equals("$dynamicRef"))
          throw new IllegalArgumentException("nonlocal_schema");
        rejectRefs(item.getValue());
      }
    if (node.isArray()) for (var child : node) rejectRefs(child);
  }

  public void require(String kind, JsonNode value) {
    if (!schemas
        .get(kind)
        .validate(value, c -> c.executionConfig(e -> e.formatAssertionsEnabled(true)))
        .isEmpty()) throw new Invalid("schema_invalid");
  }

  public static Object canonical(JsonNode value) {
    if (value.isObject()) {
      Map<String, Object> result = new TreeMap<>();
      for (var item : value.properties()) result.put(item.getKey(), canonical(item.getValue()));
      return result;
    }
    if (value.isArray()) {
      List<Object> out = new ArrayList<>();
      for (var item : value) out.add(canonical(item));
      return out;
    }
    if (value.isNull()) return null;
    if (value.isString()) return value.asString();
    if (value.isBoolean()) return value.asBoolean();
    if (value.isIntegralNumber()) return value.bigIntegerValue();
    throw new IllegalArgumentException("noninteger_projection");
  }

  public static String hash(Object object) {
    return Json.sha(Json.bytes(canonical(Json.MAPPER.valueToTree(object))));
  }

  public static String contentHash(JsonNode body) {
    var copy = body.deepCopy();
    ((tools.jackson.databind.node.ObjectNode) copy)
        .remove(List.of("content_sha256", "first_input"));
    return hash(copy);
  }

  public Document project(String topic, byte[] key, byte[] value, Location location) {
    JsonNode node;
    try {
      node = Json.read(value);
    } catch (IllegalArgumentException ex) {
      throw new Invalid("invalid_json");
    }
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("contract_version", "1.0.0");
    body.put("pipeline_id", config.get("pipeline_id").asString());
    body.put("input_sha256", Json.sha(value));
    String id, index;
    if (topic.equals(OUTPUT)) {
      if (envelopes.validate(key, value) != null) throw new Invalid("invalid_envelope");
      index = REPLAY;
      id =
          Json.identity(
              List.of(
                  "1.0.0",
                  config.get("pipeline_id").asString(),
                  node.get("run_id").asString(),
                  node.get("sequence").asString()));
      body.put("kind", node.get("type").asString());
      body.put("run_id", node.get("run_id").asString());
      body.put("sequence", node.get("sequence").bigIntegerValue());
      if (node.has("dataset_id")) body.put("dataset_id", node.get("dataset_id").asString());
      if (node.get("type").asString().equals("record")) {
        var raw = node.get("record");
        body.put("record_id", raw.get("record_id").asString());
        body.put("source", canonical(raw.get("source")));
        body.put("cursor", canonical(raw.get("cursor")));
        body.put("first_observed", raw.get("first_observed").asString());
        Map<String, Object> evidence = new TreeMap<>();
        for (String f : List.of("sha256", "encoding", "media_type", "reference"))
          if (raw.get("evidence").has(f)) evidence.put(f, canonical(raw.get("evidence").get(f)));
        evidence.put("inline_present", raw.get("evidence").has("inline"));
        body.put("evidence", evidence);
        body.put("timing", canonical(node.get("timing")));
        try {
          Instant instant = Instant.parse(node.get("timing").get("effective_time").asString());
          long nanos =
              Math.addExact(
                  Math.multiplyExact(instant.getEpochSecond(), 1_000_000_000L), instant.getNano());
          if (nanos < 0) throw new ArithmeticException();
          body.put("effective_time", node.get("timing").get("effective_time").asString());
        } catch (ArithmeticException ex) {
          body.put("time_projection_reason", "outside_nanos_range");
        }
      } else {
        body.put("record_count", node.get("record_count").bigIntegerValue());
        if (node.has("dataset_count"))
          body.put("dataset_count", node.get("dataset_count").bigIntegerValue());
      }
    } else {
      index = DIAGNOSTICS;
      String kind = topic.equals(QUARANTINE) ? "relay_quarantine" : "writer_failure";
      require(topic.equals(QUARANTINE) ? "quarantine" : "failure", node);
      id = node.get(topic.equals(QUARANTINE) ? "quarantine_id" : "failure_id").asString();
      String referenceTopic = node.get("input").get("topic").asString();
      var ref = config.get("source_topics").get(referenceTopic);
      if (ref == null
          || !ref.get("id").asString().equals(node.get("input").get("topic_id").asString())
          || !node.get("input")
              .get("cluster_id")
              .asString()
              .equals(config.get("kafka_cluster_id").asString()))
        throw new Invalid("source_reference_mismatch");
      String expected =
          topic.equals(QUARANTINE)
              ? Json.identity(
                  List.of(
                      node.get("input").get("cluster_id").asString(),
                      node.get("input").get("topic_id").asString(),
                      node.get("input").get("partition").asString(),
                      node.get("input").get("offset").asString()))
              : failureId(node.get("input"));
      if (!id.equals(expected)
          || key == null
          || !Arrays.equals(key, id.getBytes(StandardCharsets.UTF_8)))
        throw new Invalid("diagnostic_identity_mismatch");
      body.put("kind", kind);
      body.put("diagnostic", canonical(node));
      body.put("reason", node.get("diagnostic").get("category").asString());
      body.put("input_topic", referenceTopic);
      body.put("input_offset", node.get("input").get("offset").bigIntegerValue());
    }
    body.put("first_input", location);
    body.put("content_sha256", hash(bodyWithoutLocation(body)));
    require("projection", Json.MAPPER.valueToTree(body));
    return new Document(index, id, body);
  }

  private static Map<String, Object> bodyWithoutLocation(Map<String, Object> body) {
    var out = new TreeMap<>(body);
    out.remove("first_input");
    return out;
  }

  public static String failureId(JsonNode location) {
    return Json.identity(
        List.of(
            "writer:1.0.0",
            location.get("cluster_id").asString(),
            location.get("topic_id").asString(),
            location.get("partition").asString(),
            location.get("offset").asString()));
  }

  public Map<String, Object> failure(Location location, byte[] value, String reason) {
    Map<String, Object> result = new LinkedHashMap<>();
    result.put("contract_version", "1.0.0");
    result.put("failure_id", failureId(Json.MAPPER.valueToTree(location)));
    result.put("input", location);
    result.put("value_is_null", value == null);
    result.put("value_size", value == null ? 0 : value.length);
    result.put("value_sha256", Json.sha(value == null ? new byte[0] : value));
    result.put("diagnostic", Map.of("category", reason, "pointer", ""));
    require("failure", Json.MAPPER.valueToTree(result));
    return result;
  }
}
