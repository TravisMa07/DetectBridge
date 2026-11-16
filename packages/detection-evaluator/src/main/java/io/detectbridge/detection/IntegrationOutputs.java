package io.detectbridge.detection;

import static io.detectbridge.detection.Contracts.*;

import io.detectbridge.transport.Json;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** P13a deterministic offline projection. No Kafka, lookup, clock or evidence resolver. */
public final class IntegrationOutputs {
  public static final String PIPELINE = "p13-offline/1.0.0";
  private static final JsonNode POLICY = Json.MAPPER.valueToTree(Map.of(
      "id", "coverage-and-rule-metadata", "version", "1.0.0",
      "tags", List.of("nonzero-coverage-in-outcome-order", "quality-eligibility"),
      "rule_metadata", "plan-without-yaml-and-expression", "external_inputs", List.of()));
  private final Evaluator evaluator;
  private final JsonNode plan;
  private final Contracts contracts = new Contracts();

  public IntegrationOutputs(Evaluator evaluator) {
    evaluator.requireMappedDeployment(); this.evaluator = evaluator; this.plan = evaluator.planSnapshot();
  }

  public static String identity(String domain, Object... parts) {
    List<Object> preimage = new ArrayList<>(); preimage.add(domain); preimage.addAll(Arrays.asList(parts));
    return "sha256:" + hash(Json.MAPPER.valueToTree(preimage));
  }
  private static String hash(JsonNode node) { return Json.sha(Json.bytes(canonical(node))); }

  /** Semantic projection excludes receipt clocks while the published P03 event stays intact. */
  static ObjectNode semanticEvent(JsonNode event) {
    ObjectNode result = ((ObjectNode) event).deepCopy();
    ((ObjectNode) result.get("event")).remove("ingested");
    ObjectNode time = (ObjectNode) result.at("/detectbridge/time");
    time.remove("received"); time.remove("processed");
    JsonNode linuxContext = result.at("/detectbridge/extensions/linux.context/context");
    if (linuxContext.isObject()) ((ObjectNode) linuxContext).remove("receipt");
    return result;
  }

  public JsonNode process(JsonNode event, JsonNode manifest) {
    return process(event, manifest, adapterContext(event));
  }

  private static JsonNode adapterContext(JsonNode event) {
    JsonNode context = event.at("/detectbridge/extensions/linux.context/context");
    return context.isObject() ? context : null;
  }

  public JsonNode process(JsonNode event, JsonNode manifest, JsonNode context) {
    check(Json.bytes(event).length <= 1024 * 1024, "integration_event_limit");
    JsonNode compact = evaluator.evaluateCompact(Json.bytes(event));
    return outputs(event, manifest, compact, context);
  }

  /** Consumer verification requires the pinned plan and original audit manifest. */
  public void verify(JsonNode integration, JsonNode manifest) {
    verify(integration, manifest, adapterContext(integration.path("tagged").path("event")));
  }

  public void verify(JsonNode integration, JsonNode manifest, JsonNode context) {
    JsonNode expected = process(integration.path("tagged").path("event"), manifest, context);
    check(canonical(expected).equals(canonical(integration)), "integration_content_mismatch");
  }

  /** Canonical content comparison for duplicate/conflict consumers; no physical input locations. */
  public static String contentHash(JsonNode integration) {
    ObjectNode semantic = ((ObjectNode) integration).deepCopy();
    ObjectNode tagged = (ObjectNode) semantic.get("tagged");
    tagged.set("event", semanticEvent(tagged.get("event")));
    semanticManifestReference(tagged);
    for (var detection : semantic.get("detections")) semanticManifestReference((ObjectNode) detection);
    return hash(semantic);
  }

  private static void semanticManifestReference(ObjectNode document) {
    JsonNode reference = document.get("manifest");
    if (reference != null && !reference.isNull())
      document.set("manifest", Json.MAPPER.valueToTree(Map.of("semantic_sha256", reference.get("semantic_sha256"))));
  }

  private static String manifestSemanticHash(JsonNode manifest) {
    ObjectNode semantic = ((ObjectNode) manifest).deepCopy(); semantic.remove("manifest_id");
    // P12 context hashes include receipt clocks. The original hash remains in the retrieval link.
    // Source/mapping, scope provenance, policy, quality and exact raw/evidence membership stay bound.
    for (var member : semantic.get("members")) ((ObjectNode) member).remove("context_sha256");
    return hash(semantic);
  }

  JsonNode outputs(JsonNode input, JsonNode manifest, JsonNode compact) {
    return outputs(input, manifest, compact, adapterContext(input));
  }

