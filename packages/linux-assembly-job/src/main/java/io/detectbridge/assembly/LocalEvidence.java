package io.detectbridge.assembly;
import static io.detectbridge.detection.Contracts.check;
import io.detectbridge.transport.Json;
import java.net.URI;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
/** Explicit locally registered objects only; source URI text is never fetched. */
final class LocalEvidence {
 private final Path objects,manifest;private final String expected;private final Map<String,Long> allowed;
 private LocalEvidence(Path objects,Path manifest,String expected,Map<String,Long> allowed){this.objects=objects;this.manifest=manifest;this.expected=expected;this.allowed=Map.copyOf(allowed);}
 static String emptyHash(){return Machine.hash(Json.MAPPER.valueToTree(Map.of("version","1.0.0","objects",List.of())));}
 static LocalEvidence open(Path objects,Path manifest,String expected) throws java.io.IOException {
   JsonNode registration=registration(manifest);check(Machine.hash(registration).equals(expected),"assembly_registry_changed");
   Map<String,Long> allowed=new HashMap<>();long total=0;
   for(JsonNode entry:registration.get("objects")) {
     check(entry.get("size_bytes").isIntegralNumber(),"assembly_registry_integer");
     total=Math.addExact(total,entry.get("size_bytes").asLong());check(total<=64*1024*1024,"assembly_registry_limit");
     check(allowed.putIfAbsent(entry.get("sha256").asString(),entry.get("size_bytes").asLong())==null,"duplicate_registered_object");
   }
   return new LocalEvidence(objects,manifest,expected,allowed);
 }
 private static JsonNode registration(Path path) throws java.io.IOException {
   JsonNode value;
   if(Files.exists(path)){try(var in=Files.newInputStream(path)){value=Json.read(in.readNBytes(Json.MAX_VALUE+1));}}
   else value=Json.MAPPER.valueToTree(Map.of("version","1.0.0","objects",List.of()));
   Schemas.require("registration",value);return value;
 }
 void verify() throws java.io.IOException {check(Machine.hash(registration(manifest)).equals(expected),"assembly_registry_changed");}
 byte[] resolve(JsonNode raw) throws java.io.IOException {
        var e = raw.get("evidence");
        byte[] record;
        if (e.has("inline")) {
          String value = e.get("inline").asString();
          if (e.get("encoding").asString().equals("utf-8")) record = value.getBytes(java.nio.charset.StandardCharsets.UTF_8);
          else {
            check(value.length() % 4 == 0 && value.matches("[A-Za-z0-9+/]*={0,2}"), "encoding");
            record = Base64.getDecoder().decode(value);
          }
        } else {
          var r = e.get("reference");
          String hash = r.get("object_sha256").asString();
          check(hash.matches("[a-f0-9]{64}"), "object_hash");
          if(!allowed.containsKey(hash))throw new java.io.IOException("registered_object_unavailable");
          if(Files.isSymbolicLink(objects.resolve(hash)))throw new java.io.IOException("registered_object_unavailable");
          URI uri = URI.create(r.get("uri").asString());
          check(uri.getScheme() != null, "uri_scheme");
          String scheme = uri.getScheme().toLowerCase(Locale.ROOT);
          check(Set.of("urn", "file", "https", "s3").contains(scheme), "uri_scheme");
          check(uri.getRawUserInfo() == null && uri.getRawQuery() == null && uri.getRawFragment() == null
              && (uri.getRawAuthority() == null || !uri.getRawAuthority().contains("@")), "unsafe_uri");
          if (scheme.equals("urn")) check(uri.toString().equals("urn:sha256:" + hash), "content_address");
          if (Set.of("https", "s3").contains(scheme)) check(uri.getHost() != null, "uri_host");
          byte[] object;
          try (var in = Files.newInputStream(objects.resolve(hash))) { object = in.readNBytes(32 * 1024 * 1024 + 1); }
          check(object.length <= 32 * 1024 * 1024 && object.length == allowed.get(hash) && Json.sha(object).equals(hash), "object_integrity");
          long offset = 0, length = object.length;
          if (r.has("byte_range")) {
            var range = r.get("byte_range");
            check(range.get("offset").isIntegralNumber() && range.get("length").isIntegralNumber(), "range_integer");
            offset = range.get("offset").asLong(); length = range.get("length").asLong();
          }
          check(offset >= 0 && length > 0 && offset <= object.length && length <= object.length - offset, "range_bounds");
          check(offset == 0 || object[(int) offset - 1] == '\n', "record_start");
          long position = 0;
          for (int i = 0; i < offset; i++) if (object[i] == '\n') position++;
          if (raw.path("cursor").path("kind").asString().equals("dataset")) {
            check(raw.get("cursor").get("artifact_sha256").asString().equals(hash)
                && raw.get("cursor").get("position").asLong() == position, "cursor_range");
          }
          record = Arrays.copyOfRange(object, (int) offset, (int) (offset + length));
          check(offset + length == object.length || record[record.length - 1] == '\n', "record_end");
        }
        check(record.length <= Json.MAX_VALUE && Json.sha(record).equals(e.get("sha256").asString()), "record_digest");
        for (int i = 0; i < record.length - 1; i++) check(record[i] != '\n', "record_framing");
        return record;
 }
}
