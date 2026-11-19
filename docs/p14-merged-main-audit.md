# P14 actual merged-main audit

Status: actual merged-main technical qualification passed. Owner-performed merge
is established. The owner subsequently selected “Accept bounded P14 completion”
in this continuation session. Issue #14 is closed and its project card is Done;
M5 remains open for P15/P16. No separate prior acceptance is invented.

## Exact revision and CI

The owner merged the P14 stack in PRs [#54](https://github.com/TravisMa07/DetectBridge/pull/54),
[#52](https://github.com/TravisMa07/DetectBridge/pull/52) and
[#55](https://github.com/TravisMa07/DetectBridge/pull/55). GitHub reports the same
merge SHA for these three PRs:
`f44c9f91e10414cd2b03481951a2e2a1c7b2a4a0`. The actual Git object is one regular
two-parent merge, with parents `b495c2bc706d4ac7f2515fe7b1240c5b8ae70904` and
`7b9520cc7163e05859f70c4230c89a1154ebfcde`. It is not three separately qualified
mainline merges. Its tree is `ee686c3ed6bf72af8588eb8ac926a62333b6ea84`;
identical trees do not transfer CI evidence.

Actual main push [run 44458422172](https://github.com/TravisMa07/DetectBridge/actions/runs/44458422172),
attempt 1, completed successfully on that exact SHA. Every one of eighteen
applicable jobs passed, including required aggregate job 135347520753, which
completed at `2026-11-19T04:50:19Z`; run metadata updated at
`2026-11-19T04:50:20Z`. Five explicit acquisition/recording opt-ins were skipped.
The checkout logs show actual `main` at f44c9f9, independently of the earlier PR
test-merge runs. No failed attempt or generic retry is hidden by this result.

| Job | Job ID | Conclusion |
| --- | --- | --- |
| repository-hygiene | 135339037255 | success |
| classify-changes | 135339037608 | success |
| secret-scan | 135339037610 | success |
| controlled-windows-recording | 135339038819 | skipped |
| dataset-acquisition | 135339039134 | skipped |
| toolchain-verification | 135339077960 | success |
| local-stack-verification | 135339078063 | success |
| replay-qualification | 135339098170 | skipped |
| detection-verification | 135339714429 | success |
| windows-verification | 135339714462 | success |
| transport-verification | 135339714584 | success |
| opensearch-writer-verification | 135339714587 | success |
| integration-verification | 135339714608 | success |
| linux-verification | 135339714622 | success |
| historical-replay-verification | 135339714688 | success |
| archive-verification | 135339714703 | success |
| current-replay-verification | 135339714704 | success |
| search-verification | 135339714709 | success |
| linux-assembly-verification | 135339714715 | success |
| archive-maintenance-verification | 135339714865 | success |
| recorded-writer-qualification | 135339716315 | skipped |
| recorded-transport-qualification | 135339717173 | skipped |
| required-checks | 135347520753 | success |

Original downloaded metadata and complete logs are retained locally, outside Git,
in `.cache/p15-main-audit/`:

- `run.json` SHA-256: `63cf2c235aa83c52af4b2bb8d9b3d0971f19e2e033350f8c51c5b138a7806f96`.
- `run.log` SHA-256: `6cba44c3384494ca2f7bab003f74433ec2b9f1480ee5b824dd532e16eb13df3b`.

## Actual managed runtime evidence

The merged-main maintenance job 135339714865 passed all 44 actual synthetic
fault/recovery/pressure/replay cases in project
`detectbridge-p14-managed-a028d55de107`, source revision
`f44c9f91e10414cd2b03481951a2e2a1c7b2a4a0`, Linux/x86_64 host and
`linux/amd64` runtime. Its emitted complete summary names actual image ID
`sha256:6b26436e8a89f49acaf0133e35f1e3715544e7c984d0f68cd8038137ab2e6be9`.

| Artifact | SHA-256 |
| --- | --- |
| Managed JAR | `9598289011727e96e1e633642f6926893161c5889e90ffe1cdd85c2642ff46df` |
| Original archive reader | `e5eaea3560d150e176cb0f68e941ca22efb25fb6f16b2a1d1d76465a94ef02d0` |
| Original historical executor | `32bad6f526e3208bf4b2684979a4d600c82b35070e39cbeb3a5fce6d5fccfcc4` |
| Original current executor | `ea9d47406651a686546a2514f83fe59689fa38902e76b0c2c6aa129c37a511e2` |
| Original producer | `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d` |
| Merged-main maintenance probe | `7cdfc5102744e3249939731b6d34fa854116bf2250d16e28f2d912e6d5023cc5` |
| Merged-main historical probe | `2759ee259ba282946efd45a3780c2e3202a404aca50688652ca2c541d3856c17` |

The command was `uv run --locked python tools/dev.py maintenance` followed by
`uv run --locked python tools/archive_maintenance_verify.py`. The actual summary
preserves all case names and controller/qualifier/helper hashes. Cases include
lease exclusion, exact clone/import/restore, hold release, durable retirement and
cleanup, corruption rejection, metadata midwrite/sync crash windows, unknown graph
rejection, isolated historical/current replay, Kafka payload/rename/commit crashes,
retired-anchor append, fingerprint conflict, broker pause/resume, initialization
crashes and lower-cap visible backlog. The prepared Gradle dependency cache was
required before bootstrap. Other applicable existing consumers also passed; this
is independent merged-main evidence, not a transfer of PR-head qualification.

## Completion reconciliation and retained limits

The [P14 acceptance map](p14-acceptance.md) and [P14c2 ledger](p14c2-ledger.md)
retain independent expectations, exact local ARM64 artifacts, approved-original
P05 import/restore and controlled-recording evidence. Earlier failed runs and
unsafe intermediate candidates remain historical failures. This successful
merged-main run resolves the previously pending native merged-revision technical
gate. It does not retroactively alter those failures or qualify another revision.

The native maintenance qualifier explicitly exercises a synthetic injected P05
catalog and does not exercise private originals. Private recorded native AMD64
qualification remains unavailable. Recorded error/budget, malformed and
missing-identity cases retain supplemental synthetic status. Local recorded
coverage remains attributed to its original source/artifacts and platform in the
owning ledger. There is no throughput, unbounded-outage, HA, physical power-loss
or local-disk-loss claim. Kafka acknowledgment, archive durability, processing
completion and derived OpenSearch indexing remain separate facts.

The initial live remote audit found issue #14 open with project status Ready; issues #15/#16
open with status Backlog; milestone M5 open with three open and zero closed
issues. PR #55 was merged by TravisMa07 at `2026-11-19T04:27:10Z`; its body still
contains pre-merge gate prose, with no comments or submitted reviews. The owner
merge is an observed disposition; a separate final P14 semantic/completeness
acceptance is not asserted here. The owner subsequently explicitly accepted bounded P14 completion in this session.
Issue #14 was closed with that decision and exact CI evidence in its body; its
project card is Done. P15 is In progress. M5 remains open through P15/P16.

The original checkout's untracked `docs/p14-handoff.md`, and the P14 worktree's
six uncommitted native-completion edits plus `docs/p15-handoff.md`, remain
preserved. This audit supplements them without rewriting historical freeze prose
or modifying those files. No merge or release authorization is inferred.
