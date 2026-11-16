package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.*;

import io.detectbridge.linux.Assembler;
import io.detectbridge.linux.Boundary;
import io.detectbridge.transport.Json;
import java.time.Clock;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

/** Pure checkpoint/outbox model. Staging is volatile; only completed snapshots release intents. */
public final class Machine {
  public static final int QUEUE_BYTES = 32 * 1024 * 1024, QUEUE_COUNT = 128;
  public static final int STATE_BYTES = 160 * 1024 * 1024 + 131072;
  public record Intent(long sequence, String kind, String key, JsonNode document) {
    public Intent { document = document.deepCopy(); }
    @Override public JsonNode document() { return document.deepCopy(); }
  }
  @FunctionalInterface public interface Emit { void emit(Intent intent) throws Exception; }
  @FunctionalInterface public interface Resolver { byte[] resolve(JsonNode raw) throws Exception; }
  private final Clock clock;
  private final Assembler.Limits limits;
  private final String binding;
  private final JsonNode source;
  private final Resolver resolver;
  private final io.detectbridge.detection.IntegrationOutputs integration;
  private final io.detectbridge.detection.Contracts contracts = new io.detectbridge.detection.Contracts();
  private ObjectNode state;
  private Assembler cachedCore;
  private final TreeMap<Long, Long> seals = new TreeMap<>();

