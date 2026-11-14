package io.detectbridge.writer;

import com.sun.net.httpserver.HttpServer;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.KafkaException;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;

public final class Main {
  private static final ConcurrentHashMap<String, java.util.concurrent.atomic.LongAdder> COUNTERS =
      new ConcurrentHashMap<>();
  private static final AtomicReference<String> STATE = new AtomicReference<>("STARTING");
  private static final AtomicReference<String> REASON = new AtomicReference<>("none");
  private static final AtomicLong BLOCKED_SINCE = new AtomicLong();
  private static final AtomicLong LAG_AT = new AtomicLong();
  private static final ConcurrentHashMap<String, Long> LAG = new ConcurrentHashMap<>();

  static void state(String value) {
    STATE.set(STOP_REQUESTED.get() ? "STOPPING" : value);
    if (value.equals("BACKPRESSURED")) BLOCKED_SINCE.compareAndSet(0, System.nanoTime());
    else BLOCKED_SINCE.set(0);
  }

  static void lag(KafkaConsumer<byte[], byte[]> consumer) {
    long now = System.nanoTime();
    if (LAG_AT.get() != 0 && now - LAG_AT.get() < 5_000_000_000L) return;
    var parts = consumer.assignment();
    if (parts.isEmpty()) return;
    try {
      var ends = consumer.endOffsets(parts, Duration.ofSeconds(2));
      var committed = consumer.committed(parts, Duration.ofSeconds(2));
      for (var part : parts) {
        var offset = committed.get(part);
        if (offset != null) LAG.put(part.topic(), Math.max(0, ends.get(part) - offset.offset()));
      }
      LAG_AT.set(System.nanoTime());
    } catch (org.apache.kafka.common.KafkaException ex) {
      LAG.clear();
      metric("lag_probe_failures", 1);
      LAG_AT.set(System.nanoTime());
    }
  }

  private static final AtomicBoolean RUNNING = new AtomicBoolean(true);
  private static final AtomicBoolean STOP_REQUESTED = new AtomicBoolean();
  private static final AtomicLong STOP_DEADLINE = new AtomicLong();

  static void metric(String name, long value) {
    COUNTERS.computeIfAbsent(name, k -> new java.util.concurrent.atomic.LongAdder()).add(value);
  }

  static Map<String, Object> health() {
    var result = new TreeMap<String, Object>();
    result.put("state", STATE.get());
    result.put("category", REASON.get());
    var metrics = new TreeMap<String, Long>();
    COUNTERS.forEach((k, v) -> metrics.put(k, v.sum()));
    result.put("counters", metrics);
    return result;
  }

  static HttpServer server() throws Exception {
    var server = HttpServer.create(new InetSocketAddress("0.0.0.0", 9250), 8);
    server.createContext(
        "/health",
        exchange -> {
          byte[] body = Json.bytes(health());
          exchange.getResponseHeaders().set("Content-Type", "application/json");
          exchange.sendResponseHeaders(STATE.get().equals("READY") ? 200 : 503, body.length);
          try (var out = exchange.getResponseBody()) {
            out.write(body);
          }
        });
    server.createContext(
        "/metrics",
        exchange -> {
          StringBuilder text = new StringBuilder();
          COUNTERS.forEach(
              (k, v) ->
                  text.append("detectbridge_writer_")
                      .append(k)
                      .append("_total ")
                      .append(v.sum())
                      .append('\n'));
          text.append("detectbridge_writer_backpressured ")
              .append(STATE.get().equals("BACKPRESSURED") ? 1 : 0)
              .append('\n');
          long blocked = BLOCKED_SINCE.get();
          text.append("detectbridge_writer_blocked_seconds ")
              .append(blocked == 0 ? 0 : (System.nanoTime() - blocked) / 1_000_000_000.0)
              .append('\n');
          for (String topic : Projection.TOPICS)
            text.append("detectbridge_writer_lag{topic=\"")
                .append(topic)
                .append("\"} ")
                .append(LAG.containsKey(topic) ? LAG.get(topic).toString() : "NaN")
                .append('\n');
          text.append("detectbridge_writer_lag_observation_age_seconds ")
              .append(
                  LAG_AT.get() == 0
                      ? "NaN"
                      : Double.toString((System.nanoTime() - LAG_AT.get()) / 1_000_000_000.0))
              .append('\n');
          byte[] body = text.toString().getBytes(StandardCharsets.UTF_8);
          exchange.getResponseHeaders().set("Content-Type", "text/plain; version=0.0.4");
          exchange.sendResponseHeaders(200, body.length);
          try (var out = exchange.getResponseBody()) {
            out.write(body);
          }
        });
    server.start();
    return server;
  }

