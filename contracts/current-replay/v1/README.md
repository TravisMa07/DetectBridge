# Current-policy replay 1.0.0

Closed contracts for explicit new-plan replay of a sealed P14b selection. The
[owning freeze](../../../docs/p14c1-design.md) specifies semantics, supported
executable, finite bounds, deterministic scheduling and atomic state/output
publication. Generic nested Machine state and native output objects are validated
through the supported original Java APIs and complete deterministic re-execution;
they are not an arbitrary extensibility mechanism.

`request` selects all original source admissions exactly once and a new explicit
plan. `run` pins that request, execution artifacts, image and destination. `result`
commits one schedule transition with outputs and post-transition state. `commit`
chains exact result-file hashes/lengths; metadata has canonical compact sorted
UTF-8 JSON plus LF and a separate exact-file checksum. Identity hashes canonical
JSON without LF. No float/bool coercion is permitted for integer metadata.

Fixtures are original DetectBridge Apache-2.0 synthetic rules and independently
reasoned source/count/identity expectations, frozen before implementation. They
reuse the preceding frozen source packet rather than recapturing any evidence.
No retention/deletion or complete P14 runtime claim follows from these contracts.
