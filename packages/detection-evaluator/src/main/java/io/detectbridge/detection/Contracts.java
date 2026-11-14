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
    resources.forEach((id, text) -> checkRefs(Json.MAPPER.readTree(text), resources, id));
    registry =
        SchemaRegistry.withDefaultDialect(
            SpecificationVersion.DRAFT_2020_12, builder -> builder.schemas(resources));
  }

  private static void checkRefs(JsonNode node, Map<String, String> resources, String current) {
    if (node.isObject())
      for (var p : node.properties()) {
        if (p.getKey().equals("$ref") || p.getKey().equals("$dynamicRef")) {
          String[] ref = p.getValue().asString().split("#", 2);
          String id = ref[0].isEmpty() ? current : ref[0];
          check(resources.containsKey(id), "nonlocal_schema");
          if (ref.length == 2 && ref[1].startsWith("/"))
            check(
                !Json.MAPPER.readTree(resources.get(id)).at(ref[1]).isMissingNode(),
                "unknown_schema_fragment");
        }
        checkRefs(p.getValue(), resources, current);
      }
    else if (node.isArray()) for (var item : node) checkRefs(item, resources, current);
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
