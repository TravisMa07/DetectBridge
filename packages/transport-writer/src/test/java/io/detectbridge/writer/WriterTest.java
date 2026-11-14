package io.detectbridge.writer;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.net.URI;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.Flow;
import javax.net.ssl.SSLContext;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;

class WriterTest {
  JsonNode config() {
    return Json.MAPPER.valueToTree(
        Map.of(
            "pipeline_id",
            "00000000-0000-4000-8000-000000000001",
            "kafka_cluster_id",
            "cluster-a",
            "source_topics",
            Map.of(
                Projection.OUTPUT,
                Map.of("id", "output-id"),
                Projection.QUARANTINE,
                Map.of("id", "quarantine-id"),
                Projection.FAILURES,
                Map.of("id", "failure-id"),
                "detectbridge.replay.input.v1",
                Map.of("id", "input-id"))));
  }

  byte[] example() throws Exception {
    return getClass().getResourceAsStream("/replay/v1/examples/record.json").readAllBytes();
  }

  byte[] key(byte[] value) {
    return Json.read(value).get("run_id").asString().getBytes(StandardCharsets.UTF_8);
  }

  Projection.Location location(long offset) {
    return new Projection.Location("cluster-a", "output-id", Projection.OUTPUT, 0, offset);
  }

  Projection.Document doc(byte[] value, long offset) {
    return new Projection(config()).project(Projection.OUTPUT, key(value), value, location(offset));
  }

  ConsumerRecord<byte[], byte[]> input(long offset, byte[] value) {
    return new ConsumerRecord<>(Projection.OUTPUT, 0, offset, key(value), value);
  }

  static class Fake extends SearchClient {
    List<List<Projection.Document>> batches = new ArrayList<>();
    Queue<List<Outcome>> outcomes = new ArrayDeque<>();
    Queue<Response> responses = new ArrayDeque<>();

    Fake() throws Exception {
      super(URI.create("https://localhost"), SSLContext.getDefault(), null, 1);
    }

    @Override
    public List<Outcome> bulk(List<Projection.Document> docs) {
      if (outcomes.isEmpty()) return super.bulk(docs);
      batches.add(List.copyOf(docs));
      return outcomes.remove();
    }

    @Override
    public Response request(String method, String path, byte[] body) {
      return responses.remove();
    }
  }

  @Test
  void immutableIdentityAndProjectionAcrossKafkaCopies() throws Exception {
    byte[] raw = example();
    var first = doc(raw, 0);
    var duplicate = doc(raw, 19);
    assertEquals(first.id(), duplicate.id());
    assertEquals(first.body().get("content_sha256"), duplicate.body().get("content_sha256"));
    assertEquals(Projection.REPLAY, first.index());
    assertEquals(
        Json.read(raw).get("record").get("record_id").asString(), first.body().get("record_id"));
    assertEquals(Json.sha(raw), first.body().get("input_sha256"));
    assertEquals("2026-11-13T00:11:27.635116Z", first.body().get("effective_time"));
    var second = Json.read(raw).deepCopy();
    ((tools.jackson.databind.node.ObjectNode) second)
        .put("run_id", "00000000-0000-4000-8000-000000000002");
    assertNotEquals(first.id(), doc(Json.bytes(second), 0).id());
    var control =
        Map.of(
            "contract_version",
            "1.0.0",
            "run_id",
            Json.read(raw).get("run_id").asString(),
            "sequence",
            0,
            "type",
            "run_end",
            "record_count",
            0,
            "dataset_count",
            0);
    assertEquals(
        first.id(),
        doc(Json.bytes(control), 0).id()); // Cross-kind collisions share one physical index.
  }

