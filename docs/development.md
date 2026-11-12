# Reproducible local development

P02 establishes build infrastructure, not application services. Supported development
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

`doctor` reports effective versions and pin drift; `check` runs repository hygiene,
Ruff lint/format checks and mypy; `smoke` compiles/runs temporary Java and compiles
TypeScript, also requiring invalid programs to fail. `verify` combines check and
smoke. No smoke program is shipped as a service or detection test.

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
Java 17. Root build has no application modules. Use Kotlin DSL for future builds.

The distribution and Wrapper JAR have independent official SHA-256 pins. The JAR
is the only allowed tracked binary and is still included in secret scanning.
Future modules must commit resolved dependency locks and Gradle verification
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
ARM64 checks qualify tooling only, not future runtime compatibility or throughput.
