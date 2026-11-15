# P10–P12 implementation ledger

The owner instructed implementation after reviewing the
[consolidated plan](p10-p12-plan.md), and selected a reviewed OpenSSH recording for
P12. Merge/release authorization remains separate for every PR/release. Planning
children completed P11/P12 design read-only; they have not implemented adapters.

| Unit | Owner | Base / branch / worktree | Dependencies | Status and blockers |
| --- | --- | --- | --- | --- |
| P10a | Main orchestrator | `4d7d685`; `feat/p10-mapping-contracts`; `/Users/travisma/GitHub_Projects/DetectBridge-p10a` | P04/P09 merged | Implemented in [draft PR #36](https://github.com/TravisMa07/DetectBridge/pull/36); local check/java passed; merge unauthorized |
| P10b | Main orchestrator | Not created | Authorized P10a merge + green main | Planned; complete P10 semantic/selection/runtime gate pending |
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
