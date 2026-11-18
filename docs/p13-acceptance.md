# P13 implementation and acceptance map

Current completion (2026-11-18 UTC): **P13 is Done within its owner-accepted
bounded scope; P14 prerequisites are met.** The owner explicitly accepted final
head `85818875576616e42aa26720dc74486f93b9655c`, including unavailable private
recorded AMD64 qualification and separate supplemental synthetic coverage, then
performed regular merge [#49](https://github.com/TravisMa07/DetectBridge/pull/49)
as `07e53822dd8a5035125804321e5c852f9a466aef`. Final-head run 44202078968 and
actual merged-main push [44206958555](https://github.com/TravisMa07/DetectBridge/actions/runs/44206958555),
attempt 1, passed every applicable job and required-checks; merged run completed
2026-11-18 00:43:43 UTC. Refreshed review threads are empty and issue #13 is closed.
This completion supersedes pending-status checkpoints below, preserving every
historical failure, artifact attribution and bounded limitation. No P14 runtime
capability follows; its own design/freeze/qualification gates remain required.

Pre-merge acceptance checkpoint (2026-11-17): **P13 remains open; P14 is not ready.** P13a–c are owner-merged bounded
slices. [P13d PR #49](https://github.com/TravisMa07/DetectBridge/pull/49)
adds original-recording qualification and the remaining acceptance packet.
Implementation, qualification, owner semantic/completeness acceptance, resolved
review, merge authorization and merged-commit success are separate gates.

## Prerequisite audit

Refreshed 2026-11-17 against base
`0f6d758b8228a3ccce35f1af83174addc4835126`. GitHub reports each PR below merged;
all inspected inline review-thread lists are empty. An empty list is not a new
owner semantic approval. Historical pending text in earlier ledgers records its
original checkpoint; the subsequent evidence below supersedes that status only.

| Bounded deliverable | Exact PR head | Exact merged artifact | Applicable qualification and disposition |
| --- | --- | --- | --- |
| P05 replay, #26 (P14 direct dependency) | `d8d2a745f65c4884d68b21662e0bf6e7b99b1034` | Historical `30b14627d32036f30d2afb6573f325e8ef6e4cc3`; restored `ee3ad63f872e88500748e2e693fcb125a1fd201f` | Required 43337097483 and opt-in recorded replay [43337148531](https://github.com/TravisMa07/DetectBridge/actions/runs/43337148531) passed; issue #5 closed; bounded local replay only |
| P09 compiler/evaluator, #34 | `dc13530426d14784870b0f78de120772640e4fd8` | Historical `4d7d685ae65b2163906f7b662aac411583c5250d`; restored `172b77427f6062e777538184cb75009fa189a549` | Final-head 43618611836 and historical merged-main [43655314953](https://github.com/TravisMa07/DetectBridge/actions/runs/43655314953) passed; owner accepted bounded semantics on 2026-11-17; issue #9 closed |
| P10a mapping, #36 | `b3e118fe451c31bad84a5a46f71d11edd1b22109` | Historical `b45fba48b57eb360087521bc9ba06113cb34ef88`; restored `199c25d8926a003cb8bc231696f86868cdfe67d6` | Exact-head 43661432091 and historical merged-main [43673156008](https://github.com/TravisMa07/DetectBridge/actions/runs/43673156008) passed; bounded semantic review accepted on 2026-11-17 |
| P10b selection/runtime, #37 | `db2cddf37be972da57f8185d5d86098165bc88b8` | Historical `df3144822ddd5694b9244ae29eb4a3c9e2815376`; restored `71242918fcc867d43cdbc2008cd97bad2e881d87` | Final-head 43678093289 and historical merged-main [43679437257](https://github.com/TravisMa07/DetectBridge/actions/runs/43679437257) passed; owner declared P10 finished/authorized dependent work; bounded expectation review accepted on 2026-11-17; issue #10 closed |
| P08 writer, #35 | `4dfc1f0296059f12090430655d087af9b1387a97` | Historical `430609a17996470159f07fc0cfe53028e552a5ef`; restored `4cf6850d1ce7b491f193606ffbe7e1f0717a4d12` | Exact-head [43649896735](https://github.com/TravisMa07/DetectBridge/actions/runs/43649896735) and historical merged-main 43652317692 passed; history mapping below |
| P11 initial adapters, #38 | `aa1afacc89a09dd9ecda64d338e46565b50237f2` | `46fb080013e4623eb019e6ada829fc909a7cbfe0` | Exact-head [43742653410](https://github.com/TravisMa07/DetectBridge/actions/runs/43742653410) passed; older public inputs remain missing trusted identity/unsupported; controlled completion is #45 below |
| P12a adapters, #39 | `81904936257c29d81be79b88843772ef2c6010ea` | `9ea1c68e0846e27ffa4ae94390429b5330ceb5b0` | Exact-head [43749273538](https://github.com/TravisMa07/DetectBridge/actions/runs/43749273538) passed; bounded source acceptance is #43 below |
| P12b checkpointing, #42 | `fd3607e5397b16a0ca35447d65e61de5dbbafb69` | `e2d06c3a8519673455f7662a0928c24823fe249e` | Final-head 43768117676 and merged-main [43804124770](https://github.com/TravisMa07/DetectBridge/actions/runs/43804124770) passed; limits/history in its ledger |
| P12c recorded acceptance, #43 | `adf71f8301d0b6c8ebcd4dc81d590186b6288ee3` | `c02449745ddb87605d0bd85841f77fdad2fb382a` | [43812450381 attempt 2](https://github.com/TravisMa07/DetectBridge/actions/runs/43812450381) and merged-main [43873905332](https://github.com/TravisMa07/DetectBridge/actions/runs/43873905332) passed; owner bounded semantic/completeness acceptance and merge authorization recorded in #43 |
| P11 controlled completion, #45 | `a52847214d7d2aa0eccf1464854348f334ade6e4` | `4ac31fa50cf8f3a23db89afc7436710bfe7a9a93` | Exact-head [43884159909](https://github.com/TravisMa07/DetectBridge/actions/runs/43884159909) passed; owner bounded acceptance in [review packet](p11-recording-review.md); merged-main [43900545102](https://github.com/TravisMa07/DetectBridge/actions/runs/43900545102) passed |
| P13a compact outputs, #46 | `8050b315914d837c9a3ff2c3a6e1f1156d0a3329` | `e09c2712b685a627895067b5a0c4bfc39fe7b59e` | Exact-head [43917575419](https://github.com/TravisMa07/DetectBridge/actions/runs/43917575419) and merged-main [43954609201](https://github.com/TravisMa07/DetectBridge/actions/runs/43954609201) passed |
| P13b integrated runtime, #47 | `8cc680ce069e432908fd18aa6714e4c49f4e3e6a` | `500ffc79deb8843488cbdaa85e4d5ebf64e82b70` | [43978412654](https://github.com/TravisMa07/DetectBridge/actions/runs/43978412654) passed; merged-main 44004484594 failed assembly checkpoint selection, preserved in P13c ledger |
| P13c search, #48 | `8588c8dbfdb9ddd768507faaf19bb469c1481821` | `0f6d758b8228a3ccce35f1af83174addc4835126` | [44023058246 attempt 2](https://github.com/TravisMa07/DetectBridge/actions/runs/44023058246) passed; merged-main [44145796752](https://github.com/TravisMa07/DetectBridge/actions/runs/44145796752) failed integration and aggregate; every other applicable job passed |

P08 issue #8 is closed within its metadata-writer scope. Merged artifact `430609a17996470159f07fc0cfe53028e552a5ef`
and [merged-main 43652317692](https://github.com/TravisMa07/DetectBridge/actions/runs/43652317692)
qualified its actual writer; P13c's separately versioned three-index writer is
required for P13. Its P08 compatibility regression remains in the P13c ledger.
The owner-authorized [history restoration](history-restoration.md) replaced P08
merge 430609a with current-main ancestor 4cf6850. Both have exact tree
`230d8c65e1149af23ff7687e43be612e891914ca`; this byte identity does not transfer
historical CI to a new SHA. Later current-history P13c P08 compatibility and P13d
native P08 checks supply separately attributed runtime evidence.

P05/P09/P10 history was restored under the same owner-authorized migration.
Historical/restored tree pairs were verified identical: P05
`26260d5a9d8901eaf7f86da611945257da95cab2`, P09
`05967991ac1f508012eef52402ce8573c27ffdf1`, P10a
`d9c4ee11b7bbf8738a3ae9dcf5b75c47306f8fde`, P10b
`f875fe64cd80cc58e51ef4ab248bc945d2bbca4d`. No historical CI is reassigned to
restored commit IDs. Later current-history detection checks independently exercise
the legacy and mapped consumers. P05 is a completed local replay prerequisite,
not a claim that P14 archive/replay services exist.

P09/P10 issues #9/#10 were initially still open, with independent expectation
review pending in their historical designs/PR bodies. After reviewing the exact
32-case [prerequisite packet](p13-prerequisite-review.md), the owner explicitly
accepted the bounded P09/P10 semantics and completeness limits on 2026-11-17.
Both issues are now closed with exact fixture/packet hashes and qualification
references. This supplies the missing independent review while preserving earlier
authorization to proceed with P11/P12; it does not accept P13 or authorize merging.

P11 #11 and P12 #12 were closed after this audit with completed bounded acceptance
in #45/#43 and exact CI evidence recorded in their issue bodies. This tracking
correction does not treat P13 as Done.
P13 #13 remains open until the final gates below pass.

All refreshed successful runs above passed their applicable jobs and aggregate.
Recorded/acquisition opt-in skips are not recorded qualification. P12c's initial
Maven Central HTTP 429 failure preceded tests; its unchanged rerun passed. P13b's
older unexplained processing-sink failure remains a failed attempt. P13c's first
AMD64 attempt and earlier source/time/permission failures remain historical in
its ledger. No historical failure is erased or reclassified as a pass.

## Requirement-to-evidence map

| P13 requirement | Exact implementation/evidence | Limit or remaining gate |
| --- | --- | --- |
| Tagged events, one linked detection per match | P13a output 1.0.0 and P13b runtime 1.1.0; literal identity vectors; compact/exhaustive independent semantic cases | Fixed 100-rule/100-match bounds; no per-rule nonmatch documents |
| Six distinct outcomes and source quality | Independent P13a/b fixtures, actual P13c synthetic source-to-search suite; P13d recorded twelve-rule [expectation freeze](p13d-design.md) | Recorded inputs cover matched/nonmatched/inapplicable/blocked/skipped; error/budget and missing-identity cases remain explicitly synthetic |
| Bounded diagnostics, pinned enrichment | Rule-set bit membership/count/hash, source/context/parser/mapping/compiler/evaluator/selector and enrichment-policy hashes; empty external inputs | No live enrichment or activation service |
| Actual source adapters and assembly | Kafka/Flink P13b job uses WindowsAdapter, selected Linux auth adapter, prepared audit assembler and Java evaluator | Exact selected source signatures/grammars; no generic corpus-completeness claim |
| Source-to-search metadata and retrieval | P13c exact three-index writer; P13d opt-in `verify --recorded`, original artifacts checked before runtime; independent source and search field checks | OpenSearch remains a derived view; originals retained locally/in Kafka, no archive claim |
| Original provenance and independent expectations | Accepted controlled catalogs, original byte hashes, terms, capture/host/boot bindings, P11/P12 source assertions; P13d freeze commit `55e9715` precedes implementation `7446337` | Older public Windows identity remains unknown; no inferred binding |
| Logical/physical accounting and isolated replay | P13d verifies every admission/receipt/member/reference, stable event/evidence identity, isolated processing/detection IDs, exact logical kind counts and Kafka retrieval hashes | ARM64 cleanup-guard project 8348892e80 passed 99 admissions, 223 logical/233 physical outputs and 76 search documents; [exact artifacts](p13d-ledger.md) below |
| Checkpoint/deadline and required-sink recovery | Existing full assembly/integration suites; P13d recorded original-member checkpoint, TaskManager/deadline recovery, tagged-sink rejection and explicit restore | All seven P13b sinks/five P12 sinks remain required; no unrelated failure satisfies a rejection assertion |
| Pinned writer cleanup failure | Five actual pinned-connector regressions reproduce the stock error and preserve primary/cleanup/JVM failures; full ARM64 required-sink recovery passes with the guard | P13-only package-access bridge pins connector 5.0.0-2.2; review/remove on dependency changes; new artifact requires a fresh project, no old-checkpoint migration |
| Duplicate/conflict and writer commit ordering | P13c actual duplicate/tamper/conflict, partial bulk, failure publication/indexing backpressure and index-before-uncommitted-crash suite | At-least-once contract; no exactly-once or immutable-storage credential claim |
| ARM64 and native AMD64 | Cleanup-guard JAR 51a984de passed full ARM64 integration/recorded/search and every applicable native AMD64 job plus required-checks in 44196952063 | Native ordinary CI is synthetic; private recorded AMD64 qualification is unavailable and remains an explicit owner-review limit |
| Review, accepted integration and P14 readiness | Concrete owner packet below; PR #49 and issue #13 | Final documentation-head checks, owner acceptance, resolved review, explicit authorized merge and successful merged-commit checks remain mandatory |

## Concrete owner semantic/completeness packet

Review the [P09/P10 prerequisite expectation packet](p13-prerequisite-review.md)
and the twelve-rule literal table and bit positions in [P13d design](p13d-design.md),
unchanged source policies in the accepted [P11 packet](p11-recording-review.md) and
[P12 acceptance map](p12-acceptance.md), and exact reports/artifacts/failures in the
[P13d ledger](p13d-ledger.md). Selected Windows cmd/hostname pairs demonstrate
actual positive/negative outcomes; the Linux probe demonstrates actual match plus
capability blocking; both password events are real nonmatches. Nine audit groups
remain quality-skipped and unsupported/extraction-failed originals remain preserved.
Controls, duplicates and the new qualification late cursor are explicitly counted
separately from the original 46-record population per replay.

Owner acceptance is requested only on a completed concrete evidence packet. This
map does not claim that acceptance has happened. Any unavailable platform/source
qualification remains explicit. Separate merge permission is still required after
review; no release or P14 implementation is included.
