# Lifecycle runtime contract draft 1.0.0

Original DetectBridge content, Apache-2.0. This is a design-only P15b1 contract
draft, pending integrated review and freeze. It is not implemented behavior,
cryptographic qualification, archive support or runtime evidence. See the
[owning draft](../../../docs/p15b-design.md),
[independent expectations](../../../docs/p15b-expectations.md) and
[P15a contracts](../../lifecycle/v1/README.md). Original P15a schemas are unchanged.

## Closed documents and semantic validation

`common.schema.json` owns reusable definitions and fixed finite limits. `control`,
`artifact` and `ack` are Ed25519 signed wrappers with closed fields `version`,
`key_sha256`, `payload`, `signature`. Their payloads are closed. `output` is a
closed processing envelope. `worker-config` is trusted local configuration, not
candidate content or an administrative Kafka command. `state` is a new checkpoint
envelope; its opaque `core` and the output's opaque `document` require the original
pinned core/body validators in addition to this outer schema. They do not authorize
arbitrary fields in original contracts. Unknown fields elsewhere fail.

All integer syntax is exact JSON integer syntax: reject booleans/floating counters,
duplicate keys, nonfinite values, invalid Unicode and trailing tokens before
validation. SHA-256 values are lowercase 64-digit hex; public/signature strings are
canonical base64. Decode and require Ed25519 X.509 DER public keys of at most 64
bytes, and exactly 64-byte signatures. Pattern matching alone proves neither.
Serialize canonical JSON as UTF-8 sorted keys/compact separators/unescaped Unicode.
All limits apply to exact bytes as well as schema-level lengths.

Signature preimage is UTF-8 domain followed by one NUL byte and canonical payload.
Domains are `detectbridge.p15b.control/1`, `detectbridge.p15b.artifact/1` and
`detectbridge.p15b.ack/1`. Verify only configured pinned authority keys for controls
and artifacts, and exact currently authority-registered worker/incarnation keys for
acks. UUID identity and private-network Kafka PLAINTEXT do not authenticate an
administrator. The fixed JDK 17 helper uses built-in Ed25519; private keys remain
owner-only ignored PKCS#8 files. Imported content never selects commands/classpaths,
key paths or executable code. No listening administration endpoint exists.

## Two independent revision histories

The control payload is `version`, `deployment_id`, `authority_id`, `proposal`,
`proposal_sha256`, `revision`, `previous_control_sha256`, `runtime_binding_sha256`,
`registrations`. The exact P15a proposal document is embedded unchanged. Its own
revision/predecessor are preparation history; it may never publish. The publisher
adopts one proposal once and CAS-allocates an independent effective control revision.
An exact adoption retry returns the same effective revision and signed bytes.
Uncertain publication blocks a later effective revision; it does not force every
older unadopted proposal to become live.

`proposal_sha256` hashes canonical proposal bytes. Effective `control_sha256`
hashes the complete unsigned control payload. New runtime `command_sha256` fields
in selection/output/ack/head mean this effective control hash, never the proposal
hash. Effective genesis is revision 1 with null predecessor; later controls bind
the preceding complete unsigned payload hash. Compare authority/deployment/proposal
request/target identities and current installed profile in addition to schema.
Rollback requires a target from earlier published intended history. Membership
selects the current intended bundle. These authority-history checks cannot be
proved by the embedded proposal's syntax.

## Registration, isolated workers and run ownership

Registrations are sorted by stable worker UUID with unique worker IDs, incarnation
pairs, public keys and input topics/IDs. The full snapshot contains 1–16 workers
and matches exactly the proposal participant pairs. Each `assigned_runs` is a sorted
unique UUID array of at most 16. Across the deployment there are at most 256 runs,
with at most 16 lifetime-owned runs per stable worker, matching the retained original
assembler's finite run semantics. More restrictive original profiles still apply.

Controller history permanently binds every admitted run to one stable worker. No
later omission, retirement, timeout or reincarnation releases that ownership.
The same run cannot move to another worker. Omitting a previously owned run or
worker disables fresh admissions and source/timer transitions for that scope;
it does not discard retained state/backlog or transfer ownership. Run-end and
source-boundary controls follow the same owner. Replacement must honor the latest
signed ownership snapshot before any new processing. Exhaustion requires an
explicit fresh deployment, not automatic reuse or silent reassignment.

Every worker uses its own one-JobManager/one-TaskManager Flink cluster and private
key/state/evidence/store volumes. `worker-config.flink_project` identifies that
explicit isolated Compose project. Two jobs on one unconstrained scheduler do not
prove private key/state routing or mixed-worker isolation. Parallelism and slots
remain one per worker. Protocol bound16 is not demonstrated 16-worker capacity.
No automatic new-runtime task restart is supported; explicit replacement has a
new incarnation/key and a higher signed membership revision. Old completed output
intents retain their original bytes and origin incarnation.

## Binding preimages

The deployment common runtime binding is SHA-256 of canonical closed object:

