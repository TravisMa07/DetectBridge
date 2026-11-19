# P15b independent runtime expectations

Status: independent draft before P15b production code. Base is owner-merged P15a
`f44403e2975db46554c9c5033f87886d880c4087`; actual merged-main push run
44472864062 was pending when discovery began and subsequently passed all nineteen
applicable jobs and required-checks in attempt 1 on that exact merge. No dependent implementation
or qualification is established here. Preserve the [P15 owning design](p15-design.md),
[independent milestone matrix](p15-expectations.md), A02–A07 and accepted P09–P14
source, detection, recovery and replay limits. The [runtime owning design](p15b-design.md)
separates P15b1 worker-runtime delivery from the dependent P15b2 archive/replay
profile; B1 alone does not complete P15 or authorize P16. The final runtime design must resolve
the explicitly identified interface choices below before the expectation freeze.

Expectations derive from accepted requirements and original fixture/source meaning,
not new worker output. P15a fixtures remain unchanged. This author owns only this
document; the primary owns integration and the runtime design owner owns protocol
choices. Agent review and successful checks do not establish owner acceptance.

## Independent literal A → B → A scenario

Use two compatible immutable bundles with exactly the same four original source
and mapping snapshots: Windows Security/Sysmon and Linux audit/authentication.
Keep parser/normalizer/assembler/evaluator/selector/enrichment profiles and runtime
executable identities fixed. The original synthetic [frozen fixture packet](../contracts/lifecycle-runtime/v1/fixtures/README.md)
contains exact A/B YAML, original-to-modified provenance, source snapshot references,
actual source admissions, complete compact expectations and identity vectors;
its expected results were created without compiling/evaluating the new plans. A and B differ only in the following original
synthetic rule literals, with the same rule IDs and explicit original-to-modified
YAML hash lineage. Exact bytes, provenance, semantic plan hashes and full closure
hashes must be frozen before execution; do not generate them from worker output.

| Rule | Stable rule identity | A predicate | B predicate |
| --- | --- | --- | --- |
| Windows process creation | `71500000-0000-4000-8000-000000000001` | Existing original P15a `User: Alice` | Local modification `User: Bob` |
| Linux process creation | `72000000-0000-4000-8000-000000000001` | Existing original P12 `Image: /usr/bin/whoami` | Local modification `Image: /bin/false` |

A's Windows YAML is [the original P15a rule](../contracts/lifecycle/v1/fixtures/rule.yml).
A's Linux YAML is [the original P12 rule](../packages/linux-adapters/fixtures/rules/image-match.yml).
Both are original Apache-2.0 synthetic fixtures. For B retain each original hash,
repository revision/path and license, then bind one documented modification to its
new exact-byte revision. Candidate tests must cover the positive and negative
meaning of each changed rule using independently authored normalized cases; these
candidate tests remain distinct from actual source-runtime qualification.

Freeze literal results below as six counts in order matched, unmatched,
inapplicable, configuration_blocked, quality_skipped, evaluation_error. The
fixture publisher may create distinct admitted occurrences using explicit source
cursors, preserving the original bytes and trusted contexts. It must not mutate
normalized fields and claim those mutations were actual adapter results.

| Actual source case | A expected counts | B expected counts | Expected matches |
| --- | --- | --- | --- |
| Original eligible Security fixture with subject Alice | `1,0,1,0,0,0` | `0,1,1,0,0,0` | A: Windows ID/revision only; B: none |
| Independently specified synthetic Security subject Bob, with all affected raw hashes/IDs rebound | `0,1,1,0,0,0` | `1,0,1,0,0,0` | A: none; B: Windows ID/new revision only |
| Original eligible audit execution with executable `/usr/bin/whoami` | `1,0,1,0,0,0` | `0,1,1,0,0,0` | A: Linux ID/revision only; B: none |
| Independently specified eligible audit execution `/bin/false` | `0,1,1,0,0,0` | `1,0,1,0,0,0` | A: none; B: Linux ID/new revision only |
| Original authentication event, with both rules outside its logsource | `0,0,2,0,0,0` | `0,0,2,0,0,0` | None |
| Insufficient-quality audit process event | `0,0,1,0,1,0` | `0,0,1,0,1,0` | None; one applicable-rule quality diagnostic |

