# Dependency bootstrap failure recovery

Scope: correct repeated Gradle setup failures observed in P14a/P14b PR and actual
merged-main runs. This changes development/CI bootstrap only, preserving dependency
versions, locks, artifacts, runtime fault assertions and required aggregate behavior.
Owner: primary agent. P14c1 #52 stays design-only until its merged prerequisite is
qualified. This repair does not authorize merging either PR.

## Evidence and owning choices before code

P14b PR run 44252222524 attempt 1 failed Windows/search setup on Maven Central
HTTP 429; unchanged attempt 2 passed. Actual merged-main run 44326278636 on
943d143 has OpenSearch writer setup failure at `gradlew help`: ten plugin
classpath artifacts could not be found through the Gradle Plugin Portal. This
second log does not report 429. Its original full log remains in
`.cache/p14b-merge-ci-44326278636/opensearch-writer-verification.log`.
Integration in that run is still active; no cause is assigned without its logs.

Resolve plugin libraries from Maven Central, with an explicit module filter
keeping the existing Shadow plugin marker on the Plugin Portal. Ordinary
project repository declarations do not configure plugin repositories; Gradle's
[plugin repository documentation](https://docs.gradle.org/current/userguide/plugins_intermediate.html)
explains their separate search order. Keep the verified marker origin unchanged. Do not add a mirror, change versions/locks or bypass integrity checks.

Retry only the bootstrap `gradlew help` invocation, at most three attempts, after
explicit GET/HEAD failures against Maven Central/Plugin Portal with HTTP
429/502/503/504. Use delays of five then fifteen seconds plus a stable zero-to-six
second job-specific stagger. Retain each complete stdout/stderr log privately
under `.cache/bootstrap/gradle-help-*/attempt-N.log` before retry. Success is a new
attempt; earlier failure remains evidence. Exhaustion remains failure. Ordinary
404/missing coordinates, script errors, version/integrity failures and runtime
verification commands are not retried. No general workflow/job retry is added.
CI uploads these bootstrap-only logs immediately after a failed bootstrap.

## Independent regression expectations

| Input or operation | Required observation |
| --- | --- |
| Actual-shaped GET HTTP 429, then success | Two help invocations, one bounded delay, both original logs retained; smoke runs only after success |
| Three consecutive HTTP 429 failures | Three help invocations, two delays, all logs retained, final nonzero status propagates; smoke never runs |
| Explicit HTTP 502/503/504 on GET or HEAD | Same bounded recovery policy |
| HTTP 404, generic nonzero exit, unresolved module or Kotlin compilation failure | One invocation, no retry, original failure propagates |
| Source/error text merely contains 429, untrusted host, malformed URL, or success text with 429 | No transient classification; success does not retry |
| Runtime test fails after successful bootstrap | No runtime retry; existing commands and stable required gate still fail normally |
| Gradle repository declarations | Central searched before Portal; existing pinned modules, locks and generated runtime artifacts remain identical |
| CI failure diagnostics | Every job invoking bootstrap has a failure-only upload of bootstrap logs, no credentials or private evidence supplied |

The focused red must show the old bootstrap fails on the intended transient error,
not an import/setup mistake. Follow with focused regressions, locked root checks,
actual pinned Gradle help/bootstrap, unchanged artifact hashes and native CI.
PR checks and actual merged-main qualification remain separate; repeated manual
reruns alone are not claimed as the permanent correction.

## Retained implementation observations

The focused old-bootstrap regression failed on the intended mocked HTTP 429
without reaching smoke; log `.cache/ci-bootstrap-red.log`. The recovery regression
then passed. The initial diagnostics regression failed because CI had no attempt
upload step; adding failure-only uploads corrected it.

An actual Central-first help run correctly failed dependency verification: the
Shadow marker POM served by Central differs from the already verified Portal
marker. Log `.cache/ci-bootstrap-actual-help.log` and Gradle verification report
`build/reports/dependency-verification/at-1795014723789/` retain that failure.
The correction preserves the original marker origin with module content filters;
no checksum or lock is relaxed or regenerated.

The prerequisite actual merged-main run has now completed: all runtime jobs,
including integration, passed; only the retained OpenSearch writer setup failure
and required aggregate failed. GitHub accepted its unchanged failed-jobs retry.
That retry is separate evidence; this repair still requires its own native PR
and later actual merged-main qualification.

## Local qualification

On Darwin ARM64, the actual filtered repository configuration passed with an
empty Gradle dependency cache, using the verified Gradle 9.9.1 distribution.
`.cache/ci-bootstrap-cold-help.log` records the marker fetched from the Portal
and Shadow/logging/codec/Plexus libraries fetched directly from Central; strict
dependency verification passed. Cache identity and result are retained in
`.cache/ci-bootstrap-cold-result.json`. Full locked bootstrap, including actual
positive/negative Java/TypeScript smoke, passed in `.cache/ci-bootstrap-full.log`.
Final bootstrap help passed in `.cache/ci-bootstrap-final-help.log`.

Locked `uv run --locked python tools/dev.py check` passed 198 regressions,
contracts/catalog/dependency/hygiene/secrets checks, lint/format and types;
log `.cache/ci-bootstrap-final-source-check.log`. Eight focused bootstrap cases
include stderr-only errors, bounded exhaustion and no retry of permanent/runtime
failures. Logs preserve the earlier whole-check failures: diagnostics placement
initially displaced existing final workflow steps; placing bootstrap diagnostics
immediately after setup retained existing runtime diagnostic steps. The remaining
mypy argument-type error was corrected without changing command semantics.

An actual rebuild of integration, archive and historical artifacts passed with
unchanged SHA-256 values, respectively:

- `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`
- `e5eaea3560d150e176cb0f68e941ca22efb25fb6f16b2a1d1d76465a94ef02d0`
- `32bad6f526e3208bf4b2684979a4d600c82b35070e39cbeb3a5fce6d5fccfcc4`

Build log: `.cache/ci-bootstrap-artifact-build.log`. Dependency verification
metadata and all dependency locks remain unchanged. Exact source/log hashes and
base 943d143 are retained in `.cache/ci-bootstrap-qualified-source.json`.
This is local tooling/build evidence, not a new runtime or performance claim.
Native CI and actual merged-main verification of this correction remain open.
