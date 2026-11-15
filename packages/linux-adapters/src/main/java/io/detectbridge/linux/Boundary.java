package io.detectbridge.linux;

import static io.detectbridge.detection.Contracts.*;

import com.networknt.schema.*;
import io.detectbridge.detection.Contracts;
import io.detectbridge.detection.Normalized;
import io.detectbridge.transport.EnvelopeValidator;
import io.detectbridge.transport.Json;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Module-local implementation of the fixed adapter JSON boundary. No URI retrieval. */
public final class Boundary {
  public static final String VERSION = "1.0.0";
  private static final Contracts CONTRACTS = new Contracts();
  private static final Normalized NORMALIZED = new Normalized(CONTRACTS);
  private static final SchemaRegistry SCHEMAS = schemas();

  private Boundary() {}

  private static SchemaRegistry schemas() {
    Map<String, String> resources = new HashMap<>();
    for (String path : List.of("/v1/common.schema.json", "/v1/raw-record.schema.json",
        "/context.schema.json", "/manifest.schema.json", "/state.schema.json",
        "/preservation.schema.json", "/context-extension.schema.json")) {
      try (var in = Boundary.class.getResourceAsStream(path)) {
        String text = new String(Objects.requireNonNull(in).readAllBytes(), StandardCharsets.UTF_8);
        resources.put(Json.MAPPER.readTree(text).get("$id").asString(), text);
      } catch (Exception e) { throw new IllegalStateException("schema_load_failure"); }
    }
    return SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,
        b -> b.schemas(resources));
  }

  static void schema(String id, JsonNode value) {
    check(SCHEMAS.getSchema(SchemaLocation.of(id)).validate(value,
        c -> c.executionConfig(e -> e.formatAssertionsEnabled(true))).isEmpty(), "schema_invalid");
  }

  public static JsonNode resource(String name) {
    try (var in = Boundary.class.getResourceAsStream("/" + name + ".json")) {
      return Json.read(Objects.requireNonNull(in).readAllBytes());
    } catch (Exception e) { throw new IllegalStateException("resource_failure"); }
  }

  /** Resolver must verify full object hash/range and return exact record bytes. I/O propagates. */
  @FunctionalInterface
  public interface EvidenceResolver { byte[] resolve(JsonNode evidence) throws Exception; }

  public record Input(JsonNode raw, JsonNode context, byte[] bytes) {
    public Input {
      raw = raw.deepCopy(); context = context.deepCopy(); bytes = bytes.clone();
    }
    @Override public JsonNode raw() { return raw.deepCopy(); }
    @Override public JsonNode context() { return context.deepCopy(); }
    @Override public byte[] bytes() { return bytes.clone(); }
  }

  public static Input resolve(JsonNode raw, JsonNode context, EvidenceResolver resolver)
      throws Exception {
    validateContext(raw, context);
    byte[] bytes = resolver.resolve(raw.get("evidence").deepCopy());
    check(bytes != null && bytes.length > 0 && bytes.length <= Json.MAX_VALUE, "evidence_size");
    check(Json.sha(bytes).equals(raw.get("evidence").get("sha256").asString()), "record_digest");
    JsonNode evidence = raw.get("evidence");
    if (evidence.has("inline")) {
      byte[] expected = evidence.get("encoding").asString().equals("utf-8")
          ? evidence.get("inline").asString().getBytes(StandardCharsets.UTF_8)
          : Base64.getDecoder().decode(evidence.get("inline").asString());
      check(Arrays.equals(bytes, expected), "inline_evidence_mismatch");
    } else if (evidence.path("reference").has("byte_range")) {
      check(evidence.at("/reference/byte_range/length").asLong() == bytes.length, "record_range");
    }
    return new Input(raw, context, bytes);
  }

  static void validateContext(JsonNode raw, JsonNode ctx) {
    Normalized.unicode(raw); Normalized.unicode(ctx);
    check(Json.bytes(raw).length <= Json.MAX_VALUE && Json.bytes(ctx).length <= 65536, "boundary_size");
    strictIntegers(raw); strictIntegers(ctx);
    schema("urn:detectbridge:contracts:1.0.0:raw-record", raw);
    schema("urn:detectbridge:linux:1.0.0:context", ctx);
    check(raw.get("record_id").asString().equals(EnvelopeValidator.recordIdentity(raw)), "record_identity");
    check(raw.get("source").equals(ctx.get("source")), "source_context");
    check(raw.get("first_observed").equals(ctx.get("first_observed")), "observation_context");
    String first = raw.get("first_observed").asString();
    check(first.matches("[0-9]{4}-.*Z") && Integer.parseInt(first.substring(0, 4)) > 0
        && Integer.parseInt(first.substring(17, 19)) <= 59, "invalid_observation");
    java.time.LocalDateTime.parse(first.substring(0, 19));
    JsonNode evidence = raw.get("evidence");
    if (evidence.has("inline")) {
      String inline = evidence.get("inline").asString();
      byte[] original;
      if (evidence.get("encoding").asString().equals("utf-8")) original = inline.getBytes(StandardCharsets.UTF_8);
      else {
        check(inline.length() % 4 == 0 && inline.matches("[A-Za-z0-9+/]*={0,2}"), "invalid_base64");
        original = Base64.getDecoder().decode(inline);
      }
      check(Json.sha(original).equals(evidence.get("sha256").asString()), "inline_digest");
    } else {
      JsonNode ref = evidence.get("reference");
      String uriText = ref.get("uri").asString(), hash = ref.get("object_sha256").asString();
      java.net.URI uri = java.net.URI.create(uriText);
      check(uri.getRawUserInfo() == null && uri.getRawQuery() == null && uri.getRawFragment() == null
          && (uri.getRawAuthority() == null || !uri.getRawAuthority().contains("@")), "unsafe_reference");
      check(uri.getScheme() != null, "unsupported_reference");
      String scheme = uri.getScheme().toLowerCase(Locale.ROOT);
      check(Set.of("urn", "https", "s3", "file").contains(scheme), "unsupported_reference");
      if (scheme.equals("urn")) check(uriText.equals("urn:sha256:" + hash), "content_address");
      if (Set.of("https", "s3").contains(scheme)) check(uri.getHost() != null, "reference_host");
      check(ref.has("byte_range") || evidence.get("sha256").asString().equals(hash), "whole_object_digest");
    }
    String id = ctx.at("/source_contract/id").asString();
    check(Set.of("linux-audit-execution-p12a", "openssh-authentication-p12a").contains(id), "unsupported_contract");
    JsonNode source = resource(id + ".source"), profile = resource(id + ".mapping");
    check(ctx.at("/source_contract/snapshot").equals(source), "source_snapshot");
    check(ctx.at("/source_contract/sha256").asString().equals(hash(source)), "source_hash");
    JsonNode mapping = ctx.get("mapping_profile");
    check(mapping.get("declaration").equals(profile) && mapping.get("id").equals(profile.get("id"))
        && mapping.get("version").equals(profile.get("version"))
        && mapping.get("sha256").equals(profile.get("sha256")), "mapping_snapshot");
    if (ctx.has("host_binding")) {
      JsonNode host = ctx.get("host_binding");
      check(host.get("source").equals(raw.get("source")), "binding_source");
      ObjectNode unhashed = ((ObjectNode)host).deepCopy(); unhashed.remove("sha256");
      check(hash(unhashed).equals(host.get("sha256").asString()), "binding_hash");
    }
    check(ctx.at("/parser/id").asString().equals(id.startsWith("linux") ? "linux-audit" : "openssh-password"), "parser_binding");
    NORMALIZED.source(source);
  }

  static void strictIntegers(JsonNode node) {
    if (node.isNumber()) check(node.isIntegralNumber(), "integer_required");
    if (node.isContainer()) for (JsonNode child : node) strictIntegers(child);
  }

  static String hash(JsonNode node) { return Json.sha(Json.bytes(canonical(node))); }

  static JsonNode configuration(JsonNode ctx) {
    ObjectNode config = ((ObjectNode) ctx).deepCopy();
    config.remove(List.of("first_observed", "receipt"));
    return config;
  }

  static String text(byte[] bytes) {
    try {
      return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
    } catch (CharacterCodingException e) { throw new IllegalArgumentException("invalid_utf8"); }
  }

  static ObjectNode member(JsonNode raw) {
    ObjectNode n = Json.MAPPER.createObjectNode();
    n.set("record_id", raw.get("record_id")); n.set("evidence", raw.get("evidence"));
    return n;
  }

  /** Descriptor of an already retained raw occurrence; never invents an evidence locator. */
  static ObjectNode referenceMember(JsonNode raw, JsonNode context) {
    ObjectNode m = Json.MAPPER.createObjectNode(); JsonNode evidence = raw.get("evidence");
    m.set("record_id", raw.get("record_id")); m.set("evidence_sha256", evidence.get("sha256"));
    m.set("encoding", evidence.get("encoding")); m.set("media_type", evidence.get("media_type"));
    m.put("retention", evidence.has("inline") ? "raw_inline" : "raw_reference");
    if (evidence.has("reference")) m.set("reference", evidence.get("reference"));
    m.set("cursor", raw.get("cursor")); m.set("first_observed", raw.get("first_observed"));
    m.put("raw_sha256", hash(raw)); m.put("context_sha256", hash(context));
    if (Json.bytes(m).length <= 2048) return m;
    ObjectNode compact = Json.MAPPER.createObjectNode();
    compact.set("record_id", m.get("record_id")); compact.set("evidence_sha256", m.get("evidence_sha256"));
    compact.set("raw_sha256", m.get("raw_sha256")); compact.set("context_sha256", m.get("context_sha256")); compact.put("retention", "retained_raw"); return compact;
  }

  static ObjectNode diagnostic(Input input, String code) {
    ObjectNode out = Json.MAPPER.createObjectNode();
    out.put("version", VERSION); out.put("kind", "preservation"); out.put("code", code);
    out.set("run_id", input.context.get("run_id")); out.set("source", input.raw.get("source"));
    out.set("member", referenceMember(input.raw, input.context)); out.set("context", input.context);
    out.put("id", Json.identity(List.of(input.context.get("run_id").asString(),
        input.raw.get("record_id").asString(), code)));
    check(Json.bytes(out).length <= Json.MAX_VALUE, "diagnostic_limit_backlog");
    return out;
  }

  private static int compareUtc(String a, String b) {
    int seconds = a.substring(0, 19).compareTo(b.substring(0, 19));
    if (seconds != 0) return seconds;
    String af = a.length() == 20 ? "" : a.substring(20, a.length() - 1);
    String bf = b.length() == 20 ? "" : b.substring(20, b.length() - 1);
    int length = Math.max(af.length(), bf.length());
    return (af + "0".repeat(length - af.length())).compareTo(bf + "0".repeat(length - bf.length()));
  }

  static ObjectNode event(JsonNode ctx, List<JsonNode> raws, String occurrence, String timeQuality,
      String originalTime, String closure, boolean eligible, List<String> findings, JsonNode fields,
      Map<String, Object> extracted) {
    ObjectNode out = Json.MAPPER.createObjectNode();
    String first = raws.stream().map(r -> r.get("first_observed").asString())
        .min(Boundary::compareUtc).orElseThrow();
    out.put("@timestamp", occurrence == null ? first : occurrence);
    out.set("ecs", Json.MAPPER.valueToTree(Map.of("version", "9.5.0")));
    JsonNode source = ctx.at("/source_contract/snapshot");
    ObjectNode event = (ObjectNode) source.get("classification").deepCopy();
    List<String> ids = raws.stream().map(r -> r.get("record_id").asString()).sorted().toList();
    event.put("id", Json.identity(List.of(ctx.at("/source/namespace").asString(),
        ctx.at("/source/instance").asString(), ids)));
    event.put("created", first); event.put("code", closure.equals("not_required") ? "sshd" : "EXECVE");
    event.put("provider", closure.equals("not_required") ? "sshd" : "auditd");
    event.put("dataset", source.get("id").asString()); out.set("event", event);
    if (ctx.has("host_binding")) out.set("host", Json.MAPPER.valueToTree(Map.of("id", ctx.at("/host_binding/host_id").asString())));
    extracted.forEach((k, v) -> out.set(k, Json.MAPPER.valueToTree(v)));
    out.set("source_fields", fields);
    ObjectNode db = out.putObject("detectbridge"); db.put("contract_version", VERSION);
    db.set("source", ctx.get("source")); db.set("run_id", ctx.get("run_id"));
    db.set("source_contract", Json.MAPPER.valueToTree(Map.of("id", source.get("id").asString(), "version", VERSION)));
    db.set("processing", Json.MAPPER.valueToTree(Map.of("parser", ctx.at("/parser/id").asString() + "/" + VERSION,
        "mapping", ctx.at("/mapping_profile/id").asString() + "/" + VERSION, "normalizer", "linux-p12a/" + VERSION)));
    ObjectNode time = db.putObject("time"); time.put("basis", occurrence == null ? "first_observed" : "source");
    time.put("quality", timeQuality); time.put("first_observed", first);
    if (originalTime != null) time.put("source_value", originalTime);
    if (occurrence != null) time.put("source_utc", occurrence);
    db.set("assembly", Json.MAPPER.valueToTree(Map.of("mode", closure.equals("not_required") ? "standalone" : "assembled",
        "closure", closure, "quality", eligible ? "source_indicated"
            : findings.stream().anyMatch(f -> f.contains("conflict")) ? "conflicting" : "known_missing", "assembler_version", VERSION)));
    List<Object> diagnostics = new ArrayList<>();
    if (!eligible) diagnostics.add(Map.of("code", "assembly_insufficient", "field", ""));
    if (findings.stream().anyMatch(f -> f.startsWith("unsupported_")))
      diagnostics.add(Map.of("code", "unsupported_source", "field", ""));
    if (findings.stream().anyMatch(f -> f.contains("conflict")))
      diagnostics.add(Map.of("code", "conflicting", "field", ""));
    if (timeQuality.equals("missing")) diagnostics.add(Map.of("code", "timestamp_missing", "field", "/@timestamp"));
    db.set("quality", Json.MAPPER.valueToTree(Map.of("integrity", eligible ? "sufficient" : "insufficient",
        "eligibility", eligible ? "eligible" : "skipped", "diagnostics", diagnostics)));
    db.set("evidence", Json.MAPPER.valueToTree(raws.stream().map(Boundary::member).toList()));
    // Namespaced metadata is separately validated by manifest schema, never added to P03 core.
    db.putObject("extensions").set("linux.context", Json.MAPPER.valueToTree(Map.of(
        "version", VERSION, "source_sha256", ctx.at("/source_contract/sha256").asString(),
        "mapping_sha256", ctx.at("/mapping_profile/sha256").asString(), "findings", findings, "context", ctx)));
    schema("urn:detectbridge:linux:1.0.0:context-extension", db.at("/extensions/linux.context"));
    NORMALIZED.validate(out, source);
    return out;
  }
}
