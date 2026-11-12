# GitHub governance setup

These are owner-operated administrative commands, never untrusted PR jobs.
The desired repository policy is in `tools/hygiene/repository-policy.json`.
Existing tracking items are preserved; duplicate planning IDs stop setup.

## Tracking and policy commands

```sh
python3 tools/setup_github.py
python3 tools/setup_github.py --apply tracking
# Only after required-checks succeeds on the exact local HEAD:
python3 tools/setup_github.py --apply policies
python3 tools/setup_github.py
```

Default mode reads current settings without mutations. Tracking setup creates
missing milestones, issues and the blocked marker, preserving existing issues,
labels and milestone contents. Newly created issues link their dependency issues.
If interrupted between creation and dependency linking, inspect affected issues
and repair missing links explicitly; rerunning never overwrites user-edited bodies.

Policy setup explicitly reconciles the listed merge/workflow settings. It creates
an absent ruleset; if an existing named ruleset differs, it stops for review rather
than overwriting changes. Other rulesets and settings are not deleted. Readback
must be reviewed against desired policy; a local JSON file does not enforce GitHub.

The main ruleset requires PRs with zero reviewer approvals, resolved discussions,
strict GitHub Actions `required-checks`, and blocks force pushes/deletion without
standing bypass actors. Owners still authorize every merge. Administrators can
edit rulesets; this is not an immutable security boundary. Do not test enforcement
by deleting or force-pushing main.

## Project board access and owner-assisted setup

The current CLI token lacks Projects scope. To grant it interactively:

```sh
gh auth refresh -s project
gh project list --owner TravisMa07 --format json
```

Do not put authentication tokens in files, issues, or chat. If authorization is
not desired, configure the board in GitHub's UI:

1. Under TravisMa07's Projects, inspect existing projects for **DetectBridge Roadmap**.
2. Create that project only if absent and link the DetectBridge repository in settings.
3. Edit the Status field options to **Backlog**, **Ready**, **In progress**,
   **In review**, and **Done**. Use a board view grouped by Status.
4. Add P01–P21 issues. Set P01 to In progress, all others to Backlog initially.
5. Use the repository's blocked label independently of Status. Keep status changes
   manual; do not add privileged automation or automatic Done transitions.
6. Verify issue membership, repository linkage and statuses; record the project URL
   in the P01 PR. After review readiness, move P01 to In review; do not mark Done
   until its full acceptance gate and authorized merge are complete.

P01 remains partially configured while the board is unavailable. Issue bodies
retain initial workflow status as a fallback, not as a replacement for the board.

## Validation evidence

Record successful, intentional-failure and recovered workflow URLs in the PR.
Use a temporary broken relative link on the feature branch, revert it, and verify
both hygiene and aggregate outcomes. Read back policies after the first success.
A draft PR itself is nonmergeable: distinguish draft status from failing required
checks rather than interpreting all blocked states as proof of check enforcement.

Private reporting is enabled remotely during policy setup. Before that operation,
the security reporting link may not yet be available. Templates on this branch
become default repository templates only after authorized merge.
