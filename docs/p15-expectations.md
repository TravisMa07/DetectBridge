# P15 independent lifecycle and activation expectations

Status: independently derived before P15 production implementation. Base:
`f44c9f91e10414cd2b03481951a2e2a1c7b2a4a0`. P14 bounded acceptance is complete; P15 owner semantic/completeness
acceptance remains pending. These expectations are not runtime evidence or P15 owner
approval. The primary owns integration; the expectation author owns this matrix.

Requirements: A02–A07 in [architecture](architecture.md), [roadmap P15/P16](roadmap.md),
[P10b selection](p10b-design.md), [P13a output identities](p13a-design.md),
[P13b checkpoint semantics](p13b-design.md), [P14c2 preservation](p14c2-design.md),
and their actual compiler, evaluator, integration machine and retention consumers.
The [owning design](p15-design.md) selects routine protocol details. This matrix
was derived from accepted requirements/source semantics, without running P15 code
or producing expected results from a new implementation.

## Scope and selection assumptions

**P15a** qualifies immutable candidate closure, import/validate/test/stage lifecycle,
private administrative state and preparation of ordered control requests. It cannot
prove Kafka publication, worker application, durable application or convergence.
**P15b** must qualify the actual control-topic and integrated Kafka/Flink consumers,
worker membership/incarnations, recovery, attribution, rollback and retention.
P15 is incomplete until both slices and milestone acceptance gates pass. P16
implementation depends on accepted/qualified P14/P15 prerequisites, not merely a
P15a preparation artifact.

The primary selects **closure-time policy** as the design assumption: capture one
active evaluator for each atomic prepared transition; fixed compatible parser,
source, mapping and assembler profiles preserve original source semantics. An
open audit group's evaluation uses the policy active at its closure transition.
A deferred, uncommitted proposal is retried under the policy active when that
transition commits. Already committed outbox documents retain their original
policy, canonical bytes and identities across activation. This choice is frozen
behavior to test, not an observed implementation result. No activation may split
one committed proposal across evaluators or rewrite membership, deadlines, quality,
late links or old output.

Existing attribution `bundle_sha256` means evaluator-plan identity. Existing
integration deployment bundle identity additionally fingerprints runtime build
inputs. Full lifecycle closure identity must remain distinct and retain the plan
identity. Historical P14 executors pin their original producer; qualification of
a new runtime does not qualify replacement of that producer or old checkpoints.

## P15a candidate, staging and control preparation matrix

| ID | Independent input/operation | Expected result and rationale |
| --- | --- | --- |
| A01 | Valid candidate imported, validated, tested, staged | Separate durable lifecycle facts; no active runtime change. Synchronization never autoactivates (A05). |
| A02 | Stage before required validation/test success | Explicit prerequisite failure; candidate and prior valid state preserved. A lifecycle step cannot imply its predecessors passed. |
| A03 | Missing plan, mapping/source snapshot, required runtime/parser/evaluator/selector/enrichment identity or rule provenance | Complete closure validation fails before stage/control publication; no partial executable bundle (A04/A05). |
| A04 | Changed bytes or length under a declared object identity | Integrity failure; original immutable object remains authoritative. |
| A05 | Unknown schema/version/field, unsupported Sigma or executable extension | Explicit rejection; no semantic downgrade or arbitrary execution (A04/A07). |
| A06 | Exact retry with identical request identity/content | Same authoritative result; no duplicate lifecycle step or new revision. |
| A07 | Reuse request identity with changed candidate or operation | Conflict; never overwrite the original operation. |
| A08 | Candidate changes upstream provenance/license/revision or local modification | New closure identity or rejection if inconsistent; retained provenance cannot be silently replaced. |
| A09 | Valid plan at existing 100-rule and 4 MiB compiler limits; corresponding limit+1 | Existing bounded compiler semantics retained; over-limit inputs rejected without partial publication. Test exact serialized framing used by the owning contract. |
| A10 | At-limit and limit+1 lifecycle closure/object/history/control budgets | Valid exact boundary permitted; exhaustion fails visibly before mutation. No eviction of immutable required history to admit another operation. Frozen new bounds: manifest 64 KiB; closure 8 MiB; 64 bundles; 4,096 journal entries; 16 participants; command/ack 64 KiB; signed 64-bit revision. Test each reachable boundary and reject overflow before mutation. |
| A11 | Prepare B after staged A with expected current revision | One ordered preparation record; intent/preparation distinct from Kafka publication and application. |
| A12 | Race two preparations against the same expected revision | Exactly one compare-and-advance succeeds; the other conflicts. Arrival timing cannot create divergent authoritative sequences. |
| A13 | Stale expected revision, reordered older request, same revision/different target | Reject stale/conflicting mutation; no backward selection. Exact retry remains A06. |
| A14 | Missing/corrupt target or incompatible parser/source/mapping/evaluator closure | Preparation fails; prior valid state and immutable records unchanged. |
| A15 | Rollback preparation B→retained compatible A | New forward revision selecting old closure; history never rewinds or overwrites B. Preparation alone establishes no applied rollback. |
| A16 | Rollback target absent, corrupt, retired or incompatible | Explicit rejection; no reconstruction from changed inputs passed off as the old artifact. |
| A17 | Corrupt checked head/history record, gap, conflicting revision or unknown foreign entry | Fail closed before mutation; no inference that missing history means empty configuration. |
| A18 | Crash before/after durable operation publication | Before publication no completed operation; after publication identical recovery verifies that operation. No duplicate or contradictory authoritative record. Exercise exact durability boundaries frozen in design. |
| A19 | Invalid local authority or private-root boundary; symlink/overlapping/foreign root | Reject before mutation; no exposed unauthenticated administrative endpoint (A07). |
| A20 | Imported rule/evidence contains secrets, newlines or log-like text | Bounded sanitized operational categories; no raw evidence/secret interpolation into routine diagnostics. |
| A21 | Test-result claim supplied without qualifying independent expectation/artifact binding | Reject or retain explicitly unqualified status; staging cannot turn arbitrary caller text into production qualification. |
| A22 | Inspect staged/prepared state while no worker runtime exists | Status explicitly reports only established preparation facts. Never report published/applied/durable/converged. |

