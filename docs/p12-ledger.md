# P12a subsystem ledger

## Checkout and ownership

- Base verified clean before editing:
  df3144822ddd5694b9244ae29eb4a3c9e2815376.
- Original child branch: t3/linux-audit-assembly; now feat/p12a-linux-adapters.
- Worktree: /Users/travisma/.t3/worktrees/DetectBridge/t3-0d1707c7-0b0f38be33ce0e0e.
- Owner authorized dependent implementation after P10. No separate P10 semantic
  approval is invented; referenced merged-main CI was not polled/watched.
- Linux owns module code/tests, source/profile/schema proposals, source review,
  synthetic expectations, design and runbook. Shared ownership remains with the
  orchestrator; actual root registration is a distinct integration commit.
- Initial design/expectations commit: 6f65020.
- Subsystem implementation: 232b634.
- Separate shared integration proposal (root Gradle registration only): 3362780.

## Delivered offline core

Raw LF audit parsing for SYSCALL/EXECVE/CWD/PATH/PROCTITLE/EOE; explicitly pinned
execution ABI/syscall pairs; positional/split/hex/empty/repeated argument decoding;
all raw token/PATH occurrences; no shell command_line or singular file.path.
Exact OpenSSH9 RFC5424 Accepted/Failed password parser, including IPv4/IPv6,
structured data and explicit NIL-time fallback; excluded grammars stay unsupported.

Bounded scope-keyed assembly with injected clocks, closure independent from
eligibility, transactional output/state callback, idempotent same-ID retries,
conflicts, immutable late links, resource backpressure and retained closed keys.
State serialization/restore is offline and version/policy/source/mapping bound.
P03 schemas/identities and existing runtime topics/projects remain unchanged.

Interfaces and caller retention/durability requirements are in the
[runbook](p12-runbook.md). Module-local context, context-extension, manifest,
preservation and state schemas are separately validated. New -p12a source/profile
IDs distinguish proposals from existing fixture content. No shared adapter module
or competing root registry was added.

## Verification evidence

Local macOS ARM64 with locked Python 3.12.12, Java 17.0.21 and Gradle 9.9.1:

- Locked tools/dev.py check passed: repository/contract/catalog/deployment checks,
  121 Python regressions, Ruff and mypy. Final log is ignored
  .cache/p12-check-final.log.
- Locked tools/dev.py java passed: existing transport (5), evaluator (19) and
  writer (15) Java tests/builds plus 20 legacy, 20 mapped and 12 P10 mapping
  independent YAML-to-Java semantic cases. Final log is ignored
  .cache/p12-java-final.log. The final root Gradle invocation reused successful
  unchanged Java task outputs; the semantic CLI cases executed again. Root command
  does not implicitly run Linux tests.
- Offline strict-lock/verification Linux test and jar tasks passed: 31 tests. The suite
  includes actual compiler-to-adapter-to-P10 Evaluator match/nonmatch/block/skip,
  interleaved scopes, original identity/hash literals, malformed/excluded auth,
  all closure/resource modes, durable-callback failure, late/ended lifecycle,
  closed-budget admission stops, large-record/output bounds and state round trips.
  Final log: ignored .cache/p12-tests-final.log; XML reports are ignored build data.
- Module fixture-preparation locked Ruff lint/format passed. All 23 module
  coordinates already exist in base locked modules; module lock and local review
  metadata include compile/runtime/test configurations. No new upstream artifact
  or verification checksum was needed.
- Production jar excludes test classes, synthetic rule fixtures and contract
  example events. Module source/profile/schema resources are included.

Pure-state round trips are not actual checkpoint recovery. No Docker/runtime,
AMD64, performance, production integration or recorded eligible acceptance is
claimed. No evidence payload, credentials or build artifacts are committed.

## Child handoff blockers (historical)

The [shared handoff](p12-integration.md) enumerates concrete Gradle/dev/CI/gate,
inventory and context/schema reconciliation requirements. No draft PR was opened
without that serial integration. Existing root gates were preserved.

Independent owner review of P12 expectations/completeness policy remains pending.
Existing audit excerpts lack trusted host/generation/completeness. Reviewed source
research rejected the inspected Loghub and Splunk auth candidates for exact scope;
no suitable exact OpenSSH recording was substantiated. A pinned real Linux
OpenSSH9/rsyslog capture protocol is proposed, not executed. Actual capture,
provenance/terms, immutable hash/revision and independently reviewed expectations
remain acceptance blockers; no synthetic data is substituted for recording.

