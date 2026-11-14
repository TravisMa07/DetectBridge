# Idempotent OpenSearch metadata writer

P08 adds an independent Java consumer of P07 output, relay quarantine, and writer
failures. It indexes metadata only. It does not parse telemetry, assemble events,
evaluate detections, dereference original evidence, or implement the P14 archive.
The [ADR](decisions/0008-opensearch-writer.md) records the accepted choices.

## Build and initialize

Use the [pinned development environment](development.md), [local infrastructure](local-stack.md),
and [transport guide](transport.md). The selected P07 pipeline must already be
initialized, and its full-profile OpenSearch must be running before writer init.
For an existing core project, prepare the full profile using stack commands. If
stack recreation is needed, capture the latest retained checkpoint, stop the job,
and restore explicitly after recreation. Writer initialization never stops or
resubmits Flink on the operator's behalf.

```sh
uv run --locked python tools/writer.py build
uv run --locked python tools/writer.py init
uv run --locked python tools/writer.py start
uv run --locked python tools/writer.py status
uv run --locked python tools/writer.py metrics
uv run --locked python tools/writer.py stop
```

Global `--project detectbridge-example` precedes the command. Default:
`detectbridge-dev`. `init` requires the writer stopped and is rerunnable: existing
resources are verified, not silently migrated or rebound. A partial init keeps its
pending identity and credential for explicit retry. Missing/changed credentials
beside existing state require recovery of the original material.

The local image uses the existing digest-pinned Java 17 base, excludes Flink runtime
classes from the writer JAR, and is frozen by JAR checksum and image ID. It does
not change P07's transport bundle or checkpoint compatibility. Application/client
versions retain existing reviewed pins and strict Gradle locks/checksums.

## Resources and access

The opt-in writer has 512 MiB memory, a 256 MiB heap, 0.5 CPU and 128 PIDs. It runs
as UID/GID 9999 with a read-only root filesystem, bounded temporary storage, no
added capabilities, and `no-new-privileges`. Logs rotate at three 10 MiB files.
The full stack plus writer has 6.5 GiB container ceilings; writer commands require
7.5 GiB Docker memory. These are development bounds, not measured throughput.
Concurrent independent projects share the Docker VM and can exceed its capacity;
per-project checks do not reserve memory for every other workload.

Only internal port 9250 serves health/Prometheus metrics. Kafka, Flink and writer
ports remain unpublished. OpenSearch retains authenticated TLS on loopback and
its internal service name. Never disable CA or hostname verification.

A separate writer user can bulk-create/index, retrieve duplicate documents and
read necessary metadata only for the two managed indices. The sole additional
cluster actions are main/cluster identity inspection and bulk dispatch; actual
item writes remain subject to the two-index permission boundary. It cannot delete
indices/documents, administer security/templates, or access unrelated indices.
Create-only behavior is enforced by the application; credentials are not claimed
to be an independent write-once storage boundary.

Initialization uses the existing signed admin PKCS#12 certificate in an isolated
helper to provision only named writer security entries. Existing CA, operator and
health credentials and unrelated security entries remain intact. OpenSearch role
responses are compared semantically, including defaults/reordered permission
sets, without accepting broader grants.

Host state is under ignored `.cache/writer/<project>/` with restrictive permissions.
Owned named volumes establish actual UID/mode readability on Linux. Runtime
`writer-secrets` contains only configuration, the public CA and writer password;
it never contains CA/admin/node private stores. The one-shot admin volume is
removed after use. Root is used only for bounded volume ownership initialization.
Passwords, private material, request bodies, response dumps and source values are
not printed or placed in container command arguments.

## Search view and immutable identities

| Resource | Purpose |
| --- | --- |
| `detectbridge-replay-v1` | Physical index for records and control markers |
| `detectbridge-records-v1` | Filtered record alias |
| `detectbridge-controls-v1` | Filtered control-marker alias |
| `detectbridge-diagnostics-v1` | Relay and writer failure diagnostics |

Mappings are strict and explicitly versioned. Each physical index has one primary,
zero replicas, request translog durability and a one-second refresh interval.
No automatic rollover, retention deletion or rebuild is introduced. Alias filters
are convenience views, not an authorization boundary.

