package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Identical-operation initialization only. Never repairs or adopts an existing published root. */
final class ManagedInitialization {
  static Path container(Path target,String operation,JsonNode owner)throws IOException {
    try{check(UUID.fromString(operation).toString().equals(operation),"managed_operation_id");}catch(IllegalArgumentException invalid){throw new Failure("managed_operation_id");}
    Path container=target.resolveSibling("."+target.getFileName()+"-managed-"+operation);Store.safeAncestors(container);
    if(!Files.exists(container,LinkOption.NOFOLLOW_LINKS)){Files.createDirectory(container);Store.sync(container.getParent());}
    check(Files.isDirectory(container,LinkOption.NOFOLLOW_LINKS),"managed_initialization_owner");Path marker=container.resolve("owner.json");
    if(Files.exists(marker,LinkOption.NOFOLLOW_LINKS)) {
      byte[] raw=Store.bounded(marker,MIB);check(Arrays.equals(raw,ndjson(owner))&&Arrays.equals(Store.bounded(Store.checksumPath(marker),65),(io.detectbridge.transport.Json.sha(raw)+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII)),"managed_initialization_owner");
    }else {Store.contents(container,Set.of());Store.write(marker,ndjson(owner));Store.writeChecksum(marker,ndjson(owner));Store.sync(container);}
    try(var entries=Files.newDirectoryStream(container)){for(Path entry:entries){String name=entry.getFileName().toString();check(Set.of("owner.json","owner.sha256","archive").contains(name)||name.startsWith(".archive-init-"),"managed_initialization_foreign");}}
    return container;
  }
  static void removeInitialMetadata(Path stage,JsonNode registration)throws IOException {
    // Only the unpublished initializer's exact partial metadata can be reconstructed.
    Path maintenance=stage.resolve("maintenance"),imports=stage.resolve("imports");
    var files=new TreeMap<String,byte[]>();files.put("maintenance/registration.json",ndjson(registration));
    var holds=JSON.createObjectNode();holds.put("version","1.0.0");holds.set("managed_id",registration.get("managed_id"));holds.put("revision",0);holds.putNull("previous_sha256");holds.put("reason","explicit managed initialization");holds.putArray("holds");
    files.put("maintenance/holds/00000000000000000000/holds.json",ndjson(holds));files.put("maintenance/holds/head.json",ndjson(ManagedFormat.head("holds",registration.get("managed_id").asString(),0,hash(holds))));files.put("maintenance/retirements/head.json",ndjson(ManagedFormat.head("retirements",registration.get("managed_id").asString(),0,null)));
    for(var entry:new ArrayList<>(files.entrySet()))if(!entry.getKey().endsWith("head.json"))files.put(entry.getKey().replace(".json",".sha256"),(io.detectbridge.transport.Json.sha(entry.getValue())+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    var directories=new HashSet<String>();directories.addAll(Set.of("maintenance","maintenance/holds","maintenance/holds/00000000000000000000","maintenance/retirements","imports"));
    for(Path root:List.of(maintenance,imports))if(Files.exists(root,LinkOption.NOFOLLOW_LINKS)) {
      try(var paths=Files.walk(root)){for(Path path:paths.toList()){
        String relative=stage.relativize(path).toString();Store.safeAncestors(path);
        if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))check(directories.contains(relative),"managed_initialization_foreign");
        else {check(files.containsKey(relative),"managed_initialization_foreign");byte[] expected=files.get(relative),actual=Store.bounded(path,expected.length);check(Arrays.equals(actual,Arrays.copyOf(expected,actual.length)),"managed_initialization_foreign");}
      }}Store.deletePartial(root);Store.sync(stage);
    }
  }
  static void legacyPartials(Path container)throws IOException {
    try(var entries=Files.newDirectoryStream(container,".archive-init-*")){for(Path partial:entries){
      check(Files.isDirectory(partial,LinkOption.NOFOLLOW_LINKS),"managed_initialization_foreign");
      try(var paths=Files.walk(partial)){for(Path path:paths.toList()){
        Store.safeAncestors(path);String relative=partial.relativize(path).toString();
        if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))check(Set.of("","objects","segments").contains(relative),"managed_initialization_foreign");
        else check(Set.of("archive.json","archive.sha256").contains(relative)&&Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)&&Files.size(path)<=MIB,"managed_initialization_foreign");
      }}Store.deletePartial(partial);Store.sync(container);
    }}
  }
  static JsonNode registration(Path stage,Path target,JsonNode supplied,String kind,String scope)throws Exception {
    var registration=((tools.jackson.databind.node.ObjectNode)supplied).deepCopy();registration.put("archive_binding_sha256",hash(Store.metadata(stage.resolve("archive.json"),"configuration")));registration.put("implementation_sha256",Main.implementation());registration.put("group","detectbridge-archive-managed-v1-"+registration.get("managed_id").asString());
    var origin=registration.putObject("origin");origin.put("kind",kind);if(scope==null)origin.putNull("source_scope_sha256");else origin.put("source_scope_sha256",scope);
    check(registration.get("destination").asString().equals(target.toString()),"managed_destination");ManagedFormat.require("registration",registration);return registration;
  }
  static void publish(Path container,Path target)throws Exception {
    Path stage=container.resolve("archive");ManagedImport.syncTree(stage);Main.hook().at("before_managed_publication");Files.move(stage,target,StandardCopyOption.ATOMIC_MOVE);Main.hook().at("after_managed_publication");Store.sync(target.getParent());
    Store.contents(container,Set.of("owner.json","owner.sha256"));Store.deletePartial(container);Store.sync(container.getParent());
  }
  static Map<String,Object> fresh(Path target,String bootstrap,Path request,Path registry,JsonNode supplied,String operation)throws Exception {
    target=target.toAbsolutePath().normalize();Store.safeAncestors(target);check(Files.isDirectory(target.getParent(),LinkOption.NOFOLLOW_LINKS),"managed_destination");ManagedFormat.require("registration",supplied);
    JsonNode r=read(Store.bounded(request,MIB),MIB);var registered=new TreeMap<String,String>();
    try(var entries=Files.newDirectoryStream(registry)){for(Path path:entries){String sha=path.getFileName().toString();check(sha.matches("[a-f0-9]{64}")&&io.detectbridge.transport.Json.sha(Store.bounded(path,OBJECT)).equals(sha),"registry_invalid");registered.put(sha,sha);}}
    JsonNode owner=JSON.valueToTree(Map.of("version","1.0.0","operation_id",operation,"registration",supplied,"input_sha256",hash(List.of(bootstrap,r,registered))));
    if(Files.exists(target,LinkOption.NOFOLLOW_LINKS)) {
      try(var verified=new ManagedStore(target,false,Main.implementation())) {
        check(hash(verified.registration).equals(hash(registration(target,target,supplied,"fresh",null))),"managed_initialization_binding");
        check(verified.config.get("bootstrap").asString().equals(bootstrap)&&verified.config.get("limits").equals(r.get("limits"))&&verified.config.get("provenance").equals(r.get("provenance"))&&Store.strings(verified.config.get("objects")).equals(registered.keySet()),"managed_initialization_binding");
        for(JsonNode topic:verified.config.get("topics"))check(topic.get("start").equals(r.get("starts").get(topic.get("name").asString())),"managed_initialization_binding");
        ManagedImport.syncTree(target);Store.sync(target.getParent());
        Path pending=target.resolveSibling("."+target.getFileName()+"-managed-"+operation);
        if(Files.exists(pending,LinkOption.NOFOLLOW_LINKS)){pending=container(target,operation,owner);Store.contents(pending,Set.of("owner.json","owner.sha256"));Store.deletePartial(pending);Store.sync(pending.getParent());}
        return verified.progress();
      }
    }
    Path container=container(target,operation,owner),stage=container.resolve("archive");legacyPartials(container);
    if(!Files.exists(stage,LinkOption.NOFOLLOW_LINKS))Main.initialize(stage,bootstrap,request,registry);
    else {
      JsonNode config=Store.metadata(stage.resolve("archive.json"),"configuration");Store.validateConfig(config);Main.verifyBroker(config);
      check(config.get("bootstrap").asString().equals(bootstrap)&&config.get("limits").equals(r.get("limits"))&&config.get("provenance").equals(r.get("provenance"))&&config.get("implementation_sha256").asString().equals(Main.implementation()),"managed_initialization_binding");
      for(JsonNode topic:config.get("topics"))check(topic.get("start").equals(r.get("starts").get(topic.get("name").asString())),"managed_initialization_binding");
      var objects=new TreeSet<String>();try(var entries=Files.newDirectoryStream(registry)){for(Path path:entries){String sha=path.getFileName().toString();check(sha.matches("[a-f0-9]{64}")&&io.detectbridge.transport.Json.sha(Store.bounded(path,OBJECT)).equals(sha),"registry_invalid");objects.add(sha);}}
      check(objects.equals(Store.strings(config.get("objects"))),"managed_initialization_binding");
      removeInitialMetadata(stage,registration(stage,target,supplied,"fresh",null));Store.contents(stage.resolve("segments"),Set.of());try(var original=new Store(stage,true)){Main.register(original,registry);}
    }
    ManagedMain.enable(stage,target,supplied,"fresh",null);publish(container,target);try(var verified=new ManagedStore(target,false,Main.implementation())){return verified.progress();}
  }  static void preflightLegacy(Path root)throws IOException {
    final long[] count={0};Files.walkFileTree(root,new java.nio.file.SimpleFileVisitor<>() {
      private void entry()throws IOException {check(++count[0]<=262144,"managed_identity_budget");}
      @Override public java.nio.file.FileVisitResult preVisitDirectory(Path path,java.nio.file.attribute.BasicFileAttributes attributes)throws IOException {entry();check(!attributes.isSymbolicLink(),"unsafe_path");return java.nio.file.FileVisitResult.CONTINUE;}
      @Override public java.nio.file.FileVisitResult visitFile(Path path,java.nio.file.attribute.BasicFileAttributes attributes)throws IOException {entry();check(attributes.isRegularFile(),"unsafe_path");return java.nio.file.FileVisitResult.CONTINUE;}
    });
  }
  static Map<String,Object> cloneLegacy(Path source,Path target,JsonNode supplied,String operation)throws Exception {
    source=source.toAbsolutePath().normalize();target=target.toAbsolutePath().normalize();Store.safeAncestors(source);Store.safeAncestors(target);check(Files.isDirectory(target.getParent(),LinkOption.NOFOLLOW_LINKS)&&!source.startsWith(target)&&!target.startsWith(source),"managed_clone_overlap");ManagedFormat.require("registration",supplied);
    try(var channel=FileChannel.open(source.resolve(".lock"),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS);var lease=channel.tryLock(0,Long.MAX_VALUE,true)) {
      check(lease!=null,"archive_locked");preflightLegacy(source);try(var original=new Store(source,false)) {
        for(String sha:Store.strings(original.config.get("objects")))original.object(sha);
        var files=new TreeMap<String,Path>();var scope=new TreeMap<String,String>();var directories=new TreeSet<String>();long total=0;
        try(var paths=Files.walk(source)){var iterator=paths.iterator();while(iterator.hasNext()) {Path path=iterator.next();
          String relative=source.relativize(path).toString();if(relative.isEmpty())continue;check(!relative.startsWith(".partial-"),"managed_clone_requires_recovery");if(Set.of(".lock","progress.json").contains(relative))continue;
          if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))directories.add(relative);
          else {check(files.size()<262144,"managed_identity_budget");byte[] bytes=Store.bounded(path,48*MIB);total=Math.addExact(total,bytes.length);files.put(relative,path);scope.put(relative,io.detectbridge.transport.Json.sha(bytes));}
        }}
        check(total<=original.config.at("/limits/archive_bytes").asLong()-ManagedFormat.HEADROOM,"managed_admission_budget");check(Files.getFileStore(target.getParent()).getUsableSpace()-total>=original.config.at("/limits/reserve_bytes").asLong(),"disk_reserve");String sourceScope=hash(scope);
        JsonNode owner=JSON.valueToTree(Map.of("version","1.0.0","operation_id",operation,"registration",supplied,"input_sha256",sourceScope));
        if(Files.exists(target,LinkOption.NOFOLLOW_LINKS)) {
          try(var verified=new ManagedStore(target,false,Main.implementation())) {
            check(verified.binding.equals(original.binding)&&hash(verified.registration).equals(hash(registration(target,target,supplied,"clone",sourceScope))),"managed_initialization_binding");ManagedImport.syncTree(target);Store.sync(target.getParent());
            Path pending=target.resolveSibling("."+target.getFileName()+"-managed-"+operation);
            if(Files.exists(pending,LinkOption.NOFOLLOW_LINKS)){pending=container(target,operation,owner);Store.contents(pending,Set.of("owner.json","owner.sha256"));Store.deletePartial(pending);Store.sync(pending.getParent());}
            return verified.progress();
          }
        }
        Path container=container(target,operation,owner),stage=container.resolve("archive");
        if(!Files.exists(stage,LinkOption.NOFOLLOW_LINKS))Files.createDirectory(stage);
        if(Files.exists(stage.resolve("maintenance"),LinkOption.NOFOLLOW_LINKS)||Files.exists(stage.resolve("imports"),LinkOption.NOFOLLOW_LINKS))removeInitialMetadata(stage,registration(stage,target,supplied,"clone",sourceScope));
        try(var paths=Files.walk(stage)){for(Path path:paths.toList()) {
          String relative=stage.relativize(path).toString();if(relative.isEmpty())continue;Store.safeAncestors(path);
          if(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS))check(directories.contains(relative),"managed_initialization_foreign");
          else check((relative.equals(".lock")&&Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)&&Files.size(path)==0)||files.containsKey(relative),"managed_initialization_foreign");
        }}
        for(String relative:directories)Files.createDirectories(stage.resolve(relative));
        for(var entry:files.entrySet()) {
          Path copy=stage.resolve(entry.getKey());byte[] expected=Store.bounded(entry.getValue(),48*MIB);
          if(Files.exists(copy,LinkOption.NOFOLLOW_LINKS)){byte[] actual=Store.bounded(copy,expected.length);check(Arrays.equals(actual,Arrays.copyOf(expected,actual.length)),"managed_initialization_foreign");if(actual.length==expected.length)continue;Files.delete(copy);}
          Store.write(copy,expected);
        }
        if(!Files.exists(stage.resolve(".lock"),LinkOption.NOFOLLOW_LINKS))Store.write(stage.resolve(".lock"),new byte[0]);
        try(var verified=new Store(stage,false)){check(verified.binding.equals(original.binding),"managed_clone_binding");}
        ManagedMain.enable(stage,target,supplied,"clone",sourceScope);publish(container,target);
      }
    }
    try(var verified=new ManagedStore(target,false,Main.implementation())){return verified.progress();}
  }

}
