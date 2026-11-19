# P15b — Applied worker activation and rollback

Status: design frozen in commit `0a41ee4900fb3430d4fff98b9fd9b884c383b4f1`
before production implementation, on owner-merged P15a
`f44403e2975db46554c9c5033f87886d880c4087`. Its exact merged-main push run
44472864062 attempt 1 passed all nineteen applicable jobs and required-checks.
No P15b production implementation, runtime qualification or owner acceptance is
established by the freeze. The [P15 owning design](p15-design.md),
[P15a evidence](p15a-ledger.md) and
[independent P15b cases](p15b-expectations.md) remain authoritative inputs.
The slice map below assigns archive/replay completion to a real dependent artifact
boundary; neither runtime-only delivery nor this draft completes P15.

The owner subsequently retained S12's independent worker recompilation boundary.
The separately frozen [validator addendum](p15b-validator-design.md) extends the
runtime binding and isolated deployment before that new artifact is implemented.

Implementation review refinements retain the frozen wire/state contracts: verify
private copied executables/configuration again before every helper and operation;
bind Kafka drain/commit helpers to the exact cluster/topic ID before and after
their operation; use withheld recovery headroom for already adopted publication
and ACK catch-up. A local integrity failure cannot be recorded as a bad remote ACK.
Container UID checks on Linux use the fixed kernel `/proc/self` owner because
the JDK passwd-based lookup reports zero for otherwise valid unmapped helper UIDs.
Candidate path symlink rules remain unchanged.

