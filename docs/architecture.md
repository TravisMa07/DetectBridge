# Architecture decision register

Status: accepted architectural direction; implementation and qualification status
varies by milestone. Individual wire formats, algorithms, version pins, and
numerical limits are assigned to PRs in the [roadmap](roadmap.md). Accepted
direction alone does not establish implemented or qualified capability.

For a material change, add a numbered ADR under `docs/decisions/` describing
context, alternatives, decision, consequences, validation, and revisit conditions.
Reference the superseded register entry; retain decision history rather than
silently rewriting it. Routine details belong in PR design notes.

## A01 — Independent, laptop-first platform

Use a public monorepo and Apache 2.0 for original work. Build independently while
reusing suitable licensed dependencies. Start with restartable local operation,
recorded Windows/Linux datasets, and local OpenSearch. No cloud source, SaaS,
multi-tenancy, host-failure availability, or throughput commitment in v1.

Use Kafka, Java/Flink, Python management API, PostgreSQL, and React/TypeScript.
Local Compose profiles precede Kubernetes. Service boundaries avoid assuming
multiple workers share a local filesystem. Owner: P02, P06, P17–P19.

## A02 — ECS and standards-based source contracts

Adopt an ECS common core with source-specific fields and `detectbridge.*`
processing metadata. Preserve original evidence independently. Contracts reuse
source documentation, ECS semantics, and Sigma logsource conventions; our layer
defines mappings, integrity checks, and capability diagnostics.

Separate event identity, source event code, replay identity, and detection
identity. Separate occurrence, observation, ingestion, and processing timestamps;
record fallback/quality explicitly. Pin schema and transformation versions.
P03 implements the v1 contract baseline; see [ADR 0001](decisions/0001-event-source-contracts.md)
and [field reference](../contracts/v1/README.md). Parsers remain P11/P12.
Owner: P03, P11, P12.

## A03 — Source-specific assembly and quality

Assemble records only using source-defined relationships, never merely nearby
timestamps, process IDs, or hostnames. Record closure reason separately from
evidence quality. Preserve record membership and assembler version in manifests.

Insufficient-quality assemblies are preserved/forwarded but skipped for ordinary
detection. Emitted events remain immutable; late evidence is retained and linked
for isolated replay. Profile-specific eligibility remains an owning-PR decision.
No 2-second/10-second timing proposal is adopted as a final default.

Distinguish legitimate absence, extraction failure, unmapped, truncated, and
conflicting fields. Distinguish matched, unmatched, not applicable,
configuration-blocked, quality-skipped, and evaluation-error outcomes. A rule
referencing an absent field is not automatically invalid; retain supported Sigma
semantics. Fixed, reviewed source policies precede operator-editable policies.
Owner: P03, P11–P13, P16.

## A04 — pySigma compiler and Java evaluation

Sigma YAML is parsed and validated by pySigma. A DetectBridge compiler emits a
versioned execution plan loaded by a Java evaluator inside Flink. Python is not
invoked per event. Do not translate Python source into Java or assume pySigma
validation proves Java semantic equivalence.

Document supported constructs, reject unsupported behavior explicitly, compile
once per bundle, and test with independently reviewed expectations. Supplementary
comparisons to pySigma are not the sole oracle. Optimize only with equivalent
results and measured evidence. Custom semantics and compatibility maintenance
are accepted costs. Native-engine evaluation is not a prerequisite; P09 is an
end-to-end compiler/evaluator proof of concept. Owner: P09, P10, P20.

## A05 — Rules and configuration

Lifecycle: import → validate → test → stage → activate → retire. Preserve upstream
provenance, licenses, revisions, and local modifications. Synchronization creates
candidates, never automatic activation. Bundles are immutable and include the
applicable mappings. Rollback selects an earlier compatible bundle.

Workers validate complete bundles and swap atomically per worker. Temporary
mixed versions are allowed and visible; events carry the actual versions used.
Activation is complete only when participating workers acknowledge the intended
bundle. Handle joining/restarting workers and publish failures explicitly.
Owner: P10, P15, P17, P18.

## A06 — Preservation, recovery, and replay

Acceptance is successful Kafka acknowledgment under the configured durability
policy. Use checkpoint recovery and at-least-once processing with stable output
identities. Retry transient errors; durably quarantine permanent failures.
Backpressure and alert under exhaustion rather than intentionally discarding
accepted events. Kafka retention must account for archive progress; finite disk
capacity cannot preserve an unbounded outage. Local storage is not disk-failure
protection. Owner: P07, P08, P14, P16.

