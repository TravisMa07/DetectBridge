# Delivery roadmap and decision ownership

P01–P05 are merged. P06 implementation is under review; subsequent PRs remain
planned. P numbers are planning IDs, not GitHub PR numbers. Milestones require
their acceptance evidence and authorized merges; documentation alone does not
complete a milestone.

## Milestones

| Milestone | Work | Exit gate |
| --- | --- | --- |
| M0 — Repository foundation | Bootstrap, P01–P02 | Public documented repo, real checks, usable contribution/decision workflow |
| M1 — Contracts and evidence | P03–P05 | Pinned Windows/Linux evidence enters reproducibly under explicit contracts |
| M2 — Working transport | P06–P08 | Recorded events traverse local stack with accounted delivery outcomes |
| M3 — Detection proof of concept | P09–P10 | Independent expected matches pass; unsupported features fail explicitly |
| M4 — Source integrity | P11–P13 | Both sources evaluated with traceable evidence and distinct quality outcomes |
| M5 — Recovery and configuration | P14–P16 | Qualified recovery, pinned historical evidence and visible preservation limits |
| M6 — Operator experience | P17–P19 | Operator can configure, test, inspect and troubleshoot supported workflows |
| M7 — Release qualification | P20–P21 | Exact candidate meets v0.1.0 acceptance suite |

Numbering is the intended sequence; explicit dependencies govern scheduling.
Independent design work may proceed earlier. Split oversized work into coherent
PRs without losing its acceptance gate. Do not implement all milestones in the
bootstrap commit. Instrumentation, security and docs accompany each owning PR.

## Bootstrap — initial local seed

Deliver overview/status, license/content policy, accepted architecture, SDLC,
roadmap, contribution/security guidance and ignore rules. Check contents and
relative links, initialize `main`, and create the local seed commit. Present the
exact contents and commit before publication. Confirm GitHub owner/repo first.
No application scaffolding, runtime capability claims or release tag.

## M0 — Repository foundation

### P01 — Governance, CI and remote repository policies

- Depends on: reviewed/published bootstrap.
- Deliver: issue/PR templates, real hygiene checks, `required-checks` aggregate,
  milestones/issues/project board, private security reporting and branch policies.
- Resolve: check tooling and versions, trigger/applicability logic, board fields,
  repository permissions and administration limits.
- Acceptance: positive and intentional-failure checks demonstrate enforcement;
  docs-only PR avoids runtime services; protections and merge settings are read
  back from GitHub; owner retains merge authorization.
- Boundary: no passing dummy component jobs, no production service implementation.

### P02 — Language tooling and local conventions

- Depends on: P01.
- Deliver: uv, Gradle Wrapper and npm conventions, pinned compatible toolchains,
  dependency lockfiles where applicable, shared local/CI verification entrypoints.
- Resolve: exact runtime/build versions, workspace paths and formatting/type tools.
- Acceptance: clean checkout can run documented bootstrap/build commands on
  supported development architecture; toolchain incompatibilities fail clearly.
- Boundary: do not claim service behavior from toolchain smoke checks.

## M1 — Contracts and evidence

### P03 — Event/source contracts, identity and time

- Depends on: P02.
- Deliver: versioned event/source schemas, examples and validation cases.
- Resolve: ECS version/subset, required fields/namespaces, source identity,
  event/detection/replay IDs, timestamp fallback and quality, schema evolution,
  source capabilities and blocking conditions.
- Acceptance: Windows/Linux examples distinguish event code from occurrence ID,
  absent from failed extraction, and occurrence from ingestion time; incompatible
  contracts fail visibly. Document expansion hooks and consumer compatibility.

### P04 — Dataset catalog, licensing and acquisition

- Depends on: P03.
- Deliver: selective acquisition, pinned manifests, cache and provenance records.
- Resolve: initial scenarios/formats, artifact-specific terms, checksums, safe
  archive extraction/size limits, labels and conversion provenance.
- Acceptance: repeated acquisition produces identical artifacts; corruption is
  rejected; Windows/Linux selections have documented rights/context. No bulk
  downloaded corpus enters Git. Unknown labels remain unknown.

### P05 — Replay CLI and run isolation

- Depends on: P03, P04.
- Deliver: replay reader, rate control, preserved/time-shifted timestamp modes,
  explicit run identity and output isolation contract.
