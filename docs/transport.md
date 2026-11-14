# Checkpointed replay transport

P07 connects completed replay evidence to Kafka, through a validating Flink job,
and into output or quarantine. It does not parse, normalize, assemble, detect or
index events. P03/P05 contract definitions remain unchanged.

## Setup and lifecycle

Use the [development environment](development.md) and
[local Docker infrastructure](local-stack.md). Commands may acquire pinned build
dependencies or Docker images when absent; preload them for offline operation.
No Python Kafka client or host Kafka port is required.

```sh
uv run --locked python tools/dev.py java
uv run --locked python tools/transport.py build
uv run --locked python tools/transport.py init
uv run --locked python tools/transport.py start
uv run --locked python tools/transport.py status
uv run --locked python tools/transport.py metrics
```

Global `--project detectbridge-example` precedes the command. Init requires the
selected idle P06 stack to be stopped first; it explicitly recreates Kafka/Flink
with the reviewed transport bundle. It preserves volumes, cluster identity and
credentials. Existing transport initialization verifies its frozen configuration.

The local image derives from the locked Flink 2.2.1 Java 17 image, includes the
job/publisher JARs, and uses its existing Prometheus plugin. The upstream pins,
CPU/memory limits, non-root users and internal network remain in effect. The
transport overlay identifies the exact local image ID and bundle checksum.
Changing that bundle beside existing state requires compatibility review.

The publisher helper runs as UID 9999 with 512 MiB memory, a 256 MiB Java heap,
0.5 CPU, 128 PIDs and no added capabilities. It joins only the project's internal
network. Kafka, Flink REST and Prometheus port 9249 have no host publication.
OpenSearch is not needed for this transport path. Helpers have project-scoped names,
use Docker logging driver `none`, and are explicitly removed after exit. Their
private stdout carries broker IPC, so retaining it in Docker logs is prohibited.
Only publication/injection attaches stdin. Read-only helpers retry a recognized
Docker API/setup failure once, after removing the old helper; broker/application
failures are not retried through this path. Publication never uses this retry.

## Topics and public contracts

Each project's Kafka broker holds three topics:

| Topic | Contents |
| --- | --- |
| `detectbridge.replay.input.v1` | Original replay envelope values |
| `detectbridge.replay.output.v1` | Validated, unchanged input key/value bytes |
| `detectbridge.replay.quarantine.v1` | Diagnostics and references to invalid input |

Topics have one partition, replication factor one, minimum ISR one, delete cleanup
policy, disabled time/size expiration, and a 2 MiB broker topic message bound.
The accepted replay value limit is **1 MiB**, leaving room for Kafka overhead.
The pipeline freezes cluster ID, topic UUIDs, configuration, consumer group, bundle
and supported schema versions. Changed topic identity/policy is rejected at
administration/publication and checked again during Flink checkpoints.

Kafka keys are UTF-8 replay UUIDs. `(run_id, sequence)` identifies a logical replay
envelope, independently of immutable raw-record identity. Run ordering follows
its input partition. There is no event-time processing or watermark policy here.
Kafka metadata timestamps describe transport, not inferred source occurrence.

Transport schemas are separate under
[contracts/transport/v1](../contracts/transport/v1/configuration.schema.json),
version `1.0.0`. Configuration and acknowledgment receipts are local interfaces;
quarantine is a Kafka output contract. Publication state and versioned job history
complete the five document kinds. Readers reject unregistered versions.

## Publication and acknowledgment

First create and verify a completed run using the [replay guide](replay.md):

```sh
uv run --locked python tools/transport.py publish <run-uuid>
uv run --locked python tools/transport.py publication <run-uuid>
uv run --locked python tools/transport.py publish <run-uuid> --unpaced
```

Use an explicit rate or unpaced override on the **first** publication only.
Otherwise the run's frozen rate is inherited. The selected rate becomes immutable
publication configuration. Repeating publish resumes the acknowledged prefix;
completed publications are verified no-ops. Local replay and publication are
separate timed operations. Pacing uses a monotonic clock without catch-up bursts.

