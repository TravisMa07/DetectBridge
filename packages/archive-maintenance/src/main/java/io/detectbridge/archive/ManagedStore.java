package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static io.detectbridge.archive.ManagedFormat.CONTROL;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Managed format reader and lock boundary. Legacy Store/reader remain separate and unchanged. */
final class ManagedStore implements AutoCloseable {
  record Prefix(long next,String previous) {}
  final Path root;
  final JsonNode config,registration;
  final String binding,managed;
  final boolean writer;
  private final FileChannel channel;
  private final FileLock lease;
  final Map<String,Prefix> floors=new TreeMap<>(),prefixes=new TreeMap<>();
  final Map<String,JsonNode> retiredGarbage=new TreeMap<>();
  final Map<String,Set<String>> fingerprints=new TreeMap<>();
  final Map<String,Map<Long,String>> boundaries=new TreeMap<>();
  final Set<String> verifiedObjects=new HashSet<>();
  long boundaryCount,liveRows;
  String operation;
  Store.Hook hook=p->{};
  final Set<String> retiredImports=new TreeSet<>();
  final Map<String,JsonNode> retiredImportPlans=new TreeMap<>();
  JsonNode holds,lastRetirement;
  long retirementSequence;
  String retirementHash;
  boolean retirementHeadStale,holdsHeadStale;
  ManagedStore(Path path,boolean writer,String implementation)throws IOException {
    root=path.toAbsolutePath().normalize();this.writer=writer;Store.safeAncestors(root);
    check(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS),"archive_missing");
    FileChannel opened=FileChannel.open(root.resolve(".lock"),writer?StandardOpenOption.WRITE:StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS);FileLock held=null;
    try {
      try{held=opened.tryLock(0,Long.MAX_VALUE,!writer);}catch(OverlappingFileLockException locked){throw new Failure("archive_locked");}
      check(held!=null,"archive_locked");
      config=Store.metadata(root.resolve("archive.json"),"configuration");Store.validateConfig(config);binding=hash(config);
      registration=ManagedFormat.metadata(root.resolve("maintenance/registration.json"),"registration");managed=registration.get("managed_id").asString();
      check(registration.get("archive_binding_sha256").asString().equals(binding)&&registration.get("implementation_sha256").asString().equals(implementation)&&registration.get("group").asString().equals("detectbridge-archive-managed-v1-"+managed),"managed_registration_binding");
      tree();
      for(JsonNode topic:config.get("topics")) {
        String name=topic.get("name").asString();floors.put(name,new Prefix(topic.get("start").asLong(),null));boundary(name,topic.get("start").asLong(),null);
      }
      validateObjects();loadHolds();loadRetirements();
      scan();validateObservations();validateImports();channel=opened;lease=held;
    }catch(Exception failure){if(held!=null)held.release();opened.close();throw failure;}
  }
  void boundary(String topic,long next,String sha)throws IOException {
    Map<Long,String> values=boundaries.computeIfAbsent(topic,k->new TreeMap<>());
    if(values.containsKey(next))check(Objects.equals(values.get(next),sha),"managed_boundary_conflict");
    else {check(++boundaryCount<=registration.at("/limits/identity_tokens").asLong(),"managed_identity_budget");values.put(next,sha);}
  }
  void validateObjects()throws IOException {
    try(var files=Files.newDirectoryStream(root.resolve("objects"))) {
      for(Path p:files){String sha=p.getFileName().toString();check(Store.strings(config.get("objects")).contains(sha),"unregistered_object");object(sha);verifiedObjects.add(sha);}
    }
    check(verifiedObjects.equals(Store.strings(config.get("objects"))),"missing_object");
  }
  void validateObservations()throws IOException {
    Path directory=root.resolve("maintenance/retirements");
    for(long n=1;n<=retirementSequence;n++) {
      JsonNode plan=ManagedFormat.metadata(directory.resolve(sequence(n)).resolve("plan.json"),"plan");
      for(JsonNode observed:plan.get("observed")) {
        Map<Long,String> values=boundaries.get(observed.get("topic").asString());long next=observed.get("next").asLong();
        check(values.containsKey(next)&&Objects.equals(values.get(next),observed.get("head_sha256").isNull()?null:observed.get("head_sha256").asString()),"managed_observed_head_binding");
      }
    }
  }
  static String sequence(long n){return String.format(Locale.ROOT,"%020d",n);}
  long journalCount(Path directory,long first)throws IOException {
    long count=0;
    try(var entries=Files.newDirectoryStream(directory)) {
      for(Path p:entries) {
        String name=p.getFileName().toString();if(name.equals("head.json"))continue;
        if(name.startsWith(".partial-")){ManagedMutation.partial(p,directory.getFileName().toString(),managed);continue;}
        check(name.matches("[0-9]{20}")&&Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS),"managed_journal_entry");
        try{check(Long.parseLong(name)>=first,"managed_journal_sequence");}catch(NumberFormatException invalid){throw new Failure("managed_journal_sequence");}
        count=Math.addExact(count,1);check(count<=registration.at("/limits/identity_tokens").asLong(),"managed_identity_budget");
      }
    }
    return count;
  }
  void loadHolds()throws IOException {
    Path directory=root.resolve("maintenance/holds");JsonNode head=ManagedFormat.head(directory.resolve("head.json"),"holds",managed);
    long count=journalCount(directory,0);check(count>0&&head.get("sequence").asLong()<count,"managed_hold_head_missing");String previous=null;
    for(long n=0;n<count;n++) {
      Path entry=directory.resolve(sequence(n));Store.contents(entry,Set.of("holds.json","holds.sha256"));JsonNode value=ManagedFormat.metadata(entry.resolve("holds.json"),"holds");
      check(value.get("managed_id").asString().equals(managed)&&value.get("revision").asLong()==n&&Objects.equals(value.get("previous_sha256").isNull()?null:value.get("previous_sha256").asString(),previous),"managed_hold_chain");
      validateHolds(value,this);
      previous=hash(value);if(n==head.get("sequence").asLong())check(head.get("record_sha256").asString().equals(previous),"managed_hold_head_binding");holds=value;
    }
    holdsHeadStale=head.get("sequence").asLong()!=count-1;
  }
  static void validateHolds(JsonNode value,ManagedStore store)throws IOException {
    var ids=new HashSet<String>();
    for(JsonNode hold:value.get("holds")) {
      check(ids.add(hold.get("id").asString()),"managed_duplicate_hold");String scope=hold.get("scope").asString();
      boolean range=scope.equals("range"),subject=Set.of("run","import","object").contains(scope);
      check(hold.get("topic").isNull()!=range&&hold.get("first").isNull()!=range&&hold.get("next").isNull()!=range&&hold.get("subject").isNull()!=subject,"managed_hold_scope");
      if(range){store.topic(hold.get("topic").asString());check(hold.get("first").asLong()<hold.get("next").asLong(),"managed_hold_range");}
      if(scope.equals("run")){try{check(UUID.fromString(hold.get("subject").asString()).toString().equals(hold.get("subject").asString()),"managed_hold_subject");}catch(IllegalArgumentException invalid){throw new Failure("managed_hold_subject");}}
      if(scope.equals("object"))check(Store.strings(store.config.get("objects")).contains(hold.get("subject").asString()),"managed_hold_subject");
      if(scope.equals("import"))check(hold.get("subject").asString().matches("[a-f0-9]{64}"),"managed_hold_subject");
    }
  }
  void loadRetirements()throws IOException {
    Path directory=root.resolve("maintenance/retirements");JsonNode head=ManagedFormat.head(directory.resolve("head.json"),"retirements",managed);
    long count=journalCount(directory,1);check(head.get("sequence").asLong()<=count,"managed_retirement_head_missing");
    if(head.get("sequence").asLong()==0)check(head.get("record_sha256").isNull(),"managed_retirement_head_binding");
    String previous=null;
    for(long n=1;n<=count;n++) {
      Path entry=directory.resolve(sequence(n));Store.contents(entry,Set.of("plan.json","plan.sha256","retirement.json","retirement.sha256"));
      JsonNode plan=ManagedFormat.metadata(entry.resolve("plan.json"),"plan"),record=ManagedFormat.metadata(entry.resolve("retirement.json"),"retirement");
      String planHash=hash(plan);
      check(record.get("managed_id").asString().equals(managed)&&record.get("sequence").asLong()==n&&record.get("plan_sha256").asString().equals(planHash)&&Objects.equals(record.get("previous_sha256").isNull()?null:record.get("previous_sha256").asString(),previous),"managed_retirement_chain");
      check(plan.get("managed_id").asString().equals(managed)&&plan.get("archive_binding_sha256").asString().equals(binding)&&Objects.equals(plan.get("previous_retirement_sha256").isNull()?null:plan.get("previous_retirement_sha256").asString(),previous),"managed_plan_binding");
      check(record.get("id").asString().equals("sha256:"+hash(List.of("detectbridge.archive.retirement/1",managed,plan.get("operation_id").asString(),planHash))),"managed_retirement_identity");
      applyAnchors(plan);
      previous=hash(record);if(n==head.get("sequence").asLong())check(head.get("record_sha256").asString().equals(previous),"managed_retirement_head_binding");lastRetirement=record;
    }
    retirementSequence=count;retirementHash=previous;retirementHeadStale=head.get("sequence").asLong()!=count;
  }
  void applyAnchors(JsonNode plan)throws IOException {
    var observed=new HashSet<String>();
    for(JsonNode value:plan.get("observed")) {
      String name=value.get("topic").asString();topic(name);check(observed.add(name),"managed_duplicate_topic");Prefix floor=floors.get(name);
      check(value.get("floor").asLong()==floor.next()&&Objects.equals(value.get("floor_sha256").isNull()?null:value.get("floor_sha256").asString(),floor.previous())&&value.get("next").asLong()>=floor.next(),"managed_anchor_observation");
    }
    check(observed.size()==9,"managed_observation_incomplete");
    var advanced=new TreeMap<String,Prefix>();for(var e:floors.entrySet())advanced.put(e.getKey(),e.getValue());
    var used=new HashSet<String>();
    for(JsonNode candidate:plan.get("candidates")) {
      String name=candidate.get("topic").asString();JsonNode t=topic(name),meta=candidate.get("segment");Prefix old=advanced.get(name);
      check(meta.get("binding_sha256").asString().equals(binding)&&meta.get("topic_id").equals(t.get("id"))&&meta.get("first").asLong()==old.next()&&meta.get("next").asLong()>old.next()&&Objects.equals(meta.get("previous").isNull()?null:meta.get("previous").asString(),old.previous())&&hash(meta).equals(candidate.get("segment_sha256").asString()),"managed_anchor_chain");
      String key=t.get("id").asString()+"/0/"+meta.get("first").asLong();check(used.add(key),"managed_duplicate_segment");
      if(Files.exists(root.resolve("segments").resolve(key),LinkOption.NOFOLLOW_LINKS))retiredGarbage.put(key,meta);
      check(retiredGarbage.size()<=256,"managed_retired_garbage_budget");
      for(JsonNode fp:candidate.get("fingerprints"))fingerprints.computeIfAbsent(fp.get("identity_sha256").asString(),k->new TreeSet<>()).add(fp.get("content_sha256").asString());
      boundary(name,meta.get("next").asLong(),hash(meta));advanced.put(name,new Prefix(meta.get("next").asLong(),hash(meta)));
    }
    long size=fingerprints.values().stream().mapToLong(Set::size).sum();check(size<=registration.at("/limits/source_fingerprints").asLong(),"managed_fingerprint_budget");
    var targets=new HashSet<String>();for(JsonNode target:plan.get("targets")) {
      String name=target.get("topic").asString();topic(name);check(targets.add(name)&&target.get("next").asLong()==advanced.get(name).next()&&target.get("next").asLong()>floors.get(name).next(),"managed_anchor_target");
    }
    for(var e:advanced.entrySet())if(!e.getValue().equals(floors.get(e.getKey())))check(targets.contains(e.getKey()),"managed_anchor_target_missing");
    if(plan.get("kind").asString().equals("segments"))check(!used.isEmpty()&&plan.get("imports").isEmpty(),"managed_empty_retirement");
    else {check(used.isEmpty()&&targets.isEmpty()&&plan.get("imports").size()==1,"managed_import_retirement");JsonNode target=plan.get("imports").get(0);check(retiredImports.add(target.get("id").asString()),"managed_import_already_retired");retiredImportPlans.put(target.get("id").asString(),target);}
    floors.clear();floors.putAll(advanced);
  }
  JsonNode topic(String name)throws IOException {for(JsonNode topic:config.get("topics"))if(topic.get("name").asString().equals(name))return topic;throw new Failure("topic_binding");}
  Path partition(JsonNode topic){return root.resolve("segments").resolve(topic.get("id").asString()).resolve("0");}
  Prefix prefix(String topic)throws IOException {check(prefixes.containsKey(topic),"topic_binding");return prefixes.get(topic);}
  void validateImports()throws IOException {
    long count=0;try(var entries=Files.newDirectoryStream(root.resolve("imports"))){for(Path path:entries){
      check(++count<=registration.at("/limits/identity_tokens").asLong(),"managed_identity_budget");String name=path.getFileName().toString();
      if(name.startsWith(".partial-"))ManagedImport.verifyPartial(this,path);
      else if(!retiredImports.contains(name))ManagedImport.verifyClosure(this,name);
      else ManagedImport.validateRetired(this,path,retiredImportPlans.get(name));
    }}
  }
  void operation(String id,Store.Hook hook)throws IOException {
    check(writer,"read_only_archive");try{check(UUID.fromString(id).toString().equals(id),"managed_operation_id");}catch(IllegalArgumentException invalid){throw new Failure("managed_operation_id");}operation=id;this.hook=hook;
  }
  void reserve(long bytes)throws IOException {
    check(bytes>=0&&managedBytes()+bytes<=config.at("/limits/archive_bytes").asLong()-ManagedFormat.HEADROOM,"managed_admission_budget");
    check(Files.getFileStore(root).getUsableSpace()-bytes>=config.at("/limits/reserve_bytes").asLong(),"disk_reserve");
  }
  void tree()throws IOException {
    try(var files=Files.newDirectoryStream(root)){for(Path path:files)if(path.getFileName().toString().startsWith(".partial-"))ManagedPending.verify(this,path);else check(Set.of("archive.json","archive.sha256",".lock","objects","segments","maintenance","imports","progress.json").contains(path.getFileName().toString()),"unknown_managed_file");}
    Store.contents(root.resolve("maintenance"),Set.of("registration.json","registration.sha256","holds","retirements"));
    for(String directory:List.of("objects","segments","imports"))check(Files.isDirectory(root.resolve(directory),LinkOption.NOFOLLOW_LINKS),"managed_layout");
    check(config.at("/limits/archive_bytes").asLong()>ManagedFormat.HEADROOM&&managedBytes()<=config.at("/limits/archive_bytes").asLong()-CONTROL,"managed_budget");
  }
  long managedBytes()throws IOException {
    long[] total={0},nodes={0};Files.walkFileTree(root,new SimpleFileVisitor<>() {
      private void entry()throws IOException {check(++nodes[0]<=registration.at("/limits/identity_tokens").asLong(),"managed_identity_budget");}
      @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a)throws IOException {entry();check(!a.isSymbolicLink(),"unsafe_path");return FileVisitResult.CONTINUE;}
      @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {entry();check(a.isRegularFile(),"unsafe_path");total[0]=Math.addExact(total[0],a.size());return FileVisitResult.CONTINUE;}
    });return total[0];
  }
  byte[] payload(Path directory,String file,JsonNode metadata,int compressed,int decoded)throws IOException {
    JsonNode p=metadata.get("payload");byte[] zipped=Store.bounded(directory.resolve(file),compressed);
    check(zipped.length==p.get("compressed_bytes").asLong()&&io.detectbridge.transport.Json.sha(zipped).equals(p.get("compressed_sha256").asString()),"compressed_integrity");
    byte[] raw=decompress(zipped,decoded);check(raw.length==p.get("uncompressed_bytes").asLong()&&io.detectbridge.transport.Json.sha(raw).equals(p.get("uncompressed_sha256").asString()),"uncompressed_integrity");return raw;
  }
  byte[] object(String sha)throws IOException {
    check(sha.matches("[a-f0-9]{64}")&&Store.strings(config.get("objects")).contains(sha),"object_binding");return objectAt(root.resolve("objects").resolve(sha),sha);
  }
  byte[] objectAt(Path directory,String sha)throws IOException {
    Store.contents(directory,Set.of("bytes.ndjson.gz","object.json","object.sha256"));JsonNode metadata=Store.metadata(directory.resolve("object.json"),"object");
    check(metadata.get("sha256").asString().equals(sha)&&metadata.get("length").asLong()<=config.at("/limits/object_bytes").asLong(),"object_binding");
    byte[] raw=payload(directory,"bytes.ndjson.gz",metadata,48*MIB,44*MIB);
    check(raw.length==0||raw[raw.length-1]==10,"ndjson_final_lf");var out=new ByteArrayOutputStream();int start=0,count=0;
    for(int end=0;end<raw.length;end++)if(raw[end]==10) {
      check(end>start&&end-start<=ROW&&count<32,"ndjson_limit");JsonNode chunk=read(Arrays.copyOfRange(raw,start,end),ROW);require("chunk",chunk);
      byte[] bytes=decode(chunk.get("bytes"));check(chunk.get("offset").asLong()==out.size()&&bytes.length>0&&bytes.length<=MIB&&out.size()+(long)bytes.length<=metadata.get("length").asLong(),"chunk_bounds");out.write(bytes);start=end+1;count++;
    }
    check(count==metadata.at("/payload/rows").asLong(),"object_count");
    byte[] original=out.toByteArray();check(original.length==metadata.get("length").asLong()&&io.detectbridge.transport.Json.sha(original).equals(sha),"object_integrity");return original;
  }
  byte[] range(String sha,long offset,int length,String expected)throws IOException {
    byte[] bytes=object(sha);check(offset>=0&&length>0&&offset<=bytes.length&&length<=bytes.length-offset,"range_bounds");byte[] range=Arrays.copyOfRange(bytes,(int)offset,(int)offset+length);check(io.detectbridge.transport.Json.sha(range).equals(expected),"range_integrity");return range;
  }
  JsonNode segment(Path path,JsonNode topic,Prefix previous)throws IOException {
    Store.contents(path,Set.of("records.ndjson.gz","segment.json","segment.sha256"));JsonNode meta=Store.metadata(path.resolve("segment.json"),"segment");
    check(meta.get("binding_sha256").asString().equals(binding)&&meta.get("topic_id").equals(topic.get("id"))&&meta.get("first").asLong()==previous.next()&&meta.get("next").asLong()>previous.next()&&Objects.equals(meta.get("previous").isNull()?null:meta.get("previous").asString(),previous.previous())&&path.getFileName().toString().equals(Long.toString(previous.next())),"segment_binding");return meta;
  }
  List<JsonNode> segmentRows(Path path,JsonNode metadata,JsonNode topic)throws IOException {
    List<JsonNode> values=rows(payload(path,"records.ndjson.gz",metadata,17*MIB,(int)config.at("/limits/segment_bytes").asLong()),"wire",(int)config.at("/limits/segment_rows").asLong());
    check(values.size()==metadata.at("/payload/rows").asLong()&&Store.strings(metadata.get("dependencies")).equals(Store.strings(config.get("objects"))),"segment_count_or_dependencies");
    check(verifiedObjects.containsAll(Store.strings(metadata.get("dependencies"))),"missing_object");
    long previous=metadata.get("first").asLong()-1;for(JsonNode row:values){verifyWire(row,topic);long offset=row.get("offset").asLong();check(offset>previous&&offset>=metadata.get("first").asLong()&&offset<metadata.get("next").asLong(),"wire_interval");previous=offset;}return values;
  }
  void verifyWire(JsonNode row,JsonNode topic)throws IOException {
    require("wire",row);check(bytes(row).length<=ROW&&row.get("topic").equals(topic.get("name"))&&row.get("topic_id").equals(topic.get("id"))&&row.get("id").asString().equals(Store.wireId(config.get("cluster").asString(),topic.get("id").asString(),row.get("offset").asLong()))&&Store.strings(row.get("dependencies")).equals(Store.strings(config.get("objects"))),"wire_binding");
    byte[] value=decode(row.get("value"));check(value==null||value.length<=2*MIB,"wire_value_limit");decode(row.get("key"));for(JsonNode header:row.get("headers"))decode(header.get("value"));
  }
  void scan()throws IOException {
    Set<String> ids=new HashSet<>();for(JsonNode t:config.get("topics"))ids.add(t.get("id").asString());
    try(var files=Files.newDirectoryStream(root.resolve("segments"))){for(Path p:files){check(ids.contains(p.getFileName().toString()),"topic_binding");Store.contents(p,Set.of("0"));}}
    for(JsonNode t:config.get("topics")) {
      Prefix p=floors.get(t.get("name").asString());Path directory=partition(t);int entries=0,verified=0;
      if(Files.exists(directory)) {
        try(var paths=Files.newDirectoryStream(directory)){for(Path value:paths){
          String name=value.getFileName().toString();check(name.matches("0|[1-9][0-9]{0,18}"),"segment_path");
          long first;try{first=Long.parseLong(name);}catch(NumberFormatException invalid){throw new Failure("segment_path");}
          if(first<p.next()) {
            String key=t.get("id").asString()+"/0/"+name;check(retiredGarbage.containsKey(key)&&Files.isDirectory(value,LinkOption.NOFOLLOW_LINKS),"unowned_retired_segment");
            try(var garbage=Files.newDirectoryStream(value)){for(Path file:garbage)check(Set.of("records.ndjson.gz","segment.json","segment.sha256").contains(file.getFileName().toString())&&Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS),"unsafe_retired_segment");}
          }else entries++;
        }}
        while(Files.exists(directory.resolve(Long.toString(p.next())),LinkOption.NOFOLLOW_LINKS)) {
          Path path=directory.resolve(Long.toString(p.next()));JsonNode meta=segment(path,t,p);liveRows+=segmentRows(path,meta,t).size();check(liveRows<=registration.at("/limits/scan_rows").asLong(),"managed_scan_budget");p=new Prefix(meta.get("next").asLong(),hash(meta));boundary(t.get("name").asString(),p.next(),p.previous());verified++;
        }
        check(entries==verified,"segment_chain_gap");
      }
      prefixes.put(t.get("name").asString(),p);
    }
  }
  List<JsonNode> readSegment(String name,long first)throws IOException {
    JsonNode t=topic(name);check(first>=floors.get(name).next(),"archive_retired");Path p=partition(t).resolve(Long.toString(first));return segmentRows(p,Store.metadata(p.resolve("segment.json"),"segment"),t);
  }
  void forEachRow(String name,Store.RowAction action)throws IOException {
    JsonNode t=topic(name);long cursor=floors.get(name).next();
    while(cursor<prefix(name).next()) {
      Path path=partition(t).resolve(Long.toString(cursor));JsonNode meta=Store.metadata(path.resolve("segment.json"),"segment");
      for(JsonNode row:segmentRows(path,meta,t))action.accept(row);cursor=meta.get("next").asLong();
    }
  }
  void commitSegment(String name,long first,long next,List<JsonNode> rs)throws IOException {
    check(writer&&operation!=null,"managed_operation_required");JsonNode t=topic(name);Prefix old=prefix(name);
    if(first<old.next()) {check(next<=old.next(),"overlapping_retry");check(first>=floors.get(name).next(),"archive_retired");List<JsonNode> retained=readSegment(name,first);check(Arrays.equals(bytes(retained),bytes(rs)),"wire_conflict");return;}
    check(first==old.next()&&next>first&&rs.size()<=config.at("/limits/segment_rows").asLong(),"segment_interval");
    check(liveRows+rs.size()<=registration.at("/limits/scan_rows").asLong(),"managed_scan_budget");reserve(18L*MIB);var raw=new ByteArrayOutputStream();long prev=first-1;
    for(JsonNode row:rs){verifyWire(row,t);long off=row.get("offset").asLong();check(off>prev&&off>=first&&off<next,"wire_interval");raw.write(ndjson(row));prev=off;check(raw.size()<=config.at("/limits/segment_bytes").asLong(),"segment_limit");}
    for(String sha:Store.strings(config.get("objects")))object(sha);
    byte[] plain=raw.toByteArray(), zipped=compress(plain);check(zipped.length<=17*MIB,"compressed_limit");
    var m=new TreeMap<String,Object>();m.put("version","1.0.0");m.put("codec",CODEC);m.put("binding_sha256",binding);m.put("topic_id",t.get("id").asString());m.put("partition",0);m.put("first",first);m.put("next",next);m.put("previous",old.previous());m.put("dependencies",config.get("objects"));m.put("payload",Store.payloadMeta(plain,zipped,rs.size()));
    JsonNode meta=JSON.valueToTree(m);boundary(name,next,hash(meta));ManagedPending.segment(this,partition(t).resolve(Long.toString(first)),zipped,meta);prefixes.put(name,new Prefix(next,hash(meta)));liveRows+=rs.size();
  }
  Map<String,Object> progress()throws IOException {
    var parts=new TreeMap<String,Long>();for(var e:prefixes.entrySet())parts.put(e.getKey(),e.getValue().next());var retained=new TreeMap<String,Long>();for(var e:floors.entrySet())retained.put(e.getKey(),e.getValue().next());
    long used=managedBytes(),cap=config.at("/limits/archive_bytes").asLong(),pending=retiredGarbage.keySet().stream().filter(path->Files.exists(root.resolve("segments").resolve(path),LinkOption.NOFOLLOW_LINKS)).count();
    pending+=retiredImportPlans.keySet().stream().filter(id->Files.exists(root.resolve("imports").resolve(id),LinkOption.NOFOLLOW_LINKS)).count();
    var result=new TreeMap<String,Object>();result.put("retained_floor",retained);result.put("active_group",registration.get("group").asString());result.put("version","1.0.0");result.put("binding_sha256",binding);result.put("durable_next",parts);result.put("managed_bytes",used);result.put("historical_ready",false);result.put("dependencies_ready",Store.strings(config.get("objects")).stream().allMatch(sha->Files.isDirectory(root.resolve("objects").resolve(sha),LinkOption.NOFOLLOW_LINKS)));
    result.put("archive_bytes_cap",cap);result.put("archive_bytes_used",used);result.put("ordinary_headroom_bytes",Math.max(0,cap-ManagedFormat.HEADROOM-used));result.put("maintenance_headroom_bytes",Math.max(0,cap-ManagedFormat.CONTROL-used));result.put("free_bytes",Files.getFileStore(root).getUsableSpace());result.put("reserve_bytes",config.at("/limits/reserve_bytes").asLong());
    result.put("holds_count",(long)holds.get("holds").size());result.put("pending_cleanup_count",pending);result.put("fingerprint_count",fingerprints.values().stream().mapToLong(Set::size).sum());result.put("live_rows",liveRows);result.put("retirement_sequence",retirementSequence);return result;
  }

  void advisory(Object progress)throws IOException {check(writer&&operation!=null,"managed_operation_required");ManagedPending.progress(this,progress);}
  @Override public void close()throws IOException {lease.release();channel.close();}
}
