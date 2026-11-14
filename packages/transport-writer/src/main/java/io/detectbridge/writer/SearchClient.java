package io.detectbridge.writer;

import io.detectbridge.transport.Json;
import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.Flow;
import javax.net.ssl.*;
import tools.jackson.databind.JsonNode;

/** Bounded TLS REST client. Response text never escapes into operational logs. */
public class SearchClient implements AutoCloseable {
  public enum Kind {
    RETRY,
    BLOCK,
    FATAL
  }

  public static final class Failure extends RuntimeException {
    public final Kind kind;
    public final String category;

    public Failure(Kind kind, String category) {
      super(category);
      this.kind = kind;
      this.category = category;
    }
  }

  public record Response(int status, JsonNode body) {}

  private final HttpClient client;
  private final String authorization;
  private final URI base;
  private final int timeout;

  public SearchClient(URI base, SSLContext ssl, String authorization, int timeout) {
    if (!base.getScheme().equals("https")
        || base.getUserInfo() != null
        || base.getQuery() != null
        || base.getFragment() != null) throw new IllegalArgumentException("unsafe_endpoint");
    this.base = base;
    this.authorization = authorization;
    this.timeout = timeout;
    client =
        HttpClient.newBuilder()
            .sslContext(ssl)
            .connectTimeout(Duration.ofSeconds(5))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();
  }

  public static SSLContext tls(Path ca, Path admin, Path password) throws Exception {
    KeyStore trust = KeyStore.getInstance(KeyStore.getDefaultType());
    trust.load(null, null);
    try (var in = Files.newInputStream(ca)) {
      trust.setCertificateEntry(
          "ca", CertificateFactory.getInstance("X.509").generateCertificate(in));
    }
    var tm = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
    tm.init(trust);
    KeyManager[] keys = null;
    if (admin != null) {
      char[] secret = Files.readString(password).strip().toCharArray();
      KeyStore store = KeyStore.getInstance("PKCS12");
      try (var in = Files.newInputStream(admin)) {
        store.load(in, secret);
      }
      var km = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
      km.init(store, secret);
      keys = km.getKeyManagers();
      Arrays.fill(secret, '\0');
    }
    SSLContext ssl = SSLContext.getInstance("TLS");
    ssl.init(keys, tm.getTrustManagers(), null);
    return ssl;
  }

  public static SearchClient runtime(Path secrets) throws Exception {
    String password = Files.readString(secrets.resolve("writer-password")).strip();
    String auth =
        "Basic "
            + Base64.getEncoder()
                .encodeToString(
                    ("detectbridge_writer_v1:" + password).getBytes(StandardCharsets.UTF_8));
    return new SearchClient(
        URI.create("https://opensearch:9200"),
        tls(secrets.resolve("ca.pem"), null, null),
        auth,
        20);
  }

  public static final class LimitedBody implements HttpResponse.BodySubscriber<byte[]> {
    private final CompletableFuture<byte[]> done = new CompletableFuture<>();
    private final ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    private Flow.Subscription subscription;

    public CompletionStage<byte[]> getBody() {
      return done;
    }

    public void onSubscribe(Flow.Subscription subscription) {
      this.subscription = subscription;
      subscription.request(1);
    }

    public void onNext(List<ByteBuffer> buffers) {
      for (var buffer : buffers) {
        if (bytes.size() + buffer.remaining() > 4 * 1024 * 1024) {
          subscription.cancel();
          done.completeExceptionally(new IOException("response_limit"));
          return;
        }
        byte[] data = new byte[buffer.remaining()];
        buffer.get(data);
        bytes.writeBytes(data);
      }
      subscription.request(1);
    }

    public void onError(Throwable error) {
      done.completeExceptionally(new IOException("response_transport"));
    }

    public void onComplete() {
      done.complete(bytes.toByteArray());
    }
  }

