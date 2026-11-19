# CI dependency cache fan-out repair

Scope: follow up the actual merged-main failure after owner merge #53 as
`b495c2bc706d4ac7f2515fe7b1240c5b8ae70904`. This prepares shared dependencies
and corrects recovery qualification/diagnostics; P14c1 implementation is separate. P14c1's freeze, local base merge, fixture/compiler and
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

Actual merged-main 44339557684 attempt 2 also failed Windows setup and aggregate.
Job 134950149976 reported that the exact pinned Shadow POM could not be found;
it did not report HTTP 429. Full original log is retained as
`.cache/ci-bootstrap-merge-44339557684/windows-attempt-2.log`. A subsequent direct
GET of that exact Maven Central URL returned HTTP 200 on 2026-11-18 16:24:24 UTC,
recorded in `shadow-pom-probe.json` in the same directory. That local availability
check does not establish what the CI endpoint returned or qualify a failed job.
After inspecting that evidence, another unchanged failed-jobs retry was accepted.
No generic missing-coordinate retry, checksum change or passing CI claim is added.
These observations remain local while the separately published cache repair is
being qualified on native CI.

## Assembly qualification correction after first PR run

PR #54 run 44346736555 at a21bec7 passed cache restoration and bootstrap for
Linux assembly, then failed the incompatible-restore probe in job 134952383496.
The original full log and artifact inventory remain in
`.cache/ci-cache-pr-44346736555/`; that run retained no original incompatible-job
exception artifact. Its category `assembly_unrelated_restore_failure` is not the
required `incompatible_assembly_restore` assertion and remains failed. The exact
underlying exception of that original job cannot be recovered from its hash.

An independent focused regression reproduces a source-visible race: the running
job can supersede/delete a candidate checkpoint before cancellation. The old
probe uses that stale path and fails with an unrelated restore error. Reselect the
verified retained checkpoint after cancellation using the existing lifecycle API,
and use that same retained checkpoint for the subsequent healthy restore. Retain
the actual incompatible job's original exception before checking its marker;
wrong failures still raise, and only narrowly selected synthetic assembly reports
are uploaded after CI failure. No service semantics, resource limits, sink marker
or expected incompatibility marker changes.

The race and missing-diagnostics regressions failed before correction in
`.cache/ci-cache-assembly-probe-red.log`, then passed. Actual local Linux ARM64
container qualification passed project `detectbridge-p12-test-6f797dd978ff`:
52 inputs, 83 logical / 93 physical outputs, ten verified duplicates, all five
sink failures, 40-second broker outage, TaskManager/JobManager and healthy/invalid
restore, plus limits and serialized-byte pressure profiles. Retained checkpoint
36 produced the exact required marker in incompatible job
`fa34cd8726730fe215fc4b6104ab8105`. Full exception artifact SHA-256 is
`93021eb0aa86e7bc4a17296e0c29beca23d68f2a0cb28dc37b26e79283508576`;
it and the report remain under `.cache/linux-assembly-reports/`.

Exact unchanged assembly JAR is
`d341724639876de0e09a5006bf2e265172a75cd16b7d03b495dc1f4086d19a99`;
bundle `9cba7aed38a1dfd2a3ad57e46cb785cb7863807a13809afa41bfb0c95dad2f15`,
Linux ARM64 image `sha256:805b4978b6a2eb9816c6a66f77922cdfd07b84dfd35a92d03c3fed3875bdf4c8`.
Component/image/runtime logs are `.cache/ci-cache-assembly-component.log`,
`.cache/ci-cache-assembly-image.log` and `.cache/ci-cache-assembly-runtime.log`.
This independently corrects a reproducible harness race; it does not retroactively
assign that cause to the original CI failure whose exception was not retained.

Separately, actual #53 merged-main run 44339557684 attempt 3 passed every
applicable job/aggregate on exact b495c2b at 2026-11-18 16:27:17 UTC; both earlier
attempts remain failed. Metadata is retained in
`.cache/ci-bootstrap-merge-44339557684/attempt-3-completed.json`. P14c1 may now
implement from that qualified base. This additional PR's correction still needs
native qualification on its own final head and owner-authorized integration.

## Follow-up fail-closed cache and outage observations

The cache action's unsupported-backend branch can return successfully without
restoring bytes, before its `fail-on-cache-miss` branch. Every consumer now checks
that the restore action returned literal `cache-hit: true` before bootstrapping.
The regression executes the actual guard with absent, false and malformed values;
none can silently fan out cold requests. No token permissions or cache contents
are expanded. Red/green logs are `.cache/ci-cache-exact-hit-guard-{red,green}.log`.

Source-visible broker recovery probes also selected a checkpoint while Kafka was
paused, then allowed it to advance after unpause before cancellation. Quiesce the
job while Kafka remains paused, independently verify its retained completed
checkpoint, and bind its exact pending members/opening/deadline or frozen manifest
before unpause. A latest-only integration deadline observation can miss the exact
closure outbox after retirement; bounded REST-confirmed completed history can
prove that transition without restoring an obsolete candidate. Changed members
or deadlines still fail. Ten focused checkpoint-observation regressions cover
terminal state/path/job validation, ordering, changed state and history eviction.
Original historical CI failures lacking exceptions are not assigned these causes.