Records retain run/sequence/dataset identifiers, raw identity, source/cursor,
first observation, evidence hashes/encoding/media type and references, and replay
timing. Inline bodies and original log text are excluded. Original timestamp
strings remain exact. The optional `effective_time` search field uses nanosecond
resolution. Dates outside the representable range remain in `timing` with
`time_projection_reason=outside_nanos_range`; no rounding or substituted occurrence
time is introduced. No normalized ECS `event.ingested` field is populated here.

Example operator queries, using the existing CA and prompted operator password:

```sh
curl --cacert .cache/stack/detectbridge-dev/security/ca.pem --user operator \
  'https://127.0.0.1:9200/detectbridge-records-v1/_search?size=10'
curl --cacert .cache/stack/detectbridge-dev/security/ca.pem --user operator \
  'https://127.0.0.1:9200/detectbridge-diagnostics-v1/_search?size=10'
```

Replay IDs are SHA-256 over canonical JSON `["1.0.0", pipeline_id, run_id,
sequence_as_decimal_string]`. Control markers use the same identity domain and
physical index, so cross-kind conflicts cannot create a second document. Replays
with different run UUIDs remain separate. Original raw identity is unchanged.

Every projected document carries the exact Kafka value SHA-256 and a stable
projection SHA-256. Canonical projection JSON recursively sorts object keys,
preserves array order and UTF-8, uses compact JSON and integer values, and excludes
`first_input` and `content_sha256`. `first_input` retains the first accepted physical
Kafka location. Duplicate conflicts retrieve the existing `_source` and recompute
its hash; the stored hash alone is not trusted. Matching content is an accounted
duplicate. Different content is durably quarantined without overwriting.

## Delivery, retries and offsets

A writer consumer group reads:

- `detectbridge.replay.output.v1`
- `detectbridge.replay.quarantine.v1`
- `detectbridge.opensearch.writer-failures.v1`

The new failure topic has one partition, replication/minimum ISR one and no
automatic expiration. Init explicitly seeds a new group's beginning offsets;
subsequent starts require committed, in-range offsets. There is no implicit reset.
Kafka cluster/topic UUIDs, OpenSearch cluster/index UUIDs, mappings/templates,
consumer group, contract versions and artifact/credential bindings are frozen.
Unexpected recreation or drift stops progress.

Only one HTTP request is in flight. Bulks contain at most 100 documents or 2 MiB
including NDJSON framing. Low-volume work is sent immediately, within the
one-second flush ceiling. Consumed windows are bounded to 100 records/16 MiB.
Connections time out after five seconds, requests after 20 seconds, and responses
are bounded to four MiB. An outer watchdog prevents an unresponsive dependency
operation from accumulating unbounded worker tasks.

Every bulk item is inspected. Known successful items are not resent within the
current window. Transport failures, 429/5xx and recognized temporary cluster blocks
receive bounded exponential retries (one-second initial delay, 30-second cap,
20% jitter, five fast attempts). Exhaustion pauses fetching and probes every 30
seconds while maintaining consumer membership. Outage exhaustion is not a reason
to discard or permanently quarantine accepted data.

Authentication, certificate, permission and destination/configuration failures
stop the writer. Invalid replay input, verified content conflicts and recognized
per-document mapping failures enter the writer-failure topic. Unknown responses
remain unresolved and block. Template/security bindings are audited at init/start;
active index identity and mapping/settings fingerprints are checked before commits. Diagnostic failures block instead of recursively
creating more diagnostics.

Offsets commit only when every item in a consumed window has either an indexed/
verified-duplicate result or an acknowledged failure-topic record. Failure-topic
publication uses idempotence, `acks=all`, one request in flight, bounded buffers
and a 30-second delivery timeout. Failure to acknowledge it blocks source commits.
Indexing that failure topic into diagnostics is a secondary step.

Crashes after indexing or failure publication but before offset commit can repeat
work. This is at-least-once processing, not a distributed transaction. Kafka offsets
are the consumption ledger; counters are observations. Indexing acknowledgment
precedes search refresh and has no single-node disk/host-failure protection.
End markers still mean input exhaustion, not successful indexing or detection.

## Failure retrieval and recovery

