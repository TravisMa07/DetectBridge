# ADR 0003 — Bounded local infrastructure and trusted Docker access

Status: accepted

Owning issue: [P06](https://github.com/TravisMa07/DetectBridge/issues/6).

Refines architecture-register A01, A06 and A07; supersedes no prior ADR.

## Context

P07 needs real local Kafka/Flink infrastructure, with optional searchable storage,
before transport, detection and application consumers exist. Laptop resources and
local credential/persistence handling must be observable and reproducible.

## Alternatives

Starting every future component adds unused resource costs. Publishing Kafka and
Flink would expand access before authenticated management exists. Native volume
size quotas require platform-specific storage provisioning. Disabling OpenSearch
security or using demo credentials would leave an exposed administrative interface.

## Decision

Core runs a single KRaft broker/controller and an idle Flink session cluster; full
adds authenticated TLS OpenSearch. Defer PostgreSQL to its first actual consumer.
Pin multiarchitecture images, enforce memory/CPU/PID bounds and rotate container
logs. Keep Kafka/Flink internal under trusted Docker administration. Publish only
loopback OpenSearch with independently generated credentials and a private CA.
Docker Desktop cannot publish internal-only container ports, so OpenSearch alone
also joins a project-scoped access bridge. Kafka/Flink stay exclusively internal;
OpenSearch egress is not blocked by this additional bridge.

Use project-scoped volumes and ignored immutable initialization metadata. Preserve
Kafka cluster identity and TLS material across recreation. Fail on missing metadata
or changed credentials beside data. Disk preflight/status checks do not claim hard
quotas; automatic telemetry expiration remains disabled. See the
[local stack guide](../local-stack.md) for interfaces and exact resource defaults.

The approved OpenSearch image lacks OpenSSL. Use its bundled keytool to generate
CA-signed PKCS#12 stores, preserving the intended TLS trust model without another
image or host dependency. Flink uses UID 9999 and Kafka/OpenSearch UID 1000, verified
from the pinned images rather than assuming all images share one identity.

## Consequences

This is a trusted single-host development environment, not high availability or
network isolation from the Docker administrator. Persistent shared Flink files do
not prove job recovery. Disk pressure still needs an operator until P16 implements
continuous admission policy. Certificate rotation, image upgrades and backups need
reviewed maintenance; initialization never silently replaces identity beside data.

## Validation

Offline policy/negative cases and fail-closed CI classification accompany actual
ARM64/AMD64 readiness, resource inspection, authentication and recreation/persistence
qualification. Synthetic evidence stays isolated from development resources.

## Revisit conditions

Revisit for exposed clients, P07 transport, P14 archives, P16 disk-pressure policy,
certificate renewal, distributed storage or deployment beyond one trusted Docker
host. Record image/data compatibility before changing persisted installations.
