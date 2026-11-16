# ADR 0008 — Independent metadata indexing and durable writer failures

Status: accepted; P08 implemented and qualified locally on ARM64. Native AMD64
merged-main run 43652317692 passed writer/required-checks on 430609a; CI does not
establish unrecorded owner review. P13 projection compatibility planning is in
[owning design notes](../p13-design.md); P13 remains unimplemented.

Owner: P08, issue #8. This number follows the planning ID to avoid ADR filename
collisions with parallel development in other worktrees.

## Context

P07 produces validated replay envelopes and reference-based quarantine in Kafka.
Search availability must not become a dependency of the validating Flink relay.
The local OpenSearch view precedes source parsing and detection implementation.

## Alternatives

An OpenSearch sink inside the relay would couple its checkpoints and progress to
search availability. Updating documents on retry would conceal conflicting
content. An index per run would increase shard count. An OpenSearch-only failure
index could not durably account for rejected items while OpenSearch is unavailable.

## Decision

Use an independent bounded Java Kafka consumer. Project selected metadata without
retrieving original evidence or retaining inline bodies. Store records and control
markers together in one versioned index so a logical identity cannot bypass
conflict detection by changing kind. Provide filtered aliases for convenience and
a separate diagnostics index. Alias filters are not authorization boundaries.

Use create-only writes with stable identities. Verify duplicates against original
value checksums and recomputed immutable projection content. Exclude physical
Kafka copy location from content identity; retain the first accepted location.
Never overwrite a conflicting document.

Commit consumed windows only after every item is indexed, verified as a duplicate,
or acknowledged into a reference-only writer-failure Kafka topic. Indexing that
failure topic is secondary. Diagnostic failures block rather than recurse.
Unknown failures remain unresolved. Outages exhaust bounded fast retries into
backpressure, not permanent quarantine. Preserve Kafka input while references
or search rebuild requirements depend on it.

Use the existing TLS CA, a dedicated least-privilege writer user, and short-lived
certificate-authenticated administrative helpers. Keep administrative private
material out of the runtime volume. Freeze Kafka and destination identities,
projection/template versions, artifacts, and credential fingerprints.

## Consequences

Indexing and Kafka commits are separate acknowledgment boundaries. Crashes can
repeat work; stable identities account for those attempts. Search is a derived
metadata view, not an archive or completion ledger. First-copy provenance is not
a complete duplicate history. A one-node index has no host/disk-failure guarantee.

A running Flink pipeline can continue buffering output during writer outages,
within finite disk capacity. The optional writer adds 512 MiB to the full profile.
Authentication/configuration drift requires operator repair, not data disposal.

## Validation

Independent expected identities, pure bulk/offset tests, real TLS negative tests,
synthetic full-stack fault qualification, and opt-in recorded qualification cover
this decision. Native AMD64 CI results must be reviewed separately from local
ARM64 qualification. See the [writer guide](../writer.md).

## Revisit conditions

Revisit for normalized/detection documents, archive-backed rebuilds, index lifecycle
management, additional partitions/workers, multi-tenancy, or production deployment.
A projection/index/state change requires explicit compatibility and migration review.