P15a's focused behavioral reds must demonstrate missing lifecycle prerequisites,
immutable-content conflict, request conflict, compared-revision race/staleness,
corrupt-history rejection and rollback preparation preserving monotonic order.
A failed harness/bootstrap command is not a behavioral red. File-level integrity
checks alone do not prove power-loss durability.

The original [literal suite](../contracts/lifecycle/v1/fixtures/README.md) and
[closed suite schema](../contracts/lifecycle/v1/test-suite.schema.json) freeze
one new Windows `User: Alice` rule and two eligible normalized events. Alice has
matched=1, Bob has unmatched=1; all other counts are zero and diagnostics empty.
The sole positive match revision is SHA-256 of the exact original YAML, calculated
without running a compiler/evaluator. These are normalized-only tests, not adapter
or recorded-source proof.

| ID | Runner failure/boundary | Independent expected result |
| --- | --- | --- |
| A23 | Frozen Alice positive and Bob negative through pinned Java compact runner | Full output equals the literal compact JSON, including rule revision and every count, not counts-only comparison. |
| A24 | Changed candidate plan, source/mapping hash, expected JSON, suite bytes or evaluator artifact after prior pass | Previous receipt cannot authorize stage of changed content; fail integrity/binding or require a fresh actual test. |
| A25 | Caller-supplied passing receipt, fabricated report or changed report hash | Cannot satisfy test/stage; only verified trusted-runner result binds candidate/profile/artifact/exact suite and observed report. |
| A26 | Actual evaluator mismatch, nonzero exit, invalid JSON, timeout beyond 10 seconds, stdout over 2 MiB | Test fails with sanitized bounded status; no stage promotion or arbitrary stderr leakage. |
| A27 | 2 and 64 cases; 1 and 65 cases; event 1 MiB/+1; complete suite 16 MiB/+1 | Valid exact limits admitted, outside rejected before expensive execution; case IDs unique and complete outcomes schema-valid. |

## P15b actual runtime, attribution and preservation matrix