  public Machine(Clock clock, Assembler.Limits limits, String binding, JsonNode source, Resolver resolver, io.detectbridge.detection.Evaluator evaluator) {
    check(binding.matches("[a-f0-9]{64}"), "invalid_runtime_binding");
    this.integration = new io.detectbridge.detection.IntegrationOutputs(evaluator, io.detectbridge.detection.IntegrationOutputs.RUNTIME_PIPELINE);
    this.clock = clock; this.limits = limits; this.binding = binding;
    this.source = source.deepCopy(); this.resolver = resolver;
    state = Json.MAPPER.createObjectNode(); state.put("version", "1.0.0"); state.put("binding", binding);
    state.set("assembler", parseState(new Assembler(clock, limits).snapshot()));
    ObjectNode windows = state.putObject("windows"); windows.putObject("runs"); windows.putObject("records");
    state.putArray("inbox"); state.putArray("outbox"); state.put("next_sequence", 0);
    state.put("retired_sequence", -1);state.put("received_offset", -1); state.put("received_hash", "");
  }
  public static byte[] inline(JsonNode raw) {
    var e = raw.get("evidence"); check(e.has("inline"), "registered_object_required");
    return e.get("encoding").asString().equals("utf-8")
        ? e.get("inline").asString().getBytes(java.nio.charset.StandardCharsets.UTF_8)
        : Base64.getDecoder().decode(e.get("inline").asString());
  }
  public static JsonNode parseState(byte[] bytes) {
    check(bytes.length <= STATE_BYTES, "integration_state_limit");
    BoundaryText.require(bytes);
    var factory = tools.jackson.core.json.JsonFactory.builder()
        .enable(tools.jackson.core.StreamReadFeature.STRICT_DUPLICATE_DETECTION)
        .streamReadConstraints(tools.jackson.core.StreamReadConstraints.builder()
            .maxNestingDepth(96).maxStringLength(4 * Json.MAX_VALUE).maxNumberLength(128).build()).build();
    JsonNode result = tools.jackson.databind.json.JsonMapper.builder(factory)
        .enable(tools.jackson.databind.DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build().readTree(bytes);
    io.detectbridge.detection.Normalized.unicode(result); return result;
  }
  public static String hash(JsonNode value) { return Json.sha(Json.bytes(canonical(value))); }
  private Assembler assembler() {
    if (cachedCore == null) cachedCore = Assembler.restore(clock, limits, Json.bytes(state.get("assembler")));
    return cachedCore;
  }
  private ArrayNode inbox() { return (ArrayNode) state.get("inbox"); }
  private ArrayNode outbox() { return (ArrayNode) state.get("outbox"); }
  public synchronized int pendingInputs() { return inbox().size(); }
  public synchronized int pendingOutputs() { return outbox().size(); }
  public synchronized int outboxBytes() { return Json.bytes(outbox()).length; }
  public synchronized int inboxBytes() { return Json.bytes(inbox()).length; }
  public synchronized long nextDeadline() { return assembler().nextDeadline(); }
  public synchronized int groupCount() { return state.at("/assembler/groups").size(); }
  public synchronized int closedCount() { return state.at("/assembler/closed").size(); }
  public synchronized int coreBytes() { return Json.bytes(state.get("assembler")).length; }
  public synchronized JsonNode coreState() { return state.get("assembler").deepCopy(); }

  public static JsonNode wire(byte[] value, String cluster, String topicId, String topic, long offset) {
    return Json.MAPPER.valueToTree(Map.of("input", Map.of("cluster_id", cluster, "topic_id", topicId,
        "topic", topic, "partition", 0, "offset", offset, "value_sha256", Json.sha(value == null ? new byte[0] : value)),
        "value_base64", value == null ? "" : Base64.getEncoder().encodeToString(value),
        "value_is_null", value == null));
  }
  private void validateWire(JsonNode wire) {
    Schemas.require("wire", wire);
    var input = wire.get("input");
    check(input.get("partition").isIntegralNumber() && input.get("offset").isIntegralNumber(),"integration_integer_required");
    for (String key : List.of("cluster_id", "topic_id", "topic")) check(input.get(key).equals(source.get(key)), "integration_input_destination");
    check(input.get("partition").asInt() == 0, "integration_input_partition");
    byte[] value = Base64.getDecoder().decode(wire.get("value_base64").asString());
    check(value.length <= 2 * Json.MAX_VALUE && Json.sha(value).equals(input.get("value_sha256").asString()), "integration_input_digest");
    check(!wire.get("value_is_null").asBoolean() || value.length == 0, "integration_null_input");
  }
  public synchronized void enqueue(JsonNode wire) {
    validateWire(wire);
    long offset = wire.at("/input/offset").asLong(); String digest = hash(wire);
    if (offset == state.get("received_offset").asLong()) {
      check(digest.equals(state.get("received_hash").asString()), "integration_input_conflict"); return;
    }
    check(offset == state.get("received_offset").asLong()+1, "integration_input_regression");
    ArrayNode next = inbox().deepCopy(); next.add(wire.deepCopy());
    check(next.size() <= QUEUE_COUNT && Json.bytes(next).length <= QUEUE_BYTES, "integration_inbox_backlog");
    state.set("inbox", next); state.put("received_offset", offset); state.put("received_hash", digest);
  }
  private static String kind(JsonNode output) {
    if (output.has("processing_id") && output.has("event")) return "tagged";
    if (output.has("detection_id")) return "detection";
    if (output.has("diagnostic_id")) return "processing";
    if (output.has("manifest_id")) return "manifest";
    if (output.has("preservation_id")) return "preservation";
    return output.path("kind").asString().equals("input_receipt") ? "receipt" : "quarantine";
  }
  private static String key(String kind, JsonNode output) {
    return output.get(switch(kind) {
      case "tagged" -> "processing_id";
      case "detection" -> "detection_id";
      case "processing" -> "diagnostic_id";
      case "manifest" -> "manifest_id";
      case "preservation" -> "preservation_id";
      default -> "id";
    }).asString();
  }
  private static JsonNode preservation(JsonNode diagnostic, String adapter, JsonNode source) {
    String id = io.detectbridge.detection.IntegrationOutputs.identity("detectbridge.p13.preservation/1", adapter, source, diagnostic);
    return Json.MAPPER.valueToTree(Map.of("version", "1.0.0", "preservation_id", id, "adapter", adapter,
        "source", source, "run_id", diagnostic.get("run_id"), "diagnostic", diagnostic));
  }
  private List<JsonNode> project(List<JsonNode> nativeOutputs, JsonNode windowsContext) {
    List<JsonNode> result = new ArrayList<>();
    for (JsonNode document : nativeOutputs) {
      if (document.has("@timestamp")) {
        JsonNode manifest = nativeOutputs.stream().filter(n -> n.has("manifest_id") && n.path("event_id").equals(document.at("/event/id"))).findFirst().orElse(null);
        JsonNode projected = windowsContext == null ? integration.process(document, manifest) : integration.process(document, manifest, windowsContext);
        result.add(projected.get("tagged")); projected.get("detections").forEach(result::add); projected.get("diagnostics").forEach(result::add);
      } else if (document.path("kind").asString().equals("quarantine") || document.has("manifest_id") || document.has("preservation_id")) result.add(document);
      else result.add(preservation(document, "linux", document.get("source")));
    }
    return result;
  }
  private void validateWindows(ObjectNode windows, JsonNode core) {
    check(windows.isObject() && windows.size() == 2 && windows.path("runs").isObject() && windows.path("records").isObject(), "integration_windows_state");
    Set<String> runs = new HashSet<>(); core.get("runs").propertyNames().forEach(runs::add);
    windows.get("runs").propertyNames().forEach(runs::add);
    check(runs.size() <= limits.runs() && windows.get("records").size() <= limits.closedKeys()
        && Json.bytes(windows).length <= limits.closedBytes(), "integration_windows_limit_backlog");
    for (var run : windows.get("runs").properties()) {
      java.util.UUID.fromString(run.getKey());
      check(Set.of("active", "ended").contains(run.getValue().asString()), "integration_windows_state");
    }
    for (var receipt : windows.get("records").properties())
      check(receipt.getKey().matches("[a-f0-9]{64}") && receipt.getValue().isString() && receipt.getValue().asString().matches("[a-f0-9]{64}"), "integration_windows_state");
  }
  static String transportId(String binding,JsonNode input,String category) {
    return Json.identity(List.of(binding,input.get("cluster_id").asString(),input.get("topic_id").asString(),
        input.get("partition").asInt(),input.get("offset").asLong(),input.get("value_sha256").asString(),category));
  }
  private JsonNode receipt(JsonNode wire, JsonNode row) {
    var input = wire.get("input");
    ObjectNode doc = Json.MAPPER.createObjectNode(); doc.put("version", "1.0.0");
    doc.put("id", transportId(binding,input,"receipt")); doc.set("input", input.deepCopy());
    doc.put("kind", "input_receipt"); doc.put("action", row.get("kind").asString());
    if (row.has("raw")) doc.put("record_id", row.at("/raw/record_id").asString());
    return doc;
  }
  private JsonNode quarantine(JsonNode wire) {
    var input = wire.get("input");
    return Json.MAPPER.valueToTree(Map.of("version", "1.0.0", "id", transportId(binding,input,"invalid_input"),
        "kind", "quarantine", "category", "invalid_integration_input", "input", input,
        "value_is_null", wire.get("value_is_null").asBoolean(),
        "value_size", Base64.getDecoder().decode(wire.get("value_base64").asString()).length));
  }
  /** One bounded transition only. False means no work or waiting for durable outbox capacity. */
  public synchronized boolean pump() throws Exception {
    Assembler core = assembler(); Assembler.Prepared prepared;
    JsonNode wire = inbox().isEmpty() ? null : inbox().get(0), row = null;
    List<JsonNode> outputs = new ArrayList<>(); boolean consumed = false;
    ObjectNode windows = ((ObjectNode) state.get("windows")).deepCopy();
    JsonNode windowsContext = null;
    if (core.nextDeadline() <= clock.millis()) {
      prepared = core.prepareTick(); outputs.addAll(prepared.outputs());
    } else if (wire == null) return false;
    else {
      try {
        check(!wire.get("value_is_null").asBoolean(), "null_input");
        row = Json.read(Base64.getDecoder().decode(wire.get("value_base64").asString()));
        Schemas.require("input", row);
        switch (row.get("kind").asString()) {
          case "record" -> {
            var raw = row.get("raw"); var input = Boundary.resolve(raw, row.get("context"), e -> resolver.resolve(raw));
            if (row.at("/context/parser/id").asString().equals("openssh-password")) {
              prepared = core.prepareAuthentication(input);
            } else prepared = core.prepare(input);
          }
          case "windows_record" -> {
            var raw = row.get("raw"); var context = row.get("context");
            var adapted = new io.detectbridge.windows.WindowsAdapter().adapt(raw, r -> {
              try { return resolver.resolve(r); }
              catch (java.io.IOException io) { throw io; }
              catch (IllegalArgumentException bad) { throw new io.detectbridge.windows.EvidenceResolver.IntegrityFailure(); }
              catch (Exception failure) { throw new java.io.IOException("integration_evidence_unavailable", failure); }
            }, context);
            String run = context.get("run_id").asString();
            ObjectNode semanticContext = ((ObjectNode) context).deepCopy(); semanticContext.remove("receipt");
            String occurrence = hash(Json.MAPPER.valueToTree(List.of(run, raw.get("record_id"))));
            String fingerprint = hash(Json.MAPPER.valueToTree(List.of(raw, semanticContext)));
            JsonNode previous = windows.path("records").get(occurrence);
            if (previous != null) check(previous.asString().equals(fingerprint), "conflicting_redelivery");
            else {
              JsonNode diagnostic = adapted.diagnostic();
              if (windows.path("runs").path(run).asString().equals("ended") || coreState().path("runs").path(run).asString().equals("ended")) {
                diagnostic = Json.MAPPER.valueToTree(Map.of("version", "1.0.0", "run_id", run, "record_id", raw.get("record_id"), "code", "after_dataset_end", "evidence_sha256", raw.at("/evidence/sha256")));
              }
              if (diagnostic != null) outputs.add(preservation(diagnostic, "windows", raw.get("source")));
              else { outputs.add(adapted.event()); windowsContext = context; }
              ((ObjectNode) windows.get("runs")).putIfAbsent(run, Json.MAPPER.stringNode("active"));
              ((ObjectNode) windows.get("records")).put(occurrence, fingerprint);
            }
            prepared = new Assembler.Prepared(core.snapshot(), List.of(), true);
          }
          case "run_end" -> {
            check(coreState().get("runs").has(row.get("run_id").asString()) || windows.get("runs").has(row.get("run_id").asString()), "unknown_control_run");
            if (windows.get("runs").has(row.get("run_id").asString())) ((ObjectNode) windows.get("runs")).put(row.get("run_id").asString(), "ended");
            if (coreState().get("runs").has(row.get("run_id").asString())) prepared = core.prepareEnd(row.get("run_id").asString());
            else {
              ObjectNode ended = (ObjectNode) parseState(core.snapshot());
              ((ObjectNode) ended.get("runs")).put(row.get("run_id").asString(), "ended");
              prepared = new Assembler.Prepared(Json.bytes(ended), List.of(), true);
            }
          }
          case "source_boundary" -> prepared = core.prepareBoundary(row.get("run_id").asString(),
              row.at("/source/namespace").asString(), row.at("/source/instance").asString(),
              row.get("host_id").asString(), row.get("generation").asString());
          default -> throw new IllegalArgumentException("unknown_input");
        }
        outputs.addAll(prepared.outputs()); consumed = prepared.consumed();

      } catch (IllegalArgumentException invalid) {
        String category = invalid.getMessage();
        if (category != null && (category.endsWith("backlog") || category.equals("conflicting_redelivery"))) throw invalid;
        windows = ((ObjectNode) state.get("windows")).deepCopy(); windowsContext = null;
        outputs.clear(); outputs.add(quarantine(wire)); consumed = true;
        prepared = new Assembler.Prepared(core.snapshot(), List.of(), true);
      }
    }
    outputs = new ArrayList<>(project(outputs, windowsContext));
    if (consumed && row != null && !outputs.stream().anyMatch(o -> o.path("kind").asString().equals("quarantine"))) outputs.add(receipt(wire, row));
    validateWindows(windows, parseState(prepared.nextSnapshot()));
    ArrayNode nextOut = outbox().deepCopy(); long sequence = state.get("next_sequence").asLong();
    for (JsonNode output : outputs) {
      String type = kind(output);
      validateDocument(type, output);
      nextOut.add(Json.MAPPER.valueToTree(Map.of("sequence", sequence, "kind", type, "key", key(type, output), "document", output)));
      sequence = Math.addExact(sequence, 1);
    }
    check(outputs.size() <= QUEUE_COUNT && Json.bytes(outputs).length <= QUEUE_BYTES, "integration_proposal_limit_backlog");
    if (nextOut.size() > QUEUE_COUNT || Json.bytes(nextOut).length > QUEUE_BYTES) return false;
    state.set("windows", windows); state.set("assembler", parseState(prepared.nextSnapshot())); cachedCore = null; state.set("outbox", nextOut);
    state.put("next_sequence", sequence); if (consumed) inbox().remove(0);
    return true;
  }
  private void validateDocument(String kind, JsonNode document) {
    check(Json.bytes(document).length <= 2 * Json.MAX_VALUE, "integration_output_limit_backlog");
    switch(kind) {
      case "tagged", "detection", "processing" -> {
        check(document.path("version").asString().equals("1.1.0"), "integration_output_version");
        contracts.require("integration", kind.equals("tagged") ? "tagged-event" : kind.equals("processing") ? "diagnostic" : "detection", document);
      }
      case "manifest" -> Schemas.linux("manifest", document);
      case "preservation" -> {
        Schemas.require("preservation", document);
        check(preservation(document.get("diagnostic"), document.get("adapter").asString(), document.get("source")).equals(document), "integration_preservation_identity");
        if (document.get("adapter").asString().equals("linux")) Schemas.linux("preservation", document.get("diagnostic"));
      }
      case "receipt", "quarantine" -> Schemas.require(kind, document);
      default -> throw new IllegalArgumentException("invalid_outbox_kind");
    }
  }
  public synchronized byte[] snapshot(long checkpoint) {
    check(checkpoint >= 0, "invalid_checkpoint");
    seals.put(checkpoint, state.get("next_sequence").asLong() - 1);
    // Flink is configured for one concurrent checkpoint; retain at most current and predecessor seals.
    while (seals.size() > 2) seals.pollFirstEntry();
    ObjectNode envelope = state.deepCopy(); envelope.put("sha256", hash(state));
    byte[] bytes = Json.bytes(envelope); check(bytes.length <= STATE_BYTES, "integration_state_limit"); return bytes;
  }
  /** Qualification evidence only, never a recovery source. No original bodies are copied. */
  public synchronized JsonNode inventory(long checkpoint, byte[] snapshot) {
    ObjectNode result=Json.MAPPER.createObjectNode(); result.put("version","1.0.0");result.put("checkpoint_id",checkpoint);
    result.put("binding",binding);result.put("snapshot_sha256",Json.sha(snapshot));result.put("received_offset",state.get("received_offset").asLong());
    ArrayNode groups=result.putArray("groups");
    for(JsonNode group:state.at("/assembler/groups")) {
      ObjectNode item=groups.addObject();item.set("key",group.get("key"));ArrayNode members=item.putArray("members");
      for(JsonNode member:group.get("members")) members.add(Json.MAPPER.valueToTree(Map.of("record_id",member.at("/raw/record_id").asString(),
          "evidence_sha256",member.at("/raw/evidence/sha256").asString(),"raw_sha256",hash(member.get("raw")),"context_sha256",hash(member.get("context")))));
    }
    ArrayNode pending=result.putArray("inbox");for(JsonNode wire:inbox())pending.add(wire.get("input"));
    ArrayNode intents=result.putArray("outbox");
    for(JsonNode intent:outbox()) {
      ObjectNode item=intents.addObject();item.put("sequence",intent.get("sequence").asLong());item.set("kind",intent.get("kind"));item.set("key",intent.get("key"));
      JsonNode doc=intent.get("document");item.put("document_sha256",Json.sha(Json.bytes(canonical(doc))));
      String run=doc.has("event")?doc.at("/event/detectbridge/run_id").asString():doc.at("/detectbridge/run_id").asString();if(run.isEmpty())run=doc.has("manifest_id")?doc.at("/key/run_id").asString():doc.path("run_id").asString();item.put("run_id",run);
      if(doc.has("input"))item.set("input",doc.get("input"));
      ArrayNode refs=item.putArray("members");
      JsonNode originals=doc.has("event")?doc.at("/event/detectbridge/evidence"):doc.path("members");
      for(JsonNode original:originals) refs.add(Json.MAPPER.valueToTree(Map.of("record_id",original.get("record_id").asString(),
          "evidence_sha256",original.has("evidence")?original.at("/evidence/sha256").asString():original.get("evidence_sha256").asString())));
      if(doc.has("member"))refs.add(Json.MAPPER.valueToTree(Map.of("record_id",doc.at("/member/record_id").asString(),"evidence_sha256",doc.at("/member/evidence_sha256").asString())));
    }
    return result;
  }
  public synchronized void abort(long checkpoint) { seals.remove(checkpoint); }
  public synchronized void complete(long checkpoint, Emit emit) throws Exception {
    Long through = seals.get(checkpoint); if (through == null) return;
    release(through, emit); seals.headMap(checkpoint, true).clear();
  }
  private void release(long through, Emit emit) throws Exception {
    int count = 0;
    for (JsonNode intent : outbox()) {
      if (intent.get("sequence").asLong() > through) break;
      emit.emit(new Intent(intent.get("sequence").asLong(), intent.get("kind").asString(),
          intent.get("key").asString(), intent.get("document"))); count++;
    }
    for (int i = 0; i < count; i++) {state.put("retired_sequence",outbox().get(0).get("sequence").asLong());outbox().remove(0); }
  }
  public synchronized void releaseRestored(Emit emit) throws Exception { release(Long.MAX_VALUE, emit); }
  public static Machine restore(Clock clock, Assembler.Limits limits, String binding, JsonNode source, Resolver resolver, io.detectbridge.detection.Evaluator evaluator, byte[] bytes) {
    JsonNode envelope = parseState(bytes); Schemas.require("state", envelope);
    ObjectNode unhashed = ((ObjectNode) envelope).deepCopy(); String digest = unhashed.remove("sha256").asString();
    check(hash(unhashed).equals(digest) && unhashed.get("binding").asString().equals(binding), "incompatible_integration_restore");
    for(String counter:List.of("next_sequence","received_offset","retired_sequence"))check(unhashed.get(counter).isIntegralNumber(),"integration_integer_required");
    Machine machine = new Machine(clock, limits, binding, source, resolver, evaluator); machine.state = unhashed;
    machine.assembler(); machine.validateWindows((ObjectNode) unhashed.get("windows"), unhashed.get("assembler"));
    check(machine.inbox().size() <= QUEUE_COUNT && machine.inboxBytes() <= QUEUE_BYTES
        && machine.outbox().size() <= QUEUE_COUNT && machine.outboxBytes() <= QUEUE_BYTES, "integration_queue_limit");
    long previous = -1;
    for (JsonNode wire : machine.inbox()) {
      machine.validateWire(wire); long offset = wire.at("/input/offset").asLong();
      check(offset > previous && offset <= unhashed.get("received_offset").asLong(), "integration_input_order"); previous = offset;
    }
    previous = unhashed.get("retired_sequence").asLong();
    for (JsonNode intent : machine.outbox()) {
      long sequence = intent.get("sequence").asLong(); String kind = intent.get("kind").asString();
      check(intent.get("sequence").isIntegralNumber() && sequence == previous+1 && sequence < unhashed.get("next_sequence").asLong(), "integration_intent_order");
      machine.validateDocument(kind, intent.get("document"));
      check(key(kind, intent.get("document")).equals(intent.get("key").asString()), "integration_intent_key"); previous = sequence;
    }
    check(previous+1==unhashed.get("next_sequence").asLong(),"integration_retirement_order");
    return machine;
  }
  private static final class BoundaryText {
    static void require(byte[] bytes) {
      try { java.nio.charset.StandardCharsets.UTF_8.newDecoder()
          .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)); }
      catch (java.nio.charset.CharacterCodingException invalid) { throw new IllegalArgumentException("invalid_state_encoding"); }
    }
  }
}