Each JobManager joins only its worker's private network. TaskManager joins that
network and the shared private broker network; the validator has no network.
Kafka calls occur in the TaskManager reader/sink or separate owned admin helpers,
not the JobManager/client/enumerator. This avoids exposing duplicate `jobmanager`
aliases or another cluster's REST/RPC endpoint on the shared network.
[Compose alias rules](https://docs.docker.com/reference/compose-file/services/#aliases)
do not guarantee which container a shared alias resolves to. Network-list ordering
therefore cannot establish scheduler isolation. Actual qualification must use the
corrected topology; earlier successful scenarios alone cannot qualify that boundary.

The exact value-free logger resource is extracted from the verified new JAR and
mounted read-only at Flink's actually selected console configuration path. Its
nonsensitive mode0444 file is the sole file-mode exception inside the mode0700
controller root; keys, inputs and checked state remain mode0600. Startup verifies
the in-container hash, active JVM configuration argument and an observed structured
backend record before claiming the job submitted. This records the implementation
choice; actual runtime evidence remains in the [qualification ledger](p15b1-ledger.md).

## Reviewable slices and total milestone gate

| Slice | Concrete deliverable | Acceptance boundary |
| --- | --- | --- |
| P15b1 | Additive worker runtime, signed publication/artifact transfer/acks, actual mixed-worker selection, checkpoint recovery, attribution and rollback | Qualified finite local runtime/control behavior; new output is not yet supported by old archive/replay readers |
| P15b2 | Separate lifecycle archive graph/backend and original-membership historical/current replay profile, artifact pins, retention integration and acceptance map | New-runtime evidence retained and replayed with the actual closed processing graph; complete P15 requirement disposition |

This is routine slicing by real runtime/graph artifact boundaries, not delegation
count. Carry P15b1 through reviewable PR delivery first. P15b2 dependent
implementation starts only after an owner-authorized P15b1 merge and independently
successful exact merged-commit checks. No stacking permission is inferred.
P15b1 is not full P15b or P15 completion. P15b2 requirements remain P15 work, not
silently deferred to P16 or P17. P16 dependent implementation waits for complete
P14/P15 gates. Until P15b2, qualify b1 in isolated finite operator test deployments;
operator documentation must expose its unsupported new-output archive/replay
boundary rather than encouraging unattended source admission without that profile.

## Bounded topology and additive artifact

Create `packages/lifecycle-job` and `tools/lifecycle_runtime.py`, with new closed
contracts under `contracts/lifecycle-runtime/v1`. Keep old integration source,
resources, deployment, checkpoint UIDs and artifacts unchanged. The new Java module
uses compile-only references to the original classes; its reproducible slim JAR
runs with the exact original producer
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`
and the existing pinned Flink libraries. Verify both JAR identities independently.
Do not rebuild old replay artifacts to accept changed hashes. Prefer the classes-only
new JAR plus provided original51 classpath over a new shadow that copies original
classes. A shadow would require separately proving class/resource byte identity,
duplicate resolution and effective class origin while still producing a distinct
runtime artifact; it offers no benefit to old replay compatibility. The slim
option follows the existing historical/current executor pattern. Both JAR URLs
must enter the same Flink user-code classloader (the pinned producer is an explicit
provided user JAR/classpath URL), not unrelated parent/child loaders; same-package
access to retained `LocalEvidence` otherwise risks runtime IllegalAccessError.
Verify retained semantic classes' actual code-source artifact hash at startup,
not just a configured filename. No downloaded artifact or candidate-selected
classpath is permitted. A new deployment
execution binding additionally pins the actual new runtime JAR, image, fixed
source/assembler limits, evidence registry, control/artifact/output topic IDs,
public authority key and stable worker/input identity. P15a's bundle profile
continues to describe the retained semantic evaluator; the new runtime execution
binding is a separate artifact identity and compatibility fact.

Use independent Flink jobs as participating workers. Each job has parallelism one,
one slot, one dedicated single-partition raw-input topic and a stable worker UUID.
Each consumes all deployment controls and artifact chunks using its own stable
manual-assignment consumer group. This demonstrates real mixed participating workers without
splitting one legacy audit assembler's keyed state across subtasks. Use at least
two simultaneously running worker jobs for mixed-version qualification. Each worker has an isolated one-JobManager/one-TaskManager cluster with its own
private state/evidence/key/bundle volumes. No worker reads another worker's local
filesystem, and no unconstrained shared scheduler can place a job on another
worker's keys/state. The new bounded Compose profile reuses the existing explicit
per-process budgets and does not change the old integration service.
Protocol membership supports 1–16 workers; runtime qualification initially covers
exactly two on the reported host/platform. This does not prove 16-worker capacity.

Private topic roles are control, artifact, acknowledgments, outputs and one input
per worker. Names are deployment-scoped and pinned with broker cluster/topic UUIDs;
every supported topic has one partition. All outputs are new versioned envelopes,
never injected into the old nine P14 topics. Routing is explicit before source
admission: one complete run/host/source-generation scope is assigned to one worker.
Run-end/source-boundary controls go to that same worker. Resharding open assembly
state is unsupported. Removing a worker does not reassign or drop its backlog.
Kafka acknowledgment remains the source acceptance boundary.

Automatic restart is disabled for the new runtime (`restart-strategy.type=none`).
Supported restart is an explicit controller replacement with a new incarnation and
key, matching signed membership revision and compatible completed checkpoint.
Do not change old P13 restart behavior. This is a bounded laptop operator workflow,
not automatic failover or HA.

## Authority and signing

Existing private-network Kafka PLAINTEXT is not authenticated Kafka-principal
access. Add application-level Ed25519 signatures using only JDK 17 built-ins.
The fixed Java `LifecycleCrypto` helper generates keys and signs/verifies canonical
closed documents. Python administration invokes that fixed helper with bounded
file arguments; no candidate chooses a classpath, algorithm, executable or command.
Keep private keys in owner-only ignored files. Do not print keys, signatures of
secret documents or source bodies in operational logs. Public key fingerprints
and fixed failure categories are safe status fields.

A deployment configuration pins the authority UUID and exact Ed25519 public key.
The private authority key remains controller-local. UUIDs are identifiers, not
secrets. Each explicitly registered worker incarnation has its own signing key;
only that worker receives its private key. Controller and worker state roots use
P15a's Unix ownership/mode/symlink/private-file checks. No listening management
endpoint is added. Registration alone does not prove liveness or applied state.

The signed control payload has `version`, `deployment_id`, `authority_id`,
`proposal`, `proposal_sha256`, `revision`, `previous_control_sha256`,
`runtime_binding_sha256` and `registrations`. `proposal` is the unchanged closed
P15a prepared-command document. Its proposal revision/predecessor retain their
P15a inspection-only meaning; they are not authoritative publication ordering.
The effective `revision` is allocated independently by the deployment publisher.
`control_sha256` is the canonical hash of this complete unsigned payload; new
output/state fields named `command_sha256` below mean this effective control hash,
never the P15a proposal hash alone. Registrations are a complete canonically ordered
snapshot of 1–16 `{worker_id, incarnation, public_key, input_topic, input_topic_id}`
objects, matching exactly the proposal participant pairs. Validate unique worker
IDs and public keys. The signature wrapper has `version`, `key_sha256`,
`payload`, `signature`; the signature signs UTF-8 domain
`detectbridge.p15b.control/1` followed by one NUL byte and canonical payload bytes.
Verify the pinned public key before parsing payload semantics or mutating state.
Raw JSON decoding/byte/depth limits still precede cryptographic work.

Acks use a distinct domain `detectbridge.p15b.ack/1`; artifact chunks use
`detectbridge.p15b.artifact/1`. Domain separation prevents transplanting a signed
artifact/ack as a command. Signature strings have the canonical base64 encoding of
64 bytes; Ed25519 public keys use canonical base64 X.509 DER encoding, bounded to
64 decoded bytes, with exact key fingerprint pinned. Private keys use PKCS#8 DER,
owned mode0600 files outside imported candidate content.

## Publication, ordering and recovery

The controller reads the verified P15a preparation journal without editing it and
adopts one immutable prepared proposal into a separate durable deployment
publication journal. Only staged, nonretired, still-valid closures can be adopted.
Proposals may remain permanently unpublished; adopting a later proposal does not
activate earlier proposals. P15a request/proposal identity and hash are retained
as provenance, never interpreted as broker publication evidence.

Publication compares the explicit expected effective control revision/hash and
CAS-allocates exactly its successor. Genesis effective revision is 1 and predecessor
null. Subsequent control bodies bind `previous_control_sha256` to the previous
authoritative complete unsigned body hash. The control body binds the adopted
proposal and exact registration/runtime snapshot. One proposal is adopted at most
once; an exact adoption retry returns the same effective control revision and
identical signed bytes. Reuse with different registration/runtime/content conflicts.
A rollback proposal must target an earlier published intended compatible bundle;
a membership proposal must select the current intended bundle. These checks use
authoritative deployment history, not merely an earlier prepared candidate.

Persist immutable publication intent before sending; record Kafka topic identity,
partition, offset and exact value hash only after broker acknowledgment. A crash
or broker uncertainty retries identical signed bytes and effective control identity.
Duplicate broker records are permitted; they cannot create another logical revision.
No new effective revision is reserved while publication of its predecessor remains
uncertain. Signed same revision/different content, previous-hash gaps, foreign
deployment/key, request conflicts and overflows fail closed. Never mint a revision
to hide an ambiguous earlier send. Report prepared, adopted-publication-pending
and broker-published separately.

Workers keep ordered observed command history distinct from applied command state.
Here and below revision/command refer to effective publisher state, not P15a
proposal numbering. Exact signed retries are idempotent. A valid next command may be observed while
its artifact is unavailable; keep the prior valid active selection, record pending
or rejected application and never acknowledge it as applied. A later signed ordered
revision may supersede a failed pending revision; the worker retains the observed
chain and its actual old selection. It must not apply a formerly pending older
revision when its chunks arrive after supersession. Catch-up verifies every command
in the chain; a larger number alone proves no earlier application.

Before the first valid selection the worker is not ready for source transitions.
A replacement incarnation may release already persisted old output intents but
cannot process new source/timer transitions until a signed command registers that
new pair and selects its compatible bundle. Excluded workers stop new transitions
and remain visibly unready, retaining their state/backlog/artifacts. A timeout does
not remove a participant or complete activation. Joining/removing/replacing members
requires a new forward `membership` revision.

## Complete artifact transport and worker-local retention

Publish immutable bundle manifest and plan over the separate artifact topic before
control publication. It is a bounded transfer protocol, not a filesystem assumption.
A signed chunk payload has `version`, authority/deployment IDs, lifecycle bundle
hash, common runtime binding (including broker cluster), logical member name (`manifest.json` or `plan.json`), complete member SHA-256,
complete byte length, zero-based chunk index, chunk count, decoded chunk SHA-256
and canonical base64 bytes. Fixed decoded chunk size is 256 KiB except the final
chunk; signed encoded Kafka records are at most 512 KiB. The exact plan is at most
4 MiB (16 chunks); the manifest is at most 64 KiB (one chunk). Nonfinal short chunks,
wrong count/index/length/hash, foreign authority, conflicting duplicate chunks,
extra logical members and oversized encodings fail before publication to the
worker's immutable store. No arbitrary extraction paths or external fetches exist.

Each worker assembles at most one bundle transfer at a time under a private
8 MiB operation allowance, preserving bounded source/control progress. Control
and artifact sources are independently checkpointed, so arrival order is not a
correctness assumption. Artifact-incomplete application remains pending on the
latest observed revision. After all chunks are durable, validate full manifest,
profile, plan closure and Java evaluator before atomically publishing the bundle.
Exact duplicate chunks reuse matching bytes. Interrupted partial transfers may be
resumed from verified chunk inventory; unknown/conflicting files block adoption.
No partial bundle can become selected.

Worker store limit is 512 MiB, with 128 MiB filesystem reserve, 64 retained bundles,
4,096 observed controls and64 KiB per command/ack. Count partial files and all
retained objects. Stop source admission visibly under exhaustion; do not evict a
needed artifact to admit a new version. Initial implementation does not garbage
collect: all referenced versions, prepared/published commands, worker pending/active
state, retained checkpoints, outbox, replay/archive pins and explicit holds retain
closure bytes. Unknown references block deletion. This conservative permanent
retention is finite and visible, not a promise of indefinite operation.

## LifecycleMachine and checkpoint/outbox correctness

Use an explicitly source-attributed adaptation of the exact legacy `Machine` in
the new module, named `LifecycleMachine`; preserve original algorithms and test
expectations outside the explicit additions. Do not edit or subclass the final
legacy class. The adaptation retains its real per-checkpoint seal map, bounded
inbox/outbox, assembler membership/quality/late handling, source validation and
completed-checkpoint intent release.

Reject snapshot/restore composition for activation: restoring a new evaluator
loses the private pending seal map. Re-snapshotting old checkpoint IDs on the newer
state would widen their sealed prefixes and release uncheckpointed work. Restricting
swaps to no pending checkpoint could avoid that specific failure but still needs
costly snapshots to recover per-intent provenance. A direct additive adaptation
keeps both real seal boundaries and commit-time provenance explicit.

The new selection is immutable `{revision, command_sha256, bundle_sha256,
plan_sha256, compatibility_sha256, origin_incarnation, evaluator}`. Validate the
complete candidate before replacing one selection reference between mailbox
transitions. At the start of one `pump` transition capture that reference once;
prepare and project every document under it. Commit assembler/windows state,
source consumption and the entire immutable output proposal together. A capacity-
blocked proposal commits nothing and is retried under the selection active at its
actual committing transition. No transition can mix evaluator versions.

Open audit groups keep original members, closure policy, quality, late links and
parser/mapping versions. Their detection selection is the active compatible bundle
at the closing transition. Old queued output is never regenerated after a swap.
Timers and actual source input are serialized in the operator mailbox with controls.
Every committed intent stores complete envelope bytes and its original selection;
emit/retry never consults the current selection to relabel it.

The checkpoint envelope pins stable deployment/worker/source/runtime/profile/topic
identities and includes observed control/artifact positions, applied selection,
verified command-chain head, assembler/inbox/outbox/counters and all artifact references.
Full retained signed control history remains in the checked worker-local journal;
checkpoint state stores its bound head/reference rather than copying 4,096 full
controls into every snapshot. Recovery verifies that referenced prefix, tolerates
an exact verified later journal suffix only as replayable observed history, and
never adopts its selection ahead of the restored source/checkpoint boundary.
Set the new state limit to the original `Machine.STATE_BYTES` plus 2 MiB for bounded
lifecycle metadata, references, envelope overhead and ack candidates. Keep original
inbox/outbox count 128 and each raw document budget unchanged; the versioned output
wire adds at most 64 KiB fixed metadata to the existing 2 MiB body maximum. Full
artifact chunks stay in the bounded local store and enter snapshots by hash only.
Incarnation is recorded as execution provenance, but replacement may restore stable
compatible worker state and preserved old intents only through the explicit
registered replacement path. Another worker's checkpoint, old P13 state descriptor,
changed executable/profile/topic/evidence registry, missing closure or corrupt state
is rejected. Restore validates all bounds and references before work. Retain at
least the configured completed checkpoints and every artifact they name.

## Output identities and immutable attribution

All derived kinds use the same new closed output envelope with `version`,
`output_id`, `deployment_id`, `worker_id`, `origin_incarnation`, `revision`,
`command_sha256`, `bundle_sha256`, `plan_sha256`, `compatibility_sha256`,
`sequence`, `kind`, `inner_key`, `document`, `document_sha256` and
`semantic_sha256`. The original P13 body is preserved unchanged inside `document`;
source event/evidence IDs and manifests are not rewritten into lifecycle identities.
The new key is `sha256:` plus SHA-256 of the canonical JSON array:

`["detectbridge.p15b.output/1", deployment_id, worker_id, revision, command_sha256, kind, inner_key]`.

Incarnation, physical output sequence and raw document hash are excluded from the
key. A→B→A uses three increasing command revisions, so A's return is a new processing
decision even when the plan and original inner keys are identical. Retry of the
same persisted intent preserves exact envelope bytes, origin incarnation and key.
A worker cannot fabricate different actual attribution under a stable key.

`document_sha256` hashes exact canonical original body bytes for integrity. Semantic
duplicate comparison hashes canonical `{deployment_id,worker_id,origin_incarnation,
revision,command_sha256,bundle_sha256,plan_sha256,compatibility_sha256,kind,inner_key,
document:<semantic projection>}`. It excludes sequence and exact-byte checksum.
For tagged bodies remove only `event.event.ingested`,
`event.detectbridge.time.received`, `event.detectbridge.time.processed` and
`event.detectbridge.extensions.linux.context.context.receipt`; replace a nonnull
manifest retrieval reference with its `semantic_sha256` only. For detection bodies
replace the same manifest reference only. Processing diagnostics, native manifests,
preservation, receipts and quarantine keep their complete body. This mirrors the
existing deliberate P13 semantic/physical distinction. Different semantic content
under the same output ID is a conflict, not a reason to mint another ID. Exact wire
checksums and Kafka locations remain separately retrievable archive facts.

## Real applied/durable acknowledgments

One custom single-split source reader consumes raw input and authenticated
control/artifact records, with stable new source/sink UIDs. The transport and
checkpoint callback choice is specified below. An applied
selection is checkpointed with source/control offsets and immutable intents.
At reader snapshotState create a bounded per-checkpoint durable-ack candidate naming the
command, actual bundle and that checkpoint ID, serialized into that snapshot copy.
Do not append an aborted-checkpoint acknowledgment to the ordinary live output
outbox: a later checkpoint must never release a durable ack naming an aborted one.
Keep these candidates in a separate map bounded by the one-concurrent-checkpoint
policy. They are not yet emitted as durable.
`notifyCheckpointComplete` marks only the saved prefix and durable-ack intent
for the actual completed snapshot ready; the next reader poll emits them. Abort releases neither and removes its live ack candidate. A restored completed
snapshot may release its saved candidate as actual completed-checkpoint evidence. An ack is durable
application evidence only after a completed checkpoint containing the selection;
a receipt or successful evaluator construction is insufficient.

The signed ack payload has `version`, deployment/authority/worker/incarnation IDs,
command revision/hash, actual bundle/profile, phase (`observed`, `rejected`,
`applied`, `durable`), applicable checkpoint ID and fixed category. The ack ID
hashes domain `detectbridge.p15b.ack/1` plus these stable fields. Persist signed
bytes before release; retries do not sign a changed current state. Controller
accepts only the exact registered current pair/key, intended command and phase;
foreign, stale-incarnation, conflicting and wrong-bundle acks cannot converge.
A restored completed checkpoint can release its saved exact durable ack, but an
old-incarnation ack remains historical evidence after replacement.

The controller's durable signed-ack journal records exact received Kafka locations
and bytes. Broker acknowledgment of the ack publication is distinct from worker
checkpoint completion. Convergence requires verified `durable` acknowledgments for
the intended command/bundle from every explicit current participant incarnation.
No worker missing from that set can be silently treated as removed. Completion of
one worker or a timeout reports mixed/incomplete state. Rollback publishes a new
forward command selecting a retained tested compatible bundle; it never rewinds
source offsets, authority history, event identity, assembler state or checkpoints.

## P15b2 archive/replay boundary and implementation ownership

**Assigned P15b2 freeze work:** define the exact lifecycle archive/replay profile
contracts and independently expected reproduction cases on qualified P15b1 main. The existing archive Store/Main hard-code nine legacy topics,
and the historical/current executors bind old artifact identities. They cannot
safely be pointed at new lifecycle topics by relaxing a name/hash check.

The selected implementation direction is an additive lifecycle archive backend adapted from the
existing atomic segment Store, with an explicit deployment topic inventory and
closed envelope/dependency graph. It must retain exact raw input, control,
artifact, acknowledgment and output wires, originals/registered objects, command
and bundle closures, runtime JAR/image and original producer pins. Offset commit
still follows durable segment publication. Lifecycle graph/version recognition
must be separate; old managed-retention unknown-graph guards stay unchanged.
Historical verification/replay then uses the recorded original membership,
per-output recorded command/plan and pinned semantic evaluator, with isolated
replay identities. Current-policy replay requires an explicitly selected compatible
bundle and isolated new run; it cannot silently use current worker state. This
P15b2 direction needs its own precise schemas/limits/expectations and actual artifact
qualification before claiming lifecycle historical reproducibility.

The separate bounded P15b2 PR is required before full P15 acceptance and P16
dependent implementation; no earlier stacked-PR authorization applies. The P15b1
freeze must retain this scope map and honest unsupported-profile status. This draft
does not turn a proposed
capsule, file export or unchanged legacy replay pass into new-runtime replay proof.

Suggested disjoint ownership: primary controls deployment protocol/contracts,
execution/CI inputs and status; Java worker owner implements additive machine/job,
crypto and unit cases; Python controller owner implements signed publication and
ack journal plus exact chunk distribution; independent expectation/qualification
owner verifies literal A/B results, identities and faults. Archive implementation
needs an explicitly assigned owner after its boundary is frozen. Serialize heavy
qualification and keep each actual failed attempt/source/artifact/platform attributed.
No code or tests have been changed by this draft.

## Selected B1 reader transport and remaining freeze integration

Use one custom Flink `Source<Delivery,WorkerSplit,EnumeratorState>` with one
single-split `SourceReader` owning the complete lifecycle machine and a manually
assigned Kafka consumer. The pinned 2.2.1 SourceReader supports snapshot, completion
and abort callbacks; SourceOperator delegates those methods. The inspected
StreamingJobGraphGenerator rejects checkpoint-enabled InputSelectable, so that
alternative is excluded. Original P13 topology and source code remain unchanged.

Each isolated worker cluster has parallelism/slots one. A fresh enumerator has
one initial split; assignment removes it from pending state. Restored enumerator
state does not create another initial split. Reader rejects duplicate/foreign
splits; an empty or mismatched restored source cannot initialize fresh worker
state. Split/enum serializer version is 1; source UID is `lifecycle-source-v1`,
sink UID `lifecycle-sink-v1`; state codec is `lifecycle-worker/1.0.0`.

All consumer/machine mutations occur on the reader task thread. A scheduler only
completes the availability future, at most every 500 ms. The reader polls at most
one Kafka record per call. When unready or without conservative raw-inbox room,
pause only raw input and keep control/artifact partitions eligible. At most one
fetched raw record waits for admission; it is omitted from snapshots while the
saved raw cursor remains the last admitted offset plus one. Restore seeks that
cursor and fetches the unadmitted record again. Never checkpoint an advanced
consumer fetch position as though the record entered the machine. Control/artifact
cursors advance only after verified durable worker-journal/transfer accounting.

Snapshot stores exact machine state, source cursors, journal-prefix proof, selection,
immutable output/provenance and checkpoint-specific signed ack candidate. Completion
and abort callbacks only mark or discard saved seals; the next poll with a valid
ReaderOutput emits the appropriate exact prefix. Do not retain ReaderOutput across
callbacks. Required sink/network blocking can still stall emission and controls;
reader arbitration promises progress through local raw backlog, not convergence
through a failed required sink. Actual source/offset/seal/restart tests remain
required; API inspection is not runtime qualification.

Use a required synchronous KafkaProducer-backed Flink SinkWriter for data/ack
records, with fixed topics, acks=all and the already reviewed producer limits.
Each write waits for the actual broker acknowledgment; failed/blocked sends fail
or backpressure visibly. No P13-only connector cleanup guard is copied or widened.
The worker's completed-source state/outbox remains recovery authority for
at-least-once sends; collecting a record is not broker acknowledgment. The controller
converges only from actual signed durable ack records read back from Kafka.

Common runtime and per-worker checkpoint binding preimages are the separate exact
objects in the contract README. Key fingerprints hash decoded canonical X.509 DER
bytes, not their base64 spelling. Require decoded key equality with its re-encoded
Ed25519 public key; reject trailing/foreign algorithm encodings. Keys enter owned
private container volumes through a fixed private helper with mode0600 and service
UID ownership; never bake private keys into an image or public qualification artifact.

Each registration carries at most16 sorted assigned run UUIDs. History permanently
binds every run to one stable worker, at most16 per worker/256 deployment. A later
omission disables fresh admission, not ownership or retained state. Never route a
run's source/EOE/run-end/boundary rows to another worker on removal or replacement.
The fixture packet uses distinct worker/phase runs; source semantic event IDs remain
unchanged. No resharding or lifetime ownership release is supported in B1.

Controller persistence is capped at512 MiB including partials, with128 MiB free
reserve and32 MiB recovery headroom withheld from ordinary writes. Limits are4096
publications,256 incarnation keys and ack evidence262144 observations or128 MiB,
whichever first. Exact signed ack ID/bytes duplicates update only durable source
position without retaining another payload. Conflicting duplicate proof blocks.
Force exact received Kafka location/hash/proof before committing the ack-consumer
offset. Exhaustion stops unsafe publication/admission with visible Kafka backlog;
no automatic history eviction or hidden offset advancement is permitted.

Before B1 freeze, finish cross-schema/fixture review of these selected contracts.
B2 archive/replay remains a separate real dependent artifact slice. This design
is not permission to claim B1 runtime or skip the merged-main prerequisite.

## B1 bounded rejection and checkpoint storage

An invalid control/artifact message never advances effective observed command
history or creates an applied/durable acknowledgment. Before advancing its source
cursor, force a bounded immutable rejection record containing only pinned Kafka
location, exact key/value hashes, byte lengths and fixed category, with a checked
chained rejection head. Original exact bytes remain in the pinned no-deletion Kafka
topic for B2 archival; routine diagnostics do not copy source bodies. Snapshot binds
the rejection-head prefix and matching cursor. Reconsuming the same Kafka location
verifies that exact record rather than appending another; a new physical occurrence
is separately accounted. At most4096 rejections, all counted in the store cap.
Missing/corrupt rejection proof or exhausted persistence leaves visible source
backlog; never advance a cursor on an unrecorded rejection.

After durable rejection the prior valid selection can continue and a later valid
ordered control may apply. Same-revision signed conflicting content is retained as
conflict and cannot replace the first verified authoritative chain. Current conflict
prevents convergence until a newer valid forward control explicitly resolves that
history; the failed attempt remains retained. Bad signatures/foreign keys are not
observed policy revisions. Raw source values up to the unchanged2 MiB limit use the
original invalid-input quarantine semantics. An accepted raw value above that limit
remains explicit size-blocked Kafka backlog with no cursor advance/truncation;
no new oversized legacy quarantine body is fabricated.

New topic byte limits include wire headroom: control/ack128 KiB, artifact1 MiB,
raw input2 MiB+64 KiB, output4 MiB. Protocol payload limits remain64 KiB control/ack,
512 KiB signed artifact,2 MiB raw and2 MiB body+64 KiB lifecycle metadata. Producer
max.request.size remains the reviewed4 MiB. Topic headroom is for Kafka framing,
not permission to accept over-contract data as valid input.

The worker artifact/journal store stays512 MiB. Its separate private Flink checkpoint
root is capped at1 GiB, with a conservative192 MiB reservation before each new
snapshot and128 MiB filesystem free reserve. One concurrent checkpoint, three
retained completed checkpoints and bounded170000384-byte serialized source state
fit this declared reservation envelope; no indefinite restart/history capacity is
claimed. Count owned completed, in-progress, aborted and retained-job files before
admission; at most65536 filesystem entries. Actual write/sync failure remains a
failed checkpoint even after preflight, because external disk use can race it.
Never turn a failed/aborted snapshot into a durable ack or delete needed completed
state to admit another. Root exhaustion is visible failure/backlog; B1 has no
checkpoint garbage-collection or retention waiver. Existing runtime heaps remain
unchanged and actual resource/fault qualification remains required.

A managed replacement verifies termination of the old owned worker cluster before
starting its replacement, then uses a new incarnation/key, newer signed membership
and an actual compatible completed checkpoint/savepoint. If old termination cannot
be verified, fail replacement rather than run two unfenced manual-assignment
consumers for one stable worker. This is explicit single-owner laptop control,
not distributed fencing or HA. Retained old intents keep original signed/envelope
bytes; fresh transitions wait for the new membership. Never stop another project's
container or assume a maximum checkpoint filename means completed state.

Store each full lifecycle output body once in the adapted core outbox. The separate
provenance array contains only immutable selection/ID/hash metadata; duplicating a
second full body would exceed the2 MiB additional snapshot allowance. The unchanged
32 MiB outbox admission cap counts complete wrapped bytes. Restore validates both
outer identities/provenance and the exact original body contracts.

The common deployment runtime binding explicitly includes the exact broker
`cluster_id`; topic names/IDs alone are insufficient. Signed controls bind this
recomputed common hash; signed artifact chunks carry it too. Ack verification
requires the intended effective command hash covering that same common binding.
A cloned/changed broker cannot become compatible merely by retaining topic IDs.

## Qualification artifact boundary

The normal job always uses production hooks with no injected faults. A separate
first-party qualification source set/JAR may drive fixed fault hooks in the exact
production reader/machine/writer classes, loaded from the verified runtime JAR.
No imported candidate, signed control or normal worker configuration selects Java
classes, hooks or probe modes. Probe bytes/hash and target operation are separately
attributed; a probe artifact never substitutes for the production runtime identity.

The fixed probes may hold data release while allowing reader control polling,
block a targeted snapshot until the unchanged60-second checkpoint timeout, or fail
after one proven Kafka-acknowledged sink write. They must record exact checkpoint/
command/sequence/offset/hash markers, actual global completed/failed checkpoint
status and original failure evidence. An unrelated crash is not the intended fault.
Normal two-worker A/B/A source qualification runs the production entry point;
probe windows supplement real broker policy/outage/container-replacement cases.
Actual required-sink broker rejection still needs the named Kafka failure, not a
probe exception alone. All probe release/cleanup is scoped to its owned operation;
no timeout/resource is enlarged to pass qualification.

Qualification execution refinement (owner requested faster feedback): retain the
default complete fourteen-scenario gate and add fresh-deployment focused scenario
groups for diagnosis. A focused success is explicitly `partial_passed`, never
`passed`/`full_gate`; required CI rejects focused selection before starting Docker.
Focused runs cannot import previous passes. The final full gate still executes all
fourteen scenarios. Batch existing ACK reads at32 records and output reads at64,
within the already frozen128-record APIs and unchanged byte/storage reservations.
Every actual signature, broker location, checked journal cursor and exact named
checkpoint proof remains required. This reduces helper startup overhead without
changing the production, probe or compiler artifact or adding a new helper protocol.

The native mixed-worker failure exposed a pause window that included signed-ACK
backlog readback. Pinned Flink2.2.1 has a50-second TaskManager heartbeat timeout;
the original native REST exception was retained only privately, so its published
`TimeoutException` class alone does not identify the exact cause. Keep all Flink
timeouts unchanged. Within a shared40-second qualification pause budget, prove W1's
exact independently COMPLETED B checkpoint, its literal B outputs, and W2's actual
owned paused state with its prior A checkpoint. Resume W2 in `finally`, then require
normal signed-ACK convergence and remaining B outputs before passing C07. No
snapshot observation is inserted into controller ACK state. A focused mixed-worker
group retains the same cases and the default core remains42 admissions/66 outputs.

The timeout probe records the serialized snapshot hash only after actual sealing
and durable-ack candidate construction. Advisory inventory verifies that
observation without promoting the snapshot to COMPLETED. After observing the
named expiration, qualification fences the worker and checks the entire frozen
broker ACK prefix for an acknowledgment naming that failed checkpoint. A later
legitimate completed checkpoint is allowed; task-side abort callback execution is
a separate component claim unless directly observed. Recovery uses only the
previous independently verified completed checkpoint. Open-group qualification
confirms all five exact source members and their hashes under the initial
selection before changing policy, with preexisting ACK catch-up completed before
opening the fixed thirty-second group window.

Use the existing exact Flink image with verified runtime/retained-producer JARs and
public logging resources mounted or copied through owned initialization, never
private keys baked into an image. The runtime JAR binds its public logging resource;
record actual platform image identity separately. Private Flink REST/RPC stays
inside each owned cluster; no host unauthenticated management port is published.
Controller commands use the local Docker administrative boundary and fixed private
helper/exec operations. Reuse the existing768m JobManager /1536m one-slot TaskManager
process budgets (1g/2g container limits); no old deployment settings are changed.
