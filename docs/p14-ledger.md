# P14 design and qualification ledger

## Current implementation boundary

P14a is locally implemented on `feat/p14a-durable-archive`, based on qualified
07e5382. Concrete schemas and independent vectors were separately frozen in
`e9b6143` before production code. The archive consumer/backend, lifecycle/retrieval/
metrics tools, meaningful regressions and actual Kafka/filesystem qualifier exist.
The final local artifact passed all twenty-six actual Kafka/filesystem scenarios;
exact identities and limits are consolidated below. Owner acceptance,
authorized merge and successful merged-commit checks remain separate gates.
P14b/c execution, P05 local-file import, retention/deletion, private recorded replay
and complete P14 milestone acceptance remain pending. The handoff remains untracked
and uncommitted; no merge or release is authorized or performed.

## Initial design checkpoint — 2026-11-18 UTC

P14 prerequisites are met. [Owning design](p14-design.md) and
[independent matrix](p14-expectations.md) are local proposals, authored before
production code. No P14 schema, implementation, freeze commit, runtime test,
semantic acceptance, PR, merge or release exists. The first concrete P14a
schema/vector freeze remains required before implementation. The local handoff
is intentionally uncommitted and must remain outside any publication.

Checkout inspection found `main` at
`07e53822dd8a5035125804321e5c852f9a466aef`, with only untracked
`docs/p14-handoff.md`. The handoff's described tracked completion edits were
absent in this checkout; none were discarded. Fetched `origin/main` is still
that exact qualified SHA. Created `docs/p14-archive-design` from it, preserving
the handoff unchanged. Completion records are reconciled locally against live
evidence, without rewriting historical failed runs or published history.

## Refreshed prerequisite evidence

- P05 remains complete in its local replay scope; historical/restored artifact
  mapping and exact runs remain in [P13 acceptance](p13-acceptance.md).
- Live PR #49 is owner-merged as `07e5382`, head
  `85818875576616e42aa26720dc74486f93b9655c`; inline review threads are empty.
  Its body and issue #13 record explicit bounded owner acceptance, including the
  private recorded AMD64 limitation. Issue #13 is closed.
