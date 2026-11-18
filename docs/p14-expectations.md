# P14 independent expectation matrix

Status: requirements matrix authored before code, 2026-11-18 UTC. This document
records independent expectations; actual P14a execution is attributed in the
[ledger](p14-ledger.md). Owner review and P14b/c execution remain separate. [Design](p14-design.md) owns proposed limits and
interfaces; [ledger](p14-ledger.md) owns observed evidence. Before each slice's
implementation, freeze concrete schemas, byte fixtures and literal identity/hash
vectors in a separate commit. This matrix does not replace those concrete gates.

Origins: A02–A07; P03 field/identity/time contracts; ADR 0002 and P05 local replay;
ADR 0004 acknowledged transport; accepted P12 membership/quality/late links;
P13a canonical semantic identity; P13b original wire/context and checkpoint output;
ADR 0008/P13c derived search. Proposed new limits derive from this owning design.
Every rationale below is specified independently of future archive output.

## Original bytes, metadata and compatibility

| ID / slice | Input or source fact | Expected observable result and rationale |
| --- | --- | --- |
| B01 / a | Literal UTF-8 bytes `41 0d 0a 0a c3 a9 0a 5a` | Retrieval returns all eight bytes; LF framing is lengths 3,1,3,1 at offsets 0,3,4,7. CRLF, blank record, multibyte character and unterminated final record stay exact (P05 framing). |
| B02 / a | Empty object; separately one LF byte | Empty object round-trips as zero bytes/no records; LF object has one one-byte empty-content record. No invented zero-length P03 range. |
| B03 / a | Opaque non-UTF-8 original, null Kafka key/value, empty key/value | Base64 retrieval preserves bytes; null and empty remain distinct; invalid source text is retained without normalized event. NDJSON itself remains valid UTF-8. |
| B04 / a | Duplicate ordered Kafka headers and explicit timestamp/type | Exact header order/repetitions, bytes, timestamp and type round-trip. Parsing cannot discard transport provenance. |
| B05 / a | Integers -9223372036854775808, 9007199254740993, 9223372036854775807 in permitted fields | Exact integer values survive serialization/retrieval, without double coercion. Contract-bound nonnegative fields still reject negatives. Out-of-domain integer or integral float in an integer field fails visibly. |
| B06 / a,b | Source strings with 0,6,9,12 fractional digits, year 1800 and fallback basis | Original strings/precision/basis survive unchanged; P05 timing input still rejects >9 digits. Archive does not round through a datetime/float helper. |
| B07 / a | Original URI/range with verified whole-object and selected-record digests | Retrieval verifies both hashes and exact bounds; it never fetches URI text or trusts a search projection. |
| B08 / a | Bad range, wrong record hash, wrong object hash or absent registered object | Integrity errors block; missing object is visible dependency backlog with unchanged offset. No substitution or truncation. |
| B09 / a | Catalog/terms/capture/host/boot objects referenced by a source | Exact referenced artifacts remain available and hash-verifiable before source archival is called durable; local-only terms do not authorize public CI upload. |
| B10 / a | Unknown schema/codec, duplicate JSON key, trailing token, invalid Unicode or symlink/path traversal | Reject before adoption or output. Originals may be archived as opaque malformed input; malformed archive metadata cannot be adopted. |
| B11 / a | Existing P03/P05/P08/P12/P13/P13c fixtures and defaults | Existing consumers retain their accepted results and checkpoint/configuration incompatibility rules; archive mode cannot silently select a new projection or pipeline. |

## Publication, offsets and failure recovery

