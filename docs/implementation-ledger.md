# P10–P12 implementation ledger

The owner instructed implementation after reviewing the
[consolidated plan](p10-p12-plan.md), and selected a reviewed OpenSSH recording for
P12. Merge/release authorization remains separate for every PR/release. Planning
children first completed P11/P12 design read-only; their later implementation
and integration history is recorded below.

| Unit | Owner | Base / branch / worktree | Dependencies | Status and blockers |
| --- | --- | --- | --- | --- |
| P10a | Main orchestrator | `4d7d685`; `feat/p10-mapping-contracts`; `/Users/travisma/GitHub_Projects/DetectBridge-p10a` | P04/P09 merged | Merged in [PR #36](https://github.com/TravisMa07/DetectBridge/pull/36) as `b45fba4`; semantic acceptance remains separately pending |
| P10b | Main orchestrator | `b45fba4`; `feat/p10-source-selection`; `/Users/travisma/GitHub_Projects/DetectBridge-p10b` | P10a merged; merged-main checks recorded separately | Merged in [PR #37](https://github.com/TravisMa07/DetectBridge/pull/37) as `df31448`; merged-main checks passed; owner authorized P11/P12 |
| P11 | Windows child; orchestrator integration | `df31448`; `feat/p11-windows-adapters`; `/Users/travisma/.t3/worktrees/DetectBridge/t3-689cf405-5fa25cc439f21f05` | P10 merged; owner authorized dependent work | Merged in #38 as `46fb080`; recorded trusted host bindings and owner acceptance remain blocked |
| P12a | Linux child | `df31448`; isolated P12a worktree; merged branch | P10 merged; owner authorized dependent work | Merged in #39 as `9ea1c68`; reviewed local OpenSSH9 slice passed; audit provenance and owner review remain open |
| P12b | Main orchestrator | `9ea1c68`; `feat/p12b-linux-qualification` | P12a merged | Merged in #42 as `e2d06c3`; final ARM64/AMD64 and merged-main qualification passed |
| P12c | Main orchestrator | `e2d06c3`; `feat/p12c-recorded-source-evidence` | P12b merged + reviewed local auth originals | Implemented in draft #43; corrected audit offline and final-artifact ARM64 full/auth qualification passed; PR-head CI/owner review pending |
| P13 | Unassigned | Not created | P08 + complete P11/P12 | Blocked |

Shared ownership: orchestrator owns contracts/readers, Gradle registration,
root locks/inventories, CI/gates, dev commands and status docs. P10 owns generic
compiler/mapping/selection; Windows child owns Windows code/tests/profile proposals;
Linux child owns Linux code/tests/assembly manifests/profile proposals. Separate
worktrees isolate implementation; serialize shared integration edits and heavy
Docker qualification. Update remaining branches and rerun affected consumers after
each authorized merge. Implementation, qualification, semantic review and merged
status are separate states; no row implies an unrecorded pass or authorization.

P10a implementation revision: `62c3e5a731a5ea2908fe7cac4917292962441e40`.
Local locked check: 108 Python tests, contracts/catalog/replay/deployment checks,
hygiene/secrets, Ruff and mypy passed. Locked Java verification: 13 evaluator,
5 transport-contract and 15 writer tests passed, affected JARs packaged, 20 legacy
and 12 P10 YAML-to-Java semantic cases passed. Independent code review found two
issues (analysis timeout handling and generated fixture provenance); both were
fixed before this revision. Owner semantic acceptance remains pending.

ARM64 legacy P09 regression qualification passed on that implementation revision:
11 valid and 2 invalid inputs accounted for across replay isolation, TaskManager
restart, unavailable quarantine sink, explicit checkpoint restore, JobManager
restore, metrics and value-free logs. Exclusive project
`detectbridge-p09-test-423072d74a5a` was cleaned. Runtime JAR SHA-256:
`e869254779f90b6b7c6229c81b4f1b498cb29b4acf5949f3f426081fc8372218`.
This qualifies legacy deployment preservation, not P10b's future v2 runtime or
production source adapters. Initial build failed while Docker was stopped; it was
started and the successful build/qualification was rerun. AMD64 checks are reported
on the PR against each pushed head; they are not inferred from the local run.

P10a merged-main [AMD64 CI](https://github.com/TravisMa07/DetectBridge/actions/runs/43673156008)
succeeded on `b45fba48b57eb360087521bc9ba06113cb34ef88`, including detection,
writer, transport, local-stack and required-checks. Optional recorded jobs were
skipped; independent semantic review is not inferred from this result.

## P10b validation record

Runtime implementation revision: `111151a745bf32cba840f406bb7b0b1ab50ee9f4`. Final
locked verification, including the test-only follow-up, passed with 116 Python tests, hygiene/secrets, contracts/catalog/replay/
deployment checks, dependency inventory, Ruff and mypy. Locked Java verification
passed with 19 evaluator, 5 transport-contract and 15 writer tests and affected
JAR packaging. Independently expected YAML-to-Java cases: 20 legacy, 20 mapped
predicate and 12 mapped capability cases; all 32 mapped cases additionally compare
complete optimized/exhaustive outputs.

Final strengthened ARM64 mapped qualification passed with 16 valid and 2 invalid
inputs accounted for across all six outcomes, seven explicit run IDs, TaskManager
recovery, unavailable quarantine output, checkpoint restore, actual changed-group
restore rejection, JobManager restore, metrics and value-free logs. Project
`detectbridge-p10-test-e4692c6d6170` was cleaned. Runtime JAR SHA-256:
`59a3bca0f6ff994ffb687485b9b2fffd0a7657085a36f5493b3e9ecec54c4c39`.
Earlier mapped qualification preceded the stronger attribution checks and is not
used as the final acceptance evidence. Final legacy regression passed as recorded below. PR AMD64 CI and owner semantic acceptance remain separate gates.

Final ARM64 legacy v1 regression passed with 11 valid and 2 invalid inputs,
including TaskManager restart, unavailable quarantine sink, checkpoint and
JobManager restore, independent attribution, metrics and value-free logs. Project
`detectbridge-p09-test-73bc018a6fca` was cleaned. It used the same runtime JAR hash
as the mapped run, with a separate legacy bundle/plan and v1 project/topics.
The final follow-up adds a literal independently hashed legacy binding vector and
a wrong-Kafka-key regression; production runtime code is unchanged from 111151a.
No source eligibility or throughput claim follows. AMD64 CI, owner semantic
acceptance and separate merge authorization remain gates.

PR #37 AMD64 run 43675094807 failed on 8e561ec during the legacy
JobManager-restore phase, before the mapped run. The required-checks failure was
its expected fail-closed aggregate result. Root cause is not yet established:
the existing CLI logged only a generic failure. A diagnostic follow-up adds
redacted failure categories and narrower recovery phases, with nonzero-exit and
redaction regressions. Existing local ARM64 passes do not override this CI failure.

[Diagnostic AMD64 run 43676210039](https://github.com/TravisMa07/DetectBridge/actions/runs/43676210039)
qualified legacy v1 recovery on 2d60c2c (11 valid, 2 invalid inputs), then failed at
the mapped incompatible-restore probe with command_failed_job_submission_exit_1.
The probe assumed the CLI would return a JobID before asynchronous failure. The
follow-up handles a synchronous CLI failure only by verifying one newly submitted
FAILED job and the exact binding-rejection marker through REST. No unrelated
submission failure is accepted, and no mutation is retried. Local locked checks
pass with 121 Python tests; fresh mapped ARM64 qualification and AMD64 confirmation
remain separate from that unit/check evidence.

The follow-up's fresh ARM64 mapped qualification passed with 16 valid and 2
invalid inputs, including the strict incompatible-restore proof and subsequent
checkpoint/JobManager recovery, attribution, metrics and value-free logs. Project
`detectbridge-p10-test-65b32a68c093` was cleaned. Runtime JAR remains
`59a3bca0f6ff994ffb687485b9b2fffd0a7657085a36f5493b3e9ecec54c4c39`;
this change affects qualification, not evaluator semantics or production bindings.
AMD64 confirmation remains pending; unrelated CLI failures remain failures.

## P11/P12 authorization and current integration

The owner declared P10 finished and requested the agreed P11/P12 planning and
implementation. P10b merged as df3144822ddd5694b9244ae29eb4a3c9e2815376;
[merged-main CI](https://github.com/TravisMa07/DetectBridge/actions/runs/43679437257)
passed. This records authorization to proceed, not an invented semantic-review
approval. P11 and P12a run in separate worktrees from that same base; P12b remains
dependent on P12a's authorized merge and complete P12 acceptance remains separate.

P11 child commits f78e221/f764907/eb44769/f82e83b provide design/expectations,
isolated Gradle integration, adapters and qualification. Orchestrator-owned CI/dev
gates, inventories, source-signature verifier and System/Data attribution fix are
being integrated for a draft PR. See [subsystem ledger](p11-ledger.md). Recorded
Windows accounting is preservation/skip evidence; no eligible recording claim
is made without trusted host bindings. No services, P13 pipeline, release or
authorized merge is implied.

P11 draft PR #38 at 4f741c2 passed all required AMD64 jobs in run 43684323177,
including Windows, shared Java, legacy/mapped detection and existing transport/
writer gates. It remains unmerged with trusted recorded Windows host bindings
missing and owner review outstanding.

P12a's isolated offline core is now integrated for review on
feat/p12a-linux-adapters, stacked above P11 only to serialize shared changes. The
real local OpenSSH9 capture has 11 original messages, two eligible success/failure
events and nine unsupported diagnostics, with immutable byte/context/terms review
and independent adapter/evaluator accounting. No P12b checkpoint qualification or
recorded eligible audit claim is made. See the P12 ledger for exact heads/evidence.

## P12b planning after adapter merges

P11 #38 and P12a #39 merged as 46fb080 and 9ea1c68 respectively. P12a PR CI passed;
merged-main run 43750911904 was still in progress when the next plan was written.
The [P12b implementation plan](p12b-plan.md) covers checkpointed Linux assembly,
bounded output intents, timers, real Kafka/Flink failure qualification and exact
accepted-input accounting. It is a proposal, not implemented recovery evidence.
Recorded audit eligibility, Windows host binding and independent owner semantic
review remain separate acceptance items; no P13 readiness is inferred from merges.

## P12b implementation and qualification

The owner authorized the P12b plan and implementation. The initial P12a
merged-main run 43750911904 failed P10 incompatible restore with an unclassified
cause; one unchanged failed-job rerun passed. No acceptance was relaxed. P11 #38
and P12a #39 are merged; earlier unmerged/AMD64-pending entries above describe
historical checkpoints rather than their current integration status.

The checkpointed Linux implementation, prepared transition model, source/binding
contracts, local evidence registration and real conditional CI/dev gate are now
on feat/p12b-linux-qualification. The [P12b ledger](p12b-ledger.md) records exact
artifact/runtime results, failed attempts, final-head evidence and remaining gates.
No P13 production wiring, recorded audit eligibility, owner semantic approval,
merge authorization or release is inferred from these checks.

Final P12b ARM64 qualification passed on the artifact recorded in its ledger:
52 default inputs, 83 logical documents, 93 physical rows including 10 stable
recovery duplicates, all five actual required-sink failures, real broker pause,
TaskManager/JobManager/checkpoint recovery and both pressure profiles. Local locked
checks passed with 133 Python regressions and combined Java/semantic consumers.
Draft PR #42 targets main; actual linux-assembly-verification and shared AMD64
jobs were created. Final-head AMD64 CI, owner review and merge remain pending.

## P12c inspection and next slice

PR #42 is observed merged as e2d06c3. Its final-head AMD64 run 43768117676
passed; merged-main repository qualification 43804124770 was still in progress
at inspection (successful dependency-automation runs do not establish that gate).
It subsequently passed all required jobs. Earlier pending/unmerged P12b entries
describe historical checkpoints.
[Next-PR design](p12c-design.md): qualify the already reviewed local OpenSSH9
recording through P12b checkpoint recovery and an isolated replay, preserving all
11 originals and independent per-record expectations. No audit recording or Windows
host binding is invented, and no owner semantic approval or P13 readiness follows.

The owner expanded P12c to sustained roadmap work. A separate-kernel audit capture
now has pinned local-use provenance, trusted guest/boot bindings and independently
reviewed membership. Atomic audit replay and three real compiler/evaluator cases
passed on all 30 original rows. The [P12c ledger](p12c-ledger.md) preserves exact
artifacts, failures, runtime qualification and remaining owner/Windows gates.

P12c final local evidence passed: corrected audit context/1.1.0 across all three
frozen rule cases, 146 Python regressions, combined Java/semantic consumers, full
ARM64 assembly/five-sink/broker/recovery and both resource profiles, plus final-
artifact real auth checkpoint restore and isolated replay. Draft #43 remains
unmerged. Exact artifact IDs, failed attempts and remaining gates are in its ledger.

The final P12 technical evidence gap is now qualified: real recorded audit group
checkpoint/TaskManager/deadline recovery and eligible-event sink failure/restore,
with both complete isolated runs and all 63 record/control admissions accounted for.
[Acceptance map](p12-acceptance.md) distinguishes bounded implementation completion
from pending owner semantic review, actual PR-head CI and authorized integration.

## P13 handoff audit after the P12c merge

PR #43 merged as c02449745ddb87605d0bd85841f77fdad2fb382a. Its description
explicitly marks owner semantic/completeness review and merge authorization
complete, superseding the earlier pre-merge pending entries. Exact PR head adf71f8
passed AMD64 run 43812450381 attempt 2; the initial Maven HTTP 429 bootstrap failure
and unchanged successful failed-job rerun remain distinct. Current merged-main run
43873905332 was still running when audited; no pass is inferred from the merge or
from unrelated successful Dependabot checks.

[The P13 handoff](p13-handoff.md) records the prerequisite closure procedure and
bounded integration plan. P08 and the P11/P12 implementations exist, but P13 is
not Ready: trusted eligible recorded Windows host bindings and its separate
semantic acceptance remain unresolved in the P11 ledger. No Windows binding,
P13 service, source-to-detection writer projection, merge or release was invented
by this documentation audit. Linux original integrity was reverified read-only
(30 audit rows, 11 auth rows); no new runtime/performance qualification was run.
