package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.clients.producer.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.header.internals.RecordHeaders;

/** Synthetic qualification only; excluded from the production JAR. */
public final class KafkaProbe {
  public static void main(String[] args)throws Exception {
    String command=args[0],bootstrap=args[1];Object result;
    if(command.equals("join")) {
      var props=Broker.properties(bootstrap);props.put("group.id",args[2]);props.put("enable.auto.commit","false");props.put("auto.offset.reset","none");props.put("session.timeout.ms","6000");props.put("heartbeat.interval.ms","1500");props.put("key.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");props.put("value.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");
      try(var c=new org.apache.kafka.clients.consumer.KafkaConsumer<byte[],byte[]>(props)) {
        c.subscribe(Main.TOPICS);long deadline=System.nanoTime()+java.time.Duration.ofSeconds(50).toNanos();
        while(c.assignment().isEmpty()&&System.nanoTime()<deadline)c.poll(java.time.Duration.ofMillis(200));
        check(!c.assignment().isEmpty(),"probe_assignment_timeout");result=Map.of("assigned",c.assignment().size());
      }
    } else if(command.equals("publish")||command.equals("transaction")) {
      var rows=read(Files.readAllBytes(Path.of(args[2])),16*MIB);var ack=new ArrayList<Object>();
      var properties=Broker.producerProperties(bootstrap);if(command.equals("transaction"))properties.put("transactional.id","archive-probe-"+UUID.randomUUID());
      try(var producer=new KafkaProducer<byte[],byte[]>(properties)) {
        if(command.equals("transaction")){producer.initTransactions();producer.beginTransaction();}
        for(var row:rows){byte[] key=decode(row.get("key")),value=decode(row.get("value"));var headers=new RecordHeaders();for(var h:row.get("headers"))headers.add(h.get("name").asString(),decode(h.get("value")));var r=producer.send(new ProducerRecord<>(row.get("topic").asString(),0,1234567890L,key,value,headers)).get(35,TimeUnit.SECONDS);var a=new TreeMap<String,Object>();a.put("topic",r.topic());a.put("offset",r.offset());a.put("key_sha256",key==null?null:Json.sha(key));a.put("value_sha256",value==null?null:Json.sha(value));ack.add(a);}
        if(command.equals("transaction"))producer.commitTransaction();
      }result=ack;
    } else try(var admin=Admin.create(Broker.properties(bootstrap))) {
      if(command.equals("init")){var topics=new ArrayList<NewTopic>();for(String name:Main.TOPICS)topics.add(new NewTopic(name,1,(short)1).configs(Broker.TOPIC_CONFIG));admin.createTopics(topics).all().get(20,TimeUnit.SECONDS);result=Map.of("created",topics.size());}
      else if(command.equals("advance")){admin.alterConsumerGroupOffsets(args[2],Map.of(new TopicPartition(Main.INPUT,0),new OffsetAndMetadata(Long.parseLong(args[3])))).all().get(15,TimeUnit.SECONDS);result=Map.of("changed",true);}
      else if(command.equals("recreate")){admin.deleteTopics(List.of(Main.TOPICS.get(8))).all().get(15,TimeUnit.SECONDS);admin.createTopics(List.of(new NewTopic(Main.TOPICS.get(8),1,(short)1).configs(Broker.TOPIC_CONFIG))).all().get(15,TimeUnit.SECONDS);result=Map.of("recreated",true);}
      else {check(command.equals("offsets"),"probe_usage");var group=admin.listConsumerGroupOffsets(args[2]).partitionsToOffsetAndMetadata().get(15,TimeUnit.SECONDS);var offsets=new TreeMap<String,Object>();for(String name:Main.TOPICS){var off=group.get(new TopicPartition(name,0));offsets.put(name,off==null?null:off.offset());}result=offsets;}
    }
    System.out.println(new String(bytes(result),java.nio.charset.StandardCharsets.UTF_8));
  }
}