- Resolve: input framing, ordering, pacing, bounded buffers, interruption/resume,
  timestamp shifts and dataset-end signaling. Kafka execution is wired in P07.
- Acceptance: repeated fixture playback is attributable and reproducible; original
  evidence is unchanged; separate runs cannot collide with live output identities.

## M2 — Working transport

### P06 — Resource-limited local environment

- Depends on: P02, P03.
- Deliver: core/full Compose profiles, pinned compatible images, private networking,
  persistent volumes, health checks, credentials and start/stop documentation.
- Resolve: versions, memory/CPU/disk allocations, exposed interfaces, storage
  mounts, image architectures, readiness and clean-reset procedures.
- Acceptance: local ARM64 start/stop preserves intended state; full profile adds
  OpenSearch; optional dashboards are not required; no default shared secrets.

### P07 — Kafka/Flink transport path

- Depends on: P05, P06.
- Deliver: ingestion acknowledgment, Kafka sources/sinks, checkpoints and metrics;
  wire replay into transport.
- Resolve: topics/partitions, keying, acknowledgment policy, checkpoint cadence,
  error contracts and retention assumptions.
- Acceptance: accounted fixture counts traverse Kafka → Flink → Kafka; restart
  behavior and acceptance boundary are documented; no detection claim yet.

### P08 — OpenSearch writer

- Depends on: P07.
- Deliver: idempotent indexing, error index/quarantine, per-item retries and metrics.
- Resolve: index templates, IDs, batching, retry bounds, permanent failure classes
  and sink offset acknowledgment.
- Acceptance: partial bulk failures are handled individually; outage/recovery
  preserves accounted inputs; replay does not overwrite live results.

## M3 — Detection proof of concept

### P09 — Compiler and evaluator vertical slice

- Depends on: P03, P07.
- Deliver: pySigma parser/validation integration, execution-plan compiler and
  minimal Java evaluator together, integrated into a Flink path.
- Resolve: pySigma version/license obligations, plan format/version, minimum
  constructs, type/case/null behavior, regex safety, resource limits and errors.
- Acceptance: independently reviewed normalized fixtures prove complete
  YAML → plan → Java → matches behavior. Unsupported constructs fail explicitly;
  no per-event Python calls. No native-engine comparison prerequisite.

### P10 — Compatibility matrix and mapping coverage

- Depends on: P04, P09.
- Deliver: supported-feature matrix, semantic regressions, mapping validation and
  source-aware rule selection. Preserve candidate rule provenance.
- Resolve: added modifiers, list/boolean/negation behavior, field mapping
  capabilities, corpus compatibility and compile-time diagnostics.
- Acceptance: meaningful positive/negative/edge expectations; supplementary
  pySigma comparisons do not replace independent expectations. Optimized rule
  selection matches exhaustive supported evaluation.

## M4 — Source integrity

### P11 — Windows adapters and quality

- Depends on: P04, P10.
- Deliver: source contracts/adapters for selected Security and Sysmon formats,
  ECS mappings and quality/capability diagnostics.
- Resolve: provider/event versions, XML/JSON framing, decoded fields, timestamp
  quality and source-specific eligibility; legitimate missing command-line data
  must not automatically be called parser corruption.
- Acceptance: recorded fixtures distinguish unsupported sources, missing capture
  capability, parse failure and actual nonmatches; originals remain accessible.

### P12 — Linux adapters and audit assembly

- Depends on: P04, P10.
- Deliver: audit execution and selected authentication adapters, bounded keyed
  assembly state, closure metadata and membership manifests.
- Resolve: exact authentication format, grouping identity, boundaries/timeouts,
  argument/path preservation, late-key retention, conflicts and overflow behavior.
- Acceptance: interleaved hosts/runs cannot merge; repeated/out-of-order records,
  incomplete groups and multiple paths are tested. Closure is not proof of
  completeness. Known-bad evidence is retained with skipped-detection reasons.

### P13 — Integrated enrichment and evaluation outcomes

- Depends on: P08, P11, P12.
- Deliver: tagged events, linked detections and quality/configuration diagnostics.
- Resolve: match metadata, diagnostics aggregation, evidence references and
  enrichment-version recording.
- Acceptance: both platforms run end-to-end; matched/unmatched/inapplicable/
  blocked/skipped/error remain distinct. Avoid per-event-per-rule output explosion.

## M5 — Recovery and configuration

