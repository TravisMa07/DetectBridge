# CI-01 qualification ledger

See [owning RCA design and independent expectations](ci-01-design.md).

## Baseline and protected evidence

Prepared checkout is clean at `6e1ed1c0771711eb42faef0f9e4556999762830c`,
on short-lived `t3/ci-01-root-cause`. Original working tree, dirty documents/tests,
handoffs, stashes, deployment configurations and private evidence are read-only.
Failed native runs remain attributed in [P15b ledger](p15b1-ledger.md).
Native44636802418 late CP87/110 joins establish the deadline failure, not its cause.

## Gates

Design/independent expectations freeze precedes instrumentation. This delivery
prepares bounded diagnostics; no correction/root-cause/native pass is claimed.
Unit/static checks, independent artifact review, native timing collection, paired
backlog mechanics, demonstrated correction and exact all14 gate are separate gates.
The selected production-faults workflow does not replace required activation.
PR61 stays parked; CI-01 blocks its continuation. No merge/release authorization.

## Preserved failure and artifact matrix

| Evidence | Source and outcome | Limits |
| --- | --- | --- |
| Native44636802418 / activation135958213204 | Feature head6e1ed1c, actual test-merge source863bc078435b8b29cdf1cb0c101fe4062a009190; convergence timeout after required-sink recovery | Late CP87/110 proofs; no native stage ranking |
| Native44631611463 | Test-merge sourcee0bd6a75110c136af6f0d0071c6da97d22220156; convergence timeout | Original failure retained; no all14 pass |
| Local ACK verifier host profile | Eight retained real ACK verifies:1.428410792s individual versus0.287962375s batch | Helper startup mechanics, not remaining native critical path |
| Focused core9c04211de14a4e66b56aaa47b1e0058b | 42 admissions/66 physical and logical outputs, selected core/mixed passed | Partial scope; not all14/native qualification |

Read-only verification found native44636802418 summary SHA-256
`daed8c6b6858b54d5c6f9e441b8baae7ac0efc5b5befb9cd0cb5560b4c1b63e7`
and native44631611463 summary
`e281326428478bf95ebbb5bc75eb5e46bd4bc3200de177b4038c7050c10503a1`.
Host profile report hash is
`0b0fe143610e53fecd9576b14e1bfd9d30246a73d5b4e57f7b192b27a67ff7c0`.
Raw private evidence remains in the original ignored cache and is never uploaded.

Production artifact055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d,
original producer51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d,
validatorf2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d,
and QA7b677b24bd39308a603e12f4e9c300d67d5b9cc2041a81103cb7481673361afd
are prior identities, not artifacts rebuilt or newly qualified by this delivery.

## Diagnostic implementation and local verification

Freeze commit8c42bf9 preceded implementation. Scoped monotonic inclusive spans
now cover the frozen stages plus existing job-health queries. Fixed-stage final
rows and latest/late predicate outcomes survive general sample saturation. The
existing public qualification summary carries the bounded report; no new network
query or per-record telemetry fsync is introduced. The frozen8/16 polling sizes,
120s cutoff, all14 required invocation and aggregate remain unchanged.

A dedicated additional manually selected `activation-diagnostic` job runs actual
`--scenario-group production-faults` with fresh setup and the same native settings.
It reports partial scope and cannot satisfy the required activation gate. To invoke,
dispatch existing `hygiene.yml` on this CI branch with `activation-diagnostic=true`;
the normal required jobs still run. PR trigger explicitly includes the owner-chosen
feature base. Every diagnostic bootstrap uses the same exact dependency-cache
hit guard as required consumers. No remote workflow dispatch was performed here.

Read-only independent review found two diagnostic defects: nonempty inspection
reported zero processed, and saturation could discard late truth. Both are fixed
with regressions. The inspection red actually observed0 instead of1; the late
report red lacked retained outcome data. The first full check also found three
cache consumer-count expectations needing the additional diagnostic consumer;
all guards still run, now for17 consumers. A test-fixture setup error (missing
publication) was corrected and is not a behavioral red.

On macOS ARM64, `uv run --locked python tools/dev.py check` passed the complete
applicable static/contract/hygiene workflow,412 Python tests (one class skipped:
exact retained lifecycle evaluator unavailable), Ruff/formatting and mypy for117
source files, plus adapter checks. Focused diagnostic/controller/oracle cases passed.
No Gradle build, Docker worker execution or native AMD64 qualification ran locally.
The local check is not evidence of real worker recovery or deadline performance.

Original dirty docs/tests and all eight protected handoff/doc hashes were checked
read-only against both preserved manifests and remained unchanged. No original
worktree/stash/deployment, container, volume or network was altered.

## Next evidence and remaining gates

Collect exact diagnostic PR-head native all14 results first; preserve the complete
failed attempt and inspect nested costs/cursors before naming a cause. The paired
101-wire signed-backlog8/128 mechanics experiment is frozen but not executed or
claimed by this diagnostic draft. Preserve fresh equivalent stores and test an
invalid historical signature separately. Select only a measured correction, then
qualify focused failure and all14 at its exact source/artifact identities. P15b61
remains Draft/parked. Owner acceptance/merge authorization and actual merged-main
verification remain separate; no throughput/HA/recorded AMD64 claim is made.

Local evidence hashes: final full-check log
`3d36e4089d1c5492890dd96fc4f8c79dae1075df137d8b5e2fa04b6ad7230129`;
initial failed full-check log
`9d0a50507fd190b2622dd856578944f9999da5a691a06d3ed1e9d3b032b68ebb`;
inspection regression red
`1c6d992537a0f222f0aad3ffafc1076f815001c691be9ddf6bfe1e35331cf4eb`;
saturation regression red
`621e297b168a76874fcf30af784f6b3ff294cbeb9cce928ec1b2e0b06539f849`.
A subsequent documentation-only check found one missing table-cell space; it was
corrected, with failed log retained as `ci01-doc-final.log` in this checkout's cache.
