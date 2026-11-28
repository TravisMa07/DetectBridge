# P15b qualification-only batch producer

Status: pre-implementation boundary freeze after native activation run44609809010
failed during initial A source accounting. Its `unexpected_event`,14 admitted
inputs and10 logical outputs do not identify the exact cause: the offending raw
batch was private and was not uploaded. Per-record helper startup is a measured
hotspot and can consume the existing30-second audit assembly window. Preserve
the native failure, add value-free unexpected-output diagnostics, and qualify the
unchanged original source/closure expectations with bounded batch delivery.

This is a separate qualification artifact and local administration transport, not
a new worker execution engine. Production lifecycle JAR `055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d`,
original producer `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`
and compiler packet `f2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d`
remain unchanged. The separately pinned qualification JAR gains a fixed first-party
`LifecycleBatchProducer` entry point; imported content and normal worker config
cannot choose it. No Flink timeout, assembler age, CPU/memory budget, source
membership, literal expected result or required scenario is relaxed.

## Exact helper contract

The command has eight positional arguments: expected qualification-JAR SHA256,
expected runtime-JAR SHA256, bootstrap, cluster ID, topic name, topic ID, private
operation root, and request SHA256. Before effects, verify this class's actual
code source, runtime `LifecycleSupport` code source and original `Schemas` code
source. The controller chooses every argument from verified configuration; it
does not forward caller-selected commands or classpaths.

The operation root basename is its canonical UUID. Its closed layout is
`request.json`, `values/`, `attempts/`, `acknowledgments/`, and `receipts/`.
Directories are0700 and files0600, current UID, single-link regular files, with
no symlink path component. Values use `%020d.value`; journal metadata use
`%020d.json`. A bounded private `.partial-<UUID>` from atomic publication is
retained as uncommitted evidence, never promoted to a receipt. The helper refuses
any existing attempt/acknowledgment/receipt or partial metadata; it never resumes
or retries an existing operation.

`request.json` is closed canonical JSON, at most64 KiB, with fields `version`
(`1.0.0`), `operation_id`, `worker_id`, `incarnation`, `command_sha256`,
`cluster_id`, `topic`, `topic_id`, and `records`. Records have exactly `index`,
`run_id`, `key_base64`, `value_file`, `value_bytes`, and `value_sha256`.
Indices are dense0–N−1, N is1–128, each value is1 byte through2 MiB, aggregate bytes at most
8 MiB. Integer fields reject booleans/floats. Keys are canonical base64 of the
record's canonical run UUID in UTF-8, at most256 decoded bytes. The request hash,
scope, every input byte/hash/length, closed layout and private attributes must
validate before any attempt or broker effect.

One Admin client and Producer are reused. Preserve existing Kafka ACK and request
timeouts and explicit partition0. Check actual cluster ID, topic ID/name and one
partition before and after **every** send. A topic name alone is not an identity.

All three per-index metadata files are closed JSON and at most4096 bytes:

- Attempt: `version`, `operation_id`, `request_sha256`, `index`, `cluster_id`,
  `topic`, `topic_id`, `partition`, `key_sha256`, `value_sha256`, `value_bytes`.
- Acknowledgment: `version`, `operation_id`, `request_sha256`, `index`, `topic`,
  `partition`, `offset`, `key_sha256`, `value_sha256`, `broker_timestamp`.
  The timestamp is actual Kafka metadata, allowing−1 for unavailable metadata.
- Receipt: attempt fields plus `offset`, `broker_timestamp`, and
  `acknowledgment_sha256`.

Force immutable attempt bytes and parent directory **before** invoking send.
After actual broker acknowledgment, preserve/force its metadata before post-send
namespace verification. If that verification succeeds, force the receipt and its
parent **before** attempting the next record. Offsets must be nonnegative and
strictly increasing in this single partition; gaps are allowed. Existing files
are never silently repaired or overwritten. Success stdout is a closed summary
with `version`, `operation_id`, `request_sha256`, `completed`, and
`receipt_sha256` (ordered hashes), bounded64 KiB. Failure remains nonzero with
fixed value-free category/class metadata. Original input and partial files remain.

## Controller ownership and recovery

Expose batch admission only through an explicit qualification method requiring a
registered, hash-verified qualification artifact. Normal production admission
retains its ordinary transport. Prevalidate all current publication/incarnation,
run ownership and input-byte limits before preparing the batch.

Use permanent `qualification-batches/<operation UUID>/` storage, never a temporary
directory removed on failure. Bound the deployment to64 operations, reserve16 MiB
per operation before copying, and count all files against existing512 MiB store,
free-space/headroom and65,536-entry limits. No automatic deletion or retention
increase. Source bytes are at most8 MiB and three4096-byte metadata sets for128
records are at most1.5 MiB; the16 MiB reservation covers inputs, request, metadata,
publication temporaries and controller journal writes.

Force input files/request/directories, then append an immutable checked
`qualification_batch_intent` referencing the request hash, scope, worker,
incarnation, publication hash and count before helper launch. The Docker helper
uses the same limits as existing helpers and the120-second operation deadline.
Its deterministic operation name/owner labels permit exact fencing after a
controller crash. Classpath order keeps verified runtime/producer before the
qualification JAR, avoiding worker-class shadowing.

On success, failure, missing stdout or controller recovery: first fence any exact
owned still-running batch helper; never kill an unrelated container. Validate the
dense immutable attempt/ACK/receipt prefix against request bytes and physical
scope, force surviving certified files/directories, then append each actual
receipt through the normal `admit` journal. Bind each admission to operation/index
and request hash so recovery cannot append it twice. A later corrupt record cannot
erase earlier verified admissions. Reject conflicting metadata and preserve it.

There can be at most one attempted index without a certified receipt, since the
next send requires the previous receipt's force. It is uncertain even if a raw
broker ACK exists without post-send namespace proof. Later indices are unsent;
neither category is invented as an admission or silently retried. A failed,
incomplete or recovered operation blocks further admission for that worker in
the qualification deployment; abort the attempt rather than automatically resend
the suffix. Return the full receipt list only on complete verified helper success.
Actual verified prefixes are still journaled before an error is returned. A
recovered complete prefix does not manufacture a successful original process.

## Qualification and diagnostics

Freeze [independent Q01–Q20 expectations](p15b-batch-expectations.md) before code.
Unit tests may inject transport/force failures as explicitly labeled mechanics;
they do not establish Kafka acceptance. Actual focused core qualification must
deliver original six-member audit fixtures, exact eligible `source_boundary`
closure, fixed A/B/A decisions, complete receipt/output accounting and unchanged
worker/compiler hashes. Then native CI executes all fourteen required scenarios.

Before checking an output batch, retain its complete original privately. On an
oracle failure export only bounded validated identifiers/hashes and fixed enums:
record index, known kind, canonical run UUID, SHA256 output/event IDs, wire/document
hashes, manifest closure allowlist, member count and allowlisted finding codes.
Unknown strings remain private and are represented by counts/hashes. This does
not classify the original native failure retroactively or change any oracle.

The additional freeze and implementation commits preserve published history and
the new qualification artifact/recovery boundary under the SDLC exception. They
do not authorize merge, release, P15b2 implementation or P16 advancement.
