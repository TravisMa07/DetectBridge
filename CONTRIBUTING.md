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

Use the [reproducible development guide](docs/development.md) for pinned tooling,
bootstrap, lockfiles, local commands and CI applicability. Start with:

```sh
python3 tools/dev.py bootstrap
python3 tools/dev.py verify
```

The existing `python3 tools/check_repo.py` hygiene entrypoint remains available
inside the locked Python environment. Stage new files before checks so tracked-file
verification includes them. Original license text is exempt from rewriting;
binary verification permits only the checksum-verified Gradle Wrapper JAR.

Documentation checks validate local file links and ATX heading anchors rather
than external network availability. Temporary negative fixtures contain no live
credentials. Follow [GitHub governance setup](docs/github-setup.md) for owner-run
administrative operations; they never run in untrusted CI.

## Test and content expectations

Follow the [SDLC gates](docs/sdlc.md) and [third-party policy](THIRD_PARTY.md).
Use recorded public telemetry for integration scenarios and small synthetic cases
for targeted semantic/error behavior. Retain independent expected results.

Do not open public issues containing sensitive events, credentials, or exploit
details for a suspected project vulnerability; see [SECURITY.md](SECURITY.md).

## Contract verification

`uv run --locked python tools/check_contracts.py` validates local schemas, source
profiles and synthetic examples; the developer check command includes it. See the
[contract field reference](contracts/v1/README.md) for version, identity, evidence
and time rules. Add positive and negative cases when changing a contract. Do not
regenerate expected identity digests using the implementation being tested.

## Dataset catalog checks

The developer check includes `uv run --locked python tools/check_datasets.py`.
Use the [dataset guide](docs/datasets.md) to acquire selected recorded evidence.
Normal tests use temporary synthetic bytes and loopback HTTP, not public download
availability. Catalog updates require pinned provenance, artifact-specific terms
review, and explicit payload/framing verification.

## Replay verification

The developer check includes `uv run --locked python tools/check_replay.py` and
synthetic timing/recovery tests. See the [replay guide](docs/replay.md) for the
separate opt-in recorded-data qualification. Normal PR checks do not download
public evidence or wait for real-time replay pacing. Keep P03 raw contracts
unchanged when extending replay-specific envelopes.