  static Map<TopicPartition, Long> rewindOffsets(
      ConsumerRecords<byte[], byte[]> records, Set<TopicPartition> assigned) {
    Map<TopicPartition, Long> result = new HashMap<>();
    for (var part : records.partitions())
      if (assigned.contains(part))
        result.put(
            part,
            records.records(part).stream().mapToLong(ConsumerRecord::offset).min().orElseThrow());
    return result;
  }

  static void maintenancePoll(KafkaConsumer<byte[], byte[]> consumer) {
    consumer.pause(consumer.assignment());
    var records = consumer.poll(Duration.ofMillis(200));
    rewindOffsets(records, consumer.assignment()).forEach(consumer::seek);
  }

  static <T> T await(
      Future<T> operation,
      KafkaConsumer<byte[], byte[]> consumer,
      AtomicLong epoch,
      long startEpoch)
      throws Exception {
    long deadline = System.nanoTime() + Duration.ofSeconds(35).toNanos();
    try {
      while (!operation.isDone()) {
        if (!RUNNING.get()
            || System.nanoTime() > deadline
            || (STOP_REQUESTED.get() && System.nanoTime() > STOP_DEADLINE.get())) {
          operation.cancel(true);
          throw new SearchClient.Failure(
              RUNNING.get() && !STOP_REQUESTED.get()
                  ? SearchClient.Kind.FATAL
                  : SearchClient.Kind.RETRY,
              "operation_interrupted_or_timed_out");
        }
        maintenancePoll(consumer);
      }
      T value = operation.get();
      if (epoch.get() != startEpoch) throw new Reassigned();
      return value;
    } catch (ExecutionException ex) {
      if (ex.getCause() instanceof SearchClient.Failure f) throw f;
      if (ex.getCause() instanceof IllegalStateException)
        throw new SearchClient.Failure(
            SearchClient.Kind.FATAL, "source_identity_or_policy_changed");
      throw new SearchClient.Failure(SearchClient.Kind.RETRY, "dependency_unavailable");
    }
  }

  static final class MembershipSignal implements ConsumerRebalanceListener {
    final AtomicBoolean joined = new AtomicBoolean();
    final AtomicInteger assigned = new AtomicInteger(-1);

    public void onPartitionsRevoked(Collection<TopicPartition> parts) {}

    public void onPartitionsAssigned(Collection<TopicPartition> parts) {
      assigned.set(parts.size());
      joined.set(true);
    }
  }

  static final class Reassigned extends RuntimeException {}

