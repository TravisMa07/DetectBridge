# P13b integrated runtime qualification

Base: owner-merged P13a #46, e09c271. Its exact PR head passed every applicable
native AMD64 check; merged-main 43954609201 was still running when implementation
began and subsequently succeeded before P13b runtime initialization. No merge
or release is authorized for this PR.

## Implementation and independent expectations

Owning design and literal counts were committed at 7476a1b before runtime code.
The isolated integration-job retains P12's prepared assembler transitions,
checkpoint-prefix release and absolute deadlines, with new P13 state/destination
bindings. Actual Windows and Linux adapters feed the compact evaluator before
proposal commit. Existing P12 implementation/checkpoints are unchanged.
Runtime tagged/detection/diagnostic profile 1.1.0 identifies p13-runtime/1.0.0;
P13a offline 1.0.0 schemas/defaults remain unchanged.

The initial membership-bit oracle assumed input filename order; inspection of the
compiler confirmed UUID-sorted serialized rules. Independently recomputed audit
skipped membership is bits 2,4,5,8 (0x134); literal counts were unchanged. Initial
model tests also exposed a copied quarantine category still naming assembly and
a strict JSON-node numeric-type comparison after restore. The runtime quarantine
schema now names integration, and recovery checks compare actual canonical sink
bytes plus original sequence/kind/key. These failures are retained as failed
attempts, not acceptance. Initial Markdown lint rejected an unquoted placeholder.

All dependencies reuse the existing 67 reviewed Maven coordinates and strict
checksums; the inventory adds actual module/configuration uses only. No new
upstream pin or fresh security-remediation claim is made.

## Current checks

The state-model, registered evidence, source/evaluation literal cases and artifact
checks have passed during implementation. Full locked repository/Java and actual
Docker qualification are in progress. Exact artifacts/results and any failed
runtime attempts will be appended before handback. No synthetic/component pass
establishes Kafka recovery, recorded-source or search acceptance.

P13c search and complete recorded source-to-search acceptance remain separate.
No throughput, archive, activation, API/UI or release claim is made.

## Retained early attempts

The first verify invocation failed before any runtime initialization because the
verifier imported audit fixture helpers from the wrong module. That import was
corrected; it is not runtime qualification. Adding the real fail-closed integration
job also correctly invalidated three older aggregate test fixtures that omitted
its applicability/result fields. Those fixtures now include explicit inapplicable/
skipped integration entries; the gate was not weakened. Logs remain local under
`.cache/p13b-*`. No original evidence or existing qualification project was changed.

The first initialized runtime attempt reached actual audit TaskManager recovery
and failed independent processing-identity verification: the Python oracle used
the P03 array identity helper without recursively sorting nested attribution keys.
Production identities already used canonical nested JSON. The oracle now follows
the frozen P13 canonical preimage and is checked against independent committed
literal identity vectors. No counts/source expectations or runtime policy were
weakened. This failed run is retained separately from later qualification.

The next initialized attempt passed audit TaskManager recovery, all baseline source/
evaluation/replay checks, explicit restore, exact incompatible-group rejection,
JobManager recovery and broker pause, then failed the sink stage with an unrelated
pressure-failure marker. Its original exception was retained only as a hash, so
that exact job failure is not assigned an unobserved cause. Inspection found reused
synthetic Linux cursor positions between fault cases; a new real-Machine regression
reproduces conflicting_redelivery for that collision. Fault cases now have disjoint
positions. Full original exceptions and acknowledged input references are retained
locally for subsequent failures. No producer-failure assertion was weakened.

Final qualification additionally requires each blocked checkpoint intent's exact
original member/event/input reference, a completed idle prefix before each fault,
and an expired audit group's closure by the first restored checkpoint. Inventories
carry bounded IDs/hashes and admission/deadline metadata, never evidence bodies.
The following qualification uses a newly frozen artifact with those observations.

An ingress review aligned the input topic's message limit with the 2 MiB internal
wire bound while retaining 4 MiB output headroom. This prevents Kafka accepting a
value beyond the bounded wire's capacity under the managed topic policy. The
actual runtime suite includes an acknowledged frame just over the 1 MiB JSON
limit and requires original-hash/location quarantine rather than an event, loss
or indefinite retry. This uses a newly frozen final artifact.

## Completed intermediate ARM64 runtime qualification

Code a50a687, project detectbridge-p13-test-73035eefc646: actual source/evaluation,
TaskManager, explicit/incompatible restore, JobManager, 40-second broker pause,
expired deadline at the first restored checkpoint and all seven required sinks
passed. There were 43 accepted inputs, 20 logical events, 102 logical documents
and 144 physical outputs; duplicates retained identical canonical bytes/IDs.
Blocked original-source intents were confirmed in completed checkpoints 38/45/52/
59/66/73/81 for tagged/detection/processing/manifest/preservation/quarantine/receipt.
Every original input was retrieved and rehashed. Metrics and payload-log isolation
passed. Only that owned stack/volumes were removed; original ledgers remain local.

Bundle `c7428de22979df1df05c696e6d7a433aecd3e424c36662091fa25464faaac4d4`,
JAR `25df4e83ff99bcb12fcb0269d8a8ace2f852f6cb9ca861a8680fff379cbb92b7`,
image `sha256:44677f5d93eca4ec405b4f5c075db38df0e8effb4404a01314b557f1a0ef0437`.
This is intermediate evidence, superseded by final ingress-bound artifact checks
below; it is not silently attributed to later code/artifacts.

## Final ingress regression and retained failures

Code 012056a passed locked check, Java, integration, Windows, Linux and assembly
checks serially, then built its frozen runtime artifact. The initial overlapping
Gradle invocations collided in generated test-result files; they reached no runtime.
Only generated integration test output was cleared before those serial checks.

Runtime project detectbridge-p13-test-21c3cea48595 passed the audit TaskManager
phase but failed publishing the new oversized-source probe. Its private Base64
IPC envelope exceeded the shared source mapper's 1 MiB string limit before Kafka
admission. A focused regression reproduces that rejection, then proves the separate
bounded 4 MiB IPC parser carries a 2 MiB source while source parsing still rejects
it. IPC duplicate keys, trailing values, nesting and total-size bounds stay strict.
The source JSON parser and wire/topic bounds are unchanged. The failed artifact
(bundle 39124a013b0536664425972f9bb77e3f402e3d5f168e20e7e3608224c23156bb,
JAR 065d833a20f5ac5611e88536efe5c1dafad1870fefcdcd9fecbb389e75663a3c)
is not a passing runtime qualification. Original inputs/acks/failure observations
remain local; its owned stack was removed.

Intermediate code a50a687 also passed all applicable native AMD64 CI checks in
43962035651, including the actual integration runtime suite. That result is
attributed to that code, not the subsequent ingress changes.
