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
Root `java` now selects this module; `tools/dev.py linux` is the targeted
developer/CI command. The shared handoff records the original child requirements. Existing transport/writer/detection
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
- host_binding: host_id/source/revision/SHA-256/provenance/kind, plus optional
  computer display context. Hash binds canonical content without sha256.
- source_contract: id/version/SHA-256 plus immutable snapshot.
- mapping_profile: id/version/sha256/declaration wrapper binding the complete
  pinned P10 declaration.
- parser: id/version. receipt: optional received/processed timestamps, when
  actually known.

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

These findings reject these candidates without claiming no suitable public artifact
exists elsewhere. The orchestrator completed the selected alternative below.

## Reviewed real opt-in authentication recording

The versioned local catalog pins an actual Debian bookworm ARM64 OpenSSH
9.2p1-2+deb12u10 and rsyslog 8.2302.0-1+deb12u2 capture from a disposable container
with no external network or published port. An immutable image was built from the
committed base digest and exact main package versions before capture. All resolved
packages, binary hashes, effective daemon config, image/container inspection and
upstream copyright notices are retained and hashed locally. This replaces the
child's unexecuted source-build proposal; it stays within the selected 9.x scope.

The committed capture tool generates one real accepted and one failed password
attempt for bridgeauth over 127.0.0.1, using a real SSH client. Passwords exist only
in process memory/stdin. Host keys/passwords are not copied; the container is
removed on exit. Docker's exact container identity binds the ephemeral lab host;
its actual start and one daemon invocation bind generation. No hostname or random
capture ID is substituted for identity. First observation records actual local
artifact acquisition, separately from source message timestamps.

All 11 native daemon messages and corresponding RFC5424 collector rows were
retained. The pinned collector template removes the native tag separator from
msg while rendering RFC5424, with exact body identity independently checked for
every row. Original native bytes are never relabelled as daemon-native RFC5424.
Two messages normalize as eligible password success/failure; nine unrelated daemon
messages are preserved unsupported. Both eligible events are independently
expected nonmatches for the original synthetic auth-user rule targeting alice.
Original synthetic cases separately exercise true matches and other outcomes.
No IPv6 recorded coverage, production distribution or performance is claimed.

Exact hashes, context and per-record expectations live in
[catalog/recordings/openssh9-password-lab-v1.json](../catalog/recordings/openssh9-password-lab-v1.json).
Payloads remain in ignored `.cache/p12-auth-reviewed-v1`. The local-use terms review
authorizes qualification only; public payload redistribution needs owner review.
To reverify retained originals and the frozen plan:

```sh
uv run --locked python packages/linux-adapters/recording/qualify.py \
  .cache/p12-auth-reviewed-v1 --prepare .cache/p12-auth-reviewed-v1/input.ndjson
JAVA_HOME="$PWD/.cache/jdk" packages/linux-adapters/build/install/linux-adapters/bin/linux-adapters \
  .cache/p12-auth-reviewed-v1/input.ndjson .cache/p12-auth-reviewed-v1/output.ndjson \
  .cache/p12-auth-reviewed-v1/frozen-plan.json
uv run --locked python packages/linux-adapters/recording/qualify.py \
  .cache/p12-auth-reviewed-v1 --input .cache/p12-auth-reviewed-v1/input.ndjson \
  --output .cache/p12-auth-reviewed-v1/output.ndjson --plan .cache/p12-auth-reviewed-v1/frozen-plan.json
```

`AuthReplay` accepts bounded NDJSON raw/context rows with retained inline UTF-8 or
base64 evidence. It uses the real adapter and mapped evaluator, retaining every
raw/context/result. Failed parsing/configuration/output publication leaves the
previous output intact. It does not resolve reference URIs or implement audit
replay/checkpointing. Reference evidence remains available through Boundary's
explicit caller resolver contract. The independent verifier checks all originals,
framing, expected fields/outcomes/quality/membership, exact frozen bundle and result
attribution. Payloads are absent from ordinary CI.

To create another recording, explicitly build the committed lab Dockerfile, record
its immutable image ID and invoke `recording/capture.py IMAGE_ID NEW_EMPTY_DIRECTORY`.
New bytes/identity require a new reviewed manifest; never overwrite this recording
ID or infer a new capture has identical hashes. No lab image or payload is published.

An eligible audit recording needs an equivalent reviewed Linux capture with audit
configuration/rule inventory, trusted host/boot binding, syscall table version,
known successful execution action, exact complete record membership and independently
reviewed args/PATH counts. Existing excerpts remain skipped unless such provenance
is substantiated. Full P12 still requires P12a, separately authorized P12b and both
reviewed recorded acceptance gates; it does not unlock P13 here.

