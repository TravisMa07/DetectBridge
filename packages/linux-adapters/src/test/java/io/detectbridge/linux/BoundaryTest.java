package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import io.detectbridge.transport.Json;
import java.io.IOException;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class BoundaryTest {
  @Test void exactContextVersionsHashesAndObservationsCannotDrift() throws Exception {
    Boundary.Input original = input(line("EOE"), 0, context(false));
    for (String change : List.of("version", "parser", "source_hash", "source_snapshot", "mapping", "first", "unknown", "generation")) {
      ObjectNode ctx = (ObjectNode) original.context();
      switch (change) {
        case "version" -> ctx.put("version", "1.1.0");
        case "parser" -> ((ObjectNode)ctx.get("parser")).put("version", "1.1.0");
        case "source_hash" -> ((ObjectNode)ctx.get("source_contract")).put("sha256", "0".repeat(64));
        case "source_snapshot" -> ((ObjectNode)ctx.at("/source_contract/snapshot")).put("id", "different");
        case "mapping" -> ((ObjectNode)ctx.get("mapping_profile")).put("id", "unreviewed");
        case "first" -> ctx.put("first_observed", "2026-01-01T00:00:02Z");
        case "unknown" -> ctx.put("executable_code", "ignored");
        case "generation" -> ((ObjectNode)ctx.get("source_generation")).remove("provenance");
      }
      assertThrows(IllegalArgumentException.class, () -> Boundary.resolve(original.raw(), ctx, e -> original.bytes()), change);
    }
    assertThrows(IOException.class, () -> Boundary.resolve(original.raw(), original.context(), e -> { throw new IOException("synthetic_offline"); }));
    assertThrows(IllegalArgumentException.class, () -> Boundary.resolve(original.raw(), original.context(), e -> new byte[]{0}));
    ObjectNode raw = (ObjectNode)original.raw(); raw.put("record_id", "sha256:" + "0".repeat(64));
    assertThrows(IllegalArgumentException.class, () -> Boundary.resolve(raw, original.context(), e -> original.bytes()));
  }
  @Test void schemeCasePreservesEvidenceAndBindingHashesAreRequired() throws Exception {
    var original = input(line("EOE"), 0, context(false));
    for (String scheme : List.of("https", "HTTPS", "hTtPs", "s3", "S3", "file", "FILE")) {
      ObjectNode raw = (ObjectNode)original.raw();
      ObjectNode evidence = (ObjectNode)raw.get("evidence"); evidence.remove("inline");
      String uri = scheme + "://evidence.example/object";
      evidence.set("reference", Json.MAPPER.valueToTree(Map.of("uri", uri,
          "object_sha256", evidence.get("sha256").asString())));
      var resolved = Boundary.resolve(raw, original.context(), e -> original.bytes());
      assertEquals(uri, resolved.raw().at("/evidence/reference/uri").asString());
    }
    for (String change : List.of("source", "hash", "kind", "mapping_declaration")) {
      ObjectNode c = (ObjectNode)original.context();
      switch(change) {
        case "source" -> ((ObjectNode)c.at("/host_binding/source")).put("instance", "wrong");
        case "hash" -> ((ObjectNode)c.get("host_binding")).put("sha256", "0".repeat(64));
        case "kind" -> ((ObjectNode)c.get("host_binding")).put("kind", "invented");
        case "mapping_declaration" -> ((ObjectNode)c.at("/mapping_profile/declaration")).put("id", "wrong");
      }
      assertThrows(IllegalArgumentException.class, () -> Boundary.resolve(original.raw(), c, e -> original.bytes()), change);
    }
  }
  @Test void suppliedResolverSeesExactReferenceRangeAndPreservationRetainsIt() throws Exception {
    Boundary.Input inline = input(line("EOE"), 0, context(false)); ObjectNode raw = (ObjectNode)inline.raw();
    ObjectNode evidence = (ObjectNode)raw.get("evidence"); evidence.remove("inline");
    evidence.set("reference", Json.MAPPER.valueToTree(Map.of("uri", "urn:sha256:" + "b".repeat(64), "object_sha256", "b".repeat(64),
        "byte_range", Map.of("offset", 123, "length", inline.bytes().length))));
    Boundary.Input resolved = Boundary.resolve(raw, inline.context(), e -> { assertEquals(evidence, e); return inline.bytes(); });
    ObjectNode ctx = (ObjectNode)resolved.context(); ctx.remove("host_binding");
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    a.accept(Boundary.resolve(raw, ctx, e -> inline.bytes()), sink);
    assertEquals(evidence.get("reference"), sink.diagnostics().get(0).at("/member/reference"));
    assertEquals(evidence.get("sha256"), sink.diagnostics().get(0).at("/member/evidence_sha256"));
    assertEquals(raw.get("cursor"), sink.diagnostics().get(0).at("/member/cursor"));
    assertEquals(FIRST, sink.diagnostics().get(0).at("/member/first_observed").asString());
    assertEquals("b".repeat(64), sink.diagnostics().get(0).at("/member/reference/object_sha256").asString());
    ((ObjectNode)evidence.get("reference")).set("byte_range", Json.MAPPER.valueToTree(Map.of("offset", 123, "length", 1)));
    assertThrows(IllegalArgumentException.class, () -> Boundary.resolve(raw, ctx, e -> inline.bytes()));
  }
  @Test void schemasRejectUnknownManifestAndStateSemantics() throws Exception {
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    a.accept(input(line("EOE"), 0, context(false)), sink);
    ObjectNode manifest = (ObjectNode)sink.manifests().get(0).deepCopy(); manifest.put("new_core_field", true);
    assertThrows(IllegalArgumentException.class, () -> Boundary.schema("urn:detectbridge:linux:1.0.0:manifest", manifest));
    ObjectNode state = (ObjectNode)Json.MAPPER.readTree(a.snapshot()); state.put("binding", "0".repeat(64));
    assertThrows(IllegalArgumentException.class, () -> Assembler.restore(new Time(), Assembler.Limits.defaults(), Json.bytes(state)));
  }
  @Test void proposedSourceContractExamplesRemainReadableWithFixtureAttribution() {
    var normalized = new io.detectbridge.detection.Normalized(new io.detectbridge.detection.Contracts());
    for (String id : List.of("linux-audit-execution-p12a", "openssh-authentication-p12a")) {
      JsonNode event = Boundary.resource(id + ".contract-example.event");
      normalized.validate(event, Boundary.resource(id + ".source"));
      assertEquals("fixture-only/1.0.0", event.at("/detectbridge/processing/parser").asString());
    }
  }

  @Test void validP03ObservationPrecisionAndUuidCaseArePreserved() throws Exception {
    ObjectNode c = context(false); c.put("first_observed", "2026-01-01T00:00:01.123456789123Z");
    c.put("run_id", "ABCDEF00-0000-4000-8000-000000000001");
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    complete(a, sink, c, 0); ObjectNode earlier = c.deepCopy();
    earlier.put("first_observed", "2026-01-01T00:00:01.123456789122Z");
    a.accept(input(line("EOE"), 5, earlier), sink);
    assertEquals("2026-01-01T00:00:01.123456789122Z", sink.events().get(0).at("/event/created").asString());
    assertEquals(c.get("run_id"), sink.events().get(0).at("/detectbridge/run_id"));
    assertDoesNotThrow(() -> Assembler.restore(new Time(), Assembler.Limits.defaults(), a.snapshot()));
  }

  @Test void longOriginalCursorUsesHashBoundRetainedRawDescriptorWithoutTruncation() throws Exception {
    var original = input(line("EOE"), 0, context(false));
    ObjectNode raw = (ObjectNode)original.raw();
    ((ObjectNode)raw.get("cursor")).put("value", "x".repeat(8000));
    raw.put("record_id", io.detectbridge.transport.EnvelopeValidator.recordIdentity(raw));
    ObjectNode c = (ObjectNode)original.context(); c.remove("host_binding");
    var supplied = Boundary.resolve(raw, c, evidence -> original.bytes());
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    a.accept(supplied, sink); JsonNode member = sink.diagnostics().get(0).get("member");
    assertEquals("retained_raw", member.get("retention").asString());
    assertEquals(raw.get("record_id"), member.get("record_id"));
    assertEquals(Boundary.hash(raw), member.get("raw_sha256").asString());
    assertEquals(8000, supplied.raw().at("/cursor/value").asString().length());
    assertFalse(member.has("cursor")); assertFalse(member.has("reference"));
    assertTrue(Json.bytes(member).length <= 2048);
  }

}
