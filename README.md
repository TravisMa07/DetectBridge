# DetectBridge

DetectBridge is a personal, self-hosted detection-engineering project intended to
sit between log collectors and a SIEM. It aims to normalize telemetry, evaluate
Sigma rules in flight, enrich events, and preserve evidence for investigation and
replay.

## Current status

**Local replay and checkpointed Kafka/Flink transport implemented; detection is pending.**
The transport validates replay envelopes and forwards unchanged bytes or quarantine
references. No detector, management API, UI or OpenSearch writer is implemented.
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
- [Local infrastructure and qualification](docs/local-stack.md)
- [Kafka/Flink replay transport](docs/transport.md)
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