## P12c reviewed audit recording and atomic offline replay

The [P12c ledger](p12c-ledger.md) records a real, bounded, locally reviewed native
audit capture. Its [catalog](../catalog/recordings/linux-audit-execve-lab-v1.json)
pins original auditd output, complete guest serial, guest boot/container identity,
zero-loss observations, source membership and local-use license provenance.
Original action expectations precede capture; per-record/group expectations precede
adapter/evaluator replay. Owner semantic/completeness acceptance is still pending.

The guest is a separate emulated kernel inside an unprivileged networkless
container. No host audit capabilities/devices/bind mounts are used. Building the
lab image is explicit; running capture requires an immutable image ID and a new
empty directory. New capture bytes require a new reviewed catalog, not automatic
promotion or an overwrite of this recording. Original payloads and guest/image
binaries must remain ignored. Primary sources and hashes are in its reference
review; exact binaries, package versions and notices are retained locally.

```sh
docker build -t detectbridge-p12-audit-lab:pinned packages/linux-adapters/audit-recording
uv run --locked python packages/linux-adapters/audit-recording/capture.py \
  sha256:REVIEWED_IMMUTABLE_IMAGE_ID .cache/NEW_AUDIT_CAPTURE
```

To qualify the existing reviewed originals, build with `tools/dev.py linux`, then
prepare exact retained raw/context inputs and copy a compiled plan to an immutable
local frozen-plan path before replay. Example for the positive probe rule:

```sh
uv run --locked python tools/linux_assembly_audit_recording.py \
  .cache/p12-audit-reviewed-v1 --prepare .cache/p12-audit-reviewed-v1/input-context-1.1.ndjson
cp -n .cache/linux-adapters/plans/audit-probe-match.json \
  .cache/p12-audit-reviewed-v1/frozen-audit-probe-match.json
JAVA_HOME="$PWD/.cache/jdk" packages/linux-adapters/build/install/linux-adapters/bin/linux-audit-replay \
  .cache/p12-audit-reviewed-v1/input-context-1.1.ndjson .cache/p12-audit-reviewed-v1/output-context-1.1.ndjson \
  .cache/p12-audit-reviewed-v1/frozen-audit-probe-match.json
uv run --locked python tools/linux_assembly_audit_recording.py \
  .cache/p12-audit-reviewed-v1 --input .cache/p12-audit-reviewed-v1/input-context-1.1.ndjson \
  --output .cache/p12-audit-reviewed-v1/output-context-1.1.ndjson \
  --plan .cache/p12-audit-reviewed-v1/frozen-audit-probe-match.json --rule audit-probe-match
```

Repeat with separately frozen image-nonmatch and command-blocked plans. Never
replace a reviewed frozen plan merely because compilation was rerun. The verifier
checks original YAML/revision, independent literal predicate, source/mapping
snapshots, bundle digest, exact counts/matches/diagnostics and input attribution.
For the unsupported CommandLine rule, configuration blocking precedes source-quality
skipping under existing P10 semantics; source quality remains explicitly skipped.

`linux-audit-replay INPUT OUTPUT PLAN` accepts bounded inline raw/context NDJSON.
It uses prepared transitions, a fixed offline clock and explicit dataset_end for
all admitted runs. It does not model processing-time timeout replay. It writes a
temporary file, forces it and atomically replaces OUTPUT only after successful
complete processing; malformed input, reference resolution requests, exhausted
state limits or evaluation/publication failures leave prior output intact. Output
must differ from both input and plan, including existing symlink/hardlink aliases.
It is non-resumable offline qualification, not a Commit API store or archive.

Each local output row has version=1.0.0 and kind=input/event/manifest/preservation.
Input rows retain raw and context unchanged; other rows contain document, and only
event rows contain a separate P10 evaluation. Every original input occurrence is
retained, even when adapter redelivery deduplicates its semantic output. This is
an owning-command format, not a new P03/P13 wire contract. P03 events and separate
module manifest/preservation/P10 result contracts stay unchanged.

The catalog records audit-recording-context/1.1.0: the original v1 script labelled
capture start as first_observed. Corrected envelopes use the original manifest
completion time as conservative complete-batch observation, not an invented per-row
receipt. Original source/manifest bytes and source-time fields remain unchanged.
Corrected processing uses a separate run ID ending 0014; old 0013 output snapshots
remain local and are not silently overwritten or adopted as corrected evidence.
