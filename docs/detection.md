# Compiler and evaluator slice

Current review status (2026-11-17): the owner accepted bounded P09/P10 semantics
and completeness limits in the [prerequisite packet](p13-prerequisite-review.md).
Issues #9/#10 are closed; pending-review caveats below are historical.
P13 acceptance, merge authorization and merged checks remain separate.

P09 provides a bounded proof of concept over original synthetic normalized events.
It does not parse raw replay input or establish Windows/Linux adapter coverage.
P08's writer and P07's relay remain independent. See [design decisions](p09-design.md).

## Compile and evaluate

```sh
uv run --locked python tools/detection_compile.py contracts/detection/v1/fixtures/rules/process.yml --source contracts/v1/examples/windows-security-4688.source.json --output .cache/detection/plan.json
uv run --locked python tools/dev.py java
.cache/jdk/bin/java -jar packages/detection-evaluator/build/libs/evaluator.jar .cache/detection/plan.json contracts/detection/v1/fixtures/positive.event.json
```

Compilation is all-or-nothing and replaces the output atomically only on success.
A failed compile leaves a previous valid output intact; callers must check exit
status. Original YAML and SHA-256 revisions remain in the plan. Java validates the
complete bundle once at startup; no per-event Python call exists.

The pySigma 2.1.0 numeric constructor can lose precision for large integers. Our
adapter restores validated original integer values in its typed tree before
condition expansion. Literal signed-64-bit boundary tests protect this behavior.

The supported subset and all numerical limits are in the design notes. Strings
use Java 17 code-point lower(upper(cp)) folding. This is not full Unicode casefold:
`SS` does not match `ß`, and composed/decomposed text is not normalized. Wildcards
consume code points, not UTF-16 units. Unsupported features fail compilation even
inside unused selections. Empty optional ECS strings/nulls follow P03 validity;
null rule literals are unsupported.

## Runtime and recovery

```sh
uv run --locked python tools/detection.py build
uv run --locked python tools/detection.py --project detectbridge-p09-dev init
uv run --locked python tools/detection.py --project detectbridge-p09-dev start
uv run --locked python tools/detection.py --project detectbridge-p09-dev status
uv run --locked python tools/detection.py --project detectbridge-p09-dev stop
```

The local image embeds the prepared immutable fixture bundle. General activation
and deployment of arbitrary imported bundles remain P15. Development projects must
start with `detectbridge-p09-`; never target a P07/P08 project. P09 reuses P06's
checked local image-overlay slot (historically named `transport_bundle`) only in
its exclusive project. No host Kafka/Flink port or OpenSearch dependency is added.

The three topics are `detectbridge.detection.input.v1`,
`detectbridge.detection.results.v1` and `detectbridge.detection.quarantine.v1`.
Inputs are P03 normalized-event JSON, keyed by UTF-8 run UUID. The private Java
helper accepts bounded base64 injection for qualification; the production job is
the validation boundary. Results contain event/run/bundle identity, version
attribution and input location/hash; original evidence stays in the retained input.
Invalid input emits a value-free quarantine reference. Unknown source snapshots
are configuration-blocked, not nonmatches. No evidence URI is fetched.

Retain input topics while results/quarantine reference them. Delivery is
at-least-once, and output can precede checkpoint completion. Duplicate result IDs
remain stable for a fixed event/run/bundle; replay runs have distinct IDs. A result
ID is not P13's detection ID. No archive or exactly-once claim is made.

Use `start --restore file:///state/checkpoints/<job-id>/chk-<number>` for explicit
recovery, or `--from-beginning` for deliberate retained-input reprocessing.
The launcher checks checkpoint ownership and image history; operator state binds
bundle and Kafka identities and rejects incompatible restore. P07's 10-second
checkpoint cadence and finite three-attempt restart policy apply. Sink failure
blocks successful checkpoint progress. Local disk and single-host limits remain.

## Acceptance evidence

```sh
uv run --locked python tools/check_detection.py --java
uv run --locked python tools/detection.py verify
```

The first command uses literal handwritten expected outcomes and explanations,
not evaluator-generated truth. Java unit tests additionally cover arrays and
empty strings at the predicate boundary; mapped P03 scalar fields remain scalar.
The second uses an exclusive synthetic stack, verifies semantic results and input
hashes, exercises TaskManager and JobManager recovery plus an unavailable
quarantine sink, and writes ignored local reports. It cleans only its test project.
CI runs Linux AMD64 qualification when detection/shared dependencies change.
Independent owner review of expected semantics is pending; passing tests alone do
not establish that review, production coverage, or throughput capacity.

## P10 offline mapping compatibility

P10a adds [typed source mapping and candidate provenance](p10-design.md). See the
[feature matrix](compatibility.md) and [implementation ledger](implementation-ledger.md).
To prepare both legacy and v2 synthetic plans:

