# P14c2 managed retention, local import and final qualification

Status: owning design and independent expectations before production code.
Owner: primary agent, issue #14. Stack base: P14c1 #52 head
`8e4c832283268897887999efe22152b2f0b41eb5`; actual native run 44408227593
passed every applicable job, including current replay, on that head. The owner
explicitly authorized this final P14 slice to stack before parent merge. Neither
PR #52 nor CI repair #54 is merged or authorized to merge by this work.

Preserve A02–A07, the [milestone design](p14-design.md), existing contracts and
accepted P05/P12/P13 limits. This is the final implementation slice, with milestone
acceptance still a separate explicit decision. [Independent cases](p14c2-expectations.md)
and closed maintenance contracts must be frozen separately before production code.

## Scope and compatibility

Deliver explicit bounded retirement plans and resumable deletion, verified chain
anchors, active-reader/pin/hold blockers, finite admission headroom and P16 progress
interfaces. Add exact completed-P05 import/restore and controlled-original
source-to-archive-to-historical/current qualification. Complete the P14 acceptance
map. Do not implement activation, API/UI, Kafka deletion, distributed storage,
automatic expiry, throughput or local-disk-loss protection.

Introduce an opt-in `archive-managed/1.0.0` extension. Preserve archive v1's exact
wire/segment/object formats and immutable `archive.json` creator binding. A new
`archive-maintenance` JAR and controller own the extension; do not edit the legacy
archive writer, historical/current controllers, their schemas or original engines.
The original reader e5eaea35, historical executor 32bad6f5, current executor
ea9d4740 and producer 51a984de must rebuild unchanged. Full hashes remain in
[P14c1 qualification](p14c1-ledger.md). This avoids invalidating old controller
resource pins or adopting old checkpoints under new code.

The new module compiles only the unchanged legacy Format/Store/Main source files
as explicit generated build inputs, plus its own managed implementation and
ReplaySource entrypoint. It does not duplicate or modify original P13 classes.
Use only already reviewed Kafka/Jackson/schema/logging dependencies and licenses.
Its verified JAR embeds the new controller, contracts and legacy-source hashes.
Separate JVMs keep archive dependencies outside the pinned processing classpath.

Legacy archives and commands remain unchanged. Create a fresh managed archive,
or clone a fully verified v1 archive into a new, disjoint, atomically published
managed root. Never upgrade a live legacy root in place. Clone holds the original
archive's shared Java lease, blocking its writer while copying exact authoritative
bytes, and leaves its
original catalog/evidence untouched. It requires sufficient bounded headroom and
a fresh explicit destination catalog. A new managed UUID and distinct consumer
group prevent the clone sharing the creator's Kafka group. Original wire identities,
archive creator UUID/binding and offset history remain provenance, not fabricated
new Kafka occurrences. Old tools reject the managed extension explicitly.

## Layout, identity and coordination

Existing `objects/`, `segments/` and creator metadata stay intact. Managed roots
add `maintenance/` and `imports/`. Registration binds managed UUID, original archive
binding, exact managed artifact, canonical host destination and the one registered
historical catalog destination and private control destination. Physical roots must be disjoint; reject symlinks,
foreign entries and source/destination overlap before mutation. The catalog and registered control root must
exist and verify during maintenance; absence never means no holds. Initial creation
explicitly creates a fresh catalog. Registered source objects remain protected by
the immutable global registration/dependency set; no unsafe object reclamation is
claimed. Import objects have their own bounded dependency closure.

Lock order is P05 source-run lock (imports only), registered Python catalog lock,
then archive Java lock. Managed readers acquire a shared Java FileLock for their
entire export/retrieval; writers/retirement acquire its exclusive counterpart.
Do not mix Python flock and Java FileLock as if they were the same lock protocol.
The catalog lock covers sealing, historical/current execution and retirement
preflight/publication. An outer catalog lock may be reused only for that exact
already-held catalog by the single-process controller; never bypass it or start
concurrent controller threads. Active readers and mutators fail visibly rather
than spin or widen deadlines.

Managed replay uses explicit, temporary build-profile overlays selecting the new
reader and the unchanged pinned processing artifacts. Existing request/result/state
contracts and Java executors are reused verbatim. Verify the new controller against
the managed JAR, bind the exact reader in each sealed selection, and restore all
module build pointers/context after each call, including failure. Unmanaged CLI
profiles are neither overwritten nor silently migrated. The registered catalog
and managed instance must match before a managed operation starts.

