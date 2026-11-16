# P11 subsystem ledger

- Base: df3144822ddd5694b9244ae29eb4a3c9e2815376, verified clean before edits.
- Branch: feat/p11-windows-adapters.
- Worktree: /Users/travisma/.t3/worktrees/DetectBridge/t3-689cf405-5fa25cc439f21f05.
- Owner: Windows implementation child; no delegated children.
- Owns: packages/windows-adapters, p11 design, ledger and Windows guide.
- Interface: exact context JSON boundary; local resolver; P03 normalized event or
  preservation diagnostic; offline output retains context and optional P10 result.
- Shared integration: minimal Gradle registration and lock resolution in separate
  commit; CI/dev-command/inventory/status integration remains orchestrator-owned.
- Acceptance blockers: recorded trusted host binding provenance, AMD64 subsystem
  execution, orchestrator integration/review. No Docker runs authorized here.
- Tests/evidence: child and orchestrator evidence recorded below; no throughput claim.

## Implementation and integration handoff

- `f78e221`: design and independent literal expectations, committed before coding.
- `f764907`: **isolated integration commit**, root settings module registration and
  Windows module lock. No common reader/schema/interface was changed.
- `eb44769`: bounded adapter, parser-backed profiles, original synthetic fixtures,
  actual P10 compiler/evaluator consumer, atomic offline runner and Windows guide.
- Follow-up qualification commit: independent recorded verifier, committed-rule
  provenance check, task revision input and real process-kill publication test.

The Windows lock has 23 Maven coordinates, all already present in reviewed module
locks. No new runtime dependency, executable transform or checksum was introduced.
Module packaging excludes expected fixtures from production resources. No shared
cache runtime state, Docker service, topic or checkpoint was used.

The child identified these serial integration requirements (resolved by the
orchestrator integration below):

1. Retain the two root settings lines from f764907 and the Windows module lock.
2. In `tools/dev.py` and `.github/workflows/hygiene.yml` (including the owning
   change classifier and fail-closed aggregate), add
   `:windows-adapters:test :windows-adapters:installDist` plus the two Python
   verifier regressions and subsystem Ruff checks to appropriate developer/CI gates.
   Existing `tools/dev.py java` intentionally remains untouched and does not select
   the Windows module yet. Preserve all existing transport/writer/detection gates.
3. Reconcile `tools/dependency_inventory.py`, `tools/check_detection.py` and the
   owning inventory JSON files: existing inventory readers cover
   transport/detection paths, not the new Windows lock. Record its 23 reused
   coordinates in the owning inventory without regenerating unrelated locks.
4. Coordinate AMD64 execution and shared README/roadmap/architecture/status updates.
   No closed P03 schema or shared context/result API revision is needed.

The child opened no PR and performed no merge/release. Shared integration was
subsequently completed by the orchestrator below.

## Verification and limits

macOS ARM64, pinned Temurin 17.0.21+9 and Gradle 9.9.1, strict dependency verification:

- Locked `tools/dev.py check`: PASS, 121 Python regressions, contracts/mappings,
  lint/format/types and repository hygiene. First attempt lacked isolated npm
  dependencies; rerun passed after locked npm installation.
- Locked `tools/dev.py java`: PASS, existing transport/writer/detection semantic
  tests and bundles, 20 legacy + 20 mapped independent YAML-to-Java cases, mapped
  exhaustive equivalence and 12 P10 mapping cases. No Docker qualification.
- `:windows-adapters:test`: PASS, 32 Java tests including all six offline evaluator
  outcomes, literal complete fixtures, parser/resource limits, integrity/range
  failures, replay identity and actual hard process interruption before publication.
- Subsystem Ruff lint/format and two Python verifier regression tests: PASS.
- Recorded payload/provenance rehash and independent signature inventory: PASS,
  Security 8 supported; Sysmon 353 supported / 6,657 unsupported; all 7,018 inputs
  accounted, all 361 candidates contain command lines. No evidence committed.
- First 7,018-row atomic run completed; attribution verification correctly rejected
  the mutable plan reference. This is superseded by the frozen-plan rerun below,
  not accepted as final qualification. Preparation now checks actual committed rule
  bytes and binds Gradle task inputs to the Git revision.
- Frozen-plan recorded run and independent accounting: PASS, all 7,018 published
  atomically; 361 normalized/skipped with identity_missing, 6,657 unsupported-source
  preservation rows. Each normalized row independently checks original byte/range
  identity, mapped values, source-time precision, unchanged first observation,
  parser/mapping attribution, literal evaluator gates and exact frozen bundle.
  No eligible or matched recorded result is claimed.