Literal equality and exact logsource applicability establish these outcomes. The
unchanged selection order and one shared per-event evaluation budget remain
required. There are no blocked/error outcomes in the eligible core cases; separate
adversarial cases exercise those outcomes. Verify full compact results, ordered
matches/revisions, diagnostic membership, original fields, quality and attribution,
not counts alone. If any selected source fixture does not satisfy the stated
source assumptions, correct the independent input/freeze before execution rather
than adjusting expectations to a new observed result.

For A revision 1 → B revision 2 → rollback A revision 3, every eligible Alice
occurrence processed at each phase therefore produces match → nonmatch → match.
The corresponding whoami audit result is match → nonmatch → match. The frozen
packet uses six explicit worker/phase run IDs (Windows worker20: suffixes
101/102/103; audit worker21: 201/202/203), overriding only context.run_id, to avoid
turning same-run source deduplication into artificial reevaluation. Original raw
bytes/cursors/member/event IDs remain unchanged, with per-phase context hashes
frozen in expectations.json. Permanent signed run-to-worker ownership forbids
splitting a shared phase run across the two workers. This is a pre-freeze routing
contract correction, derived without runtime output. Same-run exact raw redelivery
must still deduplicate.
Rollback uses exact original A bytes and closure, not a rebuilt approximation. Source offsets,
assembler deadlines, original membership, late associations and historical B
results do not rewind. Both A and B remain retained.

## Control, publication and membership matrix

| ID | Operation or fault | Independent required observations |
| --- | --- | --- |
| C01 | Publish staged A for explicit W1/I1 and W2/I2 participants | One authoritative ordered command. Preparation, acknowledged broker publication, each receipt/application, each durable acknowledgment and overall convergence remain separate facts. |
| C02 | Exact request retry after confirmed publication | Same command hash/revision/bytes; no second logical transition. Physical at-least-once duplicate publication is allowed only with identical authoritative content. |
| C03 | Broker accepts command but client loses acknowledgment | Publication is uncertain until verified. Retry identical request/bytes; do not allocate a replacement revision, silently skip it or report convergence from local intent. |
| C04 | Broker rejects/unavailable before acceptance | No successful-publication claim; retained previous desired/applied state is inspectable. Actual accepted source input remains preserved/backlogged. |
| C05 | Same request ID/different command; same revision/different bytes; wrong predecessor; revision gap; stale authority/deployment | Explicit rejection without backward selection or new successful acknowledgment. Never choose conflict by last arrival. |
| C06 | Exact old command redelivery after newer durable state | No rewind; duplicate/stale observation distinct from current apply. |
| C07 | W1 applies B while W2 does not receive it | W1 actual outputs B, W2 A; mixed state visible and convergence false. |
| C08 | W2 receives B but closure missing/corrupt/incompatible | W2 retains complete A; fixed failure category, no partial B or acknowledgment implying valid application. W1's independent success remains visible. |
| C09 | W1 applies B; its acknowledgment publication fails | W1 actual B decision attribution persists; coordinator cannot infer acknowledged/durable convergence from source output or local apply alone. |
| C10 | Finite deadline expires while W2 unavailable | Explicit incomplete/timeout; no implicit membership removal, fake success or revision rewind. Preserve this attempt if later convergence succeeds. |
| C11 | Old W1/I1 acknowledgment after replacement W1/I3 registration | Cannot satisfy I3's obligation, even if bundle/revision match. |
| C12 | Restart/new incarnation and ordered membership command | Restore compatible state, catch up verified commands and validate intended closure before readiness; acknowledgments identify the new explicit participant incarnation. |
| C13 | New W3 joins after previous cohort converged | New ordered membership/revision changes the obligation. Membership registration alone is not process readiness or durable acknowledgment. |
| C14 | Membership command uses same bundle as prior activation | Prior-command acknowledgments cannot satisfy new command/hash/revision, even though plan bytes are unchanged. |
| C15 | Attempt empty membership, duplicate worker IDs with distinct incarnations, 17 workers, boolean/fractional/overflow revision | Reject according to frozen closed contract; no vacuous convergence. Test valid 1/16 participant boundaries separately. |
| C16 | Unauthorized source-input record tries to act as control or worker ack | Source admission cannot cross authority/control namespace; no lifecycle mutation. |
| C17 | Two administrator processes race expected revision | Exactly one authoritative successor; explicit conflict for the other. No divergent durable branch. |
| C18 | Replacement process tries fresh evaluation before its newer signed membership revision | Reject/not-ready. Restored immutable intents may retain their original incarnation and identity; registration cannot relabel them. |
| C19 | Policy converges while source output/archive/indexing remain pending | Convergence establishes only the defined durable worker-policy obligation; it cannot imply source completion, archive durability or indexing. |