A private operation lock is acquired before those data locks. It scopes helper
ownership to one explicit operation UUID. Recovery may stop only that operation's
verified orphan after acquiring its released lock; it must not kill another live
reader to obtain a deletion lease. Control inputs/derived indexes and bounded
private failures use the registered 32 MiB control root. Exhaustion blocks visibly;
there is no automatic diagnostic eviction. Source files mount read-only and are
streamed into archive storage, not copied unboundedly through control space.

## Plans, dependencies and retirement boundary

No default retention duration. The operator supplies an inclusive Kafka timestamp
cutoff, exact per-topic next-offset targets, operation UUID and a private reason.
Every candidate is a complete contiguous prefix segment at or above the current
retired floor. Every selected row must have a known nonnegative Kafka timestamp
at or before the cutoff; unknown timestamps fail instead of borrowing filesystem
mtime or source-event clocks. Empty read-committed intervals retain their explicit
metadata and can be retired without inventing rows.

A dry plan verifies the full bounded archive, current retirement/hold heads,
registered catalog, exact segment metadata/payloads and dependency closure. Freeze
those observations and hashes in a canonical plan before apply. Apply rechecks
all bindings, heads, holds, pins and payloads under locks. Any advancement or
changed input makes the plan stale; no automatic replan or broader selection.
Identical operation retries verify their committed plan; conflicting content never
overwrites it.

Deny a plan intersecting any sealed selection input/output/anchor/control reference
or an explicit external hold. Retained manifests, late links and derived references
must not lose selected identities. Conservatively treat a retained occurrence of
any selected run/record/event/manifest/processing/detection/diagnostic/preservation
identity as a dependency. Hash identity tokens in plans; ordinary host, policy and
rule IDs are not evidence identities. Retained quarantine/writer-failure rows or
unrecognized reference graphs block partial retirement. Unknown graphs may retire
only when the complete retained wire population is selected and no external hold
or pin remains. These conservative blockers are visible, not silently waived.

Preserve retired source identity/content fingerprints so later admission at a new
Kafka location still exposes conflicting raw/context content. Identical bytes at
new offsets remain distinct occurrences. Requests below a retired floor return
explicit `retired`, not not-found or an unverified successful retry.

Two-phase apply publishes one immutable retirement directory containing the exact
plan and chained record, syncs it and its parent, and advances a checksummed head
before deleting any owned file. The record defines each topic's next retained
floor and previous original segment hash. Retained segments keep their original
metadata and continue from those anchors. Kafka durable-next/head watermarks do
not roll back when a floor advances.

Only exact files named by that committed plan may be removed. Interrupted cleanup
finishes that same plan, syncs affected parents and leaves an advisory completion
receipt. Before record publication no evidence is retired; after durable publication
recovery never restores a retired payload or invents a new plan. A surviving rename
must be synced before cleanup resumes. Readers hide committed retired intervals
even when interrupted garbage remains. Missing/corrupt records, heads, anchors,
checksums, gaps or foreign partials fail closed. Required head files detect loss of
a committed last record; a stale head after interrupted publication is recovered
from verified contiguous records, never used to discard evidence.

Holds are explicit immutable revision records with a checked head, previous hash,
managed binding and scope (all, topic range, run, import or registered object).
Releasing a hold is an explicit compared-revision operation; deleting a file is
not a release. Plans pin the exact hold/catalog snapshot. P16 can consume archive
floors, durable/broker watermarks, lag, byte/reserve state and fixed blocker counts;
these are not permission to change Kafka retention or activation.

## Finite bounds and admission

Keep the existing 2 GiB archive/control-files cap and 128 MiB free-space reserve.
Withhold 64 MiB from ordinary managed admission: 32 MiB for the bounded external
control root and 32 MiB inside the archive for maintenance records/recovery. The
archive itself can never exceed cap minus 32 MiB, even while retiring; ordinary
admission stops at cap minus 64 MiB. Existing separate historical/current 512 MiB
catalog/workspace budgets and externally retained build/image hash pins remain
unchanged. Metadata/plans are at most 16 MiB; one plan has at most 256 segments.
Bound dependency analysis to 65,536 rows and 262,144 identity tokens, and retained
source fingerprint summaries to 131,072 entries. Exhaustion stops planning or
admission visibly; it does not drop old fingerprints or infer independence.
All records, anchors, imports, partials and advisory files count toward the cap.
A legacy clone lacking headroom is rejected before destination publication.
No resource limit is increased to make a failing qualification pass.