```sh
uv run --locked python tools/check_mapping.py --prepare
uv run --locked python tools/dev.py java
.cache/jdk/bin/java -jar packages/detection-evaluator/build/libs/evaluator.jar .cache/detection/mapped-plan.json contracts/detection/v1/fixtures/positive.event.json
```

Compile v2 by supplying `--mapping` once per exact source snapshot and
`--provenance` pointing to the JSON candidate manifest array in addition to the
existing rules/`--source`/`--output` arguments. `--analyze` with the same inputs
publishes a bounded candidate disposition report instead of an executable bundle;
it includes rejected candidates and never partially activates supported ones.
Original files and notices must remain accessible by their recorded hashes.

The new offline mode emits result 2.0.0. P09's deployed job rejects v2 plans to
protect its v1 result topic; keep its existing commands/projects/checkpoints.
P10b provides the separate runtime below; exact-head evidence is recorded in its
PR and ledger.

## P10 mapped runtime

P10b evaluates v2 plans through a loader-built source index, preserving serialized
rule order and the shared operation budget. `Evaluate` accepts `--exhaustive` as a
third argument for complete-result comparison. The regression suite checks both
paths against independent expectations; no field-presence pruning is performed.

```sh
uv run --locked python tools/detection.py --mapped build
uv run --locked python tools/detection.py --mapped verify
uv run --locked python tools/detection.py --mapped --project detectbridge-p10-dev init
uv run --locked python tools/detection.py --mapped --project detectbridge-p10-dev start
uv run --locked python tools/detection.py --mapped --project detectbridge-p10-dev status
uv run --locked python tools/detection.py --mapped --project detectbridge-p10-dev stop
```

Mapped projects must start `detectbridge-p10-`; legacy projects remain
`detectbridge-p09-`. Mapped mode uses separate `.cache/detection-v2-{build,runtime,reports}`
folders and `detectbridge.detection.{input,results,quarantine}.v2` topics. Inputs
remain P03 normalized contract 1.0.0; results are 2.0.0 and quarantine references
retain their 1.0.0 shape. Explicit Java mapped entrypoints reject legacy plans.
The legacy job retains its existing v1 topic and plan restrictions.

Use the same `start --restore file:///state/checkpoints/...` or deliberate
`start --from-beginning` options with `--mapped`. Restore binds actual evaluator,
selector policy, complete bundle, cluster, consumer group and topic identities.
Cross-mode adoption, changed binding and unknown checkpoint ownership fail. No
state migration is promised. Keep frozen build inputs alongside runtime metadata
for qualification attribution; don't replace them with a later fixture plan.

Mapped qualification covers all six outcomes, two baseline replay runs plus five
isolated synthetic diagnostic cases, TaskManager recovery, unavailable quarantine
sink, explicit checkpoint restore, actual changed-group restore rejection,
JobManager restore, metrics and value-free logs. Every accepted input must remain
accounted for with its original location/hash and independently expected identity,
match metadata and diagnostics. Retain original input topics while output/quarantine
references depend on them. Heavy legacy/mapped qualification runs are sequential.
No recorded source eligibility, production detection, archive or throughput claim
follows. Independent owner semantic acceptance remains pending.

## P13a compact mapped API and offline outputs

`Evaluator.evaluateCompact(bytes)` accepts mapped v2 bundles and returns compact
1.0.0 counts, ordered matches and at most three grouped diagnostic references.
The evaluator CLI accepts `--compact` in place of `--exhaustive`. Legacy APIs and
CLI default results remain unchanged. `IntegrationOutputs.process(event, manifest)`
wraps unchanged P03 events with attributed deterministic tags, linked detections
and grouped diagnostics; `verify` consumes these documents against the pinned plan
and original manifest. Windows context is supplied with the three-argument
`process`/`verify` overloads; Linux extracts its original context extension.
Actual source attribution remains available when the evaluator bundle lacks a source. Source quality remains distinct from coverage.

The Windows Offline, Linux AuthReplay and AuditReplay installed commands accept
an explicit final `--integrated` argument after their mapped plan. Audit output
binds the validated original manifest and exact members; standalone events reject
an assembly manifest. Malformed/unsupported input remains preservation output.
Resolver I/O still fails the offline transaction for retry. Output overflow also
fails atomically without replacing a prior publication. Retain original raw/context
rows and immutable bundles/manifests. Tagged events remain unchanged;
`IntegrationOutputs.contentHash` excludes receipt/processing clocks from semantic
content comparisons, as do processing identities. [Contracts/decisions](p13a-design.md) and
[qualification](p13a-ledger.md) specify limits and acceptance status. These are
actual offline consumers, not the separate P13b Kafka/Flink deployment.
