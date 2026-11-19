# Private candidate lifecycle

P15a prepares immutable candidates with the retained Java evaluator. It does not
activate workers. [Design](p15-design.md), [independent cases](p15-expectations.md)
and [qualification](p15a-ledger.md) distinguish this slice from P15b activation,
convergence and rollback. P17 API/UI is not required to use this private CLI.

## Prepare files and authority

Use an approved mapped v2 plan from the existing compiler, retaining original
YAML, candidate provenance, licenses, source contracts and mapping declarations.
Do not import credentials or private source evidence into Git. Construct candidate
files in a fresh directory with:

```sh
uv run --locked python tools/lifecycle_validation.py /absolute/plan.json /absolute/candidate
```

This produces `manifest.json` and exact `plan.json` bytes. Candidate file creation
is not a durable lifecycle transition. The manifest has separate full-closure,
exact plan-file, semantic plan and compatibility hashes. Its sole plan member
includes YAML/provenance/source/mapping snapshots. Treat supplied plans as
untrusted until the later compiler validation and actual sample test succeed.

Retain the original integration JAR at its exact SHA-256 `51a984de…` from the
ledger. The trusted runner also verifies the existing locked SLF4J API 2.0.20
from the prepared Gradle cache. It never downloads runtime dependencies. Build and
qualify that artifact using `uv run --locked python tools/lifecycle_verify.py`;
this runs the synthetic preparation suite and writes ignored local evidence.
It does not qualify arbitrary imported rules.

Choose one authority UUID for a new private store and save the candidate's
`profile` object as a separate JSON input. The authority UUID is an identity;
Unix account ownership and mode 0700 provide local administrative authentication.
No listening endpoint is opened. Keep the store, candidate/suite inputs and
external JAR disjoint; use canonical paths without symlinks or `..` components.

```sh
uv run --locked python tools/lifecycle.py init \
  --root /absolute/private-store --authority AUTHORITY_UUID \
  --evaluator-jar /absolute/integration-job.jar --profile /absolute/profile.json
```

Initialization requires a fresh path. Never initialize over an existing or
partially initialized store; preserve failed initialization for diagnosis.
Source/mapping/profile compatibility is immutable within the store. A different
profile or deployment needs a fresh disjoint store.

## Lifecycle operations

Every mutation uses a request JSON conforming to
[the closed request contract](../contracts/lifecycle/v1/request.schema.json).
Its fields are `version: "1.0.0"`, authority UUID, request UUID, operation,
target full-closure `bundle_sha256`, and operation-specific `arguments`.
Request IDs are durable idempotency identities: reuse identical requests for
uncertain retries; changed content requires a new UUID.

```sh
uv run --locked python tools/lifecycle.py execute \
  --root /absolute/private-store --authority AUTHORITY_UUID \
  --evaluator-jar /absolute/integration-job.jar --request /absolute/request.json \
  --candidate /absolute/candidate
```

Use `--candidate` only for import; use `--suite /absolute/cases.json` for testing.
Validation, staging, retirement and preparation need no input directory.

| Operation | Prerequisite and observable result |
| --- | --- |
| `import` | Arguments bind exact input manifest/plan file hashes; immutable closure retained, no readiness inferred |
| `validate` | Recompile embedded original YAML/provenance/mappings and require complete plan equality |
| `test` | Validated candidate; exact suite hash; run fixed actual Java compact evaluator and compare complete independent expected JSON |
| `stage` | Validated candidate and latest actual passing test; explicit staging of those exact bytes |
| `prepare` | Staged candidate; compared preparation revision, complete command and explicit participant incarnations; immutable local proposal only |
| `retire` | No prepared reference; candidate becomes unavailable for new operations, bytes/history stay retained |

Test suites use [the suite schema](../contracts/lifecycle/v1/test-suite.schema.json).
They contain independently authored normalized events and complete compact
expectations, including eligible positive and negative cases. The runner does not
derive expected output. A passing suite proves its declared cases only. A failed
sample report is durably retained and exits nonzero from the CLI; it clears
readiness for new preparation until a new real test passes and explicit staging
occurs. Earlier proposals and reports are not erased.

Preparation reserves a local forward revision for one deployment and hashes its
predecessor. It does not install desired state, send Kafka control messages,
accept acknowledgments or establish activation. A proposal labeled `rollback`
likewise does not prove any worker rolled back. P15b must qualify those facts on
its own new runtime/profile before adopting prepared proposals.

Inspect only established facts with:

```sh
uv run --locked python tools/lifecycle.py status \
  --root /absolute/private-store --authority AUTHORITY_UUID \
  --evaluator-jar /absolute/integration-job.jar
```

## Recovery and finite limits

Every open verifies private ownership/modes, immutable files, complete checked
journal chain and exact executable dependencies. An uncertain operation may have
published a committed record before its head; recovery forces that journal entry
before repairing the head, and identical retry returns the original result.
An orphan immutable object alone does not prove import or staging. Corruption,
gaps, foreign files, incompatible identity or active locks fail visibly. Never
delete a lock file to bypass a live operation, edit checked records, or infer that
missing data means no references.

The store caps all retained data and temporary files at 512 MiB, reserves 128 MiB
filesystem free space, and permits at most 64 bundles and 4,096 journal records.
Tests reserve 24 MiB temporary headroom; each Java process has a 10-second deadline
and 2 MiB stdout cap, with stderr discarded. Other exact limits are in the design.
Exhaustion stops operations; no automatic history/bundle eviction occurs. P15a
never deletes prepared dependencies and has no release/garbage-collection protocol.

These bounds do not promise an unbounded outage, protection from external disk
consumption, physical power-loss or disk-loss survival, HA or throughput. Old
P13 checkpoints and P14 replay artifacts remain separate and unchanged. P15a
candidate tests do not establish new source coverage or worker runtime recovery.
