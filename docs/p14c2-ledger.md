# P14c2 retention/import/final qualification ledger

Status: implementation and local Linux ARM64 qualification passed after the
published design freeze and separate count correction. Exact-head native CI,
owner acceptance, authorized merges and actual merged qualification remain open. Branch
`feat/p14c2-retention-qualification` starts at qualified P14c1 head 8e4c832 and
will target `feat/p14c1-current-replay`. The owner explicitly authorized this
stack before parent merges; merges/releases remain owner-controlled.

## Prerequisite evidence and local readiness

P14c1 run 44408227593 attempt 1 passed every applicable job/required aggregate
135184964812 on exact head `8e4c832283268897887999efe22152b2f0b41eb5`, completing
2026-11-18 22:34:01 UTC. Five explicit acquisition/recorded opt-ins were skipped.
Actual checkout was GitHub test merge `096ddc136b5769de5f8537608873647b5809df96`;
this is not actual merged-main qualification. Refreshed reviews/comments/inline
threads were empty. PR #52 is marked ready for owner review and remains unmerged.
CI repair #54 is also unmerged; its separate native pass is in the P14c1 ledger.

Native current job 135170171558 passed full synthetic source, schedule, isolation,
three fresh-JVM resumes, eleven interruption windows and integrity/storage/helper
cases on Linux AMD64. Its qualification-source aggregate matches the exact local
source set `2db4412b3b73940882252cdba342c9988b014ff009f7e095b818d7e936620f2c`.
Executor ea9d4740, reader e5eaea35 and producer 51a984de are unchanged (full hashes
in [P14c1](p14c1-ledger.md)); selected AMD64 Docker image is
`sha256:6b26436e8a89f49acaf0133e35f1e3715544e7c984d0f68cd8038137ab2e6be9`.
Metadata/current full log/threads are `.cache/p14c1-native-44408227593/`.
This supplies the owner's requested acceptance-check gate for starting P14c2;
owner semantic acceptance, merge and merged qualification remain separate.

Before designing recorded cases, the original accepted preflight functions
revalidated controlled originals, usage terms and source/capture bindings from
original-checkout paths `.cache/p11-windows-capture/attempt3/originals`,
`.cache/p12-audit-reviewed-v1` and `.cache/p12-auth-reviewed-v1`. All were available;
counts are 5 Windows/30 audit/11 auth. Private report
`.cache/p14c2-readiness/preflight.json` freezes catalog hashes and absence of Bob
among reviewed auth users. The accepted eligible audit executable is not the
synthetic whoami path; the recorded current expectation is therefore nonmatch,
not a copied synthetic match. No original payload was printed, uploaded or recaptured.
All four original public P05 payload/provenance caches and five P05 run manifests
are available in the original checkout; this presence check does not claim their
new import qualification. The importer must reverify them before use.

## Freeze preparation

[Design](p14c2-design.md), [independent cases](p14c2-expectations.md), six closed
maintenance schemas and literal byte/identity/legacy-source fixtures precede
production implementation. Initial schema-authoring script incorrectly assumed
the legacy configuration schema enumerated topic names; it actually delegates
that semantic check to Main.TOPICS. The unpublished fixture generator now takes
the nine existing names explicitly. This was an authoring/setup correction, not
a behavioral red or runtime result. The failed authoring attempt remains in session output. Direct legacy-schema
validation also rejected the draft timestamp-type spelling CREATE_TIME; use the
existing literal CreateTime. The failed validation log remains
`.cache/p14c2-freeze-validation-authoring-failure.log`. Neither authoring failure
is a required retention fault assertion.

Freeze validation, implementation red/green and actual fault/recorded results
will be recorded below with exact revisions/artifacts/platforms and unavailable
coverage. No P14 completion, owner merge or runtime pass follows from this freeze.

## Freeze validation passed

