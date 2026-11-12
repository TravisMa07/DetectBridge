# Development and contribution

DetectBridge currently contains its architecture and SDLC seed. There is no
application to start, dependency installation to run, or runtime test suite yet.

## Workflow

1. Select a deliverable from the [roadmap](docs/roadmap.md). Create an issue with
   behavior, exclusions, dependencies, open decisions, acceptance evidence, and
   compatibility/recovery implications.
2. Resolve implementation decisions in design notes before coding. Changes to
   accepted architecture require discussion with the owner.
3. Use a short-lived `feat/`, `fix/`, `docs/`, or `chore/` branch and open a draft PR.
4. Implement the bounded change with applicable tests, operational diagnostics,
   and documentation. Separate unrelated changes.
5. Explain resulting behavior, validation, and limitations in the PR. Add UI
   screenshots and contract examples when relevant.
6. Update the branch from `main`, pass checks, resolve review conversations, and
   obtain the owner's explicit merge authorization.
7. Squash merge, delete the branch, and verify checks on the merged commit.

The owner authorizes every merge. A solo workflow does not require a second
GitHub account's approval. Never interpret passing CI as permission to merge.

## Development environment

P02 introduces pinned toolchains: Python/uv, Java/Gradle Wrapper, and
TypeScript/npm lockfiles. P06 adds resource-limited Compose profiles. Commands
must be documented when introduced and must match CI. Do not install floating
versions as the project's reproducibility policy.

The full local stack targets an ARM64 laptop with 24 GB host RAM. Container
resource allocation is a P06 decision, not a verified bootstrap requirement.
Local model execution is optional and competes for that same resource budget.

## Current documentation verification

After initialization, run `git diff --check` for working changes and
`git diff --cached --check` for staged changes. Check relative Markdown links,
ensure status claims remain accurate, and review the staged file list before
committing. These checks do not validate the future application. P01 will
provide reproducible automated repository hygiene checks.

## Test and content expectations

Follow the [SDLC gates](docs/sdlc.md) and [third-party policy](THIRD_PARTY.md).
Use recorded public telemetry for integration scenarios and small synthetic cases
for targeted semantic/error behavior. Retain independent expected results.

Do not open public issues containing sensitive events, credentials, or exploit
details for a suspected project vulnerability; see [SECURITY.md](SECURITY.md).
