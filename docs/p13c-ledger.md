# P13c search qualification ledger

Base: owner-merged P13b #47 as `500ffc79deb8843488cbdaa85e4d5ebf64e82b70`.
Exact P13b PR head 8cc680c passed all applicable jobs in 43978412654; its earlier
native processing-sink failure remains an unexplained failed attempt, with later
diagnostics retained. This does not invent separate owner semantic submissions.
Merged-main 44004484594 was pending at implementation preparation.

Owning design 146d1d4 and independently frozen projection contracts/count/identity
expectations 2036684 preceded Java implementation. Separate module/configuration/
resources retain P08's original contracts and two physical indices; new mode has
three exact P13 indices and a dedicated exact-index role. No new Maven coordinate
was added; the existing 67 reviewed coordinates have new actual module uses only.

## Development checks and retained corrections

Actual Java adapter/assembler-to-projection tests passed during development for
both Windows profiles, audit and authentication, independent literal six-count
cases, evidence/manifest links, receipt-clock copies, semantic tamper, partial
bulk item retries, failure acknowledgement/nonrecursion, independent literal
hashes, response bounds, TLS CA/hostname and role/default comparisons. Python
schema/mode/project isolation, independent content vector and fail-closed search
gate regressions passed. Exact final code/artifact qualification is still pending.

An initial test compile needed an explicit Linux test dependency (implementation
project dependencies are not compile APIs). A literal JSON comparison exposed
integer-node representation differences; comparisons now use exact integer-preserving
canonical values, without changing expectations. Actual detection tests rejected
an assumed title/tags accessor: the accepted pinned rule contract supplies neither
after YAML removal. Projection retains actual metadata plus rule ID/revision and
claims no inferred title/tags. Schema checks rejected a copied external diagnostic
reference; the owning self-contained schema now inlines that unchanged definition.
Workflow lint caught the new output's step ID; it now references the actual paths
step. None of these failures is runtime qualification or a passing placeholder.

## Pending qualification and boundaries

Run serial locked check, Java, search, Windows, Linux, assembly and integration
component checks; actual ARM64 source-to-search and writer fault/recovery checks;
and native AMD64 CI. Preserve exact artifacts, attempts, retrieval/identity/accounting
and failure assertions. Local originals remain retained and uncommitted. Full
recorded Windows Security/Sysmon and Linux audit/authentication source-to-search
acceptance is not implied by synthetic fixtures. No archive, activation, API/UI,
throughput, full P13 milestone, owner merge or release claim.

Merged-main 44004484594 subsequently reported `command_failed_checkpoint_metadata_exit_1`
in Linux assembly's JobManager-recovery phase: the selected metadata file was
missing at restore. A deterministic regression demonstrates the selection/retention
race: observing a checkpoint while the job still runs can let a newer completion
retire it before slow stack shutdown. Shared qualification now cancels the job,
then selects and verifies its final COMPLETED retained checkpoint before shutdown.
Only assembly/integration qualification call sites change; runtime checkpoint/state
semantics and assertions remain intact. The original CI trace establishes missing
metadata but does not independently establish every timing detail of this race.
Affected actual recovery suites must pass on the branch containing this correction.

The first root Java run detected an implicit Gradle output dependency: the default
integration-job classes JAR and its deployment shadow JAR shared a filename.
The consumable classes artifact now has a distinct name; the deployment filename
and production code remain unchanged. This is verified by the full root graph,
rather than relaxing Gradle's dependency validation. Initial aggregate fixtures
also lacked the new explicit search applicability field; fixtures were corrected
and the fail-closed gate remains strict.

## First initialized source-to-search attempt

Project detectbridge-p13-search-ae98f42e09 passed initial source-to-search, replay
through actual OpenSearch outage/recovery, duplicates and semantic conflict. It
failed in the blocked-failure-publication phase with search_accounting_timeout.
The writer had correctly stopped with source_identity_or_policy_changed: the
fault helper restored 1 MiB rather than the actual managed failure-topic 2 MiB
policy. The helper now accepts only block/healthy and restores Broker's exact
managed policy; an independent literal regression requires 2097152. No runtime
binding or failure-ack assertion is relaxed. The failed search artifact was
56923477ec5e40508f3640e81e12bb4ae9be1a0f965cbc92ace27ea31a9edd07
(bundle 02d4b5c2d5e768177b1b7abef398fa7c242a774564442d8a369fa8b26615ac4f).
It also preceded the exact project/ECS notice packaging update; it is not final
qualification. Only its owned stack/volumes were removed; its private inputs and
independent expectations/report remain local. P13b deployment JAR
e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a was
unchanged by the distinct classes-JAR build fix.

