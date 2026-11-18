# P14 design and qualification ledger

## Current boundary — 2026-11-18 UTC

P14 prerequisites are met. [Owning design](p14-design.md) and
[independent matrix](p14-expectations.md) are local proposals, authored before
production code. No P14 schema, implementation, freeze commit, runtime test,
semantic acceptance, PR, merge or release exists. The first concrete P14a
schema/vector freeze remains required before implementation. The local handoff
is intentionally uncommitted and must remain outside any publication.

Checkout inspection found `main` at
`07e53822dd8a5035125804321e5c852f9a466aef`, with only untracked
`docs/p14-handoff.md`. The handoff's described tracked completion edits were
absent in this checkout; none were discarded. Fetched `origin/main` is still
that exact qualified SHA. Created `docs/p14-archive-design` from it, preserving
the handoff unchanged. Completion records are reconciled locally against live
evidence, without rewriting historical failed runs or published history.

## Refreshed prerequisite evidence

- P05 remains complete in its local replay scope; historical/restored artifact
  mapping and exact runs remain in [P13 acceptance](p13-acceptance.md).
- Live PR #49 is owner-merged as `07e5382`, head
  `85818875576616e42aa26720dc74486f93b9655c`; inline review threads are empty.
  Its body and issue #13 record explicit bounded owner acceptance, including the
  private recorded AMD64 limitation. Issue #13 is closed.
- Actual merged-main push [44206958555](https://github.com/TravisMa07/DetectBridge/actions/runs/44206958555),
  attempt 1, is completed/success on exact `07e5382`, updated
  2026-11-18 00:43:43 UTC. All fourteen applicable jobs including required-checks
  succeeded; five acquisition/recorded opt-in jobs were deliberately skipped.
  This is direct merged-SHA evidence; tree identity does not transfer CI.
- Issues #1–#13 are closed, #14 is open. Project 4 shows P01–P13 Done and P14
  Ready. M0–M4 are closed. REST milestone open-item counters report 2/3 for
  M3/M4 despite the directly queried prerequisite issues being closed; no
  unrelated PR or future issue was changed to reconcile those counters.

Connector tools read issue/PR/review/job state. The commit-workflow endpoint
returned an empty list for this SHA despite the known run; direct `gh api` read
verified the run's exact SHA/event/attempt/conclusion. CLI readback supplied
project/milestone state unavailable through the connector. An initial unquoted
milestone URL hit zsh glob rejection; the quoted read succeeded. Neither read
error is a runtime qualification result.

## Implementation boundaries and remaining work

P14a owns archival durability/offset accounting and exact retrieval; P14b owns
sealed original-member pinned execution; P14c owns explicitly changed policy,
isolated resume and retention qualification. Milestone acceptance will require
an explicit requirement-to-evidence map across all slices. No circular dependency
on P15 activation, P16 coordination or a management API is introduced.

Before P14a production code: settle/freeze actual schemas and independent byte/
identity vectors as a distinct commit, then demonstrate meaningful behavioral
failures. Before P14b/c code: freeze supported executors, explicit membership/
schedule/output/state and retirement interfaces plus literal semantic cases.
Consequential architecture changes require owner discussion/ADR; merges/releases
retain separate explicit owner authorization. Existing P09–P13 bounded acceptance
is not reopened by P14's new tests.

## Local validation

On base 07e5382 with these uncommitted Markdown-only changes, macOS ARM64:

- `uv run --locked python tools/dev.py check` passed 169 Python regressions,
  contracts/catalog/dependency checks, hygiene/secrets, lint/format and types.
  Log: `.cache/p14-design-check.log`. Normal hygiene discovers tracked files.
- Explicit locked `check_repo.content_errors` validation included all untracked
  P14 Markdown files as well as tracked files; content and relative links passed.
- The installed locked Markdownlint 0.42.1 API, using the repository's config,
  explicitly checked all four P14 Markdown files, including the untouched local
  handoff; passed. The first API invocation used a nonexistent named export and
  failed before linting; corrected to the module's actual `lint` export.
- `git diff --check` passed. No production code, contract, dependency, CI job,
  private evidence or generated artifact was added to Git. No commits or remote
  mutations were made.

These are documentation/component checks. No P14 runtime, archive durability,
historical reproduction, power-loss, performance or new platform qualification
is claimed. Actual P13 merged-main qualification remains separately attributed
above; it cannot establish P14 archive behavior.
