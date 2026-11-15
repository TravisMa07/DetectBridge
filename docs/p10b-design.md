# P10b source selection and isolated runtime

Status: implemented for review on merged P10a b45fba4. Merged-main CI was
running when work began and subsequently passed on b45fba4. Independent owner review of
P09/P10 semantic expectations remains pending. This does not complete acceptance.

## Selection and equivalence

Build the source index once in the Java loader after schema, identity, hash and
mapping validation. Derive it entirely from the hashed source snapshots and rules;
no serialized user-supplied index is accepted. Each source key is exact ID/version.
Precompute inapplicable counts and keep applicable rules, including blocked ones,
in serialized rule order. Do not assume compiler-sorted IDs in the Java reader.
Unknown sources retain one configuration-blocked outcome per rule. Event structural
validation precedes all classification. Do not prune by missing values or polarity.

The exhaustive reference path retains per-event applicability/capability checks.
Both paths use identical input validation and predicate semantics, one shared
per-event operation budget, deterministic rule order and full result aggregation.
Equivalence compares matches/revisions, all six counts, ordered diagnostics,
identities and version attribution. Small-budget tests ensure no skipped gate
consumes budget, and no candidate receives a reset budget. Selection is an
optimization only; no capacity/performance claim follows from functional tests.

## Runtime isolation and compatibility

Keep P09's legacy entrypoint, projects, topics and checkpoint binding unchanged.
Add explicit mapped entrypoints using detectbridge-p10-* projects, separate local
configuration/build/report folders and v2 input/results/quarantine topic names.
Normalized inputs remain P03 v1, results are v2, quarantine references retain their
existing v1 shape. New runtime binding covers bundle, semantic evaluator, selector
policy, cluster, group and topic identities. Restore rejects changed bindings;
there is no state migration or cross-project adoption.

Share bounded Kafka/Flink transport and qualification code through explicit mode
parameters, not global monkey-patching. Legacy entrypoints reject mapped plans;
mapped entrypoints reject legacy plans. Preserve value-free diagnostics/logging,
fixed-label metrics, retained raw inputs, explicit restore and at-least-once
accounting. P10b adds no adapters, archive, activation or P13 detection identities.

## Evidence

Independent handwritten source/budget expectations precede selector changes.
Compare exhaustive and optimized outputs across supported predicates, source
mismatches, blocked/conditional aliases, quality states, invalid inputs, replay
runs, reversed rule order and budget exhaustion. Qualify the mapped runtime's
TaskManager restart, unavailable quarantine output, checkpoint and JobManager
restore, incompatible binding rejection, version attribution and all accepted-input
accounting on ARM64 and AMD64 CI. Preserve legacy runtime qualification and the
writer/detection CI gates. Actual evidence and failures belong in the ledger/PR.

## Shared adapter boundary and qualification integrity

The [adapter interface](source-adapter-interface.md) freezes context, evidence
resolution, typed mapping obligations and preservation output for P11/P12. It is a
specification, not an unused parser module or implemented capability claim.

The mapped fixture qualification uses all six outcomes across seven explicit
replay runs. Every accepted location is checked against original bytes, cluster,
topic identity, partition and offset. Independently derive event/run/result IDs
from admitted input and the frozen bundle; compare exact match UUID/revision,
all counts and ordered diagnostics. Validate output/quarantine schemas, keys,
quarantine identity, original size and null metadata. Cross-output consistency
alone is insufficient evidence. Read expected mapping/bundle attribution from
the exact frozen image build inputs, not a mutable later fixture plan.

Code review identified that the initial qualifier could accept wrong attribution
if offsets/hashes/counts agreed. The qualifier now checks input-derived expectations
and has tampered-row regressions. Initial runtime evidence is superseded for final
acceptance by qualification with those stronger checks and actual changed-group
restore rejection. Owner semantic review remains separate.

A literal system-shasum checkpoint vector pins the legacy v1 fingerprint preimage
independently of the new overload. A correct result body with an incorrect Kafka
key is explicitly rejected by qualification regression tests.

## AMD64 CI investigation

The first PR check on 8e561ec failed during legacy JobManager restoration before
mapped qualification began. The aggregate correctly failed because detection
failed; no check is waived or reclassified. The prior generic CLI failure hid the
operation category. Qualification now emits fixed, value-free categories and
separate shutdown/startup/submission/accounting phases. Unknown exception text is
never emitted, and failure still exits nonzero. The next AMD64 run must identify
the failing operation before any recovery behavior is changed.

The diagnostic run on 2d60c2c completed legacy AMD64 recovery, then failed at the
mapped incompatible-restore probe: the Flink CLI returned exit 1 before the harness
obtained a JobID. The probe previously assumed successful detached submission
followed by asynchronous job failure. It now supports both client timings. On a
submission exit 1, compare pre/post REST job identities, require exactly one new
job, then require FAILED state and the specific incompatible_detection_restore
marker. Exit status alone is never a pass; unrelated failures, missing/ambiguous
new jobs and daemon errors remain failures. Never retry the mutating submission or
modify the valid runtime configuration. Unknown failure details stay redacted.
The original 8e561ec legacy failure remains unclassified in its historical logs;
the later legacy pass does not establish its cause.
