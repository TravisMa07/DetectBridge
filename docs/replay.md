# Local replay, timing and recovery

P05 replays explicitly selected, verified P04 artifacts into local files. It does
not parse source timestamps, assemble events, run detections or send Kafka records.
P03 raw-record schemas and their fixed registry remain unchanged.

## Commands

Acquire desired artifacts first using the [dataset guide](datasets.md). Replay
never downloads a missing object:

```sh
uv run --locked python tools/replay.py start linux-audit-whoami --unpaced
uv run --locked python tools/replay.py start windows-security-4688 --rate 100
uv run --locked python tools/replay.py inspect <run-uuid>
uv run --locked python tools/replay.py resume <run-uuid>
uv run --locked python tools/check_replay.py
```

Select one or more distinct catalog IDs. Output follows selection order and then
physical record order within each artifact. Unknown/duplicate IDs fail. Start
returns a new UUID and safe JSON progress totals; inspect verifies committed state
rather than trusting the checkpoint. Errors omit event values. Ctrl-C/SIGTERM
returns nonzero (130); other failures return 1. A run interrupted before creation
has no resumable output. Keep the UUID directory when recovering interrupted runs.

## Replay envelope and evidence

Schemas and metadata-only examples are under
[contracts/replay/v1](../contracts/replay/v1/envelope.schema.json), version `1.0.0`.
The separate local registry also registers P03 raw schemas without network access.

| Document | Meaning |
| --- | --- |
| `envelope` | Record or input-exhaustion control; global zero-based sequence |
| `timing-index` | Optional explicit occurrence times, pinned to selected evidence |
| `capture` | Once-assigned local first observation, separate from run state |
| `run-manifest` | Frozen selections, complete catalog manifests, capture metadata and timing/rate configuration |
| `segment` | Committed payload digest, length, count, initial sequence and manifest digest |
| `checkpoint` | Advisory committed-prefix progress and execution status |

A data envelope carries run UUID, dataset ID, sequence, unchanged P03-valid raw
record and `timing.original_time`, `effective_time`, and `basis`. Basis is either
`timing_index` or `first_observed`. Control envelopes are `dataset_end` (one per
selection) and `run_end` (one per run), with counts. These markers mean input
exhaustion; they do not establish assembly completeness or downstream success.

LF framing retains CRLF, blank records and the final unterminated record. Evidence
is referenced by `urn:sha256:<artifact-hash>` and byte offset/length, with a digest
of the original record bytes. No payload is copied into output. Preserve the
verified dataset cache and provenance alongside the run; references cannot resolve
without those objects. The raw envelope uses UTF-8 encoding and XML media type for
these Windows artifacts, plain text for Linux artifacts.

Record identity uses the P03 canonical helper, dataset cursor (artifact hash and
zero-based position), namespace `dataset:splunk/attack_data`, and source instance
`<scenario-id>:lf-byte-records-v1`. The instance identifies capture provenance,
not a host. Replaying different positions with identical bytes keeps them distinct.
The run UUID is separate and does not change record identity.

Capture JSON is stored under ignored `.cache/replay-captures/`, keyed by source
identity, artifact hash and framing. A process lock protects first assignment.
First observation means initial local capture by this replay tool, not historical
occurrence time or acquisition time. Subsequent runs reuse it. Deleting this store
loses that local observation history; backed-up run manifests preserve the values
for their own resume. Do not delete capture metadata while writers are active.

## Explicit timing

An index is optional and may be sparse. Its shape is:

```json
{
  "contract_version": "1.0.0",
  "datasets": [{
    "dataset_id": "linux-audit-whoami",
    "artifact_sha256": "<exact 64-character lowercase artifact digest>",
    "framing": "lf-byte-records-v1",
    "timestamps": [{"position": 0, "timestamp": "2020-01-01T00:00:00.123456789Z"}]
  }]
}
```

Replace the illustrative digest with the pinned catalog digest. See the
[valid example](../contracts/replay/v1/examples/timing-index.json). Example timing
is illustrative, not extracted or attested source time. Duplicate datasets or
positions, unselected IDs, out-of-range positions, mismatched framing/hashes and
invalid dates fail. UTC `Z` is mandatory; accept zero to nine fractional digits,
reject higher precision and leap-second representations. No timezone guessing.
The original index bytes and SHA-256 are retained with the run (16 MiB limit).

