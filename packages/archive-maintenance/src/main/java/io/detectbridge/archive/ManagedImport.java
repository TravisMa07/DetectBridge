package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Python validates completed P05 semantics under its source lease; Java binds exact opaque bytes. */
final class ManagedImport {
  static final Set<String> OBJECT_FILES=Set.of("object.json","object.sha256","bytes.ndjson.gz");
  static Path logical(JsonNode file)throws IOException {
    String raw=file.get("path").asString();Path path=Path.of(raw);
    check(!path.isAbsolute()&&path.normalize().toString().replace('\\','/').equals(raw)&&path.getNameCount()>=2,"managed_import_path");
    for(Path part:path)check(!Set.of(".","..").contains(part.toString()),"managed_import_path");
    String scope=path.getName(0).toString(),kind=file.get("kind").asString(),role=file.get("role").asString();
    boolean valid=switch(role) {
      case "manifest" -> raw.equals("run/manifest.json");case "manifest_checksum" -> raw.equals("run/manifest.sha256");
      case "timing_index" -> raw.equals("run/timing-index.json");case "checkpoint" -> raw.equals("run/checkpoint.json");
      case "segment_payload" -> raw.matches("run/segments/[0-9]{8}/records\\.ndjson");case "segment_commit" -> raw.matches("run/segments/[0-9]{8}/commit\\.json");
      case "framing_index" -> raw.equals("index/framing.json");case "capture_projection" -> raw.equals("index/captures.json");
      default -> raw.equals("cache/objects/sha256/"+file.get("sha256").asString());
    };
    check(valid&&kind.equals(scope.equals("index")?"derived":"original"),"managed_import_role");return path;
  }
  static void metadata(ManagedStore store,JsonNode metadata)throws IOException {
    ManagedFormat.require("import",metadata);check(metadata.get("managed_id").asString().equals(store.managed),"managed_import_binding");
    check(metadata.get("id").asString().equals(hash(List.of("detectbridge.archive.p05-import/1",store.managed,metadata.get("run_id").asString(),metadata.get("manifest_sha256").asString(),metadata.get("files")))),"managed_import_identity");
    Set<String> paths=new HashSet<>();String previous=null;boolean manifest=false;long runBytes=0,cacheBytes=0,derived=0;
    for(JsonNode file:metadata.get("files")) {
      logical(file);String path=file.get("path").asString();check(paths.add(path),"managed_import_duplicate_path");
      String order=file.get("role").asString()+"\0"+path+"\0"+file.get("sha256").asString();check(previous==null||previous.compareTo(order)<0,"managed_import_order");previous=order;
      long length=file.get("length").asLong();if(path.startsWith("run/"))runBytes=Math.addExact(runBytes,length);else if(path.startsWith("cache/"))cacheBytes=Math.addExact(cacheBytes,length);else derived=Math.addExact(derived,length);
      if(path.equals("run/manifest.json")){manifest=true;check(file.get("sha256").equals(metadata.get("manifest_sha256")),"managed_import_manifest_binding");}
    }
    check(manifest&&runBytes<=512L*MIB&&cacheBytes<=64L*MIB&&derived<=16L*MIB,"managed_import_closure_budget");
  }
  static Set<String> hashes(JsonNode metadata){Set<String> result=new TreeSet<>();for(JsonNode file:metadata.get("files"))result.add(file.get("sha256").asString());return result;}
  static void subset(Path directory,Set<String> names,boolean dirs,long limit)throws IOException {
    Store.safeAncestors(directory);check(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"managed_import_directory");
    try(var entries=Files.newDirectoryStream(directory)){for(Path entry:entries)check(names.contains(entry.getFileName().toString())&&(dirs?Files.isDirectory(entry,LinkOption.NOFOLLOW_LINKS):Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS))&&(dirs||Files.size(entry)<=limit),"managed_import_foreign_file");}
  }
  static JsonNode verifyPartial(ManagedStore store,Path path)throws IOException {
    check(path.toAbsolutePath().normalize().getParent().equals(store.root.resolve("imports")),"managed_import_partial_owner");String name=path.getFileName().toString();check(name.startsWith(".partial-"),"managed_import_partial_owner");String operation=name.substring(9);
    try{check(UUID.fromString(operation).toString().equals(operation),"managed_import_partial_owner");}catch(IllegalArgumentException invalid){throw new Failure("managed_import_partial_owner");}
    return owner(store,path);
  }
  static JsonNode owner(ManagedStore store,Path path)throws IOException {
    Store.safeAncestors(path);check(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"managed_import_partial_owner");
    JsonNode owner=read(Store.bounded(path.resolve("owner.json"),16*MIB),16*MIB);
    check(owner.isObject()&&owner.size()==4&&owner.hasNonNull("version")&&owner.hasNonNull("operation_id")&&owner.hasNonNull("managed_id")&&owner.hasNonNull("metadata")&&owner.get("version").asString().equals("1.0.0")&&owner.get("operation_id").asString().equals(path.getFileName().toString().substring(9))&&owner.get("managed_id").asString().equals(store.managed),"managed_import_partial_owner");
    JsonNode metadata=owner.get("metadata");metadata(store,metadata);
    try(var entries=Files.newDirectoryStream(path)){for(Path entry:entries){String name=entry.getFileName().toString();check(Set.of("owner.json","publication").contains(name),"managed_import_foreign_file");if(name.equals("owner.json"))check(Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS),"unsafe_path");else partialPublication(store,entry,metadata);}}
    return metadata;
  }
  static void partialPublication(ManagedStore store,Path publication,JsonNode metadata)throws IOException {
    Store.safeAncestors(publication);check(Files.isDirectory(publication,LinkOption.NOFOLLOW_LINKS),"unsafe_path");
    try(var entries=Files.newDirectoryStream(publication)){for(Path entry:entries){String name=entry.getFileName().toString();check(Set.of("import.json","import.sha256","objects").contains(name),"managed_import_foreign_file");if(name.equals("objects")){subset(entry,hashes(metadata),true,0);try(var objects=Files.newDirectoryStream(entry)){for(Path object:objects)subset(object,OBJECT_FILES,false,48L*MIB);}}else check(Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS)&&Files.size(entry)<=16L*MIB,"unsafe_path");}}
  }
  static JsonNode verifyClosure(ManagedStore store,String id)throws IOException {
    check(id.matches("[a-f0-9]{64}"),"managed_import_identity");check(!store.retiredImports.contains(id),"archive_retired");return verifyAt(store,store.root.resolve("imports").resolve(id),id);
  }
  static JsonNode verifyAt(ManagedStore store,Path directory,String id)throws IOException {
    Store.safeAncestors(directory);check(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"managed_import_directory");Store.contents(directory,Set.of("import.json","import.sha256","objects"));JsonNode value=ManagedFormat.metadata(directory.resolve("import.json"),"import");metadata(store,value);check(value.get("id").asString().equals(id),"managed_import_identity");
    Path objects=directory.resolve("objects");Store.safeAncestors(objects);check(Files.isDirectory(objects,LinkOption.NOFOLLOW_LINKS),"managed_import_directory");Store.contents(objects,hashes(value));
    for(JsonNode file:value.get("files")){Path object=objects.resolve(file.get("sha256").asString());Store.safeAncestors(object);check(Files.isDirectory(object,LinkOption.NOFOLLOW_LINKS),"managed_import_directory");byte[] bytes=store.objectAt(object,file.get("sha256").asString());check(bytes.length==file.get("length").asLong(),"managed_import_length");}
    return value;
  }
  static Path physical(JsonNode file,Path run,Path cache,Path generated)throws IOException {
    Path logical=logical(file);Path root=switch(logical.getName(0).toString()){case "run"->run;case "cache"->cache;case "index"->generated;default->throw new Failure("managed_import_path");};Path path=root.resolve(logical.subpath(1,logical.getNameCount())).normalize();Store.safeAncestors(path);return path;
  }
  static void disjoint(Path... paths)throws IOException {
    for(int i=0;i<paths.length;i++){Store.safeAncestors(paths[i]);for(int j=0;j<i;j++)check(!paths[i].startsWith(paths[j])&&!paths[j].startsWith(paths[i]),"managed_import_root_overlap");}
  }
  static void syncTree(Path root)throws IOException {
    Files.walkFileTree(root,new SimpleFileVisitor<>(){
      @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {check(a.isRegularFile(),"unsafe_path");Store.sync(p);return FileVisitResult.CONTINUE;}
      @Override public FileVisitResult postVisitDirectory(Path p,IOException failure)throws IOException {if(failure!=null)throw failure;Store.sync(p);return FileVisitResult.CONTINUE;}
    });
  }
  static void reserve(ManagedMutation mutation,long additional)throws IOException {
    mutation.reserve(additional);check(mutation.store.managedBytes()+additional<=mutation.store.config.at("/limits/archive_bytes").asLong()-ManagedFormat.HEADROOM,"managed_admission_budget");
  }
  static JsonNode importClosure(ManagedStore store,JsonNode metadata,Path sourceRun,Path sourceCache,Path generated,UUID operation,Store.Hook hook)throws IOException {
    metadata(store,metadata);var mutation=new ManagedMutation(store,operation.toString(),hook);Path run=sourceRun.toAbsolutePath().normalize(),cache=sourceCache.toAbsolutePath().normalize(),index=generated.toAbsolutePath().normalize();disjoint(store.root,run,cache,index);for(Path source:List.of(run,cache,index))check(Files.isDirectory(source,LinkOption.NOFOLLOW_LINKS),"managed_import_source_directory");
    // Recheck every original before touching archive state. P05 remains byte-opaque here.
    for(JsonNode file:metadata.get("files")){byte[] bytes=Store.bounded(physical(file,run,cache,index),32*MIB);check(bytes.length==file.get("length").asLong()&&io.detectbridge.transport.Json.sha(bytes).equals(file.get("sha256").asString()),"managed_import_source_hash");}
    String id=metadata.get("id").asString();check(!store.retiredImports.contains(id),"archive_retired");Path parent=store.root.resolve("imports"),target=parent.resolve(id),partial=parent.resolve(".partial-"+operation);
    if(Files.exists(target,LinkOption.NOFOLLOW_LINKS)){check(verifyClosure(store,id).equals(metadata),"managed_import_conflict");syncTree(target);Store.sync(parent);if(Files.exists(partial,LinkOption.NOFOLLOW_LINKS)){check(verifyPartial(store,partial).equals(metadata),"managed_import_operation_conflict");Store.deletePartial(partial);Store.sync(parent);}return metadata;}
    if(Files.exists(partial,LinkOption.NOFOLLOW_LINKS)){check(verifyPartial(store,partial).equals(metadata),"managed_import_operation_conflict");Store.deletePartial(partial);Store.sync(parent);}
    byte[] owner=ndjson(Map.of("version","1.0.0","managed_id",store.managed,"operation_id",operation.toString(),"metadata",metadata));reserve(mutation,owner.length);Files.createDirectory(partial);Store.write(partial.resolve("owner.json"),owner);Store.sync(partial);Store.sync(parent);hook.at("after_import_owner");
    Path publication=partial.resolve("publication"),objects=publication.resolve("objects");Files.createDirectory(publication);Files.createDirectory(objects);
    for(JsonNode file:metadata.get("files")){
      String sha=file.get("sha256").asString();Path object=objects.resolve(sha);if(Files.exists(object))continue;byte[] original=Store.bounded(physical(file,run,cache,index),32*MIB);check(original.length==file.get("length").asLong()&&io.detectbridge.transport.Json.sha(original).equals(sha),"managed_import_source_hash");
      var raw=new ByteArrayOutputStream();int count=0;for(int offset=0;offset<original.length;offset+=MIB){raw.write(ndjson(Map.of("offset",offset,"bytes",b64(Arrays.copyOfRange(original,offset,Math.min(original.length,offset+MIB))))));count++;}
      byte[] plain=raw.toByteArray(),zipped=compress(plain);JsonNode objectMetadata=JSON.valueToTree(Map.of("version","1.0.0","codec",CODEC,"sha256",sha,"length",original.length,"payload",Store.payloadMeta(plain,zipped,count)));reserve(mutation,zipped.length+ndjson(objectMetadata).length+65);Files.createDirectory(object);Store.write(object.resolve("bytes.ndjson.gz"),zipped);hook.at("after_import_payload");Store.write(object.resolve("object.json"),ndjson(objectMetadata));Store.writeChecksum(object.resolve("object.json"),ndjson(objectMetadata));Store.sync(object);hook.at("after_import_object");
    }
    reserve(mutation,ndjson(metadata).length+65);ManagedFormat.metadata(publication.resolve("import.json"),"import",metadata);syncTree(publication);verifyAt(store,publication,id);hook.at("before_import_publication");Files.move(publication,target,StandardCopyOption.ATOMIC_MOVE);hook.at("after_import_publication");Store.sync(parent);hook.at("after_import_directory_sync");Store.deletePartial(partial);Store.sync(parent);return metadata;
  }
  /** Whole P05 imports have no Kafka clock: cutoff is an explicit operator marker, not an age claim. */
  static JsonNode retirementPlan(ManagedStore store,JsonNode request,JsonNode catalog)throws IOException {
    ManagedPlanner.keys(request,Set.of("operation_id","cutoff_ms","imports","reason"),"managed_import_plan_request");integers(request);
    check(request.path("operation_id").isTextual(),"managed_operation_id");String operation=request.get("operation_id").asString();
    try{check(UUID.fromString(operation).toString().equals(operation),"managed_operation_id");}catch(IllegalArgumentException invalid){throw new Failure("managed_operation_id");}
    long cutoff=ManagedPlanner.nonnegative(request.get("cutoff_ms"),"managed_cutoff");
    check(request.path("reason").isTextual()&&!request.get("reason").asString().isEmpty()&&request.get("reason").asString().codePointCount(0,request.get("reason").asString().length())<=256,"managed_reason");
    JsonNode imports=request.get("imports");check(imports.isArray()&&imports.size()==1&&imports.get(0).isTextual(),"managed_import_targets");String id=imports.get(0).asString();
    ManagedPlanner.validateCatalog(store,catalog);JsonNode metadata=verifyClosure(store,id);Set<String> references=hashes(metadata);references.add(id);references.add(hash(metadata));references.add(metadata.get("run_id").asString());references.add(metadata.get("manifest_sha256").asString());references.add(metadata.get("p05_manifest_sha256").asString());
    for(JsonNode hold:store.holds.get("holds")) {
      String scope=hold.get("scope").asString();boolean blocked=scope.equals("all");
      if(scope.equals("import"))blocked=hold.get("subject").asString().equals(id);
      if(scope.equals("run"))blocked=hold.get("subject").asString().equals(metadata.get("run_id").asString());
      if(scope.equals("object"))blocked=references.contains(hold.get("subject").asString());
      check(!blocked,"managed_hold_blocker");
    }
    for(JsonNode pin:catalog.get("pins"))noPinnedImport(pin.get("selection"),references,0);
    // An import plan selects no Kafka rows. Any unknown retained wire graph is
    // therefore partial-population retirement and cannot prove independence.
    // Retire that wire population explicitly first, then create a fresh import plan.
    Set<String> selectedIds=new HashSet<>();for(String reference:references)selectedIds.add(ManagedPlanner.token(reference));
    var budget=new ManagedPlanner.Budget(store);
    for(String topic:new TreeSet<>(store.floors.keySet()))store.forEachRow(topic,row->{
      var graph=ManagedPlanner.graph(row);budget.add(graph);
      check(!graph.unknown,"managed_unknown_graph_blocker");
      check(Collections.disjoint(selectedIds,graph.identities),"managed_retained_identity_blocker");
    });
    var plan=JSON.createObjectNode();plan.put("version","1.0.0");plan.put("managed_id",store.managed);plan.put("archive_binding_sha256",store.binding);plan.put("operation_id",operation);plan.put("kind","import");plan.put("cutoff_ms",cutoff);plan.set("reason",request.get("reason"));ManagedPlanner.nullable(plan,"previous_retirement_sha256",store.retirementHash);plan.put("holds_sha256",hash(store.holds));plan.put("catalog_sha256",hash(catalog));
    var observed=plan.putArray("observed");for(String topic:new TreeSet<>(store.floors.keySet())){var floor=store.floors.get(topic);var head=store.prefix(topic);var item=observed.addObject();item.put("topic",topic);item.put("floor",floor.next());item.put("next",head.next());ManagedPlanner.nullable(item,"floor_sha256",floor.previous());ManagedPlanner.nullable(item,"head_sha256",head.previous());}
    plan.putArray("targets");plan.putArray("candidates");plan.putArray("imports").addObject().put("id",id).put("metadata_sha256",hash(metadata));ManagedFormat.require("plan",plan);check(ndjson(plan).length<=store.registration.at("/limits/metadata_bytes").asLong(),"managed_metadata_limit");return plan;
  }
  static void noPinnedImport(JsonNode value,Set<String> references,int depth)throws IOException {
    check(depth<=64,"managed_catalog_graph");if(value.isTextual())check(!references.contains(value.asString()),"managed_pin_blocker");else if((value.isObject()||value.isArray()))for(JsonNode child:value)noPinnedImport(child,references,depth+1);
  }
  static Set<String> names(Path directory)throws IOException {
    Store.safeAncestors(directory);check(Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),"managed_import_directory");Set<String> result=new TreeSet<>();try(var entries=Files.newDirectoryStream(directory)){for(Path entry:entries)result.add(entry.getFileName().toString());}return result;
  }
  static void checksumIfPresent(Path file,byte[] raw)throws IOException {
    Path checksum=Store.checksumPath(file);if(Files.exists(checksum,LinkOption.NOFOLLOW_LINKS))check(Arrays.equals(Store.bounded(checksum,65),(io.detectbridge.transport.Json.sha(raw)+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII)),"managed_metadata_integrity");
  }
  /** The committed retirement target owns only this exact progressively unlinked closure. */
  static void validateRetired(ManagedStore store,Path directory,JsonNode target)throws IOException {
    ManagedPlanner.keys(target,Set.of("id","metadata_sha256"),"managed_import_target");String id=target.path("id").asString("");check(id.matches("[a-f0-9]{64}")&&target.path("metadata_sha256").asString("").matches("[a-f0-9]{64}")&&directory.toAbsolutePath().normalize().equals(store.root.resolve("imports").resolve(id)),"managed_import_target");
    Store.safeAncestors(directory);if(!Files.exists(directory,LinkOption.NOFOLLOW_LINKS))return;Set<String> files=names(directory);check(Set.of("import.json","import.sha256","objects").containsAll(files),"managed_import_foreign_file");if(!files.contains("import.json")){check(files.isEmpty(),"managed_import_missing_authority");return;}
    byte[] raw=Store.bounded(directory.resolve("import.json"),16*MIB);JsonNode metadata=read(raw,16*MIB);metadata(store,metadata);check(Arrays.equals(raw,ndjson(metadata))&&metadata.get("id").asString().equals(id)&&hash(metadata).equals(target.get("metadata_sha256").asString()),"managed_import_retired_binding");checksumIfPresent(directory.resolve("import.json"),raw);
    Path objects=directory.resolve("objects");if(!files.contains("objects"))return;check(files.contains("import.sha256"),"managed_import_missing_authority");Set<String> present=names(objects);check(hashes(metadata).containsAll(present),"managed_import_foreign_file");Map<String,Long> lengths=new HashMap<>();for(JsonNode file:metadata.get("files"))lengths.put(file.get("sha256").asString(),file.get("length").asLong());
    for(String sha:present){Path object=objects.resolve(sha);Set<String> entries=names(object);check(OBJECT_FILES.containsAll(entries),"managed_import_foreign_file");if(!entries.contains("object.json")){check(entries.isEmpty(),"managed_import_missing_authority");continue;}
      byte[] objectRaw=Store.bounded(object.resolve("object.json"),MIB);JsonNode info=read(objectRaw,MIB);require("object",info);check(Arrays.equals(objectRaw,ndjson(info))&&info.get("sha256").asString().equals(sha)&&info.get("length").asLong()==lengths.get(sha),"managed_import_retired_binding");checksumIfPresent(object.resolve("object.json"),objectRaw);
      if(entries.contains("bytes.ndjson.gz")){check(entries.contains("object.sha256"),"managed_import_missing_authority");store.objectAt(object,sha);}
    }
  }
  /** Caller must durably sync the committed retirement authority before invoking cleanup. */
  static void cleanupRetired(ManagedStore store,Path directory,JsonNode target,Store.Hook hook)throws IOException {
    check(store.writer,"read_only_archive");check(store.retiredImports.contains(target.path("id").asString("")),"managed_import_not_retired");validateRetired(store,directory,target);if(!Files.exists(directory,LinkOption.NOFOLLOW_LINKS))return;
    Path objects=directory.resolve("objects");if(Files.exists(objects,LinkOption.NOFOLLOW_LINKS)){
      for(String sha:names(objects)){Path object=objects.resolve(sha);for(String name:List.of("bytes.ndjson.gz","object.sha256","object.json"))if(Files.exists(object.resolve(name),LinkOption.NOFOLLOW_LINKS)){Files.delete(object.resolve(name));Store.sync(object);hook.at("during_retired_import_cleanup");}Files.delete(object);Store.sync(objects);hook.at("after_retired_import_object_cleanup");}
      Files.delete(objects);Store.sync(directory);hook.at("after_retired_import_objects_cleanup");
    }
    for(String name:List.of("import.sha256","import.json"))if(Files.exists(directory.resolve(name),LinkOption.NOFOLLOW_LINKS)){Files.delete(directory.resolve(name));Store.sync(directory);hook.at("during_retired_import_metadata_cleanup");}
    Files.delete(directory);Store.sync(directory.getParent());hook.at("after_retired_import_cleanup");
  }
  static JsonNode exportClosure(ManagedStore store,String id,Path run,Path cache,Path generated)throws IOException {
    JsonNode metadata=verifyClosure(store,id);run=run.toAbsolutePath().normalize();cache=cache.toAbsolutePath().normalize();generated=generated.toAbsolutePath().normalize();disjoint(store.root,run,cache,generated);
    for(Path root:List.of(run,cache,generated))check(!Files.exists(root,LinkOption.NOFOLLOW_LINKS)&&Files.isDirectory(root.getParent(),LinkOption.NOFOLLOW_LINKS),"managed_import_restore_destination");
    long total=0;for(JsonNode file:metadata.get("files"))total=Math.addExact(total,file.get("length").asLong());for(Path root:List.of(run,cache,generated))check(Files.getFileStore(root.getParent()).getUsableSpace()-total>=store.config.at("/limits/reserve_bytes").asLong(),"disk_reserve");
    for(Path root:List.of(run,cache,generated))Files.createDirectory(root);
    for(JsonNode file:metadata.get("files")){Path target=physical(file,run,cache,generated);Files.createDirectories(target.getParent());Store.write(target,store.objectAt(store.root.resolve("imports").resolve(id).resolve("objects").resolve(file.get("sha256").asString()),file.get("sha256").asString()));}
    for(Path root:List.of(run,cache,generated)){syncTree(root);Store.sync(root.getParent());}return metadata;
  }
}
