# DetectBridge

DetectBridge is a personal, self-hosted detection-engineering project intended to
sit between log collectors and a SIEM. It aims to normalize telemetry, evaluate
Sigma rules in flight, enrich events, and preserve evidence for investigation and
replay.

## Current status

**Integrated source adapters, checkpointed evaluation and derived search are implemented;
P13 is complete within its owner-accepted bounded scope.**
The transport validates replay envelopes and forwards unchanged bytes or quarantine
references. P08 adds a local OpenSearch metadata writer; qualification status is
recorded in the writer guide. P09 adds a bounded synthetic normalized-fixture
compiler/Java evaluator slice and a separate Flink job, with merged-main AMD64
semantic/recovery CI passed. The owner accepted bounded P09/P10 semantics and
completeness limits on 2026-11-17; see the [review packet](docs/p13-prerequisite-review.md).
P10a adds [source mapping/provenance compatibility](docs/p10-design.md).
[P10b](docs/p10b-design.md) adds source-indexed evaluation and a separate v2 runtime,
merged with ARM64/AMD64 qualification evidence. The owner authorized P11/P12;
formal semantic review history remains recorded separately.
[P11 Windows adapters](docs/windows-adapters.md) are merged with
recorded preservation accounting. A [new controlled recording](docs/p11-recording-review.md)
adds trusted host/capture evidence and eligible offline matching. The owner accepted
its bounded semantics and merged completion #45 as `4ac31fa`; final-head and
merged-main qualification passed. The older public
recordings still lack trusted bindings.
[P12a Linux adapters](docs/p12-runbook.md) are merged and provide offline audit assembly
and selected authentication parsing, with a small real reviewed local OpenSSH9
recording. A selected reviewed local audit capture and independent offline replay/evaluation
are added in [P12c](docs/p12c-ledger.md). PR #43 records completed owner
semantic/completeness review and merge authorization; it is merged as `c024497`.
Merged-main qualification passed in run 43873905332.
[P12b checkpoint qualification](docs/linux-assembly.md) now has an isolated
implementation merged in #42 with final-artifact ARM64 and final-head AMD64
qualification passed. Merged-main qualification also passed; exact evidence and remaining gates
are tracked in its ledger. [P12c](docs/p12c-design.md) adds recorded source
qualification, atomic audit replay and opt-in real audit/authentication checkpoint
recovery and isolated replay. The [P12 acceptance map](docs/p12-acceptance.md)
records completed bounded implementation, qualification, owner review and
authorized integration separately from P13 requirements.
[P13a](docs/p13a-design.md) adds compact evaluation and attributed outputs through
actual offline Windows/Linux consumers; owner-merged #46 and merged-main checks passed.
[P13b](docs/p13b-design.md) adds an isolated Kafka/Flink deployment of those actual
adapters, audit assembly and evaluation, with bounded checkpointed output intents.
[Qualification status](docs/p13b-ledger.md) records exact checks, failures and limits.
[P13c search](docs/search-writer.md) is owner-merged in #48 as `0f6d758`;
final-head native qualification passed, but merged-main integration failed.
[P13d](docs/p13d-design.md) adds opt-in original-recording source-to-search
qualification and [complete milestone acceptance tracking](docs/p13-acceptance.md).
ARM64 original-recording qualification, final-head native checks and actual
merged-main run [44206958555](https://github.com/TravisMa07/DetectBridge/actions/runs/44206958555)
passed. The owner accepted bounded P13 semantics and merged #49 as `07e5382`;
issue #13 is closed. Private recorded AMD64 qualification remains unavailable
within those accepted limits. P14 prerequisites are met; its local
[design](docs/p14-design.md) and [expectations](docs/p14-expectations.md)
precede implementation. [P14a local archive](docs/archive.md) implements exact-byte
storage and independent Kafka offset recovery, owner-merged in #50 as `cd6f46e`;
merged-main run 44232624596 attempt 2 passed after an unchanged retry of a
dependency-download HTTP 429.
[P14b historical replay](docs/historical-replay.md) implements sealed selections,
original-membership execution and isolated resumable output after its separate
expectation freeze 5922901. The owner merged #51 as `943d143`; actual merged-main
run 44326278636 attempt 2 passed on that exact revision.
[Qualification and limits](docs/p14b-ledger.md) retain the earlier failed attempt. [P14c1 current-policy replay](docs/current-replay.md)
adds explicit new-plan evaluation and scheduled regrouping in a separate resumable
local workspace. Its [qualification and acceptance gates](docs/p14c1-ledger.md)
remain separate; native run 44408227593 passed on head `8e4c832`. The final
[P14c2 owning design](docs/p14c2-design.md) starts retention, P05 archive import and
recorded qualification on that stack. Its [managed archive implementation](docs/archive-maintenance.md)
and [milestone evidence map](docs/p14-acceptance.md) record passing local ARM64
fault, approved-original P05 and controlled-recording qualification. Native CI
and owner acceptance remain open.
Management API and UI remain future work;
P14 is not complete.
P06 provides local Kafka/Flink infrastructure and optional authenticated OpenSearch.
Repository hygiene tooling and
contributor templates were introduced in P01; P02 adds reproducible build tools,
P03 adds versioned contracts and validation, and P04 adds selective recorded-data
acquisition. P05 adds isolated, resumable local replay with explicit timing. There are no released
versions or demonstrated throughput claims. The first qualified release target is
`v0.1.0`.

## Accepted direction

- Laptop-first, restartable development on ARM64; Linux AMD64 portability before release.
- Apache Kafka for buffered transport and Java/Apache Flink for stream processing.
- pySigma for parsing/validation, a DetectBridge compiler producing a versioned
  execution plan, and an in-process Java evaluator. Python is outside per-event matching.
- ECS common fields, preserved source evidence, and versioned source contracts.
- Windows and Linux recorded public telemetry first; cloud sources later.
- Python management API, React/TypeScript UI, PostgreSQL, and local OpenSearch.
- Forward all events initially, with preservation-first failure behavior and
  historical/current-rule replay.
- Later milestones: deterministic attack chains, optional local/hosted AI,
  selective forwarding, and distributed deployment.

The initial deployment is not a highly available service. No vendor licensing
caps are planned; finite operational limits are still required.

## Project guide

- [Architecture and accepted decisions](docs/architecture.md)
- [Event/source contract field reference](contracts/v1/README.md)
- [Recorded dataset acquisition](docs/datasets.md)
- [Local replay, timing and recovery](docs/replay.md)
- [Historical archive replay](docs/historical-replay.md)
- [Explicit current-policy archive replay](docs/current-replay.md)
- [Local infrastructure and qualification](docs/local-stack.md)
- [Kafka/Flink replay transport](docs/transport.md)
- [Compiler/evaluator slice](docs/detection.md)
- [OpenSearch metadata writer](docs/writer.md)
- [SDLC and review policy](docs/sdlc.md)
- [Milestones, PR ownership, and acceptance gates](docs/roadmap.md)
- [Release and recovery policy](docs/releases.md)
- [Development and contribution guide](CONTRIBUTING.md)
- [Security reporting](SECURITY.md)
- [Third-party content policy](THIRD_PARTY.md)

## Planned repository layout

| Area | Responsibility |
| --- | --- |
| Applications | Management API and React/TypeScript UI |
| Detection processing | Python compiler, Java evaluator, Flink jobs |
| Contracts | Event, source, execution-plan, and configuration definitions |
| Development tools | Acquisition, replay, benchmarks, verification |
| Deployment | Compose profiles and container definitions |
| Tests and fixtures | Semantic cases, integration scenarios, dataset manifests |
| Documentation | Decisions, roadmap, development guidance, runbooks |

Directories and build tooling will be introduced by their owning PRs rather than
populated with placeholder production services. Python uses `uv`; Java uses the
Gradle Wrapper; TypeScript uses npm lockfiles. Pinned versions and commands are in the [development guide](docs/development.md).

## Independence and licensing

Original code and documentation are licensed under [Apache 2.0](LICENSE).
Dependencies, rules, and datasets keep their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md).
