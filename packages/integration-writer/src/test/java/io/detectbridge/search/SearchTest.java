package io.detectbridge.search;

import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.detection.Evaluator;
import io.detectbridge.integration.Machine;
import io.detectbridge.linux.Assembler;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.nio.*;
import java.util.concurrent.Flow;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.net.URI;
import javax.net.ssl.SSLContext;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class SearchTest {
  static final Path ROOT=Path.of(System.getProperty("repository.root"));
  static JsonNode read(String path) throws Exception {return Json.MAPPER.readTree(Files.readAllBytes(ROOT.resolve(path)));}
  static Evaluator evaluator() throws Exception {return new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/integration/plan.json")));}
  static JsonNode config() throws Exception {
    Map<String,Object> topics=new TreeMap<>(); for(String t:Projection.SOURCE_TOPICS)topics.put(t,Map.of("id",t+"-id"));
    return Json.MAPPER.valueToTree(Map.of("pipeline_id","00000000-0000-4000-8000-000000000001","kafka_cluster_id","cluster-a",
        "source_topics",topics,"evaluation_bundle_sha256",evaluator().bundle(),"integration_binding","a".repeat(64)));
  }
  static List<Machine.Intent> outputs(String scenario) throws Exception {
    var rows=read(".cache/integration/cases.json");var source=Json.MAPPER.valueToTree(Map.of("cluster_id","cluster-a","topic_id",Projection.INPUT+"-id","topic",Projection.INPUT));
    var machine=new Machine(Clock.fixed(Instant.ofEpochMilli(1000),ZoneOffset.UTC),Assembler.Limits.defaults(),"a".repeat(64),source,Machine::inline,evaluator());
    List<JsonNode> inputs=new ArrayList<>();
    if(scenario.equals("audit")) rows.get("complete").forEach(inputs::add);
    else inputs.add(scenario.equals("audit_skipped")?rows.at("/complete/5"):rows.get(scenario));
    long offset=0;for(var row:inputs) { machine.enqueue(Machine.wire(Json.bytes(row),"cluster-a",Projection.INPUT+"-id",Projection.INPUT,offset++));while(machine.pump()){} }
    List<Machine.Intent> result=new ArrayList<>(); machine.snapshot(1);machine.complete(1,result::add); return result;
  }
  static String topic(Machine.Intent i) {return switch(i.kind()) {case "tagged"->Projection.OUTPUT;case "detection"->Projection.DETECTIONS;default->Projection.PROCESSING;};}
  static Projection.Document project(Machine.Intent i,long offset) throws Exception {return new Projection(config()).project(topic(i),i.key().getBytes(StandardCharsets.UTF_8),Json.bytes(i.document()),new Projection.Location("cluster-a",topic(i)+"-id",topic(i),0,offset));}
  static ConsumerRecord<byte[],byte[]> record(Machine.Intent i,long offset) {
    var r=new ConsumerRecord<byte[],byte[]>(topic(i),0,offset,i.key().getBytes(StandardCharsets.UTF_8),Json.bytes(i.document()));
    r.headers().add("detectbridge.runtime.binding","a".repeat(64).getBytes(StandardCharsets.UTF_8));return r;
  }
  @Test void actualAdaptersHaveIndependentLiteralFieldsCountsAndNoRawOriginals() throws Exception {
    var expected=read("contracts/search-writer/v1/fixtures/expectations.json");
    for(String name:List.of("windows","sysmon","auth","audit","audit_skipped","windows_skipped","windows_budget")) {
      for(var intent:outputs(name)) if(Set.of("tagged","detection","processing").contains(intent.kind())) {
        var projected=project(intent,0);var body=Json.MAPPER.valueToTree(projected.body());
        assertEquals(intent.key(),projected.id());assertEquals(body.get("content_sha256").asString(),Projection.contentHash(body));
        if(intent.kind().equals("tagged")) {
          assertEquals(Projection.canonical(expected.at("/counts/"+(name.equals("sysmon")?"windows":name))),Projection.canonical(body.get("counts")));
          assertEquals(intent.document().at("/event/event/id"),body.get("event_id"));
          assertFalse(body.toString().contains("\"inline\":"));assertFalse(body.has("extensions"));
          if(name.equals("audit")) assertEquals(Projection.canonical(expected.get("audit_process")),Projection.canonical(body.get("process")));
          var duplicate=project(intent,99);assertEquals(projected.body().get("content_sha256"),duplicate.body().get("content_sha256"));
        }
      }
    }
  }
  @Test void physicalCopiesAndReceiptClocksDoNotConflictButSemanticTamperDoes() throws Exception {
    var i=outputs("audit").stream().filter(o->o.kind().equals("tagged")).findFirst().orElseThrow();var original=project(i,0);
    var changed=(ObjectNode)i.document();((ObjectNode)changed.at("/event/event")).put("ingested","2026-11-17T01:00:00Z");
    ((ObjectNode)changed.at("/event/detectbridge/time")).put("processed","2026-11-17T01:00:00Z");
    var copy=new Machine.Intent(i.sequence(),i.kind(),i.key(),changed);
    assertEquals(original.body().get("content_sha256"),project(copy,41).body().get("content_sha256"));
    ((ObjectNode)changed.at("/event/process")).put("executable","/tampered");
    assertThrows(Projection.Invalid.class,()->project(new Machine.Intent(i.sequence(),i.kind(),i.key(),changed),0));
  }
  @Test void independentLiteralIdentityAndContentVectors() throws Exception {
    var vectors=read("contracts/search-writer/v1/fixtures/expectations.json");var semantic=(ObjectNode)vectors.at("/content_vector/semantic_body");
    var body=semantic.deepCopy();body.put("input_sha256","b".repeat(64));body.putObject("first_input").put("offset",17);body.putObject("evidence_source").put("topic_id","physical");
    ((ObjectNode)body.get("manifest")).put("manifest_id","physical-manifest");
    assertEquals(vectors.at("/content_vector/sha256").asString(),Projection.contentHash(body));
    assertEquals(vectors.at("/failure_vector/sha256").asString(),Projection.failureId(Json.MAPPER.valueToTree(Map.of("cluster_id","cluster-a","topic_id","topic-a","partition",0,"offset",17))));
  }
  @Test void exactTimesAndUnsupportedVersionsAreExplicit() throws Exception {
    var i=outputs("windows").stream().filter(o->o.kind().equals("tagged")).findFirst().orElseThrow();
    for(String timestamp:List.of("2026-01-01T00:00:00.123456789Z","1800-01-01T00:00:00Z")) {
      var changed=(ObjectNode)i.document();((ObjectNode)changed.get("event")).put("@timestamp",timestamp);
      String id=io.detectbridge.detection.IntegrationOutputs.identity("detectbridge.p13.processing/1","p13-runtime/1.0.0",
          changed.at("/event/detectbridge/run_id").asString(),changed.at("/event/event/id").asString(),
          Projection.hash(Projection.semanticEvent(changed.get("event"))),changed.get("attribution"),null);
      changed.put("processing_id",id);
      for(var link:changed.get("matches")) ((ObjectNode)link).put("detection_id",io.detectbridge.detection.IntegrationOutputs.identity("detectbridge.p13.detection/1",id,link.get("id"),link.get("revision")));
      var body=project(new Machine.Intent(i.sequence(),i.kind(),id,changed),0).body();
      assertEquals(timestamp,body.get("original_timestamp"));
      if(timestamp.startsWith("1800")) {assertFalse(body.containsKey("@timestamp"));assertEquals("outside_nanos_range_or_precision",body.get("time_projection_reason"));}
      else assertEquals(timestamp,body.get("@timestamp"));
    }
    var changed=(ObjectNode)i.document();changed.put("version","1.0.0");
    assertThrows(Projection.Invalid.class,()->project(new Machine.Intent(i.sequence(),i.kind(),i.key(),changed),0));
    var big=Json.bytes(Map.of("value",Base64.getEncoder().encodeToString(new byte[2*Json.MAX_VALUE])));
    assertNotNull(Main.injection(big));assertThrows(IllegalArgumentException.class,()->Main.injection(new byte[6*1024*1024+1]));
  }
  static class Fake extends SearchClient {
    Queue<List<Outcome>> outcomes=new ArrayDeque<>();Queue<Response> responses=new ArrayDeque<>();List<List<Projection.Document>> batches=new ArrayList<>();
    Fake() throws Exception {super(URI.create("https://localhost"),SSLContext.getDefault(),null,1);}
    public List<Outcome> bulk(List<Projection.Document> docs) {if(outcomes.isEmpty())return super.bulk(docs);batches.add(List.copyOf(docs));return outcomes.remove();}
    public Response request(String method,String path,byte[] body) {return responses.remove();}
  }
  @Test void partialBulkAndFailureAcknowledgementGateOffsets() throws Exception {
    var i=outputs("windows").stream().filter(o->o.kind().equals("tagged")).findFirst().orElseThrow();var records=List.of(record(i,0),record(i,1));
    var window=new Window(records,config(),new Projection(config()),(k,v)->{});var search=new Fake();
    search.outcomes.add(List.of(SearchClient.Outcome.CREATED,SearchClient.Outcome.RETRY));
    assertThrows(SearchClient.Failure.class,()->window.step(search,(l,b,c)->fail()));assertThrows(IllegalStateException.class,window::offsets);
    search.outcomes.add(List.of(SearchClient.Outcome.PERMANENT));window.step(search,(l,b,c)->fail());assertEquals(1,search.batches.get(1).size());
    assertThrows(RuntimeException.class,()->window.step(search,(l,b,c)->{throw new RuntimeException("no_ack");}));assertFalse(window.complete());
    List<String> failures=new ArrayList<>();window.step(search,(l,b,c)->failures.add(c));assertEquals(List.of("document_rejected"),failures);assertTrue(window.complete());
    assertEquals(2,window.offsets().values().iterator().next().offset());
  }
  @Test void failureInputBlocksWithoutRecursivePublicationAndBindingDriftQuarantines() throws Exception {
    var p=new Projection(config());var input=new ConsumerRecord<byte[],byte[]>(Projection.FAILURES,0,0,null,new byte[]{1});
    var w=new Window(List.of(input),config(),p,(k,v)->{});assertThrows(SearchClient.Failure.class,()->w.step(new Fake(),(l,b,c)->fail()));assertFalse(w.complete());
    var i=outputs("auth").stream().filter(o->o.kind().equals("tagged")).findFirst().orElseThrow();var bad=record(i,0);bad.headers().remove("detectbridge.runtime.binding");
    var unbound=new Window(List.of(bad),config(),p,(k,v)->{});List<String> reasons=new ArrayList<>();unbound.step(new Fake(),(l,b,c)->reasons.add(c));assertEquals(List.of("integration_binding_mismatch"),reasons);
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
        Bootstrap.template(Projection.TAGGED).keySet());
  }

  @Test
  void conflictChecksRecomputeContentAndDoNotTrustStoredHash() throws Exception {
    var i=outputs("windows").stream().filter(o->o.kind().equals("tagged")).findFirst().orElseThrow();
    var d = project(i, 1);
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
    ((tools.jackson.databind.node.ObjectNode) source).put("rule_title", "tampered");
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


}
