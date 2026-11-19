# P15b prerequisite and compatibility discovery

Current prerequisite gate: actual merged-main push run 44472864062 attempt 1
passed on f44403e. All nineteen applicable jobs and required-checks passed;
five explicit opt-ins were skipped. The earlier pending status below records
the discovery checkpoint, not an unresolved implementation gate. Exact raw
evidence is retained in `.cache/p15a-main-44472864062/`.

Status: read-only source audit and design input, not production implementation or
runtime qualification. Working base is owner-authorized regular P15a merge
`f44403e2975db46554c9c5033f87886d880c4087`. Its actual main push run
[44472864062](https://github.com/TravisMa07/DetectBridge/actions/runs/44472864062)
was in progress when this audit was assigned; the primary owns exact final run,
attempt, job and aggregate verification before dependent code. Do not infer its
result from P15a PR qualification or tree identity.

## Preserved P15a reconciliation

The root's untracked `docs/p14-handoff.md`, older P14 worktree documentation and
handoffs remain outside this audit's edits. P15a's uncommitted native completion
ledger was preserved in the existing stash and exact local copy
`.cache/p15b-prerequisites/preserved-p15a-native-ledger.md`; preserve both until the
primary incorporates the owner disposition and actual merged-main evidence.
The tracked [P15a ledger](p15a-ledger.md) is a historical local-delivery checkpoint;
its pre-merge open-gate statements require reconciliation, not deletion of evidence.

The preserved addition records native PR run 44466077762 attempt 1 on associated
head `cc31eab5dc87311bc54c05068a2b21fcce089d68`, actual test merge
`f1c078e9273adef7bc24e5002f2875654a709a8b`, nineteen applicable successes and five
explicit opt-in skips. Lifecycle job 135364841542 passed thirty no-skip tests.
This is separate evidence from f44403e's push run. The owner's current explicit
regular merge establishes merge authorization/disposition; no release is authorized.

## Selected additive runtime boundary

The existing [integration module](../packages/integration-job/build.gradle.kts)
produces both a consumable classes JAR and the pinned deployment shadow JAR.
The original deployment producer remains
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
Its Java source/resources, build inputs affecting that JAR, existing contracts,
checkpoint descriptor and UIDs must remain unchanged. Add a separate lifecycle
runtime module, artifact, contract/resource namespace, deployment/controller,
checkpoint directory/descriptor, topics, groups, fixture paths and build cache.
Reuse existing reviewed libraries and their exact lock/verification inventory;
qualify the actual new artifact independently. No new source module becomes a
replacement for the P14 producer merely because both use the same libraries.

The interface agent and primary selected an additive adapted `LifecycleMachine`
with explicit original-source provenance. Keep the legacy `Machine` untouched.
Preserve its accepted source adaptation/assembly semantics and bounded transactional
pump, while adding lifecycle selection, outbox metadata and checkpoint state in
new source. Prefer a narrow reviewed source adaptation to an undocumented broad
fork; record original hashes and reason for each semantic extension. Existing
[archive-maintenance build](../packages/archive-maintenance/build.gradle.kts)
provides a precedent for attributed reuse of unchanged legacy primitives, but not
permission to relabel changed source as unchanged.

### Why naive snapshot/restore composition is unsafe

[Machine](../packages/integration-job/src/main/java/io/detectbridge/integration/Machine.java)
is final; its `IntegrationOutputs` evaluator field, source binding, state,
projection and validation helpers are private/final. `restore` can construct a
new evaluator over retained assembler/inbox/outbox state under the same supplied
binding, but it is not an existing hot-swap API. It validates old output documents
without re-evaluation; this preservation behavior is useful and must survive.

`snapshot(checkpoint)` also changes the transient seal map and bounds it to two
entries. `restore` creates a new empty seal map. Re-snapshotting an existing pending
checkpoint after a swap can widen its sealed prefix to include post-checkpoint
intents; releasing that prefix at the old completion would falsely claim durability.
Calling `releaseRestored` during a live swap releases all intents as though an
actual completed Flink restore occurred. Neither shortcut is safe.

A release-time wrapper using the current active policy would misattribute queued
A documents as B after activation. Capture one immutable selection at committed
pump transition, and retain lifecycle metadata with each generated intent.
Checkpoint bookkeeping must retain the exact selection and prefix present at each
snapshot. Completion of A's checkpoint after B applied must acknowledge A's
snapshot, not B's current volatile state. Checkpoint abort or lost ack cannot
create a durable-B claim.

## Concrete supported profile and worker footprint

Preserve the P15a compatible source/mapping/parser/assembler/enrichment declarations.
A new runtime artifact/profile needs its own exact measured hash and test receipt;
P15a's closed artifact constant cannot simply be overwritten to accept it. Keep
candidate-plan identity distinct from full lifecycle closure, new runtime identity,
control command hash/revision and worker incarnation. Freeze the P15b profile's
relationship to existing staged P15a candidate facts explicitly.

Use independent one-slot worker jobs with explicit worker identities/incarnations,
disjoint source topics and checkpoint roots, and a common ordered control stream
consumed with distinct worker groups. This supports actual mixed versions without
claiming Flink rescaling or shared-local-filesystem distributed operation. Partition
ownership and event routing remain explicit; do not feed the same source occurrence
to both workers and call duplicates a membership demonstration. A joining worker
must converge before new input readiness. Actual max-worker qualification is
separate from the contract's sixteen-participant admission ceiling.

The new lifecycle envelope should bind immutable original body/kind/key and actual
command revision/hash, bundle/compatibility and worker/incarnation. A→B→A gets
separate activation-envelope identity while source event/evidence and original
semantic body identities remain intact. Old intents retain original envelope bytes
when publication is retried after B or rollback. Freeze exact identity preimages
and literal vectors before implementation; new runtime output must use new topics
and closed contracts, not appear as known P13 output.

## Control privacy and authority boundary

The existing [Compose broker](../deploy/local/compose.yml) has no host port and is
on an internal Docker network, but uses PLAINTEXT listeners and no configured
SASL or principal ACL authentication. An authority UUID is an identifier, not a
secret. Topic names, matching UUIDs and private networking alone do not prove who
published bytes. Explicitly freeze the trusted local-admin/container boundary;
do not claim broker-authenticated authority from this deployment.

The primary and interface agent selected authenticated Ed25519 envelopes using
JDK17's built-in implementation, with no new cryptographic dependency or
per-event Python. The proposed authority envelope binds the unchanged P15a command
and complete bounded registration snapshot: worker/incarnation, acknowledgment
public key, input topic and topic ID. Worker configuration pins the authority
public key and its own acknowledgment private key. Verify each signed acknowledgment
against the registered current pair/key; an old incarnation/key cannot satisfy it.
Workers must not receive the authority signing private key. Source-input rows
cannot become controls, and artifact distribution must bind authenticated closure
identity before any apply. The interface proposal bounds decoded artifact chunks
to 256 KiB and framed records to 512 KiB; the owning design must freeze exact
cross-field sizes, identity preimages, keys and negative cases before code.

Preserve the deployment/broker topic bindings and ordered revision/hash chain.
Signing proves authorized bytes, not application, checkpoint completion or
convergence. Keep separate private keys per role/worker outside bundles/Git/logs,
with mode/ownership checks and fixed sanitized diagnostics. The signed protocol
still needs actual invalid-signature/key/identity/replay qualification and explicit
key-retention/rotation bounds. No broker SASL/ACL authentication is claimed.

## Archive and replay compatibility gate

[archive_profiles.py](../tools/archive_profiles.py) pins original reader E5,
historical executor 32bad6f5, current executor ea9d4740 and producer 51a984de.
The managed maintenance JAR embeds closed original graph schemas and controlling
Python resource hashes. Historical/current executors are thin artifacts depending
on exact producer semantics. Editing shared old schemas/controllers to understand
lifecycle output changes those identities and invalidates old profiles.

Keep original archive/replay artifacts buildable at their exact pins. For lifecycle
output, add an explicitly versioned supported profile with its own graph reader,
selection/control facts, executor/controller pins and replay output isolation.
An additive reader may retain exact raw/archive storage framing while recognizing
new envelope dependencies; it must not weaken old unknown-graph retirement blockers.
A lifecycle selection must retain bundle, command chain, membership/incarnation,
actual decision metadata and all original evidence/manifests needed to reproduce
its selected decisions. Current-policy replay is a distinct operation; it cannot
silently borrow original activation results as its oracle.

Before full P15 completion, demonstrate the supported lifecycle archive/historical
boundary on actual artifacts or deliver it as an explicit dependent owning slice.
Deferring it is legitimate slice planning, but does not complete P15. Retain
immutable old checkpoints and artifacts, prepared/pending bundles, active mixed
worker versions, outbox references, recovery roots and replay/archive holds.
Unknown references continue blocking deletion. Nondeleting retention is safer
than unqualified garbage collection and is consistent with P15a's current limits.

## Required failure qualification footprint

Freeze positive, negative, boundary and failure expectations from accepted source
semantics before code. The actual-runtime suite needs, at minimum:

- Two real worker jobs: A→B mixed period, partial artifact distribution, actual
  apply/ack failure and timeout, then explicit convergence and distinct A→B→A.
- Duplicate/conflicting request, stale/skipped/reordered controls, foreign authority,
  wrong deployment/topic/cluster, old-incarnation ack and membership replacement.
- Input under A with commit under B; open audit group closes under B with original
  members/quality/late links; capacity-blocked proposal retried under B; old A
  outbox byte equality across B and rollback.
- Actual checkpoint completion versus abort, apply-before-checkpoint crash,
  checkpoint A completing after volatile B, partial sink publication, restored
  exact intents and incompatible/missing/corrupt state/artifact rejection.
- Broker outage during control publication and acknowledgment; bounded source,
  control, artifact and outbox exhaustion with visible backlog and unchanged
  accepted evidence. No manufactured receipt, implicit participant removal or
  new revision concealing uncertain publication.
- New-profile archive exact bytes, independently selected historical decisions,
  isolated replay/resume and retention-reference blockers; unchanged old P13/P14
  artifact builds and actual applicable regressions.

One primary-owned heavy slot serializes actual Docker/Kafka/Flink suites. Keep
source/dirty state, actual plan/bundle/JAR/image/probe identities, platform,
commands, original logs/report hashes, failures and unavailable coverage separate.
Synthetic native AMD64 is not private-recording qualification. No throughput,
rescaling, HA, unbounded outage, physical power-loss or disk-loss claim follows.

## CI and evidence integration

A new module/settings/build/dependency input must select every affected consumer,
including lifecycle, original integration and archive/historical/current/maintenance
checks. Extend classifier tests and always-running required aggregate for a new
real runtime job, without placeholder success. Preserve exact prepared Gradle
cache fan-out and fail closed on cache misses before bootstrap; use locked/offline
builds and reviewed dependency checks. New schemas/profile files must select all
consumers that embed or validate them. Independently qualify each actual new
artifact on local ARM64 and native AMD64 within its declared supported cases.

This discovery created only this draft. It ran no builds, compiler/evaluator,
Docker/Kafka/Flink suite or performance test. Source inspection and documentation
checks do not establish runtime behavior or satisfy P15b/P16 gates.
