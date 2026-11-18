# CI dependency cache fan-out repair

Scope: follow up the actual merged-main failure after owner merge #53 as
`b495c2bc706d4ac7f2515fe7b1240c5b8ae70904`. This is CI preparation, not P14c1
runtime implementation. P14c1's freeze, local base merge, fixture/compiler and
negative-test preparations remain preserved on its branch and in local stashes.
The original handoff remains uncommitted.

## Evidence and owning choices before implementation

Run 44339557684 Windows job 134925604133 failed during bootstrap on HTTP 429
for the Shadow plugin implementation POM on Maven Central. The new retry policy
worked and correctly exhausted three attempts with delays of eight and eighteen
seconds. Its full original log and all three uploaded attempt files are retained
under `.cache/ci-bootstrap-merge-44339557684/`. Runtime Windows qualification did
not start. This is a failed attempt, not a passing fault assertion.

The workflow defines thirteen independent cold dependency bootstraps (eleven
applicable on the observed push; two are manual opt-ins). The
logs prove sustained throttling for one job; attributing the rate limit specifically
to this workflow's fan-out is an inference, not a server-side diagnosis. Remove
that redundant fan-out rather than extending retry/resource limits or retrying
runtime tests. External repository outages may still fail CI visibly.

Reuse the existing real toolchain-verification job as the single dependency-cache
producer. It runs actual bootstrap, smoke and a new locked/verified Gradle external-
module prefetch task. Runtime jobs depend on its success, then restore its exact
cache before their unchanged bootstrap/qualification. No new passing gate/job or
P15/P16 prerequisite is introduced. Aggregate applicability/failure rules remain.

Use official actions/cache v4 commit
`0057852bfaa89a56745cba8c7296529d2fc39830`, verified against its official tag.
Seed uses its normal restore/save path; consumers use restore-only with exact-key
miss treated as failure. No prefix fallback, broader token permission, privileged
trigger or cross-OS cache is added. A missing/denied cache must not silently fan
out cold downloads. Cache only public external module artifacts and module
metadata, excluding credentials, private evidence, build output, mutable locks,
Gradle verification state and generated script classes. Existing verification
metadata still validates dependency bytes. PR caches stay merge-ref scoped; use
GitHub's default branch/PR cache access boundaries without elevated access.
See [official cache documentation](https://github.com/actions/cache/tree/0057852bfaa89a56745cba8c7296529d2fc39830)
and [scope rules](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

Key by cache-format version, runner OS/architecture and hashes of dependency locks,
verification/catalog/Wrapper files, all Gradle build/settings files and toolchain
pins. The prefetch task resolves only external modules from resolvable Gradle
configurations, without compiling source or running tests. It shares the same
bounded three-attempt HTTP-only setup policy; arbitrary task names and runtime
commands cannot enter that retry helper. Prefetch logs join existing bootstrap
failure diagnostics. Cache availability is a CI dependency, not product durability.

## Independent regression expectations

| Case | Required observation |
| --- | --- |
| All bootstrap consumers | Depend on successful toolchain verification; exact-key restore precedes setup, with failure on a miss and no consumer save |
| Seed | Restores/saves one versioned public-module cache and actually resolves locked external dependencies before downstream jobs start |
| New/changed dependency input | Cache key changes; no unrelated/stale prefix fallback |
| HTTP 429 during prefetch | Same three attempts, preserved logs and bounded delays; exhaustion fails and prevents cache publication |
| Integrity/compiler/runtime failure | No generic retry or successful gate; existing checks remain meaningful |
| Warm cache copied to a clean worker | Actual offline Gradle configuration/prefetch succeeds with strict verification, proving no repository request is necessary for the selected dependencies |
| Missing preparation or cache | Applicable runtime checks cannot silently qualify; aggregate fails closed |

Qualify meaningful old-workflow red, focused regressions, locked source checks,
actual prefetch and clean-worker offline reuse, unchanged runtime JAR hashes and
native CI. Actual merged qualification of #53 is separate; an unchanged rerun can
qualify that exact base without making this additional optimization a circular
feature prerequisite. Owner merge and actual merged checks of this repair remain
separate, and P14 is not complete.

## Local qualification

The old workflow failed the intended ordering/cache regression because no shared
preparation cache existed; log `.cache/ci-cache-fanout-red.log`. The three focused
cache regressions and eight existing retry regressions now pass. Actual locked
`tools/dev.py dependencies` passed with strict verification and no source/test
execution; log `.cache/ci-cache-actual-prefetch.log`.

A new Darwin ARM64 Gradle home received only the two selected module-cache
subtrees, then actual Gradle 9.9.1 `--offline ciDependencies` passed. This proves
external resolution can reuse that portable cache without repository requests;
it does not locally qualify GitHub's cache backend or Linux runners. Worker
identity/result and full log are `.cache/ci-cache-clean-worker-result.json` and
`.cache/ci-cache-clean-worker.log`.

Locked root checks passed 201 Python regressions, contracts/catalog/dependencies,
hygiene/secrets/workflows, lint/format and types; `.cache/ci-cache-source-check.log`.
Rebuilding integration/archive/historical artifacts retained hashes 51a984de,
e5eaea35 and 32bad6f5 respectively (full prior identities unchanged); build log
`.cache/ci-cache-artifact-build.log`. Dependency locks and verification metadata
are unchanged. Exact source/log hashes are `.cache/ci-cache-qualified-source.json`.
Native CI must qualify actual seed/save/restore ordering and all applicable jobs;
local component results do not establish that backend behavior.

The #53 merged-main run subsequently completed with only Windows setup and its
aggregate failed; all other applicable jobs passed. GitHub accepted an unchanged
failed-jobs retry on exact b495c2b. Retain that original failure independently;
the retry result remains pending. This follow-up repair still needs its own PR
qualification, owner merge authorization and actual merged-commit checks.
