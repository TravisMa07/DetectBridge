package io.detectbridge.linux;

import static io.detectbridge.detection.Contracts.check;

import io.detectbridge.transport.Json;
import java.time.Clock;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/** Offline bounded state machine. Commit is the sole admission/durability boundary. */
public final class Assembler {
  public record Limits(int members, int groupBytes, int openGroups, int pendingBytes,
      long ageMillis, int runs, int closedKeys, int closedBytes) {
    public Limits {
      check(members > 0 && members <= 256 && groupBytes > 0 && groupBytes <= 1048576
          && openGroups > 0 && openGroups <= 1024 && pendingBytes >= 13 && pendingBytes <= 33554432
          && ageMillis > 0 && ageMillis <= 30000 && runs > 0 && runs <= 16
          && closedKeys > 0 && closedKeys <= 100000 && closedBytes > 0 && closedBytes <= 33554432,
          "invalid_limits");
    }
    public static Limits defaults() { return new Limits(256, 1048576, 1024, 33554432, 30000, 16, 100000, 33554432); }
  }
  /** Must atomically persist every output and snapshot, or throw without committing either. */
  @FunctionalInterface
  public interface Commit { void persist(List<JsonNode> outputs, byte[] nextSnapshot) throws Exception; }

  /** Pure proposal over detached state; no live admission or external durable callback. */
  public record Prepared(byte[] nextSnapshot, List<JsonNode> outputs, boolean consumed) {
    public Prepared { nextSnapshot = nextSnapshot.clone(); outputs = outputs.stream().map(JsonNode::deepCopy).toList(); }
    @Override public byte[] nextSnapshot() { return nextSnapshot.clone(); }
    @Override public List<JsonNode> outputs() { return outputs.stream().map(JsonNode::deepCopy).toList(); }
  }
  @FunctionalInterface private interface Proposal { void apply(Assembler fork, Commit capture) throws Exception; }
  private static final class Drain extends RuntimeException {
    final String id, reason;
    Drain(String id, String reason) { this.id = id; this.reason = reason; }
  }
  private ObjectNode preparingOrigin;
  private Prepared proposalResult;
  private static final Commit NO_DURABLE_CALLBACK = (outputs,next) -> {throw new IllegalStateException("preparation_invoked_durable_callback");};

  public synchronized Prepared prepare(Boundary.Input input) throws Exception {
    return propose((fork, capture) -> fork.accept(input, capture));
  }
  /** Stateful auth admission for a checkpoint wrapper that binds both source profiles. */
  public synchronized Prepared prepareAuthentication(Boundary.Input input) throws Exception {
    return propose((fork, capture) -> fork.authentication(input, capture));
  }
  private void authentication(Boundary.Input input, Commit commit) throws Exception {
    Boundary.validateContext(input.raw(), input.context());
    check(input.context().at("/parser/id").asString().equals("openssh-password"), "parser_binding");
    check(Json.sha(input.bytes()).equals(input.raw().at("/evidence/sha256").asString()), "record_digest");
    String run = input.context().get("run_id").asString();
    String receipt = run + "/" + input.raw().get("record_id").asString();
    String fingerprint = Boundary.hash(Json.MAPPER.valueToTree(List.of(input.raw(), Boundary.configuration(input.context()))));
    if (state.get("receipts").has(receipt)) {
      check(state.get("receipts").get(receipt).asString().equals(fingerprint), "conflicting_redelivery"); return;
    }
    ObjectNode next = state.deepCopy(); ObjectNode runs = object(next, "runs");
    if (!runs.has(run)) { check(activeRuns(runs) < limits.runs, "run_limit_backlog"); runs.put(run,"active"); }
    JsonNode result = runs.get(run).asString().equals("ended") ? Boundary.diagnostic(input,"after_dataset_end") : OpenSsh.adapt(input);
    object(next,"receipts").put(receipt,fingerprint);persist(next,List.of(result),commit);
  }
  public synchronized Prepared prepareTick() throws Exception { return propose(Assembler::tick); }
  public synchronized Prepared prepareEnd(String run) throws Exception {
    return propose((fork, capture) -> fork.end(run, capture));
  }
  public synchronized Prepared prepareBoundary(String run, String namespace, String instance,
      String host, String generation) throws Exception {
    return propose((fork, capture) -> fork.boundary(run, namespace, instance, host, generation, capture));
  }
  public synchronized long nextDeadline() {
    long deadline = Long.MAX_VALUE;
    for (JsonNode group : state.get("groups"))
      deadline = Math.min(deadline, Math.addExact(group.get("opened").asLong(), limits.ageMillis));
    return deadline;
  }
  private Prepared propose(Proposal action) throws Exception {
    Assembler fork = restore(clock, limits, snapshot());
    fork.preparingOrigin = fork.state.deepCopy();
    try {
      action.apply(fork, NO_DURABLE_CALLBACK);
      // Exact same-ID retry intentionally does not call the offline Commit API.
      return fork.proposalResult == null ? new Prepared(snapshot(), List.of(), true) : fork.proposalResult;
    } catch (Drain requested) {
      Assembler single = restore(clock, limits, snapshot());
      ObjectNode next = single.state.deepCopy(); List<JsonNode> outputs = new ArrayList<>();
      single.close(next, outputs, requested.id, requested.reason);
      single.validateState(next);
      return new Prepared(Json.bytes(next), outputs, false);
    }
  }

