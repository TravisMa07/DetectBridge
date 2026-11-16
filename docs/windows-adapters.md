# Windows XML adapters and offline qualification

P11 provides an offline Java subsystem for the exact UTF-8 XML records described
in [the design](p11-design.md). It does not accept EVTX, JSON collectors, multiline
XML, Security versions other than 4688 v2, or Sysmon versions other than 1 v5.
There is no production Flink adapter pipeline, writer integration or throughput
claim. [The ledger](p11-ledger.md) distinguishes implementation and acceptance.

## Build and synthetic qualification

Use the pinned JDK, Gradle cache and locked Python environment from the
[development guide](development.md):

```sh
uv run --locked python tools/dev.py check
uv run --locked python tools/dev.py java
JAVA_HOME="$PWD/.cache/jdk" GRADLE_USER_HOME="$PWD/.cache/gradle" ./gradlew --offline --console=plain :windows-adapters:test :windows-adapters:installDist
uv run --locked ruff check packages/windows-adapters/*.py
uv run --locked ruff format --check packages/windows-adapters/*.py
uv run --locked python -m unittest discover -s packages/windows-adapters -p 'test_*.py' -v
```

The module test task compiles original synthetic YAML through pinned pySigma/P10,
then checks the same public Java evaluator on actual parser outputs. Independent
literal expectations include all six evaluator outcomes and full normalized
fixtures. Rule provenance must refer to committed bytes: commit new/changed
synthetic YAML before qualification. Plan preparation rejects a mismatch against
HEAD and Gradle includes the source revision in its task inputs. No public
recordings are required for ordinary tests.

## Module-local input boundary

`WindowsAdapter.adapt(raw, resolver, context)` consumes a validated P03 raw record,
an explicit evidence resolver and the exact context boundary. The local resolver
accepts an object directory containing files named by SHA-256; it never fetches
URI values or uses them as filesystem paths. Each resolution rehashes the complete
object (maximum 32 MiB), checks range and LF boundaries, dataset cursor position
and selected record hash. A custom resolver must provide the same verified-byte
guarantee. Resolver IOException is visible retry/backlog failure. Integrity failure
returns a value-free preservation diagnostic. The adapter independently rechecks
the supplied record-byte hash.

Context 1.0.0 has these concrete module-local shapes (no new shared schema):

- `run_id`, `source`, `first_observed`: frozen boundary values; origin and observation
  must equal raw input exactly.
- `source_contract`: `id`, `version`, canonical `sha256`, `snapshot`.
- `mapping_profile`: `id`, `version`, `sha256`, `declaration`.
- `parser`: `id: windows-xml`, `version: 1.0.0`.
- Optional `host_binding`: `host_id`, exact XML `computer`, `source`, `revision`,
  canonical `sha256` excluding itself, nonempty `provenance` string array, and
  `kind` (`reviewed` or `synthetic`). Source and Computer must agree. Checksums do
  not authenticate a binding: callers must substantiate review. Synthetic context
  cannot qualify recorded host identity.
- Optional `source_generation`: explicit `id`, nonempty `provenance` string array,
  optional `command_line_capture` (`enabled`, `disabled`, `unknown`).
- Optional `receipt`: actual `received` and/or `processed` UTC timestamps.

Snapshots/declarations must equal the module's parser-backed profiles. Unknown
members, versions, transforms, hashes and fixture-only profiles fail before XML
normalization. The fixed profiles declare Image, CommandLine, ProcessId and User
against actual extracted names. No arbitrary executable transform is supported.

Malformed/unsupported XML returns no event. A parsed supported event with missing
trusted host identity or invalid typed extraction remains normalized but skipped.
Computer is display only. Subject actor is distinct from target account. Command
lines remain literal strings; no argument tokenization. Empty optional command
line is legitimately absent unless reviewed context states capture disabled;
contradictory disabled context plus a present value is conflicting/skipped.

## Atomic offline output

Input is NDJSON with exactly `raw` and `context` per row. Run:

```sh
JAVA_HOME="$PWD/.cache/jdk" packages/windows-adapters/build/install/windows-adapters/bin/windows-adapters INPUT.ndjson OUTPUT.ndjson OBJECT_DIRECTORY .cache/windows/plan.json
```

