# P10–P12 implementation ledger

The owner instructed implementation after reviewing the
[consolidated plan](p10-p12-plan.md), and selected a reviewed OpenSSH recording for
P12. Merge/release authorization remains separate for every PR/release. Planning
children completed P11/P12 design read-only; they have not implemented adapters.

| Unit | Owner | Base / branch / worktree | Dependencies | Status and blockers |
| --- | --- | --- | --- | --- |
| P10a | Main orchestrator | `4d7d685`; `feat/p10-mapping-contracts`; `/Users/travisma/GitHub_Projects/DetectBridge-p10a` | P04/P09 merged | Merged in [PR #36](https://github.com/TravisMa07/DetectBridge/pull/36) as `b45fba4`; semantic acceptance remains separately pending |
| P10b | Main orchestrator | `b45fba4`; `feat/p10-source-selection`; `/Users/travisma/GitHub_Projects/DetectBridge-p10b` | P10a merged; merged-main checks recorded separately | Implemented in [draft PR #37](https://github.com/TravisMa07/DetectBridge/pull/37); validation evidence below; semantic review and merge authorization separate |
| P11 | Windows child | Not created | Complete accepted P10 | Planned; host binding and recorded eligible evidence required |
| P12a | Linux child | Not created | Complete accepted P10 | Planned; host/generation evidence and reviewed OpenSSH recording required |
| P12b | Linux child | Not created | Authorized P12a merge + green main | Planned; actual checkpoint/recovery qualification required |
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
