# P14b historical replay qualification ledger

Owner: primary agent; branch `feat/p14b-historical-replay`; issue #14.
[Owning design and independent expectations](p14b-design.md) precede production
implementation. P14a is owner-merged as
`cd6f46ec70e6c7ca17e3cd21594e396ef541509c`; actual merged-main run 44232624596
attempt 2 passed before production implementation. The P14a ledger preserves its
[original merge-run failure](p14-ledger.md) and original logs. No PR-head CI is
transferred to the merge. Local P14b runtime evidence is attributed below; native
CI, owner acceptance and complete P14 acceptance remain separate gates.

## Pre-implementation packet

Closed request/selection/run/result/commit 1.0.0 schemas and the original synthetic
identity vector precede code. The source fixture packet freezes existing P11/P12/
P13 input factories, literal outcome counts, source fields, distinct timeout/EOE/
incomplete audit memberships and late links. No expected outputs were generated
by a new historical executor. Original synthetic inputs are Apache-2.0; private
originals remain ignored and require their existing catalog/terms/binding review.

A separate external catalog resolves the P14a root-layout compatibility constraint
without changing original writer bindings, source objects, offsets or formats.
Exact accepted producer JAR 51a984de is the only supported execution profile;
newer rebuilt libraries cannot silently substitute for original parser/evaluator
versions. Replay artifacts, results and state have explicit finite bounds and
isolated run/destination identities. Current-policy reprocessing remains P14c.

Locked root `check` passed 177 regressions on the documentation/schema-only working
tree; log `.cache/p14b-preimplementation-check.log`. Explicit checks covered all
new schema metaschemas, original fixture/source hashes, identity vector, request
positive/negative/signed-64 boundaries, Markdown and content/relative links.
These establish draft contract consistency, not parser/evaluator execution,
archive-to-replay reproduction, interruption recovery or native CI.

## Required implementation evidence

Retain the meaningful missing-behavior red before implementing the executor.
Qualify actual old-JAR parsing/evaluation, immutable historical membership and
complete logical original-output reproduction against the frozen independent source
oracles. Qualify two new run scopes, missing/conflicting input/artifact failures,
changed resume bindings, interrupted payload/metadata/publication, corrupted
commits and finite storage failures through actual processes. Run prior affected
archive/consumer suites and record exact revisions/JARs/plans/images/platforms.
Local private recorded qualification and unavailable native coverage stay separate.
Owner review, explicit merge authorization and merged-commit success remain open.

The separate design/expectation freeze is commit 5922901. No P14b production code
precedes it. Local original integration components passed again under
`uv run --locked python tools/dev.py integration`; log
`.cache/p14b-prerequisite-component.log`. The local old JAR's full hash remains
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
These local checks do not replace P14a merged qualification. Attempt 1's runtime
jobs all passed; unchanged failed-toolchain/aggregate retry was accepted after
that run completed at 04:18:11 UTC. Implementation awaits its actual result.

## Implemented boundary and meaningful regressions

`historical.py` provides build/seal/run/resume, closed 1.0.0 wrappers, content-pinned
artifacts, a separate exclusively mutated catalog and authoritative unit commits.
The reader exports verified original Kafka rows/objects read-only. The thin Java
executor checks the accepted producer JAR before class loading and uses that JAR's
original input schemas, range/framing resolver, adapters, assembler closure and
compact evaluator. No original producer/library bytecode changes. The pinned base
image supplies its original logging runtime. CLI/validator/schema/lock bytes are
also inside the executor identity; incompatible controllers fail explicitly.

The focused timeout test first ran the original live end-of-run grouping path.
Original independent counts/membership passed, but historical reproduction failed
with `historical_original_outputs_mismatch` because the closure changed. Log:
`.cache/p14b-focused-red.log`. The explicit original-membership/closure bridge
passed the focused reproduction afterward; logs `p14b-focused-green.log` and
`p14b-original-boundary-green.log` remain local. Those preliminary artifact passes
are not reassigned to subsequent executor builds.

An invalid original P13 input wrapper initially borrowed valid old outputs when
only the pure adapter was called. The focused regression caught that acceptance;
`p14b-input-wrapper-red.log` records it. Reusing the original runtime schema and
registered-object/framing resolver rejects it with `historical_runtime_schema`;
`p14b-input-wrapper-green.log` records the corrected behavior. This preserves the
existing producer's admission boundary rather than inventing another parser.

Filesystem regressions separately caught retained helper diagnostics blocking
catalog reopen, lock creation in a foreign P05-shaped root, glob interpretation of
a literal catalog name deleting unrelated initialization metadata, and unreadable
directories disappearing from storage accounting. Their red/green logs are retained
under `.cache/p14b-*`. Fixes preserve diagnostics, validate ownership before writes,
treat names literally and propagate scan errors. Fractional counters with newly
computed checksums are rejected; original UUID identity cannot be reused through
case changes. These are actual negative behaviors, not setup errors counted as
required publication faults.