`{version, deployment_id, authority_id, authority_key_sha256, cluster_id, runtime_sha256, producer_sha256, image, topics:{control,artifact,ack,output}, compatibility_sha256, limits}`.

Each topic is its closed name/ID/partition descriptor. The binding excludes stable
worker, input topic, incarnation, run assignments, current command and local paths.
Verify new lifecycle classes' actual code-source JAR, unchanged original producer
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`,
image and same Flink user-code-classloader provided-classpath origin at startup.
The artifact carries no instance binding, avoiding circular self-hash inputs.

The stable worker checkpoint binding is SHA-256 of canonical closed object:

`{version, runtime_binding_sha256, worker_id, input_topic, evidence_registry_sha256, state_codec:"lifecycle-worker/1.0.0"}`.

It excludes current incarnation/key, command and run list, permitting only the
explicit compatible registered replacement path. Another worker, input identity,
profile/runtime/artifact, evidence registry or codec cannot restore this state.
P13 checkpoint adoption remains rejected. Both binding hashes are stored in trusted
worker config and checkpoint envelope; recompute rather than trusting hex strings.
Local bootstrap/group/path/Flink-project settings are separately validated and
pinned by deployment administration, not treated as candidate-selected endpoints.

## Artifact transfer

Only `manifest.json` and `plan.json` logical member names exist. Chunk payload binds
authority/deployment, common runtime binding (including broker cluster), lifecycle bundle, member complete hash/size, index/count,
decoded chunk hash and `data_base64`. Decode at most 256 KiB per chunk. Nonfinal
chunks are exactly 256 KiB; final length is the exact remaining positive length.
Require `chunk_count=ceil(member_bytes/262144)` and index below count. Manifest is
at most 64 KiB/one chunk; plan at most 4 MiB/16 chunks. Encoded signed record is at
most 512 KiB. Reject extra members, conflicting duplicates, malformed encoding,
wrong hashes/counts or path interpretation before immutable publication.

Workers assemble at most one bundle transfer under an 8 MiB temporary allowance.
A partial transfer cannot become selected. Exact verified chunks may resume after
interruption. Complete closure/profile/plan/evaluator validation precedes atomic
publication. Source and artifact/control arrival ordering is not a correctness
assumption: a latest control lacking complete artifacts remains pending under the
prior valid selection. Superseded pending controls cannot activate later.

## Output identity and semantic integrity

The exact identity is `sha256:` plus SHA-256 of canonical JSON array:

`["detectbridge.p15b.output/1", deployment_id, worker_id, revision, command_sha256, kind, inner_key]`.

Revision/hash identify effective publisher state. Incarnation, physical sequence and
raw-body hashes are excluded. A→B→A has three effective decisions even if original
inner keys repeat. Store `origin_incarnation` and exact envelope bytes in immutable
intents when the transition commits. Never reattribute at emit/retry. `document`
retains the original pinned P13 body; event/evidence IDs and memberships are unchanged.
`document_sha256` hashes its exact canonical bytes.

`semantic_sha256` hashes canonical object with deployment/worker/origin incarnation,
revision/command hash, bundle/plan/compatibility hashes, kind/inner key and semantic
body, excluding physical sequence and exact checksum. For tagged bodies remove
only `event.event.ingested`, `event.detectbridge.time.received`,
`event.detectbridge.time.processed`,
`event.detectbridge.extensions.linux.context.context.receipt`, and replace a nonnull
manifest retrieval reference with its `semantic_sha256` only. Detection bodies
replace that manifest reference only. Other original kinds retain complete bodies.
Different semantic content under one output ID is a conflict, not another identity.
Exact wire hashes remain separate archive facts. This contract draft does not
qualify lifecycle archive or historical/current replay, assigned to P15b2.

## Checkpoints and acknowledgments

State includes stable bindings, admitted raw/control/artifact cursors, verified observed
journal head, applied immutable selection, original bounded core, per-intent
provenance, bounded durable-ack candidates and artifact references. Provenance
sequences must match exactly retained core outbox intent sequences and complete
immutable output selection/bytes. Full 4096-entry signed history stays in a verified
worker-local journal; state binds its prefix/head. An ahead-of-checkpoint suffix
is replayable observed history, never permission to adopt active state ahead of
the restored checkpoint/source boundary. Zero observed revision has null hashes.
State's `sha256` hashes canonical envelope excluding only that outer field.

A durable ack names an actually completed checkpoint containing the selected
command/bundle. During snapshot, serialize the candidate into that snapshot copy
and retain a bounded separate per-checkpoint map. Aborted checkpoint candidates
are removed and never later emitted as durable through the ordinary live outbox.
Restore of a completed snapshot may release its saved exact candidate. Existing
source/output seal prefixes cannot widen when swapping evaluators. All serialized
state is at most 170,000,384 bytes: original `Machine.STATE_BYTES` plus 2 MiB bounded
metadata; check before commit, without increasing runtime heap.

Ack ID is `sha256:` plus hash of canonical array
`["detectbridge.p15b.ack/1", deployment_id, authority_id, worker_id, incarnation, revision, command_sha256, bundle_sha256, compatibility_sha256, phase, checkpoint_id, category]`.

Ack ID is excluded from its own preimage and signature covers it as payload data.
Only current registered matching pairs/keys and intended command/bundle can count
toward convergence. Receipt, applied state, completed checkpoint and Kafka-acked
ack publication remain distinct facts. Old-incarnation proof remains history.

## Finite controller/worker persistence

Store capacity is 512 MiB including partials; free reserve is 128 MiB. Controller
ordinary writes additionally withhold 32 MiB recovery headroom. Recovery may use
that headroom within the same hard 512 MiB cap; it does not invent extra disk.
Limits are 4096 publications/observed controls, 64 bundles, 256 incarnation
registrations, 16 workers, 16 lifetime runs per stable worker/256 deployment, 64 KiB
journal/control/ack records, and the retained 128-input/output count/32 MiB queues.
Count all retained references; no automatic eviction or lifetime counter reset.

Controller ack evidence stops at 262,144 observations or 128 MiB, whichever is reached
first. Exact signed ack ID+bytes duplicates advance only the durable observed Kafka
position, without duplicating payload/history. Same ID/different signed bytes or
semantic proof conflicts block progress. Append and force the received Kafka
location, exact wire hash and verified ack proof before committing the ack-consumer
offset. Offset advancement is not proof deletion. Exhaustion leaves visible Kafka
backlog and blocks further unsafe admission/publication; no silent shedding.

Roots are owned by the invoking Unix UID with mode 0700; private files are 0600.
Reject symlinks in every supplied path component, foreign/overlapping roots and
untrusted key/artifact files. Missing/corrupt checkpoint artifacts, signatures,
references or chain predecessors fail closed. Schema checks do not establish
fsync ordering, cryptographic authenticity or runtime recovery; those require
independent implementation/fault qualification on exact artifacts.

## Selected reader arbitration

The earlier connected raw/control operator proposal can head-of-line block control
when its raw inbox/outbox fills. The pinned checkpoint-enabled Flink topology
rejects `InputSelectable`; do not present that unsupported shortcut as a solution.
The selected transport is one custom single-split `SourceReader` containing the
lifecycle machine and one bounded Kafka consumer with explicit input/control/
artifact partition assignment. Pause only raw admission while unready/full,
continue control/artifact polling, and use `max.poll.records=1` plus at most one
fetched raw record awaiting admission. Scheduler threads may wake availability
futures but never mutate the consumer or machine.

SourceReader checkpoint methods are supported by the actual pinned 2.2.1 API;
completion/abort delegates exist in SourceOperator bytecode. One split serializer
can carry the exact bounded lifecycle snapshot and source positions; the enumerator
must not assign a fresh duplicate split on restore. Mark completed seals in the
checkpoint callback and release their exact intents from the next `pollNext(output)`
call. This avoids retaining a ReaderOutput beyond its documented callback.

`raw_cursor.next_offset` is the admitted next input, matching original core input
state, not KafkaConsumer's potentially advanced fetched position. An unadmitted
pending record need not enter the checkpoint if restore seeks that admitted cursor
and fetches it again. Advancing the saved offset without retaining/committing its
record is forbidden. Snapshotting the whole extra raw wire would require separately
accounted state headroom; the 2 MiB metadata allowance is not an implicit raw buffer.
Required sink/network backpressure can still stall source emission; reader
arbitration does not promise successful control convergence through a failed
required sink. Actual implementation/threading/offset tests follow the pre-code freeze;
API inspection itself does not establish runtime qualification.

Trusted worker configuration uses one `consumer_group` for manual assignment of
that worker's three raw/control/artifact partitions. Independent workers use
distinct groups. The owning design fixes split/enumerator restoration, checkpoint-disk reservation
and permanent run-admission accounting. Runtime/fault qualification remains required.
Key fingerprints hash canonical decoded X.509 DER bytes. A malformed or ignored
suffix must not be accepted as a second encoding of the same trusted key.

Checkpoint source state additionally pins a checked rejection-head count/hash.
Invalid controls/chunks are durably accounted by Kafka location/wire hashes and
fixed categories before cursor advancement; original bytes remain in Kafka.
Rejection capacity is4096. Same physical-location retry verifies existing proof.
The separate private checkpoint root is1 GiB with192 MiB per-checkpoint reservation,
128 MiB free reserve, one concurrent checkpoint and three retained completed
checkpoints; no automatic retained-state deletion or unbounded outage is promised.
See the owning design's exact rejection, framing, replacement and storage rules.

The common runtime binding includes exact broker `cluster_id` as well as every
shared topic ID. Recompute it from trusted configuration before accepting signed
controls or worker state. Artifact chunks additionally carry and sign that common
binding, rejecting cross-broker/runtime transplantation even when bundle bytes
match. Acks bind the intended effective command hash, which covers the common
binding; matching an authority UUID or topic name is never sufficient scope proof.