## Completed P05 import and restoration

Import only a verified completed committed P05 prefix ending in run_end, under
its original run lock. Reuse P05 load/config/input/segment validators, exact LF-
including digest rules, framing, source ranges, observations, timing and provenance.
Recheck approved frozen catalog/terms and all original payload/provenance hashes
without network acquisition. A missing/changed resource or unsupported catalog
fails before archive publication. The checkpoint is advisory; a valid absent or
behind checkpoint cannot replace authoritative committed verification.

Store original manifest/checksum, optional timing/checkpoint and segment payload/
commit bytes plus every source payload/provenance object in one atomic import
closure. Original capture objects remain in the exact original manifest. A separate
hash-bound framing index is explicitly derived from those original bytes. It never
becomes a replacement original. Each file is at most 32 MiB; retain P05's existing
100,000-record/512 MiB output and 64 MiB source bounds, at most 1,024 file descriptors,
and the archive cap. Import identity includes original run, exact manifest file
hash and sorted role/path/hash/length descriptors. Repeated identical imports verify;
changed or conflicting content cannot overwrite an import.

Restore to new disjoint roots only, preserving the original UUID directory name,
file bytes, source objects and provenance. Verify all objects/ranges and complete
P05 semantics before publishing the restored run. No original run is overwritten.
A later P05 execution may update its own restored advisory checkpoint. Import does
not manufacture Kafka offsets, P13 contexts, missing Windows host identity or a
P13 historical-processing claim. Whole imports may retire only after their own
holds/readers and exact closure checks; global registered archive objects stay held.

## Controlled-original qualification and completion

Use only the accepted originals named in the handoff. Preflight again before any
Docker/admission/archive mutation; freeze catalog hashes, terms, trusted bindings
and independent source expectations in private local reports. No recapture or
upload. Source counts are 5 Windows, 30 audit and 11 auth records, exactly 46 original
occurrences. A single original P13 run has one explicit exact redelivery, one
accepted controlled late cursor with unchanged original bytes, and run_end: 49
admissions. Keep the controlled cursor separate from the original 46.

Reuse the original recorded plan and RecordedOracle. Observe the selected audit
group's timeout and late link, then all original remaining sources; independently
verify original fields/contexts/quality/membership/counts/matches/versions. Archive
all physical inputs/outputs and registered originals through the actual managed
Kafka consumer. Seal complete logical units without converting exact redelivery
into a second source occurrence. Historical replay retains original membership;
two isolated replays and interrupted resume must reproduce the pinned decisions.

Current recorded replay explicitly uses the P14c1 Image/Bob plan. Reviewed auth
users are not Bob; the eligible audit executable is not the synthetic whoami
path. Expected eligible Linux counts are unmatched=1/inapplicable=1; skipped audit
is quality_skipped=1/inapplicable=1; Windows is inapplicable=2. Every other count
is zero, with no current detections. Preserve the original source fields/quality
and ten original audit groups. Use an explicit tick before the controlled late
cursor so the recorded current run preserves that original late relationship;
P14c1's separate synthetic cases already qualify changed membership. Original
catalogs predict 16 tagged events, 10 manifests, 13 preservations and nine quality
diagnostics for this current schedule (48 outputs; receipts are not current output).
These expectations come from accepted catalogs and the frozen two-rule source
order, never from the new archive/replay implementation.

Initial create/clone takes an explicit managed UUID, catalog, archive and control
paths. Publish bound control/catalog state before publishing the completed archive.
An interrupted initialization may resume only identical verified owned state;
missing/foreign control state is not an adoption opportunity. Clone takes a shared
Java source lease, copies no source partials, and requires original recovery if any
unpublished source transaction survives. No source file is removed or repaired.

Actual synthetic native CI qualifies managed Kafka/offset recovery, retirement,
shared-reader/pin/hold rejection, import/restore, corruption and interruption faults.
Controlled recorded qualification is local opt-in and separately attributed;
private native AMD64 coverage remains unavailable unless actually supplied later.
Restore the default integration build afterward. Map every P14 expectation to
exact artifacts/platforms/failures/limits in the final acceptance map. Passing
checks do not close issue #14 or authorize merging/releasing any stack layer.
