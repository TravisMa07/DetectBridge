package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import static org.junit.jupiter.api.Assertions.*;

import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.security.KeyPairGenerator;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.node.ObjectNode;

class LifecycleManifestTest {
    ObjectNode manifest() throws Exception {
        Path fixture=Path.of(System.getProperty("repository.root"),"contracts/lifecycle-runtime/v1/fixtures/binding-vectors.json");
        ObjectNode common=(ObjectNode) read(Files.readAllBytes(fixture),MIB).at("/vectors/0/preimage");
        byte[] key=KeyPairGenerator.getInstance("Ed25519").generateKeyPair().getPublic().getEncoded();
        common.put("authority_key_sha256",Json.sha(key)).put("runtime_sha256",LifecycleManifest.RUNTIME)
              .put("producer_sha256",LifecycleManifest.PRODUCER).put("compatibility_sha256",LifecycleManifest.COMPATIBILITY);
        ((ObjectNode)common.get("validator")).put("artifact_sha256",LifecycleManifest.COMPILER);
        return JSON.valueToTree(Map.of(
            "version", LifecycleManifest.VERSION, "archive_id", UUID.randomUUID().toString(),
            "common",common, "authority_public_key",b64(key),
            "workers",List.of(Map.of("worker_id",UUID.randomUUID().toString(),"input_topic",Map.of("name","source1","partition",0,"id","input1"))),
            "objects",List.of(Map.of("kind","runtime","sha256",LifecycleManifest.RUNTIME),Map.of("kind","producer","sha256",LifecycleManifest.PRODUCER),
                Map.of("kind","validator","sha256",LifecycleManifest.COMPILER),Map.of("kind","registry","sha256","1".repeat(64)),
                Map.of("kind","provenance","sha256","2".repeat(64)))));
    }

    @Test void checksPublicBindingsWithoutRelaxingLegacyInventory() throws Exception {
        ObjectNode original=manifest();
        LifecycleManifest profile=new LifecycleManifest(original);
        assertEquals(5,profile.topics.size());
        assertThrows(Failure.class,()-> Store.validateConfig(original));
        ObjectNode mutated=original.deepCopy();
        ((ObjectNode)mutated.at("/workers/0/input_topic")).put("id",original.at("/common/topics/control/id").asString());
        assertThrows(Failure.class,()->new LifecycleManifest(mutated));
        ((ObjectNode)original.at("/common/topics")).remove("ack");
        assertThrows(Failure.class,()->new LifecycleManifest(original));
    }

    @Test void validatesExactRegisteredBytesAndRejectsWrongRuntime() throws Exception {
        ObjectNode original=manifest();
        LifecycleManifest profile=new LifecycleManifest(original);
        Path folder=Files.createTempDirectory("lifecycle-object-test");
        Path path=folder.resolve(LifecycleManifest.PRODUCER);
        try {
            Files.writeString(path,"these bytes are not the semantic evaluator");
            assertThrows(Failure.class,()->profile.object(folder,LifecycleManifest.PRODUCER));
            assertThrows(Failure.class,()->profile.object(folder,"../outside"));
        } finally {Files.deleteIfExists(path);Files.delete(folder);}
        ((ObjectNode)original.get("common")).put("runtime_sha256","3".repeat(64));
        assertThrows(Failure.class,()->new LifecycleManifest(original));
    }
}
