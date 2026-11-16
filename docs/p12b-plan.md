# P12b — Checkpointed Linux assembly and failure qualification

Status: plan authorized for implementation, 2026-11-15. Implementation and exact
qualification evidence are now recorded in the [ledger](p12b-ledger.md). This plan
refines A03/A06 and ADR 0004's at-least-once delivery policy; preserves P03 identities
and the P12a source/mapping semantics.

## Base, prerequisites and scope

P11 PR #38 merged as 46fb080; P12a PR #39 merged as
9ea1c68e0846e27ffa4ae94390429b5330ceb5b0. P12a PR CI passed. Its merged-main run
[43750911904](https://github.com/TravisMa07/DetectBridge/actions/runs/43750911904)
was still running when this plan was prepared. Verify that run before runtime
implementation/qualification; do not infer a merged-main pass from PR checks.

The next implementation PR is P12b, based on qualified current main, on a
short-lived feat/p12b-linux-qualification branch. Deliver a bounded Kafka/Flink
qualification path around the real P12a audit assembler and selected auth adapter.
It does not add P13 production evaluation/writer wiring, detection identities,
archive, management API, UI, public evidence publication or capacity claims.

P11 recorded host binding, eligible recorded audit host/generation/completeness,
and owner review of independent expectations remain separate acceptance items.
The actual local OpenSSH9 recording qualifies its selected grammar only. P12b may
prove recovery using independently authored synthetic evidence without claiming
that these remaining recorded/semantic gates have passed. Full P12/P13 stay gated.

## Ownership and shared boundaries

The orchestrator owns this PR and serial changes to root Gradle registration,
locks/inventories, developer commands, classification/required-check aggregation,
Docker configuration and status/architecture notes. No parallel edits to these
files or overlapping heavy writer/detection/assembly qualification runs.

- packages/linux-adapters: minimal transition/drain API refinements and regression
  tests; retain the existing durable offline Commit API for existing consumers.
- packages/linux-assembly-job: proposed real Flink operator/job, immutable runtime
  binding, Kafka codecs and matching qualification helpers. Reuse pinned Flink
  2.2.1, connector 5.0.0-2.2 and existing reviewed dependencies; inventory actual
  module uses and review any genuinely new artifact before adding it.
- contracts/linux-assembly/v1: explicit qualification input/control/output/runtime
  schemas. These do not silently enter or extend the closed P03 registry.
- tools/linux_assembly.py and owning checks/tests: isolated runtime lifecycle,
  independent scenarios/accounting and real CI/developer gate integration.
- docs/p12b-design.md, runbook and ledger: exact design decisions, heads, evidence,
  failures and limits. Cross-reference this plan from the acceptance ledger.

Input contains a validated retained raw/context record, or an explicit versioned
source-boundary/run-end control. Data and controls share ordered input; controls
cannot impersonate data or silently erase receipts/closed keys. References resolve
only through an explicit retained local object registration with integrity/range
verification, never arbitrary URI fetching. Original input remains independently
retained; diagnostic references do not create an archive.

Outputs retain P03 normalized events, P12a membership manifests and preservation
associations. Invalid transport rows use bounded, value-free quarantine metadata
referencing exact Kafka location/hash and retained original. Missing identity,
unsupported source, malformed extraction, incomplete assembly and invalid wire
input remain distinguishable. No evaluator outcomes are invented for unevaluated
rows. Every output has stable identity and version/binding attribution.

## Checkpoint and output design

Start with one assembly operator at parallelism one and an explicitly ordered
single-partition qualification input. This keeps the existing aggregate job-wide
limits meaningful. Interleave hosts/runs/generations within that ordered stream.
No rescaling, partitioned global quota or production throughput claim.

The important API boundary requires explicit work: P12a Commit promises durable,
atomic output plus next state. Flink collector calls or ListState.update returning
are not that durability boundary. Do not implement the adapter by making that
claim or by acknowledging input after only volatile publication.

Introduce a bounded prepared-transition API, or equivalent tested mechanism,
returning next assembler state plus immutable output intents without advancing
live admitted state. Keep the offline durable callback API intact. The Flink
wrapper checkpoints state, output intents/progress, lifecycle and timer deadlines
under a versioned operator envelope. Release checkpointed intents through the
existing acknowledged at-least-once Kafka sink, with barriers/checkpoint completion
controlling retirement. Prove the ordering with a failure-state model before
Kafka wiring. A crash can duplicate a stable output; it cannot lose its intent or
advance a successful checkpoint past an unavailable required sink.

The envelope binds source/mapping content hashes, parser/assembler/policy/state
versions, limits, timer policy, Kafka cluster/topic identities and consumer group.
Use stable operator UIDs and Flink-managed source offsets with auto-commit disabled.
Validate complete bindings/state before consuming new data. Unknown serializer,
state/policy/source/mapping versions or changed broker/topic/group identities fail
explicitly; never silently clear state or fall back to latest/earliest on restore.
Retained-input replay is a separate explicit action with a new run scope.

Persist absolute first-admission deadlines and reconstruct actual Flink processing
timers on restore. Timers must close due groups during idle input, preserve elapsed
age across downtime, and retain closed-key/late-link knowledge. Inject clocks in
unit tests; qualify real timers and restarts separately. Never refresh age because
of redelivery or restart. Define timer/input ordering in literal scenario oracles.

## Bounds, draining and failure behavior

Retain P12a limits: 256 members/1 MiB original bytes per group; 1,024 open groups;
32 MiB pending serialized state; 30-second absolute age; 16 active runs; closed
knowledge at most 100,000 entries AND 32 MiB including receipts/metadata. No TTL,
silent eviction, automatic reopen or run-end tombstone deletion.

Propose a separate initial output-intent cap of 8 MiB serialized and 64 documents,
with each wire document at most 1 MiB. These are safety proposals, not measured
capacity. Before implementation, prove one maximal group closure fits and account
for envelope/serializer overhead, Flink buffers and transient working copies.
Bound timer/run-end/resource drains incrementally: one unbounded tick that closes
1,024 groups cannot allocate an unbounded output batch or bypass the outbox cap.
Complete overdue closure work before admitting a later row when required by the
existing semantics. Record any policy/state-version change explicitly.

At capacity, retain state/intents and apply bounded backpressure or fail visibly
with retryable input still in Kafka; never block the Flink mailbox so checkpoints
and timers cannot run. Sink recovery must allow draining and eventual progress.
Permanent closed-key exhaustion stays explicit backlog until an authorized
lifecycle/replay decision; qualification cannot hide it through eviction. Failed
output/checkpoint leaves the last usable checkpoint intact. No payloads in logs.

## Implementation sequence

1. Record design/API/state-envelope decisions and independent literal input,
   membership/ID/hash/quality/closure and output-progress expectations before code.
   Resolve the durable transition/outbox ordering and maximum-batch proof here.
2. Add the minimal core transition/budgeted-drain interface and operator state
   model. Test callback failure, retry, restore compatibility, due timers, outbox
   retirement and every exhaustion boundary without containers.
3. Implement the real Flink wrapper and isolated Kafka job. Add exact source/
   mapping/policy/serializer binding and real metrics for pending groups/bytes,
   closed knowledge, outbox/backlog, oldest deadline and restore failures.
4. Add exclusive detectbridge-p12-* lifecycle/build/publisher/verifier tooling and
   real shared gates. Use distinct topics/groups/checkpoints and immutable runtime
   manifests; do not mutate existing P07–P11 service/topic/state resources.
5. Run serialized ARM64 qualification, fix concrete failures, then open a draft PR
   targeting main with actual AMD64 CI selected. Confirm checks were created before
   claiming CI monitoring. Record final heads, checkpoints, manifests and limits.
   Owner merge authorization and subsequent merged-main qualification are separate.

## Acceptance matrix

| Scenario | Required independent evidence |
| --- | --- |
| Partial group TaskManager restart | Exact original members/args/PATHs survive; one logical closure and stable IDs |
| JobManager shutdown and explicit restore | State, offsets, lifecycle, outbox and bindings recover from the named checkpoint |
| Timeout across downtime and idle input | Original deadline retained; due closure fires without new data; quality remains independently assessed |
| Duplicate before/after checkpoint | Same occurrence retry is idempotent; distinct original positions remain separate members |
| Crash before staging, after staging, before/after publish | Every admitted occurrence is output, durable pending intent, retained state or visible backlog; stable recovery duplicates allowed |
| Late evidence before/after restore | Immutable original manifest/event; late reference links correctly and never reopens an eligible group |
| Interleaved host/run/generation | No cross-scope membership or output contamination; P03 identity/replay rules preserved |
| Event/manifest/diagnostic/quarantine sink outage | No successful checkpoint crosses failed required output; restart and sink recovery account for all accepted input |
| Group/pending/outbox/closed/run bounds | Exact limit and one-over cases, bounded batch drains, explicit backlog, no silent eviction; progress resumes where policy permits |
| Source boundary and run end | Ordered closure/drain, retained receipts/tombstones, no new eligible group after end |
| Corrupt/incompatible state or runtime destination | Explicit failure before new consumption; no arbitrary CLI exit accepted as evidence |
| Auth and invalid/unsupported wire input | Actual adapter used; preserved evidence/reference accounting and distinct disposition categories |

The oracle enumerates original IDs/hashes, input positions and expected complete
memberships/quality/outcomes before execution. Compare logical unique outputs and
physical duplicates separately; counters alone cannot establish preservation.
Rehash retained originals, verify all manifest/late links and enumerate any backlog.
Use the real reviewed auth recording optionally where exact evidence is available;
ordinary CI must not imply it replayed a recording absent from its filesystem.

Required checks: locked repository check and combined Java/semantic consumers;
meaningful core/operator/serializer tests; owning dependency/resource/notice checks;
subsystem lint/types where applicable and secret scan; actual ARM64 and AMD64
Kafka/Flink qualification, including negative restore and sink-failure evidence.
Report skipped/unavailable checks explicitly. A documentation/test-only pass is
not runtime recovery or performance qualification.

## Completion and remaining work

P12b is reviewable when the implementation, independent expectations and complete
failure/accounting evidence agree and existing gates stay green. After separate
merge authorization, qualify merged main. P12 completes only when P12a+b,
independent semantic review, and reviewed eligible audit/auth evidence all satisfy
their gates. P11's host-binding blocker also remains before P13 acceptance.
