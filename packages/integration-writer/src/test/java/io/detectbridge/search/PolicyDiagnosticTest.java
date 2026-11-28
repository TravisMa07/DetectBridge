package io.detectbridge.search;

import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.lang.reflect.Proxy;
import java.util.*;
import java.util.concurrent.*;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.common.KafkaFuture;
import org.apache.kafka.common.config.ConfigResource;
import org.apache.kafka.common.internals.KafkaFutureImpl;
import org.junit.jupiter.api.Test;

/** First-party D01–D08 literals; no broker output used as an oracle. */
class PolicyDiagnosticTest {
  static final ConfigResource RESOURCE = new ConfigResource(ConfigResource.Type.TOPIC, Projection.FAILURES);
  static class Harness {
    final Main.PolicyTrace trace = new Main.PolicyTrace();
    final List<String> calls = new ArrayList<>();
    final ByteArrayOutputStream stdout = new ByteArrayOutputStream();
    String failAt = "", actual = "1", shape = "value";
    RuntimeException error = new IllegalStateException("private-secret-sentinel");
    boolean closeFails;
    boolean timeout;
    KafkaFuture<Void> altered() {
      if (timeout) return new KafkaFutureImpl<Void>();
      if (failAt.equals("alter_wait")) {
        var future = new KafkaFutureImpl<Void>(); future.completeExceptionally(error); return future;
      }
      return KafkaFuture.completedFuture(null);
    }
    Admin create() {
      calls.add("create"); if (failAt.equals("admin_create")) throw error;
      return (Admin) Proxy.newProxyInstance(Admin.class.getClassLoader(), new Class<?>[]{Admin.class}, (p,m,a) -> {
        switch (m.getName()) {
          case "incrementalAlterConfigs":
            calls.add("alter"); if (failAt.equals("alter_submit")) throw error;
            var submitted = (Map<?,?>) a[0];
            assertEquals(Set.of(RESOURCE), submitted.keySet());
            assertEquals(1, ((Collection<?>) submitted.get(RESOURCE)).size());
            // Kafka exposes a package-private result constructor; reflection is test-only.
            var constructor = AlterConfigsResult.class.getDeclaredConstructor(Map.class);
            constructor.setAccessible(true);
            return constructor.newInstance(Map.of(RESOURCE, altered()));
          case "describeConfigs":
            calls.add("describe"); if (failAt.equals("describe_submit")) throw error;
            assertEquals(List.of(RESOURCE), a[0]);
            var configs = new HashMap<ConfigResource, Config>();
            if (!shape.equals("missing_resource")) configs.put(RESOURCE, new Config(
                shape.equals("missing_entry") ? List.of() : List.of(new ConfigEntry("max.message.bytes", actual))));
            return new DescribeConfigsResult(Map.of()) {
              @Override public KafkaFuture<Map<ConfigResource, Config>> all() {
                if (failAt.equals("describe_wait")) {
                  var f = new KafkaFutureImpl<Map<ConfigResource, Config>>(); f.completeExceptionally(error); return f;
                }
                return KafkaFuture.completedFuture(configs);
              }
            };
          case "close":
            calls.add("close"); if (closeFails) throw error; return null;
          default: throw new AssertionError("unexpected Admin query: " + m.getName());
        }
      });
    }
    void run(String intent) throws Exception {
      Main.configurePolicy(Json.MAPPER.valueToTree(Map.of("value", intent)), trace, this::create, new PrintStream(stdout));
    }
    void safe() {
      String diagnostic = Json.MAPPER.writeValueAsString(trace.snapshot());
      assertFalse(diagnostic.contains("private-secret-sentinel"));
      assertTrue(diagnostic.getBytes(java.nio.charset.StandardCharsets.UTF_8).length <= 4096);
    }
  }

