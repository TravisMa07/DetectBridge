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