The optional fourth argument is a validated mapped P10 plan. The complete-file
output contains version, original raw/context, and event plus optional evaluation,
or preservation diagnostic. Context remains beside the P03 event to retain exact
snapshot/binding hashes without changing closed P03 processing metadata. Explicit
output contains retained evidence; operational stdout prints counts only and
stderr fixed failure categories. Treat output as local evidence, keep it ignored.

The runner fsyncs a unique same-directory temporary file and atomically replaces
output after all rows complete. Invalid input, I/O, evaluator failure or interrupted
pre-publication leaves existing output intact and returns failure. A hard process
kill may leave a `.windows-*.tmp` file; it is never a published output. Remove such
files after confirming no runner owns them. Atomic rename is not archive durability,
whole-disk recovery or downstream acceptance. No non-atomic fallback is used.

## Opt-in retained recordings

Acquire only catalog-approved artifacts with the existing dataset tooling. This
subsystem performs no downloads. Prepare local inputs and independently inventory
all records, supplying an actual immutable first observation at raw creation:

```sh
uv run --locked python packages/windows-adapters/recorded.py --cache .cache/datasets --output .cache/windows/recorded-input.ndjson --first-observed ACTUAL_UTC_FIRST_OBSERVATION --run-id RUN_UUID
cp .cache/windows/plan.json .cache/windows/recorded-plan.json
JAVA_HOME="$PWD/.cache/jdk" packages/windows-adapters/build/install/windows-adapters/bin/windows-adapters .cache/windows/recorded-input.ndjson .cache/windows/recorded-output.ndjson .cache/datasets/objects/sha256 .cache/windows/recorded-plan.json
```

Freeze the compiled plan before a recorded run (for example copy it to
`.cache/windows/recorded-plan.json`) and use that copy for both the runner and
verifier. After publication, run the independent verifier:

```sh
uv run --locked python packages/windows-adapters/qualify.py .cache/windows/recorded-input.ndjson .cache/windows/recorded-output.ndjson .cache/windows/recorded-plan.json .cache/datasets/objects/sha256
```

It checks complete accounting, unchanged raw/context, original evidence hashes and
ranges, mapped source values, time representation/precision, identity, missing-host
quality gates, all six literal outcome counts, rule diagnostics and frozen bundle
attribution. Tampered output, missing/extra rows or a changed plan fails.

Preparation verifies payload, license, scenario metadata and LFS pointer against
the catalog, partitions original LF bytes and retains exact offsets/lengths/hashes.
Its ElementTree signature inventory is independent of the hardened Java admission
path; the Java runner establishes actual adapter disposition. No telemetry bodies
are printed. Outputs and raw inputs belong only in ignored cache.

Reverified inventory: Security artifact
`81e1d4e381f4dc38b97c48f9fa5b0ab0b098810c321b7d4599029a9f22530259`
has 8 supported records. Sysmon artifact
`ee1c7cd9fa20013c82da17f8cb1998197c117ab4c209ab56203290bc90739fda`
has 353 supported and 6,657 unsupported records. Total 7,018, with command lines
present in all 361 supported candidates. These are not per-record detection labels.

The pinned metadata object
`eebac0c9661cabf3b1bf36f200880516e19db43a1c3680ef17e6db43c78ac4f8`
identifies author, scenario, environment, dataset paths and collector sourcetypes.
It contains no stable host identifier or reviewed Computer-to-host binding. Neither
catalog capture identity nor metadata date can fill that gap. Preparation supplies
no host binding, so recorded candidates cannot become eligible. Full recorded
eligible qualification requires additional provenance-backed bindings; do not edit
input contexts to invent them. Synthetic disabled-capture tests remain necessary.

## Integrated developer and CI gate

```sh
uv run --locked python tools/dev.py windows
uv run --locked python tools/dev.py check
uv run --locked python tools/dev.py java
```

The Windows command runs the real Java tests, installDist packaging/profile/
license checks, five independent verifier regressions and subsystem lint/format.
CI uses the same command on AMD64, selected by owning/shared consumer changes and
required by the fail-closed aggregate. This does not establish P13 streaming
recovery or recorded eligible coverage. The distribution contains LICENSE and
ECS-NOTICE alongside original dependency JARs.

