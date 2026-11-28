package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static io.detectbridge.archive.LifecycleSegments.*;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Exclusive local archive view shared by physical capture, retention and replay export. */
final class LifecycleStore implements AutoCloseable {
    final Path root;
    final LifecycleManifest manifest;
    final String binding;
    final Map<String,LifecycleSegments> chains = new TreeMap<>();
    final FileChannel channel;
    long used;
    int rows;

    static long size(Path dir) throws IOException {
        long[] used={0};
        Files.walkFileTree(dir,new SimpleFileVisitor<>() {
            @Override public FileVisitResult visitFile(Path p,BasicFileAttributes attributes) throws IOException {
                check(attributes.isRegularFile() && ((Number) Files.getAttribute(p,"unix:nlink",LinkOption.NOFOLLOW_LINKS)).intValue()==1,"archive_file_type");
                used[0]=Math.addExact(used[0],attributes.size());
                check(used[0]<=BUDGET,"archive_budget");
                return FileVisitResult.CONTINUE;
            }
        });
        return used[0];
    }

    static void create(Path root, Path manifestPath, Path objects, String executable) throws IOException {
        Store.safeAncestors(root);
        Store.safeAncestors(manifestPath);
        Store.safeAncestors(objects);
        check(!Files.exists(root,LinkOption.NOFOLLOW_LINKS) && !root.startsWith(objects) && !objects.startsWith(root),"fresh_archive");
        LifecycleManifest manifest=new LifecycleManifest(read(Store.bounded(manifestPath,MIB),MIB));
        long sourceSize=size(objects);
        manifest.verifyObjects(objects);
        check(sourceSize+2L*MIB <= BUDGET && Files.getFileStore(root.getParent()).getUsableSpace() >= sourceSize+RESERVE+2L*MIB,"archive_budget");
        Path tmp=Files.createTempDirectory(root.getParent(),".lifecycle-init-");
        try {
            Store.write(tmp.resolve(".lock"),new byte[0]);
            writeDocument(tmp.resolve("archive.json"),JSON.valueToTree(Map.of("manifest",manifest.document,"writer_sha256",executable)));
            Path registered=Files.createDirectory(tmp.resolve("objects"));
            for (String sha:manifest.objects.keySet()) Store.write(registered.resolve(sha),manifest.object(objects,sha));
            Store.sync(registered);
            Path segments=Files.createDirectory(tmp.resolve("segments"));
            for (var topic:manifest.topics.values()) {
                Path directory=Files.createDirectory(segments.resolve(topic.id()));
                Store.write(directory.resolve("head"),emptyHead());
                Store.sync(directory);
            }
            Store.sync(segments); Store.sync(tmp);
            // A nonempty existing archive cannot be displaced by a directory rename.
            Files.move(tmp,root,StandardCopyOption.ATOMIC_MOVE);
            Store.sync(root.getParent());
        } finally {
            if (Files.exists(tmp,LinkOption.NOFOLLOW_LINKS)) Store.deletePartial(tmp);
        }
    }

    LifecycleStore(Path root, boolean recover, String executable) throws IOException {
        this.root=root;
        Store.safeAncestors(root);
        check(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS),"archive_missing");
        channel=FileChannel.open(root.resolve(".lock"),StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
        try {
            FileLock lock;
            try {lock=channel.tryLock();} catch (OverlappingFileLockException ex) {throw new Failure("archive_locked");}
            check(lock!=null,"archive_locked");
            used=size(root);
            Store.contents(root,Set.of(".lock","archive.json","archive.sha256","objects","segments"));
            JsonNode metadata=document(root.resolve("archive.json"));
            LifecycleManifest.keys(metadata,"manifest","writer_sha256");
            check(executable.equals(metadata.get("writer_sha256").asString()),"reader_identity");
            manifest=new LifecycleManifest(metadata.get("manifest"));
            binding=hash(manifest.document);
            manifest.verifyObjects(root.resolve("objects"));
            Set<String> ids=new HashSet<>();
            for (var t:manifest.topics.values()) ids.add(t.id());
            Path segments=root.resolve("segments");
            Store.contents(segments,ids);
            for (var topic:manifest.topics.values()) {
                LifecycleSegments chain=new LifecycleSegments(segments.resolve(topic.id()),topic,binding);
                chain.scan(null,recover);
                check(rows<=MAX_ROWS-chain.count,"archive_row_limit");
                rows+=chain.count;
                chains.put(topic.name(),chain);
            }
        } catch (Exception e) {channel.close(); throw e;}
    }

    Map<String,Long> heads() {
        Map<String,Long> heads=new TreeMap<>();
        chains.forEach((name,chain)->heads.put(name,chain.next));
        return heads;
    }

    void export(OutputStream destination) throws IOException {
        destination.write(ndjson(Map.of("type","manifest","manifest",manifest.document,"heads",heads())));
        for (var chain:chains.values()) chain.scan(destination,false);
    }

    void publish(String name,List<JsonNode> records,long end,Store.Hook hook) throws IOException {
        var chain=chains.get(name);
        used+=chain.publish(records,end,used,MAX_ROWS-rows,hook);
        rows+=records.size();
    }

    @Override public void close() throws IOException {channel.close();}
}