Six closed/no-reference schemas and literal identity/legacy-source pins passed
independent validation. The unchanged E5 Java reader actually verified the literal
three-segment/six-row/two-object fixture on Docker Linux ARM64, before any managed
implementation: `.cache/p14c2-freeze-validation-final.log`. Expected retirement
floor/head are 4/6 and original second-segment anchor is
`2c91f7e64a0774c6013e1103e5eb407983e5df03db7696f92072ea8c5590a7d8`.
Fixture file SHA-256 is
`45ce9bc93b5614fc301417373d8325ac978cd12f6cd6c84141d7572b59a5961d`.

Direct schema type/boundary checks passed in `.cache/p14c2-freeze-boundaries.log`,
including exact 9007199254740993/MAX_I64 cutoffs and foreign/fraction/bool/overflow
rejection. An initial generic sample generator omitted the retirement ID's sha256
prefix; that authoring failure is retained separately and is not a behavioral red.
Cross-document retirement/import semantics are still implementation work.

Locked `tools/dev.py check` passed 229 existing Python regressions, all contracts/
catalog/dependency/hygiene/secrets/workflow checks, lint/format/types in
`.cache/p14c2-freeze-final-check.log`. The first document check rejected a leading
PR number as a Markdown heading; the corrected result is separate. These checks
and the old-reader fixture run do not qualify the new managed runtime. Preserve
this design/expectation commit before writing its production code.

## Independent recorded-count correction before qualification

The published original freeze `a19693bccd346d24c5c3d899dafea5a1a139b435`
(packet SHA-256 45ce9bc93b5614fc301417373d8325ac978cd12f6cd6c84141d7572b59a5961d)
incorrectly copied thirteen original preservations into a schedule that also admits
one distinct controlled late occurrence. Preserve that original freeze as history.
Before any new recorded runtime execution, revalidated catalog counts independently
show audit 27 group members plus three extraction failures; auth two normalized
plus nine unsupported; Windows four eligible plus one unsupported. The 46 originals
therefore produce thirteen preservations. The controlled late member is distinct
and adds one `late_evidence` preservation; exact redelivery adds only a receipt.
Historical/current each require fourteen preservations, and current total is
16 + 10 + 14 + 9 = 49. Source fields, quality, membership and all other expectations
remain unchanged.

This correction comes from the accepted catalogs and existing
`tools/search_writer_recorded.py` late-preservation oracle, not from the new archive
implementation. The old original-only packet's per-run thirteen remains correct
and unchanged. [P13d](p13d-ledger.md) already records 28 preservations over two runs,
223 logical/233 physical outputs, on accepted producer 51a984de in project
`detectbridge-p13-recorded-8348892e80`. New read-only preflight independently
reverified original hashes/terms/bindings in
`.cache/p14c2-recorded-preflight.log`; its report explicitly says runtime unqualified.

The corrected packet SHA-256 is
`46eede25ee08f2f2cd576de96417004bc0c4e53a3f582031aea7040f6216e3dd`.
A separate pre-qualification correction commit preserves this evidence boundary;
it is an explained additional commit beyond the normal three-commit target.
No owner semantics acceptance, merge, milestone completion or runtime pass is
implied by correcting the expectation arithmetic.

## Correction boundary and historical managed candidate

The separate arithmetic correction is local commit
`786ec141d3dff4ea058bdb429fbca45e7216b41b`, before the actual new recorded
attempts below. Original freeze a19693b and its packet remain historical.
Public-safe source arithmetic proof is `.cache/p14c2-recorded-expectation-proof.json`,
SHA-256 `cc7c4258f6b1a062b30c5e3c63d61c29c4f34723e55ac2d0ccedecc04576d612`.
No new archive/evaluator output generated those expectations.

The following managed artifact is now historical and cannot be adopted as the
final P14c2 candidate:

- Managed JAR: `62ab6562e672d615fcbc132d97170aa05b96bf843749a51ae63681d22cf2222d`.
- Original qualification probe:
  `080248ff3143ab64f0c0a9ccbd8474fb6370e51c96abf999694672b0fcc5d1d6`.
- Expanded synthetic qualification probe:
  `bc8fa4a96c7e6ebd2fd5c4482dc7e3fc58754de47b382435920b0e82539ca68e`.