PostgreSQL holds configuration/operational metadata; Kafka transports and buffers;
compressed NDJSON archive segments and manifests retain evidence; OpenSearch
provides searchable derived views. A narrow archive interface permits later
object storage. Retention durations and budgets are not settled at bootstrap.

Historical replay uses original assembly membership and pinned rules, mappings,
parser/evaluator versions, and any decision-affecting enrichment snapshot.
Current-policy reprocessing may change membership/results. Isolate output by
replay run. Processing-time timeout replay alone cannot promise identical
historical grouping. Owner: P05, P14, P16.

## A07 — Operations and security

Provide structured JSON operational logs, Prometheus-compatible metrics, and
OpenTelemetry instrumentation where useful. Optional monitoring backends conserve
laptop resources. Separate operational health, processing quality, and evaluation
coverage. Avoid high-cardinality metric labels and raw evidence in routine logs.
Keep administrative audit history separate. Owner: each runtime PR.

Start with authenticated single-user administration, local-only exposed
interfaces, private container networking, generated credentials, and secrets
outside Git. Treat imported input as untrusted with resource/execution limits.
No arbitrary user-provided Python/Java in the pipeline. Defer enterprise RBAC/OIDC
and multi-tenancy. Owner: P06, P09–P12, P17.

## A08 — API, UI, and capacity

Use a modular management backend with versioned APIs and status-bearing jobs for
long operations. UI and automation share validation. Infrastructure deployment
stays in Compose initially; no general visual pipeline designer in v1.

Measure parsing, assembly, matching, sinks, and integrated capacity. Record
hardware, event sizes/source mix, rule corpus, latency percentiles, memory, and
backlog. Separate real supported rules from synthetic stress cases. No artificial
license caps; explicit operational limits protect resources. Owner: P17–P20.

## A09 — Expansion boundaries

- Attack chains: separate downstream Flink job, deterministic event-time Sigma
  correlation subset, bounded state and explicit entity/time/late-event policy.
  Preserve evidence links. A sequence match or step percentage is not a calibrated
  probability of compromise. Keep correlation distinct from record assembly.
- AI: optional asynchronous assistance supporting local and hosted models through
  a replaceable provider interface. Human approval for rule/mapping activation;
  no autonomous suppression or routing. Explicit external-data configuration,
  minimization and budgets. Log content is untrusted. Record model/prompt and
  evidence versions; regenerated prose is not promised identical.
- Routing: forward all first; measure shadow policies before selective routing.
  Unmatched does not imply harmless. Confirm archival availability before
  withholding SIEM forwarding; retain diagnostics and quality failures.
- Distributed deployment: externalized configuration, explicit state and stable
  schemas now; Kubernetes, shared checkpoints, object storage and replicated
  services later. Scaling and high availability need separate qualification.

Owner: post-v0.1.0 milestones, with contracts prepared in earlier PRs.

The local replay boundary is specified in [ADR 0002](decisions/0002-local-replay.md)
and the [replay guide](replay.md). It preserves P03 evidence inside a separate
run envelope; committed local files do not establish downstream delivery.

P06 refines local service/resource and access boundaries in
[ADR 0003](decisions/0003-local-infrastructure.md); see the
[local stack guide](local-stack.md). Infrastructure persistence qualification does
not establish transport delivery or Flink job recovery.

P07 introduces the checkpointed replay transport boundary in
[ADR 0004](decisions/0004-replay-transport.md) and the
[transport guide](transport.md). It does not implement normalization or detection.

P08 introduces an independent metadata-only OpenSearch writer with create-and-verify
identities, Kafka-backed failure accounting and explicit offset commits. See
[ADR 0008](decisions/0008-opensearch-writer.md) and the [writer guide](writer.md).
It preserves P03/P05 contracts and P07 transport/checkpoint boundaries.

P09 refines A04 with the bounded normalized-fixture slice in
[owning design notes](p09-design.md) and the [detection guide](detection.md).
Its separate evaluation-result contract does not freeze P13 detection outputs.

P10a refines A04/A05 with versioned source mapping/candidate provenance and
explicit legacy/v2 offline semantic modes in [design notes](p10-design.md).
It preserves the accepted boundaries; P10b owns selection/runtime acceptance,
P11/P12 own adapters, and P15 owns activation.

