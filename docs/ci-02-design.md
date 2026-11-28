# CI-02 bounded search policy diagnostics

Issue [#64](https://github.com/TravisMa07/DetectBridge/issues/64), project 4,
In progress. Base and PR target: `feat/p15b-worker-activation`, exact approved
integration `e2bec696d998dd152d609f8727ed366fdf9b27c6`.

## Scope and evidence

Native44648665426 / job135998510906 failed healthy restoration in
`blocked_failure_publication` with `writer_failed_IllegalStateException`.
Original raw cause was discarded; `fault_readback` is unproved. No retry,
Kafka eventual-consistency explanation, wait/resource increase or behavioral fix
is authorized by this evidence. CI-01 is complete only in its approved feature
integration scope; P15/P16 and Draft #61 stay parked.

## Frozen interface and implementation decisions

Add first-party `failure_policy` context only for the existing policy helper.
The [independent matrix](ci-02-expectations.md) D01–D12 is the acceptance oracle.
A closed object, at most4096 UTF-8 bytes, has exactly version, operation, intent,
phase, alter_state, readback_state, observed_policy, readback_matches_intent,
known_throw, failure_type and close_state. Fixed version/operation and enum values
are specified in the matrix. No arbitrary values, messages, names, hashes or
class text are allowed. `failure_type` also permits `none` for success.

Collect only existing call results. A package-private factory seam permits actual
Kafka Admin interface mocks in component tests; production still creates exactly
one Admin and calls alter/all/get then describe/all/get then close once, preserving
15-second gets, stdout before close, exceptions and suppressed exceptions.
Observe null shapes before the original dereferences, without replacing their
NPE behavior. Set own-throw markers only at actual scope/readback throw sites.
Record primary phase/type before resource closure and track close independently.
An unmatched foreign exception remains unclassified, including a foreign
IllegalStateException with identical message text.

Success stdout remains exactly configured JSON; emit one fixed stderr diagnostic
envelope after successful close. Failures retain existing status/category/reason
and nonzero exit with additive context. Python scans at most64 KiB/128 lines,
rejects duplicate keys, unknown fields/types/enums and oversized context before
forwarding. It preserves known legacy category strings with closed failure-policy
category/type allowlists, suppressing unknown text. A per-error attribute carries
validated context into the existing sanitized qualification artifact; no raw body.
Missing/invalid context never invents progress and never changes failure outcome.

No data-plane, indexing, membership, accounting, backpressure, source commit,
cleanup, timeout, retry, CI aggregate or classification changes. No ADR is needed:
this refines bounded observability under accepted architecture, not semantics.

## Delivery and qualification

Freeze this design/matrix before production edits; implementation plus tests is
a second cohesive commit, with consolidated evidence as a third if needed.
First-party synthetic literals/mocks only (repository Apache-2.0 provenance).
Run meaningful missing-diagnostic red, Java/Python component tests, static checks,
actual helper artifact build and owned Kafka block→healthy qualification if
available. Fresh JAR/image identities cannot reuse old qualification identities.
No repeated/toggle reproduction is planned. One fresh native PR qualification is
required; parent collects exact checkout/source/JAR/image hashes, search report,
all job results and any first failing diagnostic. Stop on failure; retain it.
A diagnostic-only Draft PR does not complete CI-02 or prove the old cause.

## Reviewed diagnostic refinements

Independent review required exact envelope/status-to-exit binding and preservation
of all existing safe legacy category literals. JSON-looking malformed/duplicate
lines invalidate the stream rather than being hidden by a later valid envelope.
The existing error handler also dereferenced a null IllegalStateException message
inside its literal allowlist; a focused regression demonstrated loss of the trace.
Guard that null before the exact allowlist check. This corrects diagnostic
publication only, with unchanged nonzero failure and no inferred broker outcome.
