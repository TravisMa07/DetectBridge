package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import org.apache.flink.api.connector.sink2.*;
import org.apache.kafka.clients.producer.*;
import tools.jackson.databind.JsonNode;

/** Required synchronous broker acknowledgment. No connector cleanup guard or hidden retry. */
public final class LifecycleSink implements Sink<LifecycleWorker.Delivery> {
  final byte[] config;final LifecycleHooks hooks;public LifecycleSink(JsonNode config){this(config,LifecycleHooks.NONE);}
  public LifecycleSink(JsonNode config,LifecycleHooks hooks){this.config=bytes(config);this.hooks=hooks;}
  public SinkWriter<LifecycleWorker.Delivery> createWriter(WriterInitContext context)throws IOException {try{return new Writer(parse(config,RECORD),hooks);}catch(Exception failure){throw new IOException("lifecycle_sink_initialize",failure);}}
  static final class Writer implements SinkWriter<LifecycleWorker.Delivery> {
    final JsonNode config;final LifecycleHooks hooks;final KafkaProducer<byte[],byte[]> producer;
    Writer(JsonNode config,LifecycleHooks hooks)throws Exception{this.config=config;this.hooks=hooks;LifecycleTool.verifyBroker(config);producer=new KafkaProducer<>(LifecycleTool.producer(config.get("bootstrap").asString()));}
    public void write(LifecycleWorker.Delivery delivery,Context context)throws IOException,InterruptedException {
      try{check(delivery.role().equals("ack")||delivery.role().equals("output"),"lifecycle_sink_scope");String topic=config.at("/topics/"+delivery.role()+"/name").asString();var ack=producer.send(new ProducerRecord<byte[],byte[]>(topic,0,delivery.key().getBytes(StandardCharsets.UTF_8),delivery.bytes())).get(35,TimeUnit.SECONDS);hooks.afterSinkAck(topic,ack.offset(),delivery.key(),io.detectbridge.transport.Json.sha(delivery.bytes()));}catch(InterruptedException e){throw e;}catch(Exception failure){throw new IOException("lifecycle_required_sink_failure",failure);}
    }
    public void flush(boolean end)throws IOException {try{producer.flush();LifecycleTool.verifyBroker(config);}catch(Exception failure){throw new IOException("lifecycle_required_sink_flush",failure);}}
    public void close(){producer.close(java.time.Duration.ofSeconds(15));}
  }
}