  @Test
  void inlineEvidenceNeverEntersSearchAndTimeIsNotRounded() throws Exception {
    var node = Json.read(example()).deepCopy();
    var raw = (tools.jackson.databind.node.ObjectNode) node.get("record");
    raw.set(
        "evidence",
        Json.MAPPER.valueToTree(
            Map.of(
                "sha256",
                Json.sha("secret-body".getBytes(StandardCharsets.UTF_8)),
                "encoding",
                "utf-8",
                "media_type",
                "text/plain",
                "inline",
                "secret-body")));
    var timing = (tools.jackson.databind.node.ObjectNode) node.get("timing");
    timing.put("original_time", "1900-01-01T00:00:00.123456789Z");
    timing.put("effective_time", "1900-01-01T00:00:00.123456789Z");
    var result = doc(Json.bytes(node), 0);
    assertFalse(
        new String(Json.bytes(result.body()), StandardCharsets.UTF_8).contains("secret-body"));
    assertEquals("outside_nanos_range", result.body().get("time_projection_reason"));
    assertFalse(result.body().containsKey("effective_time"));
    assertEquals(
        "1900-01-01T00:00:00.123456789Z",
        ((Map<?, ?>) result.body().get("timing")).get("effective_time"));
  }

  @Test
  void partialFailuresRetryOnlyUnresolvedItemsAndPreventOffsetCommit() throws Exception {
    var window =
        new Window(
            List.of(input(0, example()), input(1, example())),
            config(),
            new Projection(config()),
            (n, v) -> {});
    var fake = new Fake();
    fake.outcomes.add(List.of(SearchClient.Outcome.CREATED, SearchClient.Outcome.RETRY));
    fake.outcomes.add(List.of(SearchClient.Outcome.CREATED));
    assertThrows(SearchClient.Failure.class, () -> window.step(fake, (l, v, c) -> fail()));
    assertThrows(IllegalStateException.class, window::offsets);
    window.step(fake, (l, v, c) -> fail());
    assertTrue(window.complete());
    assertEquals(2, fake.batches.get(0).size());
    assertEquals(1, fake.batches.get(1).size());
    assertEquals(2, window.offsets().values().iterator().next().offset());
  }

  @Test
  void failureAcknowledgmentAndDiagnosticNonRecursion() throws Exception {
    var record =
        new ConsumerRecord<byte[], byte[]>(
            Projection.OUTPUT, 0, 4, null, "bad-json".getBytes(StandardCharsets.UTF_8));
    var window = new Window(List.of(record), config(), new Projection(config()), (n, v) -> {});
    var fake = new Fake();
    assertThrows(
        SearchClient.Failure.class,
        () ->
            window.step(
                fake,
                (l, v, c) -> {
                  throw new SearchClient.Failure(SearchClient.Kind.RETRY, "kafka_outage");
                }));
    assertFalse(window.complete());
    window.step(fake, (l, v, c) -> assertEquals("invalid_json", c));
    assertTrue(window.complete());
    var diagnostic = new ConsumerRecord<byte[], byte[]>(Projection.FAILURES, 0, 0, null, null);
    var blocked = new Window(List.of(diagnostic), config(), new Projection(config()), (n, v) -> {});
    assertThrows(
        SearchClient.Failure.class,
        () -> blocked.step(fake, (l, v, c) -> fail("must not recurse")));
    assertFalse(blocked.complete());
  }

