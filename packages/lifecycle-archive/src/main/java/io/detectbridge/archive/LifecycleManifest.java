package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;

import io.detectbridge.transport.Json;
import java.io.IOException;
import java.nio.file.*;
import java.security.KeyFactory;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Validates the fixed physical inventory independently of Kafka message contents. */
final class LifecycleManifest {
    static final String VERSION = "lifecycle-archive/1";
    static final String RUNTIME = "055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d";
    static final String PRODUCER = "51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d";
    static final String COMPILER = "f2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d";
    static final String COMPATIBILITY = "ff2a1f54535aa73eec63e72717426b893c2eb9d15982e807d5b46c0ee7e736ef";
    static final String IMAGE = "flink:2.2.1-scala_2.12-java17@sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe";
    record Topic(String name, String id, String role) {}
    final JsonNode document;
    final Map<String,Topic> topics = new TreeMap<>();
    final Map<String,String> objects = new TreeMap<>();
    final String cluster;
    final String group;

    static void keys(JsonNode node, String... keys) throws IOException {
        check(node != null && node.isObject() && node.size() == keys.length, "unexpected_fields");
        for (String key : keys) check(node.has(key), "missing_field");
    }

    static String string(JsonNode node, String pattern) throws IOException {
        check(node != null && node.isTextual() && node.asString().matches(pattern), "field_format");
        return node.asString();
    }

    static long integer(JsonNode value, long min, long max) throws IOException {
        check(value.isIntegralNumber() && value.canConvertToLong()
              && value.asLong() >= min && value.asLong() <= max, "integer_range");
        return value.asLong();
    }

    static String uuid(JsonNode node) throws IOException {
        return string(node, "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}");
    }

    private void topic(String role, JsonNode descriptor, Set<String> ids) throws IOException {
        keys(descriptor, "name", "id", "partition");
        String name = string(descriptor.get("name"), "[a-zA-Z0-9_.-]{1,128}");
        String id = string(descriptor.get("id"), "[a-zA-Z0-9_-]{1,64}");
        integer(descriptor.get("partition"), 0, 0);
        check(!name.equals(".") && !name.equals("..") && ids.add(id)
              && topics.putIfAbsent(name, new Topic(name, id, role)) == null, "topic_binding");
    }

    LifecycleManifest(JsonNode manifest) throws IOException {
        keys(manifest, "version", "archive_id", "common", "authority_public_key", "workers", "objects");
        check(VERSION.equals(manifest.get("version").asString()), "archive_profile");
        document = manifest;
        group = "detectbridge-lifecycle-archive-v1-" + uuid(manifest.get("archive_id"));
        JsonNode common = manifest.get("common");
        keys(common, "version", "deployment_id", "authority_id", "authority_key_sha256", "cluster_id",
             "runtime_sha256", "producer_sha256", "image", "compatibility_sha256", "limits", "validator", "topics");
        uuid(common.get("deployment_id"));
        uuid(common.get("authority_id"));
        cluster = string(common.get("cluster_id"), "[A-Za-z0-9_-]{1,128}");
        check("1.0.0".equals(common.get("version").asString())
              && RUNTIME.equals(common.get("runtime_sha256").asString())
              && PRODUCER.equals(common.get("producer_sha256").asString())
              && COMPATIBILITY.equals(common.get("compatibility_sha256").asString())
              && IMAGE.equals(common.get("image").asString()), "runtime_profile");
        byte[] publicKey = decode(manifest.get("authority_public_key"));
        check(publicKey != null && publicKey.length <= 64
              && Json.sha(publicKey).equals(common.get("authority_key_sha256").asString()), "authority_binding");
        try { KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(publicKey)); }
        catch (java.security.GeneralSecurityException e) { throw new Failure("authority_key"); }
        JsonNode validator = common.get("validator");
        keys(validator, "version", "artifact_sha256", "base_image", "image_id");
        string(validator.get("image_id"), "sha256:[0-9a-f]{64}");
        try (var stream = LifecycleManifest.class.getResourceAsStream("/lifecycle-runtime/v1/common.schema.json")) {
            var defs = Objects.requireNonNull(stream).readAllBytes();
            JsonNode schema = read(defs, MIB).get("$defs");
            check(common.get("limits").equals(schema.at("/limits/const"))
                  && validator.get("base_image").equals(schema.at("/validator/properties/base_image/const"))
                  && validator.get("version").equals(schema.at("/validator/properties/version/const"))
                  && COMPILER.equals(validator.get("artifact_sha256").asString()), "validator_or_limits");
        }
        Set<String> ids = new HashSet<>(), workers = new HashSet<>();
        JsonNode shared = common.get("topics");
        keys(shared, "control", "artifact", "ack", "output");
        for (String role : List.of("control", "artifact", "ack", "output")) topic(role, shared.get(role), ids);
        JsonNode inventory = manifest.get("workers");
        check(inventory.isArray() && !inventory.isEmpty() && inventory.size() <= 16, "worker_count");
        for (JsonNode worker : inventory) {
            keys(worker, "worker_id", "input_topic");
            check(workers.add(uuid(worker.get("worker_id"))), "duplicate_worker");
            topic("input", worker.get("input_topic"), ids);
        }
        JsonNode descriptors = manifest.get("objects");
        check(descriptors.isArray() && descriptors.size() <= 128, "object_count");
        for (JsonNode object : descriptors) {
            keys(object, "kind", "sha256");
            String sha = string(object.get("sha256"), "[a-f0-9]{64}");
            String kind = string(object.get("kind"), "original|provenance|registry|runtime|producer|validator");
            check(objects.putIfAbsent(sha, kind) == null, "duplicate_object");
        }
        for (String kind : List.of("runtime","producer","validator","registry"))
            check(Collections.frequency(objects.values(), kind) == 1, "missing_or_duplicate_" + kind);
        check("runtime".equals(objects.get(RUNTIME)) && "producer".equals(objects.get(PRODUCER))
              && "validator".equals(objects.get(COMPILER)) && objects.containsValue("provenance"), "artifact_pins");
    }

    void verifyObjects(Path dir) throws IOException {
        Store.contents(dir, objects.keySet());
        String registry = null;
        for (var entry : objects.entrySet()) {
            byte[] data = object(dir, entry.getKey());
            if (entry.getValue().equals("registry")) registry = entry.getKey();
        }
        byte[] data = object(dir, registry);
        JsonNode registration = read(data, MIB);
        keys(registration, "version", "objects");
        check(Arrays.equals(data, bytes(registration)) && "1.0.0".equals(registration.get("version").asString()), "registry_format");
        JsonNode members = registration.get("objects");
        check(members.isArray() && members.size() <= 128, "registry_limit");
        Set<String> registered = new HashSet<>();
        long total = 0;
        for (JsonNode member : members) {
            keys(member, "sha256", "size_bytes");
            String sha = string(member.get("sha256"), "[0-9a-f]{64}");
            long size = integer(member.get("size_bytes"), 1, 32L*MIB);
            check(registered.add(sha) && "original".equals(objects.get(sha))
                  && Files.size(dir.resolve(sha)) == size, "missing_original");
            total += size;
        }
        check(total <= 64L*MIB, "registry_limit");
    }

    byte[] object(Path dir, String sha) throws IOException {
        check(sha != null && objects.containsKey(sha), "unregistered_object");
        byte[] bytes = Store.bounded(dir.resolve(sha), 64*MIB);
        check(Json.sha(bytes).equals(sha), "object_integrity");
        return bytes;
    }
}
