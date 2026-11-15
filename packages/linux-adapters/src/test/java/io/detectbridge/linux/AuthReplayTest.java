package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class AuthReplayTest {
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
