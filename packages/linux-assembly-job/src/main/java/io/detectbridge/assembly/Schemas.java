package io.detectbridge.assembly;

import static io.detectbridge.detection.Contracts.check;
import com.networknt.schema.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import tools.jackson.databind.JsonNode;
import io.detectbridge.transport.Json;

final class Schemas {
  private static final SchemaRegistry REGISTRY = registry();
  private static SchemaRegistry registry() {
    Map<String,String> schemas = new HashMap<>();
    for (String path : List.of("v1/common.schema.json", "v1/raw-record.schema.json", "context.schema.json",
        "context-extension.schema.json", "manifest.schema.json", "preservation.schema.json", "state.schema.json",
        "assembly-registration.schema.json", "assembly-input.schema.json", "assembly-wire.schema.json", "assembly-state.schema.json",
        "assembly-receipt.schema.json", "assembly-quarantine.schema.json")) {
      try (var in = Schemas.class.getResourceAsStream("/"+path)) {
        String text = new String(Objects.requireNonNull(in).readAllBytes(), StandardCharsets.UTF_8);
        schemas.put(Json.MAPPER.readTree(text).get("$id").asString(),text);
      } catch(Exception e) { throw new IllegalStateException("assembly_schema_load"); }
    }
    return SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,b -> b.schemas(schemas));
  }
  static void require(String kind, JsonNode value) { validate("urn:detectbridge:assembly:1.0.0:"+kind,value); }
  static void linux(String kind, JsonNode value) { validate("urn:detectbridge:linux:1.0.0:"+kind,value); }
  private static void validate(String id, JsonNode value) {
    check(REGISTRY.getSchema(SchemaLocation.of(id)).validate(value,
        ctx -> ctx.executionConfig(c -> c.formatAssertionsEnabled(true))).isEmpty(),"assembly_schema_invalid");
  }
}
