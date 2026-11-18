# Reproducible local development

P02 established build infrastructure; P07 adds real Java transport modules. Supported development
platforms are macOS ARM64 and Linux AMD64. Network access is needed for bootstrap;
Java smoke verification uses the populated Gradle cache offline afterward.

## Setup and commands

Install uv 0.13.6 from Astral's official distribution or an isolated package
installation. A Python interpreter must be available to start the command runner.
Then run:

```sh
python3 tools/dev.py bootstrap
python3 tools/dev.py doctor
python3 tools/dev.py verify
```

Bootstrap downloads checksum-verified Node and Temurin JDK archives into `.cache`,
installs project-local npm, syncs locked Python/npm dependencies and hygiene tools,
and populates Gradle caches. It does not replace system tools. Older bootstrap
Python delegates through uv to pinned Python 3.12.12. Downloads require network access.
Gradle setup retries explicit dependency HTTP 429/502/503/504 failures at most
three times, retaining every attempt under `.cache/bootstrap/gradle-help-*`.
Missing coordinates, integrity/compiler errors and runtime checks still fail.
See [bootstrap recovery and evidence](ci-bootstrap-recovery.md).

`doctor` reports effective versions and pin drift; `check` runs repository hygiene,
Ruff lint/format checks, mypy, offline contracts/catalog checks and Python regressions.
`smoke` compiles/runs temporary Java and compiles TypeScript, also requiring invalid
programs to fail. `java` builds/tests/packages the actual transport modules with
strict dependency verification. `verify` combines check, smoke and java. Smoke
programs establish tooling compatibility; they are not detection tests.

The authoritative pins and download checksums are in `tools/toolchains.json`.
Python uses root `pyproject.toml`, `.python-version` and `uv.lock`. npm uses one
root workspace/lockfile, including existing hygiene tooling. New packages go in
`apps/` or `packages/` only when implemented, and join the appropriate workspace.

## Lockfiles and updates

Use `uv sync --locked`, `uv run --locked` and root `npm ci`. To use project-local
Node/npm directly without changing shell configuration:

```sh
PATH="$PWD/.cache/node/bin:$PATH" .cache/node/bin/node .cache/npm/node_modules/npm/bin/npm-cli.js ci --ignore-scripts
uv run --locked ruff check tools
uv run --locked ruff format --check tools
uv run --locked mypy
```

Lockfile changes require explicit `uv lock` or root npm install with the pinned
npm version, followed by review and verification. Bootstrap must not regenerate
lockfiles. Checks never apply formatting fixes. mypy checks function bodies with
incremental annotations; this is not strict typing coverage.

## Java builds

Use the committed Wrapper exclusively, with `JAVA_HOME` pointing to `.cache/jdk`
and `GRADLE_USER_HOME` to `.cache/gradle`, as the command runner does. Gradle checks
Java 17, disables automatic JDK downloads, and configures future Java modules for
Java 17. The Kotlin DSL root includes shared transport validation, publisher and
Flink job, independent OpenSearch writer, detection evaluator and detection job
modules; no unused application modules are introduced.

The distribution and Wrapper JAR have independent official SHA-256 pins. The JAR
is the only allowed tracked binary and is still included in secret scanning.
All modules must commit resolved dependency locks and Gradle verification
metadata after reviewing dependency origins/checksums. No empty dependency lock
or application library is created just to make a check pass.

## CI applicability and limits

Every PR runs classification, repository hygiene and secret scanning. Only changes
entirely in Markdown or LICENSE skip Java/TypeScript smoke verification. Unknown
file types conservatively select toolchains. Classification failure or missing
output cannot permit a skip. The aggregate requires the selected job's success,
or its explicit inapplicability and skipped status.

Workflow setup pins must agree with the manifest. Retain read-only credentials,
SHA-pinned actions and owner merge authorization. Linux AMD64 CI and local macOS
ARM64 checks qualify tooling. Applicable runtime checks additionally qualify local
infrastructure and [transport recovery](transport.md) and the [writer](writer.md); none establish throughput.
See the [reviewed Java inventory](transport-dependencies.md) for dependency findings.

## Detection slice checks

`tools/dev.py java` prepares the synthetic plan, runs Java semantic tests and
checks the same evaluator through independent YAML-to-Java cases. Run
`uv run --locked python tools/detection.py build` then
`uv run --locked python tools/detection.py verify` for isolated Kafka/Flink
qualification. See [the detection guide](detection.md).

