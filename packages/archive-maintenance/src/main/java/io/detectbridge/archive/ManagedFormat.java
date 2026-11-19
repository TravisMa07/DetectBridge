package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import com.networknt.schema.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Versioned opt-in metadata; existing archive formats and source bytes stay unchanged. */
final class ManagedFormat {
  static final long CONTROL=32L*MIB, HEADROOM=64L*MIB;
  private static final Map<String,Schema> SCHEMAS=new HashMap<>();
  static {
    for(String name:List.of("registration","holds","head","plan","retirement","import")) {
      try(var in=ManagedFormat.class.getResourceAsStream("/archive-maintenance/v1/"+name+".schema.json")) {
        String text=new String(Objects.requireNonNull(in).readAllBytes(),StandardCharsets.UTF_8);
        JsonNode schema=JSON.readTree(text);noRefs(schema);
        var registry=SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,b->b.schemas(Map.of(schema.get("$id").asString(),text)));
        SCHEMAS.put(name,registry.getSchema(SchemaLocation.of(schema.get("$id").asString())));
      }catch(Exception failure){throw new ExceptionInInitializerError("managed_schema_load");}
    }
  }
  static void require(String kind,JsonNode value)throws IOException {
    integers(value);check(SCHEMAS.get(kind).validate(value,c->c.executionConfig(e->e.formatAssertionsEnabled(true))).isEmpty(),"managed_schema_"+kind);
  }
  static JsonNode metadata(Path path,String kind)throws IOException {
    byte[] raw=Store.bounded(path,16*MIB);
    check(Arrays.equals(Store.bounded(Store.checksumPath(path),65),(Json.sha(raw)+"\n").getBytes(StandardCharsets.US_ASCII)),"managed_metadata_integrity");
    JsonNode value=read(raw,16*MIB);require(kind,value);check(Arrays.equals(raw,ndjson(value)),"managed_metadata_noncanonical");return value;
  }
  static void metadata(Path path,String kind,JsonNode value)throws IOException {
    require(kind,value);byte[] raw=ndjson(value);check(raw.length<=16*MIB,"managed_metadata_limit");Store.write(path,raw);Store.writeChecksum(path,raw);
  }
  static void metadata(Path path,String kind,JsonNode value,Store.Hook hook,String phase)throws IOException {
    require(kind,value);byte[] raw=ndjson(value);check(raw.length<=16*MIB,"managed_metadata_limit");
    ManagedPending.write(path,raw,phase,hook);
    byte[] checksum=(Json.sha(raw)+"\n").getBytes(StandardCharsets.US_ASCII);
    ManagedPending.write(Store.checksumPath(path),checksum,phase+"_checksum",hook);
  }
  static JsonNode head(Path path,String kind,String managed)throws IOException {
    byte[] raw=Store.bounded(path,MIB);JsonNode value=read(raw,MIB);require("head",value);
    check(Arrays.equals(raw,ndjson(value))&&value.get("kind").asString().equals(kind)&&value.get("managed_id").asString().equals(managed),"managed_head_binding");
    ObjectNode body=((ObjectNode)value).deepCopy();body.remove("checksum_sha256");check(hash(body).equals(value.get("checksum_sha256").asString()),"managed_head_integrity");return value;
  }
  static ObjectNode head(String kind,String managed,long sequence,String record) {
    ObjectNode value=JSON.createObjectNode();value.put("version","1.0.0");value.put("managed_id",managed);value.put("kind",kind);value.put("sequence",sequence);
    if(record==null)value.putNull("record_sha256");else value.put("record_sha256",record);value.put("checksum_sha256",hash(value));return value;
  }
}