- Exact local evidence stays ignored: `.cache/p11-check-final.log`,
  `.cache/p11-java.log`, `.cache/p11-test-final.log`,
  `.cache/p11-final-recorded-qualification.log`, and frozen
  `.cache/windows/recorded-plan.json`. Recorded input/output bodies are ignored.
  Earlier mutable-plan output is superseded and is not acceptance evidence.

Existing source metadata was inspected and its checksum reverified. It substantiates
scenario/environment/author/collector paths, not a stable host identity or reviewed
Computer-to-host binding. Full recorded eligible coverage therefore remains blocked;
no guessed bindings or metadata-date occurrence times were supplied. Synthetic host
bindings are labelled synthetic. AMD64/CI execution, owner review and integrated
P13 streaming/recovery remain outside this child evidence. No throughput claim.

## Orchestrator integration

P10 merged-main qualification passed on df31448; the owner authorized dependent
P11/P12 work without an invented formal semantic-review record. The orchestrator
retains this worktree/branch and coordinates shared changes serially. Windows
verification is now a real developer/CI gate with shared-consumer classification
and fail-closed aggregation. Root java includes the adapter tests/installed
artifact checks; owning scripts receive lint/format and independent verifier tests.
The combined inventory records all Windows lock uses, plus an owning inventory
covering 23 reused coordinates. Local distribution retains LICENSE/ECS-NOTICE.

Root review found and fixed System/Data versus EventData/Data attribution, with a
new literal regression. Independent recorded verification now validates every
source signature, raw/event/result schema and input attribution, rejecting false
unsupported/normalized classifications and incomplete result references. The
strengthened verifier rechecked all 7,018 rows (361 supported/skipped, 6,657
unsupported); a fresh runner/output check is recorded separately when complete.
Trusted host binding provenance remains missing, not silently waived.

The orchestrator renamed the completed child's branch to feat/p11-windows-adapters
for the repository convention; the prepared worktree and implementation history
are retained. Integrated validation passed: root check (124 Python tests), combined
Java verification, Windows gate (34 Java tests including UUID case preservation,
five independent verifier regressions, packaging/licenses and lint/format). A
fresh 7,018-row atomic runner/verifier pass confirms 361 supported/skipped and
6,657 unsupported records. The UUID compatibility rerun also passed with its frozen plan and ignored local
logs; no recorded host identity is inferred.

Independent review reproduced two P03 compatibility defects: base64 evidence
representation was rejected before XML parsing, and URI schemes were compared
case sensitively in the resolver and shared normalized-event consumer. Both are
corrected with original evidence metadata retained. Added regressions cover
base64 inline/reference XML, invalid UTF-8, mixed-case HTTPS/S3/file locators and
continued rejection of unsafe locators and noncanonical content-addressed URNs.
Post-review locked root check passed (124 Python tests), combined Java verification
passed (including 35 Windows tests and 20 shared evaluator tests), and all six
independent verifier regressions passed. Logs remain ignored at
`.cache/p11-compat-check.log`, `.cache/p11-compat-java.log` and
`.cache/p11-evidence-compatibility.log`.

The shared consumer compatibility correction also passed ARM64 legacy detection
runtime qualification: 11 valid inputs, two invalid inputs, replay isolation,
TaskManager recovery, sink outage, explicit checkpoint restore, JobManager restore,
metrics and payload-log checks. Evidence: `.cache/p11-compat-runtime-build.log`,
`.cache/p11-compat-runtime-verify.log` and the ignored structured report under
`.cache/detection-reports/`. This is shared-engine regression evidence, not a
streaming/recovery qualification of the standalone Windows adapter.

The final base64/URI compatibility recorded rerun passed with the frozen plan:
all 7,018 original inputs accounted, 361 supported/skipped for missing trusted
identity and 6,657 unsupported-source diagnostics. Both the atomic runner and
independent original-byte/signature/mapping/result attribution verifier passed.
Evidence stays ignored in `.cache/p11-compat-recorded-run.log`,
`.cache/p11-compat-recorded-qualification.log`,
`.cache/windows/compat-recorded-output.ndjson` and the frozen
`.cache/windows/recorded-plan.json`. No recorded eligibility is claimed.

