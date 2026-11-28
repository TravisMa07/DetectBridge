# P15a candidate lifecycle qualification

Current P15a disposition: owner-authorized regular merge #57 f44403e and
actual merged-main push run 44472864062 attempt 1 both complete. All nineteen
applicable jobs and required-checks passed; five explicit opt-ins were skipped.
The historical pending checkpoints below remain retained. P15b implementation
is authorized after its own pre-code freeze; complete P15 acceptance remains open.

Current P15a merge checkpoint: the owner explicitly authorized regular merge #57
and continuation with P15b. Merge was performed as
`f44403e2975db46554c9c5033f87886d880c4087`, with original three commits intact.
Actual merged-main push run 44472864062 is in progress; its eventual outcome must
be independently verified before P15b production code. PR run 44466077762 is not
substituted for that gate. The original uncommitted native-completion addition
was preserved in Git stash and copied before this reconciliation; neither was
removed. No P15b merge or release authorization is inferred.

Status: implemented, locally qualified and native PR-qualified for private candidate
preparation. Owner review, authorized merge and actual merged-commit checks remain
separate. The native completion addition remains uncommitted for the consolidated
owner-disposition boundary; published head cc31eab is unchanged. P15 is not complete. P15b dependent implementation waits
for this slice's qualified owner merge; P16 implementation waits for P14/P15.

## Ownership, freeze and prerequisites

Base: qualified merged main `f44c9f91e10414cd2b03481951a2e2a1c7b2a4a0`.
The owner explicitly accepted bounded P14 completion in this continuation session;
[merged-main audit](p14-merged-main-audit.md) records exact CI, retained limits and
issue/project reconciliation. Issue #14 is closed/Done; M5 remains open.

Branch: `feat/p15-rule-lifecycle`. Primary owns shared contracts/validation/CI,
status and integration. Interface agent owns private store implementation;
independent expectation agent owns literal fixtures and black-box tests; a third
agent independently audits prerequisites and reviews actual source. Primary owns
the serialized local Gradle qualification slot. No Docker/Flink/Kafka runtime
suite was run for this candidate-only slice.

[Design and expectation freeze](p15-design.md) is
`2ff0e4f978363466f63714c550a0d296a4b32a00`, before production implementation.
Independently frozen Alice/Bob outcomes, original synthetic YAML and source/license
provenance are in [the fixture packet](../contracts/lifecycle/v1/fixtures/README.md).
Separate executable-closure correction
`6a718cf30ca006996c295c72b3803c8e020aa9b2` retains the original failed assumption
and source-supported dependency correction before successful qualification.
The bounded PR preserves three cohesive commits: freeze, required correction,
then consolidated implementation/tests/docs/evidence. Published history is intact.

## Implemented boundary

The [operator guide](rule-lifecycle.md) covers fresh private store initialization,
immutable import, compiler validation, actual Java sample testing, explicit staging,
compared forward proposal preparation, read-only inspection and nondeleting
retirement. Full closure, exact-file and semantic plan identities are distinct.
Private Unix UID/mode authorization is explicit; no endpoint or candidate-supplied
executable is introduced. Hash-linked journal/head recovery and exact request
retries retain original results. Latest failed sample reports clear readiness
without erasing earlier history. Prepared references prevent retirement.

P15a does not publish control messages or accept worker acknowledgments. Prepared
`activate`, `membership` and `rollback` actions are inspectable local proposals;
P15b must establish authoritative publication/history and actual workers before
adoption. Existing P13 checkpoints/output contracts and P14 artifacts/pins remain
unchanged. No live activation, convergence, runtime rollback, archive extension,
rescaling, HA, new source coverage or throughput claim follows.

## Retained failures and corrections

1. Initial standalone Java invocation failed before evaluation with
   `NoClassDefFoundError: org/slf4j/LoggerFactory`. The original integration JAR
   excludes SLF4J because Flink supplies it. The original diagnostic is retained
   in the agent/tool transcript; no original raw file was captured. Do not label
   a later rerun log as that original. The initial scaffold stage failure also
   did not establish valid-positive behavior because its prior sample report
   failed. That early red characterization was explicitly withdrawn.
