package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.*;
import com.networknt.schema.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Closed first-party protocol, canonical integrity and private local persistence. */
public final class LifecycleSupport {
  public static final String PRODUCER="51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d";
  public static final int MIB=1048576, STATE_BYTES=170000384, RECORD=65536;
  private static final Map<String,String> DOCUMENTS=new HashMap<>();
  private static final SchemaRegistry REGISTRY=registry();
  private static SchemaRegistry registry() {
    for(String name:List.of("common","control","artifact","ack","output","worker-config","state")) load("lifecycle-runtime/v1/"+name+".schema.json");
    load("lifecycle/v1/manifest.schema.json");
    return SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,b->b.schemas(DOCUMENTS));
  }
  private static void load(String path) {
    try(var in=LifecycleSupport.class.getResourceAsStream("/"+path)) {
      String value=new String(Objects.requireNonNull(in).readAllBytes(),StandardCharsets.UTF_8);
      DOCUMENTS.put(Json.MAPPER.readTree(value).get("$id").asString(),value);
    }catch(Exception e){throw new IllegalStateException("lifecycle_schema_load");}
  }
  public static void require(String name,JsonNode value) {
    integerSyntax(value);
    String id=name.equals("manifest")?"urn:detectbridge:lifecycle:1.0.0:manifest":"urn:detectbridge:lifecycle-runtime:1.0.0:"+name;
    check(REGISTRY.getSchema(SchemaLocation.of(id)).validate(value,c->c.executionConfig(x->x.formatAssertionsEnabled(true))).isEmpty(),"lifecycle_schema_"+name);
  }
  public static void integerSyntax(JsonNode node) {
    check(!node.isFloatingPointNumber(),"lifecycle_integer_syntax");
    if(node.isObject()) {for(var field:node.properties())if(!Set.of("core","document").contains(field.getKey()))integerSyntax(field.getValue());}
    else if(node.isArray())for(JsonNode child:node)integerSyntax(child);
  }
  public static JsonNode parse(byte[] bytes,int limit) {
    check(bytes.length<=limit,"lifecycle_input_limit");
    try {
      StandardCharsets.UTF_8.newDecoder().onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes));
      var factory=tools.jackson.core.json.JsonFactory.builder().enable(tools.jackson.core.StreamReadFeature.STRICT_DUPLICATE_DETECTION)
          .streamReadConstraints(tools.jackson.core.StreamReadConstraints.builder().maxNestingDepth(128).maxStringLength(8*MIB).maxNumberLength(128).build()).build();
      var result=tools.jackson.databind.json.JsonMapper.builder(factory).enable(tools.jackson.databind.DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build().readTree(bytes);
      io.detectbridge.detection.Normalized.unicode(result);return result;
    }catch(Exception failure){throw new IllegalArgumentException("lifecycle_invalid_json");}
  }
  public static byte[] bytes(JsonNode value){return Json.bytes(canonical(value));}
  public static String hash(JsonNode value){return Json.sha(bytes(value));}
  public static ObjectNode object(){return Json.MAPPER.createObjectNode();}
  public static JsonNode value(Object value){return Json.MAPPER.valueToTree(value);}
  public static Path safe(Path input) throws IOException {
    check(!input.toString().contains("\u0000"),"lifecycle_path");
    for(Path component:input)check(!component.toString().equals(".."),"lifecycle_path");
    Path path=input.toAbsolutePath();
    for(Path cursor=path;cursor!=null;cursor=cursor.getParent())check(!Files.isSymbolicLink(cursor),"lifecycle_symlink");return path;
  }
  public static byte[] read(Path path,int max)throws IOException {
    path=safe(path);check(Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS),"lifecycle_regular_file");
    try(var in=Files.newInputStream(path)){byte[] result=in.readNBytes(max+1);check(result.length<=max,"lifecycle_file_limit");return result;}
  }
  public static long currentUid()throws IOException {
    // UnixSystem's passwd lookup reports zero for unknown Linux UIDs. This fixed
    // kernel process path intentionally follows /proc/self; imported paths never do.
    if(System.getProperty("os.name").toLowerCase(Locale.ROOT).contains("linux"))return ((Number)Files.getAttribute(Path.of("/proc/self"),"unix:uid")).longValue();
    return new com.sun.security.auth.module.UnixSystem().getUid();
  }
  public static void privatePath(Path path,boolean directory)throws IOException {
    path=safe(path);check(directory?Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS):Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS),"lifecycle_private_path");
    long uid=currentUid();
    check(((Number)Files.getAttribute(path,"unix:uid",LinkOption.NOFOLLOW_LINKS)).longValue()==uid,"lifecycle_private_owner");
    check(Files.getPosixFilePermissions(path).equals(PosixFilePermissions.fromString(directory?"rwx------":"rw-------")),"lifecycle_private_mode");
    if(!directory)check(((Number)Files.getAttribute(path,"unix:nlink")).intValue()==1,"lifecycle_private_link");
  }
  public static void mkdir(Path path)throws IOException {Files.createDirectory(safe(path),PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")));}
  public static void sync(Path path)throws IOException {try(var channel=FileChannel.open(safe(path),StandardOpenOption.READ)){channel.force(true);}}
  public static void write(Path path,byte[] data)throws IOException {
    path=safe(path);try(var channel=FileChannel.open(path,Set.of(StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE),PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------")))) {
      var buffer=java.nio.ByteBuffer.wrap(data);while(buffer.hasRemaining())channel.write(buffer);channel.force(true);
    }
  }
  @FunctionalInterface interface Force {void sync(Path path)throws IOException;}
  public static void publish(Path path,byte[] data)throws IOException {publish(path,data,LifecycleSupport::sync);}
  static void publish(Path path,byte[] data,Force force)throws IOException {
    path=safe(path);if(Files.exists(path)){check(Arrays.equals(read(path,Math.max(data.length,RECORD)),data),"lifecycle_immutable_conflict");force.sync(path);force.sync(path.getParent());return;}
    Path temporary=path.resolveSibling(".partial-"+UUID.randomUUID());
    try{write(temporary,data);Files.move(temporary,path,StandardCopyOption.ATOMIC_MOVE);force.sync(path.getParent());}
    catch(IOException|RuntimeException failure){try{if(Files.deleteIfExists(temporary))sync(path.getParent());}catch(Exception cleanup){failure.addSuppressed(cleanup);}throw failure;}
  }
  public static long used(Path root)throws IOException {
    long total=0,count=0;try(var entries=Files.walk(safe(root))){var iterator=entries.iterator();while(iterator.hasNext()){Path p=iterator.next();check(++count<=65536,"lifecycle_store_entries");privatePath(p,Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS));if(Files.isRegularFile(p))total=Math.addExact(total,Files.size(p));}}return total;
  }
  public static void reserve(Path root,long bytes,long cap)throws IOException {check(used(root)+bytes<=cap&&Files.getFileStore(root).getUsableSpace()>=128L*MIB+bytes,"lifecycle_storage_exhausted");}
  public static ObjectNode commonBinding(JsonNode c) {
    ObjectNode result=object();for(String key:List.of("version","deployment_id","authority_id","authority_key_sha256","cluster_id","runtime_sha256","producer_sha256","image","compatibility_sha256","limits","validator"))result.set(key,c.get(key));
    ObjectNode topics=result.putObject("topics");for(String role:List.of("control","artifact","ack","output"))topics.set(role,c.at("/topics/"+role));return result;
  }
  public static ObjectNode workerBinding(JsonNode c) {return (ObjectNode)value(Map.of("version","1.0.0","runtime_binding_sha256",c.get("runtime_binding_sha256"),"worker_id",c.get("worker_id"),"input_topic",c.at("/topics/input"),"evidence_registry_sha256",c.get("evidence_registry_sha256"),"state_codec","lifecycle-worker/1.0.0"));}
  public static void config(JsonNode c) throws Exception {
    require("worker-config",c);check(hash(commonBinding(c)).equals(c.get("runtime_binding_sha256").asString())&&hash(workerBinding(c)).equals(c.get("worker_checkpoint_binding_sha256").asString()),"lifecycle_binding");
    check(Json.sha(LifecycleCrypto.publicKey(c.get("authority_public_key").asString()).getEncoded()).equals(c.get("authority_key_sha256").asString()),"lifecycle_authority_key");
    check(Json.sha(LifecycleCrypto.publicKey(c.get("worker_public_key").asString()).getEncoded()).equals(c.get("worker_key_sha256").asString()),"lifecycle_worker_key");
    privatePath(Path.of(c.get("private_key_path").asString()),false);
    var pairProof=java.security.Signature.getInstance("Ed25519");pairProof.initSign(LifecycleCrypto.privateKey(Path.of(c.get("private_key_path").asString())));pairProof.update("detectbridge.p15b.worker-key/1".getBytes(StandardCharsets.UTF_8));byte[] signed=pairProof.sign();pairProof.initVerify(LifecycleCrypto.publicKey(c.get("worker_public_key").asString()));pairProof.update("detectbridge.p15b.worker-key/1".getBytes(StandardCharsets.UTF_8));check(pairProof.verify(signed),"lifecycle_worker_key_pair");
  }
  public static void codeSource(Class<?> type,String expected)throws Exception {
    Path jar=Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI());check(Json.sha(read(jar,64*MIB)).equals(expected),"lifecycle_artifact_mismatch");
  }
}