  static void serve(Path directory) throws Exception {
    JsonNode config =
        Json.MAPPER.readTree(Files.readAllBytes(directory.resolve("configuration.json")));
    var projection = new Projection(config);
    projection.require("configuration", config);
    if (!Json.sha(Files.readAllBytes(directory.resolve("writer-password")))
            .equals(config.get("password_sha256").asString())
        || !Json.sha(Files.readAllBytes(directory.resolve("ca.pem")))
            .equals(config.get("ca_sha256").asString()))
      throw new IllegalStateException("credential_changed");
    Bootstrap.kafka(config, false);
    var props = Broker.properties("kafka:9092");
    props.put("group.id", config.get("consumer_group").asString());
    props.put("enable.auto.commit", "false");
    props.put("auto.offset.reset", "none");
    props.put("key.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
    props.put("value.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
    props.put("max.poll.records", "100");
    props.put("fetch.max.bytes", "4194304");
    props.put("max.partition.fetch.bytes", "2097152");
    props.put("max.poll.interval.ms", "300000");
    props.put("allow.auto.create.topics", "false");
    var epoch = new AtomicLong();
    var stopped = new CountDownLatch(1);
    Runtime.getRuntime()
        .addShutdownHook(
            new Thread(
                () -> {
                  STOP_DEADLINE.set(System.nanoTime() + Duration.ofSeconds(15).toNanos());
                  STOP_REQUESTED.set(true);
                  try {
                    stopped.await(30, TimeUnit.SECONDS);
                  } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                  }
                }));
    HttpServer server = server();
    ExecutorService executor =
        new ThreadPoolExecutor(1, 1, 0, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(1));
    var consumer = new KafkaConsumer<byte[], byte[]>(props);
    var producer = new KafkaProducer<byte[], byte[]>(Broker.producerProperties("kafka:9092"));
    try (var search = SearchClient.runtime(directory)) {
      search.verify(config);
      consumer.subscribe(
          Projection.TOPICS,
          new ConsumerRebalanceListener() {
            public void onPartitionsRevoked(Collection<TopicPartition> parts) {
              epoch.incrementAndGet();
            }

            public void onPartitionsAssigned(Collection<TopicPartition> parts) {
              if (parts.isEmpty()) {
                epoch.incrementAndGet();
                return;
              }
              var committed = consumer.committed(new HashSet<>(parts));
              for (var part : parts) {
                var value = committed.get(part);
                if (value == null)
                  throw new SearchClient.Failure(
                      SearchClient.Kind.FATAL, "missing_committed_offset");
                consumer.seek(part, value.offset());
              }
              consumer.pause(parts);
              epoch.incrementAndGet();
            }
          });
      Window window = null;
      long windowEpoch = 0;
      int attempts = 0;
      long next = 0;
      while (RUNNING.get()) {
        try {
          if (STOP_REQUESTED.get() && (window == null || System.nanoTime() > STOP_DEADLINE.get()))
            break;
          lag(consumer);
          if (window == null) {
            consumer.resume(consumer.assignment());
            var polled = consumer.poll(Duration.ofMillis(200));
            if (!consumer.assignment().isEmpty()) state("READY");
            if (polled.isEmpty()) continue;
            List<ConsumerRecord<byte[], byte[]>> records = new ArrayList<>();
            polled.forEach(records::add);
            consumer.pause(consumer.assignment());
            window = new Window(records, config, projection, Main::metric);
            windowEpoch = epoch.get();
            attempts = 0;
            next = 0;
          }
          if (epoch.get() != windowEpoch) {
            window = null;
            continue;
          }
          if (System.nanoTime() < next) {
            maintenancePoll(consumer);
            continue;
          }
          Window current = window;
          await(
              executor.submit(
                  () -> {
                    search.verify(config);
                    if (!current.complete())
                      current.step(
                          search,
                          (location, value, category) -> {
                            var failure = projection.failure(location, value, category);
                            try {
                              producer
                                  .send(
                                      new ProducerRecord<>(
                                          Projection.FAILURES,
                                          failure
                                              .get("failure_id")
                                              .toString()
                                              .getBytes(StandardCharsets.UTF_8),
                                          Json.bytes(failure)))
                                  .get(30, TimeUnit.SECONDS);
                            } catch (Exception ex) {
                              throw new SearchClient.Failure(
                                  SearchClient.Kind.RETRY, "failure_topic_unavailable");
                            }
                          });
                    if (current.complete()) {
                      search.verify(config);
                      Bootstrap.kafka(config, false);
                    }
                    return true;
                  }),
              consumer,
              epoch,
              windowEpoch);
          attempts = 0;
          REASON.set("none");
          state("READY");
          if (window.complete()) {
            try {
              consumer.commitSync(window.offsets(), Duration.ofSeconds(5));
              metric("committed_windows", 1);
              window = null;
            } catch (KafkaException ex) {
              metric("commit_failures", 1);
              throw new SearchClient.Failure(SearchClient.Kind.RETRY, "offset_commit_failed");
            }
          }
        } catch (Reassigned ex) {
          window = null;
          metric("rebalances", 1);
        } catch (SearchClient.Failure ex) {
          if (ex.kind == SearchClient.Kind.FATAL) throw ex;
          attempts++;
          metric("retries", 1);
          REASON.set(ex.category);
          state("BACKPRESSURED");
          long seconds =
              ex.kind == SearchClient.Kind.BLOCK || attempts >= 5
                  ? 30
                  : Math.min(30, 1L << (attempts - 1));
          double jitter = ThreadLocalRandom.current().nextDouble(0.8, 1.2);
          double delay =
              ex.kind == SearchClient.Kind.BLOCK || attempts >= 5
                  ? 30.0
                  : Math.min(30.0, seconds * jitter);
          next = System.nanoTime() + (long) (delay * 1_000_000_000L);
        } catch (org.apache.kafka.common.errors.OffsetOutOfRangeException
            | org.apache.kafka.clients.consumer.NoOffsetForPartitionException ex) {
          throw new IllegalStateException("missing_or_expired_offset");
        } catch (org.apache.kafka.common.KafkaException ex) {
          Throwable cause = ex;
          while (cause != null) {
            if (cause instanceof SearchClient.Failure f && f.kind == SearchClient.Kind.FATAL)
              throw f;
            cause = cause.getCause();
          }
          metric("kafka_errors", 1);
          state("BACKPRESSURED");
          REASON.set("kafka_unavailable");
          Thread.sleep(1000);
        }
      }
      state("STOPPING");
    } finally {
      RUNNING.set(false);
      executor.shutdownNow();
      try {
        producer.close(Duration.ofSeconds(5));
      } finally {
        try {
          consumer.close(Duration.ofSeconds(5));
        } finally {
          server.stop(0);
          stopped.countDown();
        }
      }
    }
  }

  public static void main(String[] args) {
    try {
      if (args.length != 2) throw new IllegalArgumentException("arguments");
      Path directory = Path.of(args[1]);
      switch (args[0]) {
        case "admin" ->
            System.out.println(
                Json.MAPPER.writeValueAsString(
                    Bootstrap.provision(
                        Json.MAPPER.readTree(Files.readAllBytes(directory.resolve("pending.json"))),
                        directory)));
        case "serve" -> serve(directory);
        case "inject-batch" -> {
          byte[] bytes = System.in.readNBytes(65537);
          if (bytes.length > 65536) throw new IllegalArgumentException("probe_limit");
          var input = Json.read(bytes);
          if (!input.isArray() || input.size() != 2)
            throw new IllegalArgumentException("batch_requires_two");
          var records = new ArrayList<ProducerRecord<byte[], byte[]>>();
          var validator = new io.detectbridge.transport.EnvelopeValidator();
          for (var item : input) {
            byte[] key = Base64.getDecoder().decode(item.get("key").asString());
            byte[] value = Base64.getDecoder().decode(item.get("value").asString());
            if (validator.validate(key, value) != null)
              throw new IllegalArgumentException("invalid_batch_envelope");
            records.add(new ProducerRecord<>(Projection.OUTPUT, 0, key, value));
          }
          var props = Broker.producerProperties("kafka:9092");
          props.put("linger.ms", "5000");
          props.put("batch.size", "65536");
          var producer = new KafkaProducer<byte[], byte[]>(props);
          try {
            var sent = new ArrayList<Future<RecordMetadata>>();
            for (var record : records) sent.add(producer.send(record));
            producer.flush();
            List<Object> receipts = new ArrayList<>();
            for (var future : sent) {
              var metadata = future.get(30, TimeUnit.SECONDS);
              receipts.add(Map.of("partition", metadata.partition(), "offset", metadata.offset()));
            }
            System.out.println(
                Json.MAPPER.writeValueAsString(
                    Map.of("status", "acknowledged", "receipts", receipts)));
          } finally {
            producer.close(Duration.ofSeconds(5));
          }
        }
        case "membership" -> {
          var config =
              Json.MAPPER.readTree(Files.readAllBytes(directory.resolve("configuration.json")));
          var props = Broker.properties("kafka:9092");
          props.put("group.id", config.get("consumer_group").asString());
          props.put("client.id", "zzzz-writer-membership-check");
          props.put(
              "partition.assignment.strategy", "org.apache.kafka.clients.consumer.RangeAssignor");
          props.put("enable.auto.commit", "false");
          props.put("auto.offset.reset", "none");
          props.put("max.poll.records", "1");
          props.put("fetch.max.bytes", "4194304");
          props.put("max.partition.fetch.bytes", "2097152");
          props.put(
              "key.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
          props.put(
              "value.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
          var consumer = new KafkaConsumer<byte[], byte[]>(props);
          var membership = new MembershipSignal();
          try {
            consumer.subscribe(Projection.TOPICS, membership);
            long deadline = System.nanoTime() + Duration.ofSeconds(20).toNanos();
            while (!membership.joined.get() && System.nanoTime() < deadline)
              consumer.poll(Duration.ofMillis(200));
            if (!membership.joined.get())
              throw new IllegalStateException("membership_assignment_timeout");
            long hold = System.nanoTime() + Duration.ofSeconds(5).toNanos();
            while (System.nanoTime() < hold) consumer.poll(Duration.ofMillis(200));
          } finally {
            consumer.close(Duration.ofSeconds(5));
          }
          System.out.println(
              Json.MAPPER.writeValueAsString(
                  Map.of(
                      "status",
                      "membership_checked",
                      "assigned_partitions",
                      membership.assigned.get())));
        }
        case "probe" -> {
          byte[] bytes = System.in.readNBytes(65537);
          if (bytes.length > 65536) throw new IllegalArgumentException("probe_limit");
          var request = Json.read(bytes);
          try (var client = SearchClient.runtime(directory)) {
            var response =
                client.request(
                    request.get("method").asString(),
                    request.get("path").asString(),
                    request.has("ndjson")
                        ? request.get("ndjson").asString().getBytes(StandardCharsets.UTF_8)
                        : request.has("body") ? Json.bytes(request.get("body")) : null);
            System.out.println(
                Json.MAPPER.writeValueAsString(
                    Map.of("status", response.status(), "body", response.body())));
          } catch (SearchClient.Failure ex) {
            if (ex.category.equals("permission_denied")
                || ex.category.equals("authentication_failed"))
              System.out.println(
                  Json.MAPPER.writeValueAsString(
                      Map.of(
                          "status",
                          ex.category.equals("permission_denied") ? 403 : 401,
                          "body",
                          Map.of())));
            else throw ex;
          }
        }
        default -> throw new IllegalArgumentException("unsupported_command");
      }
    } catch (Exception ex) {
      STATE.set("FATAL");
      String category = ex instanceof SearchClient.Failure f ? f.category : "writer_failed";
      if (ex instanceof IllegalStateException
          && Set.of(
                  "membership_assignment_timeout",
                  "writer_role_drift",
                  "writer_user_drift",
                  "writer_role_mapping_drift",
                  "template_drift",
                  "index_mapping_drift",
                  "alias_drift",
                  "topic_topology_changed",
                  "topic_policy_changed",
                  "topic_recreated",
                  "kafka_cluster_changed",
                  "writer_group_active",
                  "partial_group_offsets_require_review",
                  "writer_role_missing",
                  "writer_user_missing",
                  "writer_mapping_missing",
                  "template_missing",
                  "index_missing",
                  "alias_read_failed")
              .contains(ex.getMessage())) category = ex.getMessage();
      System.err.println(
          Json.MAPPER.writeValueAsString(
              Map.of(
                  "status",
                  "failed",
                  "category",
                  category,
                  "reason_type",
                  ex.getClass().getSimpleName())));
      System.exit(1);
    }
  }
}
