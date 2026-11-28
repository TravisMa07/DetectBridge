package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class LifecycleSegmentsTest {
    @TempDir Path directory;
    private final LifecycleManifest.Topic output = new LifecycleManifest.Topic("worker.output","originalId","output");
    private final String binding = "a".repeat(64);
    private LifecycleSegments segments;
    private final Store.Hook normal = phase -> {};

    @BeforeEach void create() throws IOException {
        Files.write(directory.resolve("head"),LifecycleSegments.emptyHead());
        segments = new LifecycleSegments(directory, output, binding);
    }

    ObjectNode wire(long offset) {
        ObjectNode row = JSON.createObjectNode();
        row.put("type","wire").put("topic",output.name()).put("topic_id",output.id())
            .put("partition",0).put("offset",offset).put("timestamp",34)
            .put("timestamp_type","CreateTime").putNull("key").put("value","/wA=");
        var headers = row.putArray("headers");
        headers.addObject().put("name","repeated").putNull("value");
        headers.addObject().put("name","repeated").put("value","");
        return row;
    }

    @Test void publishedOpaqueBytesSurviveReopenBeforeGroupCommit() throws IOException {
        ObjectNode original = wire(1);
        segments.publish(List.of(original),2,0,65536,normal);
        // Reopening is equivalent to the durable state left by a pre-Kafka-commit death.
        var restored = new LifecycleSegments(directory,output,binding);
        var export = new ByteArrayOutputStream();
        restored.scan(export,true);
        assertEquals(2,restored.next);
        assertEquals(1,restored.count);
        assertArrayEquals(ndjson(original), export.toByteArray());
        assertEquals(2, Main.reconcile(2,0L,0,2));
        assertThrows(Failure.class,()-> Main.reconcile(2,3L,0,3));
        assertThrows(Failure.class,()-> Main.reconcile(2,0L,3,4));
        assertThrows(Failure.class,()-> LifecycleArchive.rejectRetirement());
        assertEquals(2,restored.next);
    }

    @Test void prepublicationInterruptionLeavesNoRowsAndCanResume() throws IOException {
        assertThrows(IOException.class,()->segments.publish(List.of(wire(0)),1,0,65536,
            phase->{throw new IOException("planned prepublication interruption");}));
        assertTrue(Files.exists(directory.resolve(".segment-partial/records.ndjson.gz")));
        var restored = new LifecycleSegments(directory,output,binding);
        restored.scan(null,true);
        assertEquals(0,restored.next);
        assertFalse(Files.exists(directory.resolve(".segment-partial")));
        restored.publish(List.of(wire(0)),1,0,65536,normal);
        restored.scan(null,true);
        assertEquals(1,restored.next);
    }

    @Test void postRenameInterruptionCanRepairAnchorButMissingPublishedTailFails() throws IOException {
        segments.publish(List.of(wire(0)),1,0,65536,normal);
        Files.write(directory.resolve("head"),LifecycleSegments.emptyHead());
        segments.scan(null,true);
        assertEquals(1,read(Files.readAllBytes(directory.resolve("head")),1024).get("next").asLong());
        Store.deletePartial(directory.resolve("0"));
        assertThrows(Failure.class,()->segments.scan(null,true));
    }

    @Test void corruptedPayloadBlocksExportAndRemainsOnDisk() throws IOException {
        segments.publish(List.of(wire(0)),1,0,65536,normal);
        Path payload = directory.resolve("0/records.ndjson.gz");
        byte[] corrupted = Files.readAllBytes(payload);
        corrupted[15] ^= 1;
        Files.write(payload,corrupted);
        var export = new ByteArrayOutputStream();
        assertThrows(Failure.class,()->segments.scan(export,false));
        assertEquals(0,export.size());
        assertArrayEquals(corrupted, Files.readAllBytes(payload));
    }

    @Test void unknownPartialCannotBeUnlinkedByRecovery() throws IOException {
        Path partial = Files.createDirectory(directory.resolve(".segment-partial"));
        Path original = Files.writeString(partial.resolve("unrecognized"),"retain");
        assertThrows(Failure.class,()->segments.scan(null,true));
        assertEquals("retain",Files.readString(original));
    }

    @Test void emptyIntervalAndTopicIdentityAreChecked() throws IOException {
        segments.publish(List.of(),3L,0,0,normal);
        segments.scan(null,false);
        assertEquals(3,segments.next);
        assertEquals(0,segments.count);
        ObjectNode other=wire(3).put("topic_id","same-name-different-id");
        assertThrows(Failure.class,()->segments.publish(List.of(other),4,0,1,normal));
        assertThrows(Failure.class,()->segments.publish(List.of(wire(3)),4,0,0,normal));
        assertEquals(3,segments.next);
        assertFalse(Files.exists(directory.resolve("3")));
    }
}
