# P12c recorded source acceptance evidence

Current status: [PR #43](https://github.com/TravisMa07/DetectBridge/pull/43) is merged
as c024497. Its description explicitly marks owner semantic/completeness review
and merge authorization complete. Exact PR-head adf71f8 passed AMD64 qualification
in run 43812450381 attempt 2; current merged-main run 43873905332 was still running
at the P13 handoff audit. Earlier draft/pending/failure entries below are historical.
The [P13 handoff](p13-handoff.md) records remaining Windows/P11 prerequisites; they
are not unfinished Linux implementation.

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

## Final-package qualification investigation

P12c's packaged ARM64 artifact is bundle
`5961fc44ac1548b52c59874f353a733672b4a49bb8b039e3d224f6e5d5de0c9d`, JAR
`364a342363e51c04b1e0af41bd61442eb2df8bc9daccfd2cc20731ffd4364745`, image
`sha256:8657fd0209075125403843931cd3dbcd83c750541b54d70a46b269f13028ad75`.
No source parser, mapping snapshot or checkpoint semantics changed; the new offline
runner is included in packaging, so old artifact evidence is not silently reused.

The first full final-package ARM64 run in project
`detectbridge-p12-test-6260dc2fe497` failed during required-output fault setup at
linux_assembly.py:695/fault:308/helper_run:200/stack.run:118 with command_failed.
Checkpoint/binding/TaskManager/JobManager phases, actual broker-pause recovery and
the event-sink fault/restore preceded this failure; none makes the full run a pass.
The failure occurred while configuring the manifest-sink fault, before its input
was injected. Resource profiles did not run. Exact cause remains unclassified;
original ledgers/report are retained, and owned stacks/volumes were removed.

A focused, separate project `detectbridge-p12-probe-4622fcc580bd` completed 60
read-back-verified sink-policy changes across all five output kinds without
reproducing the failure. This is administrative probe evidence only, not recovery
qualification or a reason to waive the failed run. No mutation was retried.

Shared diagnostics now recognize assembly/detection publishers, retain sanitized
operation/exception types, and preserve an owned helper's body-free exit/OOM/state
observation before cleanup. Reports retain redacted trace locations and completed
checkpoint inventories where available. Regressions verify no raw body disclosure,
mutation retry or conversion of failure to success. A fresh full diagnostic run is
in progress with all producer-rejection/checkpoint/accounting assertions unchanged.

A seventh actual-recording tamper probe also rejects changed source-quality
diagnostics. Source-quality and closure fields are now checked as complete objects.

Locked diagnostic-head repository check passed with 145 Python tests, lint/format,
types, source/contracts/catalog/deployment/inventory checks, hygiene and secrets.
The existing 39 Linux Java cases and combined semantic/component checks remain
passed; this follow-up changes qualification diagnostics/verification only.

## Observation metadata correction

Independent review found the original capture script labelled capture-start time
as first_observed, preceding later generated source events. Original capture
manifest, capture source, serial/native bytes and their hashes remain unchanged.
The catalog now records audit-recording-context/1.1.0 and the exact correction:
prepared envelope first_observed uses the original manifest's completed timestamp,
a conservative observation of the complete batch. Exact per-row observation times
are unavailable. This is not a fabricated per-message receipt or source-time change.
Future capture code records capture_started separately and observation after capture.
The original capture script remains bound to its original revision/hash; current
capture code is not silently attributed to historical bytes. Corrected prepared
inputs/results are qualified separately below; old output snapshots remain local.

Corrected context/1.1.0 was frozen at 7d5ecad/15841b1 before its fresh replay.
All three frozen rule plans again qualified all 30 original rows under separate
run 00000000-0000-4000-8000-000000000014: one eligible/nine skipped groups and
three extraction-failed preservation documents. All seven same-count tamper probes
were rerun against these corrected outputs and rejected. Old run-0013 files remain
untouched. Corrected artifacts are input-context-1.1.ndjson, output-context-1.1-*,
qualification-context-1.1.log/json in the same ignored recording directory.
Locked repository checks passed with 146 Python tests, lint/format/types, contracts,
inventories, hygiene and secrets; seventeen owning recording/assembly regressions
pass. The frozen rule bundles and original telemetry hashes did not change.

## Successful final-artifact ARM64 suite

The fresh diagnostic run passed on the same immutable P12c artifact above, with
no assertion relaxation or mutation retry. Default project
`detectbridge-p12-test-45fc12277c40` accounted for all 52 inputs, ten audit groups,
83 logical documents and 93 physical rows including ten byte-identical recovery
duplicates. Exact source/member/evidence/context/scope/quality, registered ranges,
immutable late links, actual TaskManager/checkpoint/JobManager recovery and strict
incompatible-binding rejection passed. Completed checkpoint 43 retained the group
through an actual 40-second broker pause and preserved its original deadline.
Actual RecordTooLarge event/manifest/diagnostic/quarantine/receipt failures retained
blocked intents in independently confirmed completed checkpoints 51/57/62/67/72;
healthy restored sinks drained the required outputs. Metrics/value-free logs passed.

Both profiles passed on that artifact: `detectbridge-p12-limits-1f501fbcef71`
qualified four closures and closed-budget rejection retaining original Kafka offset
8; `detectbridge-p12-bytes-d87b5ad051b5` qualified two closures under serialized
pending-byte pressure. All three owned stacks and volumes were removed. Original
input/expectation ledgers and `.cache/p12c-diagnostic-assembly-qualification.log`,
per-project reports and aggregate `.cache/linux-assembly-reports/qualification.json`
remain ignored. The report's baseline_main_run=43750911904 is the historical P12b
baseline reference, not a claim about P12c merged-main CI; the inspected current
base is e2d06c3 with successful repository run 43804124770.

The first final-package run's administrative manifest-fault setup failure remains
unclassified and separately recorded above. Neither this fresh pass nor the
60-change administrative probe is used to invent its cause or call it flaky.

## Final-artifact recorded authentication

`detectbridge-p12-recorded-71f48c040ef3` qualified the original reviewed OpenSSH9
recording on the same final P12c bundle 5961fc44 / JAR 364a3423. All 22 admissions
(11 originals plus isolated replay) produced four eligible events, 18 exact
unsupported preservation documents and 44 logical outputs. There were 77 physical
rows, including 33 byte-identical at-least-once duplicates. Actual RecordTooLarge
event rejection retained original event/member/evidence attribution in independently
confirmed completed checkpoint 2. Explicit healthy-sink restore and separate
replay run ebdac370-15d5-4304-baf7-0febc5ac5d64 drained all required outputs.

Original source bytes, host/generation/context, all per-record fields and quality,
receipts, runtime/destination binding and logical/physical accounting passed.
The original recording was read from the P12a checkout's ignored cache, not
recaptured, published or made available to ordinary CI. Its catalog digest is
97ae15e085dfe40c5e5687ecc6a69a34be9af899089259489bb8575d60d168f7.
Owned stack and volumes were removed. Final log is
`.cache/p12c-final-package-recorded-qualification.log`; report and original input/
expectation/checkpoint observations are in the ignored project paths. No later
runtime Java code or artifact changes followed this qualification.

All local acceptance checks are recorded above. PR-head AMD64 status must be read
from the actual final head; earlier/head/base CI passes are not silently attributed
to it. Owner review packet and separate merge authorization remain open.

## P12 completion — real audit checkpoint/replay

The remaining recorded-audit runtime path is implemented by
`tools/linux_assembly_audit_runtime.py`. It uses the unchanged qualified bundle
5961fc44 / JAR 364a3423 and the corrected context/1.1.0 catalog. No runtime Java,
source/mapping snapshot, checkpoint/state format, timer or broker policy changed.

Actual ARM64 project `detectbridge-p12-audit-7970e0af42a1` qualified both complete
runs of the 30-row recording. Its execution-first admission order was explicitly
specified before runtime and retained alongside original unchanged dataset positions,
source bytes and reviewed context. Completed checkpoint 5 retained the still-open
six-member execution group with exact source/member/raw/context hashes. Actual
TaskManager restart preserved it and its original absolute deadline; it closed as
an eligible timeout event. Remaining originals and explicit run end accounted for
all ten groups and three direct preservation diagnostics in the first run.

Isolated replay run `6e095bf7-f1cb-4d71-bfff-1d8e4a3728da` admitted unchanged
originals. Its explicit source boundary closed the complete execution while actual
RecordTooLarge rejection blocked the event sink. Independently confirmed completed
checkpoint 16 retained that run's eligible event and all six exact original members.
Healthy-sink explicit checkpoint restore drained the event; remaining originals
and run end completed the second full recording.

All 63 admissions (60 original record occurrences and three separately attributed
controls) were accounted for: 20 events, 20 manifests, six preservation diagnostics,
63 receipts, 109 logical documents and 117 physical rows including eight stable
byte-identical recovery duplicates. Ten event/evidence identities were identical
across the two isolated runs; closure/manifests and processing attribution remained
run-specific. Full original fields/tokens, source times, provenance, quality and
runtime/input binding checks passed, not just counters. The job does not evaluate
Sigma; the independent offline P10 cases remain separate evidence.

The owned stack/volumes were removed. Original input/ack/expectation/catalog ledgers,
open/blocked checkpoint observations and reports remain ignored. Final log:
`.cache/p12-completion-audit-runtime.log`; report:
`.cache/linux-assembly-reports/detectbridge-p12-audit-7970e0af42a1.json`.
Locked repository checks pass with 149 Python tests, twenty owning assembly/recording
regressions, lint/format/types, contracts/catalog/inventory/hygiene and secrets.
The preflight now also verifies exhaustive independent catalog membership before
Docker and retains explicit group expectations for subsequent runs. Those additions
do not alter the runtime protocol or the already qualified original/expected data.

The [P12 acceptance map](p12-acceptance.md) now separates completed bounded Linux
implementation/local evidence from owner semantic acceptance and integration gates.
Windows trusted recorded bindings belong to P11/P13; they are not unfinished Linux
implementation. Actual final-head AMD64 checks, owner review and separately
explicit merge authorization still apply before claiming P12 accepted/merged.

Targeted locked `tools/dev.py assembly` also passed after the completion work: Linux
and assembly Java tests, shadow-JAR/schema/license/dependency checks and twenty
owning Python regressions. No new runtime artifact was produced or silently
attributed; the JAR remains 364a3423. Recorded runtime timeout closure is actual
evidence; exact deadline identity is additionally covered by independent state
serialization/model tests, not a throughput or wall-clock accuracy claim.

## Subsequent owner acceptance and merge

GitHub inspection for the P13 handoff found PR #43 merged as
c02449745ddb87605d0bd85841f77fdad2fb382a. Owner semantic/completeness approval
and merge authorization are explicit checked entries in the PR description; a
generic praise comment is not used as the approval source. The original review
packet and prior pending checkpoints remain historical. The PR description also
records exact-head AMD64 success on adf71f8301d0b6c8ebcd4dc81d590186b6288ee3
in run 43812450381 attempt 2, after a classified HTTP 429 dependency-bootstrap
failure on the first attempt. No assertion/dependency pin was relaxed.

Merged-main run 43873905332 must be read independently before claiming full SDLC
completion. It was running at this audit; recorded local payloads were not replayed
by ordinary CI. P13 remains blocked separately on Windows identity/acceptance
evidence as detailed in its handoff. No P13 runtime implementation is claimed.
