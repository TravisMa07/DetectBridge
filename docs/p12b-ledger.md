# P12b implementation ledger

Status: implementation complete for draft review; final-artifact ARM64 and AMD64
qualification remain in progress. No full P12 acceptance, merge or release claimed.
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
  classification/fail-closed CI aggregation. Exact runtime evidence follows below.

The first exploratory replay exposed a verifier scope bug: manifest run_id lives
under key. It was corrected against the existing contract with a regression. A
missing diagnostic-handler import was also corrected. That failed exploratory
run is not qualification evidence. Preliminary images/configurations are not
accepted compatibility baselines.

The first full ARM64 attempt at 91e309a reached selective sink faults after the
recovery/replay phases, then correctly failed: min.insync.replicas=2 did not reject
writes in this single-broker setup. A focused probe confirmed both outputs were
acknowledged; no speculative broker-internal cause is asserted. Qualification now
requires actual RecordTooLarge producer failure using read-back-verified per-topic
max.message.bytes=1, plus a separate actual broker pause. Healthy policy is restored
explicitly before checkpoint recovery. No assertion or required gate was weakened.
The failed attempt is not accepted qualification.

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

## ARM64 runtime evidence

The corrected full run at 0b873ff passed on linux/arm64 in isolated project
`detectbridge-p12-test-d0407d140056`: 52 default-profile inputs, 10 logical groups
and 93 physical output rows (at-least-once delivery; this count is not unique
logical documents). Exact source/member/hash/context, events, manifests,
late links, reference ranges, quality and disposition accounting passed. Actual
TaskManager and JobManager recovery, incompatible-binding rejection, explicit
checkpoint restore and original idle deadlines passed.

Actual 40-second broker pause retained the admitted group in completed checkpoint
46 and recovered its original timeout closure. Actual RecordTooLarge failures for
event/manifest/diagnostic/quarantine/receipt retained their blocked intents in
completed checkpoints 51/56/61/66/71, respectively; restored healthy sinks drained
all expected outputs. Reduced limits qualified four closures and closed-budget
backlog with rejected original Kafka offset 8 retained. The byte-pressure profile
qualified two closures. No arbitrary failure or config mismatch counted as the
required producer rejection.

Default artifact: bundle
`3b6cceef2a3a832eb69fc4cd42c7f706b3e2c97ebd002cb610792ef29579a409`, JAR
`ec0af7a812ee7366819af80a1827b7b53dc51f11ded5994fffaf8aba0cc9b3e0`.
Evidence remains ignored in `.cache/p12b-qualified-run.log`, per-project original
input/expectation ledgers and `.cache/linux-assembly-reports/`. Stacks/volumes were
removed. A subsequent metadata-scope/runtime-contract/accounting correction at
9a93070 has a fresh complete final-artifact run in progress; intermediate evidence
is not silently attributed to that later artifact. Ordinary CI uses original
synthetic cases, not the reviewed local authentication recording.

Locked repository checks pass with 133 Python regressions; combined Java/P10
semantic checks, 36 Linux and 10 assembly Java tests, six assembly Python oracle/
gate/runtime-contract regressions, artifact/dependency/notice checks, lint/types
and secret scanning pass. Exact final runtime artifacts/results will be appended.

## Remaining acceptance

Complete final-artifact ARM64 qualification and actual AMD64 CI; owner review of
independent expectations/completeness policy; reviewed eligible audit provenance;
separate owner merge authorization and merged-main qualification. Windows recorded
host binding and full P12/P13 acceptance remain separate blockers. The existing
reviewed local auth recording is not silently claimed replayed by ordinary CI.
