# P12c — Reviewed authentication checkpoint qualification

Small follow-up to merged P12b #42, based on main e2d06c3. This adds an opt-in
qualification command, not a parser, policy, state format or production pipeline.
Accepted A02/A03/A06 and ADR 0012 remain unchanged.

## Dependencies and scope

Require P12b's immutable built artifact and all original local artifacts from the
reviewed openssh9-password-lab-v1 catalog. Reuse its native/collector body check,
package/container/host binding and byte hashes before starting any runtime. Missing
or changed originals fail; never recapture or generate a substitute automatically.
The recording is in the P12a checkout's ignored cache; an explicit directory is
required. Catalog terms permit local qualification, not public payload publication.

Freeze expected events from the reviewed catalog before injection: all 11 rows,
two eligible password outcomes (user, endpoint, source time), nine exact unsupported
preservation documents. Retain original input/context and independent expectations
in the exclusive ignored project before Kafka admission. The evaluator is not an
oracle; P12b emits no evaluation results.

Force actual event-sink RecordTooLarge failure using P12b's read-back-verified
policy. Independently confirm the completed checkpoint retains blocked event
intents. Restore the same bound artifact with healthy output, account for all
original inputs and logical outputs, then replay unchanged evidence under a new
run ID. Verify stable evidence/event IDs and isolated processing attribution.
Count physical recovery duplicates separately and require byte identity. Existing
strict incompatible-restore, all-sink and broker qualification stays intact.

## Acceptance and exclusions

- Local original hashes/provenance and all per-record expected outcomes verified.
- Real required-sink failure, completed-checkpoint retention and explicit restore
  drain the original recording without missing/unexpected logical documents.
- Separate replay run preserves evidence identity and original context bindings.
- Tests reject same-count semantic changes, changed original bytes and scope;
  existing synthetic tests still execute without local recording access.
- Locked repository/component checks pass. Record actual local runtime outcome
  and PR CI separately; missing recording is a failure of the opt-in command.

No eligible audit evidence, trusted Windows recording binding, owner semantic
approval, full P12/P13 readiness, performance, release or merge authorization is
created. Owner completeness/expectation review remains required. Evidence and build
artifacts stay ignored. No public fixture or new third-party dependency is added.
