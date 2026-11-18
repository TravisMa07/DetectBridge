# P14c1 current-policy replay ledger

Owning [design and independent expectations](p14c1-design.md) precede code.
Current status: implementation and full local Linux ARM64 runtime qualification
passed on the exact artifact/source set recorded below. Native implementation CI,
owner acceptance/merge and actual merged qualification remain separate. Retention,
P05 import, controlled recorded reuse and complete P14 acceptance remain open.

## Freeze checkpoint (historical)

Base: owner merge P14b #51 as `943d143eb4e5dc6d07871513f993efbddf1ab230`.
Actual merged-main run 44326278636 is pending. No P14c1 production code has begun.
The next PR implements current-policy replay only; retention/deletion, recorded
qualification, P05 archive import and complete milestone acceptance remain open.

The base run's OpenSearch writer job 134878372291 failed during `gradlew help`
bootstrap: Gradle could not find ten plugin classpath artifacts via the Gradle
Plugin Portal. Original full log is retained at
`.cache/p14b-merge-ci-44326278636/opensearch-writer-verification.log`.
This log does not report HTTP 429, so it is not labeled a verified 429 failure.
No runtime qualification started in that job. Preserve the failed attempt and
qualify an unchanged retry independently before dependent implementation.

The first local freeze check stopped on a Gitleaks false positive: a synthetic
fixture path containing `auth` was used as a JSON key for a source-file SHA-256.
The redacted report `.cache/p14c1-gitleaks-redacted.json` identifies only that
public rule-file hash; no credential was present. Store source pins as explicit
`path` / `sha256` entries instead. The unpublished freeze is organized before its
first push; independent source bytes and expectations are unchanged.

Freeze commit `b068b5358acb6313f8eb19a4055c33f3953ba2b1` passed its native
required aggregate. This qualifies the freeze's applicable checks, not an
unimplemented current-policy runtime. Latest prerequisite run metadata remains
`.cache/p14b-merge-ci-44326278636/latest.json`: actual merged SHA 943d143,
attempt 1 still active with integration pending and the retained plugin-resolution
setup failure. A failed-jobs retry request was rejected with HTTP 403,
“This workflow is already running”. Production implementation remains gated by
the milestone's explicit requirement for a qualified merged P14b base.

## Qualified base and implementation

The pending-base statements above describe the freeze checkpoint. P14b actual
merged-main 44326278636 attempt 2 subsequently passed on exact 943d143 at
2026-11-18 15:24:07 UTC. The owner then merged bootstrap repair #53 as
`b495c2bc706d4ac7f2515fe7b1240c5b8ae70904`; its actual main run 44339557684
attempt 3 passed all applicable jobs/aggregate at 16:27:17 UTC. Both preceding
setup attempts remain failed. Original metadata/logs are retained under
`.cache/ci-bootstrap-merge-44339557684/`. Local regular merge f03fcaa brings that
qualified main into the published freeze branch without rewriting b068b53.
P14c1 production code began only after this prerequisite success.

The controller now validates explicit schedules, verified selection/plan/artifact
bindings and exclusive disjoint roots. It invokes a separate thin Java executor
against original producer 51a984de and reader e5eaea35, retaining original class
origins. Actual original Machine/Assembler/adapters/evaluator execute under the
explicit virtual clock. Each atomic committed transition includes state and output;
resume verifies the complete existing prefix before appending. The operator guide
is [current replay](current-replay.md). No live forwarding or old checkpoint is
adopted; remaining P14 work is explicit.

## Regressions and retained failed attempts

Semantic preflight regressions first failed strict-schema-only validation: seven
behavioral failures without setup errors are retained in
`.cache/p14c1-semantic-preflight-red-only.log`; an earlier temporary-path alias
setup failure is separately retained. Component green is
`.cache/p14c1-component-green.log`.

Independent core review found overlapping workspace/archive/catalog roots could
initialize files inside protected originals before later rejection. Six nesting
directions and equal-root cases now reject before mutable contexts; meaningful
red/green logs are `.cache/p14c1-root-overlap-{red,green}.log`. The runtime verifier
also checks protected byte snapshots after actual equal/nested-root rejection.

The first focused actual current executor da0ec741 passed frozen regroup semantics
on seven source inputs, but that preliminary pass is not final qualification.
An initial oracle incorrectly looked for Linux receipt time in the top-level time
projection. Original Linux contracts retain it under the context extension; the
oracle was corrected from that source fact, with failed report preserved at
`.cache/current-qualification-ee5c9a9ae272/report.json`.

Full runtime attempt `.cache/current-replay-qualification-1e2481397558/report.json`
used executor 03305ad0 after the root fix. Historical compatibility and ten
supplemental source/quality cases passed, but unchanged completed resume failed
`current_committed_result_conflict`. Only final state's `received_hash` and checksum
differed: the generated end control used unordered Java Map serialization in the
local wire. Canonicalize derived local input/control wire bytes before fingerprinting;
original archive bytes remain unchanged. The verifier now requires three fresh JVM
completed-resume executions with identical committed bytes and final fingerprint.
The failed attempt remains failed; `.cache/current-full-qualification.log` retains
its original diagnostic. Final exact-artifact runtime results follow separately.

