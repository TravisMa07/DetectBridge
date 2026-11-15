# P12a Linux adapter design

Status: implementation design, recorded before code on 2026-11-15. Owner authorized
dependent implementation after P10; no additional semantic approval is inferred.
P12b checkpointed Flink qualification requires a separately authorized P12a merge.

## Ownership and boundary

Base: `df3144822ddd5694b9244ae29eb4a3c9e2815376`. Linux owns
`packages/linux-adapters/`, this design and the Linux runbook. Shared integration
is a separate commit for orchestrator reconciliation. P03 remains unchanged.
Module-local Java APIs consume the exact JSON context in
[source-adapter-interface.md](source-adapter-interface.md). Context snapshots and
mapping hashes are bound on admission; immutable evidence is explicitly resolved
and verified. No competing shared library or production pipeline is introduced.

## Source review and fixed policy

Authoritative Linux reference: v6.12 commit
`adc218676eef25575469234709c2d87185ca223a`, specifically
[kernel/auditsc.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/kernel/auditsc.c),
[kernel/audit.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/kernel/audit.c),
[audit.h](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/include/uapi/linux/audit.h),
[x86-64 table](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/arch/x86/entry/syscalls/syscall_64.tbl),
[i386 table](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/arch/x86/entry/syscalls/syscall_32.tbl)
and [generic table](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/include/uapi/asm-generic/unistd.h).
Only execution pairs are supported: c000003e/59,322 (x86-64),
40000003/11,358 (i386), c00000b7/221,281 (AArch64). x32 is excluded.
Unknown ABI/syscall/type is unsupported, retained, and prevents eligibility.
These are factual numeric definitions; no upstream implementation is copied.

Audit strings are quoted literal bytes or even-length hex; no shell escaping.
EXECVE fragments use ordered aN[F], aN_len measures emitted characters (twice
bytes for hex), not decoded Unicode length. Decode after concatenating bytes;
non-UTF-8/NUL arguments remain preserved but cannot populate ECS strings.
PROCTITLE is preserved, never a replacement for missing EXECVE arguments.
All tokens, encodings, duplicate occurrences and PATH items survive in source_fields.

Auth reference is [OpenSSH 9.9p2 auth.c](https://github.com/openssh/openssh-portable/blob/d76b2675116617394cd355a3437b4963a562b64d/auth.c)
and [RFC5424](https://www.rfc-editor.org/rfc/rfc5424.html). Only the exact
Accepted/Failed password body is supported, with literal IP and port 1–65535.
Accept RFC5424 version 1, valid bounded header and structured data; preserve
header strings. NIL timestamp falls back to original first observation; malformed
timestamps are invalid. No DNS or hostname-derived host identity. APP-NAME sshd
or sshd-session is required (9.8 split); daemon version is capture provenance,
never inferred from message text. Other auth grammars remain unsupported.

## Assembly and durability

Key is run + source namespace/instance + reviewed host ID/binding + explicit
provenance-bearing generation + exact audit timestamp/serial. Missing scope emits
separate identity_missing diagnostics. Configuration is fixed per group; differing
context snapshots conflict rather than silently changing attribution.

Eligibility independently requires exactly one successful supported SYSCALL with
exit=0, executable and PID; EXECVE argc with all contiguous argument positions and
fragments/lengths consistent; exactly one CWD; SYSCALL items matching all contiguous
PATH item slots. Multiple occurrences of singleton/argument/path slots conflict,
even with identical bytes at distinct positions. EOE is closure only. Missing EOE
can still be structurally sufficient at explicit boundary/end/timeout; resource
closure always skips. No arbitrary file.path or synthesized command_line.

Bounds: 256 members / 1 MiB original bytes per group, 1024 open groups, 32 MiB
serialized pending state including contexts/evidence/encoding overhead, absolute
30s age, 16 runs, 100000 closed keys AND 32 MiB serialized closed-key knowledge.
Output documents have a separate 1 MiB bound; oversized output becomes a bounded
preservation diagnostic with membership references rather than truncated evidence.
Clock is injected. Pressure closes oldest pending groups as incomplete. Admission
stops if a closed-key/run budget cannot be retained. Closed keys never expire or
reopen, including after dataset_end; no implicit lifecycle garbage collection.

Each operation works on a private state copy. Caller-supplied commit must atomically
persist outputs AND next snapshot before success. A commit failure leaves in-memory
state unchanged and input visibly retryable. This is an offline transactional API
requirement, not a claim of an implemented durable sink or Flink recovery. Evidence
references already point at retained original bytes. Redelivery of a record ID is
idempotent only with identical immutable raw/context content; disagreement is an
integrity error. Late evidence emits immutable separate links, never mutating the
original manifest/event. Closed receipt knowledge is budgeted and backpressures.
State restore binds exact policy/state version and validates shape/bounds before use.

## Acceptance boundaries

Independent literal cases and reasoning precede implementation in
[expectations](../packages/linux-adapters/fixtures/expectations.md). Author review
of these expectations is pending. Synthetic qualification cannot replace reviewed
recordings. Existing audit excerpts lack trusted host/generation and completeness.
No suitable exact public auth recording has yet been substantiated; the runbook
records source research and a real instrumented capture proposal. This remains an
acceptance blocker. No P12 completion, checkpoint recovery, capacity or AMD64 claim.

## Review refinements

New source IDs ending -p12a explicitly distinguish module proposals from P03's
unchanged fixture contracts. Fixture-only schema examples are not parser outputs.
Manifest/preservation descriptors identify already retained original raw records
by ID, cursor, evidence hash and canonical raw-envelope hash; original reference
locators/ranges are retained unchanged. Inline descriptors do not invent locators.
The caller must retain the raw envelope, exact context snapshot and bytes before
admission. Descriptors bind both raw and context hashes; descriptors over 2048
bytes reference those retained objects instead of copying large metadata. This is the
fixed boundary's preservation prerequisite, not an archive implementation.

Ended runs retain lifecycle knowledge under the closed-state byte budget while
releasing active-run slots. The serialized pending budget includes its wrapper;
the closed budget includes receipts for all accepted records and state metadata.
The runbook records exact semantics and concrete recording blockers.

## Orchestrator reconciliation before acceptance

P12a is stacked above P11's review branch only to serialize shared integration;
Linux parsing has no semantic dependency on Windows parsing. Retain both modules,
all existing gates and exact P03 schemas. Align the module-local context proposal
with P11: mapping_profile is the id/version/sha256/declaration wrapper; host_binding
uses host_id, source, revision, sha256, provenance and explicit reviewed/synthetic
kind (optional display computer for Linux). Verify binding content hash and source
scope. source_generation retains id/provenance; receipt can hold actual received
and processed timestamps. No common unused adapter module or closed P03 revision.

The owner already selected a real reviewed authentication recording. Execute a
small isolated Debian bookworm OpenSSH 9.x/rsyslog lab instead of making capture
conditional on another authorization. Pin actual base digest and package/binary
metadata before authentication actions, isolate networking to container loopback,
use a disposable lab-only account, and retain no passwords/private keys. Define
one accepted and one failed password action independently before capture. Retain
all native daemon messages and RFC5424 collector output with versioned framing,
immutable hashes, host/container-generation binding and terms review. Runtime
capture is distinct from hand-written synthetic messages. New local recording
catalog metadata must identify opt-in local acquisition and must not imply a
public download or broad authentication/audit coverage.
