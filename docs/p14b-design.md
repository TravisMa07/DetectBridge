# P14b pinned historical replay freeze

Status: design/independent expectation freeze 5922901, 2026-11-18 UTC, followed by
local implementation. The [ledger](p14b-ledger.md) separates actual qualification,
unavailable coverage and remaining owner/native gates.
Owner: primary agent, branch `feat/p14b-historical-replay`, issue #14. P14a is
owner-merged as cd6f46e; merged-main run 44232624596 attempt 2 passed before
production implementation. Original failed-attempt evidence is preserved;
the handoff stays uncommitted. Preserve A02–A07 and the P14 milestone design.

## Bounded behavior and exclusions

Implement explicit sealed archive selections and isolated local historical runs.
Reparse original Windows Security/Sysmon, OpenSSH9 and Linux audit bytes, evaluate
pinned rules and reconstruct original audit membership/closure/quality. No current-
policy selection, live timer regrouping, P05 import, source activation, API/UI,
search forwarding, deletion/retention or distributed/HA work. P14c and later bounded
archive interoperability still own those explicit milestone requirements.

[Closed contracts](../contracts/historical-replay/v1/request.schema.json) freeze
request, selection, run, result and commit 1.0.0. Request lists exact original run, producer/plan
hashes and units with input/output Kafka references (topic, offset, value digest).
Each audit unit's output references include its original manifest. Late preservation
units explicitly reference their original manifest; ended-run preservation explicitly
references its preceding original run-end control. All inputs/outputs are selected
from verified archive rows; no search projection or mutable query substitutes.

A unit is Windows, authentication, audit group or audit preservation. Each has a
stable caller label, at least one input and one output; source occurrence identities
and output document IDs cannot conflict within selection. Exact physical duplicate
outputs can be retained as origin references but cannot become additional logical
results. Distinct source occurrences never collapse solely because bytes match.
Every unit input shares the selected original run and every audit member must match
the exact original manifest order, full raw/context hashes and scoped audit key.

Seal verifies original wire hashes, registered objects/ranges, all selected output
references, source contexts and original processing results using the actual
supported historical executor. Missing inputs/objects/artifacts, incomplete logical
output closure, conflicts or incompatible processing fail before pin publication.
A selection records archive binding, exact original request, wire hashes, required
object hashes, executor/reader hashes and pinned container image. Its identity is
canonical sorted compact UTF-8 JSON SHA-256 without LF. Pins have separate exact-
file checksums and atomic fsynced directory publication under an exclusive replay-
catalog lock. The catalog is an explicit sibling root, keyed by archive binding,
not a new entry inside a P14a archive. Its publication never changes original
archive contents or requires the pinned P14a writer to understand a new layout.
Archive append remains permitted; an unchanged selected prefix remains verifiable.
No automatic deletion exists; P14c must require the explicit catalog and honor
its retained pins and active-run locks before introducing deletion. A missing
catalog cannot become evidence of no retention holds.

## Supported historical executable and trust boundary