The first local updated assembly attempt, project
`detectbridge-p12-test-cdc6701e747e`, failed with a `KeyError` because the new probe
expected `opened`/`deadline` fields absent from P12's diagnostic inventory. That
is a harness-shape failure, not a passed outage assertion; full log remains
`.cache/ci-cache-assembly-quiesced-runtime.log`. Add those fields from the original
opening time and configured age without changing recovery state, timers or output.
An actual Java regression proves the inventory remains stable across clock
advancement/restore and leaves snapshot bytes unchanged; its baseline red and
11-test green are `.cache/assembly-inventory-deadline-{red,green}.log`.
This changes the P12 assembly JAR identity, so the earlier d341 artifact's pass
above does not qualify this subsequent revision. Rebuild and runtime evidence are
recorded separately below. See the [cross-milestone audit](ci-reliability-audit.md)
for confirmed HTTP failures, independent harness findings and unknown causes.

## Updated assembly artifact qualification

After the inventory correction, actual Linux ARM64 runtime passed project
`detectbridge-p12-test-017820ed6bd4`: 52 inputs, 83 logical / 93 physical outputs,
ten verified duplicates, all five required sink failures and recovery, TaskManager/
JobManager recovery, valid/incompatible restore, the 40-second broker outage and
both member/serialized-byte pressure profiles. The broker remained paused until
terminal `CANCELED` checkpoint 40 proved the original deadline/membership or exact
frozen closure. Its private synthetic report hash is
`4f959ad8eba4d894b5a6af2117c0f85101ef64053bca0cbd682bb8934fcd88bc`.
Incompatible job `22d38009a2f62d0bd840388cb5d43176` restored retained checkpoint
27 and produced the required marker. Its original exception artifact hash is
`bb861695243c22bcaaafa00b68df5c2dd9ec34b2e5154719acc89e878c5b7bbb`.

Exact new assembly JAR is
`b328f293d35bbaccdf4a093f85dd43c6a278b5141d23ef99166e55e5edeb92e9`;
bundle `b6c9f3b1d6b978dccf3d4cd57849329e26218caa779aa92f16b06c53abe62c84`;
Linux ARM64 image
`sha256:ed7586d72bfd8f2f178ac1dfd8e1aa110c9a2f5428d76a908f2134b9b286f3a5`.
Component/image/runtime logs are `.cache/ci-cache-assembly-inventory-component.log`,
`.cache/ci-cache-assembly-inventory-image.log` and
`.cache/ci-cache-assembly-quiesced-final-runtime.log`; reports remain under
`.cache/linux-assembly-reports/` and the isolated runtime project directory.
The earlier d341 pass and intervening harness-shape failure remain separate.

Locked checks passed 216 Python regressions plus contracts/catalog/dependencies,
hygiene/secrets/workflows, lint/format and types in
`.cache/ci-cache-recovery-final-source-check.log`. Independent read-only review
found no concrete blocker; it is not owner acceptance or native runtime evidence.
Integration Java/components passed seven regressions in
`.cache/ci-cache-integration-component.log`; its original JAR remains exactly
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
Actual integration recovery qualification and final-head native CI remain separate.

## Integration recovery qualification passed

Actual Linux ARM64 integration passed project
`detectbridge-p13-test-2722e1625dab`: 44 inputs, 20 events, 103 logical / 145 physical
outputs, all seven required sink failures and healthy restores, TaskManager/
JobManager recovery, incompatible-binding rejection and 40-second broker pause.
Kafka remained paused until producing job 97732684650381f7864fc8bfee7015ab reached
`CANCELED` with retained completed checkpoint 37. During and terminal inventories
contained the exact original members/opening/deadline. Restored checkpoint 38
contained the expected closure manifest and outputs. This run directly observed
the closure; completed-history fallback is unit-qualified but was not exercised
by this particular runtime timing. No claim of reproducing that timing is made.

Exact integration JAR remains 51a984de (full identity above); bundle is
`37ea54a0060c7c5e64c0d649672aae83a4ca2e8b707a3ae45002143f932586a5`,
Linux ARM64 image
`sha256:1cff386f71c99bd26903ad988000ab9f5fb5dbb75592b790f86d8b2699a86f97`.
Plan is `720a40d3e03be2225976a6cb3e83f5553e0517fd3092cba92fcda56c27e470f4`;
evaluation bundle `b2a7dadff65b179e10260a0aa99d4070052df898bc7d7de2e55e122b5ba1e433`.
Build/runtime logs are `.cache/ci-cache-integration-quiesced-image.log` and
`.cache/ci-cache-integration-quiesced-runtime.log`; runtime log SHA-256 is
`bde20604c633104067e64e155e823b58b8bb45168e688034b08dc3023bb9ce6b`.
The retained paused proof hash is
`65763cac4d7ebfc75bdf611a6d4c3a1c85e20cfe0164e8cb93d0ba239248e5ed`.
Reports/proofs remain under `.cache/integration-reports/` and the isolated runtime
project directory. Cleanup left no project containers. Source was a21bec7 plus
this uncommitted correction batch; generated plan/image identities do not transfer
to a rebuilt or native CI artifact. Final native PR and actual merged gates remain.
