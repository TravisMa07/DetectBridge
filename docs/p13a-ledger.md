# P13a implementation qualification

Current audit (2026-11-17): P13a #46 is owner-merged as e09c271; merged-main 43954609201 passed.
[Complete P13 acceptance](p13-acceptance.md) remains separate; earlier pending
statements below retain their historical checkpoint.

Branch: feat/p13-output-contracts, base origin/main 4ac31fa, refreshed 2026-11-16.
PR #45 is owner-merged; merged-main run 43900545102 succeeded. P08/P11/P12 bounded
prerequisites and owner source acceptance are complete. This is the first P13
implementation slice. Owner P13a review and explicit merge authorization remain
required. Production Kafka/Flink and search integration are unimplemented.

## Decisions and independent expectations

[P13a owning notes](p13a-design.md) were written before implementation, including
wire shapes, numerical limits, overflow policy, bit membership and identity
preimages. The committed identity vectors use independent Python hashlib over
literal preimages; the compact literal oracle reasons about serialized rule order
and shared-budget exhaustion. Existing independent semantic/source expectations
are retained. Exhaustive comparison supplements those oracles.

## Executed verification

The implementation is [PR #46](https://github.com/TravisMa07/DetectBridge/pull/46).
On code commit c8f7acff76d3a4d0149331f79550c178dc01f166, local macOS ARM64:

- Locked `tools/dev.py check` passed: 150 Python regressions, contracts, lint,
  format, types, links/Markdown, reviewed dependencies and repository hygiene.
- Locked `tools/dev.py java` passed: all existing Java consumers/artifact checks,
  25 evaluator, 36 Windows, 42 Linux and 10 assembly tests; 20 legacy plus 20 mapped
  independent YAML-to-Java semantic cases and 12 independent mapping cases.
  Mapped cases compare compact counts/matches/expanded membership to exhaustive
  results, including invalid, absent/type/negation and quality/capability cases.
- Locked `tools/dev.py windows`, `linux` and `assembly` all passed final reruns
  on the same code commit, including subsystem Python, packaging/notice and
  artifact/profile/lock regressions. Heavy runtime suites were not invoked.

Test logs remain ignored under `.cache/p13a-*-final.log`. Native AMD64 PR CI and
actual Kafka/Flink deployment qualification are separate from these local results.
No heavy Docker runtime suite or recorded-source qualification was run in P13a.

Initial component tests exposed a selection-test fixture carrying its legacy
mapping name. The attribution gate correctly rejected it; the test now explicitly
binds its synthetic P10 mapping. No production validation was weakened.
Initial repository check failed Ruff formatting on two edited Python files; those
files were formatted before rerunning. A later Markdown check rejected a line
starting with PR number syntax and an extra blank line in the final documentation
update; both were corrected before passing the documentation check. The new actual-audit receipt-clock
regression exposed a second receipt location in the linux.context extension.
Semantic projection now excludes that receipt while retaining the complete original
event and manifest retrieval links. Those failed attempts are not passes.

## Scope and remaining milestone acceptance

Synthetic tests execute actual Windows Security/Sysmon, selected authentication
and audit adapter/assembler paths. They cover six outcomes, quality/configuration
precedence, counts/matches/membership, fixed diagnostic bounds, manifest tampering,
output overflow, replay and immutable late links. Recorded originals remain local
and unchanged. Ordinary CI has no implied access to them. No source-to-search,
Kafka sink recovery, runtime memory/throughput, archive or release claim follows
from these component/offline tests. P13b and P13c retain every full milestone gate.

## Exact local artifacts

Built on code commit c8f7acf with strict dependency verification and existing locks:

| Artifact | SHA-256 |
| --- | --- |
| evaluator.jar | `00e3200d4ca99242985f9394f28fbcbc246b9b18307c2ab3d552a75e0e734ec9` |
| windows-adapters.jar | `788c039e122c0fbadcc4b3d63b53dc1c74b68b7a9c689c836095784a16a5f1c6` |
| linux-adapters.jar | `4fe031cb74e56b87740042b4908629608f43758ebb1da20ab883c8ac9e8b7294` |

These identify offline implementation artifacts, not a qualified P13 deployment.
The final documentation commit does not change production code; its CI state is
reported in the PR. Owner review/merge and full P13 acceptance remain separate.

## Adapter context attribution correction

Final review found that a source absent from the evaluator bundle still needs
configuration-blocked outputs with original audit manifest attribution. Source and
mapping hashes now come from the validated adapter context, independent of rule
bundle coverage; normalized-only callers without context retain explicit null
unknown references. Windows supplies its original context explicitly; Linux uses
its validated context extension. A receipt-free context fingerprint also binds
original decision versions, host/generation provenance and completeness metadata.
Actual Windows and audit consumer regressions now exercise unrelated bundles,
retain the real source hashes and preserve exact configuration-blocked counts.
Component tests passed; final code-head qualification/artifacts follow below.

## Final code-head qualification

Final production code commit: `f171ca7a7c24ab77d2ae30bba75c591c403b78cb`. All five locked commands passed on local
macOS ARM64: `tools/dev.py check`, `java`, `windows`, `linux`, `assembly`.
This supersedes the earlier code/artifact set above. The same 150 root Python
regressions, 25 evaluator/36 Windows/42 Linux/10 assembly Java tests, independent
20 legacy + 20 mapped semantic cases and 12 mapping cases passed, with compact/
exhaustive equivalence and installed production contract/artifact checks.
Logs: `.cache/p13a-f171ca7-{check,java,windows,linux,assembly}.log`.

| Final offline artifact | SHA-256 |
| --- | --- |
| evaluator.jar | `ea3c52fafcdb9274a43cb2a8ecfee0551d1919b040a1270b28f18ac05a1f50b4` |
| windows-adapters.jar | `2aa7e178d0215df1337fe206a3fa8a0006d133ff32d499778f6e0a2f60062449` |
| linux-adapters.jar | `91069d2f56c7182308350114d617cd90448a73e1ac79d41a1bf71759a293a587` |

The subsequent documentation-only commit records these results; repository/document
checks pass on that final documentation. PR #46 is handed back for owner review.
Native AMD64 CI is pending at handback, separate from local qualification; no new
recorded replay, heavy Docker runtime suite, merge or release was performed.