The owning design selects two actual independent one-slot, parallelism-one worker
jobs with dedicated single-partition inputs and private state/evidence/bundle
volumes. Route each complete run/host/source-generation scope to one worker before
admission; run-end/source boundaries follow it. Every physical source location
has one explicit consumer scope. No resharding of open groups, worker-filesystem
sharing, 16-worker capacity or rescaling claim follows from a two-worker pass.

Effective revisions and `command_sha256` in this matrix refer to the publisher's
complete unsigned effective control body, including adopted proposal/hash,
registration snapshot and execution binding. P15a proposal revision/predecessor
are inspection-only and cannot substitute for effective control ordering. Add
negative cases for skipping an unpublished proposal without implicitly adopting
it, exact adoption retry, changed registrations on retry, ambiguous predecessor
publication blocking the next allocation, rollback to a never-published staged
bundle, and membership selecting a bundle other than current intended state.

## Signed messages and bounded bundle transfer

The runtime design selects Ed25519 authority/worker envelopes and bounded chunked
closure transfer over private Kafka. Signing is an authorization/integrity fact,
not evidence that a command was applied or a checkpoint completed. Control signatures bind domain `detectbridge.p15b.control/1`, NUL, then exact
canonical payload; acknowledgments and artifact chunks use their respective
`detectbridge.p15b.ack/1` and `detectbridge.p15b.artifact/1` domains. Canonical
Ed25519 signatures decode to exactly 64 bytes; public keys are canonical base64
X.509 DER, at most 64 decoded bytes. Freeze the closed signed payload schemas
with these preimages before implementation. Never accept a claimed valid signature or
caller-supplied acknowledgment flag instead of verifying actual bytes.

| ID | Adversarial message/transfer | Required independent outcome |
| --- | --- | --- |
| S01 | Valid canonical command signed by pinned authority key | Verify signature over exact frozen domain/payload; then apply ordinary revision/profile/bundle validation. Signature does not waive semantic checks. |
| S02 | Alter one payload byte, signature byte, authority key, deployment or signed domain | Authentication failure before state mutation or success acknowledgment. |
| S03 | Valid signature replayed as another message kind or from another deployment/topic identity | Reject cross-domain/scope replay. An authority command signature cannot become a worker durable acknowledgment. |
| S04 | Ack signed by unregistered key, stale incarnation key, wrong worker or wrong command | Cannot satisfy current convergence; preserve explicit rejected/stale status without leaking key material. |
| S05 | Malformed/oversized encoding, duplicate JSON keys, unknown fields, noncanonical signed payload ambiguity | Reject before expensive allocation/application. Signer/verifier must agree on one exact byte preimage. |
| S06 | Operator/private key file permissive, symlinked, absent or replaced after registration | Fail local boundary or pinned-key validation; never silently adopt replacement identity. No private key enters logs, Git or public artifacts. |
| S07 | Valid complete A/B manifest plus every bounded chunk | Reassemble exact declared member bytes, verify every count/size/hash and complete closure, then validate plan/profile before atomic installation. |
| S08 | Chunk lost, transfer truncated or manifest absent | Pending/incomplete or explicit bounded failure; no partial bundle activation and prior valid policy retained. |
| S09 | Exact duplicate chunk; reordered valid chunks | Safe bounded reconstruction/dedup under the frozen transfer protocol; no duplicate bytes or second logical object. |
| S10 | Same transfer/object/index with changed chunk bytes/hash, wrong target bundle/member or mixed A/B chunks | Reject conflict/integrity failure; never overwrite verified immutable objects or apply a hybrid policy. |
| S11 | Chunk count/index/size outside finite limits, integer overflow, aggregate length beyond declared closure or too many incomplete transfers | Reject/backpressure visibly before unbounded buffering; no eviction of active/recovery artifacts to admit attacker content. |
| S12 | Valid signed manifest with incompatible sources/mappings, unsupported plan, corrupt member hash or self-rehashed AST different from original YAML | Reject ordinary closure/compiler compatibility despite valid signature. |
| S13 | Publisher crashes after some chunks or after complete object before command ack | Retry exact transfer/request bytes. Worker cannot interpret artifact arrival as desired-state publication or activation. |
| S14 | Restart with partially retained transfer/checkpoint state | Verify exact owned partials/declared bounds; incomplete data never becomes a completed artifact or acknowledgment. |
| S15 | Trusted authority signs artifact bytes for another common runtime binding/broker cluster, with cloned unchanged topic descriptors | Reject before adoption. Signature and bundle hash cannot substitute for exact current runtime_binding_sha256, which includes cluster_id. |
| S16 | Signed ack/control carries proposal-only hash or altered registration snapshot instead of the effective complete control hash | Reject scope/conflict; no convergence from a hash that omits registration/runtime binding. |