2. The separate freeze correction binds already reviewed/locked SLF4J API 2.0.20
   by its existing verification checksum. No dependency, lockfile, original JAR,
   expected matching outcome or resource limit was changed to pass a test.
3. An initial test temporary path used macOS `/var` through a symlink. The strict
   path boundary correctly rejected it; tests now use resolved owned `.cache`
   directories. This was setup evidence, not the intended behavioral red.
4. Independent production review found recovery forcing the advanced head before
   forcing a surviving journal rename. The focused regression injected failure
   at the actual journal-directory sync after rename, confirmed stale head 0,
   and failed on recovery ordering. Fix forces the journal directory first.
   Original red SHA-256 is
   `cf5858c2cbfe1f09e332d516947ff0a34f2bddcb1d3983bf5b582400f1e415ef`;
   focused green SHA-256 is
   `f762afcd3cb61736eb87ff8a7a90a16e12b4fc99cf6e9f6bfdcb319e25ed460b`.
   Logs remain `.cache/p15-main-audit/recovery-order-{red,green}.log`.
5. Review also found compiler temporary files outside the reserved store budget.
   Validation and testing now reserve 24 MiB and pass an owned private temporary
   root; regression verifies the actual compiler path. Temp files use mode 0600.
6. First full check ran 312 tests with six gate-fixture failures: three expected
   fourteen cache consumers rather than the new fifteen, and three aggregate
   fixtures omitted the real new lifecycle job/output. Fixtures were updated to
   the actual additional consumer; exact-cache and fail-closed assertions remain.
   Original failed check is `.cache/p15-main-audit/check-first.log`, SHA-256
   `982c747a2ec106da120a187a1c20f26ec07f34078c6fc325b1dd081ebb92f5e1`.

Earlier successful 23- and 29-case local qualifier attempts are preserved under
`.cache/p15-main-audit/qualification-first/` and `qualification-29/`; neither
substitutes for final 30-case evidence. Final review identified that the earlier
same-bundle rollback case proved only forward proposal ordering. A separately
derived Bob-rule modification now tests distinct A→B→A proposals while preserving
original YAML provenance and A bytes/history. It remains proposal-only evidence.

## Final local artifact and source attribution

Command: `uv run --locked python tools/lifecycle_verify.py`. Host:
`macOS-26.5.1-arm64-arm-64bit`; actual Java runs locally on ARM64, not Linux or a
Flink container. Source was `6a718cf` plus the exact uncommitted implementation
and tests listed below. The report explicitly records dirty tracked source and
all implementation/test/fixture hashes. This is not qualification of a future
commit by SHA. Native CI must qualify its actual revision independently.

The command passed an offline locked original integration build/test invocation,
verified the exact retained JAR, and passed **30 required tests with zero skips**:
27 lifecycle and three gate tests. The final Gradle invocation reported eighteen
up-to-date tasks; it is successful build verification, not a claim that eighteen
fresh Java test tasks executed. Actual sample Java processes execute in the
lifecycle tests. The qualifier fails if the required JAR is unavailable or any
test is skipped; ordinary prebuild hygiene reports unavailable artifact cases
as explicit skips instead of fabricating runtime passes.

`uv run --locked python tools/dev.py check` passed all **319 Python tests**,
contracts/catalog/source checks, repository hygiene/secrets, Ruff and mypy across
105 tool files plus the existing adapter Python checks. Its final log is
`.cache/p15-main-audit/check-delivery.log`, SHA-256
`0688ea67897f5a2928789b08c6ea76a41c0d0d8d2adadc43684e6a52e8245b2d`.
After adding all new source/docs to the index, explicit content, Markdown,
workflow and secret checks passed; no handoff or raw evidence was staged.
Documentation checks do not establish runtime or performance behavior.