Locked source checks passed 210 Python regressions, contracts/catalog/dependencies,
hygiene/secrets/workflows, Ruff and types in
`.cache/p14c1-full-source-corrected-check.log`. An earlier added test had a mypy
star-argument error, and two added documentation lines needed Markdownlint fixes;
those failed checks remain retained. Actual current build/components passed 12
regressions in `.cache/p14c1-deterministic-wire-build.log`. These are source/component
checks, not a substitute for archive-to-current execution and fault qualification.

The next full attempt, `.cache/current-replay-qualification-6ef2e8811e8e/report.json`,
used executor ea9d4740. Three fresh-JVM completed resumes preserved every committed
byte and final received fingerprint. Historical/supplemental cases, exact 1 MiB
request resume, isolation and timeout/deadline/short-age schedules also passed.
The supplemental resource-limit check then failed because its oracle inherited
P13's nine-rule skipped mask. The new frozen plan orders Image rule ...0001 before
Bob rule ...0004, so the independently required skipped mask is bit zero, not
P13's mask. Assert that exact rule ordering and use literal
`0000000000000000000000001`. Source fields, two-member resource closure and four
late links were unchanged. This is a verifier correction from the frozen plan,
not a production change or expected output generated by the new executor. Retain
the failed attempt and `.cache/current-full-qualification-green.log` despite that
log's premature filename; the attempt remains failed.

Attempt `.cache/current-replay-qualification-ff21c14c9d3f/report.json` passed all
eleven actual process kills and verified recovery prefixes, then the missing-result
fixture parked its removed directory inside the workspace. The workspace correctly
rejected that foreign entry before the intended missing-file assertion. Hold test
fixtures outside the workspace; do not weaken the production allowlist. This failed
harness attempt remains retained, and the complete suite is rerun afterward.

## Full local runtime qualification passed

Actual full command `uv run --locked python tools/current_replay_verify.py` passed
on Docker Linux ARM64 from local f03fcaa plus the implementation working tree.
Report `.cache/current-replay-qualification-28856f119825/report.json` has SHA-256
`db3a06a20ed009a0b0d1cdec65eaafc589a9cb04c5dd79104b5e4459e2cc45c6`;
full log is `.cache/current-full-qualification-complete.log`. The report pins the
complete controller/Java/validator/contracts/fixture/build-lock/oracle source set;
its aggregate qualification-source hash is
`3e1d07ee67ee11f22585d45f2b3c50115010565d07d4b8deaf063c119032ad51`.
This qualifies that working source/artifact set; native final-head CI is separate.

