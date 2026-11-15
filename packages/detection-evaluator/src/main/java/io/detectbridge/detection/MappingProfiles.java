package io.detectbridge.detection;

import static io.detectbridge.detection.Contracts.*;

import io.detectbridge.transport.Json;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** Reviewed declarations only; no transform is executed by the evaluator. */
final class MappingProfiles {
  private static final Map<String, String> TARGETS = Map.of(
      "Image", "process.executable", "CommandLine", "process.command_line",
      "ProcessId", "process.pid", "User", "user.name");
  private static final Map<String, String> TRANSFORMS = Map.of(
      "identity-string/1.0.0", "string", "windows-account/1.0.0", "string",
      "decimal-integer/1.0.0", "integer", "hex-integer/1.0.0", "integer");
  private final Map<String, Set<String>> unsupported = new HashMap<>();
  private final Map<String, Set<String>> required = new HashMap<>();
  final String hash;

  MappingProfiles(JsonNode plan, Map<String, JsonNode> sources) {
    hash = Json.sha(Json.bytes(canonical(plan.get("mapping_profiles"))));
    Set<String> ids = new HashSet<>();
    for (var profile : plan.get("mapping_profiles")) {
      JsonNode ref = profile.get("source");
      String key = ref.get("id").asString() + "/" + ref.get("version").asString();
      JsonNode source = sources.get(key);
      check(source != null && ids.add(profile.get("id").asString()), "mapping_source_set");
      check(!unsupported.containsKey(key), "duplicate_mapping_source");
      check(Json.sha(Json.bytes(canonical(source))).equals(ref.get("sha256").asString()),
          "mapping_source_hash");
      ObjectNode unhashed = ((ObjectNode) profile).deepCopy();
      unhashed.remove("sha256");
      check(Json.sha(Json.bytes(canonical(unhashed))).equals(profile.get("sha256").asString()),
          "mapping_hash");
      Set<String> aliases = new HashSet<>(), blocked = new HashSet<>();
      for (var field : profile.get("fields")) {
        String alias = field.get("alias").asString(), target = field.get("target").asString();
        check(aliases.add(alias) && target.equals(TARGETS.get(alias)), "mapping_alias_target");
        String type = alias.equals("ProcessId") ? "integer" : "string";
        check(type.equals(field.get("type").asString())
            && type.equals(TRANSFORMS.get(field.get("transform").asString()))
            && (!field.get("transform").asString().equals("windows-account/1.0.0")
                || alias.equals("User")), "mapping_type");
        if (field.get("capability").asString().equals("unsupported")) {
          check(!field.has("source_path"), "unsupported_mapping_path");
          blocked.add(target);
        } else {
          int declarations = 0;
          for (var m : source.get("mappings"))
            if (m.get("target_path").equals(field.get("target"))
                && m.get("source_path").equals(field.path("source_path"))) {
              check(m.get("capability").equals(field.get("capability")), "mapping_capability");
              declarations++;
            }
          check(declarations == 1, "mapping_declaration");
        }
      }
      check(aliases.equals(TARGETS.keySet()), "mapping_alias_set");
      unsupported.put(key, Set.copyOf(blocked));
    }
    check(unsupported.keySet().equals(sources.keySet()), "mapping_source_set");
    for (var rule : plan.get("rules")) {
      Set<String> fields = new HashSet<>();
      collect(rule.get("expression"), fields);
      required.put(rule.get("id").asString(), Set.copyOf(fields));
      JsonNode provenance = rule.get("provenance");
      check(provenance.get("rule_id").equals(rule.get("id"))
          && provenance.get("revision").equals(rule.get("revision")), "candidate_identity");
      String current = provenance.get("original_sha256").asString();
      for (var change : provenance.get("modifications")) {
        check(change.get("input_sha256").asString().equals(current)
            && !change.get("output_sha256").asString().equals(current), "candidate_lineage");
        current = change.get("output_sha256").asString();
      }
      check(current.equals(rule.get("revision").asString()), "candidate_lineage");
      check(!provenance.get("kind").asString().equals("synthetic")
          || provenance.get("license").asString().equals("Apache-2.0"), "synthetic_license");
    }
  }

  private static void collect(JsonNode node, Set<String> fields) {
    switch (node.get("op").asString()) {
      case "and", "or" -> { for (var arg : node.get("args")) collect(arg, fields); }
      case "not" -> collect(node.get("arg"), fields);
      default -> fields.add(node.get("field").asString());
    }
  }

  boolean blocked(JsonNode source, JsonNode rule) {
    String key = source.get("id").asString() + "/" + source.get("version").asString();
    return !Collections.disjoint(unsupported.get(key), required.get(rule.get("id").asString()));
  }
}
