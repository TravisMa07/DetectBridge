package io.detectbridge.linux;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.detection.Evaluator;
import io.detectbridge.detection.IntegrationOutputs;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Atomic, bounded, non-resumable offline audit replay over retained inline originals. */
public final class AuditReplay {
  private AuditReplay() {}
  private static final Clock CLOCK = Clock.fixed(Instant.EPOCH, ZoneOffset.UTC);

  static long replay(Path input, Path output, Path plan) throws Exception {
    return replay(input, output, plan, false);
  }
  public static long replay(Path input, Path output, Path plan, boolean integrated) throws Exception {
    Path destination = output.toAbsolutePath().normalize();
    check(!input.toRealPath().equals(destination) && !plan.toRealPath().equals(destination), "distinct_output_required");
    if (Files.exists(destination)) {
      check(!Files.isSameFile(input, destination) && !Files.isSameFile(plan, destination), "distinct_output_required");
    }
    Evaluator evaluator = new Evaluator(io.detectbridge.detection.Evaluate.bounded(plan, 4 * 1024 * 1024));
    Path temp = Files.createTempFile(destination.getParent(), ".audit-replay-", ".tmp");
    long count = 0;
    try {
      try (InputStream in = Files.newInputStream(input);
           FileChannel out = FileChannel.open(temp, StandardOpenOption.WRITE)) {
        Writer writer = new Writer(out, evaluator, integrated);
        Assembler machine = new Assembler(CLOCK, Assembler.Limits.defaults());
        Set<String> runs = new LinkedHashSet<>();
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
          check(resolved.context().at("/parser/id").asString().equals("linux-audit"), "parser_binding");
          String run = resolved.context().get("run_id").asString();
          runs.add(run); check(runs.size() <= 16, "run_limit_backlog");
          var retained = Json.MAPPER.createObjectNode(); retained.put("version", "1.0.0"); retained.put("kind", "input");
          retained.set("raw", resolved.raw()); retained.set("context", resolved.context()); writer.write(retained);
          boolean consumed;
          do {
            var prepared = machine.prepare(resolved); consumed = prepared.consumed();
            writer.outputs(prepared.outputs());
            machine = Assembler.restore(CLOCK, Assembler.Limits.defaults(), prepared.nextSnapshot());
          } while (!consumed);
          count++;
        }
        for (String run : runs) {
          boolean consumed;
          do {
            var prepared = machine.prepareEnd(run); consumed = prepared.consumed();
            writer.outputs(prepared.outputs());
            machine = Assembler.restore(CLOCK, Assembler.Limits.defaults(), prepared.nextSnapshot());
          } while (!consumed);
        }
        out.force(true);
      }
      Files.move(temp, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
      return count;
    } finally { Files.deleteIfExists(temp); }
  }

  private static final class Writer {
    final FileChannel out; final Evaluator evaluator; long events;
    final IntegrationOutputs integration;
    Writer(FileChannel out, Evaluator evaluator, boolean integrated) {
      this.out = out; this.evaluator = evaluator;
      integration = integrated ? new IntegrationOutputs(evaluator) : null;
    }
    void write(JsonNode document) throws IOException {
      ByteBuffer buffer = ByteBuffer.wrap(Json.bytes(document));
      while (buffer.hasRemaining()) out.write(buffer);
      ByteBuffer newline = ByteBuffer.wrap(new byte[]{'\n'});
      while (newline.hasRemaining()) out.write(newline);
    }
    void outputs(List<JsonNode> documents) throws Exception {
      for (JsonNode document : documents) {
        var row = Json.MAPPER.createObjectNode(); row.put("version", "1.0.0"); row.set("document", document);
        if (document.has("@timestamp")) {
          row.put("kind", "event"); byte[] bytes = Json.bytes(document);
          if (integration != null) {
            JsonNode manifest = documents.stream().filter(d -> d.has("manifest_id") && d.path("event_id").equals(document.at("/event/id"))).findFirst().orElseThrow();
            Boundary.schema("urn:detectbridge:linux:1.0.0:manifest", manifest);
            row.set("integration", integration.process(document, manifest));
          } else row.set("evaluation", evaluator.evaluate(bytes, Map.of("cluster_id", "offline", "topic_id", "offline",
              "topic", "linux-audit-offline", "partition", 0, "offset", events++, "value_sha256", Json.sha(bytes))));
        } else row.put("kind", document.has("manifest_id") ? "manifest" : "preservation");
        write(row);
      }
    }
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
      check(args.length == 3 || (args.length == 4 && args[3].equals("--integrated")), "arguments");
      long count = replay(Path.of(args[0]), Path.of(args[1]), Path.of(args[2]), args.length == 4);
      System.out.println("{\"status\":\"published\",\"records\":" + count + "}");
    } catch (Exception e) {
      System.err.println("{\"category\":\"audit_replay_failed\"}"); System.exit(1);
    }
  }
}
