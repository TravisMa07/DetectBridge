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

Orchestrator serial integration still needs:

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

No PR was opened: shared gate/inventory integration remains orchestrator-owned and
must be reconciled for an acceptance-ready PR. No merge/release was performed.

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
Final post-review validation is recorded below when complete.
