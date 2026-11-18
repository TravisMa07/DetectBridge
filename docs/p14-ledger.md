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