Initially support exactly the accepted P13 JAR
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`,
profile `p13-runtime-51a984de/1.0.0`. Pin original plan bytes (maximum 4 MiB), its
bundle, rules/provenance, source/mapping snapshots, parser/normalizer/assembler/
completeness/evaluator/selector and enrichment attribution. Original P13 enrichment
has no external inputs; unknown external inputs fail explicitly. Wrong version
strings, changed artifacts and arbitrary Java/Python supplied by a manifest never
become an executable fallback. Future artifacts need explicit supported-profile
review and qualification, not automatic nearest-version adoption.

Build a small original Java executor JAR containing only its own history classes
and metadata copies of its controlling CLI, validator, lock and closed schemas.
Verify those controlling bytes against the pinned artifact before execution;
an incompatible orchestrator cannot silently continue a partial run.
Run it in an isolated JVM with the exact trusted original P13 JAR on its classpath;
verify the original JAR hash before class loading and enforce actual class origins.
No P13 producer/library bytecode or state serializer is changed. The archive reader
runs in a separate process, preventing its newer dependencies from shadowing the
historical classes. Both helpers have pinned artifact/image hashes, no network,
512 MiB memory, 320 MiB heap and bounded filesystem mounts; no arbitrary artifact
lookup, shell interpolation or user-supplied class entrypoint.

The pinned Flink base image supplies the original logging runtime on its fixed
library classpath; parser/evaluator/boundary classes must originate in the verified
original JAR. The bridge also invokes the original P13 input schemas and registered
object/range/framing resolver. These private APIs share the single-JAR pin and
maintenance boundary; no newer library approximates original admission semantics.

Windows and authentication use original pure adapters. Audit uses the original
Assembler's exact private `close` method with validated explicit original members,
key, context and frozen closure; never the live timeout grouping loop. This is a
narrow private-API bridge pinned to the single accepted JAR, analogous in version
maintenance cost to the existing P13-specific connector pin. Validate each original
raw/context through its original boundary, parse the actual original audit key,
check group/source/host/generation/run equality, then invoke the unmodified original
closure implementation. Its freshly produced original manifest must equal the
archived original byte-content projection before any replay output is accepted.
Incomplete and output-limit groups retain their original disposition.

Audit preservation uses original prepared admission against explicitly reconstructed
closed/ended knowledge where required; missing-identity/extraction failure uses the
actual original parser/boundary. A late member stays outside the historical group.
Unknown disposition or missing link/control fails. Transport-invalid Kafka frames
remain archived but are explicitly unsupported as executable units in this slice;
no fabricated normalized event is produced for them.

Recompute original tagged/detection/diagnostic or preservation outputs through the
original compact evaluator and compare the complete selected logical output set,
including manifest and attribution, with archive observations. This reproduction
comparison is not the independent semantic oracle: qualification also uses the
pre-existing frozen P11/P12/P13 field/count/membership expectations below.

## Replay identity, publication and resume

Use a fresh UUID different from the original run. Only derived replay contexts'
run fields change; originals, occurrence times, first observations, membership and
source bindings remain immutable. Re-run the original adapters/evaluator with the
new run, retaining original event/evidence identities for identical membership and
new run-scoped processing/detection/diagnostic/preservation IDs. Original manifests
remain origin links; derived replay manifests have explicit replay run/hashes.

Outputs are wrapped in a separate historical result envelope: version, historical
mode, selection hash, replay UUID, stable unit identity, original references and
actual reproduced native/integration outputs. Existing closed P13 1.1.0 objects
remain nested supported runtime-profile objects, never forwarded into production
topics/search or impersonating the original run. Unit identity is SHA-256 of the
canonical array [detectbridge.historical.unit/1, run UUID, selection hash, label];
its independent literal vector precedes code.

Each result has closed fields `version`, `mode`, `selection_sha256`, `run_id`,
`unit_id`, `label`, `origin`, `native` and `outputs`. `origin` retains the selected
physical references; native objects remain original adapter event/manifest/
preservation objects. Each projected output is `{kind,value}` with a supported
P13 route kind and its unchanged closed consumer schema. The wrapper's generic
nested object slots do not permit arbitrary payloads: verify their existing source
and integration schemas and re-execute/compare the complete result on resume.
Native event counts are at most one; audit groups have at most one native manifest.
The separate commit metadata records zero-based index, unit ID, exact result-file
SHA-256/byte length and previous commit identity (null only for index zero).
`commit.sha256` verifies the exact canonical metadata file including LF, while the
chain identity hashes canonical JSON without LF. Committed directories contain
exactly `result.json`, `commit.json` and `commit.sha256`.

Freeze a run specification before output; each unit publishes a complete private
result/state directory, payload/metadata/checksums and directory sync before atomic
rename and parent sync. Authoritative contiguous verified unit directories determine
progress, not an advisory checkpoint. Resume re-verifies selection, artifacts,
archive references and every committed unit, and rejects changed mode/run/selection/
artifacts/image/budgets/destination. Run specs bind the canonical absolute output
destination and fixed storage/reserve limits; relocated roots require an explicit
future migration, never silent adoption. Never adopt P05/P12/P13 or current-policy
checkpoints. A completed resume validates and appends nothing. One mutator per root;
no overwrite of committed output, silent repair or reuse of original run identity.

Create a helper container before starting it, with a deterministic catalog-owned
name and durable active marker. Under the catalog lock, stop surviving owned
helpers before cleaning unpublished work; killed parents and client timeouts cannot
leave a writer racing resume. Catalog publication is atomic. Foreign checkpoint
roots fail validation before lock creation. Storage scans reject unreadable
directories, and initialization cleanup treats root names literally.

`progress.json` is an atomic advisory hint after a unit commits. Resume ignores its
contents and rebuilds progress from verified units. Interrupted initial publication
may leave no run specification; repeat `run` only when initialization never
published one. Missing committed runs fail explicitly.

## Finite bounds and compatibility

At most 128 units, 1000 distinct wire references, 256 group members and 64 MiB
selected wire JSON, within the milestone's broader upper limits. Original evidence
object limits remain P14a's 128 objects/32 MiB each/64 MiB registered set. Request,
selection and per-unit executor input are bounded at 16/16/32 MiB; executor output
32 MiB per unit; complete replay storage 512 MiB with 128 MiB filesystem reserve.
Artifacts are explicit content-addressed local cache objects, at most 32 MiB each
and 64 MiB per set; container images remain external verified digest pins.
Source archive storage retains its 2 GiB managed budget. The replay catalog, pins,
cache/work/output share the separate 512 MiB bound; originals do not become
disposable on completion.
No capacity or unbounded outage claim follows from these serialized/storage caps.

Read original Kafka JSON values with the original producer's 1 MiB parser limit;
the archive's larger opaque wire allowance does not expand executable source
support. The original compact plan embeds its original rule YAML/provenance and
full mapping/source snapshots, so retaining and verifying exact plan bytes retains
those decision inputs. Only the original profile's empty external-enrichment list
is supported. Changed executable versions or nonempty external inputs require a
new explicit supported profile. Images must be digest-pinned and equal the trusted
local build pin; a selection cannot introduce its own executable image.

Extend the archive's narrow read interface and external pin catalog without changing its v1 wire,
metadata identity, producer configuration or restore bindings. Existing roots retain
pinned writer artifacts; readers support v1 and the separate verified historical catalog. P14a rejects
unknown root entries, so adding `pins/` inside an existing root would prevent its
exact pinned writer from resuming. The external catalog resolves that compatibility
constraint before code; it refines the milestone proposal's provisional pin layout
without changing A02–A07. Read-only archive export and catalog publication tolerate
concurrent immutable archive appends. No producer shares its filesystem. Add actual historical-replay CI only with implemented component and
runtime/fault qualification; shared affected contracts retain all consumer gates.

## Independent frozen expectations

The milestone H01–H08, R01–R04 and Q01–Q03 cases apply within the supported profile.
The [literal fixture packet](../contracts/historical-replay/v1/fixtures/expectations.json)
freezes original synthetic inputs, source-factory hashes, literal outcome counts,
eligible/incomplete memberships and late linkage before the executor exists.
Shared group field expectations apply to eligible groups; incomplete groups use
their existing source oracle's quality-dependent projection.
Reuse the literal P13 nine-rule fixture counts and P11/P12 source expectations;
private-recording archive-to-replay qualification remains pending for P14c and must
reuse the accepted twelve-rule P13d table, controlled catalogs and original
membership/late-link evidence. Never derive expected source fields,
counts or match membership from this new executor's output.

| ID | Requirement-derived input | Expected observation |
| --- | --- | --- |
| B01 | Eligible original audit group closed by timeout/boundary/end/resource | Exact original ordered members, closure, quality and fields; pinned rule results; live wall clock cannot change grouping |
| B02 | Incomplete group and original late member | Historical group stays insufficient and immutable; late row remains separately linked preservation |
| B03 | Interleaved hosts/generations/runs with equal serial/time | No cross-scope members; wrong-context/hash/order is rejected before pin/output |
| B04 | Security/Sysmon/auth positive, nonmatch, skipped, blocked, budget and native unsupported/extraction cases | Original frozen fields/counts/matches/quality; no inferred host, no conversion of preservation to nonmatch |
| B05 | Missing/changed plan/JAR/object/source snapshot, unknown enrichment or executor profile | Explicit preflight failure, no fallback or partially successful historical run |
| B06 | Missing selected output or changed manifest/member/wire hash | Selection cannot seal; same-total semantic mutations fail independently |
| B07 | Two runs of one selection | Stable evidence/event identity, disjoint run-scoped IDs, immutable originals and origin links |
| B08 | Kill during unit payload/metadata, before/after publication or advisory progress | Resume verifies exact contiguous committed units, no skipped source or conflicting overwrite |
| B09 | Changed run/mode/selection/artifact/image/limit/destination on resume; corrupt/missing committed result | Reject before append; completed resume appends nothing |
| B10 | Exact size/count boundaries and one over, disk/permission/sync failure | Finite preflight/backpressure or failed publication with originals retained; no truncation |
| B11 | Greater-than-nanosecond source time, signed 64-bit values, UTF-8/CRLF | Preserve original bytes/spelling through archive retrieval and original parsing within supported source grammar |
| B12 | Actual original-source Kafka → P13 → archive → seal → two historical runs | Independent original and replay source/count/membership/attribution/retrieval checks pass; no copied stored result presented as execution |

Before implementation, commit this design, closed schemas and independent identity
vector separately. Qualify actual Java parsing/evaluation and actual archive-to-replay
process interruptions; component/docs checks do not establish runtime reproduction.
Private originals require catalog/terms/bindings revalidation, remain ignored and
never enter public native CI. Owner review/merge and actual merged checks remain
separate. P14a's merged-main qualification must pass before implementation proceeds.
