package org.apache.flink.connector.kafka.sink;

import static org.junit.jupiter.api.Assertions.*;
import java.io.IOException;
import java.util.ArrayDeque;
import java.util.OptionalLong;
import java.util.Properties;
import java.util.concurrent.ScheduledFuture;
import org.apache.flink.api.common.JobID;
import org.apache.flink.api.common.JobInfo;
import org.apache.flink.api.common.JobInfoImpl;
import org.apache.flink.api.common.TaskInfo;
import org.apache.flink.api.common.TaskInfoImpl;
import org.apache.flink.api.common.operators.MailboxExecutor;
import org.apache.flink.api.common.operators.ProcessingTimeService;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.api.common.typeutils.TypeSerializer;
import org.apache.flink.api.connector.sink2.WriterInitContext;
import org.apache.flink.connector.kafka.sink.internal.FlinkKafkaInternalProducer;
import org.apache.flink.metrics.groups.SinkWriterMetricGroup;
import org.apache.flink.metrics.groups.UnregisteredMetricsGroup;
import org.apache.flink.util.UserCodeClassLoader;
import org.apache.flink.util.function.ThrowingRunnable;
import org.apache.kafka.common.errors.RecordTooLargeException;
import org.junit.jupiter.api.Test;

class DetectBridgeKafkaSinkTest {
  static final class Init implements WriterInitContext {
    final ArrayDeque<ThrowingRunnable<? extends Exception>> actions = new ArrayDeque<>();
    final SinkWriterMetricGroup metrics = UnregisteredMetricsGroup.createSinkWriterMetricGroup();
    int yields;
    public MailboxExecutor getMailboxExecutor() { return new MailboxExecutor() {
      public void execute(MailOptions options, ThrowingRunnable<? extends Exception> action, String description, Object... args) { actions.add(action); }
      public void yield() { yields++; }
      public boolean tryYield() { yields++; return true; }
      public boolean shouldInterrupt() { return true; }
    }; }
    public UserCodeClassLoader getUserCodeClassLoader() { return new UserCodeClassLoader() {
      public ClassLoader asClassLoader() { return getClass().getClassLoader(); }
      public void registerReleaseHookIfAbsent(String name, Runnable hook) {}
    }; }
    public ProcessingTimeService getProcessingTimeService() { return new ProcessingTimeService() {
      public long getCurrentProcessingTime() { return 0; }
      public ScheduledFuture<?> registerTimer(long time, ProcessingTimeCallback callback) { return null; }
    }; }
    public SinkWriterMetricGroup metricGroup() { return metrics; }
    public SerializationSchema.InitializationContext asSerializationSchemaInitializationContext() { return new SerializationSchema.InitializationContext() {
      public org.apache.flink.metrics.MetricGroup getMetricGroup() { return metrics; }
      public UserCodeClassLoader getUserCodeClassLoader() { return Init.this.getUserCodeClassLoader(); }
    }; }
    public boolean isObjectReuseEnabled() { return false; }
    public <T> TypeSerializer<T> createInputSerializer() { return null; }
    public OptionalLong getRestoredCheckpointId() { return OptionalLong.empty(); }
    public JobInfo getJobInfo() { return new JobInfoImpl(new JobID(), "cleanup-regression"); }
    public TaskInfo getTaskInfo() { return new TaskInfoImpl("cleanup-regression", 1, 0, 1, 0); }
  }
  static Properties properties() {
    var p = io.detectbridge.integration.IntegrationBroker.producerProperties("localhost:1");
    p.put("flink.disable-metrics", "true");
    return p;
  }
  static final class Producer extends FlinkKafkaInternalProducer<byte[],byte[]> {
    Throwable closeFailure;
    Producer() { super(properties()); }
    @SuppressWarnings("unchecked") static <E extends Throwable> void throwAny(Throwable failure) throws E { throw (E) failure; }
    @Override public void close() {
      if (closeFailure != null) throwAny(closeFailure);
      super.close();
    }
  }
  record Fixture(Init context, DetectBridgeKafkaSink.CleanupWriter<byte[]> writer,
                 DetectBridgeKafkaSink.Failure failure, Producer producer) implements AutoCloseable {
    Fixture() { this(new Init(), new DetectBridgeKafkaSink.Failure(), new Producer()); }
    Fixture(Init context, DetectBridgeKafkaSink.Failure failure, Producer producer) {
      this(context, new DetectBridgeKafkaSink.CleanupWriter<>(properties(), context, (value, sink, time) -> null, failure), failure, producer);
      writer.currentProducer = producer;
    }
    void pending() { writer.deliveryCallback.onCompletion(null, new RecordTooLargeException("synthetic rejection")); }
    public void close() { producer.closeFailure = null; producer.close(); }
  }