  @Test
  void conflictChecksRecomputeContentAndDoNotTrustStoredHash() throws Exception {
    var d = doc(example(), 1);
    var source = Json.MAPPER.valueToTree(d.body());
    var fake = new Fake();
    var conflict =
        new SearchClient.Response(
            200,
            Json.MAPPER.valueToTree(
                Map.of(
                    "items",
                    List.of(
                        Map.of(
                            "create",
                            Map.of(
                                "_id",
                                d.id(),
                                "_index",
                                d.index(),
                                "status",
                                409,
                                "error",
                                Map.of("type", "version_conflict_engine_exception")))))));
    fake.responses.add(conflict);
    fake.responses.add(
        new SearchClient.Response(200, Json.MAPPER.valueToTree(Map.of("_source", source))));
    assertEquals(List.of(SearchClient.Outcome.DUPLICATE), fake.bulk(List.of(d)));
    fake.responses.add(conflict);
    fake.responses.add(
        new SearchClient.Response(200, Json.MAPPER.valueToTree(Map.of("found", true))));
    assertThrows(SearchClient.Failure.class, () -> fake.bulk(List.of(d)));
    ((tools.jackson.databind.node.ObjectNode) source).put("dataset_id", "tampered");
    fake.responses.add(conflict);
    fake.responses.add(
        new SearchClient.Response(200, Json.MAPPER.valueToTree(Map.of("_source", source))));
    assertEquals(List.of(SearchClient.Outcome.CONFLICT), fake.bulk(List.of(d)));
    ((tools.jackson.databind.node.ObjectNode) source).put("sequence", 1.1);
    fake.responses.add(conflict);
    fake.responses.add(
        new SearchClient.Response(200, Json.MAPPER.valueToTree(Map.of("_source", source))));
    assertEquals(List.of(SearchClient.Outcome.CONFLICT), fake.bulk(List.of(d)));
    fake.responses.add(
        new SearchClient.Response(200, Json.MAPPER.valueToTree(Map.of("items", List.of()))));
    assertThrows(SearchClient.Failure.class, () -> fake.bulk(List.of(d)));
  }

  @Test
  void failureReferencesAreDeterministicAndValueFree() throws Exception {
    var p = new Projection(config());
    var a =
        p.failure(location(2), "private-sentinel".getBytes(StandardCharsets.UTF_8), "invalid_json");
    assertEquals(
        a,
        p.failure(
            location(2), "private-sentinel".getBytes(StandardCharsets.UTF_8), "invalid_json"));
    assertFalse(new String(Json.bytes(a), StandardCharsets.UTF_8).contains("private-sentinel"));
    var projected =
        p.project(
            Projection.FAILURES,
            a.get("failure_id").toString().getBytes(StandardCharsets.UTF_8),
            Json.bytes(a),
            new Projection.Location("cluster-a", "failure-id", Projection.FAILURES, 0, 1));
    assertEquals(Projection.DIAGNOSTICS, projected.index());
    var wrong = Json.MAPPER.valueToTree(a).deepCopy();
    ((tools.jackson.databind.node.ObjectNode) wrong.get("input")).put("topic_id", "wrong");
    assertThrows(
        Projection.Invalid.class,
        () -> p.project(Projection.FAILURES, new byte[0], Json.bytes(wrong), location(3)));
  }

  @Test
  void responseSizeIsBoundedAndCancellationIsVisible() {
    var body = new SearchClient.LimitedBody();
    var cancelled = new java.util.concurrent.atomic.AtomicBoolean();
    body.onSubscribe(
        new Flow.Subscription() {
          public void request(long n) {}

          public void cancel() {
            cancelled.set(true);
          }
        });
    body.onNext(List.of(ByteBuffer.allocate(4 * 1024 * 1024 + 1)));
    assertTrue(cancelled.get());
    assertTrue(body.getBody().toCompletableFuture().isCompletedExceptionally());
  }

  @Test
  void unknownVersionsUnsafeJsonAndResourceLimitsAreRejected() throws Exception {
    var node = Json.read(example()).deepCopy();
    ((tools.jackson.databind.node.ObjectNode) node).put("contract_version", "9.0.0");
    assertThrows(Projection.Invalid.class, () -> doc(Json.bytes(node), 0));
    var p = new Projection(config());
    assertThrows(
        Projection.Invalid.class,
        () ->
            p.project(
                Projection.OUTPUT,
                new byte[0],
                "{\"x\":1,\"x\":2}".getBytes(StandardCharsets.UTF_8),
                location(0)));
    var hundredOne = new ArrayList<ConsumerRecord<byte[], byte[]>>();
    for (int i = 0; i < 101; i++) hundredOne.add(input(i, example()));
    assertThrows(
        SearchClient.Failure.class, () -> new Window(hundredOne, config(), p, (n, v) -> {}));
    assertThrows(
        SearchClient.Failure.class,
        () ->
            new Window(
                List.of(new ConsumerRecord<>(Projection.OUTPUT, 1, 0, key(example()), example())),
                config(),
                p,
                (n, v) -> {}));
    assertTrue(SearchClient.retryable(429, Json.MAPPER.createObjectNode()));
    assertFalse(SearchClient.retryable(400, Json.MAPPER.createObjectNode()));
  }

