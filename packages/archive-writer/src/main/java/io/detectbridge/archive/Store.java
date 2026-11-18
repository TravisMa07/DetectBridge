package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Narrow local archive backend. Committed directories are authoritative. */
public final class Store implements AutoCloseable {
  @FunctionalInterface public interface Hook {void at(String phase) throws IOException;}
  public record Prefix(long next,String previous) {}
  public final Path root;
  public final JsonNode config;
  public final String binding;
  private final FileChannel channel;
  private final FileLock lock;
  private final Hook hook;
  private final Map<String,Prefix> prefixes=new TreeMap<>();
  public Store(Path root,boolean writer,Hook hook) throws IOException {
    this.root=root.toAbsolutePath().normalize();this.hook=hook;
    safeAncestors(this.root);check(Files.isDirectory(this.root,LinkOption.NOFOLLOW_LINKS),"archive_missing");
    FileChannel opened=null;FileLock held=null;
    try {
      if(writer){opened=FileChannel.open(this.root.resolve(".lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);try{held=opened.tryLock();}catch(OverlappingFileLockException e){throw new Failure("archive_locked");}check(held!=null,"archive_locked");}
      config=metadata(this.root.resolve("archive.json"),"configuration");binding=hash(config);validateConfig(config);
      validateTree();
      if(writer)cleanPartials();
      scan();
      if(writer) {
        // A surviving rename may precede the previous process's directory sync.
        Files.walkFileTree(this.root,new SimpleFileVisitor<>() {
          @Override public FileVisitResult postVisitDirectory(Path p,IOException error)throws IOException {
            if(error!=null)throw error;sync(p);return FileVisitResult.CONTINUE;
          }
        });
        hook.at("after_recovery_sync");
      }
      channel=opened;lock=held;
    } catch(Exception e){if(held!=null)held.release();if(opened!=null)opened.close();throw e;}
  }
  public Store(Path root,boolean writer) throws IOException {this(root,writer,p->{});}
  public static void validateConfig(JsonNode c) throws IOException {
    require("configuration",c);check(c.get("group").asString().equals("detectbridge-archive-v1-"+c.get("archive_id").asString()),"group_binding");
    var names=new HashSet<String>();var ids=new HashSet<String>();
    for(JsonNode t:c.get("topics")) {check(Main.TOPICS.contains(t.get("name").asString())&&names.add(t.get("name").asString())&&ids.add(t.get("id").asString())&&t.get("id").asString().matches("[A-Za-z0-9_-]{1,64}"),"topic_binding");}
    check(names.size()==9,"topic_binding");var objects=strings(c.get("objects"));var provenance=strings(c.get("provenance"));
    check(objects.size()==c.get("objects").size()&&provenance.size()==c.get("provenance").size()&&!provenance.isEmpty()&&objects.containsAll(provenance),"provenance_binding");
  }
  public static Set<String> strings(JsonNode a){var s=new TreeSet<String>();for(JsonNode n:a)s.add(n.asString());return s;}
  public static void create(Path root,JsonNode config) throws IOException {
    validateConfig(config);root=root.toAbsolutePath().normalize();safeAncestors(root.getParent());check(!Files.exists(root,LinkOption.NOFOLLOW_LINKS),"archive_exists");
    Path tmp=Files.createTempDirectory(root.getParent(),".archive-init-");
    try {
      write(tmp.resolve("archive.json"),ndjson(config));writeChecksum(tmp.resolve("archive.json"),ndjson(config));Files.createDirectory(tmp.resolve("objects"));Files.createDirectory(tmp.resolve("segments"));
      sync(tmp.resolve("objects"));sync(tmp.resolve("segments"));sync(tmp);Files.move(tmp,root);sync(root.getParent());
    } finally {if(Files.exists(tmp))deletePartial(tmp);}
  }
  static void safeAncestors(Path path) throws IOException {for(Path p=path;p!=null;p=p.getParent())check(!Files.isSymbolicLink(p),"unsafe_path");}
  static void sync(Path p) throws IOException {try(var c=FileChannel.open(p,StandardOpenOption.READ)){c.force(true);}}
  static void write(Path p,byte[] bytes) throws IOException {try(var c=FileChannel.open(p,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)){var b=java.nio.ByteBuffer.wrap(bytes);while(b.hasRemaining())c.write(b);c.force(true);}}
  static byte[] bounded(Path p,int cap) throws IOException {
    check(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)&&Files.size(p)<=cap,"unsafe_or_oversized_file");
    try(var in=Files.newInputStream(p,LinkOption.NOFOLLOW_LINKS)){byte[] b=in.readNBytes(cap+1);check(b.length<=cap,"file_limit");return b;}
  }
  static Path checksumPath(Path path){return path.resolveSibling(path.getFileName().toString().replace(".json",".sha256"));}
  static void writeChecksum(Path path,byte[] b)throws IOException {write(checksumPath(path),(Json.sha(b)+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));}
  static JsonNode metadata(Path path,String kind) throws IOException {byte[] b=bounded(path,MIB);check(Arrays.equals(bounded(checksumPath(path),65),(Json.sha(b)+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII)),"metadata_integrity");JsonNode n=read(b,MIB);require(kind,n);check(Arrays.equals(b,ndjson(n)),"metadata_noncanonical");return n;}
  static void deletePartial(Path dir) throws IOException {
    try(var paths=Files.walk(dir)){for(Path p:paths.sorted(Comparator.reverseOrder()).toList()){check(!Files.isSymbolicLink(p),"unsafe_partial");Files.delete(p);}}
  }
  private void cleanPartials() throws IOException {
    try(var dirs=Files.list(root)){for(Path p:dirs.filter(p->p.getFileName().toString().startsWith(".partial-")).toList()){
      check(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS),"unsafe_partial");
      Set<String> names;try(var files=Files.list(p)){names=files.map(f->f.getFileName().toString()).collect(java.util.stream.Collectors.toSet());}
      check(Set.of("bytes.ndjson.gz","object.json","object.sha256").containsAll(names)||Set.of("records.ndjson.gz","segment.json","segment.sha256").containsAll(names)||Set.of("progress.json").containsAll(names),"unsafe_partial");
      deletePartial(p);
    }}sync(root);
  }
  void validateTree() throws IOException {
    try(var entries=Files.list(root)){for(Path p:entries.toList()) {String n=p.getFileName().toString();check(Set.of("archive.json","archive.sha256",".lock","objects","segments","progress.json").contains(n)||n.matches("\\.partial-[a-zA-Z0-9-]+"),"unknown_archive_file");}}
    check(managedBytes()<=config.at("/limits/archive_bytes").asLong(),"archive_budget");
    for(String directory:List.of("objects","segments"))check(Files.isDirectory(root.resolve(directory),LinkOption.NOFOLLOW_LINKS),"archive_layout");
  }
  public long managedBytes() throws IOException {
    final long[] total={0};Files.walkFileTree(root,new SimpleFileVisitor<>() {
      @Override public FileVisitResult preVisitDirectory(Path p,BasicFileAttributes a)throws IOException {check(!a.isSymbolicLink(),"unsafe_path");return FileVisitResult.CONTINUE;}
      @Override public FileVisitResult visitFile(Path p,BasicFileAttributes a)throws IOException {check(a.isRegularFile(),"unsafe_path");total[0]=Math.addExact(total[0],a.size());return FileVisitResult.CONTINUE;}
    });return total[0];
  }
  void reserve(long bytes) throws IOException {
    check(managedBytes()+bytes<=config.at("/limits/archive_bytes").asLong(),"archive_budget");
    check(Files.getFileStore(root).getUsableSpace()-bytes>=config.at("/limits/reserve_bytes").asLong(),"disk_reserve");
  }
  public JsonNode topic(String name)throws IOException {for(JsonNode t:config.get("topics"))if(t.get("name").asString().equals(name))return t;throw new Failure("topic_binding");}
  Path partition(JsonNode t){return root.resolve("segments").resolve(t.get("id").asString()).resolve("0");}
  public Prefix prefix(String name)throws IOException {check(prefixes.containsKey(name),"topic_binding");return prefixes.get(name);}
  static void contents(Path dir,Set<String> expected)throws IOException {try(var s=Files.list(dir)){check(s.map(p->p.getFileName().toString()).collect(java.util.stream.Collectors.toSet()).equals(expected),"archive_contents");}}
  byte[] payload(Path dir,String file,JsonNode meta,int compressed,int rawLimit) throws IOException {
    JsonNode p=meta.get("payload");byte[] zipped=bounded(dir.resolve(file),compressed);
    check(zipped.length==p.get("compressed_bytes").asLong()&&Json.sha(zipped).equals(p.get("compressed_sha256").asString()),"compressed_integrity");
    byte[] raw=decompress(zipped,rawLimit);check(raw.length==p.get("uncompressed_bytes").asLong()&&Json.sha(raw).equals(p.get("uncompressed_sha256").asString()),"uncompressed_integrity");return raw;
  }
  public byte[] object(String sha)throws IOException {
    check(sha.matches("[a-f0-9]{64}"),"object_hash");Path dir=root.resolve("objects").resolve(sha);check(Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS),"missing_object");
    contents(dir,Set.of("bytes.ndjson.gz","object.json","object.sha256"));JsonNode m=metadata(dir.resolve("object.json"),"object");check(m.get("sha256").asString().equals(sha)&&m.get("length").asLong()<=config.at("/limits/object_bytes").asLong(),"object_binding");
    byte[] raw=payload(dir,"bytes.ndjson.gz",m,48*MIB,44*MIB);List<JsonNode> chunks=rows(raw,"chunk",32);check(chunks.size()==m.at("/payload/rows").asLong(),"object_count");
    var out=new ByteArrayOutputStream();for(JsonNode chunk:chunks){byte[] b=decode(chunk.get("bytes"));check(chunk.get("offset").asLong()==out.size()&&b.length>0&&b.length<=MIB&&out.size()+(long)b.length<=m.get("length").asLong(),"chunk_bounds");out.write(b);}
    byte[] original=out.toByteArray();check(original.length==m.get("length").asLong()&&Json.sha(original).equals(sha),"object_integrity");return original;
  }
  public byte[] range(String sha,long offset,int length,String expected)throws IOException {byte[] b=object(sha);check(offset>=0&&length>0&&offset<=b.length&&length<=b.length-offset,"range_bounds");byte[] r=Arrays.copyOfRange(b,(int)offset,(int)offset+length);check(Json.sha(r).equals(expected),"range_integrity");return r;}
  public void putObject(String sha,byte[] original)throws IOException {
    check(lock!=null,"read_only_archive");check(strings(config.get("objects")).contains(sha),"unregistered_object");
    check(original.length<=config.at("/limits/object_bytes").asLong()&&Json.sha(original).equals(sha),"object_integrity");
    Path target=root.resolve("objects").resolve(sha);if(Files.exists(target)){check(Arrays.equals(object(sha),original),"object_conflict");return;}
    reserve(49L*MIB);var raw=new ByteArrayOutputStream();int count=0;
    for(int off=0;off<original.length;off+=MIB){raw.write(ndjson(Map.of("offset",off,"bytes",b64(Arrays.copyOfRange(original,off,Math.min(original.length,off+MIB))))));count++;}
    byte[] plain=raw.toByteArray(), zipped=compress(plain);
    var meta=new TreeMap<String,Object>();meta.put("version","1.0.0");meta.put("codec",CODEC);meta.put("sha256",sha);meta.put("length",original.length);meta.put("payload",payloadMeta(plain,zipped,count));
    publish(target,"bytes.ndjson.gz","object.json",zipped,JSON.valueToTree(meta));
  }
  static Map<String,Object> payloadMeta(byte[] raw,byte[] zipped,int count){return Map.of("compressed_sha256",Json.sha(zipped),"compressed_bytes",zipped.length,"uncompressed_sha256",Json.sha(raw),"uncompressed_bytes",raw.length,"rows",count);}
  void publish(Path target,String filename,String metadata,byte[] zipped,JsonNode m)throws IOException {
    require(metadata.equals("object.json")?"object":"segment",m);reserve(zipped.length+MIB);
    // All destination parents must be durable before the committed child is relied on.
    var missing=new ArrayList<Path>();for(Path p=target.getParent();!Files.exists(p);p=p.getParent())missing.add(p);
    Collections.reverse(missing);for(Path p:missing){Files.createDirectory(p);sync(p);sync(p.getParent());}
    Path tmp=Files.createTempDirectory(root,".partial-");
    writePublication(tmp.resolve(filename),zipped,"payload");hook.at("after_payload");writePublication(tmp.resolve(metadata),ndjson(m),"metadata");writeChecksum(tmp.resolve(metadata),ndjson(m));hook.at("after_metadata");sync(tmp);hook.at("before_rename");
    check(!Files.exists(target,LinkOption.NOFOLLOW_LINKS),"publication_conflict");Files.move(tmp,target);hook.at("after_rename");sync(target.getParent());hook.at("after_directory_sync");
  }
  private void writePublication(Path p,byte[] bytes,String kind)throws IOException {
    try(var channel=FileChannel.open(p,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
      int middle=bytes.length/2;var first=java.nio.ByteBuffer.wrap(bytes,0,middle);
      while(first.hasRemaining())channel.write(first);hook.at("during_"+kind);
      var rest=java.nio.ByteBuffer.wrap(bytes,middle,bytes.length-middle);while(rest.hasRemaining())channel.write(rest);
      hook.at("before_"+kind+"_sync");channel.force(true);
    }
  }
  private void scan()throws IOException {
    try(var objects=Files.list(root.resolve("objects"))){for(Path p:objects.toList()){String sha=p.getFileName().toString();check(strings(config.get("objects")).contains(sha),"unregistered_object");object(sha);}}
    Set<String> ids=new HashSet<>();for(JsonNode t:config.get("topics"))ids.add(t.get("id").asString());
    try(var dirs=Files.list(root.resolve("segments"))){for(Path p:dirs.toList()){check(ids.contains(p.getFileName().toString()),"topic_binding");contents(p,Set.of("0"));}}
    for(JsonNode t:config.get("topics")) {
      Prefix prefix=new Prefix(t.get("start").asLong(),null);Path dir=partition(t);
      if(Files.exists(dir)) {
        int entries=0;
        try(var paths=Files.newDirectoryStream(dir)) {
          for(Path p:paths){check(p.getFileName().toString().matches("0|[1-9][0-9]{0,18}"),"segment_path");entries++;}
        }
        int verified=0;
        while(Files.exists(dir.resolve(Long.toString(prefix.next())),LinkOption.NOFOLLOW_LINKS)) {
          Path p=dir.resolve(Long.toString(prefix.next()));JsonNode m=segmentMeta(p,t,prefix);
          segmentRows(p,m,t);
          prefix=new Prefix(m.get("next").asLong(),hash(m));verified++;
        }
        check(verified==entries,"segment_chain_gap");
      }
      prefixes.put(t.get("name").asString(),prefix);
    }
  }
  JsonNode segmentMeta(Path dir,JsonNode t,Prefix previous)throws IOException {
    contents(dir,Set.of("records.ndjson.gz","segment.json","segment.sha256"));JsonNode m=metadata(dir.resolve("segment.json"),"segment");
    check(m.get("binding_sha256").asString().equals(binding)&&m.get("topic_id").equals(t.get("id"))&&m.get("first").asLong()==previous.next()&&m.get("next").asLong()>previous.next()&&Objects.equals(m.get("previous").isNull()?null:m.get("previous").asString(),previous.previous())&&dir.getFileName().toString().equals(Long.toString(previous.next())),"segment_binding");return m;
  }
  List<JsonNode> segmentRows(Path dir,JsonNode m,JsonNode t)throws IOException {
    List<JsonNode> rs=rows(payload(dir,"records.ndjson.gz",m,17*MIB,(int)config.at("/limits/segment_bytes").asLong()),"wire",(int)config.at("/limits/segment_rows").asLong());
    check(rs.size()==m.at("/payload/rows").asLong()&&strings(m.get("dependencies")).equals(strings(config.get("objects"))),"segment_count_or_dependencies");
    for(String sha:strings(m.get("dependencies")))object(sha);
    long offset=m.get("first").asLong()-1;for(JsonNode row:rs){verifyWire(row,t);check(row.get("offset").asLong()>offset&&row.get("offset").asLong()>=m.get("first").asLong()&&row.get("offset").asLong()<m.get("next").asLong(),"wire_interval");offset=row.get("offset").asLong();}
    return rs;
  }
  void verifyWire(JsonNode row,JsonNode t)throws IOException {
    require("wire",row);check(bytes(row).length<=ROW&&row.get("topic").equals(t.get("name"))&&row.get("topic_id").equals(t.get("id"))&&row.get("id").asString().equals(wireId(config.get("cluster").asString(),t.get("id").asString(),row.get("offset").asLong()))&&strings(row.get("dependencies")).equals(strings(config.get("objects"))),"wire_binding");
    byte[] value=decode(row.get("value"));check(value==null||value.length<=2*MIB,"wire_value_limit");decode(row.get("key"));for(JsonNode h:row.get("headers"))decode(h.get("value"));
  }
  public static String wireId(String cluster,String topic,long offset){return "sha256:"+hash(List.of("detectbridge.archive.wire/1",cluster,topic,"0",Long.toString(offset)));}
  public List<JsonNode> readSegment(String name,long first)throws IOException {
    JsonNode t=topic(name);Path p=partition(t).resolve(Long.toString(first));JsonNode m=metadata(p.resolve("segment.json"),"segment");return segmentRows(p,m,t);
  }
  @FunctionalInterface interface RowAction {void accept(JsonNode row)throws IOException;}
  void forEachRow(String name,RowAction action)throws IOException {
    JsonNode t=topic(name);long cursor=t.get("start").asLong();while(cursor<prefix(name).next()) {Path p=partition(t).resolve(Long.toString(cursor));JsonNode m=metadata(p.resolve("segment.json"),"segment");for(JsonNode row:segmentRows(p,m,t))action.accept(row);cursor=m.get("next").asLong();}
  }
  public void commitSegment(String name,long first,long next,List<JsonNode> rs)throws IOException {
    check(lock!=null,"read_only_archive");JsonNode t=topic(name);Prefix old=prefix(name);
    if(first<old.next()) {check(next<=old.next(),"overlapping_retry");List<JsonNode> retained=readSegment(name,first);check(Arrays.equals(bytes(retained),bytes(rs)),"wire_conflict");return;}
    check(first==old.next()&&next>first&&rs.size()<=config.at("/limits/segment_rows").asLong(),"segment_interval");
    reserve(18L*MIB);var raw=new ByteArrayOutputStream();long prev=first-1;
    for(JsonNode row:rs){verifyWire(row,t);long off=row.get("offset").asLong();check(off>prev&&off>=first&&off<next,"wire_interval");raw.write(ndjson(row));prev=off;check(raw.size()<=config.at("/limits/segment_bytes").asLong(),"segment_limit");}
    for(String sha:strings(config.get("objects")))object(sha);
    byte[] plain=raw.toByteArray(), zipped=compress(plain);check(zipped.length<=17*MIB,"compressed_limit");
    var m=new TreeMap<String,Object>();m.put("version","1.0.0");m.put("codec",CODEC);m.put("binding_sha256",binding);m.put("topic_id",t.get("id").asString());m.put("partition",0);m.put("first",first);m.put("next",next);m.put("previous",old.previous());m.put("dependencies",config.get("objects"));m.put("payload",payloadMeta(plain,zipped,rs.size()));
    JsonNode meta=JSON.valueToTree(m);publish(partition(t).resolve(Long.toString(first)),"records.ndjson.gz","segment.json",zipped,meta);prefixes.put(name,new Prefix(next,hash(meta)));
  }
  public Map<String,Object> progress()throws IOException {
    var parts=new TreeMap<String,Long>();for(var e:prefixes.entrySet())parts.put(e.getKey(),e.getValue().next());return Map.of("version","1.0.0","binding_sha256",binding,"durable_next",parts,"managed_bytes",managedBytes(),"historical_ready",false,"dependencies_ready",strings(config.get("objects")).stream().allMatch(sha->Files.isDirectory(root.resolve("objects").resolve(sha),LinkOption.NOFOLLOW_LINKS)));
  }
  public void advisory(Object progress)throws IOException {
    check(lock!=null,"read_only_archive");byte[] b=ndjson(progress);check(b.length<=MIB,"progress_limit");reserve(b.length);Path tmp=root.resolve(".partial-"+UUID.randomUUID());Files.createDirectory(tmp);write(tmp.resolve("progress.json"),b);sync(tmp);Files.move(tmp.resolve("progress.json"),root.resolve("progress.json"),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);Files.delete(tmp);sync(root);
  }
  @Override public void close()throws IOException {if(lock!=null)lock.release();if(channel!=null)channel.close();}
}