The independent recorded verifier checks the full source signature for every row,
including preservation rows, raw/event/result contracts, exact reference hashes
and complete input attribution. Supported records cannot count as unsupported,
and unsupported source versions cannot count as normalized merely to satisfy
aggregate totals. No host binding is invented to turn skipped into nonmatched.

P03 evidence can carry the original UTF-8 XML as inline text, base64 inline bytes,
or a locally registered object reference. Representation decoding precedes strict
XML UTF-8 validation. Allowed URI schemes compare case insensitively; locator
spelling is preserved. Content-addressed URNs retain their canonical spelling.

## Controlled recording with reviewed identity

The older public recordings remain an identity-missing preservation corpus.
The new [controlled capture](p11-recording-design.md) and
[owner review packet](p11-recording-review.md) add a separate real Windows source
scope with actual registry/VM/capture provenance. They do not change old contexts.
The [metadata catalog](../catalog/recordings/windows-process-lab-v1.json) contains
hashes, independent expectations and technical review, with owner acceptance separate.

Capture is opt-in through Repository hygiene workflow_dispatch's `windows-recipient`
input: supply a base64 DER public RSA certificate with key-encipherment usage, at
least 3072 bits, and keep its private key local. The disposable windows-2022 job
verifies the pinned Microsoft Sysmon package/signature, temporarily enables process
and command-line auditing, runs the controlled actions and restores its changes.
It refuses a non-GitHub Windows host or preexisting Sysmon. Only CMS AES-256/RSA
ciphertext is uploaded; failed attempts also retain encrypted diagnostics when
encryption succeeds. No plaintext fallback exists. Use a fresh recipient and local
evidence directory for each acquisition; do not replace the accepted catalog in place.

Download the named `p11-controlled-windows-encrypted` artifact using authenticated
GitHub access. Retain its API metadata/digest and original transport ZIP, the run
and successful capture-job JSON, ciphertext and decrypted ZIP together. Verify the
transport ZIP's SHA-256 against the GitHub artifact digest before decrypting with
OpenSSL CMS (`cms -decrypt -binary -inform DER`). Validate archive member names,
uniqueness and total expanded size before extracting. Keep all of this ignored.
The accepted acquisition layout is `.cache/p11-windows-capture/attempt3/` containing
`run.json`, `job.json`, `artifact.json`, `transport.zip`, `recording.p7m`,
`originals.zip`, and extracted `originals/`. Exact hashes bind these retained files;
do not replace API metadata with a later response or silently reuse another run.

`recording.py --candidate ... --run ...` creates a candidate only. Review original
host/process/actions, terms and native fields, then freeze a separately reviewed
catalog before evaluation. Candidate status cannot prepare inputs. Technical source
review does not approve owner semantics or claim complete host-wide telemetry.

For the retained accepted acquisition:

```sh
uv run --locked python packages/windows-adapters/recording_plan.py .cache/p11-windows-capture/frozen-plan.json
uv run --locked python packages/windows-adapters/recording.py .cache/p11-windows-capture/attempt3/originals --catalog catalog/recordings/windows-process-lab-v1.json --prepare .cache/p11-windows-capture/input.ndjson --run-id 9f1b3d5b-9c90-4ba9-8e28-d48916042b35
JAVA_HOME="$PWD/.cache/jdk" packages/windows-adapters/build/install/windows-adapters/bin/windows-adapters .cache/p11-windows-capture/input.ndjson .cache/p11-windows-capture/output.ndjson .cache/p11-windows-capture/attempt3/originals .cache/p11-windows-capture/frozen-plan.json
uv run --locked python packages/windows-adapters/recording.py .cache/p11-windows-capture/attempt3/originals --catalog catalog/recordings/windows-process-lab-v1.json --input .cache/p11-windows-capture/input.ndjson --output .cache/p11-windows-capture/output.ndjson --plan .cache/p11-windows-capture/frozen-plan.json --run-id 9f1b3d5b-9c90-4ba9-8e28-d48916042b35
```

Freeze the compiled plan once and reuse it; verification binds its committed rule
revision independently of later documentation commits. To qualify isolated replay,
use a distinct UUID and separate input/output files with the same originals/catalog
and frozen plan. Raw/event identities must stay stable and result identities must
stay isolated. Ordinary CI runs the synthetic verifier/adapter regressions without
access to local decrypted recordings; it does not claim this opt-in recorded run.
