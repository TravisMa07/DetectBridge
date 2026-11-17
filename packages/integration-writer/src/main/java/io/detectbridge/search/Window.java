package io.detectbridge.search;

import java.util.*;
import java.util.function.BiConsumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import tools.jackson.databind.JsonNode;

/** One bounded consumed window. No consumer offset is advanced here. */
public final class Window {
  public interface Failures {
    void publish(Projection.Location location, byte[] value, String category);
  }

  static final class Item {
    final ConsumerRecord<byte[], byte[]> input;
    Projection.Document doc;
    String failure;
    boolean done;

    Item(ConsumerRecord<byte[], byte[]> input) {
      this.input = input;
    }
  }

  private final List<Item> items = new ArrayList<>();
  private final JsonNode config;
  private final Projection projector;
  private final BiConsumer<String, Long> metric;

  public Window(
      List<ConsumerRecord<byte[], byte[]>> records,
      JsonNode config,
      Projection projector,
      BiConsumer<String, Long> metric) {
    if (records.stream()
        .anyMatch(record -> record.partition() != 0 || !Projection.TOPICS.contains(record.topic())))
      throw new SearchClient.Failure(SearchClient.Kind.FATAL, "source_topology_changed");
    if (records.size() > 100)
      throw new SearchClient.Failure(SearchClient.Kind.FATAL, "pending_record_limit");
    long bytes = 0;
    for (var r : records)
      bytes += (r.value() == null ? 0 : r.value().length) + (r.key() == null ? 0 : r.key().length);
    if (bytes > 16 * 1024 * 1024)
      throw new SearchClient.Failure(SearchClient.Kind.FATAL, "pending_byte_limit");
    this.config = config;
    this.projector = projector;
    this.metric = metric;
    for (var record : records) {
      var item = new Item(record);
      try {
        item.doc =
            projector.project(record.topic(), record.key(), record.value(), location(record));
        if (!record.topic().equals(Projection.FAILURES)) {
          var header = record.headers().lastHeader("detectbridge.runtime.binding");
          if (header == null || !java.util.Arrays.equals(header.value(),
              config.get("integration_binding").asString().getBytes(java.nio.charset.StandardCharsets.UTF_8)))
            throw new Projection.Invalid("integration_binding_mismatch");
        }
      } catch (Projection.Invalid ex) {
        item.failure = ex.category;
      }
      if (item.doc != null && SearchClient.size(item.doc) > 2 * 1024 * 1024)
        item.failure = "document_rejected";
      items.add(item);
    }
  }

  private Projection.Location location(ConsumerRecord<byte[], byte[]> r) {
    return new Projection.Location(
        config.get("kafka_cluster_id").asString(),
        config.get("source_topics").get(r.topic()).get("id").asString(),
        r.topic(),
        r.partition(),
        r.offset());
  }

  public boolean complete() {
    return items.stream().allMatch(i -> i.done);
  }

  public void step(SearchClient search, Failures failures) {
    for (var item : items)
      if (!item.done && item.failure != null) {
        if (item.input.topic().equals(Projection.FAILURES))
          throw new SearchClient.Failure(SearchClient.Kind.BLOCK, "diagnostic_unindexable");
        failures.publish(location(item.input), item.input.value(), item.failure);
        item.done = true;
        metric.accept("quarantined", 1L);
        return;
      }
    List<Item> batch = new ArrayList<>();
    int size = 0;
    for (var item : items)
      if (!item.done) {
        int next = SearchClient.size(item.doc);
        if (!batch.isEmpty() && size + next > 2 * 1024 * 1024) break;
        batch.add(item);
        size += next;
      }
    if (batch.isEmpty()) return;
    var results = search.bulk(batch.stream().map(i -> i.doc).toList());
    boolean retry = false;
    for (int n = 0; n < batch.size(); n++) {
      var item = batch.get(n);
      switch (results.get(n)) {
        case CREATED -> {
          item.done = true;
          metric.accept("indexed", 1L);
        }
        case DUPLICATE -> {
          item.done = true;
          metric.accept("duplicates", 1L);
        }
        case PERMANENT -> item.failure = "document_rejected";
        case CONFLICT -> item.failure = "identity_conflict";
        case RETRY -> retry = true;
      }
    }
    if (retry) throw new SearchClient.Failure(SearchClient.Kind.RETRY, "transient_bulk_items");
  }

  public Map<
          org.apache.kafka.common.TopicPartition,
          org.apache.kafka.clients.consumer.OffsetAndMetadata>
      offsets() {
    if (!complete()) throw new IllegalStateException("unresolved_window");
    Map<org.apache.kafka.common.TopicPartition, org.apache.kafka.clients.consumer.OffsetAndMetadata>
        offsets = new HashMap<>();
    for (var item : items)
      offsets.put(
          new org.apache.kafka.common.TopicPartition(item.input.topic(), item.input.partition()),
          new org.apache.kafka.clients.consumer.OffsetAndMetadata(item.input.offset() + 1));
    return offsets;
  }
}
