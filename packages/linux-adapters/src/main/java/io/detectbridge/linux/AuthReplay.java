package io.detectbridge.linux;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.detection.Evaluator;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.node.ObjectNode;

/** Bounded offline authentication replay of retained inline raw records; no network resolver. */
public final class AuthReplay {
  private AuthReplay() {}

  static long replay(Path input, Path output, Path plan) throws Exception {
    check(!input.toRealPath().equals(output.toAbsolutePath().normalize()), "distinct_output_required");
    Evaluator evaluator = new Evaluator(Files.readAllBytes(plan));
    Path destination = output.toAbsolutePath();
    Path temp = Files.createTempFile(destination.getParent(), ".auth-replay-", ".tmp");
    long count = 0;
    try {
      try (InputStream in = Files.newInputStream(input);
           FileChannel out = FileChannel.open(temp, StandardOpenOption.WRITE)) {
        byte[] line;
        while ((line = line(in)) != null) {
          var row = Json.read(line);
          check(row.isObject() && row.size() == 2 && row.has("raw") && row.has("context"), "input_shape");
          var resolved = Boundary.resolve(row.get("raw"), row.get("context"), evidence -> {
            check(evidence.has("inline"), "inline_record_required");
            return evidence.get("encoding").asString().equals("utf-8")
                ? evidence.get("inline").asString().getBytes(StandardCharsets.UTF_8)
                : Base64.getDecoder().decode(evidence.get("inline").asString());
          });
          var adapted = OpenSsh.adapt(resolved);
          ObjectNode result = Json.MAPPER.createObjectNode();
          result.put("version", "1.0.0"); result.set("raw", resolved.raw()); result.set("context", resolved.context());
          if (adapted.has("@timestamp")) {
            result.set("event", adapted); byte[] bytes = Json.bytes(adapted);
            result.set("evaluation", evaluator.evaluate(bytes, Map.of("cluster_id", "offline", "topic_id", "offline",
                "topic", "linux-auth-offline", "partition", 0, "offset", count, "value_sha256", Json.sha(bytes))));
          } else result.set("preservation", adapted);
          byte[] data = Json.bytes(result);
          ByteBuffer buffer = ByteBuffer.wrap(data);
          while (buffer.hasRemaining()) out.write(buffer);
          out.write(ByteBuffer.wrap(new byte[]{'\n'})); count++;
        }
        out.force(true);
      }
      Files.move(temp, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
      return count;
    } finally { Files.deleteIfExists(temp); }
  }

  private static byte[] line(InputStream in) throws IOException {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream(); int b;
    while ((b = in.read()) != -1 && b != '\n') {
      check(bytes.size() < Json.MAX_VALUE, "input_row_limit"); bytes.write(b);
    }
    return b == -1 && bytes.size() == 0 ? null : bytes.toByteArray();
  }

  public static void main(String[] args) {
    try {
      check(args.length == 3, "arguments");
      long count = replay(Path.of(args[0]), Path.of(args[1]), Path.of(args[2]));
      System.out.println("{\"status\":\"published\",\"records\":" + count + "}");
    } catch (Exception e) {
      System.err.println("{\"category\":\"auth_replay_failed\"}"); System.exit(1);
    }
  }
}
