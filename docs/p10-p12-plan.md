# DetectBridge P10–P12 consolidated plan

Accepted for implementation by the owner after planning. Every merge and release still requires separate explicit authorization. This document preserves the planning baseline; see [implementation ledger](implementation-ledger.md) for current status.

## Verified baseline and limits

Fetched origin on 2026-11-14 local time. Local main and origin/main both resolve to `4d7d685ae65b2163906f7b662aac411583c5250d`; the checkout is clean. P08 PR #35 merged as `430609a17996470159f07fc0cfe53028e552a5ef`; P09 PR #34 merged as current main. GitHub reports both PRs MERGED. Their review arrays and P09 comments contain no independent semantic-expectation approval. P09 PR body and detection guide explicitly leave that review pending.

Exact merged-main Repository hygiene runs:

- P09/current main: [merged-main CI](https://github.com/TravisMa07/DetectBridge/actions/runs/43655314953)
- P08 merge: [P08 merge CI](https://github.com/TravisMa07/DetectBridge/actions/runs/43652317692)

Both succeeded. Current main passed hygiene, secrets, toolchains, local stack, transport, writer, detection and required-checks jobs. The workflow specifies Ubuntu AMD64 and detection build/semantic/recovery qualification. Optional acquisition, replay and recorded transport/writer jobs were skipped; these runs do not establish fresh recorded-data qualification. ARM64 evidence in the handoff is historical, not rerun here. No build, test suite, runtime qualification or capacity measurement was run during this planning session.

Existing P09 worktree `/Users/travisma/.codex/worktrees/e48e/DetectBridge` is clean at `dc13530`, branch `codex/p09-compiler-evaluator`. Leave it intact; do not reuse it for concurrent implementation.

Stale status text to correct in P10a: roadmap calls P09 draft and P08 pre-merge; P09 design says implemented in draft; CONTRIBUTING still defers detection implementation/runtime tests. Correct merge and CI facts while retaining the outstanding semantic review and source-coverage limitations. README qualification language should identify recorded evidence precisely rather than imply broad acceptance.

Implemented boundary: versioned raw/normalized/source contracts; provenance-aware acquisition; isolated resumable replay; checkpointed raw transport; independent metadata-only OpenSearch writer; synthetic normalized-input Sigma compiler/Java evaluator and separate Flink job. Raw adapters, integrated production detection, result-to-OpenSearch, archive and activation remain future work. P09 result IDs remain distinct from P13 detection IDs. Preserve pinned pySigma replaceability/license obligations and the unresolved shaded Jackson finding in the upstream Flink image; application patches do not remediate it.

## Accountability and dependency ledger

All planning used base `4d7d685`. P11 and P12 child planning ran concurrently, read-only, and is complete. The main orchestrator owns P10 and final integration. Implementation paths below are proposals, not created worktrees or branches.

| Unit | Accountable implementation owner | Required base/dependencies | Proposed branch | Status and acceptance gate |
| --- | --- | --- | --- | --- |
| P10a | Main orchestrator | Current main; P04/P09 merged | feat/p10-mapping-contracts | Planned: mapping/provenance contracts, matrix, diagnostics, compiler and reader compatibility |
| P10b | Main orchestrator | Authorized P10a merge + green merged-main checks | feat/p10-source-selection | Planned: selector/equivalence, semantic review, runtime/recovery; completes P10 only with P10a |
| P11 | Windows child, orchestrator integrates | Complete accepted P10, authorized merges and green main | feat/p11-windows-adapters | Child plan complete; implementation blocked on P10 |
| P12a | Linux child, orchestrator integrates | Same post-P10 main as P11 | feat/p12-linux-assembly | Child plan complete; parser/assembly core plus evidence acquisition gates |
| P12b | Linux child, orchestrator integrates | Authorized P12a merge + green main | feat/p12-assembly-recovery | Planned: actual checkpoint/recovery qualification; completes P12 only with P12a |
| P13 | Future integrated owner | P08 + accepted P11 + complete accepted P12 | Not assigned | Blocked; no integrated writer, enrichment or detection-ID implementation here |

Create one dedicated worktree and draft PR per implementation unit only after authorization. Record the actual base SHA, worktree path, branch, PR, implementation/qualification/review/merge states and evidence links in the ledger as they become real. A merged prerequisite with unresolved semantic acceptance is not sufficient to call the dependent milestone accepted. P10a/b are cohesive portions of a single P10 gate; P12a/b are portions of a single P12 gate.

## Shared ownership and interfaces

The orchestrator exclusively coordinates shared schemas/readers, common adapter context/result interfaces, Gradle module registration, root locks/verification metadata, dependency inventories, developer commands, CI classification/required-checks, README/roadmap/architecture status. Children propose these changes; they do not concurrently edit shared integration files. P11 owns Windows code/tests/profile content/design/runbook; P12 owns Linux code/tests/profile content/assembly manifests/design/runbook. P10 owns generic mapping/compiler/evaluator/selection logic.

Freeze these interfaces through P10 before adapter coding:

1. **Mapping artifact:** immutable ID/version/hash; exact source-contract ID/version/content hash; Sigma alias, ECS target, declared scalar/array type, source capability and fixed parser-transform identifier/version. Source JSON Pointers refer to named parser-extracted attributes, not arbitrary executable transformation code. P10 validates the artifact; adapters execute a fixed reviewed transform registry. No scripts or user code in configuration.
2. **Types and aliases:** initial rule aliases remain Image→process.executable, CommandLine→process.command_line, ProcessId→process.pid, User→user.name. P11 needs no additions. Linux args and multiple paths are preserved without synthesizing command_line. Authentication matching can use User initially; IP/outcome aliases require explicit additional reviewed mapping/semantic cases and are not prerequisites for this bounded plan.
3. **Capability versus absence:** incompatible logsource → inapplicable; unknown profile or explicitly unsupported required alias → configuration_blocked; otherwise insufficient event eligibility → quality_skipped; eligible conditional mappings preserve ordinary missing-field and NOT semantics; supported evaluation → matched/unmatched/evaluation_error. A missing value never automatically becomes missing capture or parser corruption. Missing mapping declarations are an invalid mapping artifact, not an implicit false predicate.
4. **Adapter context:** validated raw record and exact evidence bytes from an explicit local resolver; source namespace/instance, run, immutable first observation, trusted host/generation binding and its provenance, profile/mapping/parser versions. No implicit URI fetch, timezone guessing or host fabrication. Resolver verifies object/record hashes and ranges before normalization.
5. **Adapter result:** normalized event plus unchanged evidence references, or value-free preservation diagnostic linked to original input. Malformed/unsupported data must not be fabricated into a valid process event. Failure of output persistence is visible failure/backlog, not a successful nonmatch.
6. **Assembly manifest:** versioned membership, record hashes/references, key scope, closure, independent completeness findings, assembler/policy versions, event link and immutable late-record links. P12 owns schema content; orchestrator coordinates its registry/readers. Manifests do not redefine event identity.

Current P03 schemas are closed, accept exact versions and fix several version strings/diagnostic enums. Keep existing 1.0.0 documents and identity semantics readable. For additive core fields use an explicit minor contract revision and readers; semantic/required/type/identity changes require a major revision. Prefer the existing namespaced extension container with separately validated schemas for non-core assembly links. Do not silently reinterpret fixture profiles as qualified production profiles. Initial assembler implementation may use version 1.0.0; future changes require the same explicit version discipline.

New per-source mapping semantics require a new detection plan major version (proposed 2.0.0), rather than altering the meaning of fixture plan 1.0.0. Explicitly dispatch supported readers; preserve legacy fixture evaluation tests; reject unknown versions. Keep result fields compatible where possible and populate actual compiler/evaluator/mapping versions rather than P09 hardcoded strings. Any necessary result revision is explicit. Bundle hashes cover candidate revisions, source snapshots, mappings and selection metadata. Changed evaluator/bundle bindings reject incompatible checkpoint restore; no state migration is promised. Same-version restore remains qualified, and deliberate retained-input reprocessing is explicit.

## P10a: compatibility, mapping and provenance

Keep the existing bounded operator subset. Document supported map selections, AND/OR/NOT/parentheses, OR value lists, strings/signed integers, wildcards and a single contains/startswith/endswith modifier. Distinguish boolean condition operators from unsupported boolean literals. Explicitly reject null literals, floats, regex, quantifiers, chained/unknown modifiers, unsupported selections and unused unsupported content. No broad Sigma compatibility percentage or new modifier is promised.

Create a versioned feature matrix linked to executable positive, negative, boundary and rejection cases. Preserve P09 limits unless evidence warrants an owning design-note change. Mapping validation rejects nonexistent/non-leaf ECS targets, duplicate/ambiguous aliases, wrong types/cardinality, unknown transforms, mismatched source versions/hashes and contradictory capabilities. Do not treat profile declarations as evidence that a parser actually implements them; P11/P12 qualify that binding.

Add candidate provenance manifests preserving original YAML bytes/hash, rule UUID/revision, original authorship/license/notices, upstream immutable revision/path when imported, and explicit local modification lineage. In-repository original rules are labelled synthetic Apache-2.0 with repository revision/path; never manufacture an upstream attribution. Initial required corpus is the existing independent semantic corpus expanded to cover the four profile families and blocked/rejected cases. An optional imported-candidate report must include every submitted candidate and its source/mapping/compiler disposition; it cannot silently drop unsupported rules or imply broad corpus compatibility. Any real upstream import first requires pinned content/terms review under THIRD_PARTY.md. Bulk rule sync and activation remain P15.

Candidate analysis may report mixed supported/rejected candidates, but executable bundle publication stays all-or-nothing for its explicitly selected supported input set. A failed compile or incompatible bundle leaves the previous valid artifact intact and exits nonzero. Diagnostics contain categories and source locations, never raw evidence values.

P10a acceptance: matrix and immutable provenance round trips; strict malformed/unsupported input failures; mapping capability/type/target tests; legacy/new plan reader tests and unknown-version rejection; hash/version tampering rejection; atomic failed-output preservation; independently written expectations reviewed before P10 acceptance. Update stale status docs without changing unresolved acceptance facts.

## P10b: conservative selection and complete P10 gate

Build a candidate index using exact source contract/version and logsource product/category/service. Omitted rule logsource dimensions impose no constraint, as in P09. Do not index by field presence or predicate polarity. Rule/source blocks remain explicit. Selection metadata is recomputed/validated on load so a tampered or incomplete index cannot hide a rule.

Reference path exhaustively scans supported rules with the same applicability/capability/quality policy. Optimized path must produce identical matched IDs/revisions, all six outcome counts, diagnostic categories and version attribution. Retain deterministic rule order and P09 budget semantics; skipped applicability checks must not reset or change predicate budgets. Include adversarial small-budget and limit cases so evaluation-error behavior remains equivalent.

Independent cases cover absent/empty fields under positive and NOT predicates; list OR versus event-array any-element behavior where the contract permits arrays; nested boolean combinations; wildcard escaping/Unicode supplementary code points/no normalization; integer boundaries and wrong types; logsource omissions/mismatches; unknown sources; available/conditional/unsupported mappings; eligible/skipped events; duplicate rule IDs; run isolation; compile and event limits. Keep supplementary pySigma comparisons separate from the independent oracle. Owner review of P09 and added expectations is a named pending acceptance item, not inferred from merged code.

Run locked check/java, compiler/evaluator contract cases, legacy/new plans and actual isolated detection qualification. Qualify same-bundle TaskManager/JobManager recovery, unavailable quarantine output, incompatible restore rejection and complete accepted-input accounting. Preserve P07/P08 services/topics and writer gates. Record local ARM64 and AMD64 CI evidence against exact heads. P10 is accepted only when P10a+b evidence passes and semantic review is recorded; passing CI alone is insufficient.

## P11: bounded Windows adapters

Support exact UTF-8 LF-record XML for Security 4688 version 2 and Sysmon process creation Event ID 1 version 5 with correct provider/channel/namespace. Exclude EVTX, collector JSON, arbitrary multiline framing and all other event/version combinations. Use a hardened namespace-aware Java XML parser with DTD/entities/XInclude/external resource resolution disabled. Proposed parser bounds: input within upstream 1 MiB envelope limit, depth 32, 4096 nodes, 256 named fields, 64 KiB per extracted scalar; verify all boundaries and reject visibly without truncation.

The child rehashed and inventoried existing cached artifacts without downloading: Security has 8 supported records; Sysmon has 353 supported records and 6,657 other records. Account for all 7,018 inputs; 361 are supported-version candidates, not automatically eligible or matched. All supported recorded events contain command lines, so capture-disabled behavior requires independently authored synthetic cases.

Security mapping: NewProcessName→executable; NewProcessId hex→new-process PID; XML ProcessId→parent PID; CommandLine preserved; subject account is user actor, target account retained separately. Sysmon maps Image, decimal ProcessId, User, CommandLine and supported parent/GUID/working-directory context. Do not tokenize command lines into guessed args. Retain vendor fields and original bytes.

Host IDs require explicit provenance-backed source/Computer binding; Computer is display context, not proof of stable identity. Missing binding produces identity_missing/skipped. Security source occurrence time uses SystemTime; Sysmon uses its reviewed UTC occurrence field. Preserve precision/source representation; missing/bad/ambiguous time uses existing first-observed fallback. Known disabled capture, legitimate optional absence, malformed extraction and unsupported source are distinct. Malformed XML produces a preservation reference, not a fabricated normalized event.

Acceptance: independently expected field/PID/account/time/quality cases; all recorded input accounting; evidence byte/range/hash identity checks; wrong provider/version/channel; disabled/absent command line; duplicate/hostile XML and bounds; replay identity stability with distinct runs; resolver failures; atomic interrupted output publication. Feed eligible outputs to P10 plus the same Java evaluator offline for true matches/nonmatches and distinct non-evaluation outcomes. The adapter is stateless: this does not establish integrated Flink delivery/recovery. Full recorded eligible coverage remains blocked until host bindings are substantiated. Run locked check/java and adapter qualification on ARM64/AMD64.

## P12a: Linux parsing and assembly

Support raw audit SYSCALL/EXECVE/CWD/PATH/PROCTITLE/EOE records with exact audit timestamp/serial and reviewed decoding. Pin and review architecture/syscall execution tables against authoritative source definitions before implementing; unknown combinations remain unsupported, never guessed from exe or nearby lines. Preserve ordered argument indices/fragments, empty/repeated args and encoded originals; never join them into shell command_line. Preserve every PATH member and its source index; never choose an arbitrary singular file.path.

Authentication scope is the existing OpenSSH 9.x RFC5424 Accepted/Failed password grammar. Exclude public-key/PAM/invalid-user variants, locale variants, RFC3164 and journald formats. Existing authentication examples are synthetic; no reviewed recording is in the catalog. The owner selected inclusion of a small reviewed recording during planning. Include a provenance/terms-reviewed catalog extension with pinned artifact revision/hash, verified RFC5424 framing and OpenSSH version/context, source host/generation provenance, and independently reviewed expected outcomes. Acquisition belongs to P12a and is part of its scope; until this evidence exists recorded authentication acceptance remains blocked. Do not substitute generated synthetic messages for the recording or broaden authentication grammar to fit an unreviewed artifact.

Assembly key: run_id + source namespace/instance + trusted host scope + explicit source generation + exact source audit timestamp + serial. Never group by timestamp proximity, PID, hostname or capture ID alone. Missing required host/generation context means preserved skipped records, without merging unknown hosts. Both existing audit excerpts lack proven host identity/completeness; recorded eligible audit acceptance needs provenance-backed context or an additional reviewed artifact.

Same record ID retries are idempotent; equal bytes at different original positions retain separate membership. Conflicting semantic slots remain visible. EOE/source boundary, timeout, dataset_end and resource_limit are closure reasons independent from quality. Eligibility requires the reviewed required execution evidence and argument/path consistency; unknown/incomplete/conflicted groups remain skipped. Closure alone cannot establish sufficient integrity.

Proposed laptop safety bounds, not measured capacity or previously accepted timing defaults: 256 members or 1 MiB original bytes per group; 1,024 open groups; 32 MiB aggregate pending state; 30-second absolute age from first admission; 16 active runs; closed-key state at most 100,000 entries AND 32 MiB across the job. Use references instead of duplicating raw bytes and enforce normalized output size separately. Inject clocks in tests. Final serialized-state overhead must be accounted for before implementation, not assumed to equal raw bytes.

On group/aggregate pressure, publish bounded incomplete membership/diagnostic output and retain closed-key knowledge. If the output cannot become durable, backpressure/fail without checkpoint advancement. Never silently evict accepted evidence. Retain closed keys through run lifecycle; reaching the closed-key budget stops admission rather than silently expiring keys. Drain via explicit run-end/lifecycle actions only. Late evidence after closure is immutable, linked and skipped; never reopen or mutate emitted membership. Current-policy regrouping remains P14. A different finite late-key retention policy would need an explicit decision and proof against accidental new eligible groups.

P12a acceptance includes interleaved hosts/runs/generations, reordered input, exact retry versus repeated occurrence, argument encoding/fragment/count conflicts, multiple/sparse PATHs, unknown record types, missing/early EOE, timeout/end/overflow closure, missing identity, late evidence and full preservation. OpenSSH tests cover accepted/failed password, IPv4/IPv6, timestamps, malformed header/port and unsupported grammar. Expected membership/quality/fields are independently reasoned. Pure-state tests do not establish checkpoint recovery.

## P12b: state and failure qualification

Add a separate bounded Flink qualification path around P12a, not P13 production wiring. Checkpoint buffers, timers, closed keys, manifests and output progress. Restore binds exact source/mapping/assembler policy and compatible state version. Unknown/incompatible state fails explicitly; replay from retained input is deliberate.

Qualify partial-group restart, timers across restore, duplicates around checkpoint, crash before/after output, late evidence before/after recovery, unavailable event/diagnostic sinks, group/pending/closed-key exhaustion, run-end drain and interleaved runs. Accepted records must remain output members, durable quarantine/diagnostic references or visible retained backlog. Verify unique IDs/hashes/membership, not just counters. No silent eviction or accepted-input loss. Qualify ARM64 and AMD64 in an exclusive detectbridge-p12-* project; serialize heavy runs with writer/detection qualification.

P12 is complete only with P12a+b, reviewed independent expectations, recorded audit and authentication evidence and proven context/limitations. A partial parser merge does not unlock P13.

## Merge order and next action

1. Owner accepts this plan and instructs implementation; record any requested scope changes first.
2. Implement P10a in its dedicated worktree/draft PR; review, run applicable checks, request explicit merge authorization.
3. After authorized merge, verify main checks; implement/rebase P10b and complete the P10 acceptance gate including semantic review. Obtain its separate merge authorization and verify merged main.
4. Freeze the shared interfaces, then implement P11 and P12a concurrently in isolated worktrees. Orchestrator applies shared integration changes serially. Heavy Docker runs are serialized.
5. After either adapter merge, update the remaining branch and rerun affected consumer checks. P12b follows P12a. Every merge is separately authorized.
6. Only accepted P11 and complete P12, plus P08, unblock P13. P14–P16 retain their roadmap dependencies. No release or broad capacity claim is part of this plan.

No production code changed during planning. The accepted planning record is now tracked alongside owning design notes; current implementation status belongs in the ledger.
