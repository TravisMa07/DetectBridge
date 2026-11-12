# ADR 0001 — Versioned evidence and source contracts

Status: accepted

Owning issue: [P03](https://github.com/TravisMa07/DetectBridge/issues/3).

Refines architecture-register A02, A03 and A06; supersedes no earlier ADR.

## Context

Acquisition, replay and detection need shared meanings for records, normalized
events, identity, time and data quality before runtime components are implemented.

## Alternatives

A single normalized envelope would conflate malformed raw evidence with ECS data.
Inline-only evidence simplifies small tests but scales poorly for large/multipart
events. Requiring source time would exclude retained evidence with missing clocks.

## Decision

Use JSON Schema 2020-12, ECS 9.5.0 and DetectBridge contract version 1.0.0 with
separate raw, normalized and source contracts. Permit inline or checksum-addressed
evidence references. Use source-scoped record positions/capture identifiers and
order-independent membership hashes, separate from replay/detection identity.

Preserve missing-time evidence with explicitly labeled first-observed fallback.
Separate schema validity, integrity and eligibility; skipped evidence stays
representable. Preserve vendor fields and require explicit extension namespaces.
Resolve schemas locally with no network retrieval and report value-free errors.

## Consequences

Closed schemas make compatibility deliberate. Producers/readers must register
new versions rather than assume additive compatibility. Referenced evidence needs
later durable retrieval and digest verification. Source profiles are declarations,
not claims of parser support. Correlation must inspect timestamp quality.

## Validation

Run contract validation and regression tests through the shared developer checks.
Use synthetic Windows/Linux examples, independently hashed identity vectors,
malformed schemas/envelopes and socket-blocked reference tests. Qualify on macOS
ARM64 and Linux AMD64 before PR handoff; record results in the owning PR.

## Revisit conditions

Revisit with real dataset/provider evidence in P04/P11/P12, Java interoperability
requirements, new ECS fields, archive formats or cross-host correlation needs.
Identity/meaning changes require a major contract revision and migration design.
