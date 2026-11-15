# P11 Windows adapter design

Implementation base: df3144822ddd5694b9244ae29eb4a3c9e2815376. Owner authorized
P11 after P10 completion; no additional semantic approval is inferred from CI.
This subsystem implements the accepted adapter boundary without a shared library,
wire-contract revision, service, detection identity or integrated P13 pipeline.

## Decisions recorded before implementation

Use module-local Java APIs accepting the exact JSON context members specified in
[source-adapter-interface.md](source-adapter-interface.md). Context snapshots,
hashes, four typed declarations and fixed parser identity must agree. Optional
capture configuration lives in source_generation with provenance. Host bindings
must explicitly scope source and Computer; caller review establishes authenticity,
not a checksum. Synthetic bindings are labelled synthetic and cannot qualify recordings.
Retain full context in offline output beside the P03 event, preserving binding and
snapshot attribution without extending closed core schemas.

Use JDK namespace-aware SAX with secure processing, no DTD, entities, XInclude or
external resources. Stream-check 1 MiB bytes, depth 32, 4096 element nodes, 256
EventData fields and 64 KiB UTF-8 per scalar/attribute. Reject duplicate fields,
structural ambiguity and foreign namespaces. LF framing is verified before XML;
no multiline or EVTX support. Failure produces a bounded value-free diagnostic
linked to raw record/run/evidence, never invented normalized process data.

Only Security/Security-Auditing 4688 v2 and Sysmon/Operational 1 v5 are supported.
Security XML ProcessId is parent PID; NewProcessId is hexadecimal. Subject is the
actor; target account remains vendor data. Sysmon PID is decimal; split exactly
one domain separator in User; preserve GUIDs, parent and working directory. Never
tokenize command lines. Invalid optional typed data blocks eligibility rather
than silently dropping corruption. Missing optional command line is legitimate
absence unless reviewed context explicitly says capture disabled. Empty values
are treated as absent, original values remain in source_fields.

Security SystemTime must be UTC; Sysmon UtcTime has documented UTC semantics and
its space separator is converted without rounding fractional digits. Preserve the
original representation. Validate calendar/seconds separately from arbitrary
fractional precision. Missing/unparseable/ambiguous source time falls back to
immutable first observation with the existing diagnostic enums.

Evidence resolver uses caller-registered local objects only, never URI fetching.
Rehash object, check range, LF record position and record hash; I/O escapes as
retryable failure, integrity mismatch becomes preservation failure. Inline evidence
is also rehashed. Raw identity uses the existing helper. Normalized identity uses
unchanged source and singleton membership, excluding run.

Offline runner consumes raw/context NDJSON, explicit object-root and optional P10
plan. It writes result/context/evaluation rows to a same-directory temporary file,
fsyncs and atomically renames only after all input completes. Failure preserves
previous output; no non-atomic fallback. One output file is the transaction, not
an archive or Kafka acceptance. Versioned parser-backed profiles are proposals
with real adapter consumers; fixture coverage is never relabelled.

## Independent literal expectations (before implementation)

Original synthetic cases, Apache-2.0, no copied telemetry:

| Input | Literal expectation | Rationale |
| --- | --- | --- |
| Security NewProcessId 0x10, ProcessId 0x20 | pid 16, parent.pid 32 | New versus creator identity |
| SubjectUserName Alice, TargetUserName Bob | user.name Alice; target only source_fields | Subject is actor |
| Sysmon ProcessId 42, User LAB\\Alice | pid 42; user.domain LAB; user.name Alice | Decimal and account split |
| PID -1, 0xGG, 9223372036854775808 | extraction_failed, skipped | No coercion/overflow |
| Missing host binding | identity_missing, skipped | Computer cannot establish identity |
| CommandLine absent; known disabled | legitimately_absent; capture_unavailable | Observation is not capability |
| Time .123456789123Z | same fractional digits | No nanosecond rounding |
| Bad date / local Security time | first_observed; unparseable / timezone_ambiguous | Never guess timezone |
| Wrong provider/channel/event/version | unsupported_source preservation | Exact source scope |
| DTD/entity/duplicate/foreign namespace/multiline/bounds | extraction_failed preservation | No fabricated event |
| Changed object/range/hash | preservation integrity failure | Bytes precede normalization |
| Unavailable local object | visible IOException | Retry/backlog, not nonmatch |
| Same source/cursor in two runs | same record/event IDs; different run IDs | Replay isolation |
| Interrupted publication | old output unchanged | Atomic complete-file publication |
| Image literal equals / differs | matched / unmatched | Independent P10 predicate semantics |
| Wrong rule logsource / unsupported alias | inapplicable / configuration_blocked | Static gates precede quality |
| Missing host / exhausted evaluator budget | quality_skipped / evaluation_error | Distinct six outcomes |

Tests must assert these literals, never obtain expectations by running evaluator.
Recorded inventory must independently rehash and count each supported signature;
361 candidates are not 361 eligible events. No trusted recorded host binding is
assumed. Heavy Docker qualification belongs to orchestrator.

## Orchestrator integration and review

The real Windows gate is wired into developer commands, CI applicability and the
fail-closed required-checks aggregator. Shared event/detection contracts and
compiler/evaluator validation changes select this consumer. The module's 23 reused
Maven coordinates are reconciled with the combined inventory and owning lock;
no new dependency/image pin or advisory-remediation claim is made.

Review corrected System/Data versus EventData/Data attribution: unknown System
metadata must not shadow EventData extraction or create a null vendor-field key.
The regression retains the opaque System value and the original process image.
Independent recorded verification now checks source signatures and schemas for
every original row, not only totals or normalized rows. Verifier regressions
reject supported-as-unsupported, unsupported-as-normalized and incomplete result
references. Full recorded eligible coverage remains blocked on trusted host
binding provenance; implementation is not acceptance of that missing evidence.

The context boundary accepts upper/lowercase canonical-width UUID spelling, as
P03's UUID format permits, preserving the caller's exact run string. It still
rejects abbreviated UUID spellings; no silent ID normalization is introduced.
