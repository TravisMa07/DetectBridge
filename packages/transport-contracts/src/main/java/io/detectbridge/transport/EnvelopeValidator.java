package io.detectbridge.transport;

import com.networknt.schema.Schema;
import com.networknt.schema.SchemaLocation;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SpecificationVersion;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import tools.jackson.databind.JsonNode;

/** Closed schemas plus the raw-record semantics shared with the Python boundary. */
public final class EnvelopeValidator {
    private final Schema envelope;
    public EnvelopeValidator() {
        this(loadSchemas());
    }
    public EnvelopeValidator(Map<String, String> resources) {
        resources.forEach((id, text) -> checkRefs(Json.MAPPER.readTree(text), resources));
        SchemaRegistry registry = SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,
            builder -> builder.schemas(resources));
        envelope = registry.getSchema(SchemaLocation.of("urn:detectbridge:replay:1.0.0:envelope"));
    }
    private static Map<String,String> loadSchemas() {
        Map<String,String> schemas = new HashMap<>();
        for (String file : List.of("v1/common", "v1/raw-record", "v1/normalized-event", "v1/source-contract",
                "replay/v1/envelope", "replay/v1/capture", "replay/v1/checkpoint",
                "replay/v1/run-manifest", "replay/v1/segment", "replay/v1/timing-index")) {
            try (var stream = EnvelopeValidator.class.getResourceAsStream("/" + file + ".schema.json")) {
                if (stream == null) throw new IllegalStateException("missing_schema");
                String text = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
                String id = Json.MAPPER.readTree(text).get("$id").asString();
                if (schemas.put(id, text) != null) throw new IllegalStateException("duplicate_schema");
            } catch (Exception ex) { throw new IllegalStateException("schema_load_failure"); }
        }
        return schemas;
    }
    private static void checkRefs(JsonNode node, Map<String,String> schemas) {
        if (node.isObject()) {
            for (var entry : node.properties()) {
                if (entry.getKey().equals("$ref") || entry.getKey().equals("$dynamicRef")) {
                    String id = entry.getValue().asString().split("#", 2)[0];
                    if (!id.isEmpty() && !schemas.containsKey(id)) throw new IllegalArgumentException("nonlocal_schema");
                }
                checkRefs(entry.getValue(), schemas);
            }
        } else if (node.isArray()) for (JsonNode item : node) checkRefs(item, schemas);
    }
    public String validate(byte[] key, byte[] value) {
        if (value == null) return "null_value";
        if (value.length > Json.MAX_VALUE) return "value_limit";
        try {
            JsonNode node = Json.read(value);
            strictIntegers(node);
            if (!envelope.validate(node, context -> context.executionConfig(c -> c.formatAssertionsEnabled(true))).isEmpty())
                return "schema_invalid";
            if (key == null || !Arrays.equals(key, node.get("run_id").asString().getBytes(StandardCharsets.UTF_8)))
                return "key_run_mismatch";
            if (node.get("type").asString().equals("record")) raw(node.get("record"));
            return null;
        } catch (IllegalArgumentException ex) {
            // Only our fixed categories escape. Parser/validator messages can contain input.
            return "invalid_json_or_raw_semantics";
        } catch (Exception ex) { throw new IllegalStateException("validation_infrastructure_failure"); }
    }
    private static void strictIntegers(JsonNode node) {
        // All numeric fields in replay/raw envelopes are integers, not mathematical 1.0.
        if (node.isNumber() && !node.isIntegralNumber()) throw new IllegalArgumentException("noninteger");
        if (node.isObject()) for (var entry : node.properties()) {
            validUnicode(entry.getKey()); strictIntegers(entry.getValue());
        }
        if (node.isArray()) for (JsonNode item : node) strictIntegers(item);
        if (node.isString()) validUnicode(node.asString());
    }
    private static void validUnicode(String value) {
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (Character.isHighSurrogate(c)) {
                if (++i == value.length() || !Character.isLowSurrogate(value.charAt(i))) throw new IllegalArgumentException("unicode");
            } else if (Character.isLowSurrogate(c)) throw new IllegalArgumentException("unicode");
        }
    }
    public static String recordIdentity(JsonNode raw) {
        JsonNode source = raw.get("source"), cursor = raw.get("cursor");
        String kind = cursor.get("kind").asString();
        Object token = switch (kind) {
            case "dataset" -> List.of(kind, cursor.get("artifact_sha256").asString(), cursor.get("position").asString());
            case "native" -> List.of(kind, cursor.get("value").asString());
            case "capture" -> List.of(kind, cursor.get("id").asString());
            default -> throw new IllegalArgumentException("cursor");
        };
        return Json.identity(List.of(source.get("namespace").asString(), source.get("instance").asString(), token));
    }
    private static void raw(JsonNode raw) {
        if (!recordIdentity(raw).equals(raw.get("record_id").asString())) throw new IllegalArgumentException("identity");
        JsonNode evidence = raw.get("evidence");
        String sha = evidence.get("sha256").asString();
        if (evidence.has("inline")) {
            String inline = evidence.get("inline").asString();
            byte[] bytes;
            if (evidence.get("encoding").asString().equals("utf-8")) bytes = inline.getBytes(StandardCharsets.UTF_8);
            else {
                if (inline.length() % 4 != 0 || !inline.matches("[A-Za-z0-9+/]*={0,2}")) throw new IllegalArgumentException("base64");
                bytes = Base64.getDecoder().decode(inline);
            }
            if (!Json.sha(bytes).equals(sha)) throw new IllegalArgumentException("digest");
        } else {
            JsonNode ref = evidence.get("reference");
            String uriText = ref.get("uri").asString(), object = ref.get("object_sha256").asString();
            if (!ref.has("byte_range") && !sha.equals(object)) throw new IllegalArgumentException("whole_digest");
            URI uri = URI.create(uriText);
            if (uri.getRawUserInfo() != null || uri.getRawQuery() != null || uri.getRawFragment() != null
                || (uri.getRawAuthority() != null && uri.getRawAuthority().contains("@"))) throw new IllegalArgumentException("unsafe_uri");
            String scheme = uri.getScheme();
            if (!List.of("urn", "s3", "https", "file").contains(scheme)) throw new IllegalArgumentException("uri_scheme");
            if (scheme.equals("urn") && !uriText.equals("urn:sha256:" + object)) throw new IllegalArgumentException("content_address");
            if ((scheme.equals("s3") || scheme.equals("https")) && (uri.getHost() == null || uri.getHost().isEmpty())) throw new IllegalArgumentException("host");
        }
    }
}
