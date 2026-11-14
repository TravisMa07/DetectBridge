# P09 compiler and evaluator design

Status: implemented in draft; runtime qualification and independent expectation
review are required before acceptance.

## Boundary and decisions

P09 depends on merged P03 and P07, based on cb87eb8. A separate normalized-input
Flink job preserves the replay relay and P08 writer contracts. Python compiles
once; the same Java evaluator serves offline and Flink execution. No adapters,
OpenSearch integration, dynamic activation or production detection format is added.

The plan/result contracts are version 1.0.0. Plans retain original YAML, hashes,
rule UUIDs, source-contract snapshots, mapping and compiler versions. Hashes cover
compact UTF-8 JSON with sorted object keys, without the bundle hash itself.
Bundles are immutable; unknown versions/operators and incomplete bundles fail closed.

pySigma 2.1.0 parses rules and conditions. The compiler permits named map selections,
AND/OR/NOT, parentheses, string/integer predicates, OR value lists, wildcards and
one contains/startswith/endswith modifier. Unsupported constructs, including unused
selections, null literals, regex, booleans, floats and quantifiers, fail explicitly.
Image, CommandLine, ProcessId and User map respectively to process.executable,
process.command_line, process.pid and user.name. These fixture mappings do not
claim general Sigma or source compatibility.

Strings use Java code-point lower(upper(cp)) folding, with no normalization or
multi-character expansion. Wildcards operate on code points without regex.
Missing positive predicates are false; NOT can match missing fields. ECS nulls
are invalid. Rule lists are OR and event arrays use any-element semantics.
Source applicability and quality gates precede evaluation. Unknown source contracts
are configuration-blocked; invalid events are quarantined, never unmatched.

Limits: 256 KiB/YAML, 100 rules, 4 MiB/bundle, depth 32, 4096 nodes/rule,
65536 nodes/bundle, 4096 code points/pattern, 16 source snapshots at most 4 MiB
each, 1 MiB/event, one million evaluation
operations/event and 30 seconds/compiler invocation. Limit failures are explicit.
Diagnostics expose categories/locations rather than values or exception text.

Dedicated detection input/results/quarantine topics use P07's single-partition,
retained-input, at-least-once checkpoint boundary. Results retain input references,
event/run/bundle identity and version attribution. Evaluation-result IDs are not
P13 detection IDs. Restore requires the same bundle and topic configuration.

## Independent expectations

Fixtures are original Apache-2.0 synthetic material, not captured telemetry.
Expected outcomes and rationales are written before evaluator implementation.
They must not be regenerated from evaluator results. Owner review of these
expectations is required before acceptance; authorship is not independent review.
P03 examples supply structural scaffolding only, not detection ground truth.

## P08 coordination

P08 owns writer-specific contracts/modules. Preserve its module registration when
reconciling settings.gradle.kts. Other potential overlaps: Gradle locks/verification,
Python dependency pins, dev commands, CI applicability/aggregate checks, inventories,
README, roadmap and architecture register. Use separate detection deployment files.
Do not alter P07 schemas, relay behavior or recovery state. Rebase and rerun affected
consumer checks after either PR merges. No automatic merges or publication.

## Implementation refinements

The pySigma 2.1.0 numeric constructor can convert exact large integers to floats.
The compiler restores validated YAML integers into typed detection items before
condition expansion; signed-64-bit boundary regressions verify exact results.
Source snapshots use the existing closed P03 source-contract schema. A compiler
failure preserves any previous valid output and returns nonzero; no partial bundle
is activated. Checkpoint bindings include the consumer group and evaluator version.

Fault qualification changes quarantine minimum ISR through the bounded helper
container, with readback, rather than launching another JVM inside Kafka. Outcome
counters have fixed labels; no rule/run/event identities enter metric labels.
