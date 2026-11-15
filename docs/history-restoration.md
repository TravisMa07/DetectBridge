# Individual commit history restoration

On November 15, 2026, the owner authorized restoring the individual commits from
previously squash-merged PRs and using regular merge commits for future PRs.
This changes repository governance, not the accepted runtime architecture.

## Reconstruction and verification

The previous main tip was `df3144822ddd5694b9244ae29eb4a3c9e2815376` with 12
commits. The restored tip is `71242918fcc867d43cdbc2008cd97bad2e881d87` with 54:
the initial seed, all 42 commits recorded by the 11 merged PRs, and 11 merge
commits replacing the squash commits. Existing merges inside PRs remain intact.

Every reconstructed commit retains its original tree, author identity/date,
committer identity/date, and message. Parent changes necessarily change commit
IDs; invalidated GitHub signatures were removed rather than represented as valid.
The replacement PR merge commits retain the original integration timestamps.
The restored main tree was verified identical to the previous main tree before
publication. This verification does not establish runtime or performance results.

All seven open PR branch histories were reconstructed using the same mapping,
including the stacked P11/P12a branches and five Dependabot branches. Each PR's
three-dot diff was verified byte-for-byte unchanged. The existing six local
worktrees were checked clean before and after their branch refs were updated;
their files were unchanged. Historical qualification records refer to their
original tested commit IDs; rewriting history does not transfer CI results or
semantic acceptance to new IDs.

## Publication and recovery

The previous main remains available on the remote branch
`archive/main-before-history-restoration-2026-11-15`. A full pre-migration Git
bundle, original refs, original ruleset, and old-to-new commit mapping are saved
locally under `.git/history-restoration-2026-11-15/`. These recovery artifacts
are not source files and must not be committed.

Main and the seven open PR branches were pushed atomically with explicit leases
against their observed previous tips. The main ruleset was temporarily disabled
for this owner-authorized migration and immediately restored with its original
rules and no bypass actors. Remote branch tips and the restored ruleset were
read back and verified.

Other clones must fetch and align with the restored branches before publishing
work. Save any uncommitted or unpublished work first. A clean main checkout with
no unpublished commits can use:

```sh
git fetch --prune origin
git switch main
git branch backup/main-before-history-restoration
git reset --hard origin/main
```

Do not merge the old squash history back into the restored history. Unpublished
commits should be transplanted onto the corresponding restored branch after
preserving a backup. This workspace's existing branches and checkouts have
already been aligned.

## Future merges

GitHub repository settings and the versioned repository policy allow regular
merge commits only, with squash and rebase merging disabled. Individual feature
commits remain reachable from main after branch deletion. Explicit owner merge
authorization, required checks, resolved conversations, force-push protection,
and deletion protection remain required under the [SDLC](sdlc.md).
