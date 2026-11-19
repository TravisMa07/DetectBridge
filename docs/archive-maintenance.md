# Managed archive operations

P14c2 adds the explicit `archive-managed/1.0.0` profile. Its
[design](p14c2-design.md), [expectations](p14c2-expectations.md) and
[qualification ledger](p14c2-ledger.md) own the delivery gates. The implementation
passed local ARM64 component, fault, approved-original P05 and controlled-recording
qualification. Exact native CI and owner/milestone acceptance remain open.
Existing [archive v1](archive.md), [historical replay](historical-replay.md) and
[current replay](current-replay.md) profiles retain their original artifacts.

## Artifacts and destinations

Build with `uv run --locked python tools/archive_maintenance.py build`.
The immutable managed/probe artifacts and exact original archive/historical/current/
producer artifacts are cached by SHA-256 in `.cache/archive-maintenance-build`.
Build the original historical/current profiles using their documented commands
before managed replay. Managed replay temporarily selects its reader and restores
those original build pointers afterward. The executing controller, contracts,
P05 validators and legacy-source proofs must match the managed JAR's resources.

Archive, catalog and private control roots must be physical, disjoint absolute
paths. Select explicit managed and operation UUIDs. Keep private source objects,
registries, control files and generated outputs outside Git. A registered catalog
or control root that disappears blocks operations; missing state is never treated
as an empty set of pins or holds.

Initialize a fresh instance on an existing owned, isolated Kafka project:

```sh
uv run --locked python tools/archive_maintenance.py initialize \
  --project "$PROJECT" --archive "$ARCHIVE" --catalog "$CATALOG" \
  --control "$CONTROL" --registry "$REGISTRY" --starts "$STARTS_JSON" \
  --provenance "$PROVENANCE_JSON" --managed-id "$MANAGED_UUID" --operation "$OP_UUID"
```

The registry contains original files named by their SHA-256. Starts select all nine
explicit Kafka offsets; provenance lists the registered provenance-object hashes.
Creation uses a fresh empty catalog. Alternatively, clone a fully verified legacy
archive into a new managed destination:

```sh
uv run --locked python tools/archive_maintenance.py clone \
  --source "$LEGACY_ARCHIVE" --archive "$ARCHIVE" --catalog "$CATALOG" \
  --control "$CONTROL" --managed-id "$MANAGED_UUID" --operation "$OP_UUID"
```

Clone holds a shared Java source lease, preserves original authoritative bytes and
creator binding, and uses a distinct managed consumer group. Source partials require
original archive recovery first. Resume initialization with the same operation and
identical inputs; foreign staging state is rejected. Existing archives are never
upgraded in place.

## Admission and progress

Every operation takes `--archive`, `--catalog`, `--control` and `--operation`.
`inspect` additionally takes `--project` to read actual broker watermarks/lag;
`drain` requires that project and archives its observed read-committed prefix.
Consumer commits follow durable segment publication. Archive durability, Kafka
acknowledgment, processing completion and search indexing remain separate facts.

Status includes retained floors, durable heads, active group, broker earliest/end/
committed offsets and lag when requested, archive/free/reserve bytes, admission and
maintenance headroom, hold/pin/fingerprint/cleanup counts and retirement sequence.
These vectors support later P16 coordination; they do not change Kafka retention
or activate policies.

The default archive cap is 2 GiB with a 128 MiB free-space reserve. A cloned
archive preserves its original finite creator cap; its maintenance headroom is
subject to that cap. Ordinary admission
withholds 64 MiB: 32 MiB for external control and 32 MiB for archive maintenance.
Plans/metadata are at most 16 MiB, plans select at most 256 segments, analysis scans
at most 65,536 retained rows, and identity/filesystem graphs are bounded by 262,144
entries. Retired source fingerprints retain at most 131,072 identity/content pairs.
Source objects remain protected globally. Exhaustion blocks visibly; control
failures and operation journals are retained rather than automatically evicted.
The existing separate replay workspace/catalog cap remains 512 MiB.

