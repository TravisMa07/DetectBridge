# P12b implementation ledger

Status: implementation in progress; no P12b acceptance, merge or release claimed.
Branch: feat/p12b-linux-qualification. Base: P12a merge 9ea1c68 plus approved plan
55a28f2. Design/semantic expectations were committed at 655e362 before wrapper
code; detached transitions, independently computed cases and checkpoint model
followed at 2231b03. Normative literal P03 vectors were subsequently frozen without
using adapter/evaluator output as the oracle.

## Baseline

P12a merged-main 43750911904 initially failed the existing P10 incompatible-restore
check with unrelated_incompatible_restore_failure. No exception artifact remained;
its cause is unclassified. One unchanged failed-job rerun passed. No check was
relaxed. This historical failure and the rerun are distinct evidence.

## Implemented and under qualification

- Detached one-group prepared transitions, preserving legacy durable Commit and
  original live state. The prepared path never invokes the external Commit API.
- Bounded checkpoint envelope, inbox/outbox, source progress, immutable intent
  identities and prefix retirement. Only completed-checkpoint prefixes publish;
  restoring a completed checkpoint replays its retained intents at least once.
- Real Flink operator, timers, managed source offsets, broker/topic/group/artifact/
  source/mapping/limit/registration binding, Kafka acknowledged outputs and metrics.
- Explicit locally registered evidence objects, original hash/range/cursor checks,
  immutable registration digest and read-only mounts; no source URI fetches.
- Separate event/manifest/diagnostic/quarantine/receipt topics in exclusive
  detectbridge-p12-* projects. Existing transport/detection/writer resources stay
  separate. No P13 production evaluation or writer integration.
- Body-free checkpoint inventories are observations only. Verifiers must confirm
  the exact checkpoint completed independently through Flink before treating its
  references as durable state. Recovery never reads these observation files.
- Independent original input/expectation ledgers, exact source/member/byte/hash/
  scope/quality checks, physical duplicate accounting and meaningful component
  classification/fail-closed CI aggregation. Actual runtime evidence pending.

The first exploratory replay exposed a verifier scope bug: manifest run_id lives
under key. It was corrected against the existing contract with a regression. A
missing diagnostic-handler import was also corrected. That failed exploratory
run is not qualification evidence. Preliminary images/configurations are not
accepted compatibility baselines.

## Verification so far

Prepared/model/serializer/evidence tests, owning artifact checks, new Python
oracle/gate regressions, locked root checks and combined Java checks have passed
at intermediate heads; exact final-head results will be recorded after the final
qualification. 67 reviewed Maven coordinates remain the combined set; the new
module adds uses of existing coordinates/configurations only. No new checksum or
fresh advisory-remediation claim. Existing image findings remain open.

Safety bounds are serialized budgets, not measured JVM heap/throughput capacity.
Every stopped/failed isolated runtime must retain original input or its declared
qualification ledger and expose pending intents/state/backlog; counters alone are
not accepted-input proof. Source payloads, evidence, images and build products stay
ignored. Original synthetic fixtures are Apache-2.0 and clearly labelled synthetic.

## Remaining acceptance

Complete ARM64 failure/resource qualification and actual AMD64 CI; owner review of
independent expectations/completeness policy; reviewed eligible audit provenance;
separate owner merge authorization and merged-main qualification. Windows recorded
host binding and full P12/P13 acceptance remain separate blockers. The existing
reviewed local auth recording is not silently claimed replayed by ordinary CI.