- Docker platform `linux/arm64`; selected image ID and pinned image index are
  `sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`.
- Unchanged producer 51a984de, historical executor 32bad6f5, current executor
  ea9d4740 and legacy reader e5eaea35 retain the full identities in the P14c1 ledger.

On M62ab, project `detectbridge-p14-managed-ff4c6d3553e1` passed 23 actual
synthetic cases. Report SHA-256 is
`e5ed23e76bc283d644eac830e8579e4ddf1c583282ab748cb6e4649e1f827ec8`.
Expanded project `detectbridge-p14-managed-64609d1ed200` passed 39 cases with
probe bc8fa4a9; report
`.cache/archive-maintenance-reports/detectbridge-p14-managed-64609d1ed200.json`
has SHA-256 `f876839f7bf8e2bcb163f999548df46da3ba5aab876c6a33cb9ca1dd69e6f7d1`.
These exercised actual clone/read leases, explicit holds/pins, anchors and retired
retrieval, P05 import/restore/retirement, tmpfs payload ENOSPC and injected sync EIO,
missing/corrupt backend data and heads, managed historical/current execution,
Kafka durability/crashes, broker outage and finite-headroom refusal. They are
bounded passing observations, not proof that every required case was covered.

Independent subsequent review found M11's derived-row recognition could treat a
document with a `processing_id` as known despite an incompatible version or nested
shape. That can incorrectly permit partial retirement of an unknown graph. M62ab
therefore fails the final acceptance requirement despite its earlier passing case
list. The replacement uses pinned closed output profiles and conservative handling
of open native documents. Newly explicit metadata midwrite hooks also address the
M15 qualification gap; before/after-publication passes alone do not establish each
write window. Affected runtime results remain pending. No earlier report is relabeled or
transferred to a replacement JAR.

A separate retained-graph review found that `ManagedImport.retirementPlan` did
not scan retained wires. Three pre-fix cases incorrectly allowed retirement:
a future-version row referencing the import, a supported-version row with an
unknown nested run reference, and a recognized tagged row sharing the original
run. Original red evidence is `.cache/p14c2-import-retained-graph-red.log`.
Unknown retained graphs now block import retirement with
`managed_unknown_graph_blocker`; recognized import/run/closure token intersections
block with `managed_retained_identity_blocker`, under a shared finite row/token
budget. Fifteen focused tests passed in
`.cache/p14c2-import-retained-graph-focused-green.log`. This correction is included
in c799 below; focused tests do not replace actual affected runtime qualification.

Intermediate candidate
`c799655e30d57656ba1c20a6108a829d4dd301740b79cbafe2ac65e88addadd7`, probe
`08445057e76929800d628387c78abc0c0610ee9ed4ff0ee84d92027653f2a875`,
built with 52 Java tests and legacy/resource verification passed. This is component
and artifact evidence only, on macOS 26.5.1 ARM64. The report below binds this intermediate artifact; the final replacement has
separate `.cache/p14c2-final-candidate-provenance.json`. Controller source SHA is
`445a92d607ee1be049ab266c51e293b13d13945157c589d8db779d8f2c0574a9`
and verifier source SHA is
`10212f8675e88a9650634ef24e90aeeabee7ef7a2acc8f3bc7da6f28fe1531ba`.

Its actual synthetic runtime subsequently passed 44 cases in project
`detectbridge-p14-managed-945fd545e62d`, Linux ARM64 on Darwin ARM64, with
the selected image `sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`.
The report `.cache/archive-maintenance-reports/detectbridge-p14-managed-945fd545e62d.json`
has SHA-256 `e071026c4b40c75ec14d6b9e8cba821428b95da73e83ad4d81337a65feb7750f`;
log `.cache/p14c2-managed-synthetic-runtime-attempt11.log` has SHA-256
`159d326a999dc9e9c37e23410c261cc08eee127e88008c9705b6ca3c0c4066ab`.
This passing runtime remains c799-specific and does not resolve the separate
fingerprint defect below.

