# Pinned historical archive replay

P14b adds explicit archive selections and isolated local historical execution.
It supports only the accepted P13 JAR `51a984de` (full hash in the
[design](p14b-design.md)); qualification and remaining gates are in the
[ledger](p14b-ledger.md). Current-policy regrouping, retention/deletion, P05 import,
activation, search forwarding, API/UI and HA remain future work.

Build the helpers and a default synthetic qualification plan with locked tools:

```sh
uv run --locked python tools/dev.py historical
```

For real historical evidence, use the exact original plan, including its embedded
rule YAML/provenance, source/mapping snapshots and version attribution. Supply a
closed [request](../contracts/historical-replay/v1/request.schema.json) naming the
original run, producer and plan hashes, and bounded units with exact archived
input/output topic offsets and original value hashes. Audit units include their
original manifest and exact ordered original inputs; late units name the original
manifest anchor. Ended-run preservation requires the preceding run-end reference.
No query or archive watermark alone establishes this complete dependency closure.

```sh
uv run --locked python tools/historical.py seal \
  --archive /absolute/private/archive \
  --catalog /absolute/private/replay-catalog \
  --request /absolute/private/request.json \
  --plan /absolute/private/original-plan.json
```

The seal receipt returns a selection hash. Sealing verifies archive integrity,
original objects/ranges, immutable memberships and the complete original logical
outputs by executing the exact supported producer artifact. Missing or incompatible
artifacts and conflicting or incomplete selections fail explicitly. Pin publication
follows successful verification. The separate catalog leaves the original archive
and its pinned writer unchanged; immutable archive appends remain independent.
An actively changing source may require retrying a failed read, never adopting an
unverified prefix. No automatic deletion exists; future deletion must coordinate
this explicit catalog and all its retained pins.

Choose a new UUID distinct from the original run:

```sh
uv run --locked python tools/historical.py run \
  --archive /absolute/private/archive \
  --catalog /absolute/private/replay-catalog \
  --selection SELECTION_SHA256 --run-id NEW_UUID
```

Use `resume` with the identical arguments after interruption. If initialization
never published a run specification, repeat `run`; a missing committed run is an
explicit failure. A catalog permits one
mutator. Run manifests bind the exact selection, artifacts, image, limits and
absolute destination; changed bindings or corrupted committed results fail before
append. `progress.json` is advisory; verified contiguous unit directories determine progress. Resume re-executes
and verifies committed results; a completed resume appends nothing. No P05/P12/P13
checkpoint is adopted.

The original parser/assembler/evaluator runs in a separate, digest-pinned container
without network access. Audit replay reconstructs original membership and closure;
live timing cannot add late members. Replay wrappers retain original references,
while derived processing/detection identities use the new run. Outputs remain
private files under `catalog/runs/UUID/units`; they are not published into live
Kafka or OpenSearch.

The catalog has a 512 MiB total cap and 128 MiB free-space reserve, including
artifacts, pins, work, results and retained failures. Conservative reservations can
stop an operation before the cap. Limits do not provide disk-loss protection or
unbounded outage capacity. Original evidence remains authoritative and separate.
Private originals, catalogs, artifacts and diagnostics stay outside Git/public CI.

Actual synthetic qualification, including source-to-archive-to-replay execution:

```sh
uv run --locked python tools/historical_verify.py
```

This uses an isolated P13 stack and original synthetic fixtures with frozen source
and rule expectations. Private recorded qualification is separately attributed;
public synthetic passes do not expand accepted P13 recording limits.
