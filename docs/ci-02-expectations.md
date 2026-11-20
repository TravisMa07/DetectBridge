# CI-02 independent diagnostic expectations (pre-implementation freeze)

Scope: issue64, separate from CI-01/PR63. Derived from the read-only ignored
independent draft prepared before CI-02 implementation. This owning copy froze
D01–D12 in 8551088 before source edits; it establishes expected outcomes, not
implementation, qualification or cause acceptance. Original evidence and the
ignored draft remain unchanged. This provenance wording correction does not
change any frozen outcome.

## Evidence and unknowns

Native run44648665426 job135998510906 failed in the healthy-policy restoration
call at tools/search_writer_qualification.py:581, within
`blocked_failure_publication`. The public category is
`writer_helper_failure-policy_writer_failed_IllegalStateException`. A same-source
PR run passed. That establishes an intermittent observed outcome, not the cause.
The original exception message/throw phase/readback were discarded. `fault_readback`
is a source-supported candidate, not proved native evidence.

Current first-party source:

- Main.java:386 maps only `block` to1 and `healthy` to the fixed reviewed
  Broker.TOPIC_CONFIG max.message.bytes value. No arbitrary requested policy is allowed.
- Main.java:480–490 performs incrementalAlterConfigs SET, waits15 seconds for its
  all-future, describes config with a separate15-second wait, then compares exact
  readback and throws IllegalStateException(`fault_readback`) on mismatch. Admin
  creation/close and other calls may also throw; class alone does not identify phase.
- Main.java:560–594 emits only sanitized top-level category/reason_type; its
  known IllegalStateException list omits `fault_readback`.
- search_writer.py:453–513 invokes a bounded owned helper and reduces stderr JSON
  to category/reason_type. Unknown raw exception text must not become public.
- qualification.py:567 blocks, proves BACKPRESSURED and no early source commit,
  then581 restores healthy and requires full source accounting. Failure remains a
  failed qualification. No diagnostic may change those proof obligations.

## Minimal proposed first-party protocol

Keep normal `{"status":"configured"}` success and current nonzero failure
semantics. Add a versioned closed diagnostic object for `failure-policy` only,
exported through bounded structured JSON, never arbitrary log/message parsing.
A single final object is enough; if interrupted before it exists, diagnostic state
is explicitly unavailable. Do not infer a last phase from absent output.

Fields are literal/versioned and all states are enums:

- `version`: `1.0.0`; `operation`: `failure_policy`.
- `intent`: `block`, `healthy`, or `unavailable` (parse/allowlist failed).
- `phase`: `parse_intent`, `admin_create`, `alter_submit`, `alter_wait`,
  `describe_submit`, `describe_wait`, `readback_compare`, `admin_close`, or
  `completed`. Set immediately before the corresponding existing call. Distinguish
  a successful comparison followed by close failure from a comparison failure.
- `alter_state`: `not_started`, `submitted`, `acknowledged`. A successful
  Future.get proves only the API ACK; timeout/ExecutionException cannot prove no
  broker effect or that the intended policy is active.
- `readback_state`: `not_started`, `submitted`, `received`; `observed_policy`:
  `not_observed`, `missing_resource`, `missing_entry`, `null_value`, `block`,
  `healthy`, `other`. These describe actual observed shape/value categories only.
- `readback_matches_intent`: exact boolean only after an actual available value
  comparison, otherwise null/unavailable. No success inferred from alter ACK alone.
- `known_throw`: `fault_scope`, `fault_readback`, `none`, `unclassified`, chosen
  only from exact first-party throw sites/messages. Do not classify arbitrary
  IllegalStateException messages or nested causes using substring matching.
- Optional fixed `failure_type` enum (`illegal_state`, `execution`, `timeout`,
  `illegal_argument`, `other`) and a bounded causal-type sequence with no values.
  An unwrapped type may inform diagnosis, never change retry/exit semantics.

No topic names, broker addresses, command lines, request bodies, source documents,
keys, passwords, exception messages, arbitrary config values, stack text or
unvalidated capture strings are exported. Fixed config-key literal
`max.message.bytes` and known `block`/`healthy` enum values are safe if useful.
Unknown actual values can be represented by `other`; an optional exact UTF-8 value
hash/length requires an explicit small bound, with oversize represented as bounded
unknown rather than printed or allocated again. Such hashes are diagnostic identity,
not proof of the intended value. Keep diagnostic object at most4096 UTF-8 bytes;
cap the Python structured-error scan (e.g.64 KiB total, bounded line count) and reject
noncanonical/duplicate/unknown fields before re-export. Unknown helper stderr is
not re-exported merely because its keys match a loose regex.

Prefer adding the object to the existing first-party failure JSON and forwarding
only validated fields into the qualification failure report. Use a structured
StackError field or equivalent; do not concatenate arbitrary text into category.
Do not publish hashes of raw secret-bearing messages as a substitute for this
fixed protocol. Full originals, if required for a later investigation, need a
separately scoped private retention policy; that is not implied here.