  @Test
  void roleComparisonAcceptsServerDefaultsButRejectsAdditionalGrants() {
    Map<String, Object> expected =
        Map.of(
            "cluster_permissions",
            List.of("cluster:monitor/main"),
            "tenant_permissions",
            List.of(),
            "index_permissions",
            List.of(
                Map.of(
                    "index_patterns",
                    List.of("a", "b"),
                    "allowed_actions",
                    List.of("write", "get"))));
    var actual =
        Json.MAPPER.valueToTree(
            Map.of(
                "cluster_permissions",
                List.of("cluster:monitor/main"),
                "tenant_permissions",
                List.of(),
                "index_permissions",
                List.of(
                    Map.of(
                        "index_patterns",
                        List.of("b", "a"),
                        "allowed_actions",
                        List.of("get", "write"),
                        "dls",
                        "",
                        "fls",
                        List.of(),
                        "masked_fields",
                        List.of()))));
    assertTrue(Bootstrap.roleMatches(actual, expected));
    ((tools.jackson.databind.node.ObjectNode) actual)
        .set("cluster_permissions", Json.MAPPER.valueToTree(List.of("*")));
    assertFalse(Bootstrap.roleMatches(actual, expected));
  }

  @Test
  void tlsChecksBothCertificateAuthorityAndHostname(
      @org.junit.jupiter.api.io.TempDir java.nio.file.Path temp) throws Exception {
    var store = temp.resolve("server.p12");
    var keytool =
        java.nio.file.Path.of(System.getProperty("java.home"), "bin", "keytool").toString();
    var process =
        new ProcessBuilder(
                keytool,
                "-genkeypair",
                "-alias",
                "server",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-dname",
                "CN=localhost",
                "-ext",
                "SAN=dns:localhost",
                "-validity",
                "1",
                "-keystore",
                store.toString(),
                "-storetype",
                "PKCS12",
                "-storepass",
                "test-pass",
                "-keypass",
                "test-pass",
                "-noprompt")
            .redirectErrorStream(true)
            .start();
    process.getInputStream().transferTo(java.io.OutputStream.nullOutputStream());
    assertEquals(0, process.waitFor());
    var keys = java.security.KeyStore.getInstance("PKCS12");
    try (var in = java.nio.file.Files.newInputStream(store)) {
      keys.load(in, "test-pass".toCharArray());
    }
    var km =
        javax.net.ssl.KeyManagerFactory.getInstance(
            javax.net.ssl.KeyManagerFactory.getDefaultAlgorithm());
    km.init(keys, "test-pass".toCharArray());
    var serverTls = SSLContext.getInstance("TLS");
    serverTls.init(km.getKeyManagers(), null, null);
    var ca = temp.resolve("ca.pem");
    java.nio.file.Files.writeString(
        ca,
        "-----BEGIN CERTIFICATE-----\n"
            + Base64.getMimeEncoder(64, new byte[] {'\n'})
                .encodeToString(keys.getCertificate("server").getEncoded())
            + "\n-----END CERTIFICATE-----\n");
    var server =
        com.sun.net.httpserver.HttpsServer.create(
            new java.net.InetSocketAddress("localhost", 0), 8);
    server.setHttpsConfigurator(new com.sun.net.httpserver.HttpsConfigurator(serverTls));
    server.createContext(
        "/",
        exchange -> {
          byte[] body = "{\"ok\":true}".getBytes(StandardCharsets.UTF_8);
          exchange.sendResponseHeaders(200, body.length);
          try (var out = exchange.getResponseBody()) {
            out.write(body);
          }
        });
    server.start();
    try {
      int port = server.getAddress().getPort();
      var trusted = SearchClient.tls(ca, null, null);
      try (var valid =
          new SearchClient(URI.create("https://localhost:" + port), trusted, null, 5)) {
        assertEquals(200, valid.request("GET", "/", null).status());
      }
      try (var wrongHost =
          new SearchClient(URI.create("https://127.0.0.1:" + port), trusted, null, 5)) {
        var error =
            assertThrows(SearchClient.Failure.class, () -> wrongHost.request("GET", "/", null));
        assertEquals(SearchClient.Kind.FATAL, error.kind);
        assertEquals("tls_failed", error.category);
      }
      try (var wrongCa =
          new SearchClient(
              URI.create("https://localhost:" + port), SSLContext.getDefault(), null, 5)) {
        var error =
            assertThrows(SearchClient.Failure.class, () -> wrongCa.request("GET", "/", null));
        assertEquals(SearchClient.Kind.FATAL, error.kind);
      }
    } finally {
      server.stop(0);
    }
  }

