package io.detectbridge.detection;

import static io.detectbridge.detection.Contracts.*;

import io.detectbridge.transport.Json;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.*;
import tools.jackson.databind.JsonNode;

public final class Normalized {
  private final Contracts contracts;

  public Normalized(Contracts contracts) {
    this.contracts = contracts;
  }

  public static void unicode(JsonNode n) {
    if (n.isString()) {
      String s = n.asString();
      for (int i = 0; i < s.length(); i++) {
        char c = s.charAt(i);
        if (Character.isHighSurrogate(c))
          check(++i < s.length() && Character.isLowSurrogate(s.charAt(i)), "invalid_unicode");
        else check(!Character.isLowSurrogate(c), "invalid_unicode");
      }
    } else if (n.isObject())
      for (var p : n.properties()) {
        unicode(Json.MAPPER.valueToTree(p.getKey()));
        unicode(p.getValue());
      }
    else if (n.isArray()) for (var v : n) unicode(v);
  }

  public void source(JsonNode s) {
    contracts.require("contracts", "source-contract", s);
    Set<String> blocking = new HashSet<>();
    for (var c : s.get("quality_policy").get("blocking_codes")) blocking.add(c.asString());
    for (var c : s.get("quality_policy").get("warning_codes"))
      check(!blocking.contains(c.asString()), "ambiguous_quality_policy");
    for (var m : s.get("mappings"))
      check(validTarget(m.get("target_path").asString()), "unknown_ecs_target");
    for (var f : s.get("required_fields")) check(validTarget(f.asString()), "unknown_ecs_target");
  }

  private boolean validTarget(String path) {
    try (var stream = Normalized.class.getResourceAsStream("/v1/normalized-event.schema.json")) {
      JsonNode n = Json.MAPPER.readTree(Objects.requireNonNull(stream).readAllBytes());
      if (path.startsWith("source_fields") || path.startsWith("detectbridge")) return false;
      for (String p : path.split("\\.")) n = n.path("properties").path(p);
      return !n.isMissingNode();
    } catch (Exception e) {
      throw new IllegalStateException("schema_load_failure");
    }
  }

  private static void evidence(JsonNode e) {
    String hash = e.get("sha256").asString();
    if (e.path("reference").has("byte_range"))
      for (var p : e.get("reference").get("byte_range").properties())
        check(p.getValue().isIntegralNumber(), "integer_required");
    if (e.has("inline")) {
      String v = e.get("inline").asString();
      byte[] bytes;
      if (e.get("encoding").asString().equals("utf-8")) bytes = v.getBytes(StandardCharsets.UTF_8);
      else {
        check(v.length() % 4 == 0 && v.matches("[A-Za-z0-9+/]*={0,2}"), "invalid_encoding");
        bytes = Base64.getDecoder().decode(v);
      }
      check(Json.sha(bytes).equals(hash), "inline_digest_mismatch");
    } else {
      JsonNode r = e.get("reference");
      String object = r.get("object_sha256").asString();
      check(r.has("byte_range") || hash.equals(object), "whole_object_digest_mismatch");
      String text = r.get("uri").asString();
      URI uri = URI.create(text);
      String scheme = uri.getScheme();
      check(List.of("urn", "https", "s3", "file").contains(scheme), "unsupported_evidence_scheme");
      check(
          uri.getRawUserInfo() == null
              && uri.getRawQuery() == null
              && uri.getRawFragment() == null
              && (uri.getRawAuthority() == null || !uri.getRawAuthority().contains("@")),
          "unsafe_evidence_reference");
      if (scheme.equals("urn"))
        check(text.equals("urn:sha256:" + object), "invalid_content_address");
      if (scheme.equals("https") || scheme.equals("s3"))
        check(uri.getHost() != null && !uri.getHost().isEmpty(), "invalid_object_reference");
    }
  }