```sh
uv run --locked python tools/replay.py start linux-audit-whoami \
  --timing-index timing.json --time-mode shift \
  --anchor 2026-01-01T00:00:00Z --unpaced
```

Preserve mode (default) retains supplied timestamp spelling and precision exactly.
Missing entries use persisted first observation and remain labeled as fallback.
Shift mode requires an anchor and applies one constant integer-nanosecond offset
from the earliest selected timestamp (including fallbacks) to the anchor. Shifted
values use nine fractional digits. It retains relative differences, not original
spelling. The raw record and payload timestamps never change. Shift configuration
is in the frozen manifest; neither index nor rate can be replaced on resume.

Rate defaults to 100 records/second, independent of historical event spacing or
time mode. Accept finite rates greater than zero through 10,000, or `--unpaced`.
A monotonic clock waits in at most 100 ms intervals and schedules the next record
from current time, avoiding catch-up bursts. Control markers are unpaced. Local
records accumulate in a segment before publication; pacing does not promise smooth
file visibility. Resume uses a fresh pacing interval at the next uncommitted row.

## Bounds and committed output

| Limit | Initial value |
| --- | --- |
| Artifact / selected batch | P04 limits: 32 MiB / 64 MiB, including provenance in the batch |
| Selected records | 100,000 |
| Individual record | 1 MiB |
| Serialized segment | 8 MiB or 1,000 envelopes, whichever comes first |
| Completed serialized envelope output | 512 MiB |
| Timing index / frozen manifest | 16 MiB each |

Preflight verifies inputs, framing counts, record sizes and output limits before
emission. Serialized-output accounting includes end markers, not small commit
metadata. All state is ignored under `.cache/replay/<run-uuid>/`:

```text
manifest.json + manifest.sha256     frozen configuration
[timing-index.json]                 original optional index bytes
checkpoint.json                    advisory progress
.run.lock                          per-run process lock
segments/00000000/records.ndjson    authoritative envelopes
segments/00000000/commit.json       committed segment metadata
```

A segment directory is prepared privately, payload and metadata are flushed and
fsynced, then atomically renamed and the parent directory fsynced. Only committed
segment directories count as output. Resume validates input/provenance objects,
frozen manifest/index, every segment digest and contiguous sequence, exact expected
envelopes, dataset markers and counts. It accepts an older checkpoint only if it
matches an actual committed prefix. It recovers a segment published before a
checkpoint update without duplicating its records; partial segment directories
are discarded. Corrupt committed output or inconsistent checkpoints fail visibly.
Completion requires the committed `run_end`; resuming a completed run verifies it
without appending anything. Concurrent writers fail the per-run lock.

Checkpoint status is advisory. Inspect reports completion derived from segments
and otherwise interrupted/not complete, including a previously prepared run.
Uncommitted in-memory records are emitted again after interruption. Invalid state
is never automatically repaired by deleting committed evidence. Preserve failed
runs for diagnosis; create a new run after correcting evidence availability.
Atomicity/durability assumes a local filesystem honoring rename, flock and fsync;
network filesystems and loss of the local disk are unqualified. These guarantees
apply to local committed files. P07 must define Kafka acknowledgment, deduplication
and recovery separately; P14 owns durable archival beyond this local cache.

## Verification and recorded qualification

`python3 tools/dev.py check` includes offline replay-schema validation and synthetic
recovery tests using fake clocks and temporary artifacts. Normal CI requires no
public data downloads and performs no real pacing delays.

After acquiring all four seed artifacts, run:

```sh
uv run --locked python tools/qualify_replay.py
```

This creates two isolated unpaced runs, verifies 7,046 records per run plus four
dataset-end markers and one run-end marker, independently rereads every evidence
range/digest, compares record identities/first observations across runs, verifies
completed resume, and rechecks original objects. It prints administrative totals
only. The opt-in **Recorded replay qualification** workflow repeats this on Linux
AMD64. During P05, the registered **Repository hygiene** dispatch also accepts
`qualify-replay=true` on the PR branch. External availability is excluded from the
required PR gate. These checks establish local replay correctness, not detection
accuracy, throughput capacity or Kafka delivery guarantees.
