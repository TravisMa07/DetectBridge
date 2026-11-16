package io.detectbridge.assembly;

import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.apache.flink.api.common.ExecutionConfig;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.core.memory.DataInputDeserializer;
import org.apache.flink.core.memory.DataOutputSerializer;

class WireTest {
  @Test void realFlinkSerializerPreservesNullRawAndExactOutputBytesHeaders() throws Exception {
    var config=new ExecutionConfig().getSerializerConfig();
    var serializer=TypeInformation.of(AssemblyJob.Delivery.class).createSerializer(config);
    var output=new AssemblyJob.Delivery();output.kind="diagnostic";output.key="sha256:"+"a".repeat(64);
    output.document="{\"immutable\":true}".getBytes(java.nio.charset.StandardCharsets.UTF_8);output.binding="b".repeat(64);output.sequence=42;
    DataOutputSerializer buffer=new DataOutputSerializer(256);serializer.serialize(output,buffer);
    var restored=serializer.deserialize(new DataInputDeserializer(buffer.getCopyOfBuffer()));
    assertArrayEquals(output.document,restored.document);assertEquals(output.sequence,restored.sequence);
    var record=new AssemblyJob.Encode().serialize(restored,null,null);
    assertEquals(AssemblyBroker.DIAGNOSTIC,record.topic());assertArrayEquals(output.document,record.value());
    assertEquals(output.binding,new String(record.headers().lastHeader("detectbridge.runtime.binding").value(),java.nio.charset.StandardCharsets.UTF_8));
    var wire=new AssemblyJob.WireRecord();wire.topic=AssemblyBroker.INPUT;wire.offset=5;wire.partition=0;
    var source=TypeInformation.of(AssemblyJob.WireRecord.class).createSerializer(config);buffer.clear();source.serialize(wire,buffer);
    var decoded=source.deserialize(new DataInputDeserializer(buffer.getCopyOfBuffer()));assertNull(decoded.value);assertEquals(5,decoded.offset);
  }
  @Test void changedGroupTopicArtifactAndLimitsAreDistinctRuntimeBindings() {
    String[] args={"kafka:9092","group","cluster","in","event","manifest","diagnostic","quarantine","receipt","a".repeat(64)};
    String original=new AssemblyJob.Configuration(args).binding;
    for(int index:List.of(1,2,3,4,9)) {
      String[] changed=args.clone();changed[index]=index==9?"b".repeat(64):changed[index]+"-changed";
      assertNotEquals(original,new AssemblyJob.Configuration(changed).binding);
    }
    String[] changed=Arrays.copyOf(args,11);changed[10]="limits";
    assertNotEquals(original,new AssemblyJob.Configuration(changed).binding);
  }
}
