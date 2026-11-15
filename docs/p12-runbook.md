# P12a offline Linux adapter runbook

This library implements offline parsing/assembly, not a deployed source, archive,
P13 pipeline or P12b Flink operator. Recordings, owner semantic review, shared
integration and AMD64 qualification remain acceptance gates. See the
[design](p12-design.md), [ledger](p12-ledger.md) and
[independent expectations](../packages/linux-adapters/fixtures/expectations.md).

## Build and verification

Use the pinned toolchains and a private mutable Gradle cache for this worktree.
Existing caches may be copied as download sources; do not share runtime state.
After the proposed root settings registration:

```sh
uv sync --locked
uv run --locked python tools/dev.py check
uv run --locked python tools/dev.py java
JAVA_HOME="$PWD/.cache/jdk" GRADLE_USER_HOME="$PWD/.cache/gradle" \
  ./gradlew --offline --no-daemon :linux-adapters:test :linux-adapters:jar
uv run --locked ruff check packages/linux-adapters/fixtures/prepare_cases.py
uv run --locked ruff format --check packages/linux-adapters/fixtures/prepare_cases.py
```

The module Gradle test task compiles four original synthetic YAML derivatives
through P10's real locked compiler, then tests actual adapter outputs through the
same Java Evaluator. Expectations are literal match/nonmatch/block/skip assertions.
Plans remain in ignored `.cache/linux-adapters/plans`. No Docker is used.
The root `java` command does not yet select this module; serial integration must
add its test task and CI applicability/gate as described in the
[shared handoff](p12-integration.md). Existing transport/writer/detection
checks must remain intact. Strict verification metadata is unchanged: all module
coordinates already exist in the reviewed dependency graph. A module-local lock
pins the configurations used here; orchestration owns consolidated inventories.

## Input contract

`Boundary.resolve(raw, context, resolver)` validates the P03 raw record and
[module-local context schema](../packages/linux-adapters/contracts/context.schema.json),
then invokes the explicitly supplied local evidence resolver. It verifies record
bytes/hash and declared range length. The resolver must independently verify the
whole-object hash, range bounds and immutable byte identity; a record hash alone
cannot prove the whole object. Resolver I/O/integrity errors propagate and are not
ordinary parser outcomes. No URI is fetched or transformation executed by the API.

The caller must retain each original raw envelope, context snapshot AND resolved original bytes
before admission, addressable by source/cursor/record ID and raw content hash.
The core does not implement an archive or promise upstream retention. Bounds use
manifest descriptors of those already retained occurrences, never invented object
URIs. For referenced evidence, descriptors preserve the exact original locator,
object hash and byte range. For inline evidence they refer to the retained raw
record with its byte hash and raw-envelope canonical hash. Do not discard retained
raw inputs or contexts after emitting a descriptor. Each descriptor binds the
exact context hash, including observation/receipt and provenance. Descriptors over
2048 serialized bytes refer to the complete retained raw/context hashes instead
of duplicating large metadata; no cursor or locator is truncated. This caps
256-member descriptor arrays below 512 KiB plus bounded manifest metadata. Normalized events retain unchanged P03
membership evidence; oversized normalized events produce a skipped manifest only.

Context version is exactly 1.0.0. Named members follow the agreed boundary:
run_id/source/first_observed; optional source_generation and host_binding;
source_contract/mapping_profile/parser; optional receipt. The module resolves the
previously unspecified nested shapes explicitly:

- source_generation: id and nonempty provenance-reference array.
- host_binding: id, revision, SHA-256 and nonempty provenance-reference array.
- source_contract: id/version/SHA-256 plus immutable snapshot.
- mapping_profile: complete pinned P10 declaration with own content hash.
- parser: id/version. receipt: received timestamp, when actually known.

Host/generation bindings are trusted reviewed caller input, never derived from
hostname, dataset ID, audit serial or capture ID. Tests use explicitly labelled
synthetic bindings. Declarations with unknown members/versions/snapshots/hashes
fail. Absent host/generation scope remains an identity_missing preservation result.
Raw+context sizes are independently bounded to 1 MiB and 64 KiB; parser token and
argument indices are bounded to 4096. No input is truncated to satisfy a bound.

