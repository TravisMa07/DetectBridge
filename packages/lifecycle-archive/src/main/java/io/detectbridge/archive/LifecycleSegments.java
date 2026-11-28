package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static io.detectbridge.archive.LifecycleManifest.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import tools.jackson.core.StreamReadConstraints;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.core.json.JsonFactory;
import tools.jackson.databind.*;
import tools.jackson.databind.json.JsonMapper;

/** Durable per-topic contiguous segment chain. Caller holds the archive lock. */
final class LifecycleSegments {
    static final int MAX_ROWS = 65536;
    static final int ROW_BYTES = 8*MIB;
    static final long BUDGET = 2L*1024*MIB;
    static final long RESERVE = 128L*MIB;
    static final JsonMapper ROW_JSON = JsonMapper.builder(JsonFactory.builder()
        .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
        .streamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(64)
            .maxStringLength(ROW_BYTES).maxNumberLength(128).build()).build())
        .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
    private final Path directory;
    private final String binding;
    final Topic topic;
    long next;
    String previous;
    int count;

    LifecycleSegments(Path directory, Topic topic, String binding) {
        this.directory = directory;
        this.topic = topic;
        this.binding = binding;
    }

    static void writeDocument(Path path, JsonNode document) throws IOException {
        byte[] data = ndjson(document);
        Store.write(path, data);
        Store.writeChecksum(path, data);
    }

    static JsonNode document(Path path) throws IOException {
        byte[] raw = Store.bounded(path, MIB);
        check(Arrays.equals(Store.bounded(Store.checksumPath(path),65),
            (Json.sha(raw) + "\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII)), "metadata_integrity");
        JsonNode doc = read(raw, MIB);
        check(Arrays.equals(raw, ndjson(doc)), "metadata_canonical");
        return doc;
    }

    static void verifyRow(JsonNode row, Topic topic) throws IOException {
        keys(row, "type","topic","topic_id","partition","offset","timestamp","timestamp_type","key","value","headers");
        check("wire".equals(row.get("type").asString()) && row.get("topic").asString().equals(topic.name())
              && row.get("topic_id").asString().equals(topic.id()), "wire_topic");
        integer(row.get("partition"), 0, 0);
        integer(row.get("offset"), 0, Long.MAX_VALUE-1);
        integer(row.get("timestamp"), -1, Long.MAX_VALUE);
        string(row.get("timestamp_type"), "CreateTime|LogAppendTime|NoTimestampType");
        check(row.get("key").isTextual() || row.get("key").isNull(), "wire_key");
        check(row.get("value").isTextual() || row.get("value").isNull(), "wire_value");
        decode(row.get("key"));
        LifecycleArchive.verifyValue(topic.role(), decode(row.get("value")));
        JsonNode headers = row.get("headers");
        check(headers.isArray() && headers.size() <= 128, "headers_limit");
        for (JsonNode header : headers) {
            keys(header,"name","value");
            check(header.get("name").isTextual() && (header.get("value").isTextual() || header.get("value").isNull()), "wire_header");
            decode(header.get("value"));
        }
    }

    private void segment(Path path, OutputStream wires) throws IOException {
        Store.contents(path, Set.of("segment.json","segment.sha256","records.ndjson.gz"));
        JsonNode meta = document(path.resolve("segment.json"));
        keys(meta, "version","binding_sha256","topic_id","partition","first","next","previous",
             "rows","compressed_sha256","plain_sha256");
        check(VERSION.equals(meta.get("version").asString()) && binding.equals(meta.get("binding_sha256").asString())
              && topic.id().equals(meta.get("topic_id").asString())
              && (previous == null ? meta.get("previous").isNull() : previous.equals(meta.get("previous").asString())),
              "segment_binding");
        integer(meta.get("partition"),0,0);
        integer(meta.get("first"),next,next);
        long end = integer(meta.get("next"), next + 1, Long.MAX_VALUE);
        long rows = integer(meta.get("rows"),0,256);
        byte[] zip = Store.bounded(path.resolve("records.ndjson.gz"),17*MIB);
        check(Json.sha(zip).equals(meta.get("compressed_sha256").asString()), "segment_compressed_integrity");
        byte[] raw = decompress(zip, SEGMENT);
        check(Json.sha(raw).equals(meta.get("plain_sha256").asString()), "segment_integrity");
        int start = 0, seen = 0;
        long last = next-1;
        for (int i = 0; i < raw.length; i++) if (raw[i] == 10) {
            check(i-start > 0 && i-start < ROW_BYTES && ++seen <= rows, "row_limit");
            byte[] line = Arrays.copyOfRange(raw,start,i);
            JsonNode row = ROW_JSON.readTree(line);
            check(Arrays.equals(line, bytes(row)), "row_canonical");
            verifyRow(row,topic);
            long offset = row.get("offset").asLong();
            check(offset > last && offset < end, "wire_interval");
            last = offset;
            if (wires != null) wires.write(raw,start,i+1-start);
            start = i+1;
        }
        check(start==raw.length && seen==rows && count <= MAX_ROWS-seen,"segment_rows");
        count += seen;
        previous = hash(meta);
        next = end;
    }

    void scan(OutputStream wires, boolean recover) throws IOException {
        count=0; previous=null; next=0;
        JsonNode anchor = read(Store.bounded(directory.resolve("head"),1024),1024);
        keys(anchor, "next","sha256");
        long anchored = integer(anchor.get("next"),0,Long.MAX_VALUE);
        boolean matched = anchored==0 && anchor.get("sha256").isNull();
        Set<String> names = new HashSet<>();
        try (var files=Files.newDirectoryStream(directory)) {
            for (Path entry : files) {
                String name=entry.getFileName().toString();
                if (name.equals("head")) continue;
                if (name.equals(".head-partial") || name.equals(".segment-partial")) {
                    if (recover) clean(entry);
                    continue;
                }
                check(name.matches("0|[1-9][0-9]{0,18}") && names.size() < 131072, "segment_layout");
                names.add(name);
            }
        }
        while (names.remove(Long.toString(next))) {
            segment(directory.resolve(Long.toString(next)),wires);
            if (anchored==next && previous.equals(anchor.get("sha256").asString())) matched=true;
        }
        check(names.isEmpty() && matched,"broken_segment_chain");
        if (recover) {
            // A prior process may have died after rename but before syncing its parent.
            Store.sync(directory);
            if (next != anchored) updateAnchor();
        }
    }

    private void clean(Path path) throws IOException {
        if (path.getFileName().toString().equals(".head-partial")) {
            check(Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS),"unexpected_partial");
            Files.delete(path);
        } else {
            check(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"unexpected_partial");
            try (var files=Files.list(path)) {
                for (Path member:files.toList()) {
                    check(Set.of("records.ndjson.gz","segment.json","segment.sha256").contains(member.getFileName().toString())
                          && Files.isRegularFile(member,LinkOption.NOFOLLOW_LINKS),"unexpected_partial");
                }
            }
            Store.deletePartial(path);
        }
        Store.sync(directory);
    }

    static byte[] emptyHead() {return ndjson(Map.of("next",0,"sha256",JSON.nullNode()));}
    private void updateAnchor() throws IOException {
        Path temporary=directory.resolve(".head-partial");
        Store.write(temporary,ndjson(Map.of("next",next,"sha256",previous)));
        Files.move(temporary,directory.resolve("head"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        Store.sync(directory);
    }

    long publish(List<JsonNode> rows, long end, long used, int remainingRows, Store.Hook hook) throws IOException {
        check(end > next && rows.size() <= 256 && rows.size() <= remainingRows, "segment_interval");
        var out = new ByteArrayOutputStream();
        long last = next-1;
        for (JsonNode row : rows) {
            verifyRow(row,topic);
            long offset = row.get("offset").asLong();
            check(offset>last && offset<end,"wire_interval");
            last=offset;
            byte[] line = ndjson(row);
            check(line.length <= ROW_BYTES && out.size() + line.length <= SEGMENT,"segment_size");
            out.write(line);
        }
        byte[] raw=out.toByteArray(), zip=compress(raw);
        Map<String,Object> m=new TreeMap<>();
        m.put("version",VERSION); m.put("binding_sha256",binding); m.put("topic_id",topic.id());
        m.put("partition",0); m.put("first",next); m.put("next",end); m.put("previous",previous);
        m.put("rows",rows.size()); m.put("plain_sha256",Json.sha(raw)); m.put("compressed_sha256",Json.sha(zip));
        JsonNode meta=JSON.valueToTree(m);
        long added=zip.length+ndjson(meta).length+65;
        check(used+added+1024 <= BUDGET && Files.getFileStore(directory).getUsableSpace()-added-1024 >= RESERVE,"archive_budget");
        Path tmp=Files.createDirectory(directory.resolve(".segment-partial"));
        Store.write(tmp.resolve("records.ndjson.gz"),zip);
        writeDocument(tmp.resolve("segment.json"),meta);
        Store.sync(tmp);
        if (!rows.isEmpty()) hook.at("before_segment_publish");
        Files.move(tmp,directory.resolve(Long.toString(next)),StandardCopyOption.ATOMIC_MOVE);
        Store.sync(directory);
        next=end; previous=hash(meta); count+=rows.size();
        updateAnchor();
        return added+128;
    }
}
