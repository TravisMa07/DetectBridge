# P13a implementation qualification

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

Qualification is in progress; final results will be appended before handback.
Initial component tests exposed a selection-test fixture carrying its legacy
mapping name. The attribution gate correctly rejected it; the test now explicitly
binds its synthetic P10 mapping. No production validation was weakened.
Initial repository check failed Ruff formatting on two edited Python files; those
files were formatted before rerunning. A later Markdown check rejected a line
starting with PR number syntax; it was reworded. The new actual-audit receipt-clock
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