Source/mapping files under the module contracts folder are **P12a proposals** with
new source IDs linux-audit-execution-p12a and openssh-authentication-p12a, each
1.0.0. They leave P03's existing fixture IDs/content unchanged. The small
contract-example files retain the existing original fixture-only parser attribution;
they test schema readability, not this parser's extraction or recorded acceptance.
Actual extraction tests use independently authored raw lines and expectations.
Image and auth User are qualified offline; CommandLine remains unsupported.
ProcessId/User audit aliases stay conservatively unsupported despite preserving
PID and source numeric identities. No username lookup or shell argument joining.

## Transactional assembly API

Construct `Assembler(clock, Limits.defaults())`. Call `accept(input, commit)`,
`tick(commit)` for injected processing-time expiry, `boundary(...)` for an exact
source/host/generation scope or `end(run, commit)` for explicit dataset end.
`end` retains tombstones and receipts; ended runs release active-run slots but
cannot admit new groups. Unknown keys after end are separate skipped diagnostics;
known closed keys still emit late links. There is no TTL or automatic key deletion.

The commit callback must atomically persist the complete output batch AND next
snapshot, throwing without either if unsuccessful. Return from the callback is the
admission boundary. Snapshot/output persistence failure leaves the live machine
unchanged; caller retains/retries the input as visible backlog. Idempotent exact
redeliveries do not call commit. Changed content or configuration for the same
run/record ID is an integrity error. A successful callback followed by process
failure must restore its durably stored next snapshot; restoring an older snapshot
requires caller-level transactional recovery, deferred to P12b.

Outputs are P03 normalized events, separately validated version-1 membership
manifests, or separately validated preservation diagnostics. Manifest descriptors
cover all members, closure, findings, exact key/provenance, source/mapping hashes,
policy/assembler and immutable event link when an event fits. Late associations
are separate diagnostic documents with original_manifest_id and optional
original_event_id. Original documents are not rewritten. `linux.context` is a
separately validated namespaced extension; P03 schemas/readers remain unchanged.
Diagnostic codes are value-free. Do not log source_fields or evidence bodies.

Resource pressure closes retained groups with resource_limit and skipped quality.
A single input larger than a configured group bound is preserved directly through
a skipped manifest without retaining an oversized pending group. Closed-key or
receipt-byte exhaustion stops admission; it does not drop/expire accepted evidence.
The 32 MiB pending budget counts serialized groups including contexts, byte
encoding, original metadata and the section wrapper. The independent 32 MiB
closed budget counts serialized closed keys, all receipt fingerprints (including
pending and diagnostic records), run lifecycle and state metadata. Conservative
double accounting is intentional. These are serialized state limits, not measured
JVM heap/throughput limits; working copies and output batches require additional
transient memory. Full state serialization is deliberately simple for offline
qualification; P12b must measure and bind any different serializer.

`restore(clock, limits, bytes)` rejects unknown state versions, changed policy/
source/mapping/limits bindings, malformed shapes, bad hashes, receipt/key mismatch
and exceeded bounds. Pure-state restart tests establish serialization behavior
only. They are not checkpoint recovery or Kafka exactly-once evidence.

## Recording research and unresolved evidence

The [reference review](../packages/linux-adapters/fixtures/reference-review.json)
pins reviewed primary source revisions and exact content hashes. Only metadata is
in Git; downloaded objects are under ignored `.cache/linux-references`.

Linux ABI/string/argument definitions were checked at Linux v6.12
adc218676eef25575469234709c2d87185ca223a. AArch64's generated table follows
arch/arm64/tools/syscall_64.tbl to scripts/syscall.tbl; ELF machine constants and
audit architecture flags are checked separately. Only factual execution numbers
and original decoding code are used; no upstream source implementation is bundled.
OpenSSH auth_log was checked at 9.9p2 commit
d76b2675116617394cd355a3437b4963a562b64d. OpenSSH per-file licenses and Linux
SPDX notices remain with local source downloads; reference links do not establish
recording redistribution permission.

The existing audit-whoami (3 records) and network-tools (25 records) catalog entries
establish bytes/positions and scenario provenance, not trusted host/generation or
complete execution membership. They cannot qualify eligible assembly as-is.
No dataset ID is promoted into host.id.

