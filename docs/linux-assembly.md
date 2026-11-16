# Checkpointed Linux assembly qualification

P12b provides an isolated qualification job around P12a, not a production P13
pipeline. Acceptance status and exact evidence are in the [ledger](p12b-ledger.md);
see the [plan](p12b-plan.md) and [design](p12b-design.md). No exactly-once Kafka,
rescaling, permanent archive or throughput claim.

## Commands and isolation

Use pinned development tools. `tools/dev.py assembly` runs real Linux/core,
checkpoint-model, serializer, resolver and owning Python/gate regressions plus
production schema/notice/dependency checks. Root `java` retains all existing tasks
and includes the new module. The required linux-assembly-verification CI job runs
these checks and actual Kafka/Flink qualification on selected/shared changes.

```sh
uv run --locked python tools/dev.py assembly
uv run --locked python tools/linux_assembly.py build
uv run --locked python tools/linux_assembly.py verify
```

Verification serializes default and resource-profile projects. Every project is
exclusive detectbridge-p12-* with its own broker, topics, group, checkpoint volume
and immutable build/configuration metadata. Never overlap heavy local assembly,
writer or detection runs. The verifier removes only its own temporary stacks and
volumes. Original synthetic inputs and independent expectations are retained in
ignored project ledgers before publication; real recording payloads are absent
from ordinary CI. The reviewed P12a auth recording remains separate evidence.

For manual inspection, initialize a new unused project, then start it:

```sh
uv run --locked python tools/linux_assembly.py --project detectbridge-p12-dev init
uv run --locked python tools/linux_assembly.py --project detectbridge-p12-dev start
uv run --locked python tools/linux_assembly.py --project detectbridge-p12-dev status
uv run --locked python tools/linux_assembly.py --project detectbridge-p12-dev metrics
```

Stop explicitly with `stop`. An existing job requires an explicit compatible named
checkpoint on the next `start --restore file:///state/checkpoints/JOB/chk-N`.
The launcher validates URI/ownership and retained metadata. Do not restore a
superseded checkpoint as a substitute for a reviewed replay/new run. Starting
existing input from the beginning is rejected; deliberate retained-input replay
needs an explicit new run/pipeline, not silent state reset. No PR merge or release
is performed by these commands.

## Input and evidence

The [input schema](../contracts/linux-assembly/v1/assembly-input.schema.json)
defines raw/context records and explicit source-boundary/run-end controls. All
share one ordered input partition. Control provenance and exact run/source/host/
generation scope are explicit. P03 remains closed and unchanged. The real parser
receives exact original bytes and the P12a context; unsupported/malformed/identity-
missing/late/ended outcomes remain distinct. P12b does not evaluate Sigma rules.

Inline UTF-8 and base64 are supported. Reference evidence requires opt-in local
registration at initialization:

```sh
uv run --locked python tools/linux_assembly.py --project detectbridge-p12-refs \
  init --objects /absolute/path/to/reviewed-content-addressed-objects
```

Only regular files named by their exact lowercase SHA-256 are accepted. Bounds:
128 objects, 32 MiB each, 64 MiB total. Exact bytes are copied into the ignored
owned project cache; only that cache and its immutable digest-bound registration
are mounted read only. Original files are unchanged. Resolution verifies the
whole object, record hash, byte range, LF boundaries and dataset position. Source
URI text is retained but never fetched or used as a filesystem path. Unavailable
registered evidence remains visible I/O backlog/failure. Registration changes
cannot be silently adopted on restore.

Original envelopes, contexts and evidence must remain retained by the caller.
Kafka input retention is indefinite in this qualification project; it is not an
archive guarantee. P12a assembly keys, occurrence IDs and original first observation
are preserved. Replay run identity remains separate from P03 evidence identity.

## State, outputs and limits

One operator at parallelism one enforces aggregate limits. P12a defaults remain:
256 members/1 MiB original group bytes; 1,024 open groups; 32 MiB serialized pending
state; 30-second absolute first-admission age; 16 active runs; closed knowledge at
most 100,000 entries AND 32 MiB including receipts/metadata. Run end preserves closed
keys/receipts. No TTL or silent eviction.

The wrapper separately bounds inbox and outbox to 8 MiB/64 entries each. Original
Kafka bytes/context count toward inbox serialization; complete output intents
count toward outbox serialization. One prepared transition runs per mailbox/timer
callback. Large timeout/end/resource drains close one retained group at a time,
retaining still-unconsumed input/control. A full outbox waits for checkpoint
completion; inbox or permanent closed-knowledge exhaustion fails visibly with
source backlog. These are serialized budgets, not measured heap/capacity claims;
state copies, serializers and Flink buffers add transient memory.

Outputs are exact P03 events, P12a manifests/preservation documents, or versioned
hash/location-only quarantine and input receipts. Six dedicated topics comprise
one input plus event/manifest/diagnostic/quarantine/receipt outputs. Kafka keys
retain stable document IDs; headers carry runtime binding, kind and intent sequence.
A required sink failure cannot retire its durable intent through a successful
checkpoint. A staging checkpoint can retain an intent before its first publication;
this must not be confused with an acknowledged output or retirement checkpoint.

Only a completed checkpoint seals an externally releasable outbox prefix. Restore
releases its durable retained prefix. Output collection followed by failure can
repeat stable bytes/IDs; the independent verifier counts physical duplicates
separately from logical documents. Source/mapping/parser/policy/code/limits/
registration, Kafka cluster/topic IDs and consumer group bind restore. Unknown or
incompatible state fails before new admission/output; no fallback resets state.
Absolute deadlines survive downtime and fire on idle input without refreshing age.

## Qualification evidence

The oracle specifies original IDs/hashes, membership, closure, quality, fields,
links and disposition before submission. It checks complete manifests and unchanged
raw evidence, not just totals. Checkpoint inventories contain only IDs/hashes,
scopes, input locations and pending intent references; they are observations,
never recovery sources. They count as durable only when the exact checkpoint is
independently confirmed COMPLETED by Flink. No raw body enters operator logs.

The default scenario covers partial-group TaskManager recovery, idle timeout,
immutable late links, replay scope with stable evidence identity, interleaved
hosts/generations/runs, explicit boundary/end, auth, registered range evidence,
invalid/null input, incompatible restore, JobManager restore and failure of every
required output kind. A read-back-verified per-topic max.message.bytes policy
forces actual producer RecordTooLarge rejection while source input stays writable;
this is selective sink rejection. A separate Docker broker pause exceeds a retained
group deadline and requires checkpoint restoration and idle closure after recovery.
No configuration mismatch or arbitrary process exit counts as producer failure.
Reduced limit profiles qualify member/open-group/pending-byte
pressure, incremental draining and closed-key admission failure with independently
verified retained Kafka bytes. Exact numeric/byte edge and callback crashpoint
coverage also runs through state/serializer tests; it is labelled separately from
actual runtime evidence. See the ledger for completed versus pending checks.

Full P12 still needs owner independent-expectation/completeness review and reviewed
eligible audit evidence. P11's recorded host-binding blocker also remains before
P13 acceptance. A green P12b gate cannot erase those requirements.
