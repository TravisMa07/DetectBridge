# P12 implementation and acceptance map

P12 is the bounded Linux adapter/assembly milestone. P12a #39 and P12b #42 are
merged; P12c [PR #43](https://github.com/TravisMa07/DetectBridge/pull/43) merged as
`c024497`. Its description records completed owner semantic/completeness review
and separate explicit merge authorization. Final-head AMD64 run 43812450381
attempt 2 passed on `adf71f8`. Implementation, qualification, owner acceptance and
authorized merge remain distinct; earlier pending statements in ledgers are historical.

| P12 requirement | Implementation and evidence | Acceptance state |
| --- | --- | --- |
| Selected audit execution/authentication adapters | Pinned ABI/syscall execution policy and exact selected OpenSSH9 password grammar; synthetic edge cases plus real local audit/auth recordings | Implemented; bounded source scope only |
| Source-defined assembly identity | Run/source/trusted host/generation/audit timestamp/serial; interleaved scope cases and independent identities | Implemented and qualified |
| Argument/path preservation | Positional, repeated, empty, split and hex arguments; every PATH/token occurrence; no manufactured shell command line or singular file path | Synthetic regressions and real five-argument/two-PATH execution qualified |
| Closure separate from completeness | EOE/boundary/dataset-end/timeout/resource closures; independent membership/count policy; incomplete/conflict/unsupported evidence skipped | Implemented; owner bounded completeness-policy acceptance recorded in #43 |
| Bounded state and late evidence | Prepared transitions, bounded inbox/outbox/open/closed knowledge, immutable manifests/late links and visible admission backlog | Unit/model and actual resource-profile qualification passed |
| Strict recovery and accepted-input accounting | Checkpoint-prefix output intents, stable duplicates, restored absolute timers, code/source/mapping/broker/registration binding rejection; all five required-sink faults and actual broker pause | Final-artifact ARM64 full suite and final-head AMD64 attempt 2 passed |
| Real recorded source evidence | Original bytes/terms/package/capture/host/boot provenance retained locally; expectations independent of adapter/evaluator; corrected observation metadata uses a separate replay run | Audit offline plus real audit/auth checkpoint, failure and isolated replay qualified; exact artifacts in P12c ledger |
| Reviewable source semantics | Independent expectations, exact accounting/tamper probes and explicit source/quality/capability outcomes | Owner [semantic/completeness review](p12c-review.md) complete, recorded in #43 |
| Integration into main | P12c merged after explicit owner authorization | Merged-main run 43873905332 passed including assembly and required-checks |

The [P12c ledger](p12c-ledger.md) records exact artifact IDs, successes, failed
attempts and qualification limits; the [P12a ledger](p12-ledger.md) and
[P12b ledger](p12b-ledger.md) retain their histories. Source and mapping snapshots,
P03 contracts, at-least-once delivery and the accepted architecture stay unchanged.

P11 trusted Windows recording bindings remain a Windows/P13 acceptance dependency.
They are not missing Linux implementation. Production P13 enrichment/evaluation/
writer wiring, archive services, throughput qualification, arbitrary authentication
grammars and general audit-corpus coverage are outside P12. No such capability is
inferred from CI, a controlled capture, a qualified resource budget or a PR merge.