  @Test
  void templateUsesOnlyOpenSearch39ComposableFields() {
    assertEquals(
        Set.of("index_patterns", "priority", "version", "composed_of", "_meta", "template"),
        Bootstrap.template(Projection.REPLAY).keySet());
  }

  @Test
  void independentCommittedProjectionVector() throws Exception {
    byte[] input =
        getClass().getResourceAsStream("/writer/v1/examples/input-envelope.json").readAllBytes();
    var expected =
        Json.MAPPER.readTree(getClass().getResourceAsStream("/writer/v1/examples/projection.json"));
    var c =
        Json.MAPPER.readTree(
            getClass().getResourceAsStream("/writer/v1/examples/configuration.json"));
    var location = expected.get("first_input");
    var projected =
        new Projection(c)
            .project(
                Projection.OUTPUT,
                key(input),
                input,
                new Projection.Location(
                    location.get("cluster_id").asString(),
                    location.get("topic_id").asString(),
                    location.get("topic").asString(),
                    0,
                    location.get("offset").longValue()));
    assertEquals(Projection.hash(expected), Projection.hash(projected.body()));
  }

  @Test
  void largeContractIntegersAreNeverTruncatedBeforeIndexing() {
    var envelope =
        Map.of(
            "contract_version",
            "1.0.0",
            "run_id",
            "00000000-0000-4000-8000-000000000003",
            "sequence",
            0,
            "type",
            "run_end",
            "record_count",
            new java.math.BigInteger("9223372036854775808"),
            "dataset_count",
            0);
    var value = Json.bytes(envelope);
    var projected = doc(value, 0);
    assertEquals("9223372036854775808", projected.body().get("record_count").toString());
  }

  @Test
  void emptyAssignmentStillConfirmsGroupMembership() {
    var membership = new Main.MembershipSignal();
    assertFalse(membership.joined.get());
    membership.onPartitionsAssigned(List.of());
    assertTrue(membership.joined.get());
    assertEquals(0, membership.assigned.get());
  }

  @Test
  void recordsReturnedDuringMaintenanceAreRewoundNotDiscarded() {
    var part = new org.apache.kafka.common.TopicPartition(Projection.OUTPUT, 0);
    var revoked = new org.apache.kafka.common.TopicPartition(Projection.QUARANTINE, 0);
    var records =
        new org.apache.kafka.clients.consumer.ConsumerRecords<byte[], byte[]>(
            Map.of(
                part,
                List.of(
                    new ConsumerRecord<>(Projection.OUTPUT, 0, 5, new byte[0], new byte[0]),
                    new ConsumerRecord<>(Projection.OUTPUT, 0, 6, new byte[0], new byte[0])),
                revoked,
                List.of(
                    new ConsumerRecord<>(Projection.QUARANTINE, 0, 9, new byte[0], new byte[0]))));
    assertEquals(Map.of(part, 5L), Main.rewindOffsets(records, Set.of(part)));
  }
}