  public void validate(JsonNode e, JsonNode source) {
    unicode(e);
    contracts.require("contracts", "normalized-event", e);
    for (String p : List.of("process.pid", "process.parent.pid", "source.port", "file.size")) {
      JsonNode n = field(e, p);
      if (!n.isMissingNode()) check(n.isIntegralNumber(), "integer_required");
    }
    for (String p :
        List.of(
            "@timestamp",
            "event.created",
            "event.ingested",
            "detectbridge.time.first_observed",
            "detectbridge.time.source_utc",
            "detectbridge.time.received",
            "detectbridge.time.processed")) {
      JsonNode t = field(e, p);
      if (!t.isMissingNode()) {
        String v = t.asString();
        check(
            Integer.parseInt(v.substring(0, 4)) >= 1 && Integer.parseInt(v.substring(17, 19)) <= 59,
            "invalid_timestamp");
      }
    }
    JsonNode db = e.get("detectbridge"),
        quality = db.get("quality"),
        assembly = db.get("assembly"),
        time = db.get("time");
    List<String> members = new ArrayList<>();
    for (var m : db.get("evidence")) {
      members.add(m.get("record_id").asString());
      evidence(m.get("evidence"));
    }
    check(new HashSet<>(members).size() == members.size(), "duplicate_record_membership");
    Collections.sort(members);
    check(
        Json.identity(
                List.of(
                    db.get("source").get("namespace").asString(),
                    db.get("source").get("instance").asString(),
                    members))
            .equals(e.get("event").get("id").asString()),
        "event_identity_mismatch");
    if (time.get("basis").asString().equals("source"))
      check(
          time.get("quality").asString().equals("valid")
              && time.has("source_value")
              && time.path("source_utc").equals(e.get("@timestamp")),
          "inconsistent_source_time");
    else
      check(
          !time.get("quality").asString().equals("valid")
              && !time.has("source_utc")
              && time.get("first_observed").equals(e.get("@timestamp")),
          "inconsistent_time_fallback");
    if (List.of("unparseable", "timezone_ambiguous").contains(time.get("quality").asString()))
      check(time.has("source_value"), "missing_original_time");
    if (e.get("event").has("created"))
      check(
          e.get("event").get("created").equals(time.get("first_observed")),
          "first_observed_mismatch");
    boolean skipped = quality.get("eligibility").asString().equals("skipped");
    String integrity = quality.get("integrity").asString();
    check(!integrity.equals("insufficient") || skipped, "insufficient_integrity_must_skip");
    check(
        !quality.get("eligibility").asString().equals("eligible") || integrity.equals("sufficient"),
        "eligibility_without_integrity");
    check(!skipped || !quality.get("diagnostics").isEmpty(), "skip_reason_required");
    check(
        !List.of("known_missing", "conflicting").contains(assembly.get("quality").asString())
            || integrity.equals("insufficient"),
        "assembly_integrity_mismatch");
    if (assembly.get("mode").asString().equals("standalone"))
      check(
          members.size() == 1 && assembly.get("closure").asString().equals("not_required"),
          "standalone_membership_mismatch");
    if (source == null) return; // structurally valid unknown contracts become configuration-blocked
    for (var p : source.get("classification").properties())
      check(e.get("event").path(p.getKey()).equals(p.getValue()), "source_classification_mismatch");
    for (var p : source.get("required_fields"))
      check(skipped || !field(e, p.asString()).isMissingNode(), "required_source_field_missing");
    check(
        skipped
            || !source.get("requires_host_id").asBoolean()
            || !field(e, "host.id").isMissingNode(),
        "required_source_field_missing");
    Set<String> blocking = new HashSet<>();
    for (var c : source.get("quality_policy").get("blocking_codes")) blocking.add(c.asString());
    for (var d : quality.get("diagnostics"))
      check(
          skipped || !blocking.contains(d.get("code").asString()), "blocking_diagnostic_must_skip");
  }
}
