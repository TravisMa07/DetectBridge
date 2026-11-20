package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Json;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Stable decision identities; physical receipt clocks never create another logical output. */
public final class LifecycleProtocol {
  public static String outputId(String deployment,String worker,long revision,String command,String kind,String inner) {return "sha256:"+hash(value(List.of("detectbridge.p15b.output/1",deployment,worker,revision,command,kind,inner)));}
  public static JsonNode output(JsonNode config,JsonNode selection,long sequence,String kind,String inner,JsonNode document) {
    ObjectNode result=object();result.put("version","1.0.0");for(String key:List.of("deployment_id","worker_id"))result.set(key,config.get(key));
    for(String key:List.of("revision","command_sha256","bundle_sha256","plan_sha256","compatibility_sha256","origin_incarnation"))result.set(key,selection.get(key));
    result.put("sequence",sequence);result.put("kind",kind);result.put("inner_key",inner);result.set("document",document.deepCopy());
    result.put("output_id",outputId(config.get("deployment_id").asString(),config.get("worker_id").asString(),selection.get("revision").asLong(),selection.get("command_sha256").asString(),kind,inner));
    result.put("document_sha256",hash(document));result.put("semantic_sha256",semanticHash(result));return result;
  }
  private static void manifest(ObjectNode doc) {if(doc.hasNonNull("manifest"))doc.set("manifest",value(Map.of("semantic_sha256",doc.at("/manifest/semantic_sha256"))));}
  public static String semanticHash(JsonNode envelope) {
    ObjectNode result=object();for(String key:List.of("deployment_id","worker_id","origin_incarnation","revision","command_sha256","bundle_sha256","plan_sha256","compatibility_sha256","kind","inner_key"))result.set(key,envelope.get(key));
    ObjectNode doc=((ObjectNode)envelope.get("document")).deepCopy();String kind=envelope.get("kind").asString();
    if(kind.equals("tagged")) {
      ((ObjectNode)doc.at("/event/event")).remove("ingested");JsonNode time=doc.at("/event/detectbridge/time");if(time.isObject()){((ObjectNode)time).remove("received");((ObjectNode)time).remove("processed");}
      JsonNode context=doc.at("/event/detectbridge/extensions/linux.context/context");if(context.isObject())((ObjectNode)context).remove("receipt");manifest(doc);
    }else if(kind.equals("detection"))manifest(doc);
    result.set("document",doc);return hash(result);
  }
  public static void verifyOutput(JsonNode config,JsonNode doc) {
    require("output",doc);check(doc.get("deployment_id").equals(config.get("deployment_id"))&&doc.get("worker_id").equals(config.get("worker_id")),"lifecycle_output_scope");
    check(doc.get("output_id").asString().equals(outputId(doc.get("deployment_id").asString(),doc.get("worker_id").asString(),doc.get("revision").asLong(),doc.get("command_sha256").asString(),doc.get("kind").asString(),doc.get("inner_key").asString()))&&doc.get("document_sha256").asString().equals(hash(doc.get("document")))&&doc.get("semantic_sha256").asString().equals(semanticHash(doc)),"lifecycle_output_integrity");
    check(bytes(doc.get("document")).length<=2*MIB&&bytes(doc).length<=2*MIB+65536,"lifecycle_output_size");
  }
  public static JsonNode ack(JsonNode config,JsonNode control,JsonNode selection,String phase,Long checkpoint,String category)throws Exception {
    ObjectNode p=object();p.put("version","1.0.0");for(String key:List.of("deployment_id","authority_id","worker_id","incarnation"))p.set(key,config.get(key));
    p.set("revision",control.get("revision"));p.put("command_sha256",hash(control));p.set("bundle_sha256",control.at("/proposal/bundle_sha256"));p.set("compatibility_sha256",control.at("/proposal/compatibility_sha256"));p.put("phase",phase);if(checkpoint==null)p.putNull("checkpoint_id");else p.put("checkpoint_id",checkpoint);p.put("category",category);
    List<Object> preimage=new ArrayList<>();preimage.add("detectbridge.p15b.ack/1");for(String key:List.of("deployment_id","authority_id","worker_id","incarnation","revision","command_sha256","bundle_sha256","compatibility_sha256","phase","checkpoint_id","category"))preimage.add(p.get(key));p.put("ack_id","sha256:"+hash(value(preimage)));
    return LifecycleCrypto.sign("ack",p,LifecycleCrypto.privateKey(java.nio.file.Path.of(config.get("private_key_path").asString())),LifecycleCrypto.publicKey(config.get("worker_public_key").asString()));
  }
}
