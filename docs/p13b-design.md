# P13b integrated Kafka/Flink runtime

Status: owning implementation notes, recorded before code. Base e09c271 (owner
merged P13a #46); P13a PR-head checks and merged-main 43954609201 passed.
No runtime qualification begins until that baseline succeeds. A02–A07 and P12's
accepted prepared-transition semantics remain unchanged. P13c search is separate.

## Deployment and contracts

Use a separate integration-job module and `detectbridge-p13-*` deployment. It
reuses the real adapters, P12 Assembler prepared API and P13a compact evaluator.
The P12 checkpoint-prefix model is adapted in a separate state/version boundary;
P12 deployment/state/schema/resources are not adopted or silently migrated.

Input version 1.0.0: bounded raw/context `record`, `windows_record`, source_boundary
and run_end admissions. Linux contexts use the unchanged P12 validator; Windows
contexts use the actual Windows adapter validator. All original Kafka input and
raw/context bytes remain retained. Referenced evidence resolves only registered
SHA-named objects (128 objects, 32 MiB each, 64 MiB total); missing objects are
I/O backlog, integrity mismatches are preservation failures. No URI fetch.

Eight isolated topics: integration.input, tagged-events, detections,
processing-diagnostics, manifests, preservation, quarantine, receipts, each suffixed
.v1 and prefixed detectbridge.
Each is a single partition, replication one, indefinite retention in this bounded
local deployment. Consumer group `detectbridge-integration-v1-<pipeline UUID>`;
state/project/cache/image paths are separate from P07–P12. No OpenSearch dependency.

P13a output 1.0.0 pins pipeline p13-offline/1.0.0. Runtime output uses separately
validated 1.1.0 tagged/detection/diagnostic schemas with pipeline
p13-runtime/1.0.0; no existing 1.0.0 schema or offline output changes. The added
IntegrationOutputs constructor explicitly selects the known runtime profile;
legacy constructor/defaults remain unchanged. Domain-separated identity preimages
retain P13a's format with the actual pipeline, run, event and semantic attribution.
Compact evaluation stays 1.0.0. External enrichment inputs remain explicitly empty.

Native Linux and Windows preservation documents are retained inside a separately
versioned preservation wrapper, keyed by a domain-separated canonical hash of the
unchanged native diagnostic. No malformed source becomes a normalized event.
Receipts/quarantine use separate runtime schemas and bind original input location/
hash; their transport IDs may include physical offsets, unlike semantic processing/
detection IDs. Manifests remain unchanged P12 documents with original late links.

## Atomic transitions and limits

One ordered operator at parallelism one. P12 defaults remain: 256 members/1 MiB
group bytes, 1024 open groups/32 MiB pending, 30-second absolute deadlines, 16 runs,
100000 closed keys/32 MiB. Windows adds bounded run/dedup knowledge with the same
run/key/byte limits, checked before admission; no TTL/eviction. Repeated identical
Windows occurrences do not repeat normalization; conflicting redelivery fails
visibly. Run-end retains closed knowledge and preserves subsequent Windows input.
Linux continues using its exact original membership/completeness policies.

Separate inbox/outbox caps: 32 MiB/128 entries each; serialized state cap 160 MiB
plus 128 KiB. A one-group proposal expands through compact evaluation BEFORE
committing its assembler state, input receipt and all derived output intents.
At most 100 detections, one tagged event, three compact diagnostics, one manifest
and one receipt (106 documents) fit an empty outbox; complete integration <=16 MiB
plus <=1 MiB manifest/receipt fits the byte cap. Individual output <=2 MiB.
Kafka topic/producer message limits are 4 MiB, including envelope/header headroom.
A proposal larger than an empty queue fails with visible backlog; a partially full
queue defers it without committing state or consuming input. Nothing is truncated.

Windows adaptation is stateless within a detached proposal; its proposed dedup/
run state commits only with every output intent. Linux prepared transitions retain
absolute deadlines across downtime; ticks drain one original group at a time.
Only completed checkpoint prefixes release intents. Collection/retirement crosses
a later checkpoint with required sink acknowledgements; failures can repeat stable
canonical bytes/IDs. Abort never releases; restore of a completed snapshot releases
its retained prefix. Each of the seven required output routes participates in the
same acknowledged sink. No exactly-once, rescaling or old-checkpoint migration.

Restore binds exact job artifact, immutable mapped plan, evaluator/selector/
enrichment/runtime versions, source/mapping profiles, evidence registration,
limits, broker/topic IDs and group. Validate state before output/admission; changed
bindings fail. Inventories contain IDs/hashes/member references only and are
observations, never recovery sources; require independently confirmed COMPLETED
checkpoints before using them as qualification evidence.

## Independent expectations and qualification

Freeze original synthetic raw inputs and literal outcomes before execution. Reuse
existing P11/P12 originals and independent expectations; compile a pinned combined
bundle using their committed rule bytes/provenance. Verify exact fields, evidence/
manifest membership, six counts, matched metadata, diagnostics membership, semantic
identities and physical input receipts, not counts alone or evaluator-generated truth.
Two isolated runs preserve event/evidence IDs and isolate processing/detection IDs.

Model tests cover preparation rollback, bounds, corrupt state/binding rejection,
checkpoint-prefix/abort/partial publication, Windows dedup/end and Linux deadline/
late links. Actual serialized Docker qualification must cover both Windows profiles,
audit/authentication, every required sink rejection with checkpoint-retained intent
and healthy explicit restore, broker pause, TaskManager and JobManager restart,
explicit restore and incompatible-binding rejection. Serialize heavy projects and
clean only their owned resources. CI must invoke real tests/runtime, fail closed
on unexpected applicability skips, and keep existing regression gates intact.

Record exact artifacts, attempts, passed/failed/unavailable checks and limitations
in the P13b ledger. ARM64 local and native AMD64 CI are separate evidence. Recorded
source-to-search acceptance remains the full P13 milestone with P13c; no archive,
activation, API/UI, throughput or release claim. Owner authorizes merge separately.