- Actual merged-main push [44206958555](https://github.com/TravisMa07/DetectBridge/actions/runs/44206958555),
  attempt 1, is completed/success on exact `07e5382`, updated
  2026-11-18 00:43:43 UTC. All fourteen applicable jobs including required-checks
  succeeded; five acquisition/recorded opt-in jobs were deliberately skipped.
  This is direct merged-SHA evidence; tree identity does not transfer CI.
- Issues #1–#13 are closed, #14 is open. Project 4 shows P01–P13 Done and P14
  Ready. M0–M4 are closed. REST milestone open-item counters report 2/3 for
  M3/M4 despite the directly queried prerequisite issues being closed; no
  unrelated PR or future issue was changed to reconcile those counters.

Connector tools read issue/PR/review/job state. The commit-workflow endpoint
returned an empty list for this SHA despite the known run; direct `gh api` read
verified the run's exact SHA/event/attempt/conclusion. CLI readback supplied
project/milestone state unavailable through the connector. An initial unquoted
milestone URL hit zsh glob rejection; the quoted read succeeded. Neither read
error is a runtime qualification result.

## Implementation boundaries and remaining work

P14a owns archival durability/offset accounting and exact retrieval; P14b owns
sealed original-member pinned execution; P14c owns explicitly changed policy,
isolated resume and retention qualification. Milestone acceptance will require
an explicit requirement-to-evidence map across all slices. No circular dependency
on P15 activation, P16 coordination or a management API is introduced.

Before P14a production code: settle/freeze actual schemas and independent byte/
identity vectors as a distinct commit, then demonstrate meaningful behavioral
failures. Before P14b/c code: freeze supported executors, explicit membership/
schedule/output/state and retirement interfaces plus literal semantic cases.
Consequential architecture changes require owner discussion/ADR; merges/releases
retain separate explicit owner authorization. Existing P09–P13 bounded acceptance
is not reopened by P14's new tests.

## Initial design-only local validation

On base 07e5382 with these uncommitted Markdown-only changes, macOS ARM64:

- `uv run --locked python tools/dev.py check` passed 169 Python regressions,
  contracts/catalog/dependency checks, hygiene/secrets, lint/format and types.
  Log: `.cache/p14-design-check.log`. Normal hygiene discovers tracked files.
- Explicit locked `check_repo.content_errors` validation included all untracked
  P14 Markdown files as well as tracked files; content and relative links passed.
- The installed locked Markdownlint 0.42.1 API, using the repository's config,
  explicitly checked all four P14 Markdown files, including the untouched local
  handoff; passed. The first API invocation used a nonexistent named export and
  failed before linting; corrected to the module's actual `lint` export.
- `git diff --check` passed. No production code, contract, dependency, CI job,
  private evidence or generated artifact was added to Git. No commits or remote
  mutations were made.

These are documentation/component checks. No P14 runtime, archive durability,
historical reproduction, power-loss, performance or new platform qualification
is claimed. Actual P13 merged-main qualification remains separately attributed
above; it cannot establish P14 archive behavior.

## P14a implementation and retained development failures

The archive is a separate Java module using the existing reviewed Kafka/Jackson/
schema stack, a dedicated UUID group and owned local root. No upstream coordinate,
producer topic/contract, P12/P13 checkpoint state or search permission changed.
The Java dependency inventory adds actual archive module/configuration uses to
the existing 67 reviewed coordinates. The real fail-closed archive CI gate invokes
component and actual Kafka/filesystem qualification; it is not a placeholder job.

The first compile preceded Main.java and failed on that missing entrypoint. Initial
JUnit setup rejected macOS's symlinked `/var` temporary ancestor; tests now resolve
their supplied temporary directory to its real path, preserving production path
rejection. Neither setup failure is a meaningful behavioral red.

The next actual storage tests exposed unsafe topic IDs and identical-byte retries
whose parsed integer-node representation differed from the original in-memory
nodes. Topic IDs are now path-safe and retry equality compares exact canonical
bytes. Changed wire content still fails without overwrite. These were meaningful
behavioral failures; fifteen Java regressions now cover exact vectors/ranges,
null/empty/headers, immutable retries, every partial publication window, gzip/
metadata corruption, signed integers/Unicode/schema framing, chunks/empty objects,
writer locks/path safety, budgets, offset reconciliation and source dependencies/
conflicts. A further regression rejects signed-64-bit range overflow and retains
unknown staging evidence instead of deleting it. Recovery syncs surviving
publication directories before any offset reconciliation.

The first root check failed three older aggregate fixtures that lacked the new
archive applicability/job fields. Those fixtures now explicitly say inapplicable/
skipped; the aggregate was not weakened. Subsequent lint/types failures included
an inferred heterogeneous report type and a missing Any import; explicit report
annotations/imports corrected them. Historical logs remain ignored; these failures
are not archive runtime qualification.

### Original actual runtime attempts

- Project `detectbridge-p14-test-71f0cdf9c75b`, JAR
  `128c03f547243f5732d0ff6c8f5172dd1faad8754e5e161cc4b9d23c6cb43d74`:
  initial nine-topic exact-byte/null/header/object checks passed; first process
  crash assertion failed. The original helper wrapper discarded the exit status,
  so its retained report does not independently establish that original fault.
  Original report SHA-256 `d9a8fb24c742883c07c45d3d4b84e48dcbbbc32c980fb714d098918006ca1721`.
  Later helpers retain original exit/stdout/stderr privately before owned cleanup.
- Project `detectbridge-p14-test-a4df3ccb13c7` passed its initial twelve scenarios
  and nineteen occurrences on that same actual 128c03f JAR, as its immutable root
  configuration confirms. Its original report erroneously read the changing latest
  build pointer and named def536af; report hash
  `1d64f8c63a7e21707902d44524585be77396c42fced296cdccaf189b970ac1f2`
  is retained unchanged. It does not qualify def536af. Tooling now pins production
  JAR, separately hashed qualification JAR and execution image per project; reports
  snapshot loaded tool hashes before work. Commit crash hooks were also tightened
  to run only after newly admitted records, rather than an initial empty poll.
- Project `detectbridge-p14-test-7d8bc3afa6b0`, JAR
  `be9aa340ff9937b9be64724d16c411b3d4d6fe9b98f4d9852f6031380be8cc5e`:
  sixteen expanded scenarios and twenty-three occurrences passed, including actual
  partial writes, group reassignment and filesystem permission failure/recovery.
  Report SHA-256 `e643836e2c43eca74dd8038d1b87f0dc5c62f9545f537410a0a2b3be1b1edb81`.
- Project `detectbridge-p14-test-305bb5d7ab16`, JAR
  `bf11147395642c81f8f3d54778cdfa2598caf3f75ebb199fcb786165c016e77e`:
  all twenty-four scenarios and twenty-six occurrences passed, additionally
  covering six object-publication process crashes, missing required objects,
  original reference ranges/contexts, exact signed integers/twelve-digit timestamps
  and actual 32 MiB incompressible object retrieval. Probe JAR
  `42e5a2b6c5af56e158497ac0ebd8e71c66e8907201b0df3647b0889dece6c09c`;
  report SHA-256 `ea3e17ac959c905fa931f00f3a22e325fd9d15e538dd7399536aa0aae1f1217a`.
  Final range-overflow/path/recovery guards require the separate final run below.

All runs used the pinned Flink Java17 container on local Linux ARM64; these are
synthetic original bytes, not private source recordings or historical evaluator
reproduction. Original private helper failures, admissions/expected locations,
compressed artifacts and reports remain under ignored `.cache/archive*`. Only
owned containers/volumes were removed. No historical failure or intermediate
artifact pass is reassigned to later production bytes.

## P14a acceptance map

| Requirement | Implemented evidence | Limit/gate |
| --- | --- | --- |
| Exact originals, provenance, contexts and wire occurrences | Independent byte/range/hash vectors; all nine topic bytes, null/empty and repeated headers; explicit registered originals/provenance | Classification does not authenticate caller-supplied provenance or certify adapter semantics |
| Durable publication before offsets | Separate object/segment commit metadata, gzip hashes/lengths, file/directory sync and immutable chain; actual publication/commit process crashes | Assumes local POSIX filesystem/device sync; no physical power-loss or disk-loss protection claim |
| Recovery and conflicts | Full verified-prefix scan; identical retry versus distinct location; conflicting-content/semantic-conflict cases; actual broker commit-ahead and topic replacement rejection | No reset, migration or corrupt-data repair; old checkpoints cannot be adopted |
| Corruption/missing inputs and finite exhaustion | Bounded gzip/NDJSON validation, signed-range guards, actual corruption/missing-object/permission/outage tests; model/config budget edges; 32 MiB incompressible actual boundary | Physical ENOSPC and free-space race are not claimed from injected/model tests; no unbounded outage promise |
| Progress and isolation | Separate archive UUID/root/group; durable/broker/earliest/end/lag vector, dependencies flag, Prometheus fixed labels; actual reassignment | Historical-ready remains false; archive progress alone cannot authorize another consumer's retention/deletion |
| Prior consumers | Combined Java source/parser/evaluator/writer regression suite; unchanged source/output/state contracts | Separate actual legacy Docker suites remain native CI gates, not inferred local runs |
| Native/recorded/owner integration | Real applicable archive-verification gate plus existing consumers; PR evidence will carry exact head | Native AMD64, owner bounded acceptance, authorized merge and actual merged checks remain pending until observed |
| Full P14 replay and retention | Interfaces and independent expectations are retained | P14b/c, P05 import and milestone-wide acceptance remain required; no P14 completion claim |

### Metadata-integrity behavioral red and correction

Focused `tailMetadataCorruptionCannotAdvanceDurableCoverage` failed as intended
before the fix: changing a last segment's `next` from 1 to 2 was accepted without
changing its payload. Log `.cache/p14a-metadata-red.log` retains the actual assertion
failure. A predecessor chain alone cannot protect its unreferenced final metadata.
The separate metadata-file checksums required by the freeze had not been written.

Root/object/segment checksum sidecars now cover exact JSON file bytes, are synced
before publication, and are verified before parsing/adoption. All fifteen Java
regressions passed on the corrected artifact. This implements frozen D09; no
expectation or offset assertion was weakened and no intermediate artifact's pass
is presented as coverage for this newly exposed failure. The actual qualifier adds
metadata-offset corruption with unchanged Kafka progress to its earlier scenarios.

Project `detectbridge-p14-test-712168f5749f` passed the earlier twenty-four-scenario,
twenty-six-occurrence suite on 4a979a37 (full hash in its ignored immutable config
and report). Project `detectbridge-p14-test-9817eb499033` passed twenty-five scenarios
and thirty occurrences on 02471e15, adding actual transaction control-batch gaps.
Those successful intermediate runs did not include the tail-metadata regression;
their results are not reassigned to the corrected final artifact. Original logs
and reports remain ignored, including `.cache/p14a-{qualified,gap}-runtime.log`.

## Final P14a local qualification

On the working source tree based on freeze e9b6143, project
`detectbridge-p14-test-79d118599183` passed **all 26 actual scenarios and 30 exact
wire occurrences** on Linux ARM64. This includes nine topics, original byte/range/
context and signed/time preservation, nine process-crash windows, six object
publication crashes, actual transactional control-batch gaps, group reassignment,
missing required objects, permission failure/recovery, broker outage, committed
payload AND metadata-offset corruption, broker commit-ahead and topic-UUID
replacement rejection, and 32 MiB incompressible object retrieval. Offsets were
independently read from Kafka and could not exceed verified durable coverage.
All expected original keys/values/nulls/headers/locations were independently
retrieved and compared; no fabricated control-gap record was admitted.

Exact executed artifacts:

- Production JAR SHA-256: `4b8058bde92450e3de556a029764a1168c53f8ab4e72bca005b177af2da878f7`.
- Qualification JAR SHA-256: `077d2af0c1e89c14394758d93f34b46fc7edee3e32aa245ffb82e65a2417539f`.
- Pinned image: `flink:2.2.1-scala_2.12-java17@sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`.
- Actual ARM64 image ID: `sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`.
- Loaded CLI SHA-256: `7278e38b0bb5ad0fc4fa39d4b02cb8f84369b66fe0313c45383ef419df017bcb`.
- Loaded qualifier SHA-256: `43d21eef65b5c67fde9f769607b1b87f7ee6b42b4ec63e808b830ae1bd865493`.
- Private result `.cache/archive-reports/detectbridge-p14-test-79d118599183.json`, SHA-256 `5dc43edf709ef42e306d0788dda0168405a3408e09002769e070104e310adef7`.
- Private runtime log: `.cache/p14a-metadata-runtime.log`. Original synthetic
  inputs, expected physical locations, exact archive bytes and helper failures
  remain in the ignored owned project; only its containers/volumes were removed.

Final local locked `tools/dev.py check` passed 175 Python regressions,
contracts/catalog/dependencies, hygiene/secrets, formatting/lint and types.
`tools/dev.py archive` passed six owning Python regressions and packaged schema/
license checks; the final module build passed fifteen Java tests with zero
failures/errors/skips. Combined `tools/dev.py java` passed all legacy/mapped
independent YAML-to-Java semantics and existing source/writer consumers, including
the final archive module. Logs: `.cache/p14a-{metadata-check,qualified-java}.log`,
`.cache/p14a-metadata-green-build.log` and `.cache/p14a-final-components.log`.
Documentation/component results and actual Kafka/filesystem results remain
separately attributed. The source was dirty at execution; the JAR/tool hashes above
identify the exact tested bytes subsequently consolidated for the implementation
commit, rather than claiming the initial freeze already contained this runtime.

CI's synthetic failure artifact preserves original helper exit/stdout/stderr,
immutable tooling and value-free root binding alongside the report. It excludes
payload segments, objects, admissions and original registries. Ordinary CI never
loads private recordings. Final-head native AMD64 and actual merged-commit results
remain pending until directly observed; no ARM64-to-AMD64 transfer, private
recorded qualification, physical disk-full/power-loss, throughput, HA, P05 import
or historical/current-policy execution is claimed. Owner acceptance and explicit
merge permission remain open. Full P14 is not complete.

## First native CI failure and bounded correction — 2026-11-18 UTC

[Run 44219814059](https://github.com/TravisMa07/DetectBridge/actions/runs/44219814059)
on exact head `03ca35936535b7b45ea156303921521e85e9dcdc` failed detection,
integration and required-checks. Every other applicable job passed, including
actual archive-verification on native AMD64. This is a failed required run,
not an adopted dependency/merge gate or complete P14a acceptance.

Original job logs were retained before diagnosis under
`.cache/p14a-ci-44219814059/`. Their SHA-256 values are:

- Detection job 134518638709: `5727fc3dfd91a090c89c100a8d6e3f21d0c03ca73c29a589c34d1349df568bff`.
- Integration job 134518638838: `0794d8ced6be815f76d23d672b9484158305a132bf6da693db62382be6dadfdd`.
- Archive job 134518638901: `dbdadb963617c89bb1bc4198d2c486492526303920299b83bd38c35eb48f711f`.

The run's artifact listing is empty. Integration failed at `gradlew help` before
component/runtime tests: Maven Central returned HTTP 429 for plexus-utils 4.0.3
and commons-codec 1.22.0, disabling the plugin repository's further resolution.
No version, repository, lock, retry bound or required assertion is changed to
bypass that failed attempt. A fresh successful run must supply separate evidence.

Detection reached actual legacy semantics/replay, TaskManager recovery, unavailable
sink and explicit restore, then failed `test -s .../_metadata` at
`jobmanager_restore_submission`. That establishes an unavailable/empty selected
metadata file; the original run lacks a retained checkpoint inventory proving its
exact retirement timing. Code inspection identifies the still-running selection
window previously corrected in P12/P13 qualification. A focused coordinator test
reproduces an observed checkpoint being retired during shutdown and fails at that
same restore operation. The initial model setup lacked its input-topic attribute;
that setup error is not the behavioral red. The subsequent intended missing-
metadata failure is retained in `retention-red.log`.

Both detection modes now use `retained_checkpoint` to cancel, select a COMPLETED
retained checkpoint and verify its actual metadata before shutdown. The mapped
incompatible-binding probe uses the same retained boundary and explicitly requires
its original job to be CANCELED; unrelated failure/ambiguous-job rejection stays
strict. Fifteen archive Java tests and the archive production code are unchanged.
No new semantic expectation replaces the accepted P09/P10 packet.

Root checks initially exposed the older probe test's direct-stop assertion after
cancellation moved into its caller. Tests now explicitly prove the required prior
CANCELED state, reject RUNNING before probe submission, and retain every exact
binding-failure/unrelated-failure assertion. Locked root checks then passed all
177 Python regressions plus contracts, hygiene/secrets, formatting/lint and types;
log `check-final.log` in the diagnostic directory. CI now retains only synthetic
detection report/checkpoint/job metadata on failure, excluding source inputs.

Native archive project `detectbridge-p14-test-1a3f4f703690` independently passed
all 26 actual scenarios and 30 exact occurrences in the failed aggregate run.
It used production JAR 4b8058bd and probe 077d2af0 (full hashes above), with actual
AMD64 image `sha256:6b26436e8a89f49acaf0133e35f1e3715544e7c984d0f68cd8038137ab2e6be9`.
This is actual native archive evidence on 03ca359, not a transferred ARM64 pass,
private-recording qualification, or success of the failed aggregate/new correction.
The correction is a necessary third cohesive commit after the published freeze
and implementation; existing published IDs/timestamps are preserved.

### Local correction qualification

The actual suites ran serially on local Linux ARM64, working from 03ca359 with
the qualification-only correction. Legacy project
`detectbridge-p09-test-baf7531e654d` passed eleven valid/two invalid inputs and
11 result entries through semantics/replay, TaskManager recovery,
unavailable quarantine sink, explicit restore, cancellation/retained metadata,
JobManager recreation/restore, metrics and payload-free logs. Report SHA-256:
`864e54e85c790890398506768927efb79b962ad8222020a340a743d4ac893d5d`.
It used bundle `2a2a81d6a455da844b5588d9480674f2e43e965c557564dda9af3ea995b87479`,
JAR `890a811254a24b9317bf74457a166cb877a494b80a44312af4d9f94f7a273938`,
actual image `sha256:29ca51b6f91f72d3b8c9d0af535a4ae5ca4c4b36bdcdd792ec6998d186cf9f92`.

Mapped project `detectbridge-p10-test-7dee22ef6da0` passed sixteen valid/two
invalid inputs and sixteen result entries through the same scenarios, seven
isolated runs and the exact incompatible-binding rejection followed by healthy
restore. It used the same JAR hash but separately pinned mapped bundle
`a95d40c373cb622cf2125008dd16a0e476634e61ce6479257371423b04f36df2`
and actual image `sha256:80635c0ff23877e3dd000fc81834c36e105c9fb9a5d7f15ea91797ab9eca865b`.
Logs are `legacy-runtime.log` and `mapped-runtime.log` in the diagnostic directory;
source inputs/observations remain ignored and only owned stacks were removed.
These are actual corrected local qualification paths, not native or merged-commit
passes. The final mapped run also exercises the added CANCELED-state probe guard.

Locked root checks passed 177 regressions, lint/format/types, contracts/catalog/
dependencies and hygiene/secrets; Markdown/content/relative-link and workflow
checks passed. Fresh native CI on the published correction must independently
qualify the exact new head and rerun integration after its pre-test HTTP 429.
Owner review and explicit merge authorization remain separate; no merge or release.

## Corrected-head native CI passed — local completion record

[Run 44226629958](https://github.com/TravisMa07/DetectBridge/actions/runs/44226629958),
attempt 1, completed successfully at 2026-11-18 03:17:11 UTC on exact head
`bfe656e9a3340511546e0cd7661f5c767908a0fb`. Every applicable job and
required-checks passed; five deliberately unselected acquisition/recorded jobs
were skipped. This directly qualifies the correction head; the earlier failed
44219814059 remains failed historical evidence. It is not merged-main evidence.

Native legacy project `detectbridge-p09-test-1980f9c9a268` and mapped project
`detectbridge-p10-test-7816b7c26e1e` passed 11/2 and 16/2 valid/invalid inputs,
respectively, including corrected retained checkpoints and JobManager restore.
They used JAR `890a811254a24b9317bf74457a166cb877a494b80a44312af4d9f94f7a273938`,
legacy bundle 2a2a81d6 and mapped bundle a95d40c3 (full hashes above), with actual
native images `sha256:47a41ba585442a8986ada060a4ef11138b9d3379b559a20743e12e97fb12776d`
and `sha256:ad72721efae3b0c01edaa6bee9ef1432f1d2dcc9f75a7f24b10b265e456672ed`.

Native integration project `detectbridge-p13-test-96541ba86411` passed all 44
inputs, 103 logical/145 physical outputs, 40-second broker pause and every required
sink. Its JAR remains 51a984de (full hash above); exact bundle
`db1827f0aef1f382821ce0ae0c47e093ed3a887d05f47495149f4646ace29504`,
plan `29e8073c726a2b55c136a413d6410ca2cba5938cad3e9837da1d251742aef1a4`,
actual image `sha256:87bb0e251ad2043db7232c6121a17c146763a95a213965ca23deb07bc087cc55`.
This fresh success is separate from the original pre-test HTTP 429 failure.

Native archive project `detectbridge-p14-test-364b4e81f555` independently passed
all 26 scenarios and 30 occurrences on this correction head, using actual JAR
4b8058bd, probe 077d2af0 and native image 6b26436e (full hashes above).
All remaining applicable semantic/source/assembly/search/transport gates passed.
Private recorded AMD64 qualification remains unavailable; no opt-in skip counts
as recorded qualification or expanded P13 acceptance.

Original successful job logs are retained at `.cache/p14a-ci-44226629958/`:

- detection.log SHA-256 `d5f3ce5b59ed3e6bc1940e82504b9ad41d0d8982058790c712da669ec039aef9`.
- integration.log SHA-256 `db1f5b1cf59df85fa85f001d865bc1a3e427893598bcce11f4aba83182dd2d4f`.
- archive.log SHA-256 `2df095d257c9b2b847f411d33f8b7458bc8e3b10da2b23d1c0e8f648c631cd91`.

This completion note stays local/uncommitted rather than creating a new source
head merely to record progress. PR #50's body records the same direct native
success. Owner bounded review/acceptance and explicit merge authorization remain
open; the PR stays draft and unmerged. Actual merged-commit checks will still be
required after any owner-authorized merge. The handoff remains uncommitted.

## Owner merge and P14b preparation — merged qualification still open

The owner merged PR #50 on 2026-11-18 03:45:22 UTC as
`cd6f46ec70e6c7ca17e3cd21594e396ef541509c`, regular parents 07e5382 and
bfe656e. This supersedes the preceding pre-merge status; it does not transfer the
head's CI success to main. The preserved head-completion note above is now batched
with next-slice preparation rather than published as a standalone progress commit.

Actual merged-main [run 44232624596](https://github.com/TravisMa07/DetectBridge/actions/runs/44232624596),
attempt 1, failed toolchain job 134561156553 at `gradlew help`: Maven Central
returned HTTP 429 fetching Ant 1.10.17 and Plexus XML 4.1.1 while configuring the
Shadow plugin, before tests. Other jobs were still running when diagnosed. Archive
verification independently passed on this merge, but the whole prerequisite is
not passed. No source correction or test waiver is justified by these logs.

The original full toolchain log was downloaded before diagnosis to
`.cache/p14a-merge-ci-44232624596/toolchain.log`, SHA-256
`553e8b6ca84bfcaf62c3ec3074e2274c3a5552aeda1b0e197182a9b7b03fb018`.
The original artifact listing was empty and is retained alongside it. An unchanged
job rerun request was rejected with HTTP 403 because the workflow was still
running. A later retry must remain separate attempt evidence.

The owner requested the next roadmap PR. Branch `feat/p14b-historical-replay`
preserves local documentation changes and the ignored/untracked handoff. The
[P14b design](p14b-design.md), closed request/selection/run schemas, independent
identity vector and existing-source fixture/count packet precede production code.
They prepare bounded original-membership historical execution, not current-policy
reprocessing or a complete P14 service. P14b implementation remains gated on an
actual successful merged-main run; no failed base is adopted as qualified.

Locked `uv run --locked python tools/dev.py check` passed 177 regressions,
contracts/catalog/dependency checks, hygiene/secrets, lint/format and types on this
documentation-only working tree. Log: `.cache/p14b-preimplementation-check.log`.
The new untracked schemas/fixture hashes/text/relative links were also checked
explicitly, since tracked-file discovery omits them. No P14b runtime pass is claimed.

Attempt 1 completed failed at 2026-11-18 04:18:11 UTC. Every applicable runtime
job passed on cd6f46e, including assembly and integration; only toolchain bootstrap
and the correctly failing aggregate failed. Integration project
`detectbridge-p13-test-1146eae339c3` passed 44 inputs, 103 logical/144 physical
outputs, all seven required sink failures and 40-second broker pause. Exact JAR
remains 51a984de; bundle
`843d8fad661afe4ec777d16ce504741eea72a416d96a7138d9b1516c6067f30d`,
evaluation bundle `9cf012a4583903b1f5518df83a4842922b4a1c9e5f3c1f17bfedb4222f14b69b`,
actual AMD64 image
`sha256:49c2f078c03a960971d04c29dc3991104d1b3acb46601ded18bf0224ac92449c`.

Original merged-run integration/archive/assembly logs are retained beside the
failed toolchain log; SHA-256 values respectively:
`ee1987e495ef36eca11bd420b468563985c3053f9db65b263391ed8acf53ab6b`,
`3d16ab6883cc7aedf7dc98b624ae931a9f9a580313e412dde2ea72cf7026710b`,
`f47b28f4c0c535cedaee73d8f7bf0a40cab9d4073cd86324484b72f0e94abb34`.
The original attempt's job metadata is retained as `attempt-1-jobs.json`.
After completion GitHub accepted an unchanged failed-jobs rerun on the same SHA.
Its outcome is separate evidence; the original failed attempt stays failed.

## Exact merged-main gate passed before P14b production work

Run 44232624596 attempt 2 completed successfully on exact merge
`cd6f46ec70e6c7ca17e3cd21594e396ef541509c` at 2026-11-18 04:20:11 UTC.
Every applicable job and `required-checks` passed; only the five deliberately
unselected acquisition/recorded jobs skipped. The unchanged toolchain retry is
job 134573465429 and the fresh aggregate is 134574053423. Original successful
runtime jobs from attempt 1 remain attributed to those same-SHA jobs, not to a PR
head. Attempt 1 remains failed; the retry is separate successful evidence.

The original retry toolchain log is retained as
`.cache/p14a-merge-ci-44232624596/toolchain-attempt-2.log`, SHA-256
`482c99f7bbd478465a9e759e227a35e6bddc67f9ba72977cdda75d0d4899d542`.
Exact run/job metadata is retained as `attempt-2-run.json` and
`attempt-2-jobs.json`. No source change, test waiver or resource increase was used.
The P14a bounded merge/qualification gate is complete. P14b production code began
only after this result; its separate freeze 5922901 already existed. P14b's own
[evidence and remaining gates](p14b-ledger.md) do not claim complete P14 acceptance.