Preflight validates P05 completion, manifests, input objects, segment integrity,
envelopes and the transport size limit before sending. NDJSON's final LF is a
file-framing delimiter and is omitted from the Kafka value; the JSON bytes inside
that delimiter are unchanged. Raw evidence payloads and references are unchanged.

The idempotent producer uses acks=all, one request in flight, an 8 MiB buffer,
10-second request timeout and 30-second delivery timeout. This is a broker
acknowledgment boundary on one replica, not replication, power-loss durability,
source parsing or downstream processing success.

Ignored `.cache/transport/<project>/publications/<run-uuid>/` holds frozen
configuration and atomic receipt segments, separately from P05 evidence. Each
receipt contains the logical sequence, Kafka location and key/value checksums.
Persist receipts after at most 100 acknowledgments and at successful completion.
A process lock excludes concurrent publication. Recorded locations are reread and
verified before trusting progress. Lost/changed input, altered configuration or
noncontiguous receipts fail visibly.

A crash after acknowledgment but before receipt commit can repeat records in a
new producer session. Kafka idempotence handles retries within its producer
session; it does not deduplicate separate publication or recovery sessions.
Never change a replay UUID to hide a retry. Preserve and account for duplicate
`(run_id, sequence)` identities with identical bytes.

## Validation, quarantine and preservation

Flink independently applies closed repository-local JSON schemas with explicit
format checks and no network resolution. Raw semantic checks include canonical
identity, inline evidence digests and safe reference URIs. Duplicate JSON keys,
malformed UTF-8, wrong numeric types, excessive nesting, invalid versions and
key/run mismatches are rejected. Shared synthetic cases and independent P03
identity vectors check Python/Java agreement. Input is not coerced or rounded.

Valid keys and values pass unchanged. Invalid values produce bounded metadata:
reason category, value-free diagnostic pointer, cluster/topic identity,
partition/offset, value length/hash, and a separate null-value indicator. No raw
key or payload is copied into quarantine. Quarantine identity is derived from its
source Kafka location, so retries remain attributable. No input value is emitted
in routine logs or metrics. Helper stdout carrying base64 data is private IPC to
the orchestrator, not operator logging. Flink console logs retain severity/logger
and a fixed category; message and exception rendering are disabled. Use internal
status/checkpoint diagnostics for state rather than printing arbitrary exceptions.

A quarantine reference depends on retaining the original input topic and its
identity. Do not expire/delete/recreate it while references depend on it. P14
will own archival preservation beyond Kafka/local storage. No finite local disk
provides unlimited outage retention. Existing P06 disk monitoring limitations
remain in effect.

The sink uses AT_LEAST_ONCE and flushes pending output/quarantine writes on
checkpoints. Sink failure blocks successful checkpoint advancement and causes
backpressure/recovery, not intentional dropping. Output visibility can precede a
completed checkpoint. Neither end markers nor metrics prove completeness: verify
the full expected unique envelope set, hashes and quarantine locations.

## Retrieving quarantined evidence

Quarantine offsets and input offsets are different. Inspect the quarantine topic
through the internal Java reader, then verify the referenced input against its
frozen cluster/topic identity, size, null flag and checksum. The administrative
Python helper below retrieves one quarantine offset into an exclusive, private,
ignored file. It prints no key or event body. Run from the repository root; change
the project and quarantine offset deliberately. A missing reference or mismatch
is an error, not permission to search a recreated topic for similar content.

