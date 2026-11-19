package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Managed read-only export. Holds a shared Java archive lease through all output writes. */
public final class ReplaySource {
  public static void main(String[] args) {
    try {
      check(args.length==3,"replay_reader_arguments");
      Path root=Path.of(args[0]),request=Path.of(args[1]),out=Path.of(args[2]);
      Store.safeAncestors(request);Store.safeAncestors(out);
      JsonNode refs=read(Store.bounded(request,16*MIB),16*MIB);
      check(refs.isArray()&&refs.size()>0&&refs.size()<=1000,"replay_reference_limit");
      check(Files.isDirectory(out,LinkOption.NOFOLLOW_LINKS),"replay_export_directory");
      try(ManagedStore store=new ManagedStore(root,false,Main.implementation())) {
        var wanted=new TreeMap<String,JsonNode>();
        for(JsonNode ref:refs) {
          check(ref.isObject()&&ref.size()==3&&ref.path("offset").isIntegralNumber()&&ref.get("offset").canConvertToLong()&&ref.get("offset").asLong()>=0,"replay_reference");
          store.topic(ref.get("topic").asString());
          check(ref.get("offset").asLong()>=store.floors.get(ref.get("topic").asString()).next(),"archive_retired");
          String key=ref.get("topic").asString()+"/"+ref.get("offset").asLong();
          check(wanted.put(key,ref)==null,"replay_reference_duplicate");
        }
        var rows=new ArrayList<JsonNode>();var hashes=new ArrayList<Object>();long[] size={0};
        for(String topic:refs.valueStream().map(r->r.get("topic").asString()).collect(java.util.stream.Collectors.toCollection(TreeSet::new))) {
          store.forEachRow(topic,row->{
            String key=topic+"/"+row.get("offset").asLong();JsonNode ref=wanted.remove(key);
            if(ref!=null) {
              byte[] value=decode(row.get("value"));
              check(value!=null&&Json.sha(value).equals(ref.get("value_sha256").asString()),"replay_value_integrity");
              size[0]+=bytes(row).length;check(size[0]<=64L*MIB,"replay_selected_bytes");
              rows.add(JSON.valueToTree(Map.of("reference",ref,"wire",row)));
              hashes.add(Map.of("reference",ref,"wire_sha256",hash(row)));
            }
          });
        }
        check(wanted.isEmpty(),"replay_missing_reference");
        Path objects=out.resolve("objects");Files.createDirectory(objects);long total=0;
        // The full bounded registration retains provenance/terms and source bindings too.
        Set<String> objectsSet=Store.strings(store.config.get("objects"));
        for(String sha:objectsSet){byte[] b=store.object(sha);total+=b.length;check(total<=64L*MIB,"replay_objects_limit");Store.write(objects.resolve(sha),b);}
        Store.sync(objects);
        Store.write(out.resolve("rows.json"),ndjson(rows));
        Store.write(out.resolve("export.json"),ndjson(Map.of("archive_binding_sha256",store.binding,"references",hashes,"objects",objectsSet)));
        Store.sync(out);
      }
    }catch(Exception failure){String reason=failure instanceof Format.Failure f?f.category:"archive_export_failed";System.err.println("historical_"+reason+":"+failure.getClass().getSimpleName());System.exit(1);}
  }
}