A failure contains a stable ID, value-free reason, original input Kafka location,
length, null indicator and SHA-256. Its ID is canonical SHA-256 over
`["writer:1.0.0", cluster_id, topic_id, partition_as_string, offset_as_string]`.
Quarantine values and raw keys are never copied into Kafka failure records.

For retrieval, use the [transport guide's private reader procedure](transport.md#retrieving-quarantined-evidence)
with the writer diagnostic's `input` location and the writer's frozen source topic
identities. Verify the original location's value length/hash/null indicator before
saving it to a private ignored file. Never substitute content from a recreated
topic or print an event body into operational logs. Retain input while these
references or a future rebuild depend on it.

`stop` drains for at most 30 seconds. Unresolved work remains uncommitted. Restart
with `start` after dependency repair; it uses the same group and destination.
After a credential failure, restore the original credential rather than rotating
beside retained state. Index/template/artifact changes need explicit compatibility
review. Reverting code is not a migration or rebuild procedure.

`stack.py down` stops/removes the writer along with its project containers, retaining
volumes and credentials. A subsequent full stack startup is idle until explicit
writer start. Exact-project `stack.py reset --confirm <project>` deletes its writer
state and volumes as well. It never prunes another project. Keep backups outside
this reset boundary; P21 owns release backup qualification.

## Qualification and CI

```sh
uv run --locked python tools/check_writer.py
uv run --locked python tools/dev.py check
uv run --locked python tools/dev.py java
uv run --locked python tools/writer.py verify
uv run --locked python tools/datasets.py fetch --all
uv run --locked python tools/writer.py verify --recorded
```

Ordinary integration uses invented temporary artifacts through the real P04/P05
path. It covers partial item failures, successful indexing before an uncommitted
window crash, blocked Kafka failure publication, OpenSearch outage/recovery,
duplicate/conflict handling, zero-partition member rebalances, exact timestamp
doc values, reference retrieval, authorization, restart/persistence,
internal metrics, value-free logs and isolated cleanup.

Recorded qualification selects all four pinned artifacts and two replay runs.
Additional controlled proof documents are reported separately from the two replay
runs. Public acquisition is opt-in and outside required checks. Local ARM64 and native
Linux AMD64 qualification are distinct. Consult the PR checks for native AMD64
results; the local validation record below reports ARM64 evidence only. Neither integration timing nor shared CI is a capacity
benchmark. The existing [dependency disposition](transport-dependencies.md),
including the pinned upstream image finding tracked in P21, remains applicable.

## Local validation record

Native ARM64 qualification on 2026-11-14 used Docker Engine 29.8.0, Compose 5.5.1,
and a Docker VM with 8,318,844,928 bytes of memory. The tested writer JAR SHA-256 is
`68048856dfb680d78c3609a0385536e36b35145cf45b10e31d8205b0cd569d48`.
These measurements establish compatibility and recovery behavior, not capacity.

- Developer checks: 88 Python tests, repository hygiene, Ruff, and mypy passed.
- Java verification: 15 writer tests and five shared transport semantic tests
  passed, with strict dependency verification and shaded-artifact policy checks.
- Dependency inventory: all 67 locked Maven coordinates matched the reviewed inventory.
- Synthetic full-stack qualification: 252 replay envelopes across two runs plus
  five proof documents yielded 257 unique replay documents and four retrievable
  diagnostics. All three consumed topics had zero lag after recovery and full
  recreation. Pending-input shutdown took 15.719 seconds; the container exited
  with code 143 without OOM or forced termination.
- Recorded full-stack qualification: all four pinned artifacts across two runs
  produced 14,102 replay envelopes plus five proof documents, yielding 14,107
  unique replay documents and four retrievable diagnostics. Input hashes,
  independently derived IDs, projection hashes and retained references matched.
  All three inputs had zero lag after crash recovery and full recreation.
  Pending-input shutdown took 15.692 seconds with exit code 143 and no OOM or
  forced termination.
- Native Linux AMD64 qualification: pending GitHub Actions; review its result
  separately from the local ARM64 evidence.

Generated reports remain outside Git under `.cache/writer-reports/`; neither
telemetry nor generated credentials are included in this change. Test projects
are exclusive and cleanup removes only their own resources. Local qualification
does not authorize a merge or establish the full cross-platform acceptance gate.
