package org.apache.flink.connector.kafka.sink;

import java.io.IOException;
import java.util.Collection;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.Properties;
import java.util.function.Consumer;
import org.apache.flink.api.common.JobInfo;
import org.apache.flink.api.common.TaskInfo;
import org.apache.flink.api.common.operators.MailboxExecutor;
import org.apache.flink.api.common.operators.ProcessingTimeService;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.api.common.typeutils.TypeSerializer;
import org.apache.flink.api.connector.sink2.WriterInitContext;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.metrics.Counter;
import org.apache.flink.metrics.groups.SinkWriterMetricGroup;
import org.apache.flink.util.UserCodeClassLoader;
import org.apache.flink.util.function.ThrowingRunnable;

/** P13-only compatibility boundary for the pinned 5.0.0-2.2 writer. See p13d-design.md. */
public final class DetectBridgeKafkaSink<IN> extends KafkaSink<IN> {
  private final Properties properties;
  private final KafkaRecordSerializationSchema<IN> serializer;

  public DetectBridgeKafkaSink(Properties properties, KafkaRecordSerializationSchema<IN> serializer) {
    super(DeliveryGuarantee.AT_LEAST_ONCE, properties, null, serializer, TransactionNamingStrategy.POOLING);
    this.properties = properties;
    this.serializer = serializer;
  }

  @Override public KafkaWriter<IN> restoreWriter(WriterInitContext context, Collection<KafkaWriterState> states) {
    if (!states.isEmpty()) throw new IllegalArgumentException("unexpected_at_least_once_writer_state");
    var writer = new CleanupWriter<>(properties, context, serializer, new Failure());
    writer.initialize();
    return writer;
  }

  static final class Failure {
    volatile Exception first;
    synchronized void observed(Exception error) { if (first == null) first = error; }
  }

  static final class CleanupWriter<IN> extends KafkaWriter<IN> {
    private final Failure failure;
    final Counter closedSendFailures;

    CleanupWriter(Properties properties, WriterInitContext context, KafkaRecordSerializationSchema<IN> serializer, Failure failure) {
      super(DeliveryGuarantee.AT_LEAST_ONCE, properties, new DetectBridgeKafkaSink.Context(context, failure), serializer, context.asSerializationSchemaInitializationContext());
      this.failure = failure;
      closedSendFailures = context.metricGroup().addGroup("detectbridge_cleanup").counter("closed_send_failures");
    }
    @Override public void write(IN value, org.apache.flink.api.connector.sink2.SinkWriter.Context context) throws IOException {
      try { super.write(value, context); }
      catch (IOException | RuntimeException error) { failure.observed(error); throw error; }
    }
    @Override public void flush(boolean endOfInput) throws IOException, InterruptedException {
      try { super.flush(endOfInput); }
      catch (IOException | InterruptedException | RuntimeException error) { failure.observed(error); throw error; }
    }
    @Override public void close() throws Exception {
      try { super.close(); }
      catch (IOException secondary) {
        // In the pinned implementation null is set only AFTER closeAll + isClosed check.
        // Never suppress the first delivery error or a resource-cleanup failure.
        if (failure.first == null || currentProducer != null) throw secondary;
        if (secondary != failure.first) failure.first.addSuppressed(secondary);
        closedSendFailures.inc();
      }
    }
  }

  private record Context(WriterInitContext delegate, Failure failure) implements WriterInitContext {
    @Override public MailboxExecutor getMailboxExecutor() {
      var mailbox = delegate.getMailboxExecutor();
      return new MailboxExecutor() {
        @Override public void execute(MailOptions options, ThrowingRunnable<? extends Exception> action, String description, Object... arguments) {
          mailbox.execute(options, () -> {
            try { action.run(); }
            catch (Exception error) { failure.observed(error); throw error; }
          }, description, arguments);
        }
        @Override public void yield() throws InterruptedException { mailbox.yield(); }
        @Override public boolean tryYield() { return mailbox.tryYield(); }
        @Override public boolean shouldInterrupt() { return mailbox.shouldInterrupt(); }
      };
    }
    @Override public UserCodeClassLoader getUserCodeClassLoader() { return delegate.getUserCodeClassLoader(); }
    @Override public ProcessingTimeService getProcessingTimeService() { return delegate.getProcessingTimeService(); }
    @Override public SinkWriterMetricGroup metricGroup() { return delegate.metricGroup(); }
    @Override public SerializationSchema.InitializationContext asSerializationSchemaInitializationContext() { return delegate.asSerializationSchemaInitializationContext(); }
    @Override public boolean isObjectReuseEnabled() { return delegate.isObjectReuseEnabled(); }
    @Override public <T> TypeSerializer<T> createInputSerializer() { return delegate.createInputSerializer(); }
    @Override public <T> Optional<Consumer<T>> metadataConsumer() { return delegate.metadataConsumer(); }
    @Override public OptionalLong getRestoredCheckpointId() { return delegate.getRestoredCheckpointId(); }
    @Override public JobInfo getJobInfo() { return delegate.getJobInfo(); }
    @Override public TaskInfo getTaskInfo() { return delegate.getTaskInfo(); }
  }
}
