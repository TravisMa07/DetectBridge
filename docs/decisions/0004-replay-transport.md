# ADR 0004 — Acknowledged replay transport and checkpointed validation

Status: accepted

Owning issue: [P07](https://github.com/TravisMa07/DetectBridge/issues/7).

Refines A02, A06 and A07; preserves P03/P05 contract definitions.

## Context

The local stack must now carry evidence through Kafka/Flink before parsing,
detection and searchable derived storage are implemented. Publication progress,
evidence identity, checkpoint recovery and downstream success are distinct.

## Alternatives

Transactional Kafka sinks can suppress recovery duplicates but add transaction
lifecycle/visibility policy and do not solve publisher acknowledgment ambiguity.
Live publication from active P05 runs couples two commit boundaries. Opaque relay
would allow direct malformed Kafka input to bypass producer validation. Copied
quarantine payloads duplicate sensitive evidence and require larger messages.

## Decision

Publish only verified completed runs, with independent atomic acknowledgment
receipts and frozen destinations/rates. Inherit replay pacing unless explicitly
overridden. Use Java Kafka helpers inside the private Docker network, avoiding
host broker exposure and Python Kafka dependencies.

Use one partition per topic and a validating Java Flink relay with at-least-once
sinks, stable operator IDs and shared filesystem checkpoints. Preserve valid
key/value bytes and raw evidence identities. Quarantine malformed input using
Kafka location, topic/cluster identity and checksum; retain the referenced input.
Keep control markers as input exhaustion, not processing-completion assertions.

Use bounded task retries; require explicit JobManager checkpoint restoration.
Missing/incompatible state never silently becomes an earliest reread; that action
requires an explicit flag. The [transport guide](../transport.md) defines commands,
limits, topic policies, instrumentation and the acknowledgment boundary.

## Consequences

Retries and recovery may duplicate logical envelopes. Consumers and qualification
must account for identities and hashes, not merely count physical records. Acks
on a single broker are not disk-failure protection. Quarantine needs retained
input until a later archive implementation supplies an independent reference.
One partition and local state deliberately limit scaling and availability.

## Validation

Shared independent semantic cases, strict Java dependency verification, synthetic
fault qualification, native ARM64/AMD64 integration and separate opt-in recorded
qualification accompany the implementation. No detection behavior is claimed.

## Revisit conditions

Revisit for live ingestion, additional partitions, transactional output, exposed
clients, source assembly, P14 archival retention or distributed/HA deployment.
Changing state serializers, schema support, topic identities or bundle contents
requires explicit compatibility review and applicable recovery qualification.