Subsequent review reproduced another genuine safety defect against that exact
c799 JAR: derived-topic raw/context references could seed prior source
fingerprints and affect future source identity decisions. The original red is
`.cache/p14c2-fingerprint-topic-c799-red.log` with retained test XML. Fingerprint
collection now requires `topic == Main.INPUT`, preserving input raw/context for
source, invalid-source, semantic-conflict and opaque input rows independently of
known-schema recognition. Thirty-seven focused tests passed (14 planner, eight
graph, 15 import) in `.cache/p14c2-fingerprint-topic-focused-green.log`. A new
managed artifact and its applicable runtime, approved-original, recorded and
native qualification are required. Any c799 runtime observations remain bounded
to c799; neither its results nor the M62ab reports transfer to that next artifact.

## Approved original P05 import and restore on M62ab

Actual local managed import/restore revalidated an existing completed P05 run
and its approved payload/provenance cache. It imported 7,046 records / 7,051
envelopes in eight committed segments, preserving all 33 descriptors, including
the original checkpoint and original capture metadata in the manifest. No network
acquisition or original replay execution occurred. Original run/cache byte snapshots
were unchanged. Restored original P05 inspection and completed resume both passed;
the restored advisory checkpoint stayed byte-identical. No helper remained.

The exact private/local report is
`.cache/p14c2-approved-p05-local/qualification-report.json`, SHA-256
`f4bdbb10d14dd30f0b3cf21d86052f7c88a6ac9f1abaa9a3d774def197d11d54`.
Import ID is `70914fe38ac653a6cc963ce0224c8044362b1de1167c41d377c20541b7f970fd`;
metadata hash `4e8a7b2c32352e89bb929f9e18e23ecf3ec55a32dd742e94aea8fd6c56c7aaca`.
Original and semantic P05 manifest hashes are both
`62f0758e07c6c8cb4fcd1e0a245d63644929fcf56f42acdb7bd8455244c4686a`
for this canonical LF-terminated file; the two hash definitions remain distinct.
The exact managed/probe/image identities are M62ab/080248ff/Linux ARM64 above.
This evidence does not manufacture P13 contexts or Kafka admissions for P05,
and is not a new-candidate qualification or a complete P14 acceptance.

## Recorded actual failures on M62ab

All controlled originals were reverified before Docker: five Windows, thirty audit
and eleven auth records; catalog/terms/capture/host/boot bindings match the accepted
packets. Original private data, contexts and exception bodies stay ignored and
unpublished. Both attempts below restored the default integration build and removed
their owned stack/volumes. Their failed statuses remain unchanged.

| Attempt | Exact verifier / report | Observed failure and bounded result |
| --- | --- | --- |
| `detectbridge-p13-archive-recorded-cdf028be02` | Verifier `e336067b7e02c638ad0112e8c51aa961701f4b9c28d5a846d344a032ea5d348e`; report SHA `48331c9ac93b8a971c186f595fc6b330cfa47842dab94d80fb439bbd2b7f8005` | Post-source topic inventory raised KeyError: P13 has eight topics, archive requires ninth writer-failures. Source oracle had passed; no managed archive qualification follows. Original Python traceback was unavailable in that harness version. |
| `detectbridge-p13-archive-recorded-e9d80ec920` | Verifier `3b9a53445bfab7ae2fec0e7c1e3fb66feeea0e814d93c6d5cbf6d642665ddc6b`; report SHA `a277e841e5e4f54122e877871223be6d070263f8953372fc1b77321a7be529b1` | Actual topic setup, source oracle, 49 admissions, managed drain/byte verification, seal and two historical runs including same-operation interrupted resume passed. Current output was executed, then its oracle rejected manifest comparison. Overall qualification failed. |

Reports are under `.cache/archive-recorded-reports/<project>/report.json`; original
logs are `.cache/p14c2-recorded-actual.log` and
`.cache/p14c2-recorded-actual-rerun.log`. Both ran at source revision 786ec14 plus
implementation working files; actual artifact hashes, not Git-tree similarity,
identify their executable scope.