## Explicit retention and holds

A segment-plan request contains `operation_id`, an inclusive nonnegative Kafka
`cutoff_ms`, exact `targets` of `{topic,next}`, and a private `reason`.
Targets must end at complete prefix boundaries. Unknown timestamps, retained
references, sealed selections, holds, unknown partial reference graphs or exhausted
budgets block the plan. Graph recognition uses the pinned closed source schemas.
Unknown versions and arbitrary extensions block partial wire retirement; open
Windows contexts and preservation diagnostics are conservatively unknown. A
complete wire population can be selected only when the other hold/pin/reference
checks also pass. Original source fields remain observational data. A hold is an immutable compared revision, using the closed
[maintenance contracts](../contracts/archive-maintenance/v1/README.md).

`plan --request "$REQUEST"` writes the canonical plan in the registered private
operation directory and prints its hash/counts. Review that exact plan, then use
`retire --request "$SAVED_PLAN"` with the same operation UUID. Apply rechecks its
observations, hashes, holds and catalog snapshot; changed state requires a new
explicit plan. Identical committed retries verify the original plan. `recover`
finishes committed cleanup under its original operation lease. Durable retirement
records and heads precede unlinking, and retained original segment hashes remain
chain anchors. Reads below the retired floor return an explicit retired result.

`holds --request "$NEXT_HOLDS"` publishes an explicit next revision. Removing a file
is not a hold release. Whole-import planning uses `plan-import` with one import ID;
its cutoff is an operator marker, not a claim that P05 has Kafka timestamps.
Only descriptor-owned import files may be removed after committed retirement.
Retained unknown wire graphs also block import deletion; recognized references to
the import/run or its closure must be absent. Retire any independently eligible
wire population first, then explicitly replan the import.

## Replay and local P05 compatibility

`seal --request "$REQUEST" --plan "$ORIGINAL_PLAN"` seals exact historical units.
`historical --selection "$HASH" --run "$NEW_UUID"` executes those pinned units.
`current --workspace "$WORKSPACE" --request "$CURRENT_REQUEST" --plan "$NEW_PLAN"
--run "$NEW_UUID"` uses an explicit new policy/schedule in an isolated workspace.
Add `--resume` with the same operation/run to resume interrupted execution. Required
artifacts must exist and match; checkpoint or policy substitution is rejected.
Historical membership comes from original manifests, while current requests may
choose a different supported schedule and membership.

`import-p05 --run-dir "$COMPLETED_RUN" --data-cache "$SOURCE_CACHE"` verifies the
completed original run, current approved catalog/terms, source objects/provenance,
framing and committed prefix while holding its original lease. It stores unchanged
original files and separate derived framing/capture indexes. `restore-p05
--import-id "$IMPORT_HASH" --run-dir "$NEW_PARENT/$ORIGINAL_UUID"
--data-cache "$NEW_CACHE"` restores to new disjoint roots, verifies original P05
semantics before publishing the run, and resumes only its own descriptor-bound
staging. The P05 coordination lease file is not original evidence. Import does not
supply Kafka positions or missing P13 host/processing contexts.

## Qualification and private diagnostics

`tools/dev.py maintenance` builds and checks the artifacts/components.
`uv run --locked python tools/archive_maintenance_verify.py` performs the actual
synthetic Docker/Kafka/replay fault qualification used by native CI. Only its safe
summary and public-source build/image bootstrap diagnostics are published there.
Archive/helper error packets remain in the operation's private control root.

`uv run --locked python tools/archive_recorded.py --recorded --preflight-only`
checks the accepted controlled originals without starting runtime. Full opt-in
qualification removes `--preflight-only`; it uses the existing accepted originals,
restores the default integration build afterward, and keeps private packets local.
A separate worktree must pass the three original absolute paths explicitly using
`--windows`, `--audit` and `--auth`; do not copy or
recapture originals into a worktree. Actual platforms, artifacts, failures and
unavailable coverage are attributed in
the ledger. Synthetic checks do not replace recorded-source qualification.
