# P15b1 independent worker compiler validation addendum

Owner decision on 2026-11-19: retain S12, including rejection of a validly signed
self-rehashed plan whose AST disagrees with original YAML. Controller validation
and signatures do not substitute for this worker check. This addendum is frozen
before implementing the new boundary; the earlier `0a41ee4` runtime freeze remains
historical evidence. This additional design commit is necessary because the
retained Java evaluator validates AST structure and hashes but does not recompile
YAML, and the existing Flink image contains no pinned Python compiler runtime.

## Artifact and deployment boundary

Use the existing compiler, never a duplicate Java implementation. The new first-party
validator packet contains its fixed Python service, unchanged compiler and validation
sources, their local schema/identity dependencies, the existing `uv.lock`, a hash-locked
runtime requirements export and its fixed Dockerfile. Deterministic sorted archive
members retain exact source bytes, modes and a checked file manifest. The packet
contains no candidate, evidence, keys, local environment or arbitrary plugin code.

Pin the Python3.12.12 image index:
`python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`.
Registry inspection on this date resolved AMD64 manifest
`2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301`
and ARM64 manifest
`228390eced221ad2986a3dd77e10b1accca6ba8ceb36f1572de1b346a337cc1a`.
These are provenance pins, not qualification. Install only the existing locked
compiler dependencies with verified hashes; no dependency download occurs during
worker operation. Runtime configuration binds the actual built platform image ID,
packet SHA and base index. Inspect image identity and source/base labels before use.

The closed `validator` descriptor is `{version:"1.0.0", artifact_sha256,
image_id:"sha256:<64hex>", base_image:<exact pinned reference>}`. Add it to the
common runtime binding preimage and trusted worker config. This makes checkpoint,
signed control/artifact and output execution scope inherit the exact validator
artifact and platform image. Independently refreeze binding vectors; retain their
original packet locally. Old producer, candidate and replay contracts remain intact.

Each isolated worker gets one validator container with512 MiB memory, one CPU,
64 processes, read-only root, no capabilities, no network and no privileges.
It sees only a dedicated private socket volume and a32 MiB temporary filesystem.
It cannot access worker keys, broker, evidence, bundle store or checkpoint state.
Run as the worker UID9999. The socket parent is0700 and socket0600. Inspect both
ownership and mode before Java connects. No TCP or management listener is added.

## Worker-initiated protocol and limits

Java initiates validation only for a complete candidate before immutable bundle
publication or selection. Use JDK17 Unix-domain sockets at the fixed trusted
`validator_socket_path` `/validation/compiler.sock`. Frame each canonical UTF-8
JSON message with an unsigned four-byte big-endian byte length. One request per
connection, one request executing at a time, backlog one. Request maximum8 MiB,
response maximum64 KiB, exact plan maximum4 MiB, total operation deadline10 seconds.
Decoded base64 must be canonical and match the independently computed plan hash.

Closed request fields are `version`, fresh UUID `nonce`, `plan_sha256`,
`plan_base64`, `validator_binding_sha256`. The last hashes the complete descriptor.
Closed response has the same fields except `plan_base64`, plus boolean `passed`
and fixed `category`: `ok`, `compiler_rejected`, `invalid_request`,
`validation_timeout` or `validation_failed`. Only true/ok with exact matching
nonce, plan and validator hashes establishes success. No raw source, YAML,
exception text or stderr enters the response or ordinary logs.

The service verifies its actual installed packet/source manifest and pinned Python
version at startup. It runs unchanged `lifecycle_validation.validate_plan`, which
recompiles embedded original YAML, source/mapping snapshots and provenance with
the retained compiler and requires complete plan equality. Enforce the operation
deadline and process memory limit; a compiler exception never becomes success.
No request selects a path, executable, module, dependency, endpoint or compiler mode.

Worker success proofs may cache only an actual successful exchange for exact
`plan_sha256` plus `validator_binding_sha256`, at most64 entries under the existing
store cap. Keep proof outside the immutable two-file bundle closure. Missing or
corrupt proof requires revalidation, never authority attestation. Unavailability,
timeout or failed validation preserves the prior valid selection and blocks the
candidate. Transient failure remains retryable with complete retained bytes;
cursor advancement cannot make a pending target permanently unrecoverable.

## Independent acceptance evidence

Before execution freeze a plan with original YAML intact and a changed AST whose
ordinary plan/manifest hashes are self-consistent. Actual signed transfer must
reach the worker's compiler boundary, fail recompilation comparison, preserve A,
and produce no successful B apply/durable acknowledgment. Test valid exact A/B,
wrong nonce/hash/binding, missing service, deadline, oversized frames, malformed
JSON/base64, private socket violations and packet/image mismatch separately.
Pure protocol and controller doubles do not establish actual sidecar execution.
Qualification records actual packet/image/base/platform identities and logs.
No new source coverage, event-time Python, archive/replay support or throughput
claim follows. P15b2 and full P15/P16 gates remain unchanged.