  private JsonNode outputs(JsonNode input, JsonNode manifest, JsonNode compact, JsonNode adapterContext) {
    ObjectNode event = ((ObjectNode) input).deepCopy();
    JsonNode db = event.get("detectbridge");
    JsonNode source = null, mapping = null;
    for (var candidate : plan.get("sources"))
      if (candidate.get("id").equals(db.at("/source_contract/id"))
          && candidate.get("version").equals(db.at("/source_contract/version"))) source = candidate;
    if (source != null) for (var candidate : plan.get("mapping_profiles"))
      if (candidate.get("source").get("id").equals(source.get("id"))
          && candidate.get("source").get("version").equals(source.get("version"))) mapping = candidate;
    JsonNode decisionContext = null;
    if (adapterContext != null && !adapterContext.isNull()) {
      check(Set.of("1.0.0", "1.1.0").contains(adapterContext.path("version").asString())
          && adapterContext.path("run_id").equals(db.get("run_id"))
          && adapterContext.path("source").equals(db.get("source")), "integration_context_binding");
      JsonNode actualSource = adapterContext.at("/source_contract/snapshot"), actualMapping = adapterContext.at("/mapping_profile/declaration");
      check(actualSource.path("id").equals(db.at("/source_contract/id"))
          && actualSource.path("version").equals(db.at("/source_contract/version"))
          && hash(actualSource).equals(adapterContext.at("/source_contract/sha256").asString())
          && (source == null || source.equals(actualSource))
          && (mapping == null || mapping.equals(actualMapping))
          && (adapterContext.at("/parser/id").asString() + "/" + adapterContext.at("/parser/version").asString()).equals(db.at("/processing/parser").asString()), "integration_context_attribution");
      ObjectNode mappingBody = ((ObjectNode) actualMapping).deepCopy(); mappingBody.remove("sha256");
      check(hash(mappingBody).equals(actualMapping.path("sha256").asString())
          && actualMapping.at("/source/id").equals(actualSource.get("id"))
          && actualMapping.at("/source/version").equals(actualSource.get("version"))
          && actualMapping.at("/source/sha256").asString().equals(hash(actualSource)), "integration_context_mapping");
      ObjectNode semanticContext = ((ObjectNode) adapterContext).deepCopy(); semanticContext.remove("receipt");
      decisionContext = semanticContext;
      source = actualSource; mapping = actualMapping;
    }
    var attribution = Json.MAPPER.createObjectNode();
    if (decisionContext == null) attribution.putNull("context_sha256");
    else attribution.put("context_sha256", hash(decisionContext));
    attribution.put("pipeline", PIPELINE); attribution.put("bundle_sha256", evaluator.bundle());
    attribution.set("source", db.get("source"));
    var sourceRef = ((ObjectNode) db.get("source_contract")).deepCopy();
    if (source == null) sourceRef.putNull("sha256"); else sourceRef.put("sha256", hash(source));
    attribution.set("source_contract", sourceRef);
    if (mapping == null) attribution.putNull("mapping_profile");
    else {
      check(db.at("/processing/mapping").asString().equals(mapping.get("id").asString() + "/" + mapping.get("version").asString()), "integration_mapping_binding");
      attribution.set("mapping_profile", Json.MAPPER.valueToTree(Map.of("id", mapping.get("id"), "version", mapping.get("version"), "sha256", mapping.get("sha256"))));
    }
    attribution.set("processing", db.get("processing"));
    for (String key : List.of("compiler", "evaluator", "mapping_version")) attribution.set(key, plan.get(key));
    attribution.put("selector", Evaluator.SELECTION_VERSION);
    attribution.put("mapping_sha256", hash(plan.get("mapping_profiles")));
    attribution.set("enrichment", Json.MAPPER.valueToTree(Map.of("id", POLICY.get("id"), "version", POLICY.get("version"), "sha256", hash(POLICY))));
    attribution.putArray("external_inputs");
    JsonNode manifestRef = Json.MAPPER.nullNode();
    if (!db.at("/assembly/mode").asString().equals("standalone")) {
      check(manifest != null && manifest.isObject(), "integration_manifest_required");
      check(manifest.path("version").asString().equals("1.0.0")
          && manifest.path("assembler").asString().equals("linux-audit/1.0.0")
          && manifest.path("policy").asString().equals("execution-evidence/1.0.0"), "integration_manifest_version");
      JsonNode extension = db.at("/extensions/linux.context"), context = extension.path("context");
      check(manifest.path("closure").equals(db.at("/assembly/closure"))
          && manifest.path("eligible").isBoolean()
          && manifest.path("eligible").asBoolean() == db.at("/quality/eligibility").asString().equals("eligible")
          && manifest.path("findings").equals(extension.path("findings"))
          && manifest.at("/scope_provenance/host_binding").equals(context.path("host_binding"))
          && manifest.at("/scope_provenance/source_generation").equals(context.path("source_generation"))
          && manifest.at("/members/0/context_sha256").asString().equals(hash(context)), "integration_manifest_context");
      ObjectNode unhashed = ((ObjectNode) manifest).deepCopy(); unhashed.remove("manifest_id");
      check(manifest.path("manifest_id").asString().equals("sha256:" + hash(unhashed)), "integration_manifest_hash");
      check(manifest.path("event_id").equals(event.at("/event/id"))
          && manifest.at("/key/run_id").equals(db.get("run_id"))
          && manifest.at("/key/source").equals(db.get("source"))
          && manifest.path("source_sha256").equals(sourceRef.get("sha256"))
          && mapping != null && manifest.path("mapping_sha256").equals(mapping.get("sha256")), "integration_manifest_binding");
      Map<String, String> members = new TreeMap<>(), evidence = new TreeMap<>();
      for (var member : manifest.path("members"))
        check(members.put(member.path("record_id").asString(), member.path("evidence_sha256").asString()) == null, "integration_duplicate_member");
      for (var member : db.get("evidence")) evidence.put(member.get("record_id").asString(), member.at("/evidence/sha256").asString());
      check(members.equals(evidence), "integration_manifest_members");
      manifestRef = Json.MAPPER.valueToTree(Map.of("manifest_id", manifest.get("manifest_id"), "sha256", hash(manifest), "semantic_sha256", manifestSemanticHash(manifest)));
    } else check(manifest == null || manifest.isNull(), "integration_unexpected_manifest");
    String eventId = event.at("/event/id").asString(), runId = db.get("run_id").asString();
    String processingId = identity("detectbridge.p13.processing/1", PIPELINE, runId, eventId, hash(semanticEvent(event)), attribution,
        manifestRef.isNull() ? null : Map.of("semantic_sha256", manifestRef.get("semantic_sha256")));
    ObjectNode result = Json.MAPPER.createObjectNode();
    ObjectNode tagged = result.putObject("tagged"); tagged.put("version", "1.0.0");
    tagged.put("processing_id", processingId); tagged.set("event", event); tagged.set("attribution", attribution);
    tagged.set("manifest", manifestRef); tagged.set("counts", compact.get("counts"));
    var links = tagged.putArray("matches"); var detections = result.putArray("detections");
    for (var match : compact.get("matched")) {
      String detectionId = identity("detectbridge.p13.detection/1", processingId, match.get("id"), match.get("revision"));
      ObjectNode link = ((ObjectNode) match).deepCopy(); link.put("detection_id", detectionId); links.add(link);
      ObjectNode detection = detections.addObject();
      base(detection, processingId, eventId, runId, attribution);
      detection.put("detection_id", detectionId); detection.set("manifest", manifestRef);
      for (var rule : plan.get("rules")) if (rule.get("id").equals(match.get("id"))) {
        ObjectNode metadata = ((ObjectNode) rule).deepCopy(); metadata.remove("yaml"); metadata.remove("expression");
        detection.set("rule", metadata);
      }
      require("detection", detection, 128 * 1024);
    }
    var tags = tagged.putArray("tags");
    for (String outcome : Evaluator.OUTCOMES) if (compact.get("counts").get(outcome).asInt() > 0) tags.add("coverage:" + outcome);
    tags.add("quality:" + db.at("/quality/eligibility").asString());
    var diagnostics = result.putArray("diagnostics");
    for (var group : compact.get("diagnostics")) {
      ObjectNode diagnostic = diagnostics.addObject(); base(diagnostic, processingId, eventId, runId, attribution);
      diagnostic.set("category", group.get("category")); diagnostic.set("rule_set", group.get("rule_set"));
      diagnostic.put("diagnostic_id", identity("detectbridge.p13.diagnostic/1", processingId, group.get("category"), group.at("/rule_set/sha256")));
      require("diagnostic", diagnostic, 32 * 1024);
    }
    require("tagged-event", tagged, 2 * 1024 * 1024);
    check(Json.bytes(result).length <= 16 * 1024 * 1024, "integration_output_limit");
    return result;
  }

  private static void base(ObjectNode node, String processing, String event, String run, JsonNode attribution) {
    node.put("version", "1.0.0"); node.put("processing_id", processing); node.put("event_id", event);
    node.put("run_id", run); node.set("attribution", attribution);
  }
  private void require(String kind, JsonNode document, int limit) {
    check(Json.bytes(document).length <= limit, "integration_document_limit");
    contracts.require("integration", kind, document);
  }
}
