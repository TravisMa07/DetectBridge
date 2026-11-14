# Compiler and evaluator slice

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
