# P13 prerequisite semantic-review packet

Status: **owner accepted the bounded P09/P10 semantics and completeness limits on
2026-11-17** by selecting “Accept bounded P09/P10 semantics and limits.”
Issues #9/#10 are closed with the exact evidence and owner disposition in their
bodies. The reviewed pre-acceptance packet SHA-256 was
`b1e5de2fe1e57ab3e4af11a14909f20d2f6d7e4597c247f8a8795f030e82210a`;
the unchanged expectation fixture hashes are below. This supplies the formerly
missing independent review without changing expectations or reopening accepted
P11/P12 scope. P13 acceptance and merge authorization remain separate.

Review the exact literals and rationales below against their linked complete rule
and event inputs. They were independently authored before evaluator changes;
these tables copy committed fixture expectations, never observed evaluator output.
The supported semantics and limits are in [P09 design](p09-design.md),
[P10 design](p10-design.md) and [P10b selection/recovery design](p10b-design.md).

## P09 predicate semantics, also checked through mapped mode

[Complete inputs](../contracts/detection/v1/fixtures/semantic-cases.json), raw SHA-256
`455538f9fa20e5103d0b0d600783476912119e0864cd153b27ae9b75db3783bb`.

| Frozen case | Expected disposition | Independent rationale |
| --- | --- | --- |
| integer-max | matched | Exact signed 64-bit integer equality. |
| integer-negative | unmatched | Negative rule constant differs from zero. |
| contains-case | matched | Case folding and substring modifier. |
| starts | matched | Prefix starts at first code point. |
| starts-negative | unmatched | Prefix must not search interior. |
| ends-negative | unmatched | Suffix must end at final code point. |
| escaped-star | matched | Escaped wildcard is literal. |
| escaped-star-negative | unmatched | Escaped star cannot consume arbitrary text. |
| one-codepoint | matched | Supplementary character is one code point. |
| unicode-fold | matched | Single-code-point folding. |
| no-expansion | unmatched | No multi-character fold expansion. |
| no-normalization | unmatched | No canonical normalization. |
| field-conjunction | unmatched | Fields within a selection use AND. |
| nested-negation | matched | Double negation preserves predicate. |
| missing-negative | matched | NOT of absent positive predicate is true. |
| null-invalid | invalid | Null mapped ECS field is schema-invalid, never a nonmatch. |
| float-invalid | invalid | Integral JSON float is not an integer representation. |
| string-pid-invalid | invalid | String PID is invalid, never coerced. |
| bool-pid-invalid | invalid | Boolean PID is invalid, never coerced. |
| precedence | matched | AND binds tighter than OR; NOT binds tighter than AND. |

## P10 capability, absence, quality and source precedence

[Complete inputs](../contracts/detection/v2/fixtures/compatibility-cases.json), raw SHA-256
`9de3d9bda38c7eeb21efe8976e5b98b0a0e3a3ab1f0a3a0041fa367927cfc398`.

| Frozen case | Expected disposition | Independent rationale |
| --- | --- | --- |
| conditional-missing-positive | unmatched | Missing positive predicate is false; conditional capability does not invent a value. |
| conditional-missing-negation | matched | NOT of the false missing-field predicate is true. |
| unsupported-positive | configuration_blocked | Declared unsupported capability prevents evaluation. |
| unsupported-negation | configuration_blocked | Unsupported capability cannot be replaced by missing-field negation. |
| unused-unsupported-alias | matched | Unused unsupported CommandLine does not block a supported Image-only expression. |
| or-cannot-bypass-capability | configuration_blocked | All compiled expression fields are checked before event short-circuiting. |
| capability-before-quality | configuration_blocked | The specified capability gate precedes event eligibility. |
| quality-before-predicate | quality_skipped | Insufficient eligibility prevents ordinary evaluation. |
| source-before-capability | inapplicable | A known mismatching source is inapplicable before capability and quality gates. |
| unknown-source | configuration_blocked | Unknown source policy cannot be evaluated. |
| invalid-before-inapplicable | invalid | A null ECS field is invalid input even for an inapplicable rule. |
| conditional-warning-negation | matched | A nonblocking capture warning retains existing NOT-on-missing behavior. |

## Technical evidence and requested disposition

The locked combined Java check on P13d implementation bytes passed all twenty
legacy plus twenty mapped predicate cases and twelve capability cases; all mapped
cases also compare complete optimized/exhaustive results. Supplemental unit tests
cover shared-budget exhaustion, serialized rule order, error aggregation, atomic
compile failure, provenance/mapping tamper and restore binding. These tests are technical evidence; the independent owner acceptance is
recorded above.

Historical exact-head and merged-main runs were refreshed in the
[P13 acceptance map](p13-acceptance.md), including native AMD64 legacy and mapped
recovery. Current P13d detection verification retains those consumers as a real
regression gate. Historical failures and architecture bounds remain in the
[implementation ledger](implementation-ledger.md).

The owner accepted these bounded expected semantics and supported-feature limits
as the P09/P10 prerequisite disposition. Future semantic changes require their
own independent expectation update and applicable checks. PR #49 still needs its
own semantic/completeness acceptance,
resolved review, explicit merge authorization and successful merged-commit checks.
