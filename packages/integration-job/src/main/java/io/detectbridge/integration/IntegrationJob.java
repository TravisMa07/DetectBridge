package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import io.detectbridge.linux.Assembler;
import io.detectbridge.linux.Boundary;
import io.detectbridge.transport.Json;
import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Clock;
import java.util.*;
import java.util.concurrent.ScheduledFuture;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ListState;
import org.apache.flink.api.common.state.ListStateDescriptor;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.connector.kafka.source.reader.deserializer.KafkaRecordDeserializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.runtime.state.StateInitializationContext;
import org.apache.flink.runtime.state.StateSnapshotContext;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.operators.AbstractStreamOperator;
import org.apache.flink.streaming.api.operators.OneInputStreamOperator;
import org.apache.flink.streaming.runtime.streamrecord.StreamRecord;
import org.apache.flink.util.Collector;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.producer.ProducerRecord;

/** Exclusive P12b qualification topology; at-least-once Kafka output and durable intent release. */
public final class IntegrationJob {
  public static class WireRecord implements Serializable {
    public byte[] value; public long offset; public String topic; public int partition;
    public WireRecord() {}
  }
  public static class Delivery implements Serializable {
    public byte[] document; public String kind, key, binding; public long sequence;
    public Delivery() {}
  }
  public static class Decode implements KafkaRecordDeserializationSchema<WireRecord> {
    public void deserialize(ConsumerRecord<byte[],byte[]> record, Collector<WireRecord> out) {
      check(record.partition()==0 && record.topic().equals(IntegrationBroker.INPUT),"integration_input_scope");
      WireRecord wire=new WireRecord();wire.value=record.value();wire.offset=record.offset();wire.partition=record.partition();wire.topic=record.topic();out.collect(wire);
    }
    public TypeInformation<WireRecord> getProducedType(){return TypeInformation.of(WireRecord.class);}
  }
  public static class Configuration implements Serializable {
    final String bootstrap,group,cluster,artifact,binding,profile,registry;
    final Map<String,String> ids;
    final byte[] plan;
    Configuration(String[] args) throws Exception {
      check(args.length == 14, "integration_arguments");
      bootstrap=args[0];group=args[1];cluster=args[2];artifact=args[11];profile=args[12];registry=args[13];
      check(Set.of("default","limits","bytes").contains(profile),"integration_limit_profile");
      Map<String,String> topics=new LinkedHashMap<>();for(int i=0;i<IntegrationBroker.TOPICS.size();i++)topics.put(IntegrationBroker.TOPICS.get(i),args[i+3]);ids=Map.copyOf(topics);
      check(artifact.matches("[a-f0-9]{64}") && !group.isEmpty(),"integration_configuration");
      plan = io.detectbridge.detection.Evaluate.bounded(Path.of("/opt/detectbridge/plan.json"),4*1024*1024);
      var evaluator = new io.detectbridge.detection.Evaluator(plan); evaluator.requireMappedDeployment();
      binding=Machine.hash(Json.MAPPER.valueToTree(Map.of("version","1.0.0","artifact",artifact,"group",group,"cluster",cluster,"topics",ids,
          "limits",limits(),"queue_bytes",Machine.QUEUE_BYTES,"queue_count",Machine.QUEUE_COUNT,"evidence_registry",registry,
          "profiles",Map.of("bundle",evaluator.bundle(),"evaluator",evaluator.semanticVersion(),"selector",io.detectbridge.detection.Evaluator.SELECTION_VERSION,
              "pipeline",io.detectbridge.detection.IntegrationOutputs.RUNTIME_PIPELINE))));
    }
    Assembler.Limits limits() {
      return switch(profile) {
        case "limits" -> new Assembler.Limits(2,512,2,32768,30000,2,4,65536);
        case "bytes" -> new Assembler.Limits(256,1048576,1024,12000,30000,16,100000,33554432);
        default -> Assembler.Limits.defaults();
      };
    }
    tools.jackson.databind.JsonNode source() {return Json.MAPPER.valueToTree(Map.of("cluster_id",cluster,"topic_id",ids.get(IntegrationBroker.INPUT),"topic",IntegrationBroker.INPUT));}
  }
  public static class Operator extends AbstractStreamOperator<Delivery> implements OneInputStreamOperator<WireRecord,Delivery> {
    private final Configuration config;
    private transient Machine machine;
    private transient LocalEvidence evidence;
    private transient ListState<byte[]> checkpointState;
    private transient ScheduledFuture<?> timer;
    private transient boolean restored;
    private transient long lastCompleted;
    public Operator(Configuration config){this.config=config;}
    @Override public void initializeState(StateInitializationContext context) throws Exception {
      super.initializeState(context);lastCompleted=-1;
      var failures=getMetricGroup().addGroup("detectbridge_integration").counter("restore_failures");
      try {
      IntegrationBroker.verifyIdentities(config.bootstrap,config.cluster,config.ids);
      evidence=LocalEvidence.open(Path.of("/opt/detectbridge/objects"),Path.of("/opt/detectbridge/object-registration.json"),config.registry);
      checkpointState=context.getOperatorStateStore().getListState(new ListStateDescriptor<>("linux-integration-envelope-v1",byte[].class));
      List<byte[]> snapshots=new ArrayList<>();checkpointState.get().forEach(snapshots::add);
      restored=context.isRestored();check(restored ? snapshots.size()==1 : snapshots.isEmpty(),"incompatible_integration_restore");
      machine=restored ? Machine.restore(Clock.systemUTC(),config.limits(),config.binding,config.source(),evidence::resolve,new io.detectbridge.detection.Evaluator(config.plan),snapshots.get(0))
          : new Machine(Clock.systemUTC(),config.limits(),config.binding,config.source(),evidence::resolve,new io.detectbridge.detection.Evaluator(config.plan));
      } catch(Exception failed) {if(context.isRestored())failures.inc();throw failed;}
    }
    @Override public void open() throws Exception {
      super.open();if(restored)machine.releaseRestored(this::emit);
      var metrics=getRuntimeContext().getMetricGroup().addGroup("detectbridge_integration");
      metrics.gauge("pending_inputs",()->machine.pendingInputs());metrics.gauge("pending_outputs",()->machine.pendingOutputs());
      metrics.gauge("inbox_bytes",()->machine.inboxBytes());metrics.gauge("outbox_bytes",()->machine.outboxBytes());
      metrics.gauge("open_groups",()->machine.groupCount());metrics.gauge("closed_keys",()->machine.closedCount());
      metrics.gauge("next_deadline",()->machine.nextDeadline());schedule();
    }
    private void schedule(){timer=getProcessingTimeService().registerTimer(getProcessingTimeService().getCurrentProcessingTime()+500,t->{machine.pump();schedule();});}
    public void processElement(StreamRecord<WireRecord> element) throws Exception {
      WireRecord wire=element.getValue();check(wire.topic.equals(IntegrationBroker.INPUT)&&wire.partition==0,"integration_input_scope");
      machine.enqueue(Machine.wire(wire.value,config.cluster,config.ids.get(wire.topic),wire.topic,wire.offset));machine.pump();
    }
    private void emit(Machine.Intent intent) {
      Delivery delivery=new Delivery();delivery.sequence=intent.sequence();delivery.binding=config.binding;delivery.kind=intent.kind();delivery.key=intent.key();delivery.document=Json.bytes(io.detectbridge.detection.Contracts.canonical(intent.document()));
      output.collect(new StreamRecord<>(delivery));
    }
    @Override public void snapshotState(StateSnapshotContext context) throws Exception {
      super.snapshotState(context);evidence.verify();IntegrationBroker.verifyIdentities(config.bootstrap,config.cluster,config.ids);
      byte[] snapshot=machine.snapshot(context.getCheckpointId());checkpointState.update(List.of(snapshot));
      Path directory=Path.of("/state/integration-evidence",getContainingTask().getEnvironment().getJobID().toString());
      Files.createDirectories(directory);Path temp=Files.createTempFile(directory,".inventory-",".tmp");
      try {
        byte[] data=Json.bytes(machine.inventory(context.getCheckpointId(),snapshot));
        check(data.length<=Machine.STATE_BYTES,"integration_inventory_limit");
        try(var file=java.nio.channels.FileChannel.open(temp,StandardOpenOption.WRITE)) {
          var buffer=java.nio.ByteBuffer.wrap(data);while(buffer.hasRemaining())file.write(buffer);file.force(true);
        }
        Files.move(temp,directory.resolve("checkpoint-"+context.getCheckpointId()+".json"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        try(var files=Files.list(directory)) {
          var old=files.filter(p->p.getFileName().toString().matches("checkpoint-[0-9]+\\.json"))
              .sorted(Comparator.comparingLong(p->Long.parseLong(p.getFileName().toString().replace("checkpoint-","").replace(".json","")))).toList();
          for(int i=0;i<old.size()-4;i++) {
            long candidate=Long.parseLong(old.get(i).getFileName().toString().replace("checkpoint-","").replace(".json",""));
            if(candidate!=lastCompleted)Files.deleteIfExists(old.get(i));
          }
        }
      } finally {Files.deleteIfExists(temp);}
    }
    @Override public void notifyCheckpointComplete(long id) throws Exception {super.notifyCheckpointComplete(id);lastCompleted=id;machine.complete(id,this::emit);machine.pump();}
    @Override public void notifyCheckpointAborted(long id) throws Exception {super.notifyCheckpointAborted(id);machine.abort(id);}
    @Override public void close() throws Exception {if(timer!=null)timer.cancel(false);super.close();}
  }
  public static class Encode implements KafkaRecordSerializationSchema<Delivery> {
    public ProducerRecord<byte[],byte[]> serialize(Delivery delivery,KafkaSinkContext context,Long timestamp) {
      String topic=IntegrationBroker.ROUTES.get(delivery.kind);check(topic!=null,"integration_output_scope");
      var record=new ProducerRecord<byte[],byte[]>(topic,delivery.key.getBytes(StandardCharsets.UTF_8),delivery.document);
      record.headers().add("detectbridge.runtime.binding",delivery.binding.getBytes(StandardCharsets.UTF_8));
      record.headers().add("detectbridge.intent.kind",delivery.kind.getBytes(StandardCharsets.UTF_8));
      record.headers().add("detectbridge.intent.sequence",Long.toString(delivery.sequence).getBytes(StandardCharsets.UTF_8));return record;
    }
  }
  public static void main(String[] args) throws Exception {
    Configuration config=new Configuration(args);
    Path artifact=Path.of(IntegrationJob.class.getProtectionDomain().getCodeSource().getLocation().toURI());
    check(Files.isRegularFile(artifact)&&Json.sha(Files.readAllBytes(artifact)).equals(config.artifact),"integration_artifact_mismatch");
    IntegrationBroker.verify(config.bootstrap,config.cluster,config.ids);
    var flink=new org.apache.flink.configuration.Configuration();
    flink.setString("execution.checkpointing.storage","filesystem");
    flink.setString("execution.checkpointing.dir","file:///state/checkpoints");
    flink.setString("execution.checkpointing.num-retained","3");
    flink.setString("execution.checkpointing.timeout","60s");
    flink.setString("execution.checkpointing.externalized-checkpoint-retention","RETAIN_ON_CANCELLATION");
    flink.setString("restart-strategy.type","fixed-delay");
    flink.setString("restart-strategy.fixed-delay.attempts","1");
    flink.setString("restart-strategy.fixed-delay.delay","10s");
    var env=StreamExecutionEnvironment.getExecutionEnvironment(flink);env.setParallelism(1);env.enableCheckpointing(5000);
    env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);env.getCheckpointConfig().setMinPauseBetweenCheckpoints(1000);
    var source=KafkaSource.<WireRecord>builder().setBootstrapServers(config.bootstrap).setTopics(IntegrationBroker.INPUT).setGroupId(config.group)
        .setStartingOffsets(OffsetsInitializer.earliest()).setDeserializer(new Decode()).setProperty("enable.auto.commit","false")
        .setProperty("auto.offset.reset","none").setProperty("partition.discovery.interval.ms","-1")
        .setProperty("max.partition.fetch.bytes","4194304").setProperty("fetch.max.bytes","8388608").setProperty("max.poll.records","16").build();
    var sink=KafkaSink.<Delivery>builder().setBootstrapServers(config.bootstrap).setKafkaProducerConfig(IntegrationBroker.producerProperties(config.bootstrap))
        .setRecordSerializer(new Encode()).setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE).build();
    env.fromSource(source,WatermarkStrategy.noWatermarks(),"Linux integration input").uid("linux-integration-source-v1")
        .transform("Checkpointed Linux integration",TypeInformation.of(Delivery.class),new Operator(config)).uid("linux-integration-operator-v1")
        .sinkTo(sink).name("Acknowledged Linux integration outputs").uid("linux-integration-sink-v1");
    env.execute("DetectBridge P13b integrated evaluation");
  }
}
