# P14 archive and replay acceptance map

Current completion (2026-11-19): **P14 is Done within its owner-accepted bounded
scope.** The owner explicitly selected “Accept bounded P14 completion” in the P15
continuation session after reviewing this packet, including unavailable private
recorded AMD64 coverage and no HA, disk-loss, unbounded-outage or throughput claim.
The owner merged #54/#52/#55 as the single two-parent merge
`f44c9f91e10414cd2b03481951a2e2a1c7b2a4a0`. Its actual push run
[44458422172](https://github.com/TravisMa07/DetectBridge/actions/runs/44458422172),
attempt 1, passed all eighteen applicable jobs and required-checks; five explicit
acquisition/recording opt-ins were skipped. Issue #14 is closed and its project
card is Done. M5 remains open for P15/P16. [Exact audit](p14-merged-main-audit.md)
records the evidence and separate owner disposition. P15's own gates still apply.

## Historical pre-merge acceptance checkpoint

The requirement map below retains the pre-merge packet and exact artifact evidence.
The current completion above supersedes its pending native/merge/owner statements;
no earlier failed run is reclassified.

The [milestone design](p14-design.md), [independent matrix](p14-expectations.md),
[P14c1 freeze](p14c1-design.md) and [P14c2 expectations](p14c2-expectations.md)
define the required behavior. The [P14c2 ledger](p14c2-ledger.md) retains failed
attempts, corrections, exact artifacts and unavailable coverage.

## Prerequisites and slice gates

| Scope | Exact evidence | Disposition |
| --- | --- | --- |
| P05/P13 prerequisites | [P13 acceptance](p13-acceptance.md), accepted P05 local replay and exact P13 merged-main 44206958555 on 07e5382 | Complete within accepted bounds; no archive capability inferred from local replay or search |
| P14a archive | Owner merge #50 `cd6f46ec70e6c7ca17e3cd21594e396ef541509c`; merged-main [44232624596 attempt 2](https://github.com/TravisMa07/DetectBridge/actions/runs/44232624596); [ledger](p14-ledger.md) | Bounded archive merge/qualification complete; original failed bootstrap attempt retained |
| P14b historical replay | Owner merge #51 `943d143eb4e5dc6d07871513f993efbddf1ab230`; merged-main [44326278636 attempt 2](https://github.com/TravisMa07/DetectBridge/actions/runs/44326278636); [ledger](p14b-ledger.md) | Bounded historical merge/qualification complete; setup failure is separate evidence |
| P14c1 current replay | [44408227593](https://github.com/TravisMa07/DetectBridge/actions/runs/44408227593), associated head `8e4c832283268897887999efe22152b2f0b41eb5`; actual checkout test merge `096ddc136b5769de5f8537608873647b5809df96`; [ledger](p14c1-ledger.md) | Native Linux AMD64 implementation checks passed; owner acceptance/merge and actual merged qualification remain separate |
| P14c2 freeze | Original `a19693bccd346d24c5c3d899dafea5a1a139b435`; independent recorded-count correction `786ec141d3dff4ea058bdb429fbca45e7216b41b` | Both boundaries preserved; corrected expectations precede new recorded runtime |
| P14c2 earlier managed candidate | M62ab, 39-case ARM64 report and approved-original P05 import/restore below | Bounded historical evidence only; later M11 safety finding prevents final adoption |
| P14c2 intermediate candidate | `c799655e30d57656ba1c20a6108a829d4dd301740b79cbafe2ac65e88addadd7`; probe `08445057e76929800d628387c78abc0c0610ee9ed4ff0ee84d92027653f2a875` | Build, 52 Java tests, legacy/resource checks and 44-case ARM64 runtime passed; separate source-fingerprint defect requires another artifact; no final qualification transferred |
| P14c2 final local candidate | `9598289011727e96e1e633642f6926893161c5889e90ffe1cdd85c2642ff46df`; probe `354756bf1d9e835eb366d17b645e2358295ee8c055555734aa410f18babf32bb` | Build, 53 Java tests, exact legacy/resource checks and full 44-case ARM64 runtime passed; approved-original P05 import/restore also passed; fresh controlled-recording qualification and native run 44449578701 passed; owner/merge gates pending |

Empty review-thread lists and CI success are not independent owner semantic
acceptance. No owner merge/release authorization is supplied by this map. The
qualified P14c1 stack can support explicitly authorized P14c2 work without
pretending that its PR test merge is an actual merged-main run.

## Requirement-to-evidence map

| Independent requirements | Implemented boundary and evidence | Remaining acceptance |
| --- | --- | --- |
| B01–B10: exact bytes, framing, objects/ranges, identity/time and malformed metadata | P14a [acceptance map](p14-ledger.md); original gzip/NDJSON schemas and pinned E5 reader; managed legacy-source/resource pins | Final 95982890 passed its compatibility/corruption cases; private bytes stay local |
| B11: existing consumers | P14a/P14b native gates; P14c1 native source/assembly/integration/search compatibility; unchanged producer/reader/executor identities | Final P14c2 native checks passed on exact associated head 7b9520c; no pass transferred to a future merge |
| D01–D15 and I01–I03: durability, offsets, retry/conflicts and recovery | P14a actual Kafka/filesystem fault qualification; M62ab managed Kafka, anchors, duplicate/new-occurrence/conflict and broker-pause cases | Final 95982890 full 44-case runtime passed, including four metadata midwrite/sync crash windows |
| L01–L05 and T03: finite budgets, dependency backlog and P16 progress | P14a finite admission; M62ab actual payload ENOSPC, sync-EIO injection, lower-cap backlog and broker progress cases | Final 95982890 pressure/failure cases passed; no unbounded outage or Kafka deletion claim |
| H01–H08: pinned original-membership reproduction | P14b actual original producer and two isolated replays, native AMD64; P14c2 M62ab synthetic managed seals/replays | Final 95982890 reproduced two isolated 62-output recorded historical runs; native run 44449578701 passed; owner/merge gates pending |
| C01–C03: explicit changed policy and membership | P14c1 Image/Bob and regroup/timeout/deadline/resource expectations; local ARM64 and native AMD64 passed | Final managed-profile cases and 49-output recorded current replay passed; native checks passed; owner/merge gates remain |
| R01–R03: isolated recovery and incompatible/corrupt resume | P14b and P14c1 actual interruption matrices; M62ab managed same-operation current prefix recovery | Final 95982890 managed recovery/metadata windows passed; old recorded attempts remain failed |
| R04 and P14c2 Q06: independent semantic rejection | P14c1 source/count/attribution/membership mutations; separate M62ab retained-output checker rejects nine detached mutations and verifies 30 original audit ranges | Fresh final 95982890 run rejected all nine mutations and verified 30 original ranges; old failed attempts remain failed |
| T01 and P14c2 M09–M14: pins, holds, reader leases and retained dependencies | M62ab demonstrated explicit holds, shared-reader exclusion and sealed-pin blockers | Strict-profile/import graph and INPUT-only fingerprint regressions passed; final 95982890 future-graph runtime passed |
| T02 and P14c2 M04–M08/M15–M17: retirement authority and anchors | M62ab actual retirement publication/cleanup, explicit retired retrieval, append and source fingerprints | Final 95982890 passed strict graph/import/fingerprint regressions and all 44 runtime cases |
| P14c2 I01–I06: completed P05 import/restore | Existing-source component cases and M62ab approved-original run: 7,046 records, 7,051 envelopes, eight segments, 33 exact files, original inspection/completed resume | Final 95982890 repeated approved-original import/restore, exact 33 files and unchanged originals; native original coverage remains unavailable |
| Q01 and P14c2 Q07: privacy and logs | Fixed category/class summaries; original exceptions and source packets kept in ignored private locations; no recapture/upload | Locked source/hygiene checks passed 289 Python regressions; native artifact checks passed; private payloads are excluded from public CI |
| Q02 and P14c2 Q01–Q05: controlled originals | Exact accepted catalogs/terms/source bindings reverified; old M62ab attempt reached historical/current execution | Fresh project 68401cb415 passed 49 admissions/160 exact wires, two historical runs, current replay, Q06, zero lag and default-build restore |
| Q03 and P14c2 Q08: evidence discipline and milestone closure | Exact artifact/report attribution and retained failures in owning ledgers | Final packet, owner semantic/completeness acceptance, authorized merges and actual merged-commit qualification pending |

The old import planner also omitted retained-wire scanning: three independent
pre-fix cases allowed retirement despite references to the import/run. Unknown
graphs and recognized identity intersections now block under finite scan budgets;
fifteen focused tests passed. c799 includes this correction, but an actual
c799-JAR red then demonstrated derived-topic raw/context poisoning of source
fingerprints. The input-topic-only correction passed 37 focused planner/graph/
import tests. Final replacement 95982890 passed the resulting 53 Java tests and
44 actual runtime cases. These findings and
original red/green logs are retained in the [ledger](p14c2-ledger.md).

## Recorded expectations and retained attempts

The accepted catalogs contain audit 27 group members plus three extraction
failures, auth two normalized plus nine unsupported, and Windows four eligible
plus one unsupported. The 46 originals therefore yield thirteen preservations.
One separately identified controlled late cursor adds a fourteenth; exact
redelivery adds only a receipt. Current output is 16 tagged + 10 manifests +
14 preservations + nine quality diagnostics = 49, with zero detections. This
correction was derived before new runtime output. The old P13 original-only
thirteen remains correct; P13d's two-run total is 28 after controlled late inputs.

Corrected packet SHA-256 is
`46eede25ee08f2f2cd576de96417004bc0c4e53a3f582031aea7040f6216e3dd`.
Historical/current grouping, source fields, quality and all other frozen expectations
are unchanged. No recapture, new identity inference or old-checkpoint adoption is
permitted.

Old M62ab recorded attempt `cdf028be02` failed a qualifier topic-inventory lookup:
P13 creates eight topics while archival requires a ninth writer-failure topic.
Its original traceback was not retained by that version; preserve this diagnostic
limit. The correction actually provisions only the missing topic before source
admission and verifies the existing eight identities/offsets unchanged.

Old M62ab attempt `e9d80ec920` passed source/archive checks and two historical
replays with interrupted resume, then failed current-oracle manifest comparison.
P12's source preparer shares one context across audit rows. Copying the collection
retained that alias, so assigning per-step receipts overwrote earlier expected
clocks. Per-admission copies fix this checker defect. Only expected member context
hashes and manifest identity differed; no frozen count, schedule, source field or
actual output was changed. Both failed reports remain failed.

A separately attributed corrected checker passed against detached retained output,
including field, host, context, membership, counts, match, attribution, original
range and original-byte mutations. This is diagnostic/component evidence, not a
clean end-to-end pass or qualification of the replacement managed artifact.

## Final local evidence and remaining gates

Final artifact 95982890/probe 354756bf passed 53 Java tests and all 44 actual
synthetic runtime cases on Linux ARM64. Approved-original P05 import/restore
preserved all 33 files and original run/cache snapshots. Fresh controlled-recording
project `detectbridge-p13-archive-recorded-68401cb415` passed 49 admissions and 160
exact physical archive wires, two isolated 62-output historical runs and 49-output
current replay, actual interrupted/same-operation/completed resume, nine rejected
mutations and 30 verified original ranges. All nine topic lags reached zero;
originals stayed unchanged, default integration build was restored and owned
cleanup completed. Full exact plans, bundles/images, source attribution, logs and
report hashes are in the [ledger](p14c2-ledger.md). These local results were run
on 786ec14 plus the attributed implementation changes, not a future commit.

- Locked source checks passed 289 Python regressions; maintenance build/components passed.
- Native implementation CI passed every applicable job in run 44449578701 on
  7b9520c; actual checkout was PR test merge cbbc63c, not merged main.
- Refreshed comments/reviews/threads were empty; explicit milestone semantic review remains.
- Owner performed regular merge #55; #54/#52/#55 report one actual merge object f44c9f9.
- Actual merged-main push run 44458422172 attempt 1 passed all applicable jobs and required-checks.
- Owner explicitly accepted bounded P14 completion in this continuation session;
  issue #14 and its project card are complete. M5 remains open for P15/P16; no release is authorized.

Private recorded native AMD64 coverage is unavailable. Local Linux ARM64 private
recordings and public synthetic native jobs remain separate evidence. Process kills,
actual bounded tmpfs failures and injected EIO do not establish physical power-loss,
local-disk-loss, distributed/HA storage or throughput behavior. No default retention
period, activation, management API/UI, Kafka deletion or release is delivered here.
