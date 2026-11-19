# CI-01 — Native activation deadline diagnosis

Owner: [issue #62](https://github.com/TravisMa07/DetectBridge/issues/62).
Baseline: `6e1ed1c0771711eb42faef0f9e4556999762830c`.
PR base: `feat/p15b-worker-activation`, explicitly confirmed by the owner.
P15b #61 remains Draft and parked; P15/P16 acceptance, merge and release are excluded.

## Scope and present evidence

Native run44636802418 activation135958213204 timed out after required-sink
recovery. Exact authenticated ACK-named COMPLETED proofs CP87/110 were retained
late. Earlier phases/runs also missed the same120-second deadline. Local helper
startup profiling measures one cost, not the remaining native critical path.
Neither larger readback nor worker failure is an established root cause.

This first delivery is diagnostic, not a claimed convergence correction. Preserve
8-record observe and16-record inspect, every signature/prefix/durable-cursor check,
the exact checkpoint join,120-second cutoff and mandatory default all14 gate.
No production JAR, worker, validator, contract or accepted architecture changes.

## Instrumentation contract

Enable only inside the first-party qualifier using a scoped in-process collector.
Use monotonic start/end offsets and original deadline remaining at stage entry/exit.
Capture immutable verification; load/replay; candidate REST capture; Kafka drain;
signature batch; per-record validation; durable ACK file fsync and journal/cursor
append; Kafka commit; final evidence join. Nested spans are inclusive and carry
parent IDs: never sum them as exclusive costs. Signature helper timing includes
its own immutable checks. Load includes replay and referenced-file verification.
No added broker/REST queries for logging; snapshots read existing memory only.

Fixed stage names, booleans, bounded integer counts/cursors and approved identity
hash/CP context only. No paths, messages, raw ACKs/payloads, public/private keys or
exception strings. Cap retained samples at8192, aggregate all calls by fixed stage,
and report dropped samples explicitly. No per-span disk writes/fsync. Persist in
the existing safe summary even on failure. A truthy predicate returning late is
recorded with its actual end time and still fails the unchanged original cutoff.
Instrumentation is observational and does not retry, swallow or relabel failures.

## Independent expectations frozen before instrumentation

Derived from the task, existing controller durability contract and SDLC, with a
separate read-only agent review; these are requirements, not measured outcomes.

| ID | Input/condition | Required observation and rationale |
| --- | --- | --- |
| D01 | No scoped collector | Existing controller results/effects; no report or network work |
| D02 | Nested stage calls | Ordered monotonic intervals, parent IDs and inclusive label; distinguish nesting |
| D03 | Stage raises secret-bearing error | Same exception propagates; only failure boolean emitted |
| D04 | Predicate true after original120s | Record late truth and negative remaining budget; timeout still raised |
| D05 | True exactly at deadline | Existing inclusive cutoff preserved |
| D06 | Large call count | At most8192 samples; exact aggregate counts and explicit dropped count |
| D07 | ACK observe | Start/end durable cursor and journal/count context; commit follows durable writes |
| D08 | Current exact ACK/CP join | Existing command/incarnation/job/CP proof stays mandatory; hash/CP context only |
| D09 | Failure before/within qualification | Available bounded timings retained without inventing successful stages |
| D10 | Focused production-faults invocation | Fresh real workers, selected coverage only, full_gate false; default all14 unchanged |
| D11 | PR targets frozen feature branch | CI actually triggers on that base; aggregate failure/skip policy unchanged |

## Controlled backlog experiment freeze

Before selecting a batch-size correction, freeze101 byte-identical valid signed
ACK wires:100 historical distinct-CP ACKs followed by one current-command ACK at
offset100, beyond the first8. Retain private wire/signing provenance and a safe
ordered hash manifest. Every signature and ordinary adoption/prefix check runs.
Use fresh equivalent stores at cursor0 with identical publication/registration
history and the same frozen broker prefix. Serialize8 and128 supported-limit
trials under identical native settings, artifacts, heap and original120s cutoff.
Retain starting store/prefix hashes, consumed/validated/journaled counts, final
cursor/semantic outcomes, stage costs, late results and failures. Do not compare
wallclock-dependent journal bytes as the semantic oracle. Reject mismatched
prefixes, reused progressed stores or incomplete verification. A generated ACK
is mechanics, never evidence that a real worker completed its named checkpoint.
Synthetic modeled9s rounds are not native timing evidence.

The paired native mechanics trial and real native diagnosis remain pending.
Measure dominant costs before choosing any correction. If backlog dominates,
justify a change with paired native results and focused negative/boundary tests;
otherwise fix the demonstrated cost. Requalify all14 on exact final source.
Owner review/merge authorization and actual merged-main acceptance remain separate.
