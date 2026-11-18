# P14a durable archive implementation freeze

Status: pre-implementation freeze, 2026-11-18 UTC, base 07e5382. Owner: primary
agent, branch `feat/p14a-durable-archive`, issue #14. Preserves A02–A07 and the
[milestone design](p14-design.md). Historical/current execution remains P14b/c.
No archive implementation existed when these contracts/vectors were authored.
The freeze is e9b6143. Subsequent implementation/evidence is in the
[ledger](p14-ledger.md); original pre-code expectations below remain authoritative.

## Concrete scope and contracts

Add a Java `archive-writer` module with a local archive interface, Kafka consumer
and command entrypoint. Python tooling builds/packages and launches the exact JAR
in an isolated, bounded container on the existing private P13 Kafka network.
No archive filesystem is mounted into a producer and no source state changes.
Commands: init, run/drain, inspect, object retrieval and wire retrieval. Explicit
starting offset JSON is required for every one of the nine topics. Init reads
actual cluster/topic IDs, requires one partition per topic, freezes starts, a new
UUID-scoped group, the exact JAR hash, limits and explicit object/provenance hashes.
No remote URI fetch, reset, implicit earliest, deletion or production replay.

[Archive schemas](../contracts/archive/v1/configuration.schema.json) are closed
1.0.0 definitions for configuration, wire, chunk, object and segment. Every schema
is validated offline and by production Java readers. All integer validation is
lossless and rejects floats/booleans; opaque source bytes are never reserialized.
Canonical metadata has sorted keys, compact UTF-8, unchanged arrays and no LF.
Metadata files contain those canonical bytes followed by one LF. Their canonical
SHA-256 is the chain identity; exact file hashes remain separately inspectable.
The [literal vectors](../contracts/archive/v1/fixtures/vectors.json) were computed
by the independent system shasum command before implementation.

Root owns `archive.json`, `.lock`, `objects`, `segments` and advisory
`progress.json`. Creation uses a sibling staging directory and parent sync;
interrupted initial creation is not a resumable initialized archive. Object and
segment layout/framing follow the milestone design. Schema `payload` holds both
compressed/uncompressed hashes/lengths and row counts. `previous` chains segment
metadata hashes; `first` equals prior `next` or frozen start. Record offsets are
strictly increasing within `[first,next)`; broker position proves legitimate gaps.
Same-location retries must match the exact stored wire record. Distinct physical
locations stay distinct even with identical values. No global content deduplication.

Every source input retains its original raw/context and inline bytes in the exact
wire value. Reference evidence must resolve to a frozen registered original whose
whole hash and selected range/hash verify before offset progress. Registration
also retains the explicitly supplied provenance/terms objects; provenance hashes
must be a nonempty subset of registered objects. Classification cannot establish
human authenticity of a supplied provenance object. Original source/host/boot
bindings are never inferred or changed. Each segment retains the entire frozen
object/provenance dependency set; this intentionally bounds dependency selection
and avoids claiming historical dependency closure. P14b seals processing artifacts
and membership later. A repeated raw record/run with changed raw or receipt-free
context at a distinct wire location is retained as `semantic_conflict` by scanning
verified prior source admissions. Missing objects stop with unchanged offsets;
malformed input can be archived exactly as `invalid_source` or opaque bytes.

## Bounds and publication

Default limits: 2 GiB managed bytes, 128 MiB free reserve, 32 MiB object,
16 MiB uncompressed segment and 256 rows; configuration may lower positive bounds
for fault qualification. Fixed wire row cap 4 MiB, value cap 2 MiB, 128 headers,
metadata cap 1 MiB, gzip segment cap 17 MiB, object cap 48 MiB. Object chunks
are at most 1 MiB decoded. Exactly one gzip member, level 6, mtime zero, no optional
header fields; validate footer CRC/size, all hashes, strict NDJSON and decoded
bounds before returning verified content. No shared/network filesystem support.

Hold a process lock across writer lifetime. Preflight the full conservative
transaction footprint, including existing partial/orphan files and external free
space. Finish gzip, fsync payload, metadata and staging directory, rename to an
absent destination, sync parent; new directories sync their parents too. Only then
commit the broker next offset. Errors never delete/replace committed content.
The authoritative scan verifies committed objects, bindings and per-topic chains;
progress JSON is advisory. Unknown files and symlinks reject adoption. Clean only
owned, structurally safe partial directories under the writer lock.

