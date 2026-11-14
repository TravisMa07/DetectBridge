package io.detectbridge.detection;

import com.networknt.schema.*;
import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Repository-local schemas; untrusted documents cannot supply schema resources. */
public final class Contracts {
  private final SchemaRegistry registry;

  public Contracts() {
    Map<String, String> resources = new HashMap<>();
    for (String path :
        List.of(
            "v1/common",
            "v1/normalized-event",
            "v1/source-contract",
            "detection/v1/plan",
            "detection/v1/result",
            "detection/v1/quarantine")) {
      try (var stream = Contracts.class.getResourceAsStream("/" + path + ".schema.json")) {
        String text =
            new String(Objects.requireNonNull(stream).readAllBytes(), StandardCharsets.UTF_8);
        resources.put(Json.MAPPER.readTree(text).get("$id").asString(), text);
      } catch (Exception ex) {
        throw new IllegalStateException("schema_load_failure");
      }
    }
    registry =
        SchemaRegistry.withDefaultDialect(
            SpecificationVersion.DRAFT_2020_12, builder -> builder.schemas(resources));
  }

  public void require(String domain, String kind, JsonNode node) {
    String id = "urn:detectbridge:" + domain + ":1.0.0:" + kind;
    if (!registry
        .getSchema(SchemaLocation.of(id))
        .validate(node, c -> c.executionConfig(e -> e.formatAssertionsEnabled(true)))
        .isEmpty()) throw new IllegalArgumentException("schema_invalid");
  }

  public static Object canonical(JsonNode node) {
    if (node.isObject()) {
      Map<String, Object> result = new TreeMap<>();
      for (var p : node.properties()) result.put(p.getKey(), canonical(p.getValue()));
      return result;
    }
    if (node.isArray()) {
      List<Object> result = new ArrayList<>();
      for (var value : node) result.add(canonical(value));
      return result;
    }
    if (node.isString()) return node.asString();
    if (node.isBoolean()) return node.asBoolean();
    if (node.isIntegralNumber()) return node.bigIntegerValue();
    if (node.isNull()) return null;
    throw new IllegalArgumentException("unsupported_number");
  }

  public static JsonNode field(JsonNode node, String dotted) {
    for (String part : dotted.split("\\.")) node = node.path(part);
    return node;
  }

  public static void check(boolean condition, String category) {
    if (!condition) throw new IllegalArgumentException(category);
  }
}