P10b adds `tools/detection.py --mapped build` and `--mapped verify` for the isolated
v2 runtime. Detection CI runs legacy and mapped qualification sequentially; the
existing fail-closed aggregate still gates the same real detection component.
See the [v2 detection guide](detection.md#p10-mapped-runtime).

## Windows adapter verification

`uv run --locked python tools/dev.py windows` builds/tests/packages the implemented
Windows adapter library, validates installed profiles/licenses and dependency lock,
runs independent verifier regressions and subsystem Ruff checks. `java` includes
its Java tests/installed artifact checks; `check` includes source/mapping/inventory
and classifier/gate tests plus subsystem lint/format. Mypy continues covering tools;
no blanket typing or runtime/performance claim is made.

The real `windows-verification` AMD64 job uses the same command and is selected by
Windows, shared event/detection contracts, compiler/evaluator/transport validation,
Gradle/toolchain and shared CI changes. The fail-closed aggregator requires it when
applicable and rejects unexpected skip/cancellation. Ordinary checks use original
synthetic bytes and never download telemetry. Recorded qualification is opt-in
against the reviewed local dataset cache; see [the guide](windows-adapters.md).

P12a adds `uv run --locked python tools/dev.py linux`: real Linux parser, bounded
assembly, offline replay and independent recording-verifier regressions, production
jar/notice/profile checks and subsystem lint/format. Root `java` includes Linux
alongside Windows and existing consumers. The fail-closed `linux-verification` CI
gate runs on the Linux subsystem and shared contract/compiler/build/gate changes.
Recorded payloads remain opt-in and absent from ordinary CI; see the
[P12a runbook](p12-runbook.md) and [local recording catalog](../catalog/recordings/README.md).

`uv run --locked python tools/dev.py assembly` checks P12b's real core/job,
serializers/resolver, independent oracle and fail-closed gate tests. Root `java`
includes its job build and resource/dependency checks. The separate
linux-assembly-verification required job also runs actual isolated runtime
qualification; see the [runbook](linux-assembly.md). CI targets main and concrete
check creation must be confirmed before claiming monitoring. Local recorded
payloads are not implicitly present or replayed in CI.

## P13a compact/offline output checks

`tools/dev.py java` includes compact/exhaustive Java comparisons and independent
YAML-to-Java semantic expectations, plus actual integrated Windows/Linux offline
consumer tests. Existing `windows`, `linux` and `assembly` commands retain their
checks. Integration schema changes select the real detection, Windows, Linux and
assembly gates; they do not create a placeholder P13 runtime CI job.

After `tools/dev.py windows` or `linux` installs the relevant distribution, append
`--integrated` to the Windows command after its mapped PLAN argument, or to the
Linux authentication/audit replay command after PLAN. Existing argument order and
legacy default output stay compatible. The option emits an `integration` member
instead of legacy `evaluation` on event rows. Raw/context, manifests and preservation
rows remain retained. See [P13a decisions](p13a-design.md) and
[qualification limits](p13a-ledger.md). Kafka/Flink commands are supplied by P13b
below; OpenSearch integration remains P13c.

## P13b integrated runtime

`uv run --locked python tools/dev.py integration` runs the implemented Java
state/source/evaluation/evidence tests, installed artifact/schema/license checks
and independent Python oracle/gate regressions. Root `java` retains existing
consumers and includes the new module; root `check` includes its schema/gate/
oracle/dependency checks. The real fail-closed integration-verification CI job
also builds and runs actual Kafka/Flink qualification.

Use `uv run --locked python tools/integration.py build` then
`uv run --locked python tools/integration.py verify` for the isolated P13b runtime
suite. Manual lifecycle: `tools/integration.py --project detectbridge-p13-dev init`,
then `start`, `status`, `metrics`, `stop`. Initialization optionally accepts
`--objects /absolute/path/to/registered-sha256-objects`; evidence is verified and
copied into the owned ignored project cache, never fetched from URI values.
Restart requires explicit `start --restore file:///state/checkpoints/JOB/chk-N`.
No P12 checkpoint adoption or old-project reset is allowed.

[Owning decisions](p13b-design.md) define schemas, limits and identity/restore
bindings; [qualification](p13b-ledger.md) records actual checks and failures.
Run heavy Docker qualification projects sequentially. New v1.1 runtime output
profiles retain unchanged P13a offline defaults. P13c search and full recorded
source-to-search acceptance remain separate.

## P13c search writer

`uv run --locked python tools/dev.py search` runs the actual Java projection,
protocol/TLS, installed artifact and independent Python vector/gate checks.
Build `tools/integration.py build` and `tools/search_writer.py build`, then run
`tools/search_writer.py verify` for actual isolated source-to-search qualification.
The new real search-verification gate is fail-closed; recorded original sources
remain a separate opt-in milestone gate. See [commands and limits](search-writer.md)
and [qualification](p13c-ledger.md). Existing P08 commands/configuration stay compatible.

## P14a archive checks

`uv run --locked python tools/dev.py archive` runs the real archive Java recovery,
byte/identity, format/corruption, source-reference, bounds and filesystem tests,
packaged schema/license checks and independent Python contract/gate regressions.
Root `java` includes the module and root `check` validates schemas/vectors and
fail-closed applicability. `tools/archive.py build` pins immutable production and
qualification JARs; `verify` exercises an isolated real Kafka/filesystem suite.
No private recording or P14b/c replay capability is implied. See the
[archive runbook](archive.md) and [evidence ledger](p14-ledger.md).

P14b [historical replay](historical-replay.md) uses two locked commands:

```sh
uv run --locked python tools/dev.py historical
uv run --locked python tools/historical_verify.py
```

The first builds the thin executor and archive reader, provisions the exact pinned
base image if missing, and checks contracts/packaging/components. The second runs
actual original-JAR parsing/evaluation, archive-to-replay isolation, publication
interruptions, helper recovery and an isolated original-source Kafka/Flink/archive
flow. Serialize this with other heavy suites. Synthetic qualification does not
establish private recorded or throughput coverage; exact evidence belongs in the
[P14b ledger](p14b-ledger.md).

## P14c1 current-policy replay checks

```sh
uv run --locked python tools/dev.py current
uv run --locked python tools/current_replay_verify.py
```

The first builds the thin current executor and original-profile helpers, checks
closed contracts and installed resources, and runs current component/gate tests.
The second executes actual archive/current JVM replay against independent source,
count, membership and attribution expectations, with isolated runs and publication
faults. Serialize heavy qualification with historical and other runtime suites.
The fail-closed `current-replay-verification` job runs both commands when applicable;
component checks alone do not establish runtime recovery. Private originals remain
outside public CI. See the [operator guide](current-replay.md),
[owning design](p14c1-design.md) and [qualification ledger](p14c1-ledger.md) for exact
bounds and separate acceptance gates.
