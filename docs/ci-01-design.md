# CI-01 — Native activation deadline diagnosis

Owner: [issue #62](https://github.com/TravisMa07/DetectBridge/issues/62).
Baseline: `6e1ed1c0771711eb42faef0f9e4556999762830c`.
PR base: `feat/p15b-worker-activation`, explicitly confirmed by the owner.
P15b #61 remains Draft and parked; P15/P16 acceptance, merge and release are excluded.
The initial diagnostic freeze below is retained historically; the measured
correction section supersedes its small-prefix assumption.

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
and report dropped samples explicitly. Sample storage is capped at8MiB; retain
one final bounded row per fixed stage plus latest/late predicate rows independently
of sample saturation. No per-span disk writes/fsync. Persist in
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

## Measured correction after native diagnostic run

Run44641731135 at PR head079e969 executed test-merge source
`9737e8ac7ab13667c636156e784ead629bc4770d`. Its pressure B convergence consumed
64 old ACKs in eight predicates before the original120s deadline expired. Direct,
disjoint predicate children were observe96.640740600s, candidate24.153400716s,
health1.380357525s and join0.847009391s. Within observe, eight Kafka drains took
32.048344314s and eight commits30.377200105s; signature batches took4.144503252s.
This identifies repeated helper round trips as the largest measured combined
cost in that window. It does not isolate container/JVM startup, broker inspection,
connection-close shares or producer arrival rate. Nested load/replay is not added.

The frozen local101-wire experiment corroborates the call-count mechanism with
actual signatures, Kafka transport, normal controller adoption and durable writes.
Paired trials share one frozen prefix and identical initial store bytes; no worker
is started. The invalid-signature fixture has its own fresh owned topic and changes
only one historical signature at offset50. Every trial verifies/replays the entire
durable prefix before Kafka commit and reopens it at the end. Fixed order8 then128
leaves warm-cache/order effects uncontrolled. These are mechanics, not real worker
checkpoint, throughput or native AMD64 improvement evidence.

Select the existing supported128 bound only in first-party qualification observe,
fenced-prefix drain and inspect calls. Runtime defaults and every helper/message/
heap/store ceiling stay unchanged. Larger prefixes can still finish late, so retain
original wait cutoff and exact pre-drain completion cache and ACK-named join. A
historical prefix cannot discharge the current command. The generated mechanics
mode is explicitly rejected when the required activation environment is set and
cannot report a real scenario/full-gate pass.

This supersedes the small-quantum timing assumption in the historical ACK-batch
design and the old unit test's arbitrary4s-per-record model. That model is retained
in published history, not treated as a native cost measurement. Its replacement
checks a finite historical prefix plus current exact proof without inventing a
runtime duration; separate tests retain exactly-at-deadline and late-truth rules.
Native all14 failure is the integration red; no local120s failure is invented when
both measured mechanics trials complete within that bound.

The optional diagnostic invocation now runs both generated101-wire pairs followed
by actual `production-faults`, serially on the same native settings. Default required
all14 invocation and aggregate are unchanged. A mechanics continuation beyond its
budget may complete the finite diagnostic prefix but records `deadline_met:false`;
it is never a qualification timeout waiver. Native benefit still requires results.
