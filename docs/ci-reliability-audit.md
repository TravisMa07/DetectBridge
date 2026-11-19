# CI reliability audit: P12–P14

Audit date: 2026-11-18 UTC. This separates dependency setup failures, runtime
defects and qualification-harness defects using original job logs and the owning
ledgers. A later pass is separate evidence; none of the failures below becomes a
passing attempt. No accepted P12/P13 source semantics or resource bounds change.

## Dependency setup: confirmed observations

| Scope / primary job | Actual failing operation |
| --- | --- |
| P12c [43812450381 / 133117070364](https://github.com/TravisMa07/DetectBridge/actions/runs/43812450381/job/133117070364) | `gradlew help`, before assembly tests: Commons IO 2.22.0 and Ant 1.10.17 GETs redirected from Plugin Portal resolution to Maven Central returned HTTP 429. |
| P13b [43973410719 / 133671222677](https://github.com/TravisMa07/DetectBridge/actions/runs/43973410719/job/133671222677) | Linux bootstrap, before adapter tests: Commons IO 2.22.0 GET to Maven Central returned HTTP 429. Integration's later runtime failure in the same run is separate. |
| P13d [44192849293 / 134426563765](https://github.com/TravisMa07/DetectBridge/actions/runs/44192849293/job/134426563765) | Assembly bootstrap: JDOM 2.0.6.1 GET to Maven Central returned HTTP 429. |
| P14a PR [44219814059 / 134518638838](https://github.com/TravisMa07/DetectBridge/actions/runs/44219814059/job/134518638838) | Integration bootstrap: Plexus Utils 4.0.3 and Commons Codec 1.22.0 GETs returned HTTP 429. |
| P14a main [44232624596 / 134561156553](https://github.com/TravisMa07/DetectBridge/actions/runs/44232624596/job/134561156553) | Toolchain bootstrap: Ant 1.10.17 and Plexus XML 4.1.1 GETs returned HTTP 429. |
| P14b PR [44252222524 / 134625439174](https://github.com/TravisMa07/DetectBridge/actions/runs/44252222524/job/134625439174), [search job 134625439249](https://github.com/TravisMa07/DetectBridge/actions/runs/44252222524/job/134625439249) | Windows/search bootstrap: Plexus Utils / Kotlin Metadata GETs returned HTTP 429. Unchanged attempt 2 passed on c18f778. |
| P14b main [44326278636 / 134878372291](https://github.com/TravisMa07/DetectBridge/actions/runs/44326278636/job/134878372291) | OpenSearch writer bootstrap: ten plugin libraries reported missing through the Plugin Portal. No response status establishes HTTP 429. Unchanged attempt 2 passed on 943d143. |
| CI repair main [44339557684 / 134925604133](https://github.com/TravisMa07/DetectBridge/actions/runs/44339557684/job/134925604133) | Shadow implementation POM GET to Maven Central returned HTTP 429 on all three bounded setup attempts. Windows runtime qualification never started. |
| Same main, [attempt-2 job 134950149976](https://github.com/TravisMa07/DetectBridge/actions/runs/44339557684/job/134950149976) | Shadow implementation POM reported missing without a logged 429. A subsequent local GET returned 200; that does not establish the earlier CI response. Unchanged attempt 3 passed on exact b495c2b. |

Owning records retain exact heads, artifacts and original logs:
[P12c](p12c-ledger.md), [P13b](p13b-ledger.md), [P13d](p13d-ledger.md),
[P14a](p14-ledger.md), [P14b](p14b-ledger.md),
[bootstrap repair](ci-bootstrap-recovery.md) and [cache repair](ci-cache-fanout.md).
The first two historical HTTP observations were also checked against their actual
GitHub job logs, rather than inferred from later ledger summaries.

These are failures of public dependency retrieval during Gradle configuration,
not Windows/Linux parser or archive failures. A first failed request can disable
Gradle's repository for that invocation and cascade into many unresolved modules;
the cascade is not evidence of ten independent missing artifacts. `help` configures
the multi-project build, so a Windows job can fail resolving another project's
shared plugin libraries before Windows code runs.

Before the cache repair, the workflow defined thirteen independent Gradle
bootstraps, eleven applicable on the observed push. Repeated cold resolution and
parallel requests are confirmed amplification opportunities. Whether the server's
429 policy was triggered by this workflow, shared runner egress, CDN policy or
broader service load is unknown: failed logs lack response headers and request
identifiers. Plugin Portal routing was not proved to be the cause of the 429s;
direct Central resolution later received 429 too.

## Runtime and harness failures are distinct

| Primary job / owning evidence | Established cause and limit |
| --- | --- |
| P12a [43750911904 / 132924478243](https://github.com/TravisMa07/DetectBridge/actions/runs/43750911904/job/132924478243), [P12b baseline](p12b-ledger.md) | Existing P10 incompatible-restore probe failed with an unrelated marker. Its underlying exception artifact was not retained; cause remains unclassified. An unchanged rerun passed without relaxing the assertion. |
| P13b main [44004484594 / 133776427914](https://github.com/TravisMa07/DetectBridge/actions/runs/44004484594/job/133776427914), [P13c ledger](p13c-ledger.md) | The selected checkpoint metadata was missing at restore. A deterministic regression reproduced selection while running followed by checkpoint retirement before shutdown. Cancel-then-select/verify corrected the harness; the original trace does not prove every timing detail. |
| P13d [44188937618 / 134412888731](https://github.com/TravisMa07/DetectBridge/actions/runs/44188937618/job/134412888731), [P13d ledger](p13d-ledger.md) | The qualifier incorrectly required the first restored checkpoint to follow a processing-time timer. An actual pre-tick completed checkpoint is legitimate. Bounded observation of the original deadline transition corrected the assumption; no production deadline or resource limit changed. |
| P13d [44192849293 / 134426563685](https://github.com/TravisMa07/DetectBridge/actions/runs/44192849293/job/134426563685), [pinned connector correction](p13d-ledger.md) | Retained fatal origins, a fresh ARM64 reproduction and actual pinned-writer regressions established a secondary KafkaWriter send failure rethrown during cleanup after the first failure propagated. The P13-only guard preserves the first required failure and suppresses only the redundant post-close send error. This does not explain older failures with missing exceptions. |
| First PR #54 run [44346736555 / 134952383496](https://github.com/TravisMa07/DetectBridge/actions/runs/44346736555/job/134952383496), [current correction](ci-cache-fanout.md) | Cache restore and bootstrap passed; incompatible restore later failed without the required marker. No original incompatible-job exception artifact survived, so its exact underlying cause remains unknown. A new independent regression reproduces the stale pre-cancellation candidate path, and correction/diagnostic qualification is tracked separately. |

Additional source-visible races in the
[assembly](../tools/linux_assembly.py) and
[integration](../tools/integration_verify.py) broker/deadline probes are under
correction: a checkpoint chosen while Kafka is paused can be superseded after
unpause but before cancellation. A latest-only deadline observation can also miss
the completed checkpoint containing the closure manifest after a later checkpoint
has retired that outbox entry. Inspect independently REST-confirmed completed
checkpoint history for that exact transition. Tests must bind the same admitted
members and absolute deadline to a verified retained checkpoint, allowing legitimate
open-group or exact closed-manifest observations after the intervention. The
pre-pause setup must still establish that the intended pending state and outage
were exercised; an already-finished case is not outage recovery. These findings are not
retroactive attributions for historical jobs lacking their original exceptions.

## Fixes, native evidence and remaining work

[PR #53](https://github.com/TravisMa07/DetectBridge/pull/53) preserves the verified
Shadow marker on the Portal, resolves libraries directly from Central, adds three
bounded HTTP-only setup attempts and retains their logs. It deliberately does not
retry missing coordinates, checksum/compiler errors or runtime tests. A naive
Central-first marker lookup initially failed strict verification locally because
the marker bytes differed; module filters corrected the origin without changing
checksums. Direct routing and bounded retries alone did not remove upstream
availability failures.

[PR #54](https://github.com/TravisMa07/DetectBridge/pull/54) uses the existing real
toolchain job to prepare one verified public-module cache before runtime fan-out.
Its first run already supplies native backend evidence: seed job
[134951104864](https://github.com/TravisMa07/DetectBridge/actions/runs/44346736555/job/134951104864)
logged a cold miss, completed actual `ciDependencies`, and saved the cache at
16:25:40 UTC. All ten applicable downstream Gradle jobs restored the exact cache
and passed bootstrap. Assembly restored approximately 91 MB before its later
runtime failure. This establishes setup/cache reuse, not a passing whole run or
qualification of a later head. Final PR and actual merged-main gates remain
separate.

Priorities:

1. Finish exact-head native qualification of the cache and recovery-harness
   corrections, then qualify any owner-authorized merge independently. Preserve
   the original failures and require their intended fault markers.
2. Add bounded, same-runner diagnostics immediately after a failed pinned public
   artifact request. Allowlist HTTPS dependency hosts/paths and metadata such as
   status, `Retry-After`, `Date`, `Age`, server/cache identifiers and bounded body
   hash. Exclude cookies, authorization and private evidence. A later local probe
   is insufficient to diagnose the failed runner's response.
3. Retain the actual failed restore job's exception and checkpoint identity before
   cleanup. A hash or the previous healthy job's empty exception list cannot
   identify its cause. Keep routine logs value-free and publish only diagnostics
   from explicitly synthetic CI projects.
4. Keep network/cache exhaustion visible. The seed can still fail on a cold cache
   during a real service outage. Neither caching nor a successful unchanged rerun
   guarantees server availability; no generic test retry or resource increase is
   justified by these dependency failures.
