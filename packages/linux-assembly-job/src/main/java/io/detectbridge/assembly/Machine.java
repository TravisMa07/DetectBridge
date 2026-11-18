package io.detectbridge.assembly;

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
  public static final int QUEUE_BYTES = 8 * 1024 * 1024, QUEUE_COUNT = 64;
  public static final int STATE_BYTES = 80 * 1024 * 1024 + 131072;
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
  private ObjectNode state;
  private Assembler cachedCore;
  private final TreeMap<Long, Long> seals = new TreeMap<>();

  public Machine(Clock clock, Assembler.Limits limits, String binding, JsonNode source, Resolver resolver) {
    check(binding.matches("[a-f0-9]{64}"), "invalid_runtime_binding");
    this.clock = clock; this.limits = limits; this.binding = binding;
    this.source = source.deepCopy(); this.resolver = resolver;
    state = Json.MAPPER.createObjectNode(); state.put("version", "1.0.0"); state.put("binding", binding);
    state.set("assembler", parseState(new Assembler(clock, limits).snapshot()));
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
    check(bytes.length <= STATE_BYTES, "assembly_state_limit");
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
    check(input.get("partition").isIntegralNumber() && input.get("offset").isIntegralNumber(),"assembly_integer_required");
    for (String key : List.of("cluster_id", "topic_id", "topic")) check(input.get(key).equals(source.get(key)), "assembly_input_destination");
    check(input.get("partition").asInt() == 0, "assembly_input_partition");
    byte[] value = Base64.getDecoder().decode(wire.get("value_base64").asString());
    check(value.length <= 2 * Json.MAX_VALUE && Json.sha(value).equals(input.get("value_sha256").asString()), "assembly_input_digest");
    check(!wire.get("value_is_null").asBoolean() || value.length == 0, "assembly_null_input");
  }
  public synchronized void enqueue(JsonNode wire) {
    validateWire(wire);
    long offset = wire.at("/input/offset").asLong(); String digest = hash(wire);
    if (offset == state.get("received_offset").asLong()) {
      check(digest.equals(state.get("received_hash").asString()), "assembly_input_conflict"); return;
    }
    check(offset == state.get("received_offset").asLong()+1, "assembly_input_regression");
    ArrayNode next = inbox().deepCopy(); next.add(wire.deepCopy());
    check(next.size() <= QUEUE_COUNT && Json.bytes(next).length <= QUEUE_BYTES, "assembly_inbox_backlog");
    state.set("inbox", next); state.put("received_offset", offset); state.put("received_hash", digest);
  }
  private static String kind(JsonNode output) {
    return output.has("@timestamp") ? "event" : output.has("manifest_id") ? "manifest" : "diagnostic";
  }
  private static String key(String kind, JsonNode output) {
    return switch(kind) {
      case "event" -> output.at("/event/id").asString();
      case "manifest" -> output.get("manifest_id").asString();
      default -> output.get("id").asString();
    };
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
        "kind", "quarantine", "category", "invalid_assembly_input", "input", input,
        "value_is_null", wire.get("value_is_null").asBoolean(),
        "value_size", Base64.getDecoder().decode(wire.get("value_base64").asString()).length));
  }
  /** One bounded transition only. False means no work or waiting for durable outbox capacity. */
  public synchronized boolean pump() throws Exception {
    Assembler core = assembler(); Assembler.Prepared prepared;
    JsonNode wire = inbox().isEmpty() ? null : inbox().get(0), row = null;
    List<JsonNode> outputs = new ArrayList<>(); boolean consumed = false;
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
          case "run_end" -> {
            check(coreState().get("runs").has(row.get("run_id").asString()), "unknown_control_run");
            prepared = core.prepareEnd(row.get("run_id").asString());
          }
          case "source_boundary" -> prepared = core.prepareBoundary(row.get("run_id").asString(),
              row.at("/source/namespace").asString(), row.at("/source/instance").asString(),
              row.get("host_id").asString(), row.get("generation").asString());
          default -> throw new IllegalArgumentException("unknown_input");
        }
        outputs.addAll(prepared.outputs()); consumed = prepared.consumed();
        if (consumed) outputs.add(receipt(wire, row));
      } catch (IllegalArgumentException invalid) {
        String category = invalid.getMessage();
        if (category != null && (category.endsWith("backlog") || category.equals("conflicting_redelivery"))) throw invalid;
        outputs.clear(); outputs.add(quarantine(wire)); consumed = true;
        prepared = new Assembler.Prepared(core.snapshot(), List.of(), true);
      }
    }
    ArrayNode nextOut = outbox().deepCopy(); long sequence = state.get("next_sequence").asLong();
    for (JsonNode output : outputs) {
      String type = output.path("kind").asString().equals("input_receipt") ? "receipt"
          : output.path("kind").asString().equals("quarantine") ? "quarantine" : kind(output);
      validateDocument(type, output);
      nextOut.add(Json.MAPPER.valueToTree(Map.of("sequence", sequence, "kind", type, "key", key(type, output), "document", output)));
      sequence = Math.addExact(sequence, 1);
    }
    if (nextOut.size() > QUEUE_COUNT || Json.bytes(nextOut).length > QUEUE_BYTES) return false;
    state.set("assembler", parseState(prepared.nextSnapshot())); cachedCore = null; state.set("outbox", nextOut);
    state.put("next_sequence", sequence); if (consumed) inbox().remove(0);
    return true;
  }
  private static void validateDocument(String kind, JsonNode document) {
    check(Json.bytes(document).length <= Json.MAX_VALUE, "assembly_output_limit_backlog");
    switch(kind) {
      case "event" -> new io.detectbridge.detection.Normalized(new io.detectbridge.detection.Contracts())
          .validate(document, Boundary.resource(document.at("/detectbridge/source_contract/id").asString() + ".source"));
      case "manifest", "diagnostic" -> Schemas.linux(kind.equals("manifest") ? "manifest" : "preservation", document);
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
    byte[] bytes = Json.bytes(envelope); check(bytes.length <= STATE_BYTES, "assembly_state_limit"); return bytes;
  }
  /** Qualification evidence only, never a recovery source. No original bodies are copied. */
  public synchronized JsonNode inventory(long checkpoint, byte[] snapshot) {
    ObjectNode result=Json.MAPPER.createObjectNode(); result.put("version","1.0.0");result.put("checkpoint_id",checkpoint);
    result.put("binding",binding);result.put("snapshot_sha256",Json.sha(snapshot));result.put("received_offset",state.get("received_offset").asLong());
    ArrayNode groups=result.putArray("groups");
    for(JsonNode group:state.at("/assembler/groups")) {
      ObjectNode item=groups.addObject();item.set("key",group.get("key"));
      item.set("opened",group.get("opened"));
      item.put("deadline",Math.addExact(group.get("opened").asLong(),limits.ageMillis()));
      ArrayNode members=item.putArray("members");
      for(JsonNode member:group.get("members")) members.add(Json.MAPPER.valueToTree(Map.of("record_id",member.at("/raw/record_id").asString(),
          "evidence_sha256",member.at("/raw/evidence/sha256").asString(),"raw_sha256",hash(member.get("raw")),"context_sha256",hash(member.get("context")))));
    }
    ArrayNode pending=result.putArray("inbox");for(JsonNode wire:inbox())pending.add(wire.get("input"));
    ArrayNode intents=result.putArray("outbox");
    for(JsonNode intent:outbox()) {
      ObjectNode item=intents.addObject();item.put("sequence",intent.get("sequence").asLong());item.set("kind",intent.get("kind"));item.set("key",intent.get("key"));
      JsonNode doc=intent.get("document");item.put("document_sha256",Json.sha(Json.bytes(doc)));
      String run=doc.at("/detectbridge/run_id").asString();if(run.isEmpty())run=doc.has("manifest_id")?doc.at("/key/run_id").asString():doc.path("run_id").asString();item.put("run_id",run);
      if(doc.has("input"))item.set("input",doc.get("input"));
      ArrayNode refs=item.putArray("members");
      JsonNode originals=doc.has("@timestamp")?doc.at("/detectbridge/evidence"):doc.path("members");
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
  public static Machine restore(Clock clock, Assembler.Limits limits, String binding, JsonNode source, Resolver resolver, byte[] bytes) {
    JsonNode envelope = parseState(bytes); Schemas.require("state", envelope);
    ObjectNode unhashed = ((ObjectNode) envelope).deepCopy(); String digest = unhashed.remove("sha256").asString();
    check(hash(unhashed).equals(digest) && unhashed.get("binding").asString().equals(binding), "incompatible_assembly_restore");
    for(String counter:List.of("next_sequence","received_offset","retired_sequence"))check(unhashed.get(counter).isIntegralNumber(),"assembly_integer_required");
    Machine machine = new Machine(clock, limits, binding, source, resolver); machine.state = unhashed;
    machine.assembler();
    check(machine.inbox().size() <= QUEUE_COUNT && machine.inboxBytes() <= QUEUE_BYTES
        && machine.outbox().size() <= QUEUE_COUNT && machine.outboxBytes() <= QUEUE_BYTES, "assembly_queue_limit");
    long previous = -1;
    for (JsonNode wire : machine.inbox()) {
      machine.validateWire(wire); long offset = wire.at("/input/offset").asLong();
      check(offset > previous && offset <= unhashed.get("received_offset").asLong(), "assembly_input_order"); previous = offset;
    }
    previous = unhashed.get("retired_sequence").asLong();
    for (JsonNode intent : machine.outbox()) {
      long sequence = intent.get("sequence").asLong(); String kind = intent.get("kind").asString();
      check(intent.get("sequence").isIntegralNumber() && sequence == previous+1 && sequence < unhashed.get("next_sequence").asLong(), "assembly_intent_order");
      validateDocument(kind, intent.get("document"));
      check(key(kind, intent.get("document")).equals(intent.get("key").asString()), "assembly_intent_key"); previous = sequence;
    }
    check(previous+1==unhashed.get("next_sequence").asLong(),"assembly_retirement_order");
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
