# ADR 0002 — Isolated local replay and committed segments

Status: accepted

Owning issue: [P05](https://github.com/TravisMa07/DetectBridge/issues/5).

Refines architecture-register A03/A06 and ADR 0001; supersedes no prior decision.

## Context

Replay needs stable evidence identity, explicit timing, bounded resource use and
restart recovery before P07 introduces Kafka delivery. Source parsing and assembly
are still separate work, so replay cannot infer reliable source occurrence times.

## Alternatives

Rewriting raw timestamps would change evidence semantics. Extracting timestamps
inside replay would duplicate future source adapters. One append-only output file
plus a checkpoint alone leaves uncertain partial writes after crashes. Per-run
first observation would change the raw envelope every time evidence is replayed.

## Decision

Wrap unchanged P03 raw records in a separate versioned replay envelope. Accept an
optional pinned sparse timing index; retain its exact bytes. Persist first local
observation outside run state and reuse it across runs. Shift only effective replay
time using integer nanoseconds; use a fixed monotonic rate independently of time.

Freeze selection order, catalog manifests, hashes, capture metadata, timing/rate,
anchor and tool version in an exclusive UUID run. Reference original record ranges.
Bound input, record, index, output and segment sizes before emission. Commit fsynced
segment directories atomically; derive progress/completion from verified segments,
not solely a checkpoint. Reconstruct expected output during resume, validate actual
committed prefixes and reject corruption. Use per-run process locks. End markers
represent exhaustion only. See the [replay guide](../replay.md) for exact formats,
limits and recovery assumptions.

## Consequences

Resume performs bounded full verification rather than trusting metadata, trading
startup work for strong local evidence checks. Evidence objects and captures must
remain available. Local POSIX filesystem guarantees do not establish distributed
or exactly-once Kafka delivery. A crash during initial manifest creation may leave
an invalid unused UUID directory; recovery fails explicitly rather than guessing.

## Validation

Synthetic cases cover byte ranges, stable identity, exact timing/shift, sparse
fallback, invalid inputs, bounds, pacing, publication/checkpoint crash windows,
locking and committed corruption. Separate recorded qualification verifies all
four seed artifacts on macOS ARM64 and opt-in Linux AMD64 without making public
network availability part of required CI.

## Revisit conditions

Revisit for P07 delivery acknowledgments, P14 archives, Windows host development,
network/shared filesystems, additional framing modes or larger limits. Changes to
frozen schemas or time semantics need explicit version/compatibility review.