| Identity | SHA-256 |
| --- | --- |
| Retained evaluator/producer JAR | `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d` |
| Locked SLF4J API 2.0.20 | `7e1446499b359675d8aabe6af2de86b85e72ae8a2a932c0b40d0e5ba57097439` |
| Exact fixture plan file | `cb566e7da87ac1d3f2631636ac3219dc6f723d923f165e66a4332da92ccbd66e` |
| Lifecycle A bundle | `7bc15c1a13e781a3e5bb0a7346515bd2ea9face8c086ffef346977dcbd58b111` |
| Compatible fixed profile | `9c72f903bd34cfcd54eb5de05a9ab8574f199f88a971ec4355a1e4af42b20252` |
| Original independent suite | `10b9474171da555d0bd13a87588584333ea39276c2e057f58f199fba5aabbdfb` |
| Store source | `4c9d598077b371329bf78951e60e5218e6f273f3efabe2c63bce7e22ff79c10e` |
| Validation/runner source | `1ccab0a4622cbcc4baea636f5bc2b6e4f8b75d408be844f5636bb33c065abe6e` |
| Qualifier source | `6444444c3bfdce59dca5a4f78e4a1efc5a1f4da8c4560ec94df0085f257ff037` |
| Lifecycle tests | `83fd9502a8613048107be64e0e5f766e443e0b2d6040eba82821d859d360944b` |
| Gate tests | `2c6f4129d1ddefc94908b7ca8767ecb72edfdc70cdfc5890bb2536198ae7ecb6` |
| Final summary | `0364cf560df9724729659481230400b743c617ed475793a00de1b0f2b0fbbb3a` |
| Final build log | `994b63dd64ab2e21ce98b1ed33794c90591ccfc1ddc9bc77717749c89d93dc5a` |
| Final test log | `f69b18758a1418c9ba433414d3d8a76adb7e74850c38f9537202d3176b48bd1a` |

Final report/logs remain ignored in `.cache/lifecycle-qualification/`. Raw private
recordings were not needed, read, recaptured or uploaded. All eight original
documentation/handoff file hashes in `.cache/p15-main-audit/preserved-sha256.json`
still match their original working-tree bytes. The root untracked handoff remains
uncommitted; the six older worktree completion edits and its handoff stay untouched.

## Case coverage and limits

| Frozen cases | Actual evidence / supported limit |
| --- | --- |
| A01–A08 | Real import/compiler validation/Java test/stage; exact retries, changed request conflict, manifest/plan corruption and provenance-preserving modified candidate |
| A09 / A14 | Existing compiler limits retained; rehashed AST differing from original YAML rejected; no new maximum-rule throughput qualification |
| A10 | Real bounded suite-size/count rejection; reduced effective store/free/history caps test exact admission boundary and +1. This does not establish actual 512 MiB disk-fill survival or a 4,096-record endurance run |
| A11–A16 | Staged preparation, one-winner concurrent compared revision, predecessor/membership validation, distinct compatible A→B→A proposals and prepared-reference retirement blocker; no worker application |
| A17–A18 | Checked head/journal corruption rejection; actual child `os._exit(86)` after record publication, stale-head recovery and exact retry; injected sync-order red/green; orphan object is not an import fact |
| A19–A20 | Private UID/mode/symlink/overlap checks, fixed diagnostic boundary and bounded helper-process output; not a remote authentication service |
| A21–A27 | No caller passing receipt; actual literal Java positive/negative outcomes, changed expectation mismatch, failed-retest readiness, invalid output/nonzero/timeout/oversized-output helper probes; helper probes are component evidence |
| Old artifact boundary | Actual original integration JAR rebuilt/verified at exact 51a984de; source/resources and P14 pins untouched. Native old runtime consumers still require their own actual CI |

The 10-second deadline, 2 MiB output and other maximum budgets are admission bounds,
not capacity claims. Abrupt process exit and injected sync failure do not establish
physical power-loss, local-disk-loss protection or HA. The store never deletes
immutable bytes/history and never evicts prepared references. P15b must separately
design authoritative membership/publication, apply/durable acknowledgments,
actual version attribution, checkpoint compatibility, runtime rollback and a
supported new archive/replay profile. P16 does not bypass those gates.

Native `lifecycle-verification` restores the exact prepared Gradle dependency cache
and fails closed on a miss before bootstrap. It rebuilds/verifies the actual
retained artifact and runs required no-skip tests. Classifier propagation includes
candidate inputs and all integration consumers; the aggregate rejects missing,
failed, cancelled or unexpectedly skipped lifecycle checks. Owner acceptance,
merge authorization, actual merged checks and release remain distinct.