| ID / slice | Input or injected fault | Expected observable result and rationale |
| --- | --- | --- |
| D01 / a | Kill during object/payload write, gzip footer or metadata write | No committed segment and no new Kafka commit; partials remain ignored/owned; restart retries exact bytes. Exercise each distinct write window. |
| D02 / a | Kill after file sync but before staging-directory sync/rename | No acknowledged archive receipt/offset advance; unpublished work may be removed only after lock/ownership checks. |
| D03 / a | Kill after rename but before parent sync | Kafka progress unchanged; restart verifies and syncs surviving publication before reuse, or republishes absent data. No process-kill power-loss claim. |
| D04 / a | Kill after parent sync but before Kafka commit | Verified durable prefix survives; restart reuses it, reconciles/commits next offset and adds no conflicting segment. |
| D05 / a | Kafka commit succeeds, kill before advisory progress update | Scan reconstructs original durable next offset; stale advisory file cannot duplicate/drop logical coverage. |
| D06 / a | Rebalance or commit timeout after durable publication | No unresolved partition offset advance; new assignment validates prefix/bindings. Ambiguous commit is reconciled without overwrite. |
| D07 / a | Crash while publishing dependency object, then later segment | Object-only orphan is not source completion; it counts toward storage. Missing required dependency prevents segment adoption. |
| D08 / a | Corrupt/truncate gzip header/body/footer, append bytes or a second member | Reader rejects exact corruption before yielding a verified object/segment. Check CRC, compressed/uncompressed hashes/lengths and bounded decompression. |
| D09 / a | Change metadata count, length, interval, previous hash or delete middle segment | Reject inconsistent committed chain/coverage; never repair by discarding evidence or resetting offsets. |
| D10 / a | Broker committed next offset ahead of verified archive prefix | Explicit preservation-gap stop, even if Kafka still retains bytes; no successful progress report. |
| D11 / a | Earliest retained broker offset exceeds unarchived requested start | Explicit missing-history failure. Legitimate broker offset gaps within verified returned intervals are not invented missing records. |
| D12 / a | Broker/topic UUID, group, partition set, root or implementation binding changes on resume | Reject before admission; no earliest reread or old-state adoption (P13 recovery boundary). |
| D13 / a | Permission denied, fsync error, ENOSPC, Kafka outage or unknown exception | Stop/backpressure with fixed category, exact retained input and unchanged unresolved offsets; preserve original diagnostics privately. No quarantine to bypass an outage. |
| D14 / a | Durable malformed-input quarantine followed by crash | Exact original bytes/location and category survive the same publication boundary; offsets cannot rely on a Kafka-only pointer. |
| D15 / a | Concurrent writer or reader observing staging directory | Second mutator fails exclusive lock; reader sees only verified committed directories. |

## Identity and bounded resources

| ID / slice | Input or boundary | Expected observable result and rationale |
| --- | --- | --- |
| I01 / a | Exact redelivery at same cluster/topic/partition/offset | Same wire occurrence and verified payload, no replacement or extra logical archive occurrence. |
| I02 / a | Same bytes at two offsets or two original dataset positions | Two retained occurrences and provenance links; equal content does not collapse source occurrence identity (P03). |
| I03 / a,b | Same wire location changed content; separately same raw occurrence changed context at another offset | First case blocks integrity conflict. Second retains both wire occurrences plus visible semantic conflict; historical selection cannot silently choose one. |
| L01 / a | Exact row/count/segment/object/selection caps and one byte/row over | Exact boundary accepted if other limits permit; oversized input remains backlog or explicit preflight failure. No truncation or passing partial transaction. |
| L02 / a | Highly compressible and incompressible input near total cap | Both use conservative reservations; managed files plus proposed transaction stay within 2 GiB and leave 128 MiB free. Compression ratio is not an admission assumption. |
| L03 / a | Gzip bomb, false decoded size or unbounded dependency graph | Bounded streaming length/count verification rejects before excessive allocation; original unresolved Kafka progress remains unchanged. |
| L04 / a | External disk use consumes reserved free space after preflight | Actual write/sync failure is visible; no offset advancement. Reservation cannot promise immunity to external disk pressure. |
| L05 / a | Output topic delayed while input archive catches up | Input watermark advances only for durable inputs; historical readiness remains pending with exact missing outputs/artifacts. Cross-topic progress is a vector. |

## Historical and current replay semantics