Do not move, repeat, delay or suppress any existing policy operation, Admin close,
source commit, BACKPRESSURED check, configured response, accounting call or cleanup.
Keep Java15-second get waits, existing Python90-second caller timeout, resource
limits, source expectations and current retry policy unchanged. Diagnostics must
not turn a failure into configured success, retry a policy SET or wait for eventual
readback consistency. Any such behavioral fix needs separate evidence/design.

## Independent matrix (before implementation)

| ID | Input or failure boundary | Required diagnostic and unchanged result |
| --- | --- | --- |
| D01 | block and healthy, successful alter ACK + exact readback | Literal intent and actual phase sequence; acknowledged/received/match true; configured remains success. No worker-processing proof inferred. |
| D02 | invalid/missing/nonstring/arbitrary intent | Existing rejection remains; intent unavailable, known first-party scope category only. No Admin effect; private input never echoed. |
| D03 | Admin create or alter submit throws | Exact entered phase, no fabricated ACK/readback. Original failure/nonzero remains; no automatic retry. |
| D04 | alter Future.get times out/fails after submit | Submitted, not acknowledged; observed effect unknown. No assertion that policy remained unchanged, no repeated SET. |
| D05 | alter ACK then describe submit/get fails | acknowledged plus exact describe phase, no readback match claim. Failure remains failure. |
| D06 | received readback is opposite policy or another value | Actual received category and match false; only the exact own `fault_readback` throw is labeled known. No raw value/private text. |
| D07 | missing resource/entry/null value | Actual shape category; preserve current thrown failure type/site. Do not silently translate NPE/other failure to fault_readback or healthy. |
| D08 | exact matching readback then Admin close throws | Match true and close phase, overall nonzero remains. Do not misdiagnose mismatch from IllegalStateException or configured stdout already emitted. |
| D09 | helper timeout/kill/missing/truncated/malformed/oversize diagnostic | unavailable/invalid diagnostic; original qualification fails. No guessed ACK, phase, readback or cause. Cleanup remains owned and unchanged. |
| D10 | injected sentinel strings in exception/config/key/body fields | No sentinel survives stdout/stderr validated diagnostic/report; categories only known literals. Unknown strings are neither re-exported nor promoted to known cause. |
| D11 | parser duplicate fields, unknown fields, wrong enum/type/version, nested/overflow data | Reject diagnostic as protocol-invalid without changing original failure result or leaking input. No regex-only trust of arbitrary helper JSON. |
| D12 | block BACKPRESSURED/no-early-commit then healthy restoration | Existing real source offset/accounting obligations all remain. A policy diagnostic is not evidence of accepted failure publication or source commit safety. |

Unit/component expectations use injected known exceptions and literal readbacks,
not evaluator/runtime-derived expectations. Include explicit Admin call-order and
call-count assertions: diagnostics add zero policy retries/extra describe polls.
Positive tests cover the known own throw; near-miss messages under the same class
stay unclassified. Include mixed success stdout plus close-failure stderr handling.

## Required validation and acceptance boundary

1. Freeze bounded diagnostic design and literal matrix before implementation.
   Review the exact owner files/CI applicability for a separate CI-02 PR; preserve
   CI-01 history and original native failures.
2. Run owning Java/Python tests and applicable static/type/format/dependency/artifact
   checks. Record source/artifact hashes: changing Main.java changes the search
   helper/writer artifact, so older successful artifact results do not transfer.
3. Execute actual local owned Kafka block→healthy restoration with unchanged
   sources, waits/resources and failure-accounting proof. Capture both successful
   diagnostics; exercise a deliberate readback mismatch through a bounded explicit
   test seam or controlled owned broker fault if needed. Label injected mismatch
   separately from a naturally reproduced native failure. No passing placeholder.
4. Run actual native CI on the exact new source/test merge, retain the bounded
   diagnostic/report and required checks. A successful rerun establishes only that
   attempt. Repeat only to resolve observed intermittency, with every attempt and
   artifact identity retained, not to select a passing result.
5. Claim an original-cause explanation only if a genuinely failing attempt's new
   diagnostic establishes its actual operation/ACK/readback/throw phase. Matching
   a source candidate or same exception class cannot retrospectively prove what
   occurred in run44648665426. A later behavioral stabilization, if needed, requires
   its own bounded design/expectations plus actual local/native qualification;
   successful diagnostics alone are not a fix for an unproved failure.

Unknown: original healthy readback value/shape; whether alter ACK completed; exact
throw site versus Admin close; whether broker propagation/timing, admin lifecycle,
namespace drift or another condition contributed. No current evidence authorizes
choosing a retry/wait/resource increase as the remedy.

Owning refinement: `close_state` is `not_started`, `entered`, `closed`, or `failed`.
Retain the primary failure phase across suppressed close failures. `failure_type`
is required and uses `none` for success; exact own throw markers are set at the
throw site, never from foreign exception messages. No timing or causal sequence
is exported in this bounded delivery. Success stdout stays byte-compatible; a
separate stderr diagnostic envelope is accepted only through the same validator.
