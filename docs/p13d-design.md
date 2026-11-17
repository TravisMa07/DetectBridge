# P13d recorded acceptance and recovery qualification

Status: pre-implementation design and independent-expectation freeze. Base
`0f6d758b8228a3ccce35f1af83174addc4835126`. Preserve A02–A07, all existing
contracts, source policies, checkpoint bindings and writer ordering. P14 remains
unimplemented and blocked until P13 acceptance, resolved review, authorized merge
and successful merged-commit checks.

## Recorded inputs and oracle

Reuse only the accepted catalogs `windows-process-lab-v1`,
`linux-audit-execve-lab-v1` and `openssh9-password-lab-v1`. Before runtime creation,
validate every original artifact, terms, native framing/action relations and actual
capture/host/generation evidence with the owning recording verifiers. Freeze
catalog/source/mapping/rule hashes and complete prepared input contexts locally.
Missing originals fail explicitly; never synthesize replacements or infer identity
in older public Windows recordings. Private originals and generated evidence stay
ignored. Explicit directory arguments permit reuse of accepted local caches.

Compile the existing nine P13b fixture rules plus the three committed P11
controlled-recording rules into a separate immutable qualification bundle, retaining
original rule provenance. The deployment artifact binds the actual plan bytes;
ordinary synthetic qualification keeps its existing nine-rule plan and assertions.
The twelve-rule order is four `71100000` rules, three `71110000` rules, then five
`72000000` rules, sorted by UUID. Expectations below follow literal predicates and
source capability/quality policies, never observed evaluator results.

| Recorded event | matched | unmatched | inapplicable | configuration blocked | quality skipped | evaluation error |
| --- | --- | --- | --- | --- | --- | --- |
| Security/Sysmon cmd (two) | 1 | 4 | 7 | 0 | 0 | 0 |
| Security/Sysmon hostname (two) | 0 | 5 | 7 | 0 | 0 | 0 |
| Eligible audit probe (one) | 1 | 4 | 6 | 1 | 0 | 0 |
| Insufficient audit groups (nine) | 0 | 0 | 6 | 1 | 5 | 0 |
| Password success/failure (two) | 0 | 1 | 11 | 0 | 0 | 0 |

Matches are precisely `71110000-0000-4000-8000-000000000001` for cmd and
`72000000-0000-4000-8000-000000000005` for the audit probe. Unsupported audit
CommandLine is bit 9 (`200` hex), including skipped groups; skipped Image
membership is bits 2,6,7,8,11 (`9c4` hex). Sysmon service-state is preserved
unsupported; nine auth rows are preserved unsupported; three native audit rows
are extraction failures. No fabricated event/outcome is expected for them.

The baseline per run is 46 original records, 16 logical events, ten manifests,
13 preservation documents and three detections. Explicit run-end controls close
original audit membership. A duplicate of an already admitted record must remain deduplicated. A separately
identified qualification admission reuses one original audit body with an explicit
new dataset cursor at position 1000; it must link the closed original manifest as
late evidence. That cursor is a controlled qualification input, not an original
recorded occurrence or a new capture. Two full runs retain event/evidence identity and
isolate all processing/detection identities. Duplicate physical deliveries must
have identical bytes and keys; every acknowledged input has one logical receipt
and independently verified original Kafka retrieval hash.

Reuse the independent Windows source assertions and exhaustive audit token/source
verifier; retain native auth expectations. Check full output versions, attribution,
counts, rule metadata, immutable memberships, quality and search projection fields,
not counts alone. Add same-count semantic mutations against actual observations.
Recorded evidence does not cover all six nonzero outcomes: error/budget, malformed,
missing identity and other edge coverage remains the separate synthetic suites.

## Recovery and delivery

Diagnose merged-main integration failure from original diagnostics before assigning
cause. Artifact 14358080606 (ZIP SHA-256
`b9fb795f149d3792ca938df11704f3abbf16e2dbd0ff90f50eb67c07625f290b`)
records an integration failure during the incompatible-restore phase. Its
exception handler retrieved the tracked original job, not the separately submitted
probe. The retained TaskManager heartbeat exception therefore cannot establish
the probe failure cause; it may reflect the earlier intentional kill. All three
containers were running without OOM at observation. Never count that failure as the
required incompatible-binding rejection or weaken the assertion to accept it.
Collect more diagnostics/reproduce before deciding a runtime correction.

Recorded qualification must exercise checkpoint/deadline recovery and a real
required-sink rejection retaining exact original recorded members, healthy restore,
two isolated replays and source-to-search retrieval. Existing full integration and
assembly suites retain every sink, incompatible restore, broker pause and recovery
assertion. Existing writer suite retains duplicate/conflict handling, failure
acknowledgement before commit and crash-after-indexing-before-commit ordering.
Run heavy Docker suites serially; record exact artifacts and platform separately.
Native AMD64 ordinary CI is synthetic unless the actual private originals are
explicitly available. No opt-in skip establishes recorded qualification.

## Review and completion

Produce an acceptance map and refreshed prerequisite dispositions with exact heads,
merge SHAs, runs and limitations. Preserve historical failed attempts. Carry the
standing commit-policy edits into this documentation change. Use a freeze commit,
one cohesive implementation/regression commit and one consolidated evidence commit
where possible; later published corrections preserve history. Owner semantic/
completeness acceptance and merge permission remain separate final gates.

## Qualification coordination and diagnostic refinement

Runtime inspection of the first recorded attempt established that `run_end` closes
the entire run, including Windows/authentication. All original sources must be
admitted before that control. Literal source/count expectations are unchanged;
a regression requires the global ordering. The controlled late-cursor and original
duplicate admissions remain separate from the 46-record original population.

The source tagged-route fault changes a Kafka topic policy frozen by the
independent writer. Stop the writer during that deliberate operator intervention,
restore the original topic policy, then require its ordinary strict healthy start
before search catch-up. This does not relax any producer rejection, source intent,
search field, failure acknowledgement or writer commit assertion. Retain original
writer health/offsets/logs privately before cleanup on any later failure.

Native correction run 44177420786 passed search but failed processing-sink
qualification. Original artifact 14371921401 has ZIP SHA-256
`10464b27abdb3509d21e8b8c81ff627d489c2af85b24d79283340c6e0aa9179b`.
Its TaskExecutor shutdown/NoResourceAvailableException and exited-1/non-OOM
container state do not establish the process exit cause. Add bounded original
container logs, service labels and TaskManager/slot observations to the synthetic
failure artifact; retain the exact producer-failure requirement. Separate probe
and subsequent healthy-restore diagnostic targets so an earlier expected probe
exception cannot be mistaken for a later failure. No speculative runtime, retry,
heap, resource-budget or failure-marker change is justified by those observations.

The published CI correction/diagnostic collection requires an additional cohesive
commit before native reproduction, followed by a consolidated final evidence
commit. Preserve published freeze/implementation/fix IDs under the SDLC exception;
do not rewrite history to force the original 1–3 planning target.
