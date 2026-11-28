# P15b2 lifecycle archive storage and retention freeze

Base `3fe77bb`. Owns the writer, physical reader and retention floor for the
P15b2 profile. [The lifecycle design](p15b-design.md) owns producer semantics;
[the existing managed archive](archive-maintenance.md) owns the legacy profile.
The new Gradle module `lifecycle-archive` builds a separately identified JAR.
Preserve all legacy schema resources, executables, validation and nine-topic
bindings at their existing identities.

## Initialization and physical evidence

`java -jar lifecycle-archive.jar init ROOT MANIFEST OBJECT_DIR` requires a fresh
archive on the same private local filesystem as its temporary publication area.
The UTF-8 JSON manifest has exactly these keys. Duplicate names, fractional
numbers, noncanonical UUIDs, foreign topic IDs and unrecognized fields fail.

| Key | Meaning |
| --- | --- |
| version | Literal `lifecycle-archive/1`. |
| archive_id | Fresh UUID, independent of deployment, worker, source and replay identity. Consumer group is `detectbridge-lifecycle-archive-v1-` plus this UUID. |
| common | Exact public preimage of the existing controller's `runtime_binding`. Keys are version, deployment_id, authority_id, authority_key_sha256, cluster_id, runtime_sha256, producer_sha256, image, compatibility_sha256, limits, validator and topics. The version, limits and validator follow the worker profile. |
| authority_public_key | Standard padded base64 of the authority's DER public key. Its SHA-256 must match common. |
| workers | One through sixteen distinct objects with exactly worker_id (UUID) and input_topic (descriptor). A replacement retains its worker's input topic. Membership/incarnation and per-run assignments come from verified signed commands. |
| objects | One through 128 descriptors with exactly kind and sha256. Kinds are original, provenance, registry, runtime, producer, validator. The registry owns the binding between original object identities and source evidence. Require exactly one runtime, producer, validator and registry plus at least one provenance object. Runtime, producer and validator must equal their respective common hashes and independently selected supported pins. |

Descriptors contain exactly name, id and partition (literal zero); names and IDs
are separately unique over the complete inventory. Common topics have exactly
the four roles control, artifact, ack and output. Archive exactly this set and
one input per listed worker. Register a new archive for a different inventory.
The registry object contains the canonical LocalEvidence version 1.0.0 registration
manifest (no trailing LF). Its objects carry sha256 and size_bytes; check every
registered original's digest and length against retained bytes, the 32 MiB
per-original and 64 MiB aggregate ceilings, and reject duplicate entries. The
synthetic worker registry is explicitly empty. Archive binaries and image IDs are
bound to the [independent artifact pins](p15b2-expectations.md). The reader's
own trusted JAR SHA-256 is supplied independently by the caller.

The public object registry uses filenames equal to lowercase SHA-256 hex and
the supplied bytes must hash to their descriptor. Read bounded regular files
under an explicit root without following symlinks. Copy and verify the complete
catalog before publishing initialized storage. Only public authority/worker key
material is evidence. Never traverse a controller or worker directory to discover
secrets or adopt a candidate-selected executable.

## Durable publication

`drain ROOT BOOTSTRAP` binds the actual broker cluster and topic IDs, confirms
exactly partition zero on each topic, then captures up to observed end positions
with an independent group, disabled auto-commit and verified durable prefixes.
At first use every bound prefix begins at zero. An earliest broker offset ahead
of durable storage, committed position ahead of storage, or durable position
ahead of broker end is a preservation gap. Fail before advancing group offsets.
Revalidate inventory across consumption. Explicit per-partition assignment is
permitted for this single-writer profile; a process lock excludes concurrent
capture of the same archive. The broker remains an evidence source through
recovery. This profile assumes an exclusive archive group for each archive.

Retain the original nullable key/value bytes, headers as an ordered array with
nullable values (including repetitions), physical topic ID, partition, offset,
timestamp and timestamp type. Compression uses gzip NDJSON and metadata binds
the compressed and uncompressed SHA-256, record count, first/next offsets,
archive manifest binding, topic ID and preceding manifest hash. Segment rows
must be ordered inside their half-open interval. Kafka control batches can
advance the position without application rows. Retain that empty interval.
Archive malformed payloads and keep their exact bytes available for inspection.

Write files to an owned sibling staging directory, fsync, atomically publish,
then fsync the parent before committing a durable next position to Kafka.
On interruption scan and verify the contiguous published chain, sync surviving
directories before reconciling offsets, and discard only recognized own partial
staging. Re-read from the durable prefix with the same group. Duplicate physical
delivery cannot manufacture a second occurrence at the same coordinate.
Verify all registered bytes before processing. Keep the archive bounded to
2 GiB, with 128 MiB free reserve, 64 MiB/object, 16 MiB uncompressed/segment,
256 rows/segment and 65,536 total rows. Physical payload ceilings (bytes)
are control/ack 131072, artifact 1048576, input 2162688 and output 4194304.
Cap each encoded row at 8 MiB and headers at 128. Over-limit records leave
visible backlog, with no truncation or advance. Embedded protocol limits for
valid commands, artifacts, inputs and outputs remain those of P15b1.

## Verified reading

`inspect ROOT` verifies archive layout, manifest identity, registered objects,
all segment metadata and wires, then reports durable next positions keyed by
topic name. `export ROOT` performs the same checks and emits UTF-8 NDJSON.
The first line has exactly type=`manifest`, manifest (the initialization value)
and heads (topic name to durable exclusive offset). Every remaining line has
exactly type=`wire`, topic, topic_id, partition, offset, timestamp,
timestamp_type, key, value, headers. The nullable key and value and the nullable
value in each {name,value} header use standard padded base64. Order is topic
name followed by offset. `object ROOT SHA` returns verified registered original
bytes with no framing. Readers use a consistent, locked prefix. Downstream
consumers check process completion, the expected archive binding, head snapshot
and every selection dependency before publishing or evaluating any replay unit.
Never accept an arbitrary edited NDJSON file as a verified archive export.

## Managed retention

The profile binds its graph version to `lifecycle-archive/1`. Physical coordinates
depend on the deployment catalog. Source rows link originals/registry, controls
link their predecessor, membership and bundle, chunks link complete members,
ACKs link their worker/incarnation and command, and output envelopes link
their worker, command, plan, bundle and original membership through the specific
inner document kind. The semantic reader resolves and validates these edges.
Physical preservation can precede semantic resolution. An unknown envelope,
inner extension, signature, missing edge, changed original or unsupported graph
can never establish deletion eligibility.

This first profile uses the existing P15 permanent retention policy for every
recorded occurrence, original and dependency. A bound archive itself is a
permanent hold, so complete retirement, individual segment/object retirement
and active replay releases cannot reclaim bytes. `retire ROOT` checks the
archive and fails with a retention blocker before any filesystem or Kafka
mutation. The additive lifecycle managed-retention entry point delegates to this
verified archive operation and requires a trusted archive JAR hash. Legacy managed catalog/pin/hold commands continue to reject a foreign
archive format. In particular, the legacy full-population exception for unknown
graphs is unavailable for this lifecycle profile. Reclaiming bytes would require
a separately reviewed protocol covering checkpoints, active runs and releases.

Component evidence must cover immutable input inventory, a forged object or
segment, malformed wire retention, post-publication/pre-commit interruption,
independent cuts of known and unknown retained evidence, and original legacy
inventory rejection. Actual Kafka evidence must show the group position and
durable archive prefix separately across interruption and recovery.