P12a acceptance remains incomplete. P12b was not started and requires a separately
authorized P12a merge and main qualification. Full P12 and P13 remain blocked.
No PR push, merge, release, archive or production pipeline occurred in this child.

## Orchestrator integration and current status

P12a is stacked above P11 PR #38 at 4f741c2 to serialize shared changes; this does
not create a semantic Linux dependency on Windows. The original child commits were
rebased with both Gradle module registrations retained. Source contracts/P03
registry/version semantics remain unchanged. Context proposals now align on the
P11 mapping wrapper and source-bound reviewed/synthetic host hash. Manifest scope
references the same context shapes instead of duplicating stale definitions.

Root java and a real classified/fail-closed linux-verification CI job select Linux
tests, artifact/notice checks, verifier regressions and lint/format. The combined
inventory includes all 23 existing reviewed Linux coordinates, with no new
artifact/checksum or fresh advisory claim. An owning inventory records exact locks.

Independent read-only review reproduced URI scheme case rejection and incorrect
RFC5424 structured-data rejection (duplicate parameter names and unknown escapes).
Both were corrected with boundary/literal regressions grounded in P03/RFC5424.
Review found no further concrete assembly/state defect; owner completeness-policy
and expectation review remains outstanding.

The selected real authentication recording now exists: OpenSSH 9.2p1-2+deb12u10,
rsyslog 8.2302.0-1+deb12u2, pinned Debian base and exact main packages, immutable
local image ID and container generation. Real SSH client actions produced exactly
one accepted and one failed password message. All 11 native/collector rows are
retained, two normalize eligible, nine preserve unsupported. Both eligible records
are true nonmatches for the separately authored auth-user rule selecting alice.
Original synthetic tests separately prove matches and other outcome gates.
Catalog metadata pins all original byte hashes, configuration, binary/package
versions, Docker identity, acquisition time, collector transformation, local-use
terms and independently specified per-record fields/outcomes. No payload, password,
private key, image or binary was committed/published. Preliminary captures are
superseded by `.cache/p12-auth-reviewed-v1`, never acceptance substitutes.

An atomic bounded inline-only authentication replay runner feeds actual adapter
output to P10. A separate verifier validates originals/framing, raw/context/event/
preservation/result contracts, fields, identities/membership, frozen bundle and
result attribution. Failed publication leaves prior output untouched. This is
offline evidence, not checkpointed streaming or general audit replay.

Local ARM64 verification passed: root check (127 Python regressions), combined Java
and independent P10 semantic cases, Linux gate and three verifier regressions,
subsystem lint/format, production jar/distribution resource and license checks.
Logs remain ignored at `.cache/p12-integrated-check-final.log`,
`.cache/p12-integrated-java.log`, `.cache/p12-integrated-linux-final.log`. Final
recorded replay/frozen-plan results are recorded below.

Outstanding: AMD64 CI, owner independent-expectation/completeness review, eligible
recorded audit host/generation/completeness provenance, separately authorized P12a
merge/main qualification and dependent P12b checkpoint qualification. P12 and P13
remain incomplete. No merge/release, production wiring or throughput claim.

Integrated implementation 89dfa04 passed locked root check (127 regressions),
combined Java, 34 Linux Java tests, 35 Windows Java tests, three independent
recording-verifier regressions and subsystem lint/format/artifact checks. Final
logs: `.cache/p12-integrated-check-head.log`, `.cache/p12-integrated-java-head.log`.
The Gradle preparation task now binds its inputs to Git revision, preventing stale
rule provenance across commits. Secret scanning passed with no leaks in
`.cache/p12-secrets-head.log`.

The fresh recorded replay uses immutable `.cache/p12-auth-reviewed-v1/frozen-plan.json`
and `.cache/p12-auth-reviewed-v1/output-head.ndjson`; runner and independent verifier
passed all 11 rows, two eligible/nonmatched and nine unsupported. Full original
artifact rehash, native-to-collector body identity, module-local context and
preservation schemas, P03 events, exact input/result/membership attribution and
frozen plan identity passed. Separate same-count tamper probes rejected changed
classification, source port, bundle hash, preservation reason and original cursor.
Logs remain ignored at `replay-head.log` and `qualification-head.log` under the
same recording directory. These results establish the selected local auth slice;
they do not establish recorded audit eligibility or P12b recovery.