## Preliminary runtime attempts and retained failures

Early compiler/test-classpath setup errors and missing standalone SLF4J are setup
failures. The historical runtime now uses the exact pinned original environment's
logging libraries; no parser dependency was silently replaced. They do not count
as the semantic red or a required fault assertion.

Preliminary executor b38c0be0 / reader 390ef558 qualified ten source units,
two isolated runs, eight then-selected unit publication points and actual Kafka
project `detectbridge-p13-history-812ea3297e` (19 inputs / 44 physical outputs).
Report `.cache/historical-qualification-4abb96570454/report.json` retains the exact
hashes. These are historical preliminary artifacts, not final-artifact evidence.

Executor 0b6834b0 / reader 390ef558 subsequently qualified source ranges, helper
parent-kill/client-timeout recovery and expanded original source boundaries.
Reports `historical-qualification-177a8e88ec45` and
`historical-qualification-2a471962f98d` retain exact artifacts and tool/diff hashes.
The latter's actual project `detectbridge-p13-history-da9632bb91` passed 24 inputs,
57 physical outputs and two isolated historical runs. Empty LF records preserve
`unsupported_source`; CRLF grammar preserves `extraction_failed`, not a fabricated
nonmatch. Twelve-digit observation precision and two distinct dataset occurrences
with identical record bytes survived archive retrieval and original processing.
No private recording or throughput result follows from these synthetic cases.

A later expanded seal fault attempt failed before its intended crash: its harness
passed a string where the bounded JSON loader reopened a `Path`. Report
`.cache/historical-qualification-6fc79e8c5785/report.json` and log
`.cache/p14b-qualified-historical.log` preserve the actual `AttributeError` and
failed `during_file` assertion. It is not counted as a publication fault pass.
The loader now parses the single bounded read and accepts the actual CLI/path
representation; the full fault matrix is rerun on the corrected artifact.

The separate `.cache/p14b-image-inspect-preflight-failure.log` records a setup
failure inspecting a fully tagged digest on the local Docker store. The exact
repository digest existed and canonical repository@digest inspection succeeded.
Only inspection was corrected; execution retains the trusted digest pin. Explicit
build provisions that pinned image if absent, while runtime remains network-free
and refuses implicit image pulls.

## Scope and remaining acceptance

Current-policy replay, deletion/retention coordination, P05 import and complete P14
acceptance remain P14c/later bounded work. Private accepted-original archive replay
is pending; no private originals were recaptured, replaced or uploaded. Native
private-recording coverage remains unavailable under the accepted P13 limitation.
Public synthetic CI is separate. Owner review/semantic disposition, explicit merge
authorization and actual merged-commit verification remain open for P14b.

## Prior full local historical qualification — Linux ARM64 containers on Darwin

`uv run --locked python tools/historical_verify.py` passed on the implementation
working tree after freeze 59229013c22afbc45e923266c8c1e064165fdb1c. The actual
source diff is retained with the report, SHA-256
`5a8ee341b6ea759c6a2e7fbc2cbb10c29632f4c17ff226a5ccaecbe36033fd9c`.
This is an attributed working-tree result, not CI on a later commit.

Exact executed artifacts:

| Artifact | SHA-256 |
| --- | --- |
| Historical executor, including controlling CLI/validator/lock/schemas | b98f2f3324fd1a14618360786c58b62a706706bc3788d18425cc0c1b7944d693 |
| Read-only archive reader / current archive JAR | e5eaea3560d150e176cb0f68e941ca22efb25fb6f16b2a1d1d76465a94ef02d0 |
| Unmodified original P13 producer/parser/evaluator JAR | 51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d |
| Qualification-only original producer probe | 2759ee259ba282946efd45a3780c2e3202a404aca50688652ca2c541d3856c17 |
| Exact original plan bytes | 3190a7481e1439d547fddbe36af79e9e004156a0fb41938a3ea592a15d90a5cf |
| Original evaluation bundle | d400c2b4db023a71998a3042887f8bc9a813493a3513eb6179cd65db6f1d5504 |

Image: trusted `flink:2.2.1-scala_2.12-java17` index
`sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`;
Docker inspection selected Linux/arm64. Host is Darwin; this is not native AMD64
or physical power-loss qualification. Helpers ran with no network, a read-only
root, 512 MiB memory / 320 MiB heap, one CPU and bounded mounts.

Report `.cache/historical-qualification-d3cd729cfbb5/report.json`, SHA-256
`e80ece571f435c64a092e17f2c6b14dd813cde4feafc159f53e866674bb37903`,
retains exact tool hashes, selections and platform. Main observations:

- Fifteen source units passed independent original and replay field/count/match/
  attribution/membership checks, including eligible/incomplete/late audit, Windows
  skipped/budget/extraction, authentication, source ranges, identical-byte distinct
  occurrences, empty LF, CRLF and twelve-digit observation precision.
