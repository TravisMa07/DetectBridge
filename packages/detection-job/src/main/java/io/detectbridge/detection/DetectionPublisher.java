package io.detectbridge.detection;

import io.detectbridge.transport.Json;
import java.io.ByteArrayOutputStream;
import java.time.Duration;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;

/** Private bounded JSON-line IPC. Payload IPC is never forwarded to operator logs. */
public final class DetectionPublisher {
  private static final Base64.Decoder DECODE = Base64.getDecoder();
  private static final Base64.Encoder ENCODE = Base64.getEncoder();

  private static void emit(Object value) {
    System.out.println(Json.MAPPER.writeValueAsString(value));
    System.out.flush();
  }

  private static byte[] line() throws Exception {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    int c;
    while ((c = System.in.read()) != -1) {
      if (c == '\n') return bytes.toByteArray();
      if (bytes.size() >= 2 * Json.MAX_VALUE) throw new IllegalArgumentException("ipc_limit");
      bytes.write(c);
    }
    return bytes.size() == 0 ? null : bytes.toByteArray();
  }

  private static void publish(String bootstrap, String topic, boolean validate) throws Exception {
    long count = 0;
    try (KafkaProducer<byte[], byte[]> producer =
        new KafkaProducer<>(DetectionBroker.producerProperties(bootstrap))) {
      byte[] line;
      while ((line = line()) != null) {
        JsonNode input = Json.MAPPER.readTree(line);
        byte[] key = input.get("key").isNull() ? null : DECODE.decode(input.get("key").asString());
        byte[] value =
            input.get("value").isNull() ? null : DECODE.decode(input.get("value").asString());
        if ((value != null && value.length > Json.MAX_VALUE) || (key != null && key.length > 1024))
          throw new IllegalArgumentException("value_limit");
        var meta = producer.send(new ProducerRecord<>(topic, key, value)).get(35, TimeUnit.SECONDS);
        emit(
            Map.of(
                "type",
                "ack",
                "sequence",
                input.get("sequence").asLong(),
                "partition",
                meta.partition(),
                "offset",
                meta.offset(),
                "key_sha256",
                Json.sha(key == null ? new byte[0] : key),
                "value_sha256",
                Json.sha(value == null ? new byte[0] : value)));
        count++;
      }
      producer.flush();
    }
    emit(Map.of("type", "end", "count", count));
  }

  private static void read(String bootstrap, String topic, long start, long stop) throws Exception {
    if (stop < start || stop - start > 200_000) throw new IllegalArgumentException("read_limit");
    Properties p = DetectionBroker.properties(bootstrap);
    p.put("key.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
    p.put("value.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
    p.put("enable.auto.commit", "false");
    p.put("auto.offset.reset", "none");
    p.put("max.poll.records", "100");
    p.put("fetch.max.bytes", "4194304");
    p.put("max.partition.fetch.bytes", "2097152");
    try (KafkaConsumer<byte[], byte[]> consumer = new KafkaConsumer<>(p)) {
      TopicPartition part = new TopicPartition(topic, 0);
      consumer.assign(List.of(part));
      consumer.seek(part, start);
      long deadline = System.nanoTime() + Duration.ofSeconds(30).toNanos();
      while (consumer.position(part) < stop) {
        if (System.nanoTime() > deadline) throw new IllegalStateException("read_incomplete");
        for (var record : consumer.poll(Duration.ofMillis(200))) {
          if (record.offset() >= stop) break;
          var item = new java.util.LinkedHashMap<String, Object>();
          item.put("offset", record.offset());
          item.put("partition", record.partition());
          item.put("key", record.key() == null ? null : ENCODE.encodeToString(record.key()));
          item.put("value", record.value() == null ? null : ENCODE.encodeToString(record.value()));
          emit(item);
        }
      }
    }
    emit(Map.of("type", "end"));
  }

  public static void main(String[] args) {
    try {
      switch (args[1]) {
        case "init", "describe" ->
            emit(
                DetectionBroker.describe(
                    args[0], args[1].equals("init"), args.length > 2 ? args[2] : null));
        case "inject" -> publish(args[0], args[2], false);
        case "group-offset" ->
            emit(Map.of("offset", DetectionBroker.groupOffset(args[0], args[2])));
        case "read" -> read(args[0], args[2], Long.parseLong(args[3]), Long.parseLong(args[4]));
        default -> throw new IllegalArgumentException("unknown_operation");
      }
    } catch (Exception ex) {
      Throwable reason = ex;
      while (reason.getCause() != null) reason = reason.getCause();
      emit(
          Map.of(
              "status",
              "failed",
              "category",
              "broker_operation_failed",
              "reason_type",
              reason.getClass().getSimpleName()));
      System.exit(1);
    }
  }
}