The first harness correction runs the frozen Admin probe before source admission,
creates only the missing ninth topic and verifies all existing eight topic
identities/offsets unchanged. It never infers an absent topic's end offset as zero
or resets existing topics. The second attempt observed exactly one topic created.
New failures retain original private Python traceback and source-job exception
observations before cleanup; unavailable observations are labeled explicitly.

The second failure was an expectation-construction alias, established from source
before changing the checker. `linux_assembly_audit_recording.prepared()` assigns
one shared context to all audit admissions. Deep-copying the whole collection
preserves that alias. Setting scheduled per-input receipts then overwrote earlier
expected clocks with a later receipt. Actual inputs must be copied individually
before assigning their new run/receipt, as already required by the explicit
schedule. No frozen count, original field, membership, schedule or runtime output
was changed to obtain a comparison.

The private actual/wrong-expected comparison is
`manifest-expectation-diff-private.json`, SHA-256
`b8d58ad24bca3bf6be6ee8d4ed6e14c42b030816e2a28c65ac14f07c4290fc86`.
Only `/members/0/context_sha256` through `/members/5/context_sha256` and
`/manifest_id` differed. Original failed verifier bytes are retained as
`failed-verifier-source.py` with exact hash 3b9a5344 above, together with
`failure-private-traceback.txt`. No private comparison values are copied here.

## Separately attributed retained-output checks

After per-admission copying, the corrected current checker passed against detached
copies of the second attempt's actual results: fourteen preservations and 49 total
outputs, with unchanged frozen source/count/quality/late-link expectations. The
shared-context regression reproduces the old overwrite and requires every new
expected receipt to equal its independently specified schedule clock.

This separate diagnostic run rejected nine same-population mutations: source
field, host, context, membership, counts, match and attribution all raised
`assembly_independent_expectation_failed`; original-range and byte corruption
raised `recorded_original_range_integrity`. Thirty archived original audit ranges
were positively verified against reviewed original bytes and catalog hashes.
Originals, archive, historical catalog and current workspace byte snapshots stayed
unchanged. No runtime was rerun or old failed report overwritten by these checks.

The separate report `e9d80ec920/detached-checker-report.json` under the recorded
reports root has SHA-256
`8ba84880e2a1e20d218178aa59b3d97939abf65364a232921190cc4852bf8f0e`.
It explicitly records `positive_run_status=failed` and
`full_pipeline_requalification=false`. Checker-source SHA is
`464cf14055fd4e47582caa3e323ebc2949e7185476c81eeb6d3970823fa30e6e`;
old oracle-function SHA is
`e4f5a41e15490daaf654d976425a37c11a1a06bcb0ca4d6f7b9aae46010066c8`;
fixed function SHA is
`8ebc0fc7253ca89313ae79d83e510b5d113d695f600d95e0ad81413f979458fd`.
These are checker-specific observations, not transferred pipeline qualification.

The final portable qualifier uses checkout-relative defaults and explicit source
flags for worktrees. Its current source SHA is
`e7dd507ea78ffdcf42e5489174c10d8476ac260ec0793a92e4424aa4462fcf11`.
It incorporates these negative checks into the next full run. No fresh corrected
full recorded pass exists at this checkpoint. Native private-recording AMD64
coverage remains unavailable, and no original has been recaptured or uploaded.

## Earlier pending-gate checkpoint

The [milestone acceptance map](p14-acceptance.md) is a draft with explicit pending
rows. Required remaining evidence is the replacement artifact's complete applicable
synthetic/fault/import/replay qualification, fresh full controlled-original run,
final source checks and exact native implementation CI. All exact final candidate,
probe, plan/image/source hashes and unavailable coverage must be filled from actual
results. Owner semantic/completeness acceptance, explicit merge/release authority
and actual merged-commit qualification remain separate. Do not close issue #14 or
mark P14 complete from the old M62ab reports or the corrected checker alone.

## Final local artifact build

