package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import io.detectbridge.transport.Json;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.*;
import java.security.spec.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Fixed Ed25519 domains. No imported code or candidate-directed crypto settings. */
public final class LifecycleCrypto {
  public static byte[] decode(String text,int maximum) {
    byte[] bytes;try{bytes=Base64.getDecoder().decode(text);}catch(IllegalArgumentException malformed){throw new IllegalArgumentException("lifecycle_base64");}check(bytes.length<=maximum&&Base64.getEncoder().encodeToString(bytes).equals(text),"lifecycle_base64");return bytes;
  }
  public static PublicKey publicKey(String text)throws Exception {
    byte[] bytes=decode(text,64);PublicKey key;try{key=KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(bytes));}catch(InvalidKeySpecException invalid){throw new IllegalArgumentException("lifecycle_public_key_encoding");}
    check(Arrays.equals(bytes,key.getEncoded()),"lifecycle_key_encoding");return key;
  }
  public static PrivateKey privateKey(Path path)throws Exception {privatePath(path,false);return KeyFactory.getInstance("Ed25519").generatePrivate(new PKCS8EncodedKeySpec(read(path,128)));}
  private static byte[] preimage(String domain,JsonNode payload) {
    check(Set.of("control","artifact","ack").contains(domain),"lifecycle_signature_domain");
    byte[] prefix=("detectbridge.p15b."+domain+"/1\0").getBytes(StandardCharsets.UTF_8),body=bytes(payload),result=Arrays.copyOf(prefix,prefix.length+body.length);System.arraycopy(body,0,result,prefix.length,body.length);return result;
  }
  public static JsonNode sign(String domain,JsonNode payload,PrivateKey privateKey,PublicKey publicKey)throws Exception {
    Signature signature=Signature.getInstance("Ed25519");signature.initSign(privateKey);signature.update(preimage(domain,payload));
    ObjectNode result=object();result.put("version","1.0.0");result.put("key_sha256",Json.sha(publicKey.getEncoded()));result.set("payload",payload.deepCopy());result.put("signature",Base64.getEncoder().encodeToString(signature.sign()));
    verify(domain,result,publicKey);return result;
  }
  public static JsonNode verify(String domain,JsonNode wrapper,PublicKey key)throws Exception {
    require(domain,wrapper);check(wrapper.get("key_sha256").asString().equals(Json.sha(key.getEncoded())),"lifecycle_signing_key");
    byte[] signatureBytes=decode(wrapper.get("signature").asString(),64);check(signatureBytes.length==64,"lifecycle_signature_size");
    Signature signature=Signature.getInstance("Ed25519");signature.initVerify(key);signature.update(preimage(domain,wrapper.get("payload")));try{check(signature.verify(signatureBytes),"lifecycle_invalid_signature");}catch(SignatureException invalid){throw new IllegalArgumentException("lifecycle_invalid_signature");}return wrapper.get("payload").deepCopy();
  }
  public static void generate(Path privatePath,Path publicPath)throws Exception {KeyPair keys=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();write(privatePath,keys.getPrivate().getEncoded());write(publicPath,keys.getPublic().getEncoded());sync(privatePath.toAbsolutePath().getParent());if(!privatePath.toAbsolutePath().getParent().equals(publicPath.toAbsolutePath().getParent()))sync(publicPath.toAbsolutePath().getParent());}
}