The next project detectbridge-p13-search-5bea3bc405 passed the corrected blocked
failure-publication and failure-topic indexing/nonrecursion phases, then failed
with JSONDecodeError during the source-window crash phase. That report lacked
the decoding call location. The follow-up adds value-free stack locations and
finer phase markers without weakening assertions. Its search JAR was
0d6176318911a6468e18da2d6ed185b43f0d039ec0d327aa56d2bfb9b0b90db8,
bundle 4f33e91c2e8a73c94c488ca2ef0c56a7ebe96df051ce5e7e3e87b9cd0224de74.
Its owned stack/volumes were removed; original private inputs/reports remain local.

The instrumented third attempt (detectbridge-p13-search-db639a1d66) located that
JSONDecodeError at integration.py:327, called by the crash-stage source oracle.
The writer test deliberately injected malformed output-topic probes; the original
source reader assumed every row there was producer JSON. Qualification now tracks
every probe's acknowledged topic/offset/key/exact bytes and binding, excludes only
those verified controlled admissions from the source oracle, and rejects unknown
or altered frames. A regression proves the distinction. All expected failure
references, keys, reasons, original hashes/lengths/null status and indexed first
copies are independently verified through a bounded read-only failure-topic
helper. No input is skipped by parse error, no source assertion is weakened, and
the actual writer's admission/commit algorithm is unchanged. Additional original
RFC5424 inputs freeze exact nine-digit and 1800 timestamp expectations before
admission, including actual date_nanos doc-value and out-of-range checks.

The fourth attempt detectbridge-p13-search-6851253f4c failed the independent
preservation expectation at linux_assembly_verify.py:214. The new nine-digit
RFC5424 input exceeded the accepted OpenSSH adapter's six-digit fractional bound,
so its extraction-failure preservation was correct. The negative case is retained
with that independent disposition; the six-digit indexed and 1800 retained cases
use actual authentication input. The exact nine-digit indexed case now uses the
supported Windows XML profile and four explicit literal timestamp overrides to
the original gold event, frozen in the expectation fixture. The source oracle's
default gold expectations stay unchanged. No source parser/profile is broadened
and no malformed source is converted into a normalized event. Private source
observations are now retained locally on oracle failure; CI publishes only the
value-free failure report.

The fifth attempt detectbridge-p13-search-256811d591 passed actual source/replay,
exact nanosecond doc values/outside-range handling, blocked failure publication,
failure-topic indexing, crash-after-indexing/before-commit recovery, stored-content
tamper detection and real partial bulk protocol. It failed the permissions phase.
An isolated real-role probe (detectbridge-p13-acl-e40c4b52bc) established that index
delete, document delete, unrelated-index creation, existing-P08-index access and
security administration all returned 403. The invalid empty template request
returned 400 before authorization; the structurally valid template request returned
403. The final suite uses that valid request and an existing P08 denial target,
with per-probe status evidence. No role grant is broadened or denial assertion
weakened. Original partial attempts/inputs remain local, and owned resources only
were removed. Its exact search JAR is
6f60d3589d502bee41dc926c768c130b91e6437f28d115daef8775486593a575
(bundle d78eda0c3c632a108bd89819663c8cc1c6928a1e9c76c13e2eaa274273e05fd4).

## Completed ARM64 source-to-search qualification

Implementation 90afcfe, project detectbridge-p13-search-810141a364: the full actual
Kafka/Flink adapter-to-TLS-OpenSearch suite passed. 35 source admissions produced
21 logical events and 48 source-derived search documents. Ten separately recorded
controlled output-topic admissions produced eight independently verified logical/
physical writer-failure references; the healthy duplicate admissions produced none.
The direct HTTP partial-bulk proof adds one separately identified test document,
not a source-normalization claim. Every consumed writer topic ended at zero lag.

Both Windows profiles, audit/authentication, all six literal outcomes, known-bad
audit quality/configuration precedence, unsupported and extraction-failed source
preservation, exact evidence/member/manifest/attribution links and two isolated
replays passed. Actual Windows nine-digit doc values and authentication six-digit
doc values retained precision; 1800 dates retained an explicit nonindexed reason,
and twelve-digit source strings stayed exact. OpenSearch outage buffering/recovery, duplicate
and semantic/stored-content conflicts, blocked failure publication, failure-topic
indexing backpressure/nonrecursion, actual indexing-before-uncommitted-crash and
restart, mixed 201/400 bulk protocol, all six valid denied operations, restart,
original input/failure first-copy retrieval hashes, metrics/log checks, credential
fingerprint and mapping-drift rejection passed. No source outcome assertion or
managed policy was waived. Only the owned stack/volumes were removed; private
inputs, expected dispositions, source observations, probe acknowledgements,
permission evidence and report remain local under ignored caches.

