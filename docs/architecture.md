# Architecture decision register

Status: accepted architectural direction; implementation pending. Individual
wire formats, algorithms, version pins, and numerical limits are assigned to PRs
in the [roadmap](roadmap.md). No statement here asserts implemented capability.

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
