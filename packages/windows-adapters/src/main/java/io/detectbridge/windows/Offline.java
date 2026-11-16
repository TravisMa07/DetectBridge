package io.detectbridge.windows;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.detection.Evaluate;
import io.detectbridge.detection.Evaluator;
import io.detectbridge.detection.IntegrationOutputs;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;

/** Offline complete-file transaction. It does not claim Kafka acceptance or archive durability. */
public final class Offline {
  @FunctionalInterface interface BeforePublish { void run() throws IOException; }
  public static long run(Path input, Path output, EvidenceResolver resolver, Evaluator evaluator) throws IOException {
    return run(input, output, resolver, evaluator, () -> {});
  }
  static long run(Path input, Path output, EvidenceResolver resolver, Evaluator evaluator, BeforePublish hook) throws IOException {
    return run(input, output, resolver, evaluator, hook, false);
  }
  public static long runIntegrated(Path input, Path output, EvidenceResolver resolver, Evaluator evaluator) throws IOException {
    return run(input, output, resolver, evaluator, () -> {}, true);
  }
  private static long run(Path input, Path output, EvidenceResolver resolver, Evaluator evaluator, BeforePublish hook, boolean integrated) throws IOException {
    check(!input.toRealPath().equals(output.toAbsolutePath().normalize())
        && (!Files.exists(output) || !Files.isSameFile(input, output)), "distinct_output_required");
    var adapter = new WindowsAdapter();
    IntegrationOutputs outputs = integrated ? new IntegrationOutputs(Objects.requireNonNull(evaluator)) : null;
    if (evaluator != null) evaluator.requireMappedDeployment();
    Path destination = output.toAbsolutePath(), parent = destination.getParent();
    Path temporary = Files.createTempFile(parent, ".windows-", ".tmp");
    long count = 0;
    try {
      try (var in = new BufferedInputStream(Files.newInputStream(input));
          var out = FileChannel.open(temporary, StandardOpenOption.WRITE)) {
        byte[] line;
        while ((line = line(in)) != null) {
          var row = Json.read(line);
          Boundary.keys(row, Set.of("raw", "context"), Set.of());
          var result = adapter.adapt(row.get("raw"), resolver, row.get("context"));
          Map<String, Object> published = new LinkedHashMap<>();
          published.put("version", "1.0.0"); published.put("context", row.get("context"));
          published.put("raw", row.get("raw"));
          if (result.preserved()) published.put("preservation", result.diagnostic());
          else {
            published.put("event", result.event());
            if (evaluator != null) {
              byte[] event = Json.bytes(result.event());
              if (integrated) published.put("integration", outputs.process(result.event(), null));
              else published.put("evaluation", evaluator.evaluate(event, Map.of("cluster_id", "offline", "topic_id", "offline",
                  "topic", "windows-offline", "partition", 0, "offset", count, "value_sha256", Json.sha(event))));
            }
          }
          byte[] data = Json.bytes(published);
          ByteBuffer buffer = ByteBuffer.wrap(data);
          while (buffer.hasRemaining()) out.write(buffer);
          out.write(ByteBuffer.wrap(new byte[]{'\n'}));
          count++;
        }
        out.force(true);
      }
      hook.run();
      Files.move(temporary, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
      return count;
    } finally { Files.deleteIfExists(temporary); }
  }
  private static byte[] line(InputStream in) throws IOException {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    int b;
    while ((b = in.read()) != -1 && b != '\n') {
      check(bytes.size() < Json.MAX_VALUE, "input_row_limit"); bytes.write(b);
    }
    return b == -1 && bytes.size() == 0 ? null : bytes.toByteArray();
  }
  public static void main(String[] args) {
    try {
      check(args.length == 3 || args.length == 4 || (args.length == 5 && args[4].equals("--integrated")), "arguments");
      Evaluator evaluator = args.length >= 4 ? new Evaluator(Evaluate.bounded(Path.of(args[3]), 4 * 1024 * 1024)) : null;
      if (args.length >= 4) check(!Path.of(args[3]).toRealPath().equals(Path.of(args[1]).toAbsolutePath().normalize())
          && (!Files.exists(Path.of(args[1])) || !Files.isSameFile(Path.of(args[3]), Path.of(args[1]))), "distinct_output_required");
      long count = args.length == 5
          ? runIntegrated(Path.of(args[0]), Path.of(args[1]), EvidenceResolver.local(Path.of(args[2])), evaluator)
          : run(Path.of(args[0]), Path.of(args[1]), EvidenceResolver.local(Path.of(args[2])), evaluator);
      System.out.println(Json.MAPPER.writeValueAsString(Map.of("version", "1.0.0", "records", count, "publication", "complete")));
    } catch (Exception ex) {
      System.err.println("{\"category\":\"windows_offline_failure\"}"); System.exit(1);
    }
  }
}
