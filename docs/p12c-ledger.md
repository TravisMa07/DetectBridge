# P12c recorded source acceptance evidence

Branch: feat/p12c-recorded-source-evidence, based on merged P12b e2d06c3.
Owner requested continued roadmap implementation beyond the initial small auth
qualification slice. [Design](p12c-design.md) records the expanded audit scope.
Implementation and local selected-source evidence do not constitute owner semantic
acceptance, P13 readiness, merge authorization or release qualification.

## Baseline and independent expectations

P12b #42 is observed merged as e2d06c3. Final-head AMD64 run 43768117676 passed
on fd3607e; [merged-main repository run 43804124770](https://github.com/TravisMa07/DetectBridge/actions/runs/43804124770)
subsequently passed, including actual linux-assembly-verification and all required
shared jobs. Opt-in recorded jobs were skipped. Successful dependency automation
was initially mistaken for merged-main qualification, then corrected before relying
on that gate.

Auth design was committed at 2e5a625. Audit scope/action expectations and the
original probe were frozen at efc49d2 before final capture; capture implementation
was committed at 4d96391. Original audit hashes, source membership, findings and
three independent rule outcomes were frozen at 163cfd9 before adapter/evaluator
replay. No evaluator result was used to generate source expectations.

## Reviewed audit capture and offline qualification

The [catalog](../catalog/recordings/linux-audit-execve-lab-v1.json) pins 27 original
artifacts, all 30 native LF records, source/host/generation context, package and
binary metadata, image/kernel/initramfs hashes and local-use terms. Only metadata
and original test/action code are in Git; payloads, guest/image binaries and notices
remain ignored at `.cache/p12-audit-reviewed-v1`.

Actual capture uses QEMU TCG in a cap-dropped, read-only, unprivileged, networkless
container with no host devices or filesystem bindings. Its separate Linux
6.1.0-55-arm64 guest kernel (Debian 6.1.192-1) runs auditd 3.0.9 and an original
static probe. Docker image ID:
`sha256:ba78aa7e67949b358dae9a3505a623e3bd14fa2a761906e65b6612776e020c95`.
Exact package pins, all installed package versions and copyright files remain with
the local artifacts. [Primary reference review](../packages/linux-adapters/audit-recording/reference-review.json)
pins upstream documentation and license hashes. No new library dependency,
security remediation or public fixture redistribution is claimed.

Trusted host identity binds the sole guest invocation to the inspected outer
container; generation binds the original guest boot ID. Audit status before and
after reports enabled=1, the same nonzero daemon PID, lost=0, backlog=0 and the
exact execution watch. The action exited zero. Its six execution members contain
one successful AArch64 execve (221), argc=5 with empty/repeated/space-bearing
arguments, CWD /, two distinct PATH items naming the same probe, and PROCTITLE.
There is no native EOE. Completeness follows reviewed counts/membership, capture
context and zero-loss observations; dataset_end closure alone is not proof.

All 30 original rows pass atomic offline replay and independent verification:
ten groups (one eligible execution, nine skipped non-execution/control groups)
and three extraction_failed preservation documents for native rows outside the
selected parser grammar. All original inputs/contexts, token spellings/order,
record/event/manifest IDs, membership, source times (including early-boot clocks),
source hashes, quality, processing versions and complete evaluator attribution
are checked. Eligible execution has independently expected matched, unmatched and
configuration_blocked outcomes for the probe, /bin/false and unsupported
CommandLine rules respectively. Existing P10 precedence remains: unsupported
CommandLine is configuration_blocked even for the nine quality-skipped source
events; available Image rules report quality_skipped for those events.

Frozen plan bundles:

- Probe match: `4685906490cfdd24d02091707b052e17e7fbf5b61d1c45b1d9314e6df515bf0f`.
- Image nonmatch: `4b2f52aeb278d1951e820457e07ae558f7253945afb6b9be409df02551e539df`.
- Unsupported command: `a1e3d6b023f29fe8e3934b4a976e955354bb1d54e4beba5039ea6ee15645a312`.

Same-count tampering of arguments, manifest membership, source generation,
evaluation outcome, original cursor and retained token spelling was rejected.
Local qualification report/log and frozen outputs/plans are retained in the same
ignored recording directory. They are not archive/recovery sources.

Preliminary capture attempts failed on BusyBox canonical links, dynamic-loader
permissions, invalid auditd space thresholds and missing pthread-cancellation
runtime support. Foreground debug mode also does not create the required native
log; the final protocol uses auditd -n. The serial extractor initially mishandled
empty artifacts and now has an empty-payload regression. None of those attempts
is accepted recording evidence. A completed preliminary capture whose extractor
failed is superseded by the intact final original artifacts above.

## Recorded authentication recovery

On P12b's original qualified artifact, project
`detectbridge-p12-recorded-a7c639be47c0` passed 22 admissions (11 originals plus
isolated replay), four eligible events, 18 preserved unsupported rows and 44 logical
outputs; 81 physical rows included 37 stable duplicates. A stronger repeated run
`detectbridge-p12-recorded-288f7ccd5468` failed in the sink-failure phase. Its
original report retained only StackError/phase, so its exact cause is unclassified;
it is not accepted qualification and no failure check was relaxed. Reporting now
retains redacted category/trace locations and the body-free checkpoint inventory.

The fresh diagnostic run `detectbridge-p12-recorded-1a410ec18e10` passed the stronger
original-event/member attribution check. Completed checkpoint 2 retained an
original recorded event under actual RecordTooLarge failure. Explicit restore and
isolated replay produced 44 logical outputs, 80 physical rows and 36 byte-identical
duplicates. This used P12b bundle 5d3bf6a / JAR 0f4955f, not P12c's later packaged
artifact. Logs/reports are ignored under `.cache/p12c-*recorded-qualification.log`
and `.cache/linux-assembly-reports/`. Final-artifact results follow separately.

## Verification and remaining gates

Combined locked Java/semantic verification passed, including 39 Linux tests
(three new actual offline replay/evaluator/publication cases), existing consumers,
artifact/notice checks and independent P10 semantic cases. Sixteen owning Python
assembly/recording regressions passed. Root check ran 143 Python tests successfully,
then found a test-only mypy annotation issue; the annotation is corrected and
mypy passes. Final locked checks and actual final-artifact runtime evidence remain
to be recorded. No absent local recording is claimed replayed by ordinary CI.

Windows trusted recorded host bindings, owner independent-expectation/completeness
review, PR AMD64 qualification and separate owner merge authorization remain open.
The selected local audit recording does not establish general corpus coverage,
throughput, production source wiring, archive durability or P13 readiness.
