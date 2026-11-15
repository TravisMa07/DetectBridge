# P12b design notes

Status: implementation authorized 2026-11-15; runtime qualification pending.
Base is merged P12a 9ea1c68 plus the reviewed plan 55a28f2. Merged-main CI must
pass before runtime wiring/qualification. Preserve ADR 0004 at-least-once output.

## Admission and durable intents

Prepared transitions run on detached assembler state and return next-state/output
intents; they never admit input to the live offline assembler or invoke its
external durable Commit callback. Existing offline Commit semantics stay intact.
If an operation would close unchanged retained groups, prepare just one closure
and retry the still-unconsumed input/control. This bounds timeout/end/resource
drains without changing membership or closure policy. A transition involving the
new input can close only its changed group; other retained closures are deferred.

The runtime machine retains assembler state, bounded ordered input backlog,
outbox intents with monotonic sequence IDs and timer deadlines in one operator
state envelope. Outbox cap: 8 MiB/64 documents. Input backlog cap: 8 MiB/64 rows,
separately accounted, including transport/context metadata. These are serialized
safety limits, not JVM heap claims. Capacity exhaustion fails explicitly before
admission/checkpoint progress; original Kafka data remains visible retry backlog.
This bounded qualification path does not promise unrestricted producer throughput.

snapshotState seals the current outbox prefix into a checkpoint. Only successful
checkpoint completion releases that prefix. A restored completed checkpoint also
releases its retained prefix. Prefix retirement occurs after downstream collection;
its retirement and required Kafka sink acknowledgements must cross a later
successful checkpoint together. Failure between collection and retirement or
checkpoint completion can repeat stable output IDs. A failed required sink cannot
advance the retirement checkpoint. No exactly-once claim.

New input can be retained after sealing, but cannot publish until its own
checkpoint succeeds. Due closure work drains before later input admission.
Bounded processing-time callbacks keep mailbox work finite and do not sleep or
block checkpoint handling. A full outbox waits for checkpoint completion; an
exhausted inbox fails with explicit retained-source backlog, never silent loss.

Output values remain exact P03/P12a documents, not oversized wrappers. Separate
versioned transport headers carry runtime binding and intent identity; separate
output topics route event, manifest, diagnostic and quarantine documents. Each
JSON value is at most 1 MiB; original stable document IDs remain Kafka keys.

The runtime binding includes source/mapping content, parser/assembler/policy and
state versions, limits/timer policy, Kafka cluster/topic IDs and group. Restore
validates all state before releasing output or consuming new input. Parallelism
and input partition count are one. No production rescaling or P13 integration.
