package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Read-only qualification helper. A valid signature never establishes checkpoint completion. */
public final class LifecycleAckVerifier {
  record Entry(int index,byte[] wire,PublicKey key,String wireHash,String keyHash) {}
  @FunctionalInterface interface Verification {JsonNode verify(byte[] wire,PublicKey key)throws Exception;}
  static List<Entry> prepare(Path path,String expected)throws Exception {
    path=safe(path);privatePath(path.getParent(),true);privatePath(path,false);byte[] raw=read(path,16*MIB);
    check(expected.matches("[a-f0-9]{64}")&&Json.sha(raw).equals(expected),"lifecycle_ack_batch_request_hash");
    JsonNode request=parse(raw,16*MIB);LifecycleBatchProducer.closed(request,Set.of("version","records"));check(Arrays.equals(raw,bytes(request))&&LifecycleBatchProducer.text(request.get("version")).equals("1.0.0"),"lifecycle_ack_batch_request");
    JsonNode records=request.get("records");check(records!=null&&records.isArray()&&records.size()>=1&&records.size()<=128,"lifecycle_ack_batch_count");List<Entry> entries=new ArrayList<>();long total=0;
    for(JsonNode record:records) {
      LifecycleBatchProducer.closed(record,Set.of("index","public_key","wire_base64","wire_sha256","key_sha256"));
      int index=(int)LifecycleBatchProducer.integer(record.get("index"),0,127);check(index==entries.size(),"lifecycle_ack_batch_index");
      String encodedKey=LifecycleBatchProducer.text(record.get("public_key")),encodedWire=LifecycleBatchProducer.text(record.get("wire_base64"));check(encodedKey.length()<=88&&encodedWire.length()<=87384,"lifecycle_ack_batch_encoded_limit");
      byte[] key=LifecycleCrypto.decode(encodedKey,64),wire=LifecycleCrypto.decode(encodedWire,65536);check(wire.length>=1,"lifecycle_ack_batch_wire_limit");total=Math.addExact(total,wire.length);check(total<=8L*MIB,"lifecycle_ack_batch_aggregate");
      String keyHash=LifecycleBatchProducer.text(record.get("key_sha256")),wireHash=LifecycleBatchProducer.text(record.get("wire_sha256"));check(keyHash.matches("[a-f0-9]{64}")&&wireHash.matches("[a-f0-9]{64}")&&keyHash.equals(Json.sha(key))&&wireHash.equals(Json.sha(wire)),"lifecycle_ack_batch_input_hash");
      // Construct every recorded registration key before any wire verification. An unusable
      // trusted key is infrastructure failure, never a clean negative remote signature.
      entries.add(new Entry(index,wire,LifecycleCrypto.publicKey(encodedKey),wireHash,keyHash));
    }
    return entries;
  }
  static JsonNode verify(byte[] wire,PublicKey key)throws Exception {return LifecycleCrypto.verify("ack",parse(wire,65536),key);}
  static JsonNode run(Path request,String requestHash)throws Exception {return run(request,requestHash,LifecycleAckVerifier::verify);}
  static JsonNode run(Path request,String requestHash,Verification verification)throws Exception {
    List<Entry> entries=prepare(request,requestHash);var results=Json.MAPPER.createArrayNode();
    for(Entry entry:entries) {
      ObjectNode result=object();result.put("index",entry.index());result.put("wire_sha256",entry.wireHash());result.put("key_sha256",entry.keyHash());
      try {JsonNode payload=verification.verify(entry.wire(),entry.key());result.put("verified",true);result.put("payload_sha256",hash(payload));}
      catch(IllegalArgumentException|SignatureException invalid) {result.put("verified",false);result.put("category","signature_invalid");}
      results.add(result);
    }
    JsonNode response=value(Map.of("version","1.0.0","request_sha256",requestHash,"results",results));check(bytes(response).length<=RECORD,"lifecycle_ack_batch_result_limit");return response;
  }
  static void origins(String qualificationHash,String runtimeHash)throws Exception {
    codeSource(LifecycleAckVerifier.class,qualificationHash);codeSource(LifecycleSupport.class,runtimeHash);codeSource(Schemas.class,PRODUCER);
    check(LifecycleAckVerifier.class.getClassLoader()==LifecycleSupport.class.getClassLoader()&&LifecycleSupport.class.getClassLoader()==Schemas.class.getClassLoader(),"lifecycle_ack_batch_classloader");
  }
  public static void main(String[] args) {
    try {check(args.length==4,"lifecycle_ack_batch_arguments");origins(args[0],args[1]);System.out.println(new String(bytes(run(Path.of(args[2]),args[3])),StandardCharsets.UTF_8));}
    catch(Exception failure) {System.err.println(new String(bytes(value(Map.of("category","lifecycle_qualification_ack_verifier_failed","exception_class",LifecycleTool.safeClass(failure.getClass().getName())))),StandardCharsets.UTF_8));System.exit(1);}
  }
}