After the INPUT-only fingerprint correction, the managed build produced
`9598289011727e96e1e633642f6926893161c5889e90ffe1cdd85c2642ff46df`
and probe
`354756bf1d9e835eb366d17b645e2358295ee8c055555734aa410f18babf32bb`.
All 53 Java tests passed without skips, and exact source/resource checks verified
the fifteen closed graph schemas, bound controllers and unchanged E5/32/E9/51
artifacts. Log `.cache/p14c2-final-candidate-build-attempt2.log`; source and Java
hashes are `.cache/p14c2-final-candidate-provenance.json`. These are local
`786ec141d3dff4ea058bdb429fbca45e7216b41b` plus uncommitted implementation
results on macOS 26.5.1 ARM64, not a future implementation-commit or native pass.
Full fault, approved-original import and recorded qualification remain pending
for this replacement.

## Final managed synthetic runtime passed

Attempt 12, project `detectbridge-p14-managed-6bf0cf37da3e`, passed all 44 actual
synthetic cases on managed artifact 95982890/probe 354756bf above, Linux ARM64
Docker on Darwin ARM64. The pinned image and original E5/32/E9/51 artifacts were
unchanged. This is `786ec14` plus the attributed uncommitted implementation, not
a native CI or future commit result. Qualifier source SHA-256 is
`10212f8675e88a9650634ef24e90aeeabee7ef7a2acc8f3bc7da6f28fe1531ba`;
fault helper SHA is
`d96ddec783c6bc10185601b992e014d47723e18b81b868494ce152d8a6ff3694`.

The complete aggregate repeated clone/publication/retry, shared-reader exclusion,
holds/pins, exact prefix retirement and anchors, completed synthetic P05 import/
restore and import-retirement recovery, ten corruption negatives, four actual
mid-plan/record write or sync process-86 windows, future-graph partial denial,
original pinned historical/current oracles and interruption recovery, four Kafka
durability crash windows, retired-source retry/conflict, actual broker outage,
initialization windows, lower finite creator-cap backlog and maintenance reserve,
real payload ENOSPC on a contained tmpfs, and injected metadata-sync EIO. All
helpers/projects were cleaned; `docker ps -a` was empty afterward. Injected errors
and process kills do not qualify physical power loss or disk loss.

Report `.cache/archive-maintenance-reports/detectbridge-p14-managed-6bf0cf37da3e.json`
SHA-256 `53675733540e9f316fac539feced9293adeed5bc826675e6114fc7dcc49d19a9`;
log `.cache/p14c2-managed-synthetic-runtime-attempt12.log` SHA-256
`33541fb6a230fc942dd7597c3f64d8ce4a93eceeece6968f074267e1aa075aa3`.
Approved-original P05 and controlled-recording results remain separate below;
no synthetic pass supplies their acceptance or native AMD64 coverage.

## Final approved-original P05 import/restore passed

A fresh final-95982890 run used new physical destinations under
`.cache/p14c2-approved-p05-final`, after read-only verification of all five original
completed runs and the approved original source cache. It imported the same
reviewed run `7dac0dc1-1711-4bfe-9529-c8c2489beccb`: 7,046 records, 7,051
envelopes, eight segments and 33 exact closure files. Actual public managed
clone/import/restore calls succeeded, then the unchanged P05 implementation
inspected and completed-resumed only the restored run. All descriptor bytes,
lengths, original UUID and checkpoint remained unchanged; original five-run tree
and source cache snapshots stayed exact. No original was executed, repaired,
recaptured or reacquired.

The existing approved catalog/terms, framing and timestamp validators passed.
Platform was Linux ARM64 on Darwin ARM64, pinned image 55ccb2ad. Report
`.cache/p14c2-approved-p05-final/qualification-report.json` SHA-256
`6e0d4fc1baa32a7286fa8248c51696e7d5ec07bc950e0e6c43069be3cb4c70f7`;
private driver/log/preflight snapshots remain in that ignored directory. This is
separate from the explicitly injected synthetic P05 source used by native CI.
It does not supply missing P13 host/processing context or native AMD64 original
qualification.

## Fresh full controlled-recording qualification passed