### P14 — Archive and historical/current replay

- Depends on: P05, P13.
- Deliver: durable archive segments/manifests, pinned artifacts, historical
  membership replay and current-policy reprocessing.
- Resolve: atomic segment commits, offsets, compression, retention/budgets,
  corruption handling, retrieval and preservation of enrichment inputs.
- Acceptance: commit offsets only after durable writes; recover interrupted
  archives; historical pinned results reproduce on qualified fixtures; current
  replay remains isolated. Document unsupported reproduction limits explicitly.

### P15 — Rule lifecycle, activation and rollback

- Depends on: P10, P13, P14.
- Deliver: immutable bundles, staging, worker acknowledgments, convergence state,
  rollback and version attribution. No exposed unauthenticated management endpoint.
- Resolve: config topic protocol, monotonic revisions, worker membership,
  stale/reordered updates, failure/timeouts and safe old-version retention.
- Acceptance: events record actual active bundle; failed candidates preserve
  prior valid state; joining/restarting workers converge; rollback is tested.

### P16 — Failure and preservation qualification

- Depends on: P14, P15.
- Deliver: recovery scenarios, backpressure, late-evidence association,
  disk-pressure/retention coordination and operator runbooks.
- Resolve: finite-outage envelope, stop-admission thresholds, retention versus
  archive lag, quarantine exhaustion and restart sequencing.
- Acceptance: fault injection accounts for accepted evidence as output, durable
  quarantine or visible backlog; no intentional silent shedding; immutable late
  events are linked for replay; laptop/disk-failure limits are explicit.

## M6 — Operator experience

### P17 — Authenticated management API

- Depends on: P15, P16.
- Deliver: modular versioned API, persistent metadata, authenticated administration,
  audit history and jobs for long operations.
- Resolve: API shapes, auth/session policy, secret references, pagination, job
  idempotency, database migrations, permissions and API error contracts.
- Acceptance: unauthorized mutations fail; inputs use existing validators;
  activation/replay progress and failure are inspectable; migration/recovery tested.

### P18 — Source/rule administration UI

- Depends on: P17.
- Deliver: source readiness, imports, validation, sample testing, staging,
  activation/convergence and rollback views.
- Resolve: UX states, accessible forms, editor behavior and error presentation.
- Acceptance: focused browser workflows use the same APIs; sample tests use the
  production Java evaluator; failures cannot appear as successful activation.

### P19 — Operations, detections and replay UI

- Depends on: P18.
- Deliver: pipeline health, evidence/detection inspection, quality gaps and replay.
- Resolve: query boundaries, pagination, retention indicators and metric displays.
- Acceptance: operator can trace evidence and versions, distinguish skip from
  nonmatch, diagnose backlog and start isolated replay; no infrastructure editor.

## M7 — Release qualification

### P20 — Capacity report

- Depends on: P19.
- Deliver: repeatable component/end-to-end benchmarks and report.
- Resolve: corpus sizes/mix, supported distinct-rule counts, warm-up, duration,
  load-generation limits and performance regression thresholds.
- Acceptance: declared hardware and versions, throughput/latency/memory/backlog
  curves, real versus synthetic workloads, no unsupported capacity claims.

### P21 — Release readiness

- Depends on: P20.
- Deliver: clean-install/upgrade/backup qualification, Linux ARM64/AMD64 checks,
  release notes, licenses/SBOM, checksums, pinned artifacts and operational limits.
- Resolve: artifact publication, exact candidate, compatibility matrix and
  supported rollback procedures.
- Acceptance: all milestone gates pass on exact candidate; owner authorizes
  immutable v0.1.0 publication. Do not release merely because a deadline arrives.

## Post-v0.1.0 expansion milestones

Define detailed acceptance criteria before decomposing these into PRs:

1. Deterministic attack chains: supported standard Sigma correlation, event-time
   state bounds, evidence linkage and tested late-event/entity policies.
2. AI assistance: local and hosted providers, bounded/redacted input, evidence
   attribution, human activation and failure isolation from the core pipeline.
3. Selective forwarding: shadow measurements, policy review, confirmed archive
   availability and quality/coverage-aware routing.
4. Distributed deployment: orchestration, shared storage, scaling, replication,
   failure recovery and upgrade qualification as separate concerns.

No calendar or throughput commitment exists. Use milestone evidence and measured
implementation progress to estimate schedules later.