  @Test void stockPinnedWriterDeterministicallyReproducesSecondaryCloseFailure() throws Exception {
    var context = new Init();
    var writer = new KafkaWriter<byte[]>(org.apache.flink.connector.base.DeliveryGuarantee.AT_LEAST_ONCE, properties(), context, (value, sink, time) -> null, context.asSerializationSchemaInitializationContext());
    try (var producer = new Producer()) {
      writer.currentProducer = producer;
      writer.deliveryCallback.onCompletion(null, new RecordTooLargeException("first"));
      assertThrows(IOException.class, () -> context.actions.remove().run());
      writer.deliveryCallback.onCompletion(null, new RecordTooLargeException("second"));
      assertThrows(IOException.class, writer::close);
      assertTrue(producer.isClosed());
      assertNull(writer.currentProducer);
    }
  }

  @Test void firstSendFailureAlwaysPropagatesThroughWriteFlushAndMailbox() throws Exception {
    for (String path : new String[]{"write", "flush", "mailbox"}) {
      try (var f = new Fixture()) {
        f.pending();
        IOException original = assertThrows(IOException.class, () -> {
          switch (path) {
            case "write" -> f.writer.write(null, null);
            case "flush" -> f.writer.flush(false);
            default -> f.context.actions.remove().run();
          }
        });
        assertSame(original, f.failure.first);
        assertInstanceOf(RecordTooLargeException.class, original.getCause().getCause());
        f.pending();
        f.writer.close();
        assertTrue(f.producer.isClosed());
        assertNull(f.writer.currentProducer);
        assertEquals(1, f.writer.closedSendFailures.getCount());
        assertEquals(1, original.getSuppressed().length);
        assertInstanceOf(IOException.class, original.getSuppressed()[0]);
        assertInstanceOf(RecordTooLargeException.class, original.getSuppressed()[0].getCause().getCause());
      }
    }
  }

  @Test void firstCloseOnlyFailureIsNotSuppressedEvenAfterResourcesClosed() throws Exception {
    try (var f = new Fixture()) {
      f.pending();
      assertThrows(IOException.class, f.writer::close);
      assertTrue(f.producer.isClosed());
      assertNull(f.failure.first);
      assertEquals(0, f.writer.closedSendFailures.getCount());
    }
  }

  @Test void cleanupFailureAndJvmErrorAlwaysPropagateDespitePriorSendFailure() throws Exception {
    for (Throwable cleanup : new Throwable[]{new IOException("cleanup IO"), new IllegalStateException("cleanup"), new OutOfMemoryError("synthetic VM error")}) {
      try (var f = new Fixture()) {
        f.pending();
        assertThrows(IOException.class, () -> f.context.actions.remove().run());
        f.producer.closeFailure = cleanup;
        Throwable actual = assertThrows(cleanup.getClass(), f.writer::close);
        assertSame(cleanup, actual);
        assertNotNull(f.writer.currentProducer);
        assertEquals(0, f.writer.closedSendFailures.getCount());
      }
    }
  }

  @Test void ordinaryCloseRetainsNoFailureOrCleanupCounter() throws Exception {
    try (var f = new Fixture()) {
      f.writer.flush(true);
      f.writer.close();
      assertTrue(f.producer.isClosed());
      assertEquals(0, f.writer.closedSendFailures.getCount());
      assertNull(f.failure.first);
    }
  }
}
