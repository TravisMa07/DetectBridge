package io.detectbridge.linux;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.linux.Fixtures.*;

import io.detectbridge.detection.Evaluator;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;

class EvaluationTest {
  private void outcome(String planName, JsonNode event, String expected) throws Exception {
    Path root = Path.of(System.getProperty("repository.root"));
    Evaluator evaluator = new Evaluator(Files.readAllBytes(root.resolve(".cache/linux-adapters/plans/" + planName + ".json")));
    byte[] bytes = Json.bytes(event);
    Map<String, Object> location = Map.of("topic", "synthetic-p12-offline", "partition", 0, "offset", 0,
        "cluster_id", "synthetic", "topic_id", "synthetic", "value_sha256", Json.sha(bytes));
    JsonNode result = evaluator.evaluate(bytes, location);
    assertEquals(1, result.get("counts").get(expected).asInt());
    for (String other : Evaluator.OUTCOMES) if (!other.equals(expected)) assertEquals(0, result.get("counts").get(other).asInt());
    assertEquals("2.0.0", result.get("version").asString());
  }
  @Test void actualAdapterOutputsReachP10WithIndependentMatchNonmatchBlockAndSkipExpectations() throws Exception {
    Sink sink = new Sink(); Assembler a = new Assembler(new Time(), Assembler.Limits.defaults());
    complete(a, sink, context(false), 0); a.accept(input(line("EOE"), 5, context(false)), sink);
    JsonNode event = sink.events().get(0);
    outcome("image-match", event, "matched"); outcome("image-nonmatch", event, "unmatched");
    outcome("command-blocked", event, "configuration_blocked"); outcome("auth-user", event, "inapplicable");
    sink = new Sink(); a = new Assembler(new Time(), Assembler.Limits.defaults());
    a.accept(input(line("EOE"), 5, context(false)), sink);
    outcome("image-match", sink.events().get(0), "quality_skipped");
    for (String status : List.of("Accepted", "Failed")) {
      JsonNode auth = OpenSsh.adapt(input(OpenSshTest.auth(OpenSshTest.ACCEPT.replace("Accepted", status)), 0, context(true)));
      outcome("auth-user", auth, "matched");
      auth = OpenSsh.adapt(input(OpenSshTest.auth(OpenSshTest.ACCEPT.replace("for alice", "for bob")), 1, context(true)));
      outcome("auth-user", auth, "unmatched");
    }
  }
}