  public Response request(String method, String path, byte[] body) {
    if (!path.startsWith("/") || path.startsWith("//") || path.contains("..") || path.contains("#"))
      throw new IllegalArgumentException("unsafe_path");
    var request =
        HttpRequest.newBuilder(base.resolve(path))
            .timeout(Duration.ofSeconds(timeout))
            .header(
                "Content-Type",
                path.contains("_bulk") ? "application/x-ndjson" : "application/json");
    if (authorization != null) request.header("Authorization", authorization);
    var future =
        client.sendAsync(
            request
                .method(
                    method,
                    body == null
                        ? HttpRequest.BodyPublishers.noBody()
                        : HttpRequest.BodyPublishers.ofByteArray(body))
                .build(),
            r -> new LimitedBody());
    try {
      var response = future.get(timeout, TimeUnit.SECONDS);
      if (response.statusCode() == 401) throw new Failure(Kind.FATAL, "authentication_failed");
      JsonNode value;
      try {
        value =
            response.body().length == 0
                ? Json.MAPPER.createObjectNode()
                : Json.MAPPER.readTree(response.body());
      } catch (Exception ex) {
        throw new Failure(Kind.BLOCK, "malformed_response");
      }
      if (response.statusCode() == 403 && !errorType(value).equals("cluster_block_exception"))
        throw new Failure(Kind.FATAL, "permission_denied");
      return new Response(response.statusCode(), value);
    } catch (Failure ex) {
      throw ex;
    } catch (Exception ex) {
      Throwable cause = ex;
      while (cause != null) {
        if (cause instanceof SSLException) throw new Failure(Kind.FATAL, "tls_failed");
        if (cause instanceof IOException && "response_limit".equals(cause.getMessage()))
          throw new Failure(Kind.BLOCK, "response_limit");
        cause = cause.getCause();
      }
      if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
      throw new Failure(Kind.RETRY, "http_transport_failed");
    } finally {
      if (!future.isDone()) future.cancel(true);
    }
  }

  public static String errorType(JsonNode node) {
    return node.path("error").path("type").asString("");
  }

  public static boolean retryable(int status, JsonNode body) {
    return status == 429
        || status >= 500
        || (status == 403 && errorType(body).equals("cluster_block_exception"));
  }

  private static String operation(String path) {
    if (path.startsWith("/_plugins/_security/api/internalusers/")) return "user";
    if (path.startsWith("/_plugins/_security/api/rolesmapping/")) return "role_mapping";
    if (path.startsWith("/_plugins/_security/api/roles/")) return "role";
    if (path.startsWith("/_index_template/")) return "template";
    if (path.equals("/_aliases")) return "aliases";
    return "index_metadata";
  }

  public JsonNode json(String method, String path, Object body) {
    Response response = request(method, path, body == null ? null : Json.bytes(body));
    if (response.status < 200 || response.status >= 300)
      throw new Failure(
          retryable(response.status, response.body) ? Kind.RETRY : Kind.FATAL,
          "administrative_request_failed_" + response.status + "_" + operation(path));
    return response.body;
  }

  public Map<String, String> fingerprints() {
    Map<String, String> result = new TreeMap<>();
    for (String index : List.of(Projection.REPLAY, Projection.DIAGNOSTICS)) {
      var node = json("GET", "/" + index, null).get(index);
      if (node == null) throw new Failure(Kind.FATAL, "missing_index");
      result.put(
          index,
          Projection.hash(
              Map.of(
                  "mappings",
                  Projection.canonical(node.get("mappings")),
                  "settings",
                  managedSettings(node))));
    }
    return result;
  }

  static Map<String, Object> managedSettings(JsonNode node) {
    var i = node.get("settings").get("index");
    Map<String, Object> settings = new TreeMap<>();
    for (String key :
        List.of(
            "uuid",
            "number_of_shards",
            "number_of_replicas",
            "refresh_interval",
            "default_pipeline",
            "final_pipeline")) settings.put(key, i.path(key).asString(""));
    settings.put("translog_durability", i.path("translog").path("durability").asString(""));
    return settings;
  }

