# P15 rule lifecycle acceptance map

[P15 issue #15](https://github.com/TravisMa07/DetectBridge/issues/15) remains open.
The scope covers a private authority, compatible immutable bundles and isolated
workers. The owner has accepted P14's bounded profile. P15 milestone acceptance
and authorization for each merge or release are separate decisions.

| Requirement | Evidence available for owner review | Boundary |
| --- | --- | --- |
| Candidate provenance, immutable import, validation, sample tests and staging (A01–A10, A19–A27) | The [P15a ledger](p15a-ledger.md) records 30 required tests, exact evaluator, rule provenance and actual merged-main CI on f44403e. | Private local candidate store, bounded pySigma subset and Java evaluator. |
| Ordered preparation and rollback (A11–A18) | The [candidate design](p15-design.md) and [P15a qualification](p15a-ledger.md) cover compare-and-advance, idempotent retry, conflicting requests and distinct A/B/A proposals. | Preparation and broker-acknowledged publication have separate identities. |
| Publication, membership, mixed workers and rollback (B01–B12, B28–B29) | [Worker qualification](p15b1-ledger.md) and [CI-01](ci-01-ledger.md) retain two-worker runs, authenticated convergence, publisher uncertainty and replacement. [Merged-main activation](https://github.com/TravisMa07/DetectBridge/actions/runs/46098720010/job/140836489604) passed. | A later membership revision governs joins and replacements. Loss of a participant can leave a change incomplete. |
| Recovery, per-output policy and independent rejection (B13–B26) | The [worker ledger](p15b1-ledger.md) records aborted checkpoints, old-outbox release, source-boundary closure, partial-sink retry and the authority-signed inconsistent AST. The [source matrix](p15b-expectations.md) distinguishes late evidence and coverage outcomes. | Fourteen bounded worker scenarios. P16 owns combined failure, late-evidence and restart sequencing. |
| Original evidence, isolated reprocessing and compatibility (B27, B36–B37) | [B2 expectations](p15b2-expectations.md) name input members, command-specific outputs, rollback and current B outcomes. [B2 qualification](p15b2-ledger.md) records passing public synthetic ARM64 and native AMD64 runs. All twelve historical decisions matched their frozen expectations and explicit current B changed eight. | Original source event IDs persist across isolated runs. The current-policy suite selects compatible B explicitly. |
| Retention and preservation (B30–B35) | P15a retains staged and referenced closures. [Worker evidence](p15b1-ledger.md) covers bounded backlog and broker interruption. [Lifecycle archive storage](p15b2-storage.md) places a permanent hold on the entire archive as soon as it exists. | Reclamation is unsupported for this profile. P16 owns combined archive lag, disk pressure and accepted-item accounting. |

## Owner disposition

The [P14 acceptance map](p14-acceptance.md) records the original recorded-source
limits. Private recorded AMD64 remains unavailable. Public synthetic runs cover
the specified workers and fixtures. HA, disk loss, physical power loss,
unbounded outages, rescaling and throughput remain outside these claims.
P16 implementation depends on complete P15b2 qualification and owner review
of the milestone's semantic and completeness evidence.
