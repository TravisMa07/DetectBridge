# Private worker activation

P15b1 is implemented with all fourteen bounded synthetic ARM64 runtime scenarios
passed. Native PR CI and owner review remain open; see the
[qualification ledger](p15b1-ledger.md). The frozen
[design](p15b-design.md), [contracts](../contracts/lifecycle-runtime/v1/README.md)
and [independent cases](p15b-expectations.md) define its intended boundary.
Use isolated finite qualification deployments until the dependent P15b2 archive
and replay profile is qualified. The original P14 archive and replay executors
do not accept the new lifecycle output envelope.

## Administrative boundary

`tools/lifecycle_runtime.py` supplies a trusted local Python administration API
and inspection CLI. It opens no management listener. A private owner account
controls the mode0700 deployment root and mode0600 private files. The nonsensitive
logger extracted from the verified runtime JAR is mode0444 inside that private
root and mounted read-only at Flink's selected configuration path. Each deployment has
one Ed25519 authority key; every explicit worker incarnation has its own ack key.
Keep these ignored private files outside Git and public qualification artifacts.
Candidate content cannot select an executable, key path, fault hook or endpoint.

Each worker uses a separate pinned compiler image through a private Unix socket.
The service has no network, broker access, signing keys or checkpoint storage.
It independently recompiles the embedded original YAML and compares the complete
plan before installation. A valid authority signature does not waive this check:
a signed plan with a forged AST is rejected. Compiler unavailability leaves the
last valid selection active and the new candidate pending. The artifact hash,
image identity and pinned base are part of the execution binding; see the
[validator boundary](p15b-validator-design.md) for framing and resource limits.

Prepare and stage candidates through the separate
[P15a lifecycle](rule-lifecycle.md). Preparation returns a proposal; it does not
publish desired state. The controller adopts an exact prepared proposal from the
actual locked P15a store and publishes a separately ordered signed command.
Its effective revision and complete command hash include registration and runtime
bindings. Preparation revision numbers are not effective publication revisions.

Publication, worker observation, application, completed-checkpoint durability and
read-back acknowledgment are separate facts. `status` reports the current exact
participant/incarnation obligations. `observe` verifies actual Kafka ack bytes
and advances its checked local cursor before committing the broker consumer
offset. Convergence requires a matching durable ack from every current participant.
It does not establish source completion, archive durability or indexing.

```sh
uv run --locked python tools/lifecycle_runtime.py status --root /absolute/private-runtime
uv run --locked python tools/lifecycle_runtime.py observe --root /absolute/private-runtime
```

After uncertain publication, retry the identical adoption. The controller retains
the same signed command bytes and does not allocate a successor until publication
is resolved. A finite observation deadline may report incomplete convergence;
it does not remove a missing worker or erase the failed attempt.

## Source ownership and replacement

Each stable worker owns a dedicated single-partition input topic and an isolated
one-JobManager/one-TaskManager cluster, with parallelism and slots fixed at one.
Worker management ports are private to Docker. Explicit signed registrations
assign sorted run UUIDs permanently to one stable worker. Omission disables fresh
work for that scope while preserving its state and Kafka backlog. Run-end and
source-boundary rows follow the same owner. No open-group resharding is supported.

The runtime captures one active selection when a source transition commits.
An open audit group can close under a later compatible selection; its original
membership and quality rules remain intact. Committed output retains its original
selection, incarnation, identity and bytes across later activation or rollback.
Rollback is a new forward command selecting an earlier published immutable bundle.
It does not rewind source offsets, assembly state or earlier output.

Automatic new-runtime restart is disabled. Explicit replacement must prove the
owned old cluster stopped, use a new incarnation/key and restore an independently
confirmed compatible completed checkpoint. It needs a newer signed membership
command before fresh work. Restored immutable intents keep their old attribution.
Checkpoint files or advisory inventory alone do not prove checkpoint completion.

## Qualification feedback

The default verifier runs all fourteen required scenarios. Focused groups use a
fresh real two-worker deployment to diagnose a single area without replaying the
entire passed prefix:

```sh
uv run --locked python tools/lifecycle_runtime_verify.py
uv run --locked python tools/lifecycle_runtime_verify.py --scenario-group mixed-workers
uv run --locked python tools/lifecycle_runtime_verify.py --scenario-group partial-recovery
uv run --locked python tools/lifecycle_runtime_verify.py --scenario-group checkpoint-timeout
uv run --locked python tools/lifecycle_runtime_verify.py --scenario-group hostile-ast
```

A focused success reports `partial_passed` and `full_gate: false`, with all remaining
scenarios explicit. Required CI permits only the full run. Results are never imported
from earlier attempts. Larger reads use the existing bounded APIs; all signature,
journal, exact checkpoint and immutable-output checks remain active.

Qualification source delivery uses a separately pinned batch helper, preserving
the original worker/compiler artifacts and fixed assembly deadlines. It forces
each actual broker receipt before sending the next record. Partial operations
retain their inputs and verified admission prefix; an uncertain operation blocks
fresh admission for that worker. Abort that qualification deployment rather than
automatically resend the suffix. See the [batch contract](p15b-batch-design.md).

## Finite storage and evidence

The controller and each worker store are bounded at512 MiB, with128 MiB free-space
reserve. Ordinary controller writes withhold32 MiB recovery headroom. Checkpoint
storage is separately bounded at1 GiB with192 MiB reserved per new checkpoint,
three retained checkpoints and one concurrent checkpoint. The frozen contracts
specify further record, transfer, queue, history and acknowledgment limits.

Exhaustion fails or backpressures visibly; retained history and required artifacts
are not automatically evicted. A raw Kafka value above the original2 MiB limit
remains size-blocked backlog. Invalid administrative records require durable
bounded rejection proof before advancing their cursor. Preserve private original
logs, actual broker locations, checkpoint completion proof and executable hashes
before recovery. Do not edit checked history or delete a lock to bypass an active
operation.

There is no HA, disk-loss, physical power-loss, unbounded-outage, rescaling or
throughput claim. Qualification is limited to the source, artifacts and scenarios
recorded in the ledger; complete P15 acceptance still requires P15b2.

Qualification ACK readback may explicitly use the separately pinned read-only
[ACK signature batch helper](p15b-ack-batch-design.md). It amortizes JVM startup
while retaining normal controller verification and durable-prefix handling;
signature verification alone is never checkpoint or convergence proof. Normal
controller readback remains on the original path without this explicit mode.