The final ARM64 mapped detection runtime regression also passed: 16 valid inputs,
two invalid inputs, logical outcome/replay accounting, TaskManager recovery, sink
outage, explicit restore, incompatible bundle restore rejection, JobManager restore,
metrics and payload-log checks. At-least-once recovery produced 17 physical result
rows for the 16 valid inputs; logical accounting passed without an exactly-once
claim. Logs: `.cache/p11-compat-mapped-build.log`,
`.cache/p11-compat-mapped-verify.log` and the ignored structured report under
`.cache/detection-v2-reports/`. Both temporary qualification stacks were cleaned up.
AMD64 qualification remains pending CI. Trusted recorded host bindings remain an
acceptance blocker. No merge, release, P13 integration or throughput claim.

## Subsequent integration status

P11 PR #38 passed required AMD64 jobs at 4f741c2 in run 43684323177 and the owner
merged it as 46fb080013e4623eb019e6ada829fc909a7cbfe0. Earlier pending-CI/unmerged
entries are historical. Trusted recorded host bindings and independent owner
semantic review remain acceptance blockers; no recorded eligible claim is added.

## P13 prerequisite inspection — 2026-11-16

Both original Windows payloads and the 1,259-byte scenario metadata were rehashed
against the catalog. Security and Sysmon have distinct Computer display values;
metadata supplies no stable host IDs or capture-scoped Computer bindings. The
owner reports no additional authoritative evidence. P08 has replay metadata only,
not a host-binding registry. Rule fixtures and synthetic bindings cannot supply
recorded provenance. Separate P11 semantic acceptance remains unresolved.
The [P13 plan](p13-design.md#exact-missing-windows-evidence) records exact evidence
needed and preserves the existing 361 skipped/6,657 unsupported accounting.

## Controlled Windows evidence completion

The owner requested implementation of the remaining P11 blocker. A new opt-in
controlled capture and independent verifier are implemented on
`feat/p11-controlled-windows-recording`; [design](p11-recording-design.md) and
[owner review packet](p11-recording-review.md) define the bounded scope.
The original public recordings still have no trusted bindings; their 7,018-row
preservation accounting is unchanged.

Actual accepted source capture: workflow run 43880077695, job 133343561692,
head f0ced8fe470dcb23c183979087125a77f66cf5a9. The capture job passed; unrelated
workflow checks are not substituted for source qualification. Encrypted artifact
14231737714 has transport SHA-256
7cf2898219fc6b641c1f89ca879b183390c090e1216359dd94b9dd5c661d2d2d.
Authenticated download, ciphertext identity and original archive bytes were checked.
The [new catalog](../catalog/recordings/windows-process-lab-v1.json) pins source
and terms metadata only; no original XML, binary or private key is committed.

Two real process actions yield four eligible events (Security 4688 v2 and Sysmon
1 v5), plus one native unsupported Sysmon service-state preservation row. Actual
registry/VM/boot/local-host/process/account evidence substantiates the new capture's
bindings. Per-record source expectations were frozen at dd0875a before actual
adapter/evaluator use; the later observation-policy attribution revision was frozen
at 0d9135e before the final rerun. Capture-time source expectations are independent
of the evaluator. Only retained selection-completion observation time is available;
no exact first-enumeration claim is made. Git checkout CRLF source conversion is
explicitly versioned and hashed separately from original native XML.

Actual ARM64 Java adapter/evaluator qualification passed both complete isolated
runs, each with five originals, four eligible, one unsupported, two matched, six
unmatched and four inapplicable rule outcomes. Six actual same-count output tamper
probes failed as required. Original event/evidence IDs stayed stable while run/result
IDs remained isolated. Frozen plan a90ed1b5 / adapter JAR e562f1b6 are expanded in
the review packet. Final local logs/reports and all earlier outputs remain ignored.
This is offline qualification; P13 Kafka/Flink/search integration is not implemented.

Earlier attempts are retained separately: run 43879082722 capture job failed with
a generic fixed category before usable evidence; run 43879579549 failed at XML
candidate selection, source line 89. Its encrypted retention step incorrectly
skipped because hashFiles could not select the runner-temp file. The follow-up
reads XML InnerText (including empty fields) and uploads encrypted failed-attempt
archives with an always-running step. Run 43880077695 then passed. Exact first-
attempt cause is not established, and no failed recording is accepted. Earlier
full dispatch runs were cancelled by the existing same-branch concurrency policy
when superseded; no qualification check was relaxed.

Local locked root checks initially found a bare-URL Markdown error; it was fixed.
A Windows-gate attempt reached passing Java/tests then failed import ordering in
the new verifier; that formatting error was fixed. Final-head checks and owner
semantic acceptance are recorded separately when observed; passing local evidence
alone does not complete those gates or authorize a merge.
