# P15b qualification batch admission — independent expectations

Status: pre-implementation expectations for a separate qualification helper. The
[owning batch design](p15b-batch-design.md) freezes the exact wire and durability
contract with this expectation matrix before implementation.
These expectations derive from the accepted source-preservation, broker-namespace,
admission-journal and finite-resource contracts in [P15b design](p15b-design.md),
the [frozen source packet](../contracts/lifecycle-runtime/v1/fixtures/README.md),
and [independent runtime expectations](p15b-expectations.md). No new helper output,
compiler output or evaluator output was used to choose expected results.

The purpose is to admit a finite source sequence without paying a separate JVM
startup for each record. It does not change worker source semantics, assembly age,
membership, source identity, output identity, checkpoint confirmation or expected
decisions. The original producer, production lifecycle JAR and compiler packet
remain pinned. The qualification JAR changes independently and its actual hash and
class origin must be recorded. Existing native failures remain failed evidence;
a diagnostic transport failure is not a detection-semantic red.

## Fixed inputs and evidence meaning

The proposed batch accepts 1–128 exact records, each at most2 MiB, with at most8 MiB
aggregate record bytes, through a closed request at most64 KiB. Counts and lengths
are UTF-8 byte lengths; booleans are not integers. The request anchors every fixed
indexed private input file to its exact SHA256 and length. No caller-selected
command, class, executable, network address or arbitrary filesystem path is accepted.
One persistent Admin/Producer verifies the pinned cluster, topic ID, topic name and
single partition before and after each send. It cannot weaken the normal controller
scope checks or substitute a topic name for a topic identity.

Before any send, a durable immutable attempt identifies that exact index/input and
owned broker namespace. An actual broker ACK receipt is durably forced before the
next send. Consequently there is at most one attempted index without a durable
usable receipt. A receipt means observed broker acceptance only; it never proves
worker processing, assembly completion, policy selection or checkpoint durability.
The controller journals only the verified contiguous receipt prefix through its
normal admission checks. It never invents an offset, fills a hole, automatically
resends the uncertain index, or silently creates a fresh batch to bypass uncertainty.

For the original six-member audit fixture, freeze the existing exact raw bytes,
order, source/member/event IDs and source-boundary eligible manifest. Successful
batch transport changes none of its literal expectations. Do not infer eligibility
from transport success: actual worker output must still match the frozen oracle.
Batch admission does not reset or extend the existing30-second group age.

## Independent acceptance matrix

| ID | Input or interruption | Required observation |
| --- | --- | --- |
| Q01 | One valid Windows Alice record | Exactly one actual namespace-bound ACK receipt and normal controller admission; frozen A outcome remains receipt/tagged/detection, matched1, every other count0. |
| Q02 | Original ordered six-member audit-whoami sequence | Six ordered attempts/ACKs and exact contiguous admissions; actual source output independently requires original six members, eligible source-boundary closure, expected whoami fields and fixed policy decision. No new expected event ID from observed output. |
| Q03 | Valid128-record input within byte caps | Exactly128 attempts/receipts if every send succeeds; fixed indexed order, no skipped or repeated index. This is a finite correctness case, not throughput qualification. |
| Q04 | Counts0/129; negative/fractional/boolean count; unknown/missing request field | Reject before the first send. No attempt, ACK or controller admission. |
| Q05 | Record exactly2 MiB versus2 MiB+1; aggregate exactly8 MiB versus8 MiB+1; request exactly64 KiB versus+1 | Byte-boundary input is transport-admissible if all other contracts hold; boundary+1 rejects before sends. Do not require semantically invalid padding to produce a valid source event. |
| Q06 | Missing file, symlink, wrong UID/mode, extra/unexpected indexed member, path escape, changed length/hash, duplicate index or trailing bytes | Fail closed before sends. Preserve evidence; never repair or normalize the anchored bytes silently. |
| Q07 | Broker error before the first send attempt | No successful acceptance claim or fabricated location; fixed failure evidence and immutable batch intent retained. |
| Q08 | First k actual ACK receipts durable, next attempted send fails or loses its response | Only exact verified prefix0..k-1 can become admissions. Preserve attempted index k as uncertain when acceptance is unknown; do not send k+1. |
| Q09 | Broker accepts index k but helper dies before durable receipt | Recovery exposes exactly that unresolved attempt; no invented ACK/offset and no automatic resend. Actual broker inspection, if later performed, is separately scoped evidence. |
| Q10 | Crash after forced attempt but before send | Same conservative unresolved-attempt state as Q09; absence of a receipt cannot establish that Kafka accepted nothing. |
| Q11 | Crash after forced receipt, before next attempt | Recover the exact accepted prefix once; next index has no attempt. Reopening does not duplicate existing controller admissions. |
| Q12 | Crash while controller journals an already verified receipt prefix | Replay exact retained prefix through normal idempotent admission checks; preserve accepted facts, reject conflicts and never advance across a missing receipt. |
| Q13 | Cluster ID, topic ID, partition count or topic identity differs before send | Stop before that send, retain prior verified prefix. Cloned names/offsets on another namespace are insufficient. |
| Q14 | Namespace differs or cannot be verified after send | Stop before the next attempt. Preserve actual attempt/ACK facts without presenting an unscoped ACK as a verified admission; uncertainty is visible. |
| Q15 | Receipt changed offset/key/value hash/index, wrong namespace, duplicate/conflicting receipt, missing prefix member, forged receipt without attempt | Reject recovery/admission; do not trust helper success alone or count arbitrary JSON as actual broker ACK evidence. |
| Q16 | Helper exits success but receipt prefix incomplete, or exits failure after a valid prefix | Exit success cannot replace complete receipt verification. Failure cannot erase independently verified accepted prefix; overall batch still reports failure/uncertainty. |
| Q17 | Source bytes or receipt files mutate between initial validation and use/recovery | Immutable anchored hashes detect mutation before use/journaling. No resubmission or changed-source continuation under the same intent. |
| Q18 | Store reserve, filesystem-entry cap, short write, failed fsync or rename | Visible bounded failure, no false durable-success claim, no next send before required durability. Keep recoverable previous prefix and original files. |
| Q19 | Run owned by another stable worker, absent membership, incompatible source or malformed source row | Preserve normal controller/worker rejection boundaries. Batch transport cannot authorize cross-worker routing, bypass source validation or manufacture membership. |
| Q20 | Actual complete batch admitted, later worker fails or audit expires | Retain the actual accepted input locations; report runtime/oracle failure separately. Never claim no runtime loss or redefine literal closure expectations from the observed failure. |

## Frozen design choices

The owning design specifies closed fields, indexed filenames, exact hashing,
validation and force order, and the durable controller intent. It preserves raw
ACK metadata before post-send namespace verification; that fact alone cannot
become an admission. Only certified dense receipt files authorize the prefix,
independently of stdout or process exit. At most one attempted index may remain
uncertain, and no automatic resend or new admission bypasses an incomplete batch.
These choices precede implementation rather than being inferred from its output.

Qualification must retain exact batch/helper/request/input hashes, per-index real
broker evidence, controller journal prefix, uncertainty category and safe diagnostic
hashes. Unit/component cases establish only their bounded mechanics. Actual Kafka
and Flink runs, including the final unchanged all14 gate, remain necessary. Focused
partial results cannot be combined across attempts into a full pass.
