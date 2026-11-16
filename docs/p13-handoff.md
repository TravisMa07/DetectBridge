# P13 orchestrator handoff

Verified 2026-11-16 against `origin/main` at
`c02449745ddb87605d0bd85841f77fdad2fb382a` (P12c merge). This is a readiness audit
and implementation plan, not an implemented P13 capability or dependency waiver.

**P13 is not Ready yet.** P11 trusted recorded Windows host identity is still
missing, its separate semantic acceptance record remains unresolved, and P12c
merged-main qualification was running at inspection. Complete the gates below
before starting P13 runtime implementation. Read-only design/contract research may
proceed while those gates are open. No P13 runtime work, merge or release is
performed or authorized by this documentation handoff.

## 1. Verified prerequisites

| Dependency | Evidence and current state | Gate for the next orchestrator |
| --- | --- | --- |
| P08 — writer | Issue [#8](https://github.com/TravisMa07/DetectBridge/issues/8) closed; implementation and prior merged-main AMD64 qualification recorded in [roadmap](roadmap.md). Writer passed on P12c PR head adf71f8 in run 43812450381. It is a metadata-only P07 writer, not a detection sink. | Existing capability available; preserve its tested behavior. P13 must explicitly implement a new compatible detection/event projection. |
| P11 — Windows | [PR #38](https://github.com/TravisMa07/DetectBridge/pull/38) merged as 46fb080; PR AMD64 passed. All 7,018 recorded inputs accounted for: 361 supported/skipped for identity_missing and 6,657 unsupported preservation rows. No recorded eligible/matched result. | **Blocked:** provenance-backed Computer-to-host binding and explicit resolution of the semantic-review gate in [P11 ledger](p11-ledger.md). A merge or generic praise comment is not that missing evidence. |
| P12 — Linux | [PR #39](https://github.com/TravisMa07/DetectBridge/pull/39), [#42](https://github.com/TravisMa07/DetectBridge/pull/42) and [#43](https://github.com/TravisMa07/DetectBridge/pull/43) merged. #43 merge is c024497; its description explicitly checks owner semantic/completeness review and merge authorization complete. This approval record supersedes the committed pre-merge pending state. | Bounded implementation and owner review complete; refresh merged-main qualification before calling the prerequisite Done under SDLC. Do not reopen the accepted bounded source scope merely because broad corpus coverage is absent. |
| P12c exact-head CI | adf71f8301d0b6c8ebcd4dc81d590186b6288ee3 passed [run 43812450381, attempt 2](https://github.com/TravisMa07/DetectBridge/actions/runs/43812450381), including actual assembly and required-checks. First attempt hit Maven HTTP 429 before tests; unchanged failed-job rerun passed. | Complete for that PR head. Retain the failure/rerun distinction. This is not merged-main evidence. |
| Current merged main | [Run 43873905332](https://github.com/TravisMa07/DetectBridge/actions/runs/43873905332) on c024497 was in progress. Successful Dependabot checks are unrelated to repository qualification. | **Pending:** require successful applicable jobs and required-checks on this merge, or the later actual base used. Resolve any failed required check without weakening it. |
| Issue/review bookkeeping | P11 [#11](https://github.com/TravisMa07/DetectBridge/issues/11), P12 [#12](https://github.com/TravisMa07/DetectBridge/issues/12) and P13 [#13](https://github.com/TravisMa07/DetectBridge/issues/13) were open. Issue text still contains initial backlog wording. | Do not infer implementation state from issue state alone. Reconcile P12 closure/board state after its merged-main gate; keep P11/P13 blockers visible. |

P10's compiler/evaluator/mappings are already merged and were declared complete
by the owner before P11/P12 authorization. Preserve their recorded semantic-review
history; do not invent an additional approval or reopen unrelated milestones.

### Closing the Windows gate

The inspected source metadata establishes scenario/collector context, not a stable
host identity. Neither Computer text, dataset ID, capture ID, metadata date nor a
new checksum can fill that gap. Hash validity proves binding consistency, not truth.
See [Windows guide](windows-adapters.md) and its pinned artifact/hash inventory.

A qualifying prerequisite follow-up must provide:

1. Authoritative, reviewable capture/host metadata tying the exact original XML
   Computer value and raw source namespace/instance to a real host identity. Use
   substantiated provenance for existing originals or create a separately reviewed
   controlled Windows recording; do not retrofit guessed identity into old inputs.
2. Immutable original objects, hashes/ranges/framing, exact provider/event versions,
   capture/collector/configuration context and terms review. Preserve known/unknown
   generation and command-line capture capability honestly. No new payload enters Git.
3. A versioned reviewed binding with source, computer, host_id, revision, provenance
   and canonical SHA-256, validated by the actual Windows boundary. Review content
   independently before running the adapter/evaluator. Synthetic kind stays synthetic.
4. Frozen source fields, identity, time, quality and actual rule expectations; prove
   eligible recorded Windows match and nonmatch using supported signatures and
   independently specified rules. Retain unsupported/parse/disabled-capture/missing
   identity distinctions, including original skipped recordings. Do not turn the
   current 361 skipped candidates into nonmatches by relabelling contexts.
5. Actual atomic Windows runner and independent verifier results, targeted Windows
   and shared consumer checks, owner source/semantic acceptance, an authorized
   prerequisite PR merge, and green merged-main checks. Streaming integration is
   still P13's responsibility.

No trusted Windows recording host/attestation has been supplied in this handoff.
If provenance cannot be established, report this concrete blocker; do not substitute
synthetic eligible fixtures, claim all prerequisites complete, or silently waive it.
The owner may explicitly revise a dependency, but that needs a recorded decision.

## 2. Start-of-session procedure

Read `AGENTS.md`, [README](../README.md), [architecture](architecture.md),
[SDLC](sdlc.md), [roadmap P13](roadmap.md#p13--integrated-enrichment-and-evaluation-outcomes),
[implementation ledger](implementation-ledger.md), [P12 acceptance map](p12-acceptance.md),
[P11 ledger](p11-ledger.md), [P12c ledger](p12c-ledger.md),
[source adapter interface](source-adapter-interface.md), [detection](detection.md)
and [writer guide](writer.md). Some ledger entries intentionally describe historical
checkpoints; the verified state above and subsequent GitHub evidence supersede them.

```sh
git status --short --branch
git fetch origin
git log -5 --oneline origin/main
gh pr view 43 --json state,mergedAt,mergeCommit,headRefOid,body,reviews
gh run list --branch main --workflow hygiene.yml --limit 3 --json databaseId,headSha,status,conclusion
gh run view 43873905332 --json headSha,status,conclusion,jobs
gh issue view 13 --json body,state,comments
```

Refresh exact SHAs/run status; do not reuse a pass from another head. Review checks
for the actual later base if main advances. Inspect a dirty checkout before any
switch; preserve user work. When prerequisites are green, create a short-lived P13
branch from that verified main. No direct main pushes, automatic merges or releases.
A handoff can be read from an unmerged docs branch; reconcile it against live state.

## 3. Evidence available without recapture

The local recordings were rehashed and their provenance/framing checks passed
while preparing this handoff: 30 audit rows and 11 authentication rows. This was
read-only original-integrity verification, not a new runtime or performance run.

| Evidence | Ignored local location and usage |
| --- | --- |
| Reviewed audit | Repo `.cache/p12-audit-reviewed-v1/`; catalog [linux-audit-execve-lab-v1](../catalog/recordings/linux-audit-execve-lab-v1.json). Use input-context-1.1 and frozen plan/output files. Original v1 capture metadata and run-0013 outputs remain intact; corrected context/1.1.0 uses batch completion observation and isolated run-0014. Never silently restore the obsolete observation interpretation. |
| Reviewed OpenSSH9 | `/Users/travisma/.t3/worktrees/DetectBridge/t3-0d1707c7-0b0f38be33ce0e0e/.cache/p12-auth-reviewed-v1/`; catalog [openssh9-password-lab-v1](../catalog/recordings/openssh9-password-lab-v1.json). Original root checkout does not supply this directory automatically. |
| Runtime reports | Repo `.cache/linux-assembly-reports/`; P12c ledger pins exact projects/checkpoints. Final bundle 5961fc44ac1548b52c59874f353a733672b4a49bb8b039e3d224f6e5d5de0c9d; JAR 364a342363e51c04b1e0af41bd61442eb2df8bc9daccfd2cc20731ffd4364745. These are P12 artifacts, not future P13 binaries or restore baselines. |
| Existing Windows | P11's retained originals/output/frozen-plan inventory is in the P11 worktree and ledger. It is preservation/skip evidence, not trusted eligible input. Rehash before reuse. |

Paths are machine-local conveniences, not service contracts or guaranteed contents
in a fresh checkout. Missing evidence fails the opt-in qualification; it must not
be replaced by regenerated messages. A new capture needs a new reviewed manifest.
Reports/observations are not authoritative Flink recovery state or a P14 archive.
Local-use approval does not authorize public payload/binary redistribution.

## 4. Existing integration boundaries and traps

| Area | Concrete reuse point | P13 obligation |
| --- | --- | --- |
| Windows parsing | [WindowsAdapter.java](../packages/windows-adapters/src/main/java/io/detectbridge/windows/WindowsAdapter.java), adapt(raw, resolver, context), returning event or diagnostic; [Offline.java](../packages/windows-adapters/src/main/java/io/detectbridge/windows/Offline.java) is a local runner | Add a real bounded checkpoint/delivery consumer. The existing offline runner is not a deployed Windows Flink pipeline. Respect Windows Computer binding and evidence resolver API. |
| Linux normalization/state | [Boundary.java](../packages/linux-adapters/src/main/java/io/detectbridge/linux/Boundary.java), [Assembler.java](../packages/linux-adapters/src/main/java/io/detectbridge/linux/Assembler.java), prepared audit/auth/tick/boundary/end transitions | Reuse semantic core. Preserve exact scope/membership, absolute age, retained closed keys/receipts and immutable late links. The external Commit API requires atomic output plus next state; do not implement it as an in-memory collector. |
| P12 checkpoint model | [Machine.java](../packages/linux-assembly-job/src/main/java/io/detectbridge/assembly/Machine.java), [AssemblyJob.java](../packages/linux-assembly-job/src/main/java/io/detectbridge/assembly/AssemblyJob.java), [assembly contracts](../contracts/linux-assembly/v1/assembly-input.schema.json) | Existing module is an isolated qualification job and owns its topics/bindings. Specify reuse/composition explicitly; do not turn its test deployment into production by renaming it or consume old checkpoints with a new artifact. |
| P10 evaluation | [Evaluator.java](../packages/detection-evaluator/src/main/java/io/detectbridge/detection/Evaluator.java), evaluate and evaluateExhaustive with input location; [v2 result](../contracts/detection/v2/result.schema.json), compiler/mapping tools | Compile once, match in Java. Bind actual bundle/mapping/source/evaluator versions and candidate provenance. P09/P10 result format is not a frozen P13 detection model. |
| P08 search delivery | [Projection.java](../packages/transport-writer/src/main/java/io/detectbridge/writer/Projection.java), [Window.java](../packages/transport-writer/src/main/java/io/detectbridge/writer/Window.java), writer contracts | Current projection accepts only P07 replay/quarantine/writer-failure topics; strict config, indices and roles are metadata-only. It cannot directly ingest normalized events/detection results. Introduce explicitly versioned P13 projections/config/indices and narrow permissions, preserving old P08 behavior. |
| Orchestrator integration | settings.gradle.kts, Gradle locks/verification, dependency inventories, tools/dev.py, change classifier, workflow and required aggregate | Serialize shared edits, select all affected consumers and add real gates only once implemented. No unused registry/framework or passing placeholder jobs. |

P12 topics use detectbridge.assembly.*; P09/P10 use detectbridge.detection.*;
P08 indexes replay and diagnostics only. Preserve their resources. Define dedicated
P13 resources and cleanup ownership in its design before any runtime. The four
implemented aliases are Image, CommandLine, ProcessId and User; use the actual
source capability profiles, not assumptions from a field name.

## 5. Resolve P13 design before implementation

Record routine decisions in the owning design; discuss consequential architecture
changes with the owner and add an ADR when required. Preserve A02–A07.

- Declare coverage for the actual Security 4688, Sysmon process-create, Linux
  audit execution and selected OpenSSH profiles. Legacy contract-example fixtures
  do not prove adapter extraction or recorded coverage.
- Define bounded raw/context dispatch, source/profile versions, trusted context
  authority, local evidence registration and accepted-input boundary. Never fetch
  arbitrary evidence URIs or execute transforms embedded in untrusted input.
- Define separate versioned tagged-event, matched-detection and compact outcome/
  diagnostic contracts. Preserve closed P03 and exact membership/provenance. Link
  detections to stable event/evidence identity plus run, actual rule/bundle and all
  decision-affecting versions. Freeze canonical identity/hash vectors before code.
- Specify enrichment's minimum meaningful scope and immutable version/snapshot
  semantics. Start with deterministic, reviewed metadata if accepted by the owner;
  do not invent external lookup providers, time-varying DNS/user resolution, threat
  labels, confidence or AI. Failure/absence/stale enrichment policy must be explicit.
- Preserve matched, unmatched, inapplicable, configuration_blocked, quality_skipped
  and evaluation_error separately. P10 capability blocking precedes quality gating;
  skipped source quality remains visible even when evaluation is blocked. A skipped
  or unsupported event is not an ordinary nonmatch.
- Emit bounded event summaries/diagnostics plus actual matched detections. Avoid
  per-event-per-rule unmatched rows; define overflow/detail references without
  silently dropping accepted evidence. Preserve distinct parser/preservation errors.
- Specify checkpointed input/state/output intent ordering and Kafka acknowledgments,
  permanent quarantine versus transient retry/backlog, physical duplicate handling,
  strict code/config/source/mapping/enrichment/destination restore bindings, and
  immutable late evidence. No Kafka exactly-once or host/disk-failure availability claim.
- Specify writer create-and-verify duplicate behavior, canonical content comparison,
  per-item failures, strict new templates/config/roles and run-isolated index IDs.
  No evidence bodies/source-field dumps in search or operational logs without an
  explicit reviewed data policy; retain accessible original evidence separately.

P14 archive/historical reprocessing, P15 activation, P16 broad outage qualification,
API/UI, attack chains and release/throughput claims remain outside P13. Do not claim
historical assembly reproduction merely by replaying processing-time timers.

## 6. Efficient execution and acceptance

Use a single orchestrator for shared changes. No delegation is required for this
handoff; do not create agents or extra checkouts unless the owner or applicable
instructions explicitly request them. Serialize heavy Docker qualification and
remove only owned resources. Reuse immutable dependency caches, not runtime state.

Proposed decomposition, to confirm after prerequisites (these are not new implemented
roadmap capabilities or approval to bypass dependencies):

1. **P13a contracts/composition:** freeze decisions, independent input/field/outcome/
   identity fixtures and provenance, then connect real adapter and mapped evaluator
   libraries through bounded composition. Include actual positive, negative and all
   four diagnostic outcomes on both source families, unsupported grammar and absent/
   failed/disabled/optional field distinctions. No service placeholders.
2. **P13b runtime:** implement actual Kafka/Flink dispatch, Windows delivery and Linux
   assembly/evaluation state/output intents, with dedicated versioned resources,
   strict restore binding and exact accepted-input accounting. Reuse prepared
   semantics; resolve any source-specific restore incompatibility explicitly.
3. **P13c writer/end-to-end:** implement actual normalized-event/detection/diagnostic
   projections and least-privilege indexing, then qualify both platforms from raw
   recorded evidence through search, including source/evaluation/preservation links.
   Keep these in one coherent implementation PR if splitting adds more risk than
   review value; otherwise use short-lived dependent PRs and explicit per-layer gates.

For each slice: commit independent expectations before implementation, run focused
behavioral checks, integrate shared changes once, broaden only to affected consumers,
open a draft PR early, and report exact head/artifact/platform/results. Bind Gradle
fixture preparation to source revision so a cached plan cannot drift from provenance.
Existing developer commands are `tools/dev.py check`, `java`, `windows`, `linux`
and `assembly` under `uv run --locked python`. Runtime commands/build/verify flags
are in the owning runbooks; do not run all heavy suites concurrently.

P13's final gate must demonstrate all of the following:

- Trusted eligible recorded Windows and Linux source paths run end-to-end into
  tagged/searchable events and linked matched detections; originals remain traceable.
- Independent positive/negative/edge cases prove all six evaluation outcomes,
  invalid/unsupported source preservation, quality and configuration distinctions,
  optimized/exhaustive equivalence where applicable, and exact version attribution.
- Unchanged retries are idempotent; same-ID different-content is an integrity
  failure. Other runs/bundles cannot overwrite live/prior results. Deliberate
  duplicates are counted physically and logically with stable identities.
- Actual checkpoint/TaskManager/JobManager restore, incompatible bindings, unavailable
  required sinks, writer bulk partial/permanent failures and bounded backpressure
  account for every accepted original as required output, durable quarantine or
  explicitly retained backlog. Counters alone are insufficient evidence.
- ARM64 and AMD64 exact artifacts pass actual applicable checks, existing P08/P09/
  P10/P11/P12 consumers remain green, operational logs remain value-free and no
  recording payload/credential/build output is committed. Numeric budgets are not
  throughput claims. Record every failed attempt and classified rerun independently.
- Owner semantic/design review, separate merge authorization and merged-main checks
  complete acceptance. Do not merge or release from a generic continuation request.

### Pasteable instruction for the next orchestrator

> Continue as DetectBridge's main orchestrator in
> /Users/travisma/GitHub_Projects/DetectBridge. Read docs/p13-handoff.md and the
> required repo instructions. Refresh main, P12c approval/merge/CI and P11 provenance
> before planning runtime. Clear the documented Windows binding/semantic and
> merged-main gates; do not infer them from a merge, hostname or passing synthetic
> CI. Present a bounded P13 design/acceptance plan, then implement only within the
> verified dependency scope. Preserve independent expectations, evidence and license
> provenance, strict recovery, six distinct outcomes and replay isolation. Use
> short-lived branches and actual component gates. Never merge or release without
> explicit owner authorization. Report any remaining prerequisite instead of
> claiming P13 is Ready.