  @Test void exactPoliciesUseOneAlterOneDescribeAndClose() throws Exception {
    for (String intent : List.of("block", "healthy")) {
      var h = new Harness(); h.actual = intent.equals("block") ? "1" : "2097152";
      h.run(intent);
      assertEquals(List.of("create", "alter", "describe", "close"), h.calls);
      assertEquals("{\"status\":\"configured\"}" + System.lineSeparator(), h.stdout.toString());
      assertEquals("completed", h.trace.phase); assertEquals("closed", h.trace.close);
      assertEquals("acknowledged", h.trace.alter); assertEquals("received", h.trace.readback);
      assertEquals(true, h.trace.matches); assertEquals("none", h.trace.failure); h.safe();
    }
  }
  @Test void invalidIntentHasNoAdminEffect() {
    var h = new Harness();
    assertThrows(IllegalArgumentException.class, () -> h.run("private-secret-sentinel"));
    assertEquals(List.of(), h.calls); assertEquals("unavailable", h.trace.intent);
    assertEquals("fault_scope", h.trace.known); h.safe();
  }
  @Test void absentAndNonstringIntentNeverCreatesAdmin() {
    for (String json : List.of("{}", "{\"value\":null}", "{\"value\":17}",
        "{\"value\":true}", "{\"value\":[]}", "{\"value\":{}}")) {
      var h = new Harness();
      assertThrows(Exception.class, () -> Main.configurePolicy(Json.read(json.getBytes()), h.trace,
          h::create, new PrintStream(h.stdout)));
      assertEquals(List.of(), h.calls); assertEquals("unavailable", h.trace.intent);
      assertEquals("parse_intent", h.trace.phase); h.safe();
    }
  }
  @Test void createSubmitAndWaitFailuresDoNotInventAcknowledgment() {
    for (String stage : List.of("admin_create", "alter_submit", "alter_wait", "describe_submit", "describe_wait")) {
      var h = new Harness(); h.failAt = stage;
      var ex = assertThrows(Exception.class, () -> h.run("healthy"));
      assertEquals(stage, h.trace.phase);
      assertEquals(stage.endsWith("wait") ? h.error : ex, stage.endsWith("wait") ? ex.getCause() : h.error);
      assertEquals(stage.startsWith("describe") ? "acknowledged" : stage.equals("alter_wait") ? "submitted" : "not_started", h.trace.alter);
      assertNull(h.trace.matches); assertEquals("unclassified", h.trace.known);
      assertEquals(stage.equals("admin_create") ? List.of("create") : stage.startsWith("describe") ? List.of("create", "alter", "describe", "close") : List.of("create", "alter", "close"), h.calls);
      h.safe();
    }
  }
  @Test void timeoutPreservesUnknownBrokerEffect() {
    var h = new Harness(); h.timeout = true;
    assertThrows(TimeoutException.class, () -> h.run("healthy"));
    assertEquals("submitted", h.trace.alter); assertEquals("timeout", h.trace.failure);
    assertEquals("alter_wait", h.trace.phase); assertEquals("not_observed", h.trace.observed);
    assertEquals(List.of("create", "alter", "close"), h.calls); h.safe();
  }
  @Test void mismatchIsOnlyAttributedAtOwnThrow() {
    for (String actual : List.of("1", "private-secret-sentinel")) {
      var h = new Harness(); h.actual = actual;
      assertEquals("fault_readback", assertThrows(IllegalStateException.class, () -> h.run("healthy")).getMessage());
      assertEquals("fault_readback", h.trace.known); assertEquals(false, h.trace.matches);
      assertEquals(actual.equals("1") ? "block" : "other", h.trace.observed); h.safe();
    }
    var h = new Harness(); h.failAt = "alter_submit"; h.error = new IllegalStateException("fault_readback");
    assertSame(h.error, assertThrows(IllegalStateException.class, () -> h.run("healthy")));
    assertEquals("unclassified", h.trace.known);
  }
  @Test void nullShapesRetainOriginalDereferenceFailures() {
    for (String shape : List.of("missing_resource", "missing_entry", "null_value")) {
      var h = new Harness(); h.shape = shape; if (shape.equals("null_value")) h.actual = null;
      assertThrows(NullPointerException.class, () -> h.run("healthy"));
      assertEquals(shape, h.trace.observed); assertNull(h.trace.matches);
      assertEquals("unclassified", h.trace.known); assertEquals("other", h.trace.failure);
      assertEquals("readback_compare", h.trace.phase); h.safe();
    }
  }
  @Test void closeFailureAndSuppressionPreservePrimaryOutcome() {
    var h = new Harness(); h.actual = "2097152"; h.closeFails = true;
    assertSame(h.error, assertThrows(IllegalStateException.class, () -> h.run("healthy")));
    assertEquals(true, h.trace.matches); assertEquals("admin_close", h.trace.phase);
    assertEquals("failed", h.trace.close); assertTrue(h.stdout.toString().contains("configured")); h.safe();
    var failed = new Harness(); failed.closeFails = true;
    var ex = assertThrows(IllegalStateException.class, () -> failed.run("healthy"));
    assertEquals("fault_readback", ex.getMessage()); assertArrayEquals(new Throwable[]{failed.error}, ex.getSuppressed());
    assertEquals("readback_compare", failed.trace.phase); assertEquals("fault_readback", failed.trace.known);
    assertEquals("failed", failed.trace.close); failed.safe();
  }
  @Test void nullMessageCreateAndCloseStillEmitSafeTrace() {
    for (String stage : List.of("admin_create", "admin_close")) {
      var h = new Harness(); h.error = new IllegalStateException();
      h.actual = "2097152";
      if (stage.equals("admin_create")) h.failAt = stage; else h.closeFails = true;
      assertSame(h.error, assertThrows(IllegalStateException.class, () -> h.run("healthy")));
      var detail = Main.failureDetail(h.error, h.trace);
      assertEquals("writer_failed", detail.get("category"));
      assertEquals("IllegalStateException", detail.get("reason_type"));
      assertEquals(h.trace.snapshot(), detail.get("failure_policy"));
      assertEquals(stage, h.trace.phase);
    }
    var trace = new Main.PolicyTrace();
    assertEquals("topic_policy_changed", Main.failureDetail(new IllegalStateException("topic_policy_changed"), trace).get("category"));
  }

}
