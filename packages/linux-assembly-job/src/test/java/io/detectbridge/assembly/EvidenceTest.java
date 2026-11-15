package io.detectbridge.assembly;

import static org.junit.jupiter.api.Assertions.*;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.node.ObjectNode;

class EvidenceTest {
  @Test void registeredReferencesResolveExactBytesWithoutFetchingAndRejectTampering() throws Exception {
    Path root=Files.createTempDirectory("assembly-evidence-");
    try {
      byte[] bytes="first\nsecond\n".getBytes(java.nio.charset.StandardCharsets.UTF_8);String hash=Json.sha(bytes);
      var registration=Json.MAPPER.valueToTree(Map.of("version","1.0.0","objects",List.of(Map.of("sha256",hash,"size_bytes",bytes.length))));
      Path manifest=root.resolve("registration.json");Files.write(manifest,Json.bytes(registration));Files.write(root.resolve(hash),bytes);
      var resolver=LocalEvidence.open(root,manifest,Machine.hash(registration));
      var raw=(ObjectNode)Json.MAPPER.valueToTree(Map.of("cursor",Map.of("kind","dataset","artifact_sha256",hash,"position",1),
          "evidence",Map.of("encoding","utf-8","sha256",Json.sha("second\n".getBytes(java.nio.charset.StandardCharsets.UTF_8)),
              "reference",Map.of("uri","HTTPS://never-fetch.invalid/evidence","object_sha256",hash,"byte_range",Map.of("offset",6,"length",7)))));
      assertArrayEquals("second\n".getBytes(java.nio.charset.StandardCharsets.UTF_8),resolver.resolve(raw));
      ((ObjectNode)raw.get("cursor")).put("position",0);
      assertThrows(IllegalArgumentException.class,()->resolver.resolve(raw));
      ((ObjectNode)raw.get("cursor")).put("position",1);Files.writeString(root.resolve(hash),"changed");
      assertThrows(IllegalArgumentException.class,()->resolver.resolve(raw));
      Files.delete(root.resolve(hash));assertThrows(java.io.IOException.class,()->resolver.resolve(raw));
      Files.writeString(manifest,"{}");assertThrows(IllegalArgumentException.class,resolver::verify);
    } finally {try(var files=Files.list(root)){for(Path path:files.toList())Files.delete(path);}Files.delete(root);}
  }
}