- Two isolated runs retained event/evidence identity with disjoint processing and
  detection IDs. Completed resume left run files byte-identical.
- Eleven actual unit/advisory process-interruption points and seven artifact/pin
  publication points recovered without replacing committed output. A killed parent
  and client timeout removed owned helpers before resume. Missing selected output,
  invalid original wrapper, same-ID conflicting content, missing referenced object
  and recomputed-checksum fractional commits failed for their intended reasons.
- Separate actual original-producer API cases reproduced `dataset_end` and
  `resource_limit` closures through the archive/old-JAR bridge. Together with the
  main source cases these cover all four original closure reasons. Those two
  component cases are not presented as separate Kafka deployments.
- Actual Kafka/Flink project `detectbridge-p13-history-c80fe1e5a6` passed 24 source
  admissions and 57 physical outputs through durable archive publication, sealed
  selection and two isolated historical executions. Independent P13/P12 oracles
  checked the original producer and both replays; stored outputs were not copied
  as execution. Kafka selection is
  `552985f7928910754b8d8ba93bd9f5e690e154832adc1888e072f5008864b16d`.

The exact full runtime log is `.cache/p14b-final-runtime-qualification.log`.
Locked `uv run --locked python tools/dev.py check` passed 190 Python regressions,
contracts/catalog/dependency checks, hygiene/secrets, Markdown/content/workflow
checks, lint/format and types; log `.cache/p14b-final-source-check.log`. Thirteen
new component regressions are included. No passing placeholder job was added:
the new conditional native gate runs actual component and full runtime checks,
and the stable aggregate rejects its applicable failure/cancellation/skip.

A subsequent run-allocation reservation changes the bound executor; this prior
pass does not qualify that new artifact. Its independent qualification follows.

## Archive compatibility qualification

The actual archive consumer/recovery suite passed all 26 scenarios and 30
occurrences in project `detectbridge-p14-test-ab740b1282c6` on Linux ARM64
containers on Darwin. Archive JAR SHA-256 is
`e5eaea3560d150e176cb0f68e941ca22efb25fb6f16b2a1d1d76465a94ef02d0`;
qualification probe is
`e3afd9e369716671e648845cff64970294f2bb4ff6b8af1e20a46c0b8a8292bc`.
The trusted Flink image index is the same pinned index recorded above.

Report: `.cache/archive-reports/detectbridge-p14-test-ab740b1282c6.json`;
log: `.cache/p14b-archive-runtime.log`. This independently covers exact bytes,
null/empty values, headers/ranges, all nine topics, payload/manifest publication
crashes, Kafka control-offset gaps, group reassignment, missing dependencies,
permissions, broker outage, corruption/offset validation, committed-ahead state,
the 32 MiB incompressible boundary and topic UUID replacement. Repeated topic
initialization created zero topics after the initial nine.

Public native CI and owner review/merge remain pending.

## Final candidate local qualification

After reserving catalog capacity before initial run-manifest allocation, the full
historical command passed again on the exact final executor
`32bad6f526e3208bf4b2684979a4d600c82b35070e39cbeb3a5fce6d5fccfcc4`.
Reader, original producer, qualification probe and pinned image are unchanged from
the prior full run above; their passes are independently re-established here.
Original plan SHA-256 is
`3190a7481e1439d547fddbe36af79e9e004156a0fb41938a3ea592a15d90a5cf`.

Report `.cache/historical-qualification-73f813ec50e8/report.json`, SHA-256
`19895d2d920690a7726b7834e80a3d00d1078371bb6f8d844dba68ae66be3f5c`;
log `.cache/p14b-final-candidate-runtime.log`. Source was freeze
`59229013c22afbc45e923266c8c1e064165fdb1c` plus the retained working-tree diff
`141caeb776191db08ba73425248168f927f1a5b680857f1947216a0f0009a042`.
This is local Linux ARM64 container qualification on Darwin, not native CI or
merged-commit evidence.

All fifteen units, two isolated component runs, eleven unit/advisory interruption
points, seven artifact/pin publication points, helper parent-kill/timeout cleanup,
exact retry/conflict handling and missing-object rejection passed again. Separate
original-producer `dataset_end` / `resource_limit` closures passed. Actual
Kafka/Flink project `detectbridge-p13-history-e7cc375429` admitted
24 inputs and archived 57 physical outputs; both isolated historical
runs passed independent source/field/count/match/attribution/membership checks.
Kafka selection is
`872d1e4058d9043dc78916fbc68c8b45f3c74491e88a7e7fe703d2ec8c360c89`.

The final locked source check passed 190 regressions, contracts/catalog/dependency
checks, hygiene/secrets, lint/format and types; log
`.cache/p14b-final-source-check.log`. The nine changed Markdown files were also
checked through the locked Markdownlint API; content/relative-link and workflow
validation passed. Public native CI, owner semantic review and merge authorization
remain separate open gates. No private recorded replay or complete P14 acceptance
is claimed.