## Native PR qualification passed — 2026-11-19

[Run 44466077762](https://github.com/TravisMa07/DetectBridge/actions/runs/44466077762),
attempt 1, associated head `cc31eab5dc87311bc54c05068a2b21fcce089d68`, passed
all nineteen applicable jobs and required-checks. Five explicit acquisition/recording
opt-ins were skipped. Aggregate job 135376720297 completed at 06:08:23 UTC.
Actual checkout was PR test merge `f1c078e9273adef7bc24e5002f2875654a709a8b`,
merging cc31eab into f44c9f9. This is not actual merged-main qualification.

Lifecycle job 135364841542 passed all 30 checks with zero skips on
`Linux-7.0.0-1014-aws-x86_64-with-glibc2.39`. Source was clean at f1c078e;
all seven implementation/test/fixture hashes match final local evidence above.
Exact original evaluator `51a984de`, logging `7e144649`, plan `cb566e7d`, bundle `7bc15c1a`
and compatibility `9c72f903` match the attributed local identities. Other applicable
legacy detection/source/assembly/integration/search/archive/historical/current/
maintenance consumers also passed on their actual native artifacts. The lifecycle
consumer restored the exact prepared dependency cache before bootstrap.

Metadata, complete run log and original downloaded lifecycle artifact remain under
`.cache/p15a-native-44466077762/`. SHA-256 identities:

- `run.json`: `81144924d9f434c7e4c385ecae4532b33a150bdf71b215f76cc08e44d99c2adb`.
- `run.log`: `282aaf9dc4f5c86ba4fa8164a8e01c80f8cbe0c505069efe2620d2986fb75fbe`.
- `artifact/summary.json`: `4d96f498a9beb83e19b3392f0d803086680ff3cfe37aef5e35c92ad97bd91c9b`.
- `artifact/build.log`: `19678b7db2dbc1d669acfe7bdec7a4332a65b0ca1af08681d8ef17bf77bc7f9e`.
- `artifact/tests.log`: `f866a36e9930a62004ae8775f75d899f8eff04dcd7b37e5cfd538f2b9e12c1a3`.

Refreshed comments, submitted reviews and inline review threads are empty. PR #57
is clean/mergeable with checks passed. Owner semantic/completeness review,
explicit merge authorization and actual merged-main qualification remain open.
This native result establishes P15a candidate preparation only; all P15b/P16,
private-recording, HA, disk-loss, unbounded-outage and throughput limits remain.
The PR description and issue #15 record this exact native result without an
incidental evidence-only push. No merge or release was performed.

## Actual merged-main qualification passed

[Run 44472864062](https://github.com/TravisMa07/DetectBridge/actions/runs/44472864062),
attempt 1, is an actual push on regular merge
`f44403e2975db46554c9c5033f87886d880c4087`, not the earlier PR test merge.
All nineteen applicable jobs and required aggregate135396305876 passed; five
explicit acquisition/recording opt-ins were skipped. Lifecycle job135387101572
passed all30 checks with zero skips, sourceclean at f44403e on
`Linux-7.0.0-1017-azure-x86_64-with-glibc2.39`. Original evaluator51a984de,
logging7e144649, fixture plan cb566e7d, lifecycle bundle7bc15c1a and
compatibility9c72f903 match their exact existing hashes; all seven runtime/test/
fixture source hashes match the prior attributed source set. Other applicable
source/integration/archive/replay consumers passed independently on this merge.

Raw metadata, complete log and original downloaded lifecycle artifact remain in
`.cache/p15a-main-44472864062/`. SHA-256: metadata
`951c5f711166989aa89ae2c35ba8a7aad536224cd18fb994431c324f6b9f4f21`; log
`adf485150ffa678531bcd4ac988071f344035ebef088b8ad2ba12232b74d50dd`;
summary`f795da42f82af610744c2379c3c60a689c0e8aed70d612bdd5fc92696c018f41`.
This clears the exact merged-revision prerequisite for P15b; no P15b runtime
pass or full P15/P16 completion follows. Original stashed native-completion
notes and all older uncommitted handoffs remain preserved.
