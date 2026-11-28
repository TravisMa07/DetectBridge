# P15b2 lifecycle replay profile

This design freezes an additive offline execution profile for P15b2 on
`3fe77bb`. [P15b](p15b-design.md), the [independent expectations](p15b-expectations.md)
and the [P14b membership](p14b-design.md) and [P14c1 schedule](p14c1-design.md)
rules supply its semantics. Qualification must identify the actual source and
artifacts used.

## Request and evidence boundary

Run and resume take the archive root, a separate private replay workspace, a
request and a canonical new run UUID. The caller supplies the lifecycle reader,
historical helper, current helper and original producer artifacts. The immutable
run specification binds their SHA-256 values, the controller and graph-verifier
source hashes, pinned Flink image, immutable archive manifest and prefix heads,
request hash, workspace and archive paths, run UUID and mode. A change to any
binding requires a new run. Artifact byte verification precedes execution.
Archive and workspace must be disjoint; path components cannot be symlinks.

The closed request contains `version` = `lifecycle-replay/1`, `mode`
(`historical` or `current`), `worker_id`, `original_run_id` and `units`. Each
unit contains exactly `kind`, `inputs` and `outputs`. Input and output references
contain exactly the physical topic name, offset and SHA-256 of the original
Kafka value bytes (`topic`, `offset`, `value_sha256`). Partition zero, cluster
and topic IDs come from the verified archive inventory. Supported unit kinds
are `windows` (one Windows record), `authentication` (one OpenSSH record) and
`audit` (ordered complete original member records and one original manifest).
All inputs belong to the selected worker's input topic and original run.
A request covers 1–128 units, 1–256 distinct inputs and at most 1000 distinct
physical references. A selected occurrence may appear in only one unit.
Unknown kinds, missing receipts, missing outputs, incomplete membership,
ambiguous routing, duplicate occurrences or contradictory decisions fail closed.

The lifecycle reader exports the manifest, heads and physical rows in topic then
offset order via `export ROOT`. `object ROOT SHA` supplies checked bytes.
The additive graph verifier consumes that manifest, row list and a private
hash-named object directory, and returns verified commands, bundles, inputs
and outputs. Materialize original references and registry objects from this
same archive. Bound the read to 4096 wire rows, 128 MiB of exported NDJSON and
32 MiB per original object; reject a larger prefix before replay. Require the
verified source receipt for each selected physical input. Archive receipts,
quarantine, preservation diagnostics and signed control/ack wires remain
authoritative observed evidence. This execution profile covers the three
specified semantic source unit kinds. The verifier must reject an unsupported
selected output rather than dropping it.

## Reproduction and explicit current policy

For each historical unit resolve every referenced envelope, verify the assigned
worker/incarnation and original run, and require one common recorded command for
its semantic outputs. The recorded revision, worker membership, command digest,
bundle, compatibility and plan hash must match the authenticated graph.
Different units can use different commands. Input receipt commands can differ
from the eventual audit closure command. A rollback to the same bundle retains
its distinct original command. Preserve physical reference, envelope output ID,
origin incarnation, inner stable key and exact body and semantic digests as
attribution for each selected output.

The pinned historical executor receives archived original rows in specified order,
the original complete inner output set, original run, new run and exact plan
bytes from that command's bundle. Its original-run execution compares the logical
output set and validates the ordered manifest against original raw records and
contexts. It then executes again for the new UUID. Isolation comes from the new
processing/detection identity and private destination. Original event identities,
record references and authoritative source timestamps remain available.
The controller carries original attribution alongside derived results without
impersonating the original worker or creating acknowledgments.

Current mode additionally requires `bundle_sha256` and `schedule`. The bundle
must be available and validated under the archive's compatibility profile.
Each schedule step has `at_ms`, `action` and `input` under the original P14c1
clock rules. Each selected source appears once; end once, last. Use original
assembler defaults (256 members, 1048576 group bytes, 1024 open groups,
33554432 pending bytes, 30000 ms, 16 runs, 100000 closed keys and 33554432
closed bytes), original source contexts, and empty enrichment. Verify historical
selection closure before executing the current helper. Start its assembler and
clock in a fresh isolated run. Preserve schedule order and selected bundle
attribution alongside each transition. The current helper reevaluates all
admitted inputs, allowing a changed result or membership. The only policy input
is the explicitly selected immutable bundle. No broker or worker state is an
executor input.

## Storage, isolation and qualification

The pinned producer, semantic helpers and Flink image use the exact identities
in [the original executable profile](../tools/archive_profiles.py). The lifecycle
runtime and validator identities come from the separately supported authenticated
deployment profile. Bind the new archive reader and controller identities in
each run and qualification report. Use the pinned offline JVM, 512 MiB memory,
320 MiB heap, one CPU, 128 PIDs and read-only artifact mounts. Enforce a 1 MiB
request limit, 4 MiB per plan, 32 MiB engine input/historical result, 512
current steps, 24 MiB per current transition and 128 MiB total current output.
Reserve 128 MiB free disk and limit the private workspace to 512 MiB.

One workspace mutator holds its lock. Use a fresh UUID distinct from archived
originals and existing runs. Publish each run specification and contiguous
numbered result with a synced temporary directory, atomic rename and parent
sync. A committed result binds the preceding commit and exact result digest.
On resume, reverify original inputs, closure, artifacts and run bindings;
reexecute and compare the committed prefix before appending. Reject missing run
specifications, corrupt or gapped prefixes, changed bindings and foreign state.
Completed resume writes no additional results. An interrupted unpublished
transition can be retried. Read-only archive access, no live Kafka output and
private results keep the source and historical runs separate.

Exercise crossed commands during mixed convergence, A1 and A3 rollback
attribution, exact audit member order, and current B versus original A on the
same evidence. Include omitted outputs and members, foreign worker/run,
incompatible bundle, modified pinned artifact, signed S12 invalid plan, fresh
identity and interrupted and corrupted resumes. Independent source-derived
expectations own semantic predictions. The ledger must identify actual platform
and artifacts for every runtime claim.
