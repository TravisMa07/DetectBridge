# Software development lifecycle

## Governance and planning

Use a public GitHub monorepo, Apache 2.0 for original work, GitHub Issues and
Milestones, and a project board with Backlog → Ready → In progress → In review →
Done. Mark blocking dependencies separately without obscuring workflow status.

Milestones define demonstrable outcomes. Issues define bounded deliverables and
owning PRs. Architectural decision records retain consequential choices and their
history. The [roadmap](roadmap.md) assigns open implementation decisions to PRs.

An issue is Ready only when behavior/exclusions, dependencies, interfaces,
decisions to resolve, acceptance evidence, and relevant compatibility/recovery
implications are recorded. Do not require every future detail to be settled in
advance. Resolve the owning PR's details before its implementation.

## Branches and authorization

- One integration branch, `main`; short-lived feature/fix/docs/chore branches.
- Draft PRs early; no long-lived `develop` or milestone branches.
- Squash merges; delete completed branches; no automatic merging.
- Require up-to-date branches, passing checks, and resolved review conversations.
- Protect `main` against direct pushes after bootstrap, force pushes, and deletion.
- The owner explicitly authorizes every merge and release. CI success is not
  authorization. Do not require a second account's review in the solo workflow.
- Review meaningful behavior, detection correctness, reproducibility, bounded
  resources, and failure modes. Explain limitations and include appropriate
  contract examples/UI screenshots.

Done means acceptance evidence passes, docs are current, review is resolved,
merge is authorized, and checks on the merged commit succeed. Bootstrap is the
single initial-history exception; its exact content is reviewed before publication.

## CI and local verification

P01 introduces real repository hygiene checks and the stable required aggregate
check `required-checks`. It must fail when any applicable job fails or is
unexpectedly skipped/cancelled. Use an always-running aggregator and explicit
applicability decisions; do not make required workflows disappear via path filters.
Shared contract changes select every affected consumer. Add component gates when
the corresponding implementation exists; never substitute passing placeholder jobs.

GitHub Actions use full commit SHA pins, minimal permissions, no secrets for
untrusted PR execution, and no execution of untrusted PR code in a privileged
workflow. Local commands mirror CI and are documented when introduced.

| Level | Trigger | Evidence |
| --- | --- | --- |
| Hygiene | Every PR | Formatting, config validity, secret scanning, docs checks |
| Component | Relevant changes | Builds, lint/types, meaningful unit tests |
| Contracts/Sigma | Compiler/evaluator/mapping/contract changes | Semantic cases, independent expected results, unsupported behavior |
| Integration | Cross-component changes | Small pinned datasets across affected services |
| Recovery | State/delivery/archive/configuration changes | Restart, retry, duplicates, quarantine, replay |
| UI | Affected workflows | Focused end-to-end operator tests |
| Security | Relevant changes and releases | Dependency/container findings and dispositions |
| Capacity | Performance changes and release qualification | Controlled benchmark report, not shared-runner timing alone |

No blanket coverage percentage substitutes for behavioral cases. Explicitly cover
negation, absent fields, types, mapping failures, and replay isolation. Corrected
behavioral bugs require appropriate regressions. Qualify Linux ARM64 and AMD64
before v0.1.0.

Failed required checks block merges. Unexplained correctness failures cannot be
waived as flaky tests. Any temporary exception needs an owner, justification,
tracking issue, removal condition, and owner approval; never hide a failure.

## Data and evidence

Pin datasets and checksums; retain origin, terms, transformations and capture
context. Use public recordings for integration; synthetic cases for precise edge
behavior. Distinguish malicious, documented benign, and unknown labels. Never
generate the expected result solely by running the implementation under test.

## GitHub setup sequence (P01)

1. Verify the owner, public repository identity, permissions, and feature access.
2. Configure squash-only merges, delete-branch-on-merge, and disable auto-merge.
3. Add issue/PR templates and real CI; observe successful checks before requiring them.
4. Apply main-branch protections, including strict `required-checks` and resolved
   conversations, without a required second-account approval. Verify enforcement
   and disclose administrator-bypass limitations rather than claiming absolute protection.
5. Create M0–M7 milestones and P01–P21 issues with dependencies. Create the project
   board and blocked marker; add later expansion milestone entries separately.
6. Enable and verify private security reporting. Check untrusted workflow permissions.

If repository/project administration access is unavailable, complete supported
setup and provide the exact remaining manual steps. Do not claim remote settings
were applied from local configuration files alone.

See [release policy](releases.md) for qualification, publication, migration and maintenance.