| ID | Independent input/failure | Required observable result and rationale |
| --- | --- | --- |
| B01 | Activate staged B after A | Monotonic intent revision; each worker validates complete B then atomically swaps (A05). |
| B02 | Identical activation retry; same ID/different target | Identical retry yields same result; conflicting content rejected. No duplicate transition. |
| B03 | Deliver old revision after newer; same revision/different bundle | No backward or ambiguous apply; expose stale/conflict state. |
| B04 | Broker unavailable during publication | No successful-publication claim; retain authoritative request for explicit identical recovery/retry. |
| B05 | W1 receives B; W2 receives nothing | Publication/receipt observations remain separate; W2 remains visibly A; convergence false. |
| B06 | W1 applies B; W2 cannot resolve/validate B | Visible mixed A/B; W2 retains complete A, not a partial B. |
| B07 | W1 applies B, acknowledgment send fails | W1 outputs attribute actual B; coordinator cannot infer convergence without qualifying acknowledgment. |
| B08 | Finite activation timeout with unavailable worker | Explicit incomplete/timeout; no silent success/rollback. Later success does not erase original timeout. |
| B09 | Empty, one and multiple participant sets | Exact participants visible; no vacuous success unless explicitly frozen as supported semantics. |
| B10 | Old-incarnation acknowledgment arrives after worker restart | Cannot satisfy replacement incarnation's obligation. |
| B11 | Worker restarts or joins after B intended | Validate intended closure before eligible processing; distinguish recovered/applied/durable state and join obligation. |
| B12 | Joining worker lacks B or has incompatible executable | No successful active/join acknowledgment; healthy existing workers remain valid. |
| B13 | Crash after receipt but before atomic apply | Recover prior durable policy; received does not mean applied. |
| B14 | Crash after apply but before completed checkpoint | Restore actual durable policy state; volatile apply cannot establish durable-B acknowledgment. |
| B15 | Completed snapshot containing B and pending output | Restore validates closure/state/binding, retains B and exact committed intents; independently confirm COMPLETED checkpoint. |
| B16 | Snapshot abort or incomplete checkpoint | No durable-application claim and no checkpoint-gated intent release. |
| B17 | Changed artifact/schema/parser/evaluator/closure, missing artifact or corrupt restore state | Reject before admission/output; old checkpoint compatibility guards remain closed. |
| B18 | Partial sink release followed by failure | Retained intents survive; repeated publications retain stable IDs/canonical bytes/actual attribution. At-least-once is not exactly-once. |
| B19 | Literal source field matches rule in A and fails changed predicate in B | Independently derive exact matches and six counts from frozen source/YAML; all outputs name actual plan/full closure as designed. |
| B20 | A intents pending when B activates | A documents remain byte-identical and attributed A on later publication; no relabeling. |
| B21 | Input admitted under A but transition commits under B | Closure-time selected B; admission time is not evaluation or publication time. |
| B22 | Audit group opens under A, closes after B apply | Evaluate with B; exact original members, closure, deadline, quality, source context and late links preserved. |
| B23 | Full outbox defers uncommitted A proposal, then B applies | No partial source/state/output commit; eventual atomic retry selects B and has internally coherent output attribution. |
| B24 | Late occurrence arrives after original group emitted under A and B active | Original emitted event immutable; retain late occurrence and original association for isolated replay (A03/A06). |
| B25 | Unknown source, blocked mapping, insufficient quality and operation-budget exhaustion | Distinct blocked/skipped/error outcomes; no downgrade to nonmatch; serialized rule order/shared per-event budget preserved. |
| B26 | Tagged/detection/diagnostic inspection across A/B | Original source namespace/instance, context/source/mapping hashes, parser/normalizer, compiler/evaluator/selector/enrichment and plan attribution complete and consistent. |
| B27 | Two isolated runs using same original source | Preserve evidence/event identity; processing/detection isolation follows frozen pipeline/run/decision identity preimages. |
| B28 | Actual rollback A→B→A | Third forward control revision selects retained A; B outputs/history remain immutable. |
| B29 | Rollback partially applied or acknowledgment unavailable | Mixed versions/incomplete rollback visible; no global-success claim. |
| B30 | Retire active, intended, pending or rollback-required closure | Block before deleting required artifacts. Timeout does not automatically release dependency. |
| B31 | A required by old snapshot, inbox, open group or output while B active | Retain complete A closure until safe explicit recovery disposition; active policy alone is insufficient retention inventory. |
| B32 | A referenced by replay/archive pin or external hold | Block retirement; missing state is not a hold release (A06/P14c2). |
| B33 | Hold/pin/membership/checkpoint changes after retirement dry plan | Reject stale plan; replan explicitly under owning locks. |
| B34 | Accepted evidence plus config during broker outage | Account evidence as output, durable quarantine or visible backlog; publication/apply/ack statuses remain truthful. |
| B35 | Artifact/control/checkpoint/inbox/outbox space exhaustion | Visible stop-admission/backpressure; no eviction/silent shedding of accepted input, required closure or intents. |
| B36 | Rebuild/execute old P13/P14 consumers after P15 | Original pinned producer/reader/executors and compatibility checks retained; independently qualify actual rebuilt artifacts. |
| B37 | Archive/replay a new P15 producer/output graph | Explicit supported versioned reader/executor qualification or explicit rejection. Unknown graph must not bypass conservative retention recognition. |

## Oracle and evidence requirements

Freeze literal source inputs, source/capture bindings, rule YAML/provenance,
source order, expected six counts/matches and canonical identity vectors before
new runtime execution. Supplementary old/new evaluator comparisons do not replace
these independent expectations. Keep source occurrence identity, Kafka location,
semantic event identity, processing identity, lifecycle closure and control revision
separate. For A→B→A, independently specify whether identical semantic policy yields
identical decision identity or a distinct activation identity; never infer it from
runtime output.

Record source revision/dirty state, actual artifact/plan/closure/image identities,
platform, command/scenario, report/log hashes and failed attempts. Actual broker,
checkpoint, partial-sink and worker fault cases require runtime evidence; model
unit tests cannot establish them. ARM64 local, native AMD64 synthetic and private
recorded-source coverage remain distinct. No throughput, rescaling, HA, unbounded
outage, physical power-loss or local-disk-loss protection follows from this suite.

The owning design freezes concrete lifecycle budgets, local authority/test receipt
bindings, membership revision semantics and the durable acknowledgment boundary.
Review those contracts together with this matrix before the pre-implementation
freeze; no passing model or preparation test establishes a P15b runtime gate.