  public void verify(JsonNode config) {
    if (!json("GET", "/", null)
        .path("cluster_uuid")
        .asString("")
        .equals(config.get("opensearch_cluster_id").asString()))
      throw new Failure(Kind.FATAL, "opensearch_cluster_changed");
    var prints = fingerprints();
    for (String index : prints.keySet())
      if (!prints.get(index).equals(config.get("indices").get(index).get("fingerprint").asString()))
        throw new Failure(Kind.FATAL, "index_identity_or_mapping_changed");
  }

  public enum Outcome {
    CREATED,
    DUPLICATE,
    RETRY,
    PERMANENT,
    CONFLICT
  }

  public List<Outcome> bulk(List<Projection.Document> documents) {
    var bytes = new ByteArrayOutputStream();
    for (var doc : documents) {
      bytes.writeBytes(
          Json.bytes(Map.of("create", Map.of("_index", doc.index(), "_id", doc.id()))));
      bytes.write('\n');
      bytes.writeBytes(Json.bytes(doc.body()));
      bytes.write('\n');
    }
    if (bytes.size() > 2 * 1024 * 1024) throw new IllegalArgumentException("bulk_limit");
    Response response = request("POST", "/_bulk?refresh=false", bytes.toByteArray());
    if (retryable(response.status, response.body))
      return Collections.nCopies(documents.size(), Outcome.RETRY);
    if (response.status < 200 || response.status >= 300)
      throw new Failure(Kind.BLOCK, "bulk_request_rejected");
    var items = response.body.get("items");
    if (items == null || !items.isArray() || items.size() != documents.size())
      throw new Failure(Kind.BLOCK, "invalid_bulk_response");
    List<Outcome> result = new ArrayList<>();
    for (int n = 0; n < documents.size(); n++) {
      var doc = documents.get(n);
      var item = items.get(n).get("create");
      if (item == null
          || !item.path("status").isIntegralNumber()
          || !item.path("_id").asString("").equals(doc.id())
          || !item.path("_index").asString("").equals(doc.index()))
        throw new Failure(Kind.BLOCK, "mismatched_bulk_response");
      int status = item.get("status").asInt();
      if (status == 201) {
        result.add(Outcome.CREATED);
        continue;
      }
      if (status == 409 && errorType(item).equals("version_conflict_engine_exception")) {
        var existing = request("GET", "/" + doc.index() + "/_doc/" + doc.id(), null);
        if (existing.status != 200) throw new Failure(Kind.BLOCK, "conflict_document_unavailable");
        var source = existing.body.get("_source");
        if (source == null || !source.isObject())
          throw new Failure(Kind.BLOCK, "conflict_document_unavailable");
        boolean matches = false;
        if (source != null)
          try {
            matches =
                Projection.contentHash(source).equals(doc.body().get("content_sha256"))
                    && source
                        .path("input_sha256")
                        .asString("")
                        .equals(doc.body().get("input_sha256"));
          } catch (IllegalArgumentException ignored) {
            /* Malformed stored content is a conflict, not a trusted duplicate. */
          }
        result.add(matches ? Outcome.DUPLICATE : Outcome.CONFLICT);
      } else if (retryable(status, item)) result.add(Outcome.RETRY);
      else if (status == 400
          && List.of(
                  "mapper_parsing_exception",
                  "document_parsing_exception",
                  "strict_dynamic_mapping_exception",
                  "illegal_argument_exception")
              .contains(errorType(item))) result.add(Outcome.PERMANENT);
      else if (status == 401 || status == 403)
        throw new Failure(Kind.FATAL, "item_permission_denied");
      else throw new Failure(Kind.BLOCK, "unknown_bulk_item_failure");
    }
    return result;
  }

  public static int size(Projection.Document doc) {
    return Json.bytes(Map.of("create", Map.of("_index", doc.index(), "_id", doc.id()))).length
        + Json.bytes(doc.body()).length
        + 2;
  }

  public void close() {
    /* Java 17 HttpClient has no close method. */
  }
}