P10b implements source-only candidate indexing with an exhaustive reference and a
separate v2 detection deployment in [design notes](p10b-design.md). P09 topics and
checkpoint bindings remain independent. The [adapter boundary](source-adapter-interface.md)
specifies P11/P12 obligations without claiming parser implementation.

P11 implements the bounded Windows source adapter boundary from A02/A03 in
[owning design notes](p11-design.md), using module-local JSON context APIs and
unchanged P03 schemas. This is an offline library/runner, not the P13 production
pipeline. Recorded inputs without trusted host bindings remain skipped.

P12a implements the offline Linux audit/authentication boundary with scope-keyed
bounded transactional assembly, immutable membership/late links, module-local
context/manifest/state schemas and an atomic authentication replay command. It
does not deploy P12b Flink state or P13 production wiring. A small actual local
OpenSSH9 capture qualifies the selected password grammar. Later P12c selected
audit evidence and owner acceptance are recorded below; the original P12a ledger
retains its historical gaps. See the
[P12a design](p12-design.md) and [ledger](p12-ledger.md).

P12b's isolated checkpointed Linux assembly implementation refines A03/A06 through
prepared transitions, durable output intents, restored absolute timers and strict
runtime/destination bindings. It preserves ADR 0004 at-least-once output and does
not implement P13. See [ADR 0012](decisions/0012-linux-assembly-qualification.md),
[runbook](linux-assembly.md) and [qualification ledger](p12b-ledger.md) for exact
acceptance status; implementation alone does not establish runtime qualification.

P12c adds controlled recorded-source qualification and a non-resumable atomic
offline audit replay command under existing A02/A03/A06 boundaries. The audit lab
uses a separate emulated guest kernel; host audit state is untouched. Original
evidence remains local, completeness expectations remain independent, P03/source
snapshots and persisted runtime bindings remain unchanged, and no P13/archive
service is introduced. See the [design](p12c-design.md) and [ledger](p12c-ledger.md).

P12c #43 merged as c024497 with completed bounded owner semantic/completeness
review and separate merge authorization recorded in its description. Final-head
AMD64 qualification and merged-main run 43873905332 passed.
[P13 design notes](p13-design.md) propose integration under A02–A07
and the explicit ADR 0008 projection compatibility review. Older public Windows
bindings remain unresolved; the new controlled-source owner acceptance is recorded
below. The subsequent P13a/P13b implementation boundaries are recorded below.

P11 controlled Windows source qualification adds a separately cataloged local
capture with actual registry/VM/boot provenance, encrypted acquisition and frozen
independent expectations under the unchanged A02/A03 adapter boundary. It does
not repair old recording identities or implement a registry/P13 service. See the
[owning design](p11-recording-design.md) and [review packet](p11-recording-review.md)
for technical evidence and completed bounded owner semantic acceptance. Completion
PR #45 is owner-merged as 4ac31fa with final-head and merged-main qualification passed.

P13a refines A02–A07 through separately versioned wrappers around unchanged P03,
compact mapped evaluation with fixed grouped diagnostics, domain-separated output
identities and deterministic pinned enrichment. Actual Windows/Linux offline
runners consume it explicitly; legacy result contracts/deployments remain compatible.
See [owning decisions](p13a-design.md) and [qualification](p13a-ledger.md).
This does not implement P13b production recovery/wiring or P13c search projections.

P13b adds an isolated Kafka/Flink deployment of the actual adapters, prepared audit
assembler and compact evaluation before atomic intent commit. Its versioned
state/topics/group and artifact/plan/destination/evidence bindings reject old
checkpoint adoption. [Design](p13b-design.md) retains A02–A07 checkpoint-prefix
release, immutable memberships/late links and bounded visible backlog; an explicit
1.1.0 runtime output profile preserves P13a offline 1.0.0 contracts. Existing P12
implementation/deployment is unchanged. [Qualification](p13b-ledger.md) separates
actual runtime failures/recovery from component checks; search remains P13c.

P13c adds a separate versioned search writer with three exact indices, a dedicated
role and strict producer/destination/artifact bindings. It preserves P08's existing
configuration, projections, permissions and two physical indices. Its derived
view uses original P13 identities, excludes receipt clocks/physical copies from
content conflict checks and retains original Kafka evidence/manifest links.
[Compatibility decisions](p13c-design.md) keep A02–A07 and ADR 0008's independent
consumer/acknowledged-failure boundary; [qualification](p13c-ledger.md) is separate
from complete recorded source-to-search milestone acceptance.

