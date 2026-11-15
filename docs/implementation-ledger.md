# P10–P12 implementation ledger

The owner instructed implementation after reviewing the
[consolidated plan](p10-p12-plan.md), and selected a reviewed OpenSSH recording for
P12. Merge/release authorization remains separate for every PR/release. Planning
children completed P11/P12 design read-only; they have not implemented adapters.

| Unit | Owner | Base / branch / worktree | Dependencies | Status and blockers |
| --- | --- | --- | --- | --- |
| P10a | Main orchestrator | `4d7d685`; `feat/p10-mapping-contracts`; `/Users/travisma/GitHub_Projects/DetectBridge-p10a` | P04/P09 merged | Implemented for review; validation evidence recorded in PR; merge unauthorized |
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