Kafka auto-commit is disabled; group is frozen and root-exclusive. Subscription
assignment seeks the verified durable prefix after validating committed offsets:
ahead is a gap failure, behind is reconcilable durable replay. Assignment changes
invalidate unresolved commit attempts. Every precommit checks cluster/topic IDs
and assignment; commit failures leave durable data for the next reconciliation.
No unbounded retry buffer: stop nonzero with value-free status on unresolved error;
operator restart probes the same binding. This refines the milestone's proposed
five-fast-retry daemon policy into an explicit bounded command/restart interface.
Drain snapshots finite end offsets; completion means archived through that vector,
not complete evaluation or historical replay readiness. Status reports durable,
broker, earliest/end/lag, archive bytes and category without raw values.

P05 import is deferred to a later bounded archive interoperability slice before
full P14 acceptance. P14a preserves P05 readers/contracts unchanged; it does not
claim importing local P05 segments. This decomposition avoids mixing a second
producer protocol into the Kafka durability PR. No P14 milestone completion claim.

## Independent expectations and qualification gate

The [milestone matrix](p14-expectations.md) B01–B11, D01–D15, I01–I03,
L01–L05 and Q01/Q03 apply, with D06 exercising actual assignment/commit failure.
A01: independent eight-byte vector retrieves exact ranges 0:3,3:1,4:3,7:1.
A02: literal identity/canonical hashes match system shasum vectors, including
signed-64-bit endpoints, Unicode and twelve-digit timestamp text.
A03: exact bytes/nulls/headers at distinct Kafka offsets retrieve independently;
changed same-offset content must fail without overwrite.
A04: injected process termination at payload, metadata, before-rename,
after-rename, after-directory-sync and after-Kafka-commit boundaries preserves
original data and leaves no committed offset ahead of durable coverage.
A05: real Kafka outages and group reassignment cannot commit unresolved input.
A06: actual ENOSPC/permission/sync failures or controlled filesystem fault hooks
retain uncommitted backlog; report injected operation precisely, without claiming
physical disk-full or power-loss from model tests.
A07: truncated/corrupt/concatenated gzip, changed metadata, missing objects,
invalid schema and paths reject retrieval/resume before accepted progress.
A08: root byte/reserve/row/count/decompression bounds reject at their exact edge;
there is no truncation, automatic deletion or passing placeholder CI.
A09: all nine topic watermarks remain separate; delayed processing output does
not prevent input durability and never implies replay readiness.

Before implementation, commit this owning design, schemas and independent
vectors separately. Demonstrate focused behavioral reds, implement, run actual
Kafka/filesystem fault qualification serially and regression checks for existing
consumers. Record exact source/JAR/container/plan/platform, failures and unavailable
coverage in the ledger. Native CI is synthetic; private originals stay local and
P14b/c recorded replay qualification is separate. Owner acceptance and explicit
merge authorization remain required after a concrete implementation/evidence PR.

## Implementation refinements

The consumer polls at most four records, within the proposed sixteen-record upper
bound, to keep the complete bounded wire working window at most 16 MiB. Broker
identities are checked after polling before publication and again before offset
commit. Restart verifies and syncs surviving committed directories before adopting
them. Partial cleanup recognizes only bounded object, segment or progress staging
contents; unknown staged evidence is retained and blocks. Source byte-range offsets
must fit signed 64-bit before conversion. These are requirement-preserving routine
refinements; no expectation was changed to match evaluator/archive observations.

Classification marks recognizable source admission shapes and verifies referenced
bytes; it does not independently certify host trust, context semantics, parser
support or historical readiness. Original contexts/quality remain exact wire data.
Prometheus CLI metrics use fixed topic labels. Helper failure reports retain original
exit/stdout/stderr privately; routine output exposes fixed categories and exception
class names without messages. Production and qualification JAR hashes plus pinned
image and loaded tool hashes are attributed per run, never via a mutable pointer.

## Metadata integrity regression

Frozen D09 requires corruption of counts, lengths or intervals to reject adoption.
A focused regression demonstrated that changing the last segment's `next` field
could evade the predecessor chain, because no successor yet referenced that last
metadata hash. The separate file-byte checksum promised above was missing. The
corrected layout requires `archive.sha256`, `object.sha256` and `segment.sha256`
sidecars, each the SHA-256 of the exact corresponding JSON file bytes (including
its final LF), followed by LF. Verify these before parsing/adopting metadata;
write/fsync them before staging-directory publication. This fulfills the original
checksum expectation without changing schema fields, identities or their canonical
hash preimages. Unknown/missing sidecars reject adoption; unpublished intermediate
layouts are not automatically migrated. The failing regression and original local
logs are retained in the ledger; no frozen expectation was weakened.

Broker positions that advance solely over control batches are retained as explicit
empty observed intervals with zero wire rows. The next offset is attested by the
consumer position; no source record is invented. Unit restart and actual four-record
transaction/control-batch qualification cover that bounded Kafka behavior. P13's
production at-least-once sink and acknowledgement policy remain unchanged.
