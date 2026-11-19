# Candidate lifecycle contracts 1.0.0

Original DetectBridge contracts, Apache-2.0. These are P15a pre-implementation
contracts, not evidence of implemented activation. See the
[owning design](../../../docs/p15-design.md) and
[independent expectations](../../../docs/p15-expectations.md).

## Manifest and fixed profile

`manifest.schema.json` is closed at every object boundary. Its fields are
`version`, `bundle_sha256`, `plan`, `profile`, `compatibility_sha256` and `members`.
The sole closure member is `plan.json`; mapped v2 plans already contain original
rule YAML/revisions/provenance and complete source/mapping declarations. The plan
reference carries both exact-byte `sha256`/`bytes` and the distinct semantic plan
`bundle_sha256`. Duplicate JSON keys, invalid Unicode, nonfinite numbers and
trailing tokens fail before schema validation. Serialized byte limits apply in
addition to JSON Schema.

The lifecycle bundle hash is SHA-256 of the canonical manifest with only its
outer `bundle_sha256` field removed. Canonical JSON uses UTF-8, sorted keys,
compact separators and unescaped Unicode. `compatibility_sha256` hashes the entire
canonical `profile` object. `profile.source_sha256` hashes the canonical plan
`sources` array; `profile.mappings_sha256` hashes the canonical plan
`mapping_profiles` array. Retain array ordering. Recompute these hashes and require
that `members[0]` equals the exact plan reference (with name `plan.json`), rather
than treating schema-valid hash strings as integrity evidence.

The trusted P15a executable is the retained producer artifact
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
It contains `io.detectbridge.detection.Evaluate`; invoke its fixed compact
interface with trusted local `--evaluator-jar` configuration. Candidate content
cannot choose a path, classpath, Java class, shell command or executable. Verify
this exact external artifact on every operation. It remains outside the candidate
closure. The profile's evaluator, selector, parser/normalizer/assembler-policy,
enrichment and finite limit constants match the existing implementation/design.
Their declarations do not transfer qualification to a new artifact.

The profile is closed with fields `version`, `evaluator_artifact_sha256`,
`evaluator`, `selector`, `parsers`, `enrichment`, `source_sha256`,
`mappings_sha256` and `limits`. The executable pin binds the actual existing
parser/assembler code as well as evaluator code. No declaration can make different
source/mapping/parser semantics live-swap compatible. A future P15b runtime/profile
requires its own design, measured artifact identity and qualification.

## Requests and preparation

`request.schema.json` fields are `version`, `authority_id`, `request_id`,
`operation`, `bundle_sha256` and closed operation-specific `arguments`:

| Operation | Argument fields |
| --- | --- |
| `import` | `manifest_sha256`, `plan_sha256` |
| `validate`, `stage`, `retire` | None: exactly `{}` |
| `test` | `suite_sha256` |
| `prepare` | `command`, `expected_preparation_revision` |

Import `manifest_sha256` hashes the complete exact supplied manifest bytes,
including its outer bundle identity. `plan_sha256` hashes exact supplied plan
bytes; both must agree with the manifest and outer request target. `suite_sha256`
hashes the exact frozen suite input file. Local input paths are CLI arguments,
not identity-bearing request fields. Actual test execution compares complete
compact output to separately frozen expectations. Caller-supplied passing receipts
cannot establish tested/staged state.

`prepare.arguments.command` fields are `version`, `authority_id`, `deployment_id`,
`request_id`, `revision`, `previous_sha256`, `action`, `bundle_sha256`,
`compatibility_sha256` and `participants`. Actions are `activate`, `rollback`,
`membership`. Participant pairs have UUID `worker_id` and `incarnation` fields.
There must be 1–16 unique worker IDs, sorted by worker ID; schema-level pair
uniqueness alone does not establish worker-ID uniqueness. The nested authority,
request and bundle identities must equal the outer request and trusted store.
Compatibility must equal the target manifest's recomputed profile hash.

The preparation sequence starts at zero; a successful command reserves
`expected_preparation_revision + 1`. The expectation must equal the verified
current preparation head. Command revision must equal the reserved successor.
Genesis revision 1 has null `previous_sha256`; later commands bind the previous
prepared command's canonical hash. All revisions are bounded by signed 64-bit
maximum; overflow is rejected. These equalities, sorted membership, compatibility,
byte budgets and readiness are semantic validations in addition to JSON Schema.

A prepared command is a durable local proposal. It is not installed desired state,
Kafka publication, worker application or convergence. P15b must reconcile proposals
with actual publication before adoption. No P15a operation accepts worker acks.
Retirement cannot invalidate any pending/prepared/recovery/hold reference, and does
not delete immutable bytes or history.

## Local authority and persistence

The authority UUID identifies the owner; it is not a bearer secret. The local
administrative authentication boundary is invoking Unix UID ownership and mode
0700 on the private root. Reject symlinks, foreign ownership, permissive roots and
another authority/profile before mutation. P15a opens no listening endpoint.

Every successful mutation is a checked hash-linked journal record retaining full
canonical request/result and their identities. Exact retry returns the original
committed result; changed content under the same request ID conflicts. Durable
object/record publication precedes atomic checked-head publication; verify the
entire chain on open. Recover at most the complete valid immediate successor of
a stale head. Gaps, conflicts, corruption and unknown files fail closed. No
capacity exhaustion silently evicts retained bundles or journal history.

These schemas cannot prove OS authorization, file durability, executable identity,
independent expectation provenance or worker runtime behavior. Those properties
require the owning implementation and independently attributed checks. No runtime
or performance validation is claimed by this contract freeze.
