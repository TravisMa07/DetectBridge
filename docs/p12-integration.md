# P12a shared integration handoff

The isolated integration commit contains only root settings.gradle.kts registration
of linux-adapters at packages/linux-adapters. It is deliberately separate from
subsystem implementation. No shared schema, reader, existing P10 profile, root
lock, verification metadata, inventory, CI, developer command or status doc was
silently changed. No PR was opened while serial CI integration and recorded
acceptance remain unresolved.

## Proposed serial patch requirements

1. Retain the two root Gradle registration lines, reconciled with the Windows
   module registration. Module build.gradle.kts has real compile/test tasks and
   P10 compiler preparation, not a placeholder task. The module-local lock and
   dependency-review.json record all 23 reused coordinates/configurations.
   Strict verification metadata already covers them; no new upstream pin was
   required. Reconcile consolidated inventories under orchestrator ownership.
2. In tools/dev.py java(), add `:linux-adapters:test` and `:linux-adapters:jar` to
   the existing Gradle command list, retaining every current task and subsequent
   transport/detection/writer artifact/semantic check.
3. In .github/workflows/hygiene.yml, toolchain-verification's run step currently
   executes bootstrap and smoke only. Append `python3 tools/dev.py java` after
   smoke, using the command runner's pinned JAVA_HOME/GRADLE_USER_HOME. This makes
   the actual Linux task selected for all non-Markdown changes through the
   existing conservative needs_toolchains function and required-checks gate.
   Alternatively add a real adapter component classification/job/gate serially,
   with fail-closed missing/skipped/cancelled coverage; do not add a passing shim.
   Include meaningful regressions for whichever shared gate path is adopted.
4. Include the module fixture preparation script in locked Ruff checks (or move
   it to a reconciled owning tools path while keeping imports/Gradle inputs
   correct). Its standalone locked lint/format checks pass locally.
5. Adopt/reconcile the module-local context nested shapes and namespaced
   manifest/preservation/context-extension schemas with any other adapter
   proposal. P03 remains closed and unchanged; these resources do not enter its
   fixed registry implicitly. New -p12a source IDs and profile hashes are explicit
   offline proposals, not replacement content for the existing fixture IDs.
6. Reconcile implementation/status docs without claiming P12 completion or P13
   readiness. Run root locked check/java plus Linux task on the reconciled branch,
   then obtain actual AMD64 evidence. Do not reuse this worktree's ARM64 result
   as AMD64 or checkpoint recovery evidence.

## Remaining owner decisions and acceptance gates

Review the independently authored expectations and source-specific completeness
policy. The implemented policy treats EOE/boundary/timeout/end as closure and
checks successful execution plus argument/PATH consistency separately; resource
closure always skips. P03 identities and source timestamp/serial remain exact.

Review the real Linux OpenSSH9/rsyslog capture protocol and pin actual lab image/
build/collector metadata before execution. Approve genuine recorded expectations,
terms and trusted host/generation provenance. Existing audit excerpts and rejected
auth candidates cannot establish eligible recorded acceptance. Shared catalog/
acquisition extensions follow only after concrete reviewed recording metadata.

P12b is not implemented and must wait for separately authorized P12a merge and
main qualification. No heavy Docker run was started. Main's referenced CI was not
polled or watched. No merge, release, push, archive or integrated production
pipeline occurred in this child.
