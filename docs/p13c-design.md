# P13c isolated search projections

Base: owner-merged P13b #47, `500ffc7`. Exact PR-head 8cc680c passed all applicable
native AMD64 jobs in 43978412654, including every actual sink/recovery case.
Merged-main 44004484594 was pending at design preparation and later failed
assembly checkpoint-metadata restore. A shared qualification retention race and
its regression/correction are recorded in the ledger; rerun affected actual suites
before attributing runtime qualification to this branch. Earlier P13b native failure remains an unexplained failed attempt,
not waived acceptance. P08/P11/P12 bounded acceptance is not reopened.

## Compatibility and delivery

Implement a separate integration-writer module, search-writer/1.0.0 configuration,
CLI/cache/image and exact runtime user `detectbridge_search_writer_v1`. Reuse the
reviewed P08 algorithm in this explicit mode: bounded windows, item outcomes,
create-and-verify conflicts, TLS, retry/backpressure, failure acknowledgement before
commits and strict startup/precommit destination bindings. Existing P08 schemas,
physical indices, role, binaries and defaults stay unchanged. There is no checkpoint
adoption or migration. Only dedicated `detectbridge-p13-*` projects are accepted;
P13b source/checkpoint state stays owned by its existing job.

Consume tagged-events.v1, detections.v1, processing-diagnostics.v1 plus a new
`detectbridge.integration.writer-failures.v1` topic (all prefixed detectbridge).
Failure records reference original topic/partition/offset/hash/length/null status.
Tagged, detection and compact-diagnostic inputs may be durably quarantined after
permanent rejection; failure-topic inputs block on any failure, without recursion.
P13b manifests, preservation and receipts remain in their original Kafka topics;
this derived view links them rather than inventing normalized events for them.

Freeze exactly three physical indices: detectbridge-tagged-events-v1,
detectbridge-detections-v1 and detectbridge-processing-diagnostics-v1. The last
contains distinct compact-evaluation and writer-failure kinds. No aliases, wildcard
index grants or runtime delete/security/template administration. Admin provisioning
is explicit; runtime credentials contain no admin private material. Kafka cluster/
all nine source-topic IDs, integration binding/artifact/evaluation bundle, group,
writer artifact, CA/password, OpenSearch cluster/index UUIDs/mapping/settings and
exact templates are frozen. Cross-mode configuration is rejected.

Bounds remain P08's 100 records/16 MiB consumed window, 100 documents/2 MiB NDJSON
bulk, one request/worker, 4 MiB response, 5-second connect/20-second request,
35-second outer watchdog, five fast retries then 30-second probes. Input P13
individual documents are bounded at 2 MiB. Larger projections enter permanent
failure only after acknowledged reference publication; no truncation. Unknown HTTP/
item responses block. Authentication/permission/TLS/configuration drift stops.

## Projection wire shape, mappings and identities

Projection version 1.0.0 is closed and tagged by mode `p13-search/1.0.0`. All have
kind, pipeline_id, input_sha256, first_input and canonical content_sha256. Semantic
IDs are the original P13 processing/detection/diagnostic IDs. Tagged rows validate
their processing preimage; detection/diagnostic IDs validate their domain preimages.
Version 1.1.0 and p13-runtime/1.0.0, pinned evaluation bundle, source/attribution
bindings and Kafka keys are required. This writer does not reevaluate rules or
substitute evaluator output for its expectations.

Common searchable keywords: processing_id, event_id, run_id, source namespace/
instance, bundle and version/hash fields. Retain full bounded attribution as a
nonindexed object. Tagged projections additionally contain ECS host/process/user
objects with explicit searchable fields, event code/category/type/outcome, all six
long counts, tags, eligibility, source-quality findings, match links, record IDs
and evidence hashes. Selected ECS fields alone are copied; no arbitrary vendor
extensions, raw inline originals, rule YAML or expressions enter search. Full
semantic-event hash still detects conflicting decision content in omitted fields.
Detection rows retain pinned rule metadata as a nonindexed object plus searchable
ID/revision. Title/tags are not inferred from removed YAML; the existing pinned
rule contract does not supply those fields. Compact diagnostics retain category and immutable rule-set
reference as a nonindexed object plus count/hash. Manifest and sanitized evidence
references retain IDs/hashes/retrieval locations; the immutable input/manifest
Kafka topic IDs are explicit links. OpenSearch is not original evidence storage.

All mappings use root dynamic=strict; searchable objects have closed properties.
Opaque bounded metadata uses enabled=false, never dynamic vendor mappings.
Keywords have ignore_above=4096; exact longer values remain in `_source` and its
semantic hash. Greater-than-nanosecond precision is retained without rounding, with
outside_nanos_range_or_precision when no date_nanos value can be represented. Dates
retain exact original strings and basis/quality. Optional @timestamp is date_nanos
only if its original UTC value fits nonnegative signed-long nanos (1970 through the
representable 2262 endpoint) without rounding. Other dates remain exact metadata
with outside_nanos_range. No receipt/ingestion/processing clock becomes occurrence
time; source precision and fallback remain visible in exact strings/metadata.

Canonical JSON recursively sorts keys, retains array order/integer values/UTF-8.
Content hash excludes content_sha256, first_input, input_sha256 and evidence`_source`;
manifest comparison uses only its semantic_sha256, retaining its original retrieval
link in the first document. Event semantic hashing removes event.ingested,
detectbridge.time.received/processed and Linux context.receipt exactly as P13a.
Thus physical copies and receipt clocks cannot create semantic conflicts. Existing
`_source` is rehashed, never trusted by its claimed checksum. A changed semantic
projection with the same ID is quarantined without overwrite. Failure IDs use
["p13-search-writer:1.0.0", cluster, topic ID, decimal partition, decimal offset].
Independent literal vectors and projection expectations precede Java implementation.

## Qualification and limits

Actual Windows Security/Sysmon, Linux auth and prepared audit outputs must flow
through Kafka/Flink and this independent writer to real TLS OpenSearch. Freeze
source inputs/independent outcome counts before admission, inspect actual fields,
IDs/hashes/references and two replay-isolated runs. Qualify partial bulk success,
create-and-verify duplicates/tamper, crash before commit, blocked failure publication,
OpenSearch outage and failure-topic indexing rejection, denied P08/unrelated and
management/delete access, mapping/config/credential drift, TLS/hostname negatives,
metrics/log bounds and owned cleanup. Preserve P07–P12 regression gates. ARM64 local
and native AMD64 CI are separate evidence. Original recorded source-to-search
qualification/full P13 acceptance remain explicit separate gates until actually run;
ordinary synthetic CI does not imply access to retained local recordings. No
archive, rule activation, API/UI, throughput, release or merge authorization.
