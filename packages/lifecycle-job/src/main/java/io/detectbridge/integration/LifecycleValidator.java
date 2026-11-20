package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Worker-initiated fixed compiler exchange; never on the per-event path. */
public final class LifecycleValidator {
  public static final class Unavailable extends IOException {public Unavailable(){super("lifecycle_validator_unavailable");}}
  final JsonNode descriptor;final Path socket;
  public LifecycleValidator(JsonNode config){this(config,Path.of(config.get("validator_socket_path").asString()));}
  LifecycleValidator(JsonNode config,Path socket){this.descriptor=config.get("validator").deepCopy();this.socket=socket;}
  public JsonNode verify(byte[] plan,Path store)throws Exception {
    String planHash=Json.sha(plan),binding=hash(descriptor);Path proofs=store.resolve("validation-proofs");if(!Files.exists(proofs))mkdir(proofs);privatePath(proofs,true);
    String identity=hash(value(List.of(planHash,binding)));Path target=proofs.resolve(identity+".json");
    if(Files.exists(target)) {
      try {JsonNode wrapper=parse(read(target,RECORD),RECORD),proof=wrapper.get("proof");check(wrapper.size()==2&&wrapper.get("sha256").asString().equals(hash(proof)),"lifecycle_validation_proof_hash");response(proof,proof.get("nonce").asString(),planHash,binding);sync(target);sync(proofs);return proof;}
      catch(IllegalArgumentException|NullPointerException|Unavailable invalid){Files.move(target,proofs.resolve(".invalid-"+UUID.randomUUID()),StandardCopyOption.ATOMIC_MOVE);sync(proofs);}
    }
    long count;try(var entries=Files.list(proofs)){count=entries.filter(p->p.getFileName().toString().endsWith(".json")).count();}check(count<64,"lifecycle_validation_proofs_exhausted");reserve(store,RECORD,512L*MIB);
    String nonce=UUID.randomUUID().toString();ObjectNode request=object();request.put("version","1.0.0");request.put("nonce",nonce);request.put("plan_sha256",planHash);request.put("plan_base64",Base64.getEncoder().encodeToString(plan));request.put("validator_binding_sha256",binding);byte[] body=bytes(request);check(plan.length<=4*MIB&&body.length<=8*MIB,"lifecycle_validator_request_limit");
    JsonNode proof=exchange(body);response(proof,nonce,planHash,binding);publish(target,bytes(value(Map.of("proof",proof,"sha256",hash(proof)))));return proof;
  }
  private void response(JsonNode response,String nonce,String planHash,String binding)throws Exception {
    if(!(response.isObject()&&response.size()==6&&response.has("version")&&response.has("nonce")&&response.has("plan_sha256")&&response.has("validator_binding_sha256")&&response.has("passed")&&response.has("category")))throw new Unavailable();
    if(!response.get("version").asString().equals("1.0.0")||!response.get("nonce").asString().equals(nonce)||!response.get("plan_sha256").asString().equals(planHash)||!response.get("validator_binding_sha256").asString().equals(binding)||!response.get("passed").isBoolean())throw new Unavailable();
    String category=response.get("category").asString();if(!response.get("passed").asBoolean()&&category.equals("compiler_rejected"))throw new IllegalArgumentException("lifecycle_compiler_mismatch");
    if(!response.get("passed").asBoolean()||!category.equals("ok"))throw new Unavailable();
  }
  JsonNode exchange(byte[] body)throws Exception {
    long deadline=System.nanoTime()+java.time.Duration.ofSeconds(10).toNanos();
    try {
      Path address=safe(socket);privatePath(address.getParent(),true);long uid=currentUid();
      check(((Number)Files.getAttribute(address,"unix:uid",LinkOption.NOFOLLOW_LINKS)).longValue()==uid&&Files.getPosixFilePermissions(address).equals(PosixFilePermissions.fromString("rw-------"))&&(((Number)Files.getAttribute(address,"unix:mode",LinkOption.NOFOLLOW_LINKS)).intValue()&0170000)==0140000,"lifecycle_validator_socket");
      try(var channel=SocketChannel.open(StandardProtocolFamily.UNIX);var selector=Selector.open()) {
        channel.configureBlocking(false);channel.register(selector,SelectionKey.OP_CONNECT);if(!channel.connect(UnixDomainSocketAddress.of(address)))while(!channel.finishConnect())await(selector,SelectionKey.OP_CONNECT,deadline);
        transfer(channel,selector,ByteBuffer.allocate(4).putInt(body.length).flip(),false,deadline);transfer(channel,selector,ByteBuffer.wrap(body),false,deadline);
        ByteBuffer length=ByteBuffer.allocate(4);transfer(channel,selector,length,true,deadline);length.flip();long size=Integer.toUnsignedLong(length.getInt());if(size==0||size>RECORD)throw new Unavailable();ByteBuffer response=ByteBuffer.allocate((int)size);transfer(channel,selector,response,true,deadline);return parse(response.array(),RECORD);
      }
    }catch(Unavailable unavailable){throw unavailable;}catch(IOException|IllegalArgumentException failure){throw new Unavailable();}
  }
  private void transfer(SocketChannel channel,Selector selector,ByteBuffer buffer,boolean reading,long deadline)throws Exception {
    while(buffer.hasRemaining()){if(System.nanoTime()>=deadline)throw new Unavailable();int count=reading?channel.read(buffer):channel.write(buffer);if(count<0)throw new Unavailable();if(count==0)await(selector,reading?SelectionKey.OP_READ:SelectionKey.OP_WRITE,deadline);}
  }
  private void await(Selector selector,int operation,long deadline)throws Exception {long remaining=deadline-System.nanoTime();if(remaining<=0)throw new Unavailable();for(SelectionKey key:selector.keys())key.interestOps(operation);selector.select(Math.max(1,(remaining+999999)/1000000));selector.selectedKeys().clear();}
}
