# Durable local Kafka archive

P14a implements an independent archive consumer and local compressed object/segment
store. It preserves exact original Kafka bytes and registered evidence/provenance;
it does not execute historical or current-policy replay. Acceptance and exact
qualification are in the [P14 ledger](p14-ledger.md). The
[owning freeze](p14a-design.md) defines version 1.0.0, identities, bounds and crash
semantics; [contracts](../contracts/archive/v1/README.md) remain separate from
P03/P05/P12/P13. P14b/c and P05 archive import remain later bounded work.

## Preparation and commands

Use the locked [development environment](development.md). An existing owned P13
project must provide its private `kafka:9092` network and all nine original topics
(input, seven integration outputs and search writer failures). Archive initialization
reads their IDs and never creates or changes producer topics, policies or groups.
A running OpenSearch instance or Flink job is not required by the archive itself.
Existing P13/search initialization normally supplies those topics.

```sh
uv run --locked python tools/dev.py archive
uv run --locked python tools/archive.py build
uv run --locked python tools/archive.py --project detectbridge-p13-dev init \
  --objects /absolute/path/to/reviewed-sha256-objects \
  --starts /absolute/path/to/explicit-starts.json \
  --provenance /absolute/path/to/provenance-hashes.json
uv run --locked python tools/archive.py --project detectbridge-p13-dev drain
uv run --locked python tools/archive.py --project detectbridge-p13-dev inspect --broker
uv run --locked python tools/archive.py --project detectbridge-p13-dev metrics
```

`starts.json` is an object containing every exact topic name and its nonnegative
starting offset, usually explicit zero for a complete new retained project.
No implicit earliest/reset is accepted. `provenance-hashes.json` is a nonempty
array of lowercase SHA-256 strings identifying registered original terms/catalog/
capture/source-binding files. Supply all applicable metadata and decision inputs;
a supplied hash verifies bytes, not human authenticity or completeness. P14b owns
sealing full historical processing dependencies. Registration includes those
provenance files and original evidence objects as regular SHA-named files, with
no symlinks: at most 128 files, 32 MiB each and 64 MiB per registration batch.
No original is fetched from its URI, inferred from search or manufactured.

The CLI copies these explicitly supplied inputs into the ignored owned project
command directory, then publishes compressed immutable objects into its archive.
Private originals remain private; local recording terms do not authorize CI upload.
The original producer references are unchanged. Valid source references require
matching full-object and range hashes before offsets advance. Invalid/opaque Kafka
bytes are retained exactly, without becoming normalized events or nonmatches.
Source classification is an archival annotation; it does not certify source
support, host trust, context semantics or processing completion.

`drain` snapshots a finite broker end-offset vector and archives through that vector.
`run` continues until stopped or blocked; SIGTERM/interruption may leave an
uncommitted transaction, which restart verifies and recovers. A blocked command
returns nonzero and a value-free category; it does not intentionally discard input
or change retention. Correct the underlying dependency/permissions/outage and
rerun the same command. If initial object publication was interrupted after root
creation, `register` resumes the frozen owned registry before `drain`. An interrupted
initial root-directory creation is not an initialized resumable archive.

## Inspection and retrieval

State and private observations live under `.cache/archive/<project>/`; immutable
JARs and qualification probes live under `.cache/archive-build/`. `tooling.json`
pins the actual executable/probe/image, independently of the latest build pointer.
Changing a producer topic UUID, broker/group, implementation, image or root binding
is not a migration. Missing pinned artifacts fail explicitly. Future migration
needs an independently designed compatibility procedure, never a silent reset.

Use `object SHA256 new-output.bin` to retrieve and rehash an original object, or
`wire TOPIC OFFSET new-output.json` to retrieve a verified archived wire row.
Output names are new simple filenames within the owned command directory; existing
files are not overwritten. Wire rows contain base64 exact key/value bytes,
null-versus-empty distinctions, ordered duplicate headers, Kafka timestamp/type,
immutable location/identity, dependencies and a value-free classification. Decode
privately and verify the original full-object and record-range hashes. Do not
paste original bodies or exception messages into routine logs or public issues.

`inspect --broker` reports per-topic durable next offset, broker committed next,
earliest retained offset, observed end and lag. Missing group commits remain null.
`metrics` emits Prometheus text using only the nine fixed topic labels, plus
managed-byte and historical-readiness gauges. Progress is a vector, not an atomic
processing-completion watermark. `historical_ready` remains false in P14a;
`dependencies_ready` covers the frozen original/provenance object set only.

## Durability, recovery and finite preservation

Each object and segment is privately framed as bounded gzip NDJSON, then payload,
metadata, separate metadata-file checksum sidecars and directories are synced
and renamed before Kafka offsets may commit.
Restart fully verifies committed object bytes, metadata/hash chains and partition
prefixes, then syncs surviving publication directories before adoption. Exact
metadata-file hashes protect the final segment as well as predecessor chain links;
corrupting a tail offset cannot advance acknowledged coverage. Empty broker
control-batch intervals are retained with zero invented wire records. Partial
publication is ignored and only structurally recognized owned staging directories
are cleaned under the writer lock. Unknown files, corruption, missing dependencies
and a broker commit ahead of durable coverage stop; nothing is automatically
repaired by deleting committed evidence. A successful Kafka commit followed by a
crash before advisory progress is recovered from authoritative segments.

Identical retries verify existing bytes. Equal bytes at different offsets stay
distinct occurrences. Conflicting same-location content blocks; changed raw/context
for the same logical source occurrence at another offset is retained with a
semantic-conflict annotation. A new replay cannot overwrite historical evidence.
Historical reproduction and changed-policy output isolation are P14b/c work.

Defaults are 2 GiB managed archive bytes, 128 MiB free filesystem reserve,
32 MiB objects, 16 MiB uncompressed segments and 256 rows. Wire values are at most
2 MiB and complete wire rows at most 4 MiB. Polls admit at most four records,
within the frozen sixteen-record upper bound. Reservations use worst-case
transaction sizes, not assumed compression ratios. Orphans and partials count;
external disk use can still cause a real write/sync failure after preflight.
Stop/backpressure under exhaustion. No automatic archive or Kafka deletion,
expiry, retention reduction or unbounded-outage promise exists. P14c/P16 own
reviewed deletion/retention coordination; local disks are not disk-loss protection.
POSIX rename/locking/fsync semantics are required. Process-kill qualification does
not establish physical power-loss behavior or shared/network filesystem support.

## Qualification

```sh
uv run --locked python tools/archive.py build
uv run --locked python tools/archive.py verify
```

The verifier creates one isolated `detectbridge-p14-test-*` broker project, freezes
original synthetic bytes and expected locations, and runs actual container/offset/
filesystem faults. It retains ignored originals, helper failure responses and
reports; it removes only its own containers/volumes. No private recording is read
or uploaded by this command. Serialize heavy Docker suites. The real fail-closed
`archive-verification` CI job runs these commands on native AMD64 when applicable;
local ARM64 evidence, native CI and owner acceptance remain distinct.