Transfer boundary cases use the design's exact 256 KiB decoded nonfinal chunks,
512 KiB signed record maximum, 4 MiB plan/16 chunks, 64 KiB manifest/one chunk,
one active bundle transfer and 8 MiB operation allowance. Test nonfinal short
chunks, complete-length/count arithmetic, base64 canonicality and exact-limit/+1
before reconstruction. Worker store is 512 MiB with 128 MiB free reserve,
64 bundles and 4,096 observed controls; do not confuse protocol limits with actual
16-worker capacity evidence.

Record real key identifiers/public-key hashes and command/message hashes in
private qualification evidence. Synthetic signing tests do not establish the
private broker/network access boundary; inspect actual deployment binds and topic
identity checks separately.

## Atomic transition, in-flight and checkpoint matrix

The accepted selection point is **closure-time**: one compatible evaluator and
command identity captured for one atomic committed source/assembly transition.
Control can apply between transitions, never midway through an already committed
proposal. Original `Machine.pump()` prepares source state/output then commits its
inbox/assembler/windows/outbox state together; outbox-capacity deferral does not
commit the source transition. Preserve that invariant in the additive runtime.

| ID | Controlled schedule/fault | Independent required observations |
| --- | --- | --- |
| T01 | A active; commit Alice event; apply B before its outbox publication | Later output remains A with identical committed bytes/IDs. Never reevaluate/relabel it B. |
| T02 | Admit source under A; apply B before its transition commits | Event uses B at committed evaluation, not A from admission time or intended global state. |
| T03 | Prepare A proposal, defer for outbox capacity; apply B; retry after capacity returns | Discard uncommitted proposal; retry commits entirely B. No partial member/state/output changes or abandoned A decision presented as processed. |
| T04 | Audit group opens under A; publish/apply B before EOE/timeout closure | Original whoami membership/closure/quality remains exact; closed eligible event uses B nonmatch. No dropping/reopening group to simplify activation. |
| T05 | Audit group closes and commits under A; B applies before checkpoint/sink | Original manifest and A matching output remain immutable. B cannot change closed membership/identity. |
| T06 | Controlled original late occurrence arrives after T04/T05 and rollback | Retain exact late raw/context, link original closed group; no mutation of prior event, manifest or decision. Association survives checkpoint restore. |
| T07 | B applied in memory; checkpoint containing B aborts | May expose actual volatile B apply, but no durable-B ack from aborted snapshot and no checkpoint-gated output release. |
| T08 | B snapshot exists but checkpoint not confirmed completed | Inventory/snapshot file is observation, not durable application proof. Do not promote on file presence. |
| T09 | Completed checkpoint includes B selection plus A/B pending immutable intents | Independently confirm COMPLETED checkpoint. Release only its sealed prefix; all A/B intents retain actual original attribution. |
| T10 | Kill worker after B apply before checkpoint completion | Restore actual prior completed state, not unconfirmed B; then ordered catch-up. No durable-B claim from old volatile acknowledgment. |
| T11 | Kill after B checkpoint completion before ack publication | Recovery can establish durable B from validated checkpoint; acknowledgment may retry with stable semantic identity. No fabricated earlier publication claim. |
| T12 | Sink accepts some intents, rejects next, process restores | At-least-once duplicates retain exact canonical bytes/IDs; retained remainder survives. No intentional dropping or reinterpreting output under current policy. |
| T13 | Checkpoint callback reports completion after a later control apply | Ack names the selection actually contained in that checkpoint, not the latest mutable pointer at callback time. |
| T14 | Restore with changed executable/profile/topic ID/group/deployment/worker state schema, corrupt state or absent required closure | Fail before output/admission/readiness. Never adopt P13 checkpoint bytes or another incompatible worker state. |
| T15 | Restore B state while control replays older A then current B | No rewind from stale replay. Validate predecessor/sequence and reconcile with restored command state. |
| T16 | Rollback A revision 3 after B completed and open groups/outbox exist | New forward revision; no rewind of offsets, sequence counters, deadlines or previous output. Closure-time A used only for subsequently committed transitions. |

