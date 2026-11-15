package io.detectbridge.windows;

import static io.detectbridge.detection.Contracts.*;

import io.detectbridge.detection.Contracts;
import io.detectbridge.detection.Normalized;
import io.detectbridge.transport.Json;
import java.io.IOException;
import java.math.BigInteger;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.ResolverStyle;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Stateless pure normalization over retained bytes and explicit reviewed context. */
public final class WindowsAdapter {
  private final Boundary boundary = new Boundary();
  private final Normalized normalized = new Normalized(new Contracts());
  public record Result(JsonNode event, JsonNode diagnostic) {
    public boolean preserved() { return diagnostic != null; }
  }
  private static Result failure(JsonNode raw, JsonNode context, String code, String reason) {
    return new Result(null, Json.MAPPER.valueToTree(Map.of(
        "version", "1.0.0", "record_id", raw.get("record_id"), "run_id", context.get("run_id"),
        "evidence_sha256", raw.get("evidence").get("sha256"), "code", code, "reason", reason, "field", "")));
  }
  public Result adapt(JsonNode raw, EvidenceResolver resolver, JsonNode context) throws IOException {
    boundary.raw(raw);
    String family = boundary.context(raw, context);
    byte[] bytes;
    try {
      bytes = resolver.resolve(raw);
      if (bytes == null || !Json.sha(bytes).equals(raw.get("evidence").get("sha256").asString())) throw new EvidenceResolver.IntegrityFailure();
    } catch (EvidenceResolver.IntegrityFailure ex) { return failure(raw, context, "extraction_failed", "evidence_integrity"); }
    if (!raw.get("evidence").get("encoding").asString().equals("utf-8")) return failure(raw, context, "unsupported_source", "unsupported_encoding");
    WindowsXml xml;
    try { xml = WindowsXml.parse(bytes); }
    catch (Exception ex) { return failure(raw, context, "extraction_failed", "xml_or_limit"); }
    boolean security = family.equals("security");
    String provider = xml.attributes.getOrDefault("Provider", Map.of()).get("Name");
    if (!(security ? "Microsoft-Windows-Security-Auditing" : "Microsoft-Windows-Sysmon").equals(provider)
        || !(security ? "4688" : "1").equals(xml.system.get("EventID"))
        || !(security ? "2" : "5").equals(xml.system.get("Version"))
        || !(security ? "Security" : "Microsoft-Windows-Sysmon/Operational").equals(xml.system.get("Channel")))
      return failure(raw, context, "unsupported_source", "source_signature");
    if (xml.data.containsKey("windows_system")) return failure(raw, context, "extraction_failed", "reserved_field");
    return normalize(raw, context, xml, security);
  }
  private static void diagnostic(List<Map<String, String>> ds, String code, String field) {
    var d = Map.of("code", code, "field", field);
    if (!ds.contains(d)) ds.add(d);
  }
  private static String value(Map<String, String> fields, String key) {
    String v = fields.get(key); return v == null || v.isEmpty() ? null : v;
  }
  private static void string(Map<String, Object> target, String key, String v) { if (v != null) target.put(key, v); }
  private static void pid(Map<String, Object> target, String key, String v, boolean hex,
                          List<Map<String, String>> ds, String field) {
    if (v == null) return;
    try {
      check(v.matches(hex ? "0[xX][0-9a-fA-F]+" : "[0-9]+"), "pid");
      BigInteger n = new BigInteger(hex ? v.substring(2) : v, hex ? 16 : 10);
      check(n.signum() >= 0 && n.compareTo(BigInteger.valueOf(Long.MAX_VALUE)) <= 0, "pid");
      target.put(key, n.longValueExact());
    } catch (IllegalArgumentException | ArithmeticException ex) { diagnostic(ds, "extraction_failed", field); }
  }
  private static final DateTimeFormatter CALENDAR = DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss").withResolverStyle(ResolverStyle.STRICT);
  /** Validate arbitrary fractional precision without converting/rounding it to nanoseconds. */
  static boolean utc(String v) {
    if (!v.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]+)?Z") || v.startsWith("0000")) return false;
    try { LocalDateTime.parse(v.substring(0, 19), CALENDAR); return true; }
    catch (java.time.DateTimeException ex) { return false; }
  }
  private Result normalize(JsonNode raw, JsonNode c, WindowsXml xml, boolean security) {
    var fields = xml.data;
    List<Map<String, String>> ds = new ArrayList<>();
    Map<String, Object> process = new LinkedHashMap<>(), parent = new LinkedHashMap<>(), user = new LinkedHashMap<>(), host = new LinkedHashMap<>();
    String image = value(fields, security ? "NewProcessName" : "Image");
    if (image == null) diagnostic(ds, "extraction_failed", "/process/executable");
    string(process, "executable", image);
    pid(process, "pid", value(fields, security ? "NewProcessId" : "ProcessId"), security, ds, "/process/pid");
    pid(parent, "pid", value(fields, security ? "ProcessId" : "ParentProcessId"), security, ds, "/process/parent/pid");
    String command = value(fields, "CommandLine");
    boolean disabled = c.path("source_generation").path("command_line_capture").asString().equals("disabled");
    if (command == null) diagnostic(ds, disabled ? "capture_unavailable" : "legitimately_absent", "/process/command_line");
    else {
      string(process, "command_line", command);
      if (disabled) diagnostic(ds, "conflicting", "/process/command_line");
    }
    if (security) {
      string(user, "name", value(fields, "SubjectUserName"));
      string(user, "domain", value(fields, "SubjectDomainName"));
      string(user, "id", value(fields, "SubjectUserSid"));
    } else {
      String account = value(fields, "User");
      if (account != null) {
        int slash = account.indexOf('\\');
        if (slash < 0) string(user, "name", account);
        else if (slash == 0 || slash == account.length() - 1 || slash != account.lastIndexOf('\\')) diagnostic(ds, "extraction_failed", "/user/name");
        else { user.put("domain", account.substring(0, slash)); user.put("name", account.substring(slash + 1)); }
      }
      string(process, "working_directory", value(fields, "CurrentDirectory"));
      string(parent, "executable", value(fields, "ParentImage"));
      string(parent, "command_line", value(fields, "ParentCommandLine"));
      guid(process, value(fields, "ProcessGuid"), ds, "/process/entity_id");
      guid(parent, value(fields, "ParentProcessGuid"), ds, "/process/parent/entity_id");
    }
    if (!parent.isEmpty()) process.put("parent", parent);
    String computer = value(xml.system, "Computer");
    string(host, "name", computer);
    if (c.has("host_binding") && Objects.equals(computer, c.get("host_binding").get("computer").asString())) host.put("id", c.get("host_binding").get("host_id").asString());
    else diagnostic(ds, "identity_missing", "/host/id");
    String original = security ? xml.attributes.getOrDefault("TimeCreated", Map.of()).get("SystemTime") : value(fields, "UtcTime");
    String interpreted = original;
    if (!security && original != null && original.matches("[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]+)?")) interpreted = original.replace(' ', 'T') + "Z";
    Map<String, Object> time = new LinkedHashMap<>();
    time.put("first_observed", raw.get("first_observed"));
    String timestamp = raw.get("first_observed").asString();
    if (original != null && utc(interpreted)) {
      time.put("basis", "source"); time.put("quality", "valid"); time.put("source_value", original); time.put("source_utc", interpreted); timestamp = interpreted;
    } else {
      String quality = original == null ? "missing" : (localTime(original) ? "timezone_ambiguous" : "unparseable");
      time.put("basis", "first_observed"); time.put("quality", quality);
      if (original != null) time.put("source_value", original);
      diagnostic(ds, "timestamp_" + quality, "/@timestamp");
    }
    if (c.has("receipt")) for (var p : c.get("receipt").properties()) time.put(p.getKey(), p.getValue());
    boolean blocked = ds.stream().anyMatch(d -> Set.of("extraction_failed", "identity_missing", "conflicting").contains(d.get("code")));
    Map<String, Object> vendor = new LinkedHashMap<>(fields);
    vendor.put("windows_system", Map.of("values", xml.system, "attributes", xml.attributes));
    Map<String, Object> event = new LinkedHashMap<>();
    event.put("@timestamp", timestamp); event.put("ecs", Map.of("version", "9.5.0"));
    event.put("event", Map.of("id", Json.identity(List.of(raw.get("source").get("namespace").asString(), raw.get("source").get("instance").asString(), List.of(raw.get("record_id").asString()))),
        "kind", "event", "category", List.of("process"), "type", List.of("start"), "code", security ? "4688" : "1", "created", raw.get("first_observed"), "provider", security ? "Microsoft-Windows-Security-Auditing" : "Microsoft-Windows-Sysmon"));
    event.put("source_fields", vendor);
    if (!process.isEmpty()) event.put("process", process);
    if (!user.isEmpty()) event.put("user", user);
    if (!host.isEmpty()) event.put("host", host);
    var mapping = c.get("mapping_profile");
    event.put("detectbridge", Map.of("contract_version", "1.0.0", "source", raw.get("source"),
        "source_contract", Map.of("id", c.get("source_contract").get("id"), "version", "1.0.0"),
        "processing", Map.of("parser", "windows-xml/1.0.0", "normalizer", "windows-normalizer/1.0.0", "mapping", mapping.get("id").asString() + "/" + mapping.get("version").asString()),
        "run_id", c.get("run_id"), "time", time,
        "assembly", Map.of("mode", "standalone", "closure", "not_required", "quality", "source_indicated", "assembler_version", "1.0.0"),
        "quality", Map.of("integrity", blocked ? "insufficient" : "sufficient", "eligibility", blocked ? "skipped" : "eligible", "diagnostics", ds),
        "evidence", List.of(Map.of("record_id", raw.get("record_id"), "evidence", raw.get("evidence")))));
    JsonNode output = Json.MAPPER.valueToTree(event);
    if (Json.bytes(output).length > Json.MAX_VALUE) return failure(raw, c, "extraction_failed", "normalized_output_limit");
    normalized.validate(output, c.get("source_contract").get("snapshot"));
    return new Result(output, null);
  }
  private static boolean localTime(String v) { return utc(v + "Z"); }
  private static void guid(Map<String, Object> target, String v, List<Map<String, String>> ds, String field) {
    if (v == null) return;
    if (v.matches("\\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\\}")) target.put("entity_id", v);
    else diagnostic(ds, "extraction_failed", field);
  }
}
