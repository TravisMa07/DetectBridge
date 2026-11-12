# Development and contribution

DetectBridge currently contains its architecture, SDLC, and repository hygiene
tooling. There is no application to start or detection-runtime test suite yet.

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

## Repository hygiene

Hygiene uses Python 3.12.12 and Node 24.22.3, independently of the future
application toolchains. Create an isolated Python environment, then install:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r tools/hygiene/requirements.txt
npm ci --prefix tools/hygiene
python3 tools/install_hygiene.py
python3 tools/check_repo.py
```

Native downloads are SHA-256 checked against committed manifests; supported
hygiene platforms are macOS ARM64 and Linux AMD64. Downloads require network
access. Missing dependencies fail with installation instructions.

Stage newly added files before verification: checks enumerate tracked files,
including staged additions, and inspect their current working-tree contents.
Use `--check content`, `--check markdown`, `--check workflows`, `--check secrets`,
or `--check tests` to select checks; repeat the flag to combine them. CI runs the
same commands. Secret scans cover reachable Git history and a temporary copy of
tracked current files, with redacted output. Downloaded/ignored data is excluded.

Markdown defaults apply except line-length and duplicate-heading limits. Local
file links and heading anchors are checked; external network availability is not
a merge gate. The link checker supports inline links and reference definitions,
ATX headings and explicit HTML anchors; extend it with tests before introducing
other Markdown constructs. LICENSE is exempt from whitespace rewriting.

Tests create temporary invalid configuration, links, and a generated dummy secret.
No live secret or intentionally failing fixture is committed. `required-checks`
fails unless both hygiene and secret-scan jobs explicitly succeed. Check versions
and suppression policies are reviewed in PRs; no broad scanner exclusions exist.

Native tool upgrades require reviewed checksum updates; Dependabot covers Actions,
npm, and Python dependency manifests. Actionlint's optional shellcheck/pyflakes
integrations are disabled so local and CI checks use identical installed tools.

See [GitHub setup and verification](docs/github-setup.md) for administrative work.
These checks do not validate the future detection application.

## Test and content expectations

Follow the [SDLC gates](docs/sdlc.md) and [third-party policy](THIRD_PARTY.md).
Use recorded public telemetry for integration scenarios and small synthetic cases
for targeted semantic/error behavior. Retain independent expected results.

Do not open public issues containing sensitive events, credentials, or exploit
details for a suspected project vulnerability; see [SECURITY.md](SECURITY.md).
