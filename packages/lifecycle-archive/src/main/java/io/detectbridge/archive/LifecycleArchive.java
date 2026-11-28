package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Broker;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.admin.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;

/** Private local lifecycle evidence archive, capture and managed retention entry point. */
public final class LifecycleArchive {
    static final Map<String,Integer> WIRE_LIMIT = Map.of(
        "control", 131072, "ack", 131072, "artifact", 1048576,
        "input", 2162688, "output", 4194304);

    static void verifyValue(String role, byte[] value) throws IOException {
        check(WIRE_LIMIT.containsKey(role) && (value==null || value.length<=WIRE_LIMIT.get(role)), "wire_value_limit");
    }
    static String implementation() throws Exception {
        Path jar=Path.of(LifecycleArchive.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        return Json.sha(Store.bounded(jar,64*MIB));
    }

    static void verifyBroker(Admin broker,LifecycleManifest manifest) throws Exception {
        String cluster=broker.describeCluster().clusterId().get(15,TimeUnit.SECONDS);
        check(cluster.equals(manifest.cluster),"cluster_changed");
        var actual=broker.describeTopics(manifest.topics.keySet()).allTopicNames().get(15,TimeUnit.SECONDS);
        for (var topic:manifest.topics.values()) {
            var descriptor=actual.get(topic.name());
            check(descriptor!=null && topic.id().equals(descriptor.topicId().toString()) && descriptor.partitions().size()==1
                  && descriptor.partitions().get(0).partition()==0,"topic_changed");
        }
    }

    static JsonNode wire(ConsumerRecord<byte[],byte[]> record,LifecycleManifest.Topic topic) throws IOException {
        verifyValue(topic.role(),record.value());
        var headers=new ArrayList<Object>();
        long bytes=record.serializedKeySize()+(long)record.serializedValueSize();
        for (var header:record.headers()) {
            check(headers.size()<128,"header_limit");
            bytes+=header.key().getBytes(java.nio.charset.StandardCharsets.UTF_8).length + (header.value()==null?0L:header.value().length);
            check(bytes<=LifecycleSegments.ROW_BYTES,"row_limit");
            Map<String,Object> pair=new TreeMap<>();
            pair.put("name",header.key()); pair.put("value",b64(header.value()));
            headers.add(pair);
        }
        Map<String,Object> m=new TreeMap<>();
        m.put("type","wire"); m.put("topic",record.topic()); m.put("topic_id",topic.id()); m.put("partition",record.partition());
        m.put("offset",record.offset()); m.put("timestamp",record.timestamp()); m.put("timestamp_type",record.timestampType().toString());
        m.put("key",b64(record.key())); m.put("value",b64(record.value())); m.put("headers",headers);
        return JSON.valueToTree(m);
    }

    static Map<String,Object> capture(LifecycleStore store,String bootstrap,boolean drain,Store.Hook hook) throws Exception {
        Properties p=Broker.properties(bootstrap);
        p.put("group.id",store.manifest.group);
        p.put("enable.auto.commit","false"); p.put("auto.offset.reset","none");
        p.put("key.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");
        p.put("value.deserializer","org.apache.kafka.common.serialization.ByteArrayDeserializer");
        p.put("max.poll.records","4"); p.put("max.partition.fetch.bytes","8388608");
        p.put("fetch.max.bytes","16777216");
        Set<TopicPartition> parts=new HashSet<>();
        for(String name:store.chains.keySet()) parts.add(new TopicPartition(name,0));
        try(Admin broker=Admin.create(Broker.properties(bootstrap)); var consumer=new KafkaConsumer<byte[],byte[]>(p)) {
            verifyBroker(broker,store.manifest);
            consumer.assign(parts);
            var committed=consumer.committed(parts);
            var earliest=consumer.beginningOffsets(parts);
            var target=consumer.endOffsets(parts);
            var offsets=new TreeMap<String,Long>();
            for (var part:parts) {
                Long offset=committed.get(part)==null?null:committed.get(part).offset();
                offsets.put(part.topic(),offset);
                long durable=store.chains.get(part.topic()).next;
                long start=Main.reconcile(durable,offset,earliest.get(part),target.get(part));
                consumer.seek(part,start);
            }
            if (!drain) return Map.of("binding_sha256",store.binding,"heads",store.heads(),"committed",offsets);
            long deadline=System.nanoTime()+Duration.ofMinutes(3).toNanos();
            while(true) {
                check(System.nanoTime()<deadline,"archive_drain_timeout");
                boolean done=true;
                for (var part:parts) if(store.chains.get(part.topic()).next<target.get(part)) {done=false;break;}
                var commit=new HashMap<TopicPartition,OffsetAndMetadata>();
                boolean advanced=false;
                boolean recorded=false;
                if(!done) {
                    var batch=consumer.poll(Duration.ofMillis(500));
                    verifyBroker(broker,store.manifest);
                    for (var part:parts) {
                        var chain=store.chains.get(part.topic());
                        long end=Math.min(target.get(part),consumer.position(part));
                        if(end<=chain.next) continue;
                        advanced=true;
                        List<JsonNode> rows=new ArrayList<>();
                        long size=0;
                        for(var record:batch.records(part)) {
                            if(record.offset()>=end) break;
                            recorded=true;
                            JsonNode row=wire(record,chain.topic);
                            int bytes=ndjson(row).length;
                            if(!rows.isEmpty() && size+bytes>SEGMENT) {
                                store.publish(part.topic(),rows,record.offset(),hook);
                                rows.clear(); size=0;
                            }
                            rows.add(row); size+=bytes;
                        }
                        store.publish(part.topic(),rows,end,hook);
                    }
                }
                if (!done && !advanced) continue;
                verifyBroker(broker,store.manifest);
                for (var part:parts) commit.put(part,new OffsetAndMetadata(store.chains.get(part.topic()).next));
                if(recorded) hook.at("before_kafka_commit");
                consumer.commitSync(commit,Duration.ofSeconds(20));
                if(done) break;
            }
            return Map.of("binding_sha256",store.binding,"heads",store.heads(),"rows",store.rows);
        }
    }

    static void rejectRetirement() throws IOException {throw new Failure("lifecycle_archive_permanent_hold");}

    static void run(String[] args) throws Exception {
        check(args.length>=2,"usage");
        Path root=Path.of(args[1]).toAbsolutePath().normalize();
        String sha=implementation();
        if(args[0].equals("init")) {
            check(args.length==4,"usage");
            LifecycleStore.create(root,Path.of(args[2]).toAbsolutePath().normalize(),Path.of(args[3]).toAbsolutePath().normalize(),sha);
            return;
        }
        try(var store=new LifecycleStore(root,args[0].equals("drain"),sha)) {
            switch(args[0]) {
                case "inspect" -> {check(args.length==2,"usage"); System.out.write(ndjson(Map.of("binding_sha256",store.binding,"heads",store.heads(),"rows",store.rows)));}
                case "export" -> {check(args.length==2,"usage"); store.export(System.out);}
                case "object" -> {check(args.length==3,"usage"); System.out.write(store.manifest.object(root.resolve("objects"),args[2]));}
                case "drain","status" -> {
                    check(args.length==3,"usage");
                    System.out.write(ndjson(capture(store,args[2],args[0].equals("drain"),phase->{
                        if(phase.equals(System.getenv("DETECTBRIDGE_LIFECYCLE_ARCHIVE_CRASH"))) Runtime.getRuntime().halt(86);
                    })));
                }
                case "retire" -> {check(args.length==2,"usage"); rejectRetirement();}
                default -> throw new Failure("usage");
            }
        }
        System.out.flush();
        check(!System.out.checkError(),"output_error");
    }

    public static void main(String[] args) {
        try {run(args);}
        catch(Exception e) {
            System.err.println(e instanceof Failure f ? f.category : "lifecycle_archive_"+e.getClass().getSimpleName());
            System.exit(2);
        }
    }
}