P13d adds opt-in qualification of the accepted controlled originals through the
existing P13 deployment and writer, with a separately pinned qualification plan.
It reuses accepted source/host/boot and independent source assertions, and corrects
qualification checkpoint selection/probe attribution without changing persisted
runtime semantics. See [design](p13d-design.md) and [acceptance map](p13-acceptance.md).
P13 completed its bounded owner
acceptance, owner merge #49 and actual merged-main qualification on 07e5382;
[P14 design](p14-design.md) scopes archive/replay work under A02–A07;
its implemented slices and separate qualification gates are recorded below.

The pinned Kafka writer compatibility guard is scoped to P13's existing
at-least-once sink. It preserves first-error propagation and stock resource
cleanup, and only attaches a secondary send error after proven producer closure
to an already propagated failure. JVM/resource-cleanup failures remain fatal.
The [owning decision](p13d-design.md) records the private-API pin, deterministic
regressions and mandatory fresh-artifact recovery qualification. No upstream class
is replaced and no persisted contract or writer commit policy changes.

P14a refines A02/A06/A07 with a separate local archive consumer, compressed NDJSON
object/segment backend and immutable binding/offset recovery under a distinct
root/group. [Owning freeze](p14a-design.md) e9b6143 precedes implementation;
[qualification and limits](p14-ledger.md) remain separate. Original P03/P05/P12/P13
contracts, producers and derived-search roles stay compatible. This is not P14b/c
historical/current execution, P05 archive import, automatic retention or HA.

P14b adds sealed selections, an external replay catalog and original-membership
historical batch execution under A02–A07. It invokes the exact accepted P13 JAR's
adapters/assembler/evaluator and pins its controlling CLI and local publication
contract. Separate processes keep archive dependencies out of the historical
classpath. No P13 checkpoint adoption, activation or live search forwarding occurs.
[Freeze 5922901](p14b-design.md), [operator guide](historical-replay.md) and
[qualification](p14b-ledger.md) retain the supported profile, finite bounds and
separate owner/native gates.

P14c1 adds explicit new-plan evaluation and virtual-clock admission of selected
original inputs through that supported original Machine, assembler and evaluator.
Current membership may change; original archive bytes, membership and historical
results remain immutable. A disjoint local workspace binds the request, artifacts,
root and limits; each atomic transition includes actual machine state, and resume
re-executes and verifies the complete committed prefix before appending. No old
checkpoint, live forwarding or activation is adopted. See the [owning freeze](p14c1-design.md),
[operator guide](current-replay.md) and [qualification gates](p14c1-ledger.md).
Retention/deletion and remaining milestone acceptance are separate work.

P14 bounded owner completion and actual merged-main qualification are reconciled
in the [merged audit](p14-merged-main-audit.md). P15a refines A05/A07 with a
private Unix-account candidate store, immutable full-closure identity, explicit
compiler validation and actual Java sample tests before staging, plus ordered
local proposal preparation. It does not install desired state or implement worker
activation. The [design](p15-design.md), [operator guide](rule-lifecycle.md) and
[evidence](p15a-ledger.md) preserve original P13/P14 artifacts and accepted A02–A07.
P15b owns the separate runtime/acknowledgment/archive boundary; no old checkpoint
is adopted and no complete P15/P16 capability is inferred.

P15b1's [runtime freeze](p15b-design.md) adds signed effective publication,
explicit isolated worker incarnations and immutable closure-time attribution,
with a new checkpoint/output profile. Before its implementation, the owner retained
S12's requirement to reject even a validly signed self-rehashed AST that disagrees
with original YAML. The separately frozen [validator boundary](p15b-validator-design.md)
uses the same pinned compiler in a bounded per-worker service, called over a private
Unix socket before bundle installation. Its packet and actual image identities
join the runtime/checkpoint binding; it performs no event-time Python evaluation.
This records the design and owner decision, not runtime qualification. P15b2 still
owns the new archive/replay graph before full P15 acceptance or dependent P16 work.

[ADR 0015](decisions/0015-qualification-artifact-preparation.md) records the owner's
CI-01-only artifact preparation boundary: an ephemeral qualification capability
and actual worker readiness before the30s case, with normal effective publication
and worker semantics unchanged. Implementation/qualification remain separate
from accepted direction and P15/merge/release gates.