Two public candidates were investigated and rejected rather than changing scope:

- Loghub OpenSSH at dd61d0952749ee7963bde24220d1be5ede023033 declares lab
  collection but not the required OpenSSH9 capture identity/version. Its sample is
  RFC3164, includes excluded invalid-user/PAM grammar, and terms restrict use to
  research/academic work with notice and citation obligations. This is not a
  reviewed production acquisition source.
- Splunk Attack Data at the existing pinned 4b19e4b revision includes sshhole
  syslog.log (346 bytes, 3 LF records; SHA-256 in the review). The exact payload
  was verified against its LFS pointer and retained ignored. It is not RFC5424;
  scenario metadata does not pin OpenSSH9 or trusted host/generation. Root Apache
  2.0 and the complete ancestor inventory were checked; no additional applicable
  LICENSE/NOTICE was found. It was not added to the acquisition catalog.

These findings establish rejection of these candidates, not that no suitable
public artifact exists anywhere. No recorded auth acceptance is claimed.

## Proposed real opt-in capture

If no suitable primary artifact is approved, use a disposable isolated **Linux**
lab after orchestration schedules resources. This protocol is a concrete proposal;
it was not executed here and supplies no fabricated recording hashes.

1. Build actual unmodified OpenSSH portable 9.9p2 at
   d76b2675116617394cd355a3437b4963a562b64d and rsyslog 8.2502.0 at
   a2d0282d5b8202080713bafa7a722770250394c0. Pin the Linux image/toolchain/package
   digests before capture. Keep source licenses and compiler/configure flags
   locally. Record actual `sshd -V`, `rsyslogd -v`, binary hashes, libc/kernel and
   package/build manifests; version mismatch fails the proposed protocol.
   These are proposed source pins, not assertions about installed binaries.
2. Run daemon on loopback only, disposable non-root test account, password auth
   enabled, pubkey/PAM/keyboard-interactive disabled for the case, English locale.
   Retain exact daemon configuration and effective config output. Never retain
   passwords/private host keys in the review manifest. Use a disposable password
   supplied interactively to the actual SSH client, never a synthetic log writer.
3. Send exactly one accepted and one failed password attempt for that valid user
   over IPv4, then over IPv6 when available. Preserve complete original daemon/
   collector output, including unrelated/excluded lines. Retain client exit status
   and an independently written action ledger with attempt order and endpoints.
4. Collect actual local syslog datagrams in rsyslog through a private imuxsock
   socket, retaining original rawmsg bytes in one file and RFC5424 collector output
   in a second. Pin collector configuration and RFC5424 template byte hash. Record
   framing transformation ID `openssh9-rsyslog-rfc5424-lf/1.0.0`, exact input/output
   byte hashes, source-to-output membership, timestamp/hostname interpretation and
   LF boundaries. Do not relabel RFC3164 daemon bytes as original RFC5424 bytes.
   Collector version/configuration and framing are part of the evidence.
5. Record machine-id/boot-id or another explicit stable lab host binding with
   provenance and a separately recorded capture generation. A random capture UUID
   is not host identity. Retain first observations and do not infer capture times
   from publication metadata. Review original byte ranges/record IDs and literal
   expected username/outcome/address/port against the action ledger before parser
   qualification; reviewer records actual approval identity/revision.
6. Store evidence only in ignored `.cache/linux-recordings/<capture>/objects/sha256`.
   Pin immutable capture revision, bytes, terms/ownership/consent, daemon/collector
   provenance and independently reviewed expectations in a proposed catalog
   extension. Review capture output rights separately from software licenses.
   No payload may enter Git. Orchestrator reconciles schema/catalog/acquisition
   integration and owner review before any recorded-qualification claim.

An eligible audit recording needs an equivalent reviewed Linux capture with audit
configuration/rule inventory, trusted host/boot binding, syscall table version,
known successful execution action, exact complete record membership and independently
reviewed args/PATH counts. Existing excerpts remain skipped unless such provenance
is substantiated. Full P12 still requires P12a, separately authorized P12b and both
reviewed recorded acceptance gates; it does not unlock P13 here.