Exact executor is
`ea9d47406651a686546a2514f83fe59689fa38902e76b0c2c6aa129c37a511e2`;
reader `e5eaea3560d150e176cb0f68e941ca22efb25fb6f16b2a1d1d76465a94ef02d0`;
original producer `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
Pinned Flink image index and actual local Docker inspect ID are both
`sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`;
Docker reports selected OS/architecture `linux/arm64`. New rule bundle is
`91928727021f8a528ada1d08626f862624c051a757fad130c769e1f9a4893e88`,
plan `f1cc8ffd5c996af70ceb7541dccd1d05ddfb4dc20e5c8b6bd80cbc1325da0e8a`.
Original sealed selection is
`399b48702ad06d52657d72f3dd6fa9819a88355f38107cc175c6ee1c33598e4c`.

The primary regroup case has seven source inputs, eight transitions and four
logical outputs. Original five-member timeout membership remains immutable;
current regroup has six members and a different event ID. New Image rule matches
and Bob rule does not match Alice. Timeout/exact-deadline/one-millisecond age cases
retain their independently expected late link. Member cap two emits one manifest,
two tagged events, one quality diagnostic and four late preservations with no
detection. Historical execution and ten supplemental source/quality cases passed,
including Windows families/quality, CRLF, empty bytes, twelve-digit timestamp
precision and two distinct occurrences of identical range bytes.

Three fresh-JVM completed resumes preserve every run file/final fingerprint; exact
1 MiB request acceptance and one-byte-over rejection passed. Two runs isolate state,
membership/results and attribution. Eleven real process kills cover payload,
metadata, publication and advisory windows. All retained prefixes verify before
append. Compensated result corruption, fractional metadata, missing middle result
and gapped units fail closed. Ten preflight cases and eight root-overlap cases
reject without changing protected originals. Independent oracle mutations in
counts, attribution, membership and host all fail. Missing pinned artifacts and
objects, changed plan, root/binding changes, cap/reserve/permission failures and
injected ENOSPC/EIO stop safely. Owned orphan and timed-out helpers are cleaned up;
no helper containers remained after qualification. Original archive and historical
catalog byte snapshots remained unchanged throughout.

Locked source checks passed in `.cache/p14c1-qualified-source-check.log` with 210
Python regressions, lint/format/types and repository checks. Public synthetic
fixtures establish these bounded claims; controlled recorded replay and native
AMD64 current execution remain unavailable in this local result. Process kills and
injected I/O do not prove physical power-loss or disk-loss protection. Native CI,
owner review/acceptance, owner-authorized merge and actual merged qualification
remain distinct. P14c2 may stack after P14c1 acceptance checks pass, as explicitly
authorized by the owner; no merge permission or completed P14 claim is inferred.

## Qualified CI repair integration and stack

PR #54 native run 44400444347 attempt 1 passed every applicable job and required
aggregate 135159697427 on exact head
`b4d86831bb910de9d45e2ac73a8950472d7fa1d6`, completed 2026-11-18 21:50:23 UTC.
The five explicit acquisition/recorded opt-ins were skipped. Actual PR checkout was
GitHub test merge `ec523ff8c8fcc753fe0885d3421b3cecf77cb078`; this is PR evidence,
not an owner-merged-main pass. Reviews and refreshed inline threads were empty.
Full run/jobs, assembly/integration logs and thread metadata remain under the
original checkout's `.cache/ci-cache-pr-44400444347/`.

Native Linux AMD64 assembly project `detectbridge-p12-test-d0a66eb428e7` passed
52 inputs, 83 logical / 93 physical outputs with new JAR b328f293 and bundle b6c9f3b1
(full identities in [CI repair](ci-cache-fanout.md)). Its actual image is
`sha256:e4062260cbbbf5837b48ec2cf38b943e998389a85141c98550787a6615f984a4`.
Integration `detectbridge-p13-test-63864760253f` passed 44 inputs, 103 logical / 145
physical outputs with unchanged JAR 51a984de, bundle
`85976dd240d5816ef1dac29fec888e55be3ad251df293cc496b236f29979963a`,
image `sha256:5cbce1c92fc7f769a6baf935b13e15d6b29b03c97857651be03a1db902930845`.
These independently qualify the affected repair suites on native CI; they do not
transfer a pass to the new current-replay implementation or an eventual merge.

Integrate that qualified PR head with a regular local merge preserving all
published IDs. PR #52 stacks on `fix/ci-gradle-cache-fanout` while #54 remains
owner-controlled and unmerged. This additional integration boundary is necessary
to carry the verified shared checks into the new consumer; it is not a progress-only
commit or permission to merge. The source prerequisite remains qualified main
b495c2b; the CI repair is not made a circular service prerequisite.

The new current replay job now depends on successful toolchain preparation and
requires the same exact cache hit before bootstrap. The existing cache regression
first rejected the missing dependency/cache steps; after integration its explicit
consumer-count expectations increase from twelve to thirteen. Red/green logs are
`.cache/p14c1-ci-cache-integration-{red,green}.log`; the intermediate whole-source
check retained the three expected count mismatches rather than suppressing them.
Neither the executor nor processing contracts change in this integration.

The first combined-tree rerun failed before executing source inputs because the
new metadata observer inspected a tag-plus-digest alias absent from the local
Docker catalog. The prepared immutable repository-plus-digest reference existed,
as verified by the accepted builder. Preserve failed report
`.cache/current-replay-qualification-3896caacba10/report.json` and
`.cache/p14c1-ci-integrated-runtime.log`. Normalize only the observer's reference
exactly as the builder does; the selected image digest and helper execution do
not change. A permanent regression checks canonical reference use and rejects
malformed image metadata. This is a preparation/observer failure, not a replay
fault assertion or production behavior change.

The complete combined-tree replay/fault suite then passed again on Linux ARM64:
`.cache/current-replay-qualification-82ce2cf52e4d/report.json`, SHA-256
`d275067cd6507567fc3c4485f835c3fc8304d38df4cf69ec9654c2dedfa5efc1`;
log `.cache/p14c1-ci-integrated-runtime-final.log`. Its qualification-source hash is
`2db4412b3b73940882252cdba342c9988b014ff009f7e095b818d7e936620f2c`.
The recorded source is aac3217 plus the regular qualified-repair integration working
tree. Executor ea9d4740, reader e5eaea35, producer 51a984de and selected Linux ARM64
image ID remain unchanged (full identities above). All frozen schedules, three
fresh-JVM resumes, isolation, source/quality, eleven interruption windows and
negative storage/integrity/helper cases passed; archive/history stayed unchanged.

Actual prefetch with the new module passed in
`.cache/p14c1-ci-integrated-prefetch.log`. Locked final checks passed 229 Python
regressions and all contracts/catalog/dependency/hygiene/secrets/workflow/lint/type
checks in `.cache/p14c1-final-stack-source-check.log`. Native CI on this integrated
implementation head remains required; the earlier freeze's pass is not its runtime
qualification. After those acceptance checks pass, the owner explicitly authorized
P14c2 work stacked on this branch without waiting for merge permission.

Stacked PRs also need actual native workflow triggers: the previous filter selected
only PRs targeting main. A focused regression failed for the two intended stack
bases. Explicitly allow `fix/ci-gradle-cache-fanout` and
`feat/p14c1-current-replay` alongside main for the existing read-only pull-request
event; main-only push qualification is unchanged. No privileged event or token
permission is added. Logs are `.cache/p14c1-stack-trigger-{red,green}.log`.
The explicit required aggregate and actual workflow jobs remain the acceptance
gate even if a temporary stack base has different branch-protection rules.
