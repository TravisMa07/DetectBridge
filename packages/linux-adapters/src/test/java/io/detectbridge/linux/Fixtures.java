package io.detectbridge.linux;

import io.detectbridge.transport.EnvelopeValidator;
import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Original synthetic source lines; never represented as recordings. */
final class Fixtures {
  static final String RUN = "00000000-0000-4000-8000-000000000001";
  static final String RUN2 = "00000000-0000-4000-8000-000000000002";
  static final String FIRST = "2026-01-01T00:00:01Z";
  static final String SYSCALL = "arch=c000003e syscall=59 success=yes exit=0 pid=42 items=2 exe=\"/usr/bin/whoami\"";
  static final List<String> COMPLETE = List.of("SYSCALL " + SYSCALL,
      "EXECVE argc=3 a0=\"whoami\" a1=\"\" a2=\"whoami\"", "CWD cwd=\"/tmp\"",
      "PATH item=0 name=\"/usr/bin/whoami\"", "PATH item=1 name=\"/lib/ld.so\"");
  static String line(String record) {
    int split = record.indexOf(' ');
    return "type=" + (split < 0 ? record : record.substring(0, split))
        + " msg=audit(1767225600.001:7):" + (split < 0 ? "" : record.substring(split)) + "\n";
  }
  static ObjectNode context(boolean auth) {
    String id = auth ? "openssh-authentication-p12a" : "linux-audit-execution-p12a";
    JsonNode source = Boundary.resource(id + ".source");
    ObjectNode c = Json.MAPPER.createObjectNode(); c.put("version", "1.0.0"); c.put("run_id", RUN);
    c.set("source", Json.MAPPER.valueToTree(Map.of("namespace", "original-synthetic", "instance", "a")));
    c.put("first_observed", FIRST);
    c.set("source_generation", Json.MAPPER.valueToTree(Map.of("id", "boot-a", "provenance", List.of("synthetic:boot-a"))));
    c.set("host_binding", Json.MAPPER.valueToTree(Map.of("host_id", "host-a", "revision", "synthetic-1",
        "source", c.get("source"), "kind", "synthetic", "provenance", List.of("synthetic:binding-a"))));
    bind(c);
    c.set("source_contract", Json.MAPPER.valueToTree(Map.of("id", id, "version", "1.0.0",
        "sha256", Boundary.hash(source), "snapshot", source)));
    JsonNode mapping = Boundary.resource(id + ".mapping");
    c.set("mapping_profile", Json.MAPPER.valueToTree(Map.of("id", mapping.get("id"),
        "version", mapping.get("version"), "sha256", mapping.get("sha256"), "declaration", mapping)));
    c.set("parser", Json.MAPPER.valueToTree(Map.of("id", auth ? "openssh-password" : "linux-audit", "version", "1.0.0")));
    return c;
  }
  static void bind(ObjectNode context) {
    ObjectNode host = (ObjectNode)context.get("host_binding");
    host.set("source", context.get("source").deepCopy()); host.remove("sha256");
    host.put("sha256", Boundary.hash(host));
  }
  static Boundary.Input input(String text, int position, ObjectNode ctx) throws Exception {
    byte[] bytes = text.getBytes(StandardCharsets.UTF_8); ObjectNode raw = Json.MAPPER.createObjectNode();
    raw.put("contract_version", "1.0.0"); raw.set("source", ctx.get("source")); raw.set("first_observed", ctx.get("first_observed"));
    raw.set("cursor", Json.MAPPER.valueToTree(Map.of("kind", "native", "value", "synthetic-position-" + position)));
    raw.set("evidence", Json.MAPPER.valueToTree(Map.of("sha256", Json.sha(bytes), "encoding", "utf-8", "media_type", "text/plain", "inline", text)));
    raw.put("record_id", EnvelopeValidator.recordIdentity(raw));
    return Boundary.resolve(raw, ctx, evidence -> bytes);
  }
  static final class Time extends Clock {
    long millis = 1000;
    @Override public ZoneId getZone() { return ZoneOffset.UTC; }
    @Override public Clock withZone(ZoneId zone) { return this; }
    @Override public Instant instant() { return Instant.ofEpochMilli(millis); }
    @Override public long millis() { return millis; }
  }
  static final class Sink implements Assembler.Commit {
    final List<JsonNode> outputs = new ArrayList<>(); byte[] state; boolean fail;
    @Override public void persist(List<JsonNode> batch, byte[] snapshot) throws Exception {
      if (fail) throw new java.io.IOException("synthetic_unavailable_sink");
      outputs.addAll(batch); state = snapshot;
    }
    List<JsonNode> events() { return outputs.stream().filter(n -> n.has("@timestamp")).toList(); }
    List<JsonNode> manifests() { return outputs.stream().filter(n -> n.has("manifest_id")).toList(); }
    List<JsonNode> diagnostics() { return outputs.stream().filter(n -> n.has("code")).toList(); }
  }
  static void complete(Assembler a, Sink sink, ObjectNode c, int offset) throws Exception {
    for (int i = 0; i < COMPLETE.size(); i++) a.accept(input(line(COMPLETE.get(i)), offset + i, c), sink);
  }
}