Actual broker/Flink faults must exercise the relevant paths; a pure controller
model or author-injected synthetic acknowledgment does not establish them. Fault
injection must expose phase boundaries without substituting invented state for
real source, checkpoint or sink observations.

## Identity, attribution and replay expectations

Existing P13 semantic identity includes pipeline, run/event semantic content and
actual plan/version attribution, while physical Kafka receipt identities include
location. Keep these meanings separate from full lifecycle closure and control
revision. Freeze an explicit additive runtime envelope/domain before code; do not
silently change old P13 identity preimages or repurpose `attribution.bundle_sha256`.

The primary and runtime design owner select the following exact logical key
preimage, independently audited before code:

```json
["detectbridge.p15b.output/1", "deployment_id", "stable_worker_id", 1, "command_sha256", "inner_kind", "inner_stable_key"]
```

The fourth element is the actual integer command revision, not a string.
`identity = "sha256:" + SHA256(canonical UTF-8 JSON array)`; canonical JSON has
compact separators and no terminal LF. Incarnation and raw document hash are
excluded. Exact body hash remains integrity evidence; semantic duplicate/conflict
comparison follows the accepted clock/manifest projection of the inner kind.
Changed meaning under the same logical key is a conflict, not another identifier.
Do not hash a complete receipt-clock-bearing body into the logical key.

Persist original incarnation, command, body and exact output bytes in immutable
intents. Recovery reemits those intents unchanged, including their original
incarnation. A replacement process uses a new incarnation/key and may perform
fresh source transitions only after a newer signed membership command registers
it. The new runtime has automatic Flink restart disabled; an attempt cannot
silently reuse an incarnation. Thus new decisions after replacement have a newer
command revision while restored old intents retain their old logical identity.
A new run/event semantic identity, stable worker, deployment or command changes the
appropriate lifecycle decision identity. A1 and rollback A3 retain exact original
A policy/event meaning where applicable but have different lifecycle keys.

These literal vectors were calculated using standalone Python `hashlib` and
`json.dumps(..., separators=(",", ":"), ensure_ascii=False)`, without any worker,
controller or evaluator output. They test canonicalization and isolation only;
the repeated-digit hashes are explicit synthetic vector inputs, not runtime
artifact identities. Common deployment is `71500000-0000-4000-8000-000000000011`,
worker is `71500000-0000-4000-8000-000000000020`, kind is `tagged`.

| Vector | Revision | Command hash | Inner key | Expected lifecycle identity |
| --- | --- | --- | --- | --- |
| A1 | 1 | 64 `1` digits | `sha256:` followed by 64 `a` digits | `sha256:a615b238db8a85da67f39445986b7c8db8337ce3826f16fc2236027185e65ead` |
| B2 | 2 | 64 `2` digits | `sha256:` followed by 64 `b` digits | `sha256:5107b90153695657b498c99915aa0c29d6e651acaf43dd51176ec471ea373b6f` |
| A3 rollback | 3 | 64 `3` digits | Same inner key as A1 | `sha256:0869dd875df447d7fc6c1bc88b76c0fe37179fb478b2bb2c1a7349553d1a22f7` |
| Other worker | 1 | Same as A1 | Same as A1; worker ends `0021` instead of `0020` | `sha256:8497bc6119c8e85c42a5d9ab8e12e73058ac7902b58042a582ef4aa91d931850` |
| Other deployment | 1 | Same as A1 | Same as A1; deployment ends `0012` instead of `0011` | `sha256:3fa7f4d98db55244d256f6a6b41d162938654ebc74476fa5527ada0a72fde9ac` |

An exact A1 intent retry and a change only to observational receipt clocks have
A1's logical identity. Origin-incarnation-only changes cannot rekey an old intent;
they instead violate immutable-intent integrity if applied to retained bytes.
Fresh work by an unregistered replacement incarnation must be rejected, preventing
same-key conflicting attribution after restart. Negative tests independently
change domain, inner kind/key, revision type and field order; object serialization
must not be confused with the fixed array preimage.

The independent [binding vectors](../contracts/lifecycle-runtime/v1/fixtures/binding-vectors.json)
freeze both exact documented canonical binding objects with all current fixed
limits. The deployment clone variant changes only broker cluster ID, keeping topic
names/IDs unchanged; its expected common hash differs. Worker variants change
only stable worker, input topic ID/name or inherited common binding, and each
expected checkpoint hash differs. Repeated-digit artifact/public-key/evidence
hashes are explicitly synthetic vector inputs. No implementation generated these
values. Artifact signatures bind the same common runtime hash; cross-broker bytes
cannot be adopted solely because authority/bundle/topic descriptors match.

