package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class AuthReplayTest {
  @Test void integratedAuthenticationConsumerPositiveNegativeAbsenceAndReplay(@org.junit.jupiter.api.io.TempDir Path directory) throws Exception {
    Path input = directory.resolve("input"), output = directory.resolve("output");
    Path plan = Path.of(System.getProperty("repository.root"), ".cache/linux-adapters/plans/auth-user.json");
    var processor = new io.detectbridge.detection.IntegrationOutputs(new io.detectbridge.detection.Evaluator(Files.readAllBytes(plan)));
    tools.jackson.databind.JsonNode first = null;
    for (String run : List.of(RUN, RUN2)) {
      for (String text : List.of(OpenSshTest.ACCEPT, OpenSshTest.ACCEPT.replace("for alice", "for bob"), "unsupported")) {
        var context = context(true); context.put("run_id", run);
        var supplied = input(OpenSshTest.auth(text), 0, context);
        Files.write(input, Json.bytes(Map.of("raw", supplied.raw(), "context", supplied.context())));
        AuthReplay.replay(input, output, plan, true);
        var row = Json.read(Files.readAllBytes(output)); assertEquals(supplied.raw(), row.get("raw"));
        if (text.equals("unsupported")) { assertTrue(row.has("preservation")); assertFalse(row.has("integration")); continue; }
        var integration = row.get("integration"); processor.verify(integration, null);
        boolean match = text.equals(OpenSshTest.ACCEPT);
        for (String outcome : io.detectbridge.detection.Evaluator.OUTCOMES)
          assertEquals(outcome.equals(match ? "matched" : "unmatched") ? 1 : 0, integration.at("/tagged/counts/" + outcome).asInt());
        assertEquals(match ? 1 : 0, integration.get("detections").size());
        assertEquals(0, integration.get("diagnostics").size());
        assertEquals(context.at("/source_contract/sha256"), integration.at("/tagged/attribution/source_contract/sha256"));
        if (match && first == null) first = integration;
        else if (match) {
          assertEquals(first.at("/tagged/event/event/id"), integration.at("/tagged/event/event/id"));
          assertNotEquals(first.at("/tagged/processing_id"), integration.at("/tagged/processing_id"));
          assertNotEquals(first.at("/detections/0/detection_id"), integration.at("/detections/0/detection_id"));
        }
      }
    }
  }
  @Test void actualReplayAndFailedPublicationKeepOriginalEvidenceAndPreviousOutput() throws Exception {
    Path directory = Files.createTempDirectory("p12-auth-replay-");
    try {
      var supplied = input(OpenSshTest.auth(OpenSshTest.ACCEPT), 0, context(true));
      byte[] row = Json.bytes(Json.MAPPER.valueToTree(Map.of("raw", supplied.raw(), "context", supplied.context())));
      Path input = directory.resolve("input"), output = directory.resolve("output");
      Path plan = Path.of(System.getProperty("repository.root"), ".cache/linux-adapters/plans/auth-user.json");
      Files.write(input, (new String(row, java.nio.charset.StandardCharsets.UTF_8) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
      assertEquals(1, AuthReplay.replay(input, output, plan));
      var published = Json.read(Files.readAllBytes(output));
      assertEquals(supplied.raw(), published.get("raw"));
      assertEquals("success", published.at("/event/event/outcome").asString());
      assertEquals(1, published.at("/evaluation/counts/matched").asInt());
      byte[] previous = Files.readAllBytes(output);
      Files.writeString(input, Files.readString(input) + "{\"broken\":true}\n");
      assertThrows(IllegalArgumentException.class, () -> AuthReplay.replay(input, output, plan));
      assertArrayEquals(previous, Files.readAllBytes(output));
      try (var files = Files.list(directory)) { assertEquals(2, files.count()); }
      assertThrows(IllegalArgumentException.class, () -> AuthReplay.replay(input, input, plan));
    } finally {
      try (var files = Files.list(directory)) { for (Path path : files.toList()) Files.delete(path); }
      Files.delete(directory);
    }
  }
}
