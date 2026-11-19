package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import java.io.*;
import java.nio.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** A named operation may recover only its own bounded unpublished admission. */
final class ManagedPending {
  static JsonNode verify(ManagedStore store,Path path)throws IOException {
    Store.safeAncestors(path);check(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"managed_pending_layout");
    String operation=path.getFileName().toString().substring(9);
    try{check(UUID.fromString(operation).toString().equals(operation),"managed_pending_owner");}catch(IllegalArgumentException invalid){throw new Failure("managed_pending_owner");}
    JsonNode owner=read(Store.bounded(path.resolve("owner.json"),MIB),MIB);
    check(owner.isObject()&&owner.size()==4&&owner.get("version").asString().equals("1.0.0")&&owner.get("managed_id").asString().equals(store.managed)&&owner.get("operation_id").asString().equals(operation)&&Set.of("segment","progress").contains(owner.get("kind").asString()),"managed_pending_owner");
    Set<String> names=owner.get("kind").asString().equals("segment")?Set.of("owner.json","publication","records.ndjson.gz","segment.json","segment.sha256"):Set.of("owner.json","progress.json");
    try(var entries=Files.newDirectoryStream(path)){for(Path entry:entries){
      String name=entry.getFileName().toString();check(names.contains(name),"managed_pending_foreign");
      if(name.equals("publication")){check(Files.isDirectory(entry,LinkOption.NOFOLLOW_LINKS),"managed_pending_foreign");try(var files=Files.newDirectoryStream(entry)){for(Path file:files)check(Set.of("records.ndjson.gz","segment.json","segment.sha256").contains(file.getFileName().toString())&&Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)&&Files.size(file)<=17L*MIB,"managed_pending_foreign");}}
      else check(Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS)&&Files.size(entry)<=17L*MIB,"managed_pending_foreign");
    }}
    return owner;
  }
  static Path open(ManagedStore store,String kind)throws IOException {
    check(store.writer&&store.operation!=null,"managed_operation_required");Path path=store.root.resolve(".partial-"+store.operation);
    if(Files.exists(path,LinkOption.NOFOLLOW_LINKS)){verify(store,path);Store.deletePartial(path);Store.sync(store.root);}
    store.reserve(4096);Files.createDirectory(path);Store.write(path.resolve("owner.json"),ndjson(Map.of("version","1.0.0","managed_id",store.managed,"operation_id",store.operation,"kind",kind)));Store.sync(path);Store.sync(store.root);store.hook.at("after_admission_owner");return path;
  }
  static void write(Path path,byte[] bytes,String kind,Store.Hook hook)throws IOException {
    try(var channel=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
      int middle=bytes.length/2;var first=ByteBuffer.wrap(bytes,0,middle);while(first.hasRemaining())channel.write(first);hook.at("during_"+kind);
      var rest=ByteBuffer.wrap(bytes,middle,bytes.length-middle);while(rest.hasRemaining())channel.write(rest);hook.at("before_"+kind+"_sync");channel.force(true);
    }
  }
  static void segment(ManagedStore store,Path target,byte[] zipped,JsonNode metadata)throws IOException {
    require("segment",metadata);store.reserve(zipped.length+ndjson(metadata).length+65+4096);Path stage=open(store,"segment");
    write(stage.resolve("records.ndjson.gz"),zipped,"payload",store.hook);store.hook.at("after_payload");write(stage.resolve("segment.json"),ndjson(metadata),"metadata",store.hook);Store.writeChecksum(stage.resolve("segment.json"),ndjson(metadata));store.hook.at("after_metadata");
    // Move a child containing only the unchanged v1 files. The owner stays outside authority.
    Path publication=stage.resolve("publication");Files.createDirectory(publication);
    for(String name:List.of("records.ndjson.gz","segment.json","segment.sha256"))Files.move(stage.resolve(name),publication.resolve(name));
    Store.sync(publication);Store.sync(stage);store.hook.at("before_rename");
    var parents=new ArrayList<Path>();for(Path parent=target.getParent();!Files.exists(parent);parent=parent.getParent())parents.add(parent);Collections.reverse(parents);for(Path parent:parents){Files.createDirectory(parent);Store.sync(parent);Store.sync(parent.getParent());}
    check(!Files.exists(target,LinkOption.NOFOLLOW_LINKS),"publication_conflict");Files.move(publication,target,StandardCopyOption.ATOMIC_MOVE);store.hook.at("after_rename");Store.sync(target.getParent());store.hook.at("after_directory_sync");Store.deletePartial(stage);Store.sync(store.root);
  }
  static void progress(ManagedStore store,Object value)throws IOException {
    byte[] bytes=ndjson(value);check(bytes.length<=MIB,"progress_limit");store.reserve(bytes.length+4096);Path stage=open(store,"progress");Store.write(stage.resolve("progress.json"),bytes);Store.sync(stage);Files.move(stage.resolve("progress.json"),store.root.resolve("progress.json"),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);Store.sync(store.root);Store.deletePartial(stage);Store.sync(store.root);
  }
}
