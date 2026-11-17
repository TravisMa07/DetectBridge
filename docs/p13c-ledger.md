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