Exact artifacts:

- Writer bundle: `d78eda0c3c632a108bd89819663c8cc1c6928a1e9c76c13e2eaa274273e05fd4`.
- Writer JAR: `6f60d3589d502bee41dc926c768c130b91e6437f28d115daef8775486593a575`.
- Writer image: `sha256:c82d75b5319a8790285e85b4fed34f98f53b7faf2bf29d25d1b8342d2f4cac5e`.
- Integration bundle: `9847a1aff5b41cff2ffd684855e3079ccdb7eb7c57ba2c905eafa4ecb7e8fd39`.
- Integration JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- Integration image: `sha256:7a994ab7b7371b11aaa815640e51187fd3c339be622a739d8b5e22e52bbbcef0`.

Actual assembly/integration retention-fix and P08 compatibility regressions have
completed qualification. Final native AMD64 CI, owner review and complete original
recorded source-to-search milestone acceptance remain separate gates.

## Completed ARM64 assembly retention regression

The full actual assembly suite passed on the branch's cancellation-before-selection
helper, including the JobManager restore path that failed merged-main 44004484594.
Project detectbridge-p12-test-59b1a4779167 accounted for 52 inputs, ten logical
groups and 83 logical outputs; 92 physical outputs included nine stable duplicates.
TaskManager, explicit/incompatible restore, JobManager, 40-second broker pause
with original deadline, all five blocked required sinks and original-source intent
retention passed. Blocked checkpoints were event 50, manifest 55, diagnostic 60,
quarantine 65 and receipt 70. The limits and serialized-pending byte-pressure
profiles also qualified, including visible closed-budget rejection and retained
source offset. No source/checkpoint runtime policy or assertion was weakened.

- Assembly bundle: `9cba7aed38a1dfd2a3ad57e46cb785cb7863807a13809afa41bfb0c95dad2f15`.
- Assembly JAR: `d341724639876de0e09a5006bf2e265172a75cd16b7d03b495dc1f4086d19a99`.
- Assembly image: `sha256:b46d3af0edbd8ad5dd0eb107c60988bcad5e9dc2b9f524c2b9bbfc90c55a3eee`.

## Completed ARM64 P13b integration recovery regression

The full actual P13b integration suite passed on the branch's cancellation-before-selection
helper and exact search runtime components. Project `detectbridge-p13-test-39d19241dc56`
accounted for 44 inputs, 20 logical events, 103 logical outputs and 145 physical outputs.
TaskManager restart during partial checkpointing, actual Windows authentication and
all six literal outcomes, JobManager restart with explicit restore and incompatible binding
rejection, 40-second broker pause with retained absolute deadline, all seven blocked
required sinks (`tagged` checkpoint 40, `detection` checkpoint 48, `processing` checkpoint 55,
`manifest` checkpoint 62, `preservation` checkpoint 70, `quarantine` checkpoint 78,
`receipt` checkpoint 86), healthy restore, metrics, original Kafka input hashes and
stable duplicates qualified. No source/checkpoint runtime policy or assertion was weakened.

- Integration bundle: `9847a1aff5b41cff2ffd684855e3079ccdb7eb7c57ba2c905eafa4ecb7e8fd39`.
- Integration JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- Integration image: `sha256:682776a4065b16501c5963fb34cfee24e029a08191c5e353973ab0081cc99116`.

## Completed ARM64 P08 writer compatibility regression

The existing reviewed P08 writer verification suite qualified unchanged under project
`detectbridge-test-66328b1dcfb843a3b8703a86f7d7c8a5`. Initialization idempotency,
first run, timestamp projection, OpenSearch outage buffering and recovery, Kafka outage,
duplicate detection and quarantine, partial bulk failure handling, uncommitted-window crash
recovery and rebalance, authorization enforcement, graceful stop with unresolved input,
and full-stack recreation with retained checkpoint restore passed. Accounting confirmed
257 logical documents, four diagnostics, four retrievable references, 252 replay envelopes,
and zero lag across all three managed output topics (`detectbridge.replay.output.v1`,
`detectbridge.replay.quarantine.v1`, `detectbridge.opensearch.writer-failures.v1`).

- Writer bundle: `8f07bc54372380d8fee72b38b423e4a308235a17413d2c48752ada93ee5af3ed`.
- Writer JAR: `68048856dfb680d78c3609a0385536e36b35145cf45b10e31d8205b0cd569d48`.
- Writer image: `sha256:9cf4cc61c3dc9531d813889122508c2565dacab2191cca12ff57b8cb39130eb1`.