Verify actual source namespace/instance, original raw/evidence IDs/hashes, run,
source-contract snapshot/hash, context hash, parser/normalizer/mapping profile,
assembler/quality, compiler/evaluator/selector/enrichment, semantic plan, full
closure, command revision/hash and worker/incarnation on every applicable tagged,
detection and diagnostic record. Manifest/preservation/receipt wrappers must keep
original authoritative source documents intact and provide new runtime attribution
without claiming they were ordinary detection decisions.

For any isolated replay run, preserve original evidence and source event identity,
retain original assembly membership in historical mode, and isolate derived output
from live and other replay runs. The old P14 executors remain pinned to original
producer `51a984de…`; a new lifecycle output/profile must be explicitly supported
by new versioned artifacts or explicitly rejected. Unknown retained graphs block
retirement; compatibility guards and old immutable artifacts cannot be weakened to
make a new runtime appear historically qualified.

## Preservation, retention, security and finite failures

| ID | Failure or operation | Required independent result |
| --- | --- | --- |
| P01 | Retire closure referenced by current intended command, actual mixed worker, pending change, staged rollback or unacknowledged publication | Block before deletion. A timeout does not release the dependency. |
| P02 | Retire A after workers move to B while A remains in inbox/group/outbox/checkpoint/recovery state | Retain complete A closure and executables required for actual recovery. Current desired state alone is insufficient inventory. |
| P03 | Retire pinned/held historical or current replay/archive artifact | Respect original pin/hold and exact catalog. Missing/corrupt dependency state blocks; missing file is not hold release. |
| P04 | Change membership/checkpoint/pin/hold after retirement preflight | Reject stale plan or serialize reference acquisition with retirement. Pin before publishing a reachable dependency. |
| P05 | Exhaust bounded control, bundle, inbox/outbox, checkpoint or diagnostics space | Visible fail/backpressure/stop-admission; no silent shedding of Kafka-accepted source evidence or eviction of required state/artifacts. Test exact limits and over-limit without widening them. |
| P06 | Broker outage with accepted source and pending activation | Account every accepted physical location as durable output/quarantine or visible backlog. Command publication uncertainty and source backlog remain separately inspectable. |
| P07 | Missing/corrupt artifact, unknown extension, symlinked/foreign/private-root violation | Reject before mutation/apply/output; preserve prior valid worker policy and originals. No remote URI fetch or arbitrary candidate executable. |
| P08 | Imported YAML/evidence contains secret/log-like text | Fixed bounded value-free operational categories and controlled audit metadata; no raw stderr/evidence/credential leakage. |
| P09 | Old P13/P14 regression consumers rebuilt/tested on actual P15b revision | Preserve original pinned artifact identities and independent qualification. Tree similarity or previous run cannot transfer CI/runtime evidence. |
| P10 | Replay or maintenance cannot recognize lifecycle output graph | B1 explicitly rejects unsupported lifecycle archive/replay use; B2 owns the separately frozen supported graph/profile and actual reproduction/preservation evidence before full P15/P16 gates. Never infer dependency independence or reproduction. |

## Freeze and qualification gate

Before production implementation, finalize the runtime design, canonical control/
ack/state/output schemas, source ownership, identity vectors, bundle bytes and
compatibility/retention interfaces. Reconcile any routine choice above with the
accepted milestone design. Consequential changes to accepted architecture require
owner discussion and an ADR; routine protocol choices do not justify a permission
pause.

Meaningful behavioral reds must target a real missing/incorrect transition after
its setup prerequisites pass. The P15a missing-SLF4J failure demonstrates why a
failed runtime setup cannot establish a valid semantic red. Preserve failed
attempts and report actual source revision/dirty state, artifact/plan/closure/image,
platform, original inputs and independent expectations, command/scenario and raw
report/log hashes. Never regenerate expected outputs from implementation output.

Run isolated local ARM64 and actual native AMD64 runtime cases separately. Any
private recorded-source suite is opt-in, preserves reviewed originals/catalog/
terms/trusted capture bindings and remains unavailable on native AMD64 unless
actually supplied. Serialize heavy projects and preserve exact original evidence.
No throughput, rescaling, HA, physical power-loss, local-disk-loss or unbounded
outage guarantee follows. P16 remains gated on actual P14/P15 qualification and
owner dispositions; merge and release authorization remain explicit separate facts.