```python
# Run with: uv run --locked python
import base64
import json
import os
import sys

sys.path.insert(0, "tools")
from check_transport import require
from transport import INPUT, QUARANTINE, Transport, sha

t = Transport("detectbridge-dev")
quarantine_offset = 0
broker = t.verify_destination()
items = t.read_records(QUARANTINE, quarantine_offset, quarantine_offset + 1)
assert len(items) == 1
q = json.loads(base64.b64decode(items[0]["value"]))
require("quarantine", q)
location = q["input"]
assert location["cluster_id"] == broker["cluster_id"]
assert location["topic"] == INPUT and location["partition"] == 0
assert location["topic_id"] == broker["topics"][INPUT]["id"]
items = t.read_records(INPUT, location["offset"], location["offset"] + 1)
assert len(items) == 1 and items[0]["offset"] == location["offset"]
encoded = items[0]["value"]
raw = b"" if encoded is None else base64.b64decode(encoded)
assert (encoded is None) == q["value_is_null"]
assert len(raw) == q["value_size"] and sha(raw) == q["value_sha256"]
folder = t.folder / "retrieved"
folder.mkdir(mode=0o700, exist_ok=True)
path = folder / (q["quarantine_id"] + ".json")
with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
    json.dump({"diagnostic": q, "retained_value_base64": encoded}, out)
```

This is an explicit local forensic copy, not the P14 archive or an operator API
compatibility promise. Preserve its access restrictions and do not commit it.
The Kafka quarantine record itself continues to contain references only.

## Checkpoints and explicit recovery

The job uses parallelism one, stable operator UIDs, filesystem checkpoints in
P06's shared state volume, a 10-second interval, 60-second timeout, one concurrent
checkpoint and three retained completed checkpoints. Externalized checkpoints
remain after cancellation. Retained old job state consumes disk until reviewed
cleanup; do not remove state still referenced by a checkpoint.

Task recovery has three automatic attempts separated by ten seconds. Exhausting
that finite budget stops the job; after fixing the cause, explicitly restore a
compatible retained checkpoint. There is no unbounded retry loop. JobManager
loss has no automatic resubmission or HA coordinator. Capture a completed
checkpoint's external path through status before planned interruption. A running
job can evict an earlier path as newer checkpoints complete; after a terminal
failure, inspect its latest completed checkpoint rather than reusing a stale
pre-fault path. Verify that the selected metadata and state remain present. Restore
with the same configuration/bundle and retained checkpoint files:

```sh
uv run --locked python tools/transport.py stop
uv run --locked python tools/transport.py start --restore file:///state/checkpoints/<job-id>/chk-<number>
```

After full stack recreation, run `stack.py up --profile core` before transport
start. An active job blocks duplicate submission. Restore checks path ownership
against recorded job history and requires existing metadata. Missing/incompatible
state fails rather than silently starting from committed group offsets.

If deliberately rereading retained input, use `start --from-beginning`. This can
repeat previous output and requires duplicate accounting. It cannot recover
expired/deleted input. Do not delete publication receipts to simulate a new run.

## Metrics and qualification

`metrics` reads internal Prometheus endpoints. The job exposes seen, valid,
invalid and control counters plus Flink/Kafka checkpoint, lag and restart metrics.
No run or record IDs are metric labels. Counters reset on restart and count
physical processing attempts, including duplicates. Journals and verified Kafka
locations provide accounting; volatile counters do not.

```sh
uv run --locked python tools/check_transport.py
uv run --locked python tools/transport.py verify
uv run --locked python tools/datasets.py fetch --all
uv run --locked python tools/transport.py verify --recorded
```

Ordinary qualification uses invented, temporary acquisition objects and completed
replay runs. Their copied catalog shapes are test scaffolding, not attested
upstream acquisitions. It verifies ambiguous publication, completed no-op,
finite Kafka outage, invalid-input quarantine, TaskManager recovery, unavailable
quarantine backpressure through retry-budget exhaustion and explicit checkpoint
recovery, explicit JobManager restore, complete byte accounting,
metrics and value-free logs. Exclusive test projects are cleaned on failure or
interrupt; development state is never the target.

Recorded qualification uses all four pinned P04 artifacts and two distinct runs.
Public acquisition is opt-in and excluded from required PR checks. Required Linux
AMD64 CI runs synthetic transport qualification; macOS ARM64 is qualified locally.
Build checks also reconcile the [dependency inventory and findings](transport-dependencies.md).
The pinned upstream image has a documented unresolved shaded-Jackson finding;
application dependency patching does not remediate that embedded engine component.

All results establish transport/recovery behavior within the stated single-host
limits, not detection correctness or throughput capacity.
