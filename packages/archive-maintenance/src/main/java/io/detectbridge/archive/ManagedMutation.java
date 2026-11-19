package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Exclusive-lease publication. Durable authority always precedes removal of owned evidence. */
final class ManagedMutation {
  final ManagedStore store;
  final String operation;
  final Store.Hook hook;
  ManagedMutation(ManagedStore store,String operation,Store.Hook hook)throws IOException {
    check(store.writer,"read_only_archive");
    try{check(UUID.fromString(operation).toString().equals(operation),"managed_operation_id");}catch(IllegalArgumentException invalid){throw new Failure("managed_operation_id");}
    this.store=store;this.operation=operation;this.hook=hook;
  }
  static Set<String> publicationFiles(String journal)throws IOException {
    return switch(journal){case "holds" -> Set.of("holds.json","holds.sha256");case "retirements" -> Set.of("plan.json","plan.sha256","retirement.json","retirement.sha256");default -> throw new Failure("managed_journal_kind");};
  }
  static void partial(Path path,String journal,String managed)throws IOException {
    Store.safeAncestors(path);check(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"managed_partial_directory");
    String operation=path.getFileName().toString().substring(".partial-".length());
    try{check(UUID.fromString(operation).toString().equals(operation),"managed_partial_owner");}catch(IllegalArgumentException invalid){throw new Failure("managed_partial_owner");}
    JsonNode owner=read(Store.bounded(path.resolve("owner.json"),4096),4096);
    check(owner.equals(JSON.valueToTree(Map.of("version","1.0.0","managed_id",managed,"journal",journal,"operation_id",operation))),"managed_partial_owner");
    try(var entries=Files.newDirectoryStream(path)) {
      for(Path entry:entries) {
        String name=entry.getFileName().toString();check(Set.of("owner.json","publication","head.json").contains(name),"managed_foreign_partial");
        if(name.equals("publication")) {
          check(Files.isDirectory(entry,LinkOption.NOFOLLOW_LINKS),"managed_foreign_partial");
          try(var files=Files.newDirectoryStream(entry)){for(Path file:files)check(publicationFiles(journal).contains(file.getFileName().toString())&&Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)&&Files.size(file)<=16L*MIB,"managed_foreign_partial");}
        }else check(Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS)&&Files.size(entry)<=MIB,"managed_foreign_partial");
      }
    }
  }
  Path staging(String journal)throws IOException {
    Path parent=store.root.resolve("maintenance").resolve(journal),path=parent.resolve(".partial-"+operation);
    if(Files.exists(path,LinkOption.NOFOLLOW_LINKS)){partial(path,journal,store.managed);return path;}
    reserve(4096);Files.createDirectory(path);Store.write(path.resolve("owner.json"),ndjson(Map.of("version","1.0.0","managed_id",store.managed,"journal",journal,"operation_id",operation)));Store.sync(path);Store.sync(parent);hook.at("after_operation_owner");return path;
  }
  void reserve(long additional)throws IOException {
    check(additional>=0&&store.managedBytes()+additional<=store.config.at("/limits/archive_bytes").asLong()-ManagedFormat.CONTROL,"managed_maintenance_budget");
    check(Files.getFileStore(store.root).getUsableSpace()-additional>=store.config.at("/limits/reserve_bytes").asLong(),"disk_reserve");
  }
  void head(String journal,long sequence,String record)throws IOException {
    Path staging=staging(journal),temporary=staging.resolve("head.json");
    byte[] bytes=ndjson(ManagedFormat.head(journal,store.managed,sequence,record));reserve(bytes.length);
    if(Files.exists(temporary,LinkOption.NOFOLLOW_LINKS)){ManagedFormat.head(temporary,journal,store.managed);Files.delete(temporary);}
    Store.write(temporary,bytes);Store.sync(staging);hook.at("before_head_publication");
    Files.move(temporary,staging.getParent().resolve("head.json"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);hook.at("after_head_publication");Store.sync(staging.getParent());hook.at("after_head_directory_sync");
  }
  void finish(String journal)throws IOException {
    Path path=store.root.resolve("maintenance").resolve(journal).resolve(".partial-"+operation);
    if(Files.exists(path,LinkOption.NOFOLLOW_LINKS)){partial(path,journal,store.managed);Store.deletePartial(path);Store.sync(path.getParent());}
  }
  void syncAuthority()throws IOException {
    Files.walkFileTree(store.root,new SimpleFileVisitor<>() {
      @Override public FileVisitResult visitFile(Path path,BasicFileAttributes attributes)throws IOException {check(attributes.isRegularFile(),"unsafe_path");Store.sync(path);return FileVisitResult.CONTINUE;}
      @Override public FileVisitResult postVisitDirectory(Path path,IOException failure)throws IOException {if(failure!=null)throw failure;Store.sync(path);return FileVisitResult.CONTINUE;}
    });Store.sync(store.root);hook.at("after_recovery_sync");hook.at("after_authority_sync");
  }
  void recover()throws IOException {
    // The record may have survived an unsynced rename. Establish its durability first.
    syncAuthority();
    if(store.retirementHeadStale){head("retirements",store.retirementSequence,store.retirementHash);store.retirementHeadStale=false;}
    if(store.holdsHeadStale){head("holds",store.holds.get("revision").asLong(),hash(store.holds));store.holdsHeadStale=false;}
    hook.at("before_retired_cleanup");
    for(String relative:store.retiredGarbage.keySet()) {
      Path path=store.root.resolve("segments").resolve(relative);
      if(Files.exists(path,LinkOption.NOFOLLOW_LINKS)) {
        // Recheck the exact named subset before any unlink; foreign files are never removed.
        try(var files=Files.newDirectoryStream(path)){for(Path file:files)check(Set.of("records.ndjson.gz","segment.json","segment.sha256").contains(file.getFileName().toString())&&Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS),"unsafe_retired_segment");}
        for(String file:List.of("records.ndjson.gz","segment.json","segment.sha256"))if(Files.exists(path.resolve(file),LinkOption.NOFOLLOW_LINKS)){Files.delete(path.resolve(file));hook.at("during_retired_cleanup");}
        Store.sync(path);Files.delete(path);Store.sync(path.getParent());hook.at("after_retired_segment_cleanup");
      }
    }
    store.retiredGarbage.clear();
    for(var entry:store.retiredImportPlans.entrySet()) {
      Path path=store.root.resolve("imports").resolve(entry.getKey());
      if(Files.exists(path,LinkOption.NOFOLLOW_LINKS))ManagedImport.cleanupRetired(store,path,entry.getValue(),hook);
    }
    finish("retirements");finish("holds");
  }
  JsonNode retire(JsonNode plan,JsonNode catalog)throws IOException {
    ManagedFormat.require("plan",plan);String planHash=hash(plan);
    check(plan.get("operation_id").asString().equals(operation),"managed_plan_operation");
    Path journal=store.root.resolve("maintenance/retirements");
    for(long n=1;n<=store.retirementSequence;n++) {
      JsonNode committed=ManagedFormat.metadata(journal.resolve(ManagedStore.sequence(n)).resolve("plan.json"),"plan");
      if(committed.get("operation_id").asString().equals(operation)) {
        check(hash(committed).equals(planHash),"managed_operation_conflict");recover();return ManagedFormat.metadata(journal.resolve(ManagedStore.sequence(n)).resolve("retirement.json"),"retirement");
      }
    }
    ObjectNode request=JSON.createObjectNode();for(String key:List.of("operation_id","cutoff_ms","targets","reason"))request.set(key,plan.get(key));
    JsonNode expected;
    if(plan.get("kind").asString().equals("import")) {
      request.remove("targets");var imports=request.putArray("imports");for(JsonNode target:plan.get("imports"))imports.add(target.get("id").asString());expected=ManagedImport.retirementPlan(store,request,catalog);
    }else expected=ManagedPlanner.plan(store,request,catalog);
    check(hash(expected).equals(planHash),"managed_stale_plan");
    recover();long sequence=Math.addExact(store.retirementSequence,1);ObjectNode record=JSON.createObjectNode();
    record.put("version","1.0.0");record.put("managed_id",store.managed);record.put("sequence",sequence);record.put("id","sha256:"+hash(List.of("detectbridge.archive.retirement/1",store.managed,operation,planHash)));record.put("plan_sha256",planHash);
    if(store.retirementHash==null)record.putNull("previous_sha256");else record.put("previous_sha256",store.retirementHash);
    Path staging=staging("retirements"),publication=staging.resolve("publication");
    if(Files.exists(publication,LinkOption.NOFOLLOW_LINKS))Store.deletePartial(publication);
    reserve(ndjson(plan).length+ndjson(record).length+130);Files.createDirectory(publication);
    ManagedFormat.metadata(publication.resolve("plan.json"),"plan",plan,hook,"retirement_plan");hook.at("after_retirement_plan");
    ManagedFormat.metadata(publication.resolve("retirement.json"),"retirement",record,hook,"retirement_record");Store.sync(publication);hook.at("before_retirement_publication");
    Files.move(publication,journal.resolve(ManagedStore.sequence(sequence)),StandardCopyOption.ATOMIC_MOVE);hook.at("after_retirement_publication");Store.sync(journal);hook.at("after_retirement_directory_sync");
    // Re-open recovery is authoritative after any failure from this point.
    head("retirements",sequence,hash(record));store.applyAnchors(plan);store.retirementSequence=sequence;store.retirementHash=hash(record);store.lastRetirement=record;
    recover();return record;
  }
  void holds(JsonNode next)throws IOException {
    ManagedFormat.require("holds",next);ManagedStore.validateHolds(next,store);
    if(next.equals(store.holds)){recover();return;}
    check(next.get("managed_id").asString().equals(store.managed)&&next.get("revision").asLong()==Math.addExact(store.holds.get("revision").asLong(),1)&&next.get("previous_sha256").asString().equals(hash(store.holds)),"managed_hold_compare");
    recover();Path staging=staging("holds"),publication=staging.resolve("publication");
    if(Files.exists(publication,LinkOption.NOFOLLOW_LINKS))Store.deletePartial(publication);
    byte[] data=ndjson(next);reserve(data.length+65);Files.createDirectory(publication);ManagedFormat.metadata(publication.resolve("holds.json"),"holds",next);Store.sync(publication);hook.at("before_hold_publication");
    Files.move(publication,staging.getParent().resolve(ManagedStore.sequence(next.get("revision").asLong())),StandardCopyOption.ATOMIC_MOVE);hook.at("after_hold_publication");Store.sync(staging.getParent());hook.at("after_hold_directory_sync");
    head("holds",next.get("revision").asLong(),hash(next));store.holds=next;finish("holds");
  }
}
