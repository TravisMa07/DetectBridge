# P10 synthetic compatibility fixtures

These are original Apache-2.0 synthetic declarations and independently reasoned
expectations, not telemetry recordings or upstream Sigma rules. The existing P09
rule stays at its original repository path; `candidates.json` pins its exact bytes
at commit 4d7d685 and preserves its provenance. Generated ephemeral semantic rules
retain that origin and add an explicit modification hash chain.

Mapping profiles bind exact P03 example source snapshots. Sparse source mappings
are intentional: Windows declares Image/CommandLine, Linux audit Image, and
OpenSSH User. Other aliases are explicitly unsupported, even when a synthetic
normalized event happens to contain an otherwise valid ECS value. No declaration
qualifies a production parser or capture capability.

`compatibility-cases.json` stores literal expected outcomes and rationales reasoned
from the declared semantics before evaluator changes. A read-only child review
checked them independently; owner semantic acceptance remains pending. Never
regenerate these expectations from evaluator output. `tools/check_mapping.py`
executes them through YAML → compiler → the production Java evaluator.

P10b adds four original synthetic selection rules and literal shared-budget
expectations. A/D each compare Image to x; B mismatches the Windows source; C
requires its unsupported User alias. Four ticks per supported leaf yield the
independent 7/8/3 budget outcomes in selection-expectations.json. Candidate
provenance retains the real original process.yml and explicit modification chains.
The synthetic all-capabilities profile in the test helper exists only to run the
legacy predicate oracle through both v2 paths; it claims no parser capability.
