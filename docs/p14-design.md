# P14 archive and historical/current replay design

Status: milestone proposal authored before implementation, 2026-11-18 UTC.
P14a concrete schemas/vectors were frozen in e9b6143 before local implementation;
see [owning freeze](p14a-design.md) and [actual evidence](p14-ledger.md).
P14b/c and owner milestone acceptance remain pending.
Owner: current primary agent; issue [#14](https://github.com/TravisMa07/DetectBridge/issues/14).
Base: qualified `07e53822dd8a5035125804321e5c852f9a466aef`;
branch `feat/p14a-durable-archive`. [Independent expectations](p14-expectations.md)
are authored from requirements and existing contracts before archive code.
The [ledger](p14-ledger.md) separates readiness, design and later evidence.

## Scope and delivery gates

Preserve A02–A07, P03 identity/time, ADR 0002 local replay, ADR 0004 transport,
ADR 0008 independent search and all P12/P13 source/quality semantics. Implement
compressed NDJSON evidence segments behind a narrow local archive interface.
Kafka acknowledgement, archive durability, processing completion and indexing
remain separate facts. Local disk is neither replicated storage nor protection
against disk loss. No activation, management API/UI, selective forwarding, HA,
shared filesystem, throughput or release work belongs here.

Use bounded PRs, each normally containing its separate design/expectation freeze,
one implementation/regression/docs commit and consolidated qualification evidence
if needed. This document is a milestone design; the first implementation slice
must also freeze its actual schemas and literal vectors before production code.
Later slices freeze their concrete interfaces before their own implementation.
Do not treat one slice as complete P14.

| Slice | Bounded deliverable | Required before advancing |
| --- | --- | --- |
| P14a | Local archive interface, byte/object storage, Kafka archival consumer, recovery, retrieval and progress | Concrete archive schemas/vectors frozen; meaningful fault regressions and actual Kafka/filesystem recovery; applicable legacy compatibility; owner review, authorized merge and merged checks |
| P14b | Sealed replay selection, artifact pins and original-membership historical execution | P14a qualified merged base; concrete replay schemas and independent semantic expectations frozen; actual parser/evaluator reproduction and failure/isolation qualification |
| P14c | Explicit current-policy reprocessing, resumable isolated output and retention/deletion coordination | P14b qualified merged base; current-policy/budget/deletion cases frozen; actual faults, recorded reuse, compatibility and milestone acceptance map |

Routine numerical/wire choices proposed below are owning-design decisions. They
do not amend accepted architecture. A requirement to alter P13 persisted state,
production topics/output identities, acceptance policy, or historical evidence
semantics requires renewed compatibility review; consequential architecture
changes require owner discussion and an ADR before implementation.

## Inspected baseline and compatibility

`tools/replay.py` retains original ranges and fsyncs renamed segment directories;
its checkpoint is advisory and its digest includes the serialized final LF.
`tools/replay_time.py` uses exact integer nanoseconds for P05's zero-to-nine-digit
timing domain. P14 must not use that narrower parser to rewrite source timestamps
whose existing contracts preserve greater precision.

`tools/integration.py` registers exact SHA-named objects (128 files, 32 MiB each,
64 MiB total), and defines input plus seven independent output topics.
`Machine.java` prepares adapters/evaluation before committing state and all output
intents; completed checkpoint prefixes release at-least-once outputs. Its receipts
refer to physical inputs. `Assembler.java` records ordered original members,
closure/findings, source/mapping hashes and host/generation scope; late evidence
references the original immutable manifest. Clocks affect when groups close.
Neither a run-end marker nor an input receipt proves all outputs have arrived.

`tools/search_writer_recorded.py` preflights originals/contexts and freezes source
expectations before admission; its controlled late cursor is separate from the
original population. `tools/integration_oracle.py` removes only explicitly listed
receipt clocks for semantic comparison. P13c search retains retrieval links but
omits original fields. The P13-only `DetectBridgeKafkaSink` guard is private-API
pinned and stays scoped to P13; P14's independent consumer does not copy it.

P14a adds a separate Java consumer and Python lifecycle CLI using existing pinned
Kafka/JSON dependencies and an explicit archive group. A new real CI gate exists
only with implemented tests/runtime, never a documentation placeholder. P03/P05,
P08's two indices/role, P12 deployment/state, P13 output profiles and P13c's three
indices/role remain unchanged. New archive formats start at 1.0.0 with explicit
reader support; no automatic migration or adoption of an old checkpoint.

## Authoritative data and narrow interface

The archive owns exact Kafka key/value bytes including null-versus-empty, ordered
headers including repetitions, timestamp/type and cluster/topic UUID, topic name,
partition and offset. Base64 represents bytes inside NDJSON; JSON parsing never
replaces those originals. Archive P13 input and all seven outputs plus the P13c
writer-failure topic. Explicit import supports completed P05 runs plus their
verified manifests/index/capture/provenance objects; it does not fabricate P13
adapter contexts for P05 inputs without trusted bindings.

For valid source admissions also retain original raw/context documents, original
evidence objects/ranges and applicable catalog/usage/capture/host/boot provenance.
Retain native manifests and late-link preservation unchanged, including incomplete
groups and manifests with no emitted event. Derived tagged/detection/diagnostic
and search data never substitute for original input. Malformed Kafka bytes are
archivable without interpreting them as source events.

Proposed interface, independent of Kafka and local paths:

| Operation | Observable contract |
| --- | --- |
| `putObject(expectedHash, length, stream)` | Bound and verify original bytes; publish immutably; identical bytes verify existing object; mismatch stops without overwrite |
| `commitSegment(binding, partition, first, next, rows, dependencies)` | Persist one contiguous observed Kafka interval, exact bytes and required dependencies; return a verified durable receipt only after publication sync |
| `readSegment(id)` / `readObject(hash, range)` | Verify compressed framing, original digests and bounds before returning verified data; no URI/network resolution |
| `progress(binding)` | Per-topic/partition durable next offset, broker committed next offset, observed end, lag, earliest retained offset, blocked category and dependency status |
| `sealSelection(selection, dependencies)` | P14b validates a finite immutable dependency closure and publishes a replay pin; archival offsets alone cannot imply replay readiness |

Bindings pin archive UUID, format, implementation artifact, root ownership, Kafka
cluster/topic UUIDs, group, partition set, starting offsets, object registrations
and limits. Initial scope is P13's single-partition topics and one exclusive local
writer. Replaced topics/broker/group, root symlink, unknown files or incompatible
bindings fail before consumption; no implicit earliest reset. Reading an existing
archive is format-bound; resuming its writer is also implementation-bound.

## Layout, framing and integrity

All files are ignored under an explicitly owned local archive root. Local paths
come from the configured root and validated identifiers, never evidence URIs.
Reject symlinks, traversal and nonregular object files. Hold an exclusive process
lock for mutations; readers use committed immutable directories only.

```text
archive.json + archive.sha256        immutable root binding/version/limits
objects/<original-sha256>/
  bytes.ndjson.gz + object.json       original byte chunks and commit metadata
  object.sha256                       exact metadata-file checksum
segments/<topic-uuid>/<partition>/<first-offset>/
  records.ndjson.gz + segment.json    exact wire rows and commit metadata
  segment.sha256                      exact metadata-file checksum
pins/<selection-sha256>.json          P14b immutable dependency selection
progress.json                        advisory, rebuilt from committed segments
.partial-<random>/                    unpublished owned transactions
```

P14b's [owning freeze](p14b-design.md) refines the provisional `pins/` placement
to a separate explicit replay catalog. Existing P14a roots reject unknown entries;
adding pins inside them would prevent their exact pinned writer from resuming.
P14c deletion must require and coordinate that catalog rather than infer no holds
from an absent in-root pin directory. No deletion exists yet.

Each object stream contains ordered contiguous base64 chunks (up to 1 MiB decoded
per chunk) with zero-based byte offsets. Decoding concatenates exactly to the
original object. Each segment stream contains bounded UTF-8 JSON rows, one LF per
row, escaped newlines within strings and no blank framing rows. Use one gzip
member, fixed level 6, mtime 0 and no filename/comment; reject trailing bytes,
multiple members, truncated footer, bad CRC, invalid UTF-8, duplicate JSON keys,
trailing JSON tokens, missing final LF and unknown versions/fields.

Commit metadata records exact schema/codec versions, compressed and uncompressed
SHA-256/lengths, row/chunk counts, original-object SHA-256/length or Kafka interval,
binding hash, ordered dependencies and previous segment hash. Metadata identity
is SHA-256 of canonical UTF-8 JSON without its own hash: recursively sorted keys,
compact separators, unchanged arrays, integer values, no final LF. This differs
explicitly from P05's serialized-file digest. A separate file-byte hash verifies
metadata transfer. Reject floats for integer contract fields and preserve full
signed-64-bit values; opaque originals retain their exact spelling and precision.

Validate stream lengths while decompressing, not after unbounded allocation.
Object range retrieval verifies the full original-object digest plus the requested
record digest and offset/length. Zero-length objects are representable; P03's
positive-length reference ranges remain unchanged. An empty LF record is one
original LF byte; an empty file has no records. No newline conversion, Unicode
normalization, XML reserialization or timestamp rounding is permitted.

## Durability and offset recovery

For each partition, record exact poll-order locations and a contiguous observed
interval `[first,next)`. Do not infer numeric offset adjacency where Kafka has
legitimate gaps; record every returned location and validate the broker's next
position. An offset below the broker's earliest retained offset without archived
coverage is an explicit preservation gap, never successful catch-up.

1. Verify required evidence/provenance dependency bytes. Publish each object in a
   private same-filesystem directory: finish gzip, flush/fsync payload, write and
   fsync metadata, fsync that directory, rename without replacing a committed
   destination, then fsync its parent. Existing content must fully verify.
2. Build the segment with references to those verified durable objects. Finish,
   flush/fsync payload and metadata, fsync the staging directory, rename without
   overwrite into its final partition location, fsync the parent directory.
3. Only after that durability boundary may the consumer commit `next` to Kafka.
   Persist advisory progress afterward. Auto-commit is disabled. Rebalance,
   shutdown or any publication/sync failure cannot advance unresolved offsets.

New parent directories also require parent sync before being relied on. No
cross-filesystem rename or platform with unqualified rename/lock/fsync semantics
is supported. These operations assume a filesystem/device honoring successful
sync, and cannot prove physical power-loss resilience from process-kill tests.

Crash before publication leaves Kafka progress unchanged; remove only verified
owned partial directories after taking the lock. Crash after rename but before
parent sync cannot have an acknowledged Kafka commit; inspect the surviving
directory, fully verify and sync it before adopting. Crash after publication but
before Kafka commit reuses the committed prefix after verification. Crash after
Kafka commit but before advisory update reconstructs the same durable progress.
Unreferenced durable objects are safe orphans, counted against budgets.

On restart verify metadata/hash chains, every required object and the durable
partition prefix. If Kafka committed progress is behind, seek/reconcile the
verified durable prefix and commit it; a repeated same-location read must match
exact original bytes/headers. If Kafka progress is ahead of durable coverage,
stop with a preservation-gap category, even if bytes remain in Kafka. Repair is
explicit and reviewed, never a silent reset. Corrupt committed data stops; do not
delete or rewrite it to make recovery pass. A failed Kafka commit is retried only
after confirming current assignment and immutable binding.

## Identity, conflicts and failure accounting

Wire occurrence identity is the canonical array of domain
`detectbridge.archive.wire/1`, cluster UUID, topic UUID, decimal partition and
decimal offset. Two offsets with identical bytes are two occurrences. A retry at
the same location must have identical wire content; changed content is an
integrity conflict and blocks. P03 record/event IDs and P13 IDs stay unchanged.
No unbounded in-memory global dedup map is needed: segment intervals and bounded
on-disk verified lookup establish archival identity.

Same P03 occurrence with changed raw/context remains archived at its distinct
wire location, with a visible semantic-conflict finding; it cannot overwrite the
first occurrence or be silently selected for replay. Malformed/unsupported source
admissions retain exact bytes plus a value-free classification. Valid references
whose required original objects are missing remain backlog, without offset
commit; integrity mismatch blocks. Disk, permissions, transient I/O and unknown
failures never become permanent quarantine simply to advance offsets.

Any durable quarantine must contain the original bytes (or a verified archive
object reference), location and fixed failure category, and share the same sync
boundary. A Kafka-only quarantine reference is insufficient for independent
archive durability. Every accepted input remains durable output, durable
quarantine or visible retained backlog. Source-quality distinctions are retained
as source metadata, not relabeled archive corruption or evaluator nonmatches.

## Historical replay selection and execution — P14b

Freeze an explicit finite selection, never a search query or mutable active
configuration. It records original run/source scopes, exact topic intervals and
wire hashes, member order, original manifests/full and semantic hashes, late
associations, controls, original contexts/receipts and required artifact hashes.
Selection sealing verifies all referenced members, original objects, source/host/
generation bindings, provenance/usage terms and expected output references.
Missing output/membership means `pending_dependencies`, not replay ready.

Pin original source/mapping snapshots, rules and provenance, exact compiled plan,
parser/normalizer/assembler/completeness-policy/evaluator/selector/enrichment
versions and executable artifact hashes. Preserve actual external enrichment
inputs; P13's accepted profile is explicitly empty. Pin the execution environment
and supported artifact adapter, without downloading or executing arbitrary code
from a manifest. A matching version string without matching bytes is insufficient.
Missing/incompatible artifacts fail preflight before output. P14b must freeze its
supported executable/profile list and concrete vectors before code; unsupported
historical artifacts fail explicitly, rather than claiming universal reproduction.

Historical execution reparses original bytes using pinned source code and contexts
and evaluates with pinned policies. For audit, consume the exact frozen manifest
members, order, closure and findings through a separately tested explicit-member
adapter path; do not use the live timeout/EOE grouping loop to guess original
membership. Check reparsed group keys and assessed quality against the original
manifest. Late rows remain linked preservation and are excluded from its members.
Standalone Windows/authentication inputs retain original quality and missing
identity. A manifest without an event remains preserved without fabrication.
Reproduction compares independently expected normalized fields, memberships,
quality, six counts, matched revisions and attribution, not copied stored results.

Each execution has a fresh replay UUID and separate outputs. Preserve immutable
original manifests/IDs in origin links; a derived replay view changes only its
explicit run-scoped fields and corresponding hashes. Original event/evidence IDs
remain stable for identical membership. Processing/detection/diagnostic identities
use the actual replay run and pinned attribution, with origin links in a separate
archive-replay wrapper. Never impersonate the original runtime run or claim byte
identity across receipt/run fields. No new pipeline string is sent to the closed
P13 1.1.0 schema without a supported versioned profile. Initially output stays in
exclusive local replay segments; routing into search requires its own compatible
consumer contract and qualification.

## Current-policy reprocessing and resume — P14c

Require explicit source selection, new mapped bundle, parser/assembler/source
profiles, enrichment policy/inputs, deterministic admission order, timing/closure
policy, resource limits and fresh run UUID. No implicit active bundle, timer or
checkpoint is adopted. Preserve original first-observation and occurrence strings;
new receipt/processing clocks are separate. Unknown historical host bindings
remain unknown. New trusted bindings, if ever supplied, require explicit provenance
and a separate reviewed transformation, not automatic identity repair.

Current grouping may include selected late members and produce a new event ID;
retain links from every new member/result to original wire/manifest/late links.
Define deterministic offline admission/tick/control schedules in the P14c freeze;
reusing old processing-time arrival gaps is never promised to reproduce grouping.
Changing membership or policy can legitimately change outcomes, while historical
evidence and outputs stay immutable.

Freeze selection/artifacts/mode/budgets/output profile before replay output.
Resume verifies all committed local output segments and durable transition state,
with a hash binding to that frozen specification. Publish state and output intents
atomically together; never advance the source cursor before the matching output
is durable. Completed output derives from verified segments, not an advisory
checkpoint. Changed mode, run, policy, selection, artifact, limit or destination
fails resume; operator starts a new run. P05 and P12/P13 checkpoints are not adopted.

## Finite budgets, retention and progress

Proposed initial limits are serialized/storage bounds, not measured capacity.
All values are frozen per archive; tests exercise exact boundaries and overflow.

| Resource | Bound/policy |
| --- | --- |
| Archive managed files, including objects, partials, metadata, pins and replay output | 2 GiB; stop before exceeding it, including conservative next-transaction reservation |
| Required free filesystem reserve | 128 MiB after the next worst-case transaction; failure to reserve stops admission |
| Individual registered original/artifact object | 32 MiB; larger executable/container artifacts remain explicit externally retained hash pins with verified availability, not silently copied |
| Original registration batch | Existing 128 objects / 64 MiB; larger retained collections use bounded sequential object operations |
| Wire row / original Kafka value | 4 MiB serialized / 2 MiB decoded; keys/headers count in the row bound |
| Segment | At most 256 rows and 16 MiB uncompressed; compressed cap 17 MiB; oversized row stays visible backlog |
| Object chunks / compressed object | 1 MiB decoded chunks / 48 MiB compressed; bounded total decoded original length |
| Consumer poll and working window | 16 records and 16 MiB serialized; stop polling while the pending transaction is unresolved |
| Segment metadata / selection | 1 MiB / 16 MiB; larger dependency closures require an explicit later format revision |
| Replay selection / active runs | 100,000 wire occurrences / one mutating run per root |
| Retry | Five immediate bounded retries, then 30-second probes or stopped status; no source-body logging |
| Time-based retention | No automatic expiry; explicit reviewed deletion with dependency checks; byte cap still stops admission |

Reserve compressed worst-case lengths and metadata before each object/segment
transaction; do not assume compression will save space. Count orphans/partials and
externally consumed disk space; ENOSPC after preflight remains a possible failure
and cannot advance offsets. Bounded streaming verification/index lookup avoids
loading the whole archive. Dependency indexes are rebuildable from authoritative
commits; all index/cache bytes count toward the cap.

Expose per-partition durable and broker watermarks, observed end/earliest, byte/
record lag, dependency readiness, archive bytes/reserve and blocked reason.
Cross-topic archival progress is a vector, not a claim of atomic processing
completion. A replay pin names the exact cross-topic closure explicitly.
No automatic Kafka retention reduction or deletion is introduced by P14a.

P14c deletion is an explicit two-phase operation under the root mutation lock:
freeze a bounded deletion plan/hash, verify age/selection and no replay pins,
active readers, quarantine references, manifests/late links or externally declared
retention holds, then durably publish a retirement record before deleting owned
files and syncing parents. Replay readers hold a retention lease under the same
coordination. Restart finishes the exact retirement plan; never delete a prefix
needed to verify retained chain anchors. Freeze anchor/tombstone schemas and
crash cases before implementation. Shared objects are deleted only when no
retained segment/pin refers to them. Advancing the archive floor is visible;
retrieval below it returns explicit retired status, not not-found ambiguity.

Kafka deletion additionally requires every relevant consumer's progress and all
original/quarantine/rebuild dependencies to be independently safe. P14 supplies
the archive watermarks and blockers; P16 owns broader coordination, finite-outage
qualification and operational policy. P14 never treats its own watermark as
permission to discard evidence needed by another consumer. Operator deletion of
the only evidence copy ends preservation deliberately and must be recorded.

## Verification and remaining freeze work

The [matrix](p14-expectations.md) supplies requirement-derived positive, negative,
boundary and fault expectations. Before P14a code, commit its concrete schemas,
canonical identity/hash vectors and exact synthetic wire/object fixtures, including
byte literal expectations computed without the new implementation. Preserve the
freeze as a distinct commit. No evaluator/archiver output generates the oracle.

P14a requires actual filesystem process-interruption and Kafka commit/rebalance/
outage qualification; P14b/c require actual pinned parser/Java evaluator execution,
original-member replay and output/state isolation faults. Public CI uses original
synthetic fixtures with provenance; accepted private originals remain local opt-in.
Revalidate all catalog hashes/terms/source bindings before reuse; never recapture
or upload private originals. Record exact source/artifact/plan/image/platform and
unavailable coverage separately. Serialize heavy suites and restore the default
integration build after recorded qualification.

Run locked repository checks for this documentation change. Implementation adds
focused tests and appropriate `java`, `assembly`, `integration`, `search` and actual
archive/replay qualification; old runtime successes do not qualify the archive.
Retain original logs/artifacts before diagnosing any required failure. No design
freeze, owner review, implementation, runtime pass, merge or release is implied by
this local proposal. Concrete schemas/vectors, supported historical executors and
P14b/c algorithm freezes remain next work, not hidden completed decisions.
