package io.detectbridge.integration;

import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PublisherTest {
  @Test
  void boundedEnvelopeCarriesOversizedSourceWithoutRelaxingSourceParser() {
    byte[] source = new byte[2 * Json.MAX_VALUE];
    java.util.Arrays.fill(source, (byte) 'x');
    byte[] envelope = Json.bytes(Map.of("sequence", 1, "key", "", "value",
        Base64.getEncoder().encodeToString(source)));
    // The shared source mapper cannot parse this Base64 envelope; IPC has its own bound.
    assertThrows(Exception.class, () -> Json.MAPPER.readTree(envelope));
    var parsed = IntegrationPublisher.ipc(envelope);
    assertArrayEquals(source, Base64.getDecoder().decode(parsed.get("value").asString()));
    assertThrows(IllegalArgumentException.class, () -> Json.read(source));
    assertThrows(IllegalArgumentException.class,
        () -> IntegrationPublisher.ipc(new byte[4 * Json.MAX_VALUE + 1]));
    for (String bad : new String[] {"{\"value\":1,\"value\":2}", "{} {}",
        "[[[[[[[[[0]]]]]]]]]"}) {
      assertThrows(Exception.class,
          () -> IntegrationPublisher.ipc(bad.getBytes(StandardCharsets.UTF_8)));
    }
  }
}
