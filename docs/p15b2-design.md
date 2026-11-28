# P15b2 lifecycle archive and replay

P15 issue [#15](https://github.com/TravisMa07/DetectBridge/issues/15) owns this
profile. The source base is 3fe77bbf570e59521633a218288f2144e2159113.
[Storage and retention](p15b2-storage.md), [replay](p15b2-replay.md) and the
[independent matrix](p15b2-expectations.md) specify the observable boundary.
The implementation owners are the archive writer, replay controller and primary
integrator (graph verification, deployment manifest, qualification and CI).
The expectation reviewer owns the literals.

## Dependency graph version 1

The trusted operator supplies a public deployment manifest and the expected
archive identity. Its common binding uses the complete canonical B1 preimage,
including the four shared topics, authority fingerprint, producer, runtime,
validator descriptor, cluster, Flink image, compatibility and worker limits.
Each additional inventory entry binds one stable worker to a distinct input
name and Kafka topic ID. The immutable archive instance covers that inventory
from offset zero. Expansion requires a new complete inventory. Persist only the
public verification keys. Record each execution image ID and platform in the
qualification report.

The physical archive accepts opaque bytes. Semantic verification uses closed
B1 control, artifact, ack and output schemas, the original v1 integration inputs,
P13 v1.1 decisions and the corresponding receipt, quarantine, preservation and
Linux manifest schemas. Unknown structure blocks semantic use and retirement.
Never infer dependencies from a topic suffix. Inventory and physical positions
identify the source role. Read and verify the complete bounded export before
producing a result. Limit semantic selection to 4,096 wires and 64 MiB of wire
data per verified snapshot. A larger capture remains physical evidence.

Verify Ed25519 over the original B1 domain and canonical payload. Start at
effective revision one. Require a contiguous predecessor chain, proposal hash,
authority/deployment binding, exact sorted participant snapshot, stable run
ownership and registered input identities. Verify artifact signatures and exact
transfer metadata, assemble both members using 256 KiB chunks and compare their
hashes and manifest to the independently reconstructed P15a bundle. Recompile
each executable plan against its embedded YAML with the pinned compiler packet.
S12 must reject even when the authority authenticated the inconsistent AST.
Verify ACKs against the registration at their effective revision, including the
logical ACK ID and checkpoint fields. Duplicate physical records retain all
locations. Reject logical conflicts.

Each output references its specific effective command, signed registration,
original incarnation, bundle and exact plan. Verify its B1 logical ID, inner key,
document and semantic digests. Resolve every receipt to its physical admission
and bind each selected event to the archived inputs and original membership.
Control and ACK signatures authenticate their payloads. The B1 output envelope
has integrity hashes and an origin claim on the bound Kafka topic. Preserve this
trust boundary when reporting attribution. Replay publishes only in its private
workspace. New executables bind their measured hashes at archive creation or
run creation and verify them on reopening. The accepted old artifact hashes and
qualification fixture pins are listed in the matrix.

## Qualification and acceptance

Run behavioral failures before fixes. Preserve each original run locally with
source, artifact, image, initial offsets, recovery and semantic observations.
Exercise the actual two-worker production A/B/A deployment, independently
consume Kafka into the new backend, restart across the durable publication
boundary, verify source byte equality and compare replay to the frozen matrix
on ARM64 and native AMD64. Select the dependent archive, maintenance, replay,
activation and integration gates and require their applicable successes.
P14's bounded acceptance and P16's remaining combined preservation work stand.
