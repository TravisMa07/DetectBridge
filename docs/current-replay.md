# Explicit current-policy archive replay

P14c1 implements bounded offline evaluation of archived originals with an explicitly
selected new plan and admission schedule. It uses a verified P14b sealed selection;
historical outputs and original assembly membership remain unchanged. The
[design and frozen expectations](p14c1-design.md) and [qualification ledger](p14c1-ledger.md)
separate implementation from qualification and owner acceptance. P14 remains open.

## Prepare artifacts and inputs

Use the locked tools and available Docker engine to build the thin current
executor, historical helper and archive reader, and check packaging/components:

```sh
uv run --locked python tools/dev.py current
```

`uv run --locked python tools/current_replay.py build` performs artifact preparation
alone. Keep the generated `.cache/current-replay-build/bundle.json` and hash-named
artifacts available. The supported executable profile is exactly
`p13-runtime-51a984de/1.0.0`, backed by original P13 JAR
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
It uses the original parsers, assembler and evaluator; arbitrary replacement
executables or external enrichment are unsupported. Archive reading runs in a
separate process to keep its dependencies outside the processing classpath.

First [seal a historical selection](historical-replay.md) with the exact original
plan. For current evaluation, compile the explicitly chosen new rules, source
snapshots, mappings and provenance into a compatible v2 plan using the
[compiler commands](detection.md#p10-mapped-runtime) and preceding v2 compilation
instructions. Retain those inputs and their usage terms. The current request pins
the SHA-256 of the exact new plan file bytes, including any final newline; current
replay does not select or activate a policy automatically.

Prepare a closed [request](../contracts/current-replay/v1/request.schema.json)
containing all of these explicit fields:

- `version: "1.0.0"`, `mode: "current"`, the sealed `selection_sha256` and new
  `plan_sha256`.
- `engine_profile: "p13-runtime-51a984de/1.0.0"`,
  `source_policy: "preserve-original-context/1.0.0"`,
  `schedule_policy: "explicit-offline-clock/1.0.0"` and `enrichment: []`.
- All eight `assembler_limits`: `members`, `group_bytes`, `open_groups`,
  `pending_bytes`, `age_ms`, `runs`, `closed_keys` and `closed_bytes`, within the
  contract's bounds. There are no implicit request defaults.
- An ordered `schedule` of `{at_ms, action, input}` entries. Copy each exact
  `{topic, offset, value_sha256}` input reference from the sealed selection once.
  `input` admissions require that reference; `tick` and `end` require `input: null`.

Schedule times are integral milliseconds from Unix epoch, nondecreasing from zero
through 86400000; list order breaks ties. End exactly once, last, after every
selected source input. Original controls are not replayed automatically. A tick
advances processing at the specified virtual time without sleeping. The original
machine processes a deadline before an input at that same time. Moving an original
late audit member before a deadline can therefore change current membership;
[historical replay](historical-replay.md) preserves original membership instead.

## Run and resume

Use three disjoint absolute roots for the archive, existing historical catalog and
current workspace. None may contain another; symlink paths are rejected. The new
workspace's parent must already exist. Supply a canonical lowercase UUID distinct
from the original run and existing historical runs. Use fresh UUIDs across unrelated
workspaces; there is no global identity registry.

```sh
uv run --locked python tools/current_replay.py run \
  --archive /absolute/private/archive \
  --historical-catalog /absolute/private/replay-catalog \
  --workspace /absolute/private/current-workspace \
  --request /absolute/private/current-request.json \
  --plan /absolute/private/new-plan.json --run-id NEW_UUID
```

After interruption, replace `run` with `resume` and keep every argument and binding
identical. If no run metadata was published, repeat `run`; `resume` explicitly
rejects a missing run. One mutator holds the historical catalog and current workspace
locks in that order. Changed request, plan, artifacts, limits or destination fail
before appending transitions. No P05/P12/P13 checkpoint or historical cursor is
imported.

Each start executes the entire bounded schedule privately from empty new-run state.
Resume compares every committed transition byte-for-byte before adding any missing
transition. Results and actual post-transition machine state publish together in
fsynced directories under `current-workspace/runs/UUID/units/NNNNNN`; `commit.json`
binds the result hash/length and previous commit identity. Corrupt or gapped prefixes
fail. `progress.json` is advisory. Completed resume changes no run files.

Original raw/context bytes, original observations, occurrence timestamp precision
and historical outputs remain authoritative and immutable. Execution deep-copies
each input, changes its context run UUID and replaces its receipt with `received`
from the explicit schedule clock. Original processing receipts are not reused.
Linux's native projection retains that receipt inside its context extension;
the transition wrapper records `step.at_ms`. Derived processing/detection identities
belong to the new run. Internal wire positions are local admission ordinals, not
original Kafka acknowledgments. Outputs remain private files with no live Kafka or
OpenSearch publication.

## Bounds, diagnostics and qualification

The workspace cap is 512 MiB with a 128 MiB free-space reserve, including artifacts,
temporary work, results and failures. Conservative reservations can stop earlier.
Requests permit at most 256 source inputs, 512 schedule entries and 1000 original
references; request/plan sizes are 1/4 MiB. Engine input is capped at 32 MiB, state
at 16 MiB, each transition at 24 MiB and all unpublished transitions at 128 MiB.
The digest-pinned helper has no network, a read-only root, 512 MiB memory, a 320 MiB
heap, one CPU and 128 PIDs. Disk, permission or sync errors stop publication.
Process recovery does not establish power-loss or disk-loss protection.

Routine failure output contains fixed categories and exception classes. Retained
private diagnostics under `current-workspace/failures` can contain original values;
keep workspaces, originals, plans, artifacts and diagnostics outside Git and public
CI. Owned orphan helpers are stopped before unpublished work is cleaned up.

Run the actual synthetic archive/current replay qualification separately:

```sh
uv run --locked python tools/current_replay_verify.py
```

Serialize it with other heavy suites. It uses independent source/count/membership
expectations, actual original-JAR execution, isolated runs and publication/recovery
faults. Source/component checks alone do not establish runtime qualification;
report exact artifacts and platforms through the ledger. Controlled recorded
archive-to-replay qualification, retention/deletion, P05 import, activation, API/UI,
HA and throughput claims remain outside this slice.