Project `detectbridge-p13-archive-recorded-68401cb415` completed with
`status=qualified`, `runtime_qualified=true`, exit zero on final managed
95982890/probe 354756bf. This fresh full run used the portable frozen qualifier
`e7dd507ea78ffdcf42e5489174c10d8476ac260ec0793a92e4424aa4462fcf11`
and corrected expectation packet 46eede25. Source was `786ec14` plus uncommitted
implementation; the start working diff SHA-256 was
`00d355a5fcab064f2c722c1547e0379d60a48bf58c4d2d4c896ce5aafd19140d`.
No loaded qualifier or core source changed during execution. Host was macOS
26.5.1 ARM64; actual source and replay containers were Linux ARM64.

The exact per-run original plan was
`cb8b6f66f515989b1492d38341e57ba6c21196505ee7d87f581e17fadd484492`;
current Image/Bob plan was
`f1cc8ffd5c996af70ceb7541dccd1d05ddfb4dc20e5c8b6bd80cbc1325da0e8a`.
Source bundle SHA-256 was
`3db5c8323bc157bb058c75523733a5b96144633f0be6d93d21bc4e0e4fdc5e22`,
actual source image ID
`sha256:d979bc44dba0e7f09455f258abe3c8d5953ac448ee886fdabbfdaac61eabfdac`.
Producer remained 51a984de and replay image remained 55ccb2ad; the complete exact
managed/legacy bundle is in the report. Rebuilding on another revision may change
plans/bundles/images; no identity or CI result transfers to that rebuild.

All 49 admissions were archived: 46 originals, one exact redelivery, one distinct
controlled late cursor and one run-end control. The 160 exact physical archive
wires were 49 inputs, 49 receipts and 62 semantic outputs, with zero semantic
physical duplicates. All nine archive topic lags reached zero. Original source
fields, contexts, membership, quality, late links, counts and pinned attribution
passed the independent accepted-source oracle.

Each of two isolated historical runs produced 62 outputs: 16 tagged events, three
detections, ten manifests, fourteen preservations and nineteen processing
diagnostics. Actual interruption left one committed unit; same-operation resume,
completed resumes, original-membership reproduction and isolation all passed.
Current-policy replay produced 49 outputs: 16 tagged, zero detections, ten
manifests, fourteen preservations and nine processing diagnostics, with the
independently frozen Image/Bob counts and explicit late/timeout schedule.

All nine same-count semantic/original-range/byte mutations were rejected, and
thirty original audit ranges verified positively. Post-run snapshots confirmed
all three original roots and archived bytes unchanged; negative checks also left
protected catalog/workspace/originals unchanged. The default integration build
was restored and owned cleanup completed, independently checked for no remaining
containers. No private data was recaptured, committed or uploaded.

Report `.cache/archive-recorded-reports/detectbridge-p13-archive-recorded-68401cb415/report.json`
SHA-256 `af7fc491fca5235619a569b68a2b61b22ad0fede3cb334d2dd102de2ff294a2a`;
private log `.cache/p14c2-recorded-final-actual.log` SHA-256
`90a6bfb2fe37e376d01cc2a460a2c0536ea217c7ef823fee21d44dc10db1686b`.
Separate safe evidence SHA-256 is
`54b8dd28f32405a839b9f3b479a73e27ea952d01b6e7647a69e2987826e872d7`;
negative report SHA-256 is
`c0388df67aeeea4841c964dee037fe82c6fec1044816575022e1e9a8c857f9b1`.
This fresh pass supersedes the pending local-runtime checkpoints above; both old
recorded attempts remain failed. Native private AMD64 remains unavailable. Owner
acceptance and exact native/merged qualification are still separate gates.

## Earlier failed attempts and diagnostic limits retained

The original attempt logs remain `.cache/p14c2-managed-synthetic-runtime-attemptN.log`
and matching per-project reports under `.cache/archive-maintenance-reports/`.
None of these setup/harness failures supplies a required fault assertion.