| ID / slice | Input or source fact | Expected observable result and rationale |
| --- | --- | --- |
| H01 / b | Frozen eligible audit manifest with exact original ordered members and timeout closure | Pinned parser/evaluator reconstruct expected fields, quality, counts and match revisions using exactly those members; wall-clock scheduling cannot regroup them. |
| H02 / b | Incomplete manifest, original late-link row and output-limit manifest without event | Preserve original insufficient quality, original late association and no-event disposition. Do not add late member or fabricate an event during historical execution (A03). |
| H03 / b | Interleaved hosts, boots, source instances and runs sharing audit serial/time | Only exact scoped members belong together; historical membership and source identity remain distinct. |
| H04 / b | Same original manifest reference but changed member/raw/context hash | Preflight fails before outputs; semantic hashes cannot replace full original-byte verification. |
| H05 / b | Missing or changed rule/plan/mapping/source/parser/evaluator/selector/enrichment artifact | Explicit missing/incompatible dependency failure before execution. Version-name equality cannot substitute for exact artifact bytes. |
| H06 / b | Unknown external enrichment input or unsupported historical executor | Fail explicitly; no current lookup, nearest-version fallback or stored-result copy presented as reproduced execution. |
| H07 / b | Historical source unsupported, extraction-failed, missing identity or legitimate absent command line | Preserve accepted distinct dispositions/quality and six-outcome semantics. No manufactured host binding or nonmatch substitution. |
| H08 / b | Two historical executions of the same sealed selection | Same evidence/event identities and independently expected semantics; distinct replay/processing/detection/diagnostic scopes with origin links. Original outputs are unchanged. |
| C01 / c | Explicit new rule bundle with an independently specified changed predicate | New expected result changes only within new run; historical result and pinned bundle remain available. Freeze literal positive/nonmatch cases before running new code. |
| C02 / c | Current selection includes original late record and new explicit grouping policy | Permitted new membership/event ID with links to original members/manifest/late association; historical membership stays unchanged. Freeze exact expected groups first. |
| C03 / c | Missing new policy, schedule, source selection or fresh run ID | Preflight failure; no implicit active configuration or reuse of an old checkpoint. |
| R01 / b,c | Kill before/after output publication, transition-state commit and advisory update | Committed output/state prefix resumes consistently, with stable IDs and no skipped input; each publication window is exercised separately. |
| R02 / b,c | Resume with changed mode/run/selection/artifact/limits/destination | Reject before append. A current replay cannot adopt historical, P05, P12 or P13 state. |
| R03 / b,c | Missing/corrupt committed replay output or dependency after interruption | Fail without deleting/replacing evidence or silently restarting. Completed resume verifies completion and appends nothing. |
| R04 / b,c | Alter one expected host/count/membership/attribution while retaining totals | Independent semantic verifier rejects exact category. Stored archive/evaluator output is not the expectation generator. |

## Retention, privacy and qualification

| ID / slice | Input or operation | Expected observable result and rationale |
| --- | --- | --- |
| T01 / c | Delete selected prefix with live reader/replay pin, retained late link, quarantine or shared object dependency | Deny deletion and expose blockers. Durable offset alone is insufficient deletion permission. |
| T02 / c | Unpinned explicit retirement plan, crash before/after retirement record or individual deletion | Before record, evidence stays authoritative. After record, restart finishes exact plan; retained chain anchors still verify and retired retrieval is explicit. |
| T03 / a,c | Archive byte cap reached; broker deletion proposed while another consumer lags | Stop archive admission visibly; no automatic Kafka retention decrease or deletion based solely on archive progress. P16 receives watermark/blocker interface. |
| Q01 / a,b,c | Payload/credential sentinel in malformed and exception-producing input | Routine logs expose only fixed categories/IDs/counts/hashes; original bodies and exception messages remain private. Credentials are external to manifests/Git. |
| Q02 / b,c | Accepted private Windows/audit/auth recordings, verified terms/catalog/context | Reuse exact controlled originals and independent accepted source expectations; missing/changed originals fail before mutation. Local opt-in evidence is separately attributed from synthetic native CI. |
| Q03 / a,b,c | Required fault scenario fails for an unrelated reason | Retain original logs/artifacts, mark failed, diagnose actual operation; do not count arbitrary failure as intended fault or adopt failed dependent revision. |

For implementation, map each row to named tests and runtime evidence in the
owning slice's ledger. Fault evidence must show the actual injected operation,
durable archive/consumer progress, exact retrieved originals and recovery result.
Record platform/artifact independently; process interruption, component testing,
native CI, recorded-source qualification and disk power-loss are different claims.
