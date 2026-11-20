# Additive lifecycle worker

This module implements the bounded P15b1 worker/control slice described in
[the owning design](../../docs/p15b-design.md) and
[worker compiler addendum](../../docs/p15b-validator-design.md).
Full P15 and new-output archive/replay acceptance still require P15b2.

The normal `lifecycle-job.jar` contains only newly owned `Lifecycle*` classes,
versioned protocol resources and sanitized logging configuration. It runs with
the retained original integration producer
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`
in the same Flink user-code classloader. Startup checks both actual code-source
hashes. The original integration source/resources/JAR and old replay artifacts are
unchanged. Sharing the Java package permits use of original package-private
`Schemas` and `LocalEvidence`; no existing class name is replaced.

`LifecycleMachine` is an attributed adaptation of original `Machine.java` at
merged main `f44403e2975db46554c9c5033f87886d880c4087`, source SHA-256
`99da4b07ac830e5815e68a7d921b6964b40a0c7b92d1285e8dc67228f3a88128`.
It retains source assembly/quarantine and checkpoint/outbox algorithms, adds
closure-time immutable selection and versioned output envelopes, and keeps each
full original body once. Evaluator swap preserves actual pending checkpoint seals.

Production entry is `io.detectbridge.integration.LifecycleJob <worker-config.json>`.
Administration uses the fixed `LifecycleTool`; import/candidate content cannot
select Java classes, classpaths, algorithms or runtime hooks. Complete bundles
must pass the worker-initiated private UDS compiler protocol using the actual
pinned validator packet/image. No Python runs per event. Private controller/worker
files, keys, evidence, generated plans, runtime reports and builds stay outside Git.

A separate `lifecycle-probe.jar` contains the first-party
`LifecycleQualificationJob` entry point, a bounded UID diagnostic and the fixed
`LifecycleBatchProducer` qualification transport and read-only
`LifecycleAckVerifier` signature helper. Its explicit private operation modes hold
data release, target a ready current-incarnation checkpoint timeout, or fail after
an actual Kafka-acknowledged output write. Normal job configuration cannot choose
these hooks. A probe alone is not proof of broker failure or global checkpoint
completion; qualification verifies actual Kafka and Flink evidence separately.
The batch entry reuses Kafka clients while preserving per-record namespace checks,
forced attempts/ACKs/receipts and exact input bytes; it is absent from the production
JAR. Its [frozen contract](../../docs/p15b-batch-design.md) defines prefix recovery.

Run locked component tests with:

```sh
JAVA_HOME="$PWD/.cache/jdk" GRADLE_USER_HOME="$PWD/.cache/gradle" ./gradlew :lifecycle-job:test :lifecycle-job:jar :lifecycle-job:qualificationJar --offline
```

Test preparation compiles the separately frozen synthetic packet; it never
produces expected outcomes from evaluator output. Component tests exercise actual
Windows source adaptation and A→B→A matching, preserved old/new queued decisions,
checkpoint abort/restore, signing and identity boundaries, persistence, and a
real host Python compiler over UDS. Host compiler tests do not qualify the worker
container image or actual Kafka/Flink topology. Those require the owning runtime
qualification and evidence ledger.

Initial A/B source tests passed on their first execution and are green-only
evidence. Genuine failures preserved locally include numeric JSON-node equality
breaking restore of valid checkpoint bytes, and a signed self-consistent forged
AST replacing valid A before the independent worker compiler boundary existed.
Their corrected regressions pass; original failed XML/source hashes are retained
under ignored `build/evidence/`. Compilation/setup failures remain separate from
behavioral red evidence.

The ACK helper verifies at most128 bounded signed ACK wires in one JVM using the
unchanged production cryptographic verifier. It is explicitly enabled only for
qualification readback; every controller scope, identity, durable prefix and exact
checkpoint proof check still applies. Its [frozen boundary](../../docs/p15b-ack-batch-design.md)
and [independent cases](../../docs/p15b-ack-batch-expectations.md) define the limits.