| Attempt / artifact | Actual failed operation and disposition |
| --- | --- |
| 1 / e6d62546, project 7423448041af | Frozen-fixture clone request omitted required registration fields; corrected harness, no runtime acceptance claimed |
| 2 / e6d62546, project 17cdd98a5f3d | Genuine false stale-plan rejection: persisted integers and in-memory integers had different JsonNode types although canonical hashes matched. Separate red/green plan-roundtrip regression led to canonical hash comparison |
| 3 / 3cb5c543 | Setup lacked the exact tag+digest alias although the canonical pinned image existed. Restored only the verified same-image alias; no image substitution |
| 4 / 3cb5c543, project af5ae628893a | Exact P05 restore passed, then harness incorrectly compared the coordination-only `.run.lock` as original evidence. Corrected that comparison |
| 5 / 3cb5c543, project 3ad3cc52197a | Historical replay passed, then harness variable shadowing targeted a pin directory and raised IsADirectoryError. Corrected the harness path; evidence was not overwritten |
| 6 / 3cb5c543, project 76b2e85221a3 | Nineteen bounded cases passed before later expansion; this is separate earlier-artifact evidence |
| 8–9 / M62ab | Actual ENOSPC/EIO and import-retirement checks passed, then missing-head negative asserted an overly narrow filesystem marker. Original failures retained; exact allowed category/class pairs now distinguish the actual inspect/recover guards |
| Backend target 1 / M62ab | Gap rejection came from `archive_contents`, before the narrower chain guard. Target mutation and unchanged neighbors were verified; corrected exact marker-pair expectation |
| Backend target 2 / M62ab | Test setup attempted cutoff 100 against the literal third segment timestamp 200, before the intended fault. Corrected independent boundary pairs (4,100)/(6,200); no fault assertion from the failed setup |

Backend target 3 subsequently passed all ten cases; targeted Kafka/outage/pressure
qualification passed twelve. Full attempts 10, 11 and 12 are separately attributed
above, including later safety findings that prevent adopting their earlier JARs.
The plan-roundtrip red/green logs are `.cache/p14c2-plan-roundtrip-{red,green}.log`.
Focused graph regressions also ran against immutable M62ab and rejected the old
unsafe plans, before the strict known-schema fix.

An older fifth wrapped build failed with StackError, but that wrapper did not retain
the underlying build detail. Do not assign a cause; `.cache/p14c2-fifth-build.log`
preserves the diagnostic limit. The new builder retains exact stdout/stderr bytes
before reporting failures. Earlier local compile errors, including an overly
broad Path-type edit, were corrected and do not count as runtime fault assertions.
The first final source check exposed Path/string variable reuse in resource
checks; type correction passed. A subsequent source check encountered relative
links before the acceptance-map draft existed; after saving the map, all 289
Python tests and locked source gates passed. Later doc checks caught extra blank
lines; corrected Markdown/content checks passed. All failures remain separate
from the final successful commands.

## Implementation delivery boundary and remaining gates

Locked `uv run --locked python tools/dev.py maintenance` passed its actual build,
artifact checks and focused components after recorded qualification and default
build restoration; log `.cache/p14c2-final-maintenance-command.log`. The rebuilt
managed/probe and all legacy artifact identities remained exactly those qualified
above. Locked `uv run --locked python tools/dev.py check` passed all 289 Python
regressions, contracts/catalog/dependencies, hygiene/secrets/workflows, lint/format
and types; log `.cache/p14c2-implementation-final-check.log`. Final documentation
content/Markdown and secrets checks are retained separately in
`.cache/p14c2-delivery-doc-check.log`.

The implementation commit consolidates source, meaningful regressions, operator
commands, actual qualification and the milestone map after the two preserved
freeze boundaries. The separate correction freeze explains the otherwise
additional history boundary; published IDs/timestamps are unchanged. Local runtime
evidence remains attributed to 786ec14 plus the exact implementation artifacts
and working-source hashes, never falsely to the future commit. Native CI must
qualify the actual published head independently.

Current open gates: exact-head native implementation CI and review, owner
semantic/completeness acceptance, explicit authorized regular merges of the
outstanding stack, and actual qualification of each merged commit. Private
recorded AMD64 remains unavailable. No P14 completion, issue closure, merge or
release is authorized or claimed. The original untracked handoff and all private
evidence/generated artifacts remain uncommitted.
