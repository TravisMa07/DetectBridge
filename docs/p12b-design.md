# P12b design notes

Status: implementation authorized 2026-11-15; runtime qualification pending.
Base is merged P12a 9ea1c68 plus the reviewed plan 55a28f2. Merged-main CI must
pass before runtime qualification. Preserve ADR 0004 at-least-once output.

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

## Closure budget

One prepared transition returns at most one group closure: at most one event and
one membership manifest, each independently capped at 1 MiB by P12a. If the input
is consumed, the wrapper adds at most one receipt; other preservation/quarantine
paths emit one document plus, where applicable, one receipt. The wrapper checks
each document against the same 1 MiB cap. Three maximum-size documents plus three
fixed intent wrappers (sequence, bounded kind and 71-character SHA key; below
1 KiB combined) fit below 3 MiB + 1 KiB, inside an empty 8 MiB/64-entry outbox.
A partially occupied outbox may defer the whole proposal without admitting it.
P12a's oversized-event policy and manifest_limit_backlog remain explicit; a group
at its input byte/member cap is not a promise that arbitrary metadata fits an
output document. No evidence is truncated to make it fit. These serialized bounds
do not include the transient copies, parser objects or Flink/Kafka buffers.

## Baseline qualification evidence

The first merged-main run 43750911904 failed P10 incompatible_restore with
unrelated_incompatible_restore_failure; required-checks correctly failed. No job
exception artifact was retained, so the original cause is unclassified. One
unchanged failed-job rerun was requested, without changing acceptance or treating
an arbitrary failure as binding rejection. Isolated implementation/compile work
may proceed while that reproduction runs; actual new-runtime qualification stays
gated on the baseline result. This changes work ordering, not acceptance semantics.

The unchanged failed-job rerun of merged-main 43750911904 passed. The initial P10
failure remains unclassified; no check was relaxed. Runtime qualification is now
unblocked. State-model tests cover detached one-group drains, durable prefixes,
byte-identical recovery duplicates, aborted notification, deadline restore, bounded
inbox/outbox and hash/location-only quarantine. Auth shares the runtime's bounded
run/receipt lifecycle, including idempotent retries and immutable run end.

Operator checkpoint inventories retain only IDs/hashes, scope keys, input
locations and pending intent references in the isolated /state volume. They are
qualification observations, never recovery/admission authority. A verifier may
use them only for the exact checkpoint independently confirmed completed by Flink.
Aborted/uncompleted inventories cannot establish durability. Original bodies stay
in authoritative checkpoints/retained input; no body is copied to evidence logs.

The first exploratory runtime replay exposed an oracle bug: manifest scope lives
in key.run_id, not a top-level run_id. The verifier now follows the existing
manifest contract and has a valid-manifest/wrong-scope regression. It did not
weaken manifest content/identity comparisons. A missing diagnostic-handler import
was also corrected. The exploratory failed run is not acceptance evidence.

Registered local objects are capped at 128 entries, 32 MiB per object and 64 MiB
total. The launcher verifies names/content, copies exact bytes into its ignored
owned cache and mounts only those objects plus the immutable registration read
only. The runtime validates the registration digest before restore/admission and
at checkpoints; it verifies whole-object and record hashes, range/framing and
dataset position on resolution. An absent registered object is visible I/O backlog,
not a nonmatch. No URI selects a filesystem path or causes a network request.

Prepared proposals now explicitly bypass the legacy external durable callback;
a forbidden callback guards accidental use. Offline Commit semantics are unchanged.
The runtime envelope binds auth contracts as well as audit contracts while sharing
one bounded run/receipt lifecycle. Auth retries are idempotent and run-end prevents
new auth admission just as it prevents new audit groups.