  private final Clock clock;
  private final Limits limits;
  private final String binding;
  private ObjectNode state;

  public Assembler(Clock clock, Limits limits) {
    this.clock = Objects.requireNonNull(clock); this.limits = limits;
    binding = Boundary.hash(Json.MAPPER.valueToTree(Map.of("assembler", "linux-audit/1.0.0",
        "policy", "execution-evidence/1.0.0", "limits", limits,
        "source", Boundary.resource("linux-audit-execution-p12a.source"),
        "mapping", Boundary.resource("linux-audit-execution-p12a.mapping"))));
    state = Json.MAPPER.createObjectNode(); state.put("version", "1.0.0"); state.put("binding", binding);
    state.putObject("runs"); state.putObject("groups"); state.putObject("closed"); state.putObject("receipts");
  }

  public synchronized byte[] snapshot() { return Json.bytes(state); }

  public static Assembler restore(Clock clock, Limits limits, byte[] snapshot) {
    Assembler a = new Assembler(clock, limits);
    check(snapshot.length <= 2 * 33554432 + 65536, "state_limit");
    // Snapshot is larger than the per-event JSON limit; use bounded state parser, not event reader.
    Boundary.text(snapshot);
    JsonNode parsed = tools.jackson.databind.json.JsonMapper.builder(
        tools.jackson.core.json.JsonFactory.builder()
            .enable(tools.jackson.core.StreamReadFeature.STRICT_DUPLICATE_DETECTION)
            .streamReadConstraints(tools.jackson.core.StreamReadConstraints.builder()
                .maxNestingDepth(64).maxStringLength(2 * 1048576).maxNumberLength(128).build()).build())
        .enable(tools.jackson.databind.DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build().readTree(snapshot);
    io.detectbridge.detection.Normalized.unicode(parsed); Boundary.strictIntegers(parsed);
    Boundary.schema("urn:detectbridge:linux:1.0.0:state", parsed);
    check(parsed.get("binding").asString().equals(a.binding), "incompatible_state_binding");
    a.validateState((ObjectNode) parsed);
    a.state = (ObjectNode) parsed.deepCopy(); return a;
  }

  public synchronized void accept(Boundary.Input input, Commit commit) throws Exception {
    Boundary.validateContext(input.raw(), input.context());
    check(input.context().at("/parser/id").asString().equals("linux-audit"), "parser_binding");
    check(Json.sha(input.bytes()).equals(input.raw().at("/evidence/sha256").asString()), "record_digest");
    String run = input.context().get("run_id").asString();
    String receipt = run + "/" + input.raw().get("record_id").asString();
    String fingerprint = Boundary.hash(Json.MAPPER.valueToTree(List.of(input.raw(), Boundary.configuration(input.context()))));
    if (state.get("receipts").has(receipt)) {
      check(state.get("receipts").get(receipt).asString().equals(fingerprint), "conflicting_redelivery"); return;
    }
    ObjectNode next = state.deepCopy(); List<JsonNode> outputs = new ArrayList<>();
    expire(next, outputs, clock.millis());
    ObjectNode runs = object(next, "runs");
    if (!runs.has(run)) { check(activeRuns(runs) < limits.runs, "run_limit_backlog"); runs.put(run, "active"); }
    if (!input.context().has("host_binding") || !input.context().has("source_generation")) {
      outputs.add(Boundary.diagnostic(input, "identity_missing"));
    } else {
      Audit.Record record = null;
      try { record = Audit.parse(input.bytes()); }
      catch (IllegalArgumentException e) { outputs.add(Boundary.diagnostic(input, "extraction_failed")); }
      if (record != null) admit(next, outputs, input, record);
    }
    object(next, "receipts").put(receipt, fingerprint);
    persist(next, outputs, commit);
  }

  private void admit(ObjectNode next, List<JsonNode> outputs, Boundary.Input input, Audit.Record record) {
    ObjectNode key = Json.MAPPER.createObjectNode();
    key.set("run_id", input.context().get("run_id")); key.set("source", input.context().get("source"));
    key.set("host_id", input.context().at("/host_binding/host_id"));
    key.set("generation", input.context().at("/source_generation/id"));
    key.put("audit_timestamp", record.timestamp()); key.put("audit_serial", record.serial());
    String id = Boundary.hash(key);
    ObjectNode groups = object(next, "groups"), closed = object(next, "closed");
    if (closed.has(id)) { late(outputs, input, closed.get(id)); return; }
    if (next.at("/runs/" + input.context().get("run_id").asString()).asString().equals("ended")) {
      outputs.add(Boundary.diagnostic(input, "after_dataset_end")); return;
    }
    if (!groups.has(id)) {
      while (groups.size() >= limits.openGroups) closeOldest(next, outputs);
      ObjectNode group = groups.putObject(id); group.set("key", key); group.set("context", input.context());
      group.put("opened", clock.millis()); group.put("bytes", 0); group.putArray("members");
    }
    ObjectNode group = object(groups, id);
    ArrayNode members = (ArrayNode) group.get("members");
    if (!members.isEmpty() && (members.size() >= limits.members || group.get("bytes").asLong() + input.bytes().length > limits.groupBytes)) {
      close(next, outputs, id, "resource_limit"); late(outputs, input, closed.get(id)); return;
    }
    ObjectNode member = members.addObject(); member.set("raw", input.raw()); member.set("context", input.context());
    member.put("bytes_base64", Base64.getEncoder().encodeToString(input.bytes()));
    group.put("bytes", group.get("bytes").asLong() + input.bytes().length);
    if (group.get("bytes").asLong() > limits.groupBytes) { close(next, outputs, id, "resource_limit"); return; }
    while (!groups.isEmpty() && pendingSize(groups) > limits.pendingBytes) closeOldest(next, outputs);
    if (groups.has(id) && record.type().equals("EOE")) close(next, outputs, id, "source_boundary");
  }

  private static void late(List<JsonNode> outputs, Boundary.Input input, JsonNode closed) {
    ObjectNode diagnostic = Boundary.diagnostic(input, "late_evidence");
    diagnostic.set("original_manifest_id", closed.get("manifest_id"));
    if (closed.has("event_id")) diagnostic.set("original_event_id", closed.get("event_id"));
    outputs.add(diagnostic);
  }

  public synchronized void tick(Commit commit) throws Exception {
    ObjectNode next = state.deepCopy(); List<JsonNode> outputs = new ArrayList<>();
    expire(next, outputs, clock.millis()); persist(next, outputs, commit);
  }

  /** Boundary applies only to exact source scope; never flush a neighbouring host/run. */
  public synchronized void boundary(String run, String namespace, String instance, String host,
      String generation, Commit commit) throws Exception {
    ObjectNode next = state.deepCopy(); List<JsonNode> outputs = new ArrayList<>();
    for (var entry : entries(object(next, "groups"))) {
      JsonNode key = entry.getValue().get("key");
      if (key.get("run_id").asString().equals(run)
          && key.at("/source/namespace").asString().equals(namespace)
          && key.at("/source/instance").asString().equals(instance)
          && key.get("host_id").asString().equals(host) && key.get("generation").asString().equals(generation))
        close(next, outputs, entry.getKey(), "source_boundary");
    }
    persist(next, outputs, commit);
  }

  public synchronized void end(String run, Commit commit) throws Exception {
    ObjectNode next = state.deepCopy(); List<JsonNode> outputs = new ArrayList<>();
    check(object(next, "runs").has(run), "unknown_run");
    for (var entry : entries(object(next, "groups")))
      if (entry.getValue().at("/key/run_id").asString().equals(run)) close(next, outputs, entry.getKey(), "dataset_end");
    object(next, "runs").put(run, "ended"); persist(next, outputs, commit);
  }

  private void expire(ObjectNode next, List<JsonNode> outputs, long now) {
    for (var entry : entries(object(next, "groups")))
      if (now - entry.getValue().get("opened").asLong() >= limits.ageMillis) close(next, outputs, entry.getKey(), "timeout");
  }

  private void closeOldest(ObjectNode next, List<JsonNode> outputs) {
    var oldest = entries(object(next, "groups")).stream().min(Comparator
        .comparingLong((Map.Entry<String, JsonNode> e) -> e.getValue().get("opened").asLong())
        .thenComparing(Map.Entry::getKey)).orElseThrow();
    close(next, outputs, oldest.getKey(), "resource_limit");
  }

  private void close(ObjectNode next, List<JsonNode> outputs, String id, String closure) {
    ObjectNode group = object(object(next, "groups"), id);
    if (preparingOrigin != null && preparingOrigin.path("groups").path(id).equals(group))
      throw new Drain(id, closure);
    List<JsonNode> raws = new ArrayList<>(); List<Audit.Record> records = new ArrayList<>();
    boolean contextConflict = false;
    for (JsonNode member : group.get("members")) {
      raws.add(member.get("raw")); records.add(Audit.parse(Base64.getDecoder().decode(member.get("bytes_base64").asString())));
      if (!Boundary.configuration(member.get("context")).equals(Boundary.configuration(group.get("context")))) contextConflict = true;
    }
    Audit.Assessment assessment = Audit.assess(records);
    List<String> findings = new ArrayList<>(assessment.findings());
    if (contextConflict) findings.add("context_conflict");
    if (closure.equals("resource_limit")) findings.add("resource_limit");
    boolean eligible = findings.isEmpty();
    JsonNode ctx = group.get("context");
    ObjectNode event = Boundary.event(ctx, raws, Audit.occurrence(records.get(0).timestamp()), "valid",
        records.get(0).timestamp(), closure, eligible, findings, assessment.fields(), Map.of("process", assessment.process()));
    String observedCode = records.stream().anyMatch(r -> r.type().equals("EXECVE")) ? "EXECVE"
        : records.stream().anyMatch(r -> r.type().equals("SYSCALL")) ? "SYSCALL" : records.get(0).type();
    ((ObjectNode) event.get("event")).put("code", observedCode);
    ObjectNode manifest = Json.MAPPER.createObjectNode(); manifest.put("version", "1.0.0");
    manifest.set("key", group.get("key")); manifest.put("closure", closure);
    manifest.put("assembler", "linux-audit/1.0.0"); manifest.put("policy", "execution-evidence/1.0.0");
    manifest.set("findings", Json.MAPPER.valueToTree(findings)); manifest.put("eligible", eligible);
    manifest.put("source_sha256", ctx.at("/source_contract/sha256").asString());
    manifest.put("mapping_sha256", ctx.at("/mapping_profile/sha256").asString());
    manifest.set("scope_provenance", Json.MAPPER.valueToTree(Map.of("host_binding", ctx.get("host_binding"),
        "source_generation", ctx.get("source_generation"))));
    ArrayNode membership = manifest.putArray("members");
    for (JsonNode member : group.get("members"))
      membership.add(Boundary.referenceMember(member.get("raw"), member.get("context")));
    if (Json.bytes(event).length <= Json.MAX_VALUE) {
      manifest.set("event_id", event.at("/event/id")); outputs.add(event);
    } else {
      manifest.put("eligible", false); ((ArrayNode) manifest.get("findings")).add("output_limit");
    }
    String manifestId = "sha256:" + Boundary.hash(manifest); manifest.put("manifest_id", manifestId);
    Boundary.schema("urn:detectbridge:linux:1.0.0:manifest", manifest);
    check(Json.bytes(manifest).length <= Json.MAX_VALUE, "manifest_limit_backlog");
    outputs.add(manifest);
    ObjectNode knowledge = object(next, "closed").putObject(id);
    knowledge.set("key", group.get("key")); knowledge.put("manifest_id", manifestId);
    if (manifest.has("event_id")) knowledge.set("event_id", manifest.get("event_id"));
    object(next, "groups").remove(id);
  }

  private void persist(ObjectNode next, List<JsonNode> outputs, Commit commit) throws Exception {
    validateState(next);
    // Detached outputs/snapshot: callers cannot mutate the live state through commit arguments.
    for (JsonNode output : outputs) if (output.path("kind").asString().equals("preservation"))
      Boundary.schema("urn:detectbridge:linux:1.0.0:preservation", output);
    if(preparingOrigin!=null) {proposalResult=new Prepared(Json.bytes(next),outputs,true);return;}
    commit.persist(outputs.stream().map(JsonNode::deepCopy).toList(), Json.bytes(next)); state = next;
  }

  private void validateState(ObjectNode n) {
    Boundary.schema("urn:detectbridge:linux:1.0.0:state", n);
    check(n.get("binding").asString().equals(binding), "incompatible_state_binding");
    check(activeRuns(n.get("runs")) <= limits.runs, "run_limit_backlog");
    check(n.get("groups").size() <= limits.openGroups && pendingSize(n.get("groups")) <= limits.pendingBytes, "pending_limit_backlog");
    check(n.get("closed").size() <= limits.closedKeys
        && closedSize(n) <= limits.closedBytes, "closed_limit_backlog");
    for (var entry : n.get("groups").properties()) {
      JsonNode g = entry.getValue();
      check(entry.getKey().equals(Boundary.hash(g.get("key"))) && !n.get("closed").has(entry.getKey()), "state_key");
      check(g.get("context").equals(g.get("members").get(0).get("context")), "state_initial_context");
      long bytes = 0; Set<String> ids = new HashSet<>();
      for (JsonNode m : g.get("members")) {
        JsonNode raw = m.get("raw"), ctx = m.get("context"); Boundary.validateContext(raw, ctx);
        check(ctx.at("/run_id").equals(g.at("/key/run_id")) && ctx.at("/source").equals(g.at("/key/source"))
            && ctx.at("/host_binding/host_id").equals(g.at("/key/host_id"))
            && ctx.at("/source_generation/id").equals(g.at("/key/generation"))
            && n.get("runs").path(ctx.get("run_id").asString()).asString().equals("active"), "state_scope");
        String receipt = ctx.get("run_id").asString() + "/" + raw.get("record_id").asString();
        check(n.get("receipts").path(receipt).asString().equals(Boundary.hash(
            Json.MAPPER.valueToTree(List.of(raw, Boundary.configuration(ctx))))), "state_receipt");
        byte[] original = Base64.getDecoder().decode(m.get("bytes_base64").asString()); bytes += original.length;
        check(Json.sha(original).equals(raw.at("/evidence/sha256").asString()), "state_record_digest");
        check(ids.add(raw.get("record_id").asString()), "state_duplicate");
        Audit.Record record = Audit.parse(original);
        check(record.timestamp().equals(g.at("/key/audit_timestamp").asString())
            && record.serial().equals(g.at("/key/audit_serial").asString()), "state_record_key");
      }
      check(bytes == g.get("bytes").asLong() && bytes <= limits.groupBytes
          && !ids.isEmpty() && ids.size() <= limits.members, "state_group_limit");
    }
    for (var entry : n.get("closed").properties())
      check(entry.getKey().equals(Boundary.hash(entry.getValue().get("key"))), "state_closed_key");
  }

  private static int pendingSize(JsonNode groups) { return Json.bytes(Map.of("groups", groups)).length; }
  private static int closedSize(ObjectNode state) {
    ObjectNode retained = state.deepCopy(); retained.remove("groups"); return Json.bytes(retained).length;
  }

  private static long activeRuns(JsonNode runs) {
    long count = 0; for (JsonNode status : runs) if (status.asString().equals("active")) count++; return count;
  }

  private static ObjectNode object(ObjectNode n, String name) { return (ObjectNode) n.get(name); }
  private static List<Map.Entry<String, JsonNode>> entries(ObjectNode n) { return new ArrayList<>(n.properties()); }
}
