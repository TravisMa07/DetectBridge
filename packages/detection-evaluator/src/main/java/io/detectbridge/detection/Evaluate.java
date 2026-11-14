package io.detectbridge.detection;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.Map;

/** Offline one-event interface. stdout is explicit result output, never an operational log. */
public final class Evaluate {
  public static byte[] bounded(Path path, int max) throws java.io.IOException {
    try (var input = Files.newInputStream(path)) {
      byte[] value = input.readNBytes(max + 1);
      Contracts.check(value.length <= max, "input_limit");
      return value;
    }
  }

  public static void main(String[] args) {
    try {
      Contracts.check(args.length == 2, "arguments");
      Evaluator evaluator = new Evaluator(bounded(Path.of(args[0]), 4 * 1024 * 1024));
      byte[] event = bounded(Path.of(args[1]), 1024 * 1024);
      System.out.println(
          evaluator.evaluate(
              event,
              Map.of(
                  "cluster_id",
                  "offline",
                  "topic_id",
                  "offline",
                  "topic",
                  "offline",
                  "partition",
                  0,
                  "offset",
                  0,
                  "value_sha256",
                  Json.sha(event))));
    } catch (Exception e) {
      System.err.println("{\"category\":\"evaluation_input_failure\",\"pointer\":\"\"}");
      System.exit(1);
    }
  }
}
