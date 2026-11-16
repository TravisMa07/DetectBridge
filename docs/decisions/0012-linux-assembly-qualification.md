# ADR 0012 — Checkpointed Linux assembly qualification

Status: proposed implementation decision for owner review in P12b.

Refines A03/A06 and accepted ADR 0004; preserves at-least-once acknowledged Kafka
output, P03 identity and P12a semantic policy. The owner authorized the P12b plan
and implementation; this does not invent a separate semantic-review approval.

## Decision

Use detached, bounded prepared transitions plus a checkpointed output-intent
prefix. An in-memory callback or collector return is not durable admission.
Only completed-checkpoint intents publish; retirement crosses a subsequent
successful checkpoint together with required sink acknowledgements. Restoring a
completed checkpoint can repeat its retained stable intents. Do not claim Kafka
exactly once or introduce transactional activation/archive services.

Keep one ordered partition/operator for meaningful global quotas. Bound source
inbox, output intents and incremental drains explicitly. Retain absolute deadlines,
closed keys, fingerprints and run lifecycle; capacity failure keeps visible
retained input instead of silently evicting accepted evidence. Bind restore to
immutable code/source/mapping/policy/limits/registration and broker destination.

Qualification observations are body-free and independently tied to completed
checkpoints. They never replace authoritative Flink state or original evidence.
Existing offline durable Commit remains intact; prepared transitions do not invoke
that external callback. No production P13 or scaling decision is made here.

## Alternatives and consequences

Immediate volatile emission cannot establish the promised atomic state/output
intent boundary, particularly for time-dependent closure before a checkpoint.
Kafka transactions would change the existing delivery policy and still need
source/assembly/late-evidence semantics; they remain outside this PR.

Checkpoint-first release adds latency and bounded queues. The current JSON state
format deliberately favors inspectability over capacity; transient memory and
checkpoint cost require honest limits and evidence. Permanent closed-key pressure
can halt admission; explicit new-run/replay policy is separate work. Source/semantic
review and recorded eligible audit evidence remain full-P12 acceptance gates.
