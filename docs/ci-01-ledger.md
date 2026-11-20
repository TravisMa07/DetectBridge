# CI-01 qualification ledger

Current status: native mechanics and recovery support the bounded128 ACK-read
correction. A same-source dispatch exposed a distinct open-group30s scheduling
failure and separate search failure. Owner-approved A is implemented with local
focused proof; fresh native/repeatability remain open. CI stays gated; PR63 is Draft. Earlier diagnostic-only gates below are historical.

See [owning RCA design and independent expectations](ci-01-design.md).

## Baseline and protected evidence

Prepared checkout is clean at `6e1ed1c0771711eb42faef0f9e4556999762830c`,
on short-lived `t3/ci-01-root-cause`. Original working tree, dirty documents/tests,
handoffs, stashes, deployment configurations and private evidence are read-only.
Failed native runs remain attributed in [P15b ledger](p15b1-ledger.md).
Native44636802418 late CP87/110 joins establish the deadline failure, not its cause.

## Gates

Design/independent expectations freeze precedes instrumentation. This delivery
prepares bounded diagnostics; no correction/root-cause/native pass is claimed.
Unit/static checks, independent artifact review, native timing collection, paired
backlog mechanics, demonstrated correction and exact all14 gate are separate gates.
The selected production-faults workflow does not replace required activation.
PR61 stays parked; CI-01 blocks its continuation. No merge/release authorization.

## Preserved failure and artifact matrix

| Evidence | Source and outcome | Limits |
| --- | --- | --- |
| Native44636802418 / activation135958213204 | Feature head6e1ed1c, actual test-merge source863bc078435b8b29cdf1cb0c101fe4062a009190; convergence timeout after required-sink recovery | Late CP87/110 proofs; no native stage ranking |
| Native44631611463 | Test-merge sourcee0bd6a75110c136af6f0d0071c6da97d22220156; convergence timeout | Original failure retained; no all14 pass |
| Local ACK verifier host profile | Eight retained real ACK verifies:1.428410792s individual versus0.287962375s batch | Helper startup mechanics, not remaining native critical path |
| Focused core9c04211de14a4e66b56aaa47b1e0058b | 42 admissions/66 physical and logical outputs, selected core/mixed passed | Partial scope; not all14/native qualification |

Read-only verification found native44636802418 summary SHA-256
`daed8c6b6858b54d5c6f9e441b8baae7ac0efc5b5befb9cd0cb5560b4c1b63e7`
and native44631611463 summary
`e281326428478bf95ebbb5bc75eb5e46bd4bc3200de177b4038c7050c10503a1`.
Host profile report hash is
`0b0fe143610e53fecd9576b14e1bfd9d30246a73d5b4e57f7b192b27a67ff7c0`.
Raw private evidence remains in the original ignored cache and is never uploaded.

Production artifact055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d,
original producer51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d,
validatorf2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d,
and QA7b677b24bd39308a603e12f4e9c300d67d5b9cc2041a81103cb7481673361afd
are prior identities, not artifacts rebuilt or newly qualified by this delivery.

## Diagnostic implementation and local verification

Freeze commit8c42bf9 preceded implementation. Scoped monotonic inclusive spans
now cover the frozen stages plus existing job-health queries. Fixed-stage final
rows and latest/late predicate outcomes survive general sample saturation. The
existing public qualification summary carries the bounded report; no new network
query or per-record telemetry fsync is introduced. The frozen8/16 polling sizes,
120s cutoff, all14 required invocation and aggregate remain unchanged.

A dedicated additional manually selected `activation-diagnostic` job runs actual
`--scenario-group production-faults` with fresh setup and the same native settings.
It reports partial scope and cannot satisfy the required activation gate. To invoke,
dispatch existing `hygiene.yml` on this CI branch with `activation-diagnostic=true`;
the normal required jobs still run. PR trigger explicitly includes the owner-chosen
feature base. Every diagnostic bootstrap uses the same exact dependency-cache
hit guard as required consumers. No remote workflow dispatch was performed here.

Read-only independent review found two diagnostic defects: nonempty inspection
reported zero processed, and saturation could discard late truth. Both are fixed
with regressions. The inspection red actually observed0 instead of1; the late
report red lacked retained outcome data. The first full check also found three
cache consumer-count expectations needing the additional diagnostic consumer;
all guards still run, now for17 consumers. A test-fixture setup error (missing
publication) was corrected and is not a behavioral red.

On macOS ARM64, `uv run --locked python tools/dev.py check` passed the complete
applicable static/contract/hygiene workflow,412 Python tests (one class skipped:
exact retained lifecycle evaluator unavailable), Ruff/formatting and mypy for117
source files, plus adapter checks. Focused diagnostic/controller/oracle cases passed.
No Gradle build, Docker worker execution or native AMD64 qualification ran locally.
The local check is not evidence of real worker recovery or deadline performance.

Original dirty docs/tests and all eight protected handoff/doc hashes were checked
read-only against both preserved manifests and remained unchanged. No original
worktree/stash/deployment, container, volume or network was altered.

## Next evidence and remaining gates

Collect exact diagnostic PR-head native all14 results first; preserve the complete
failed attempt and inspect nested costs/cursors before naming a cause. The paired
101-wire signed-backlog8/128 mechanics experiment is frozen but not executed or
claimed by this diagnostic draft. Preserve fresh equivalent stores and test an
invalid historical signature separately. Select only a measured correction, then
qualify focused failure and all14 at its exact source/artifact identities. P15b61
remains Draft/parked. Owner acceptance/merge authorization and actual merged-main
verification remain separate; no throughput/HA/recorded AMD64 claim is made.

Local evidence hashes: final full-check log
`3d36e4089d1c5492890dd96fc4f8c79dae1075df137d8b5e2fa04b6ad7230129`;
initial failed full-check log
`9d0a50507fd190b2622dd856578944f9999da5a691a06d3ed1e9d3b032b68ebb`;
inspection regression red
`1c6d992537a0f222f0aad3ffafc1076f815001c691be9ddf6bfe1e35331cf4eb`;
saturation regression red
`621e297b168a76874fcf30af784f6b3ff294cbeb9cce928ec1b2e0b06539f849`.
A subsequent documentation-only check found one missing table-cell space; it was
corrected, with failed log retained as `ci01-doc-final.log` in this checkout's cache.

## Native diagnostic run44641731135 — measured failure

PR head079e969f16ec0cce39ac2668400fc9669cef3128, actual test-merge source
9737e8ac7ab13667c636156e784ead629bc4770d, activation135975023394,
attempt4d02c87ba0f340ad8eb3e9a7504ab62f. Summary SHA-256
`047a50a6000e18ea0e55c43869f1c440db70892cfce84aac21b220931072616e`;
original artifact ZIP
`4e0b38d6c2e22efcbd476a1312495cf10da280a890e96fc8ee6698dcc8f8a114`.
Private original report, logs, ZIP and parent's window analysis remain read-only.
Both implementation analysis and independent read-only reviewer reproduced every
window count/duration from the actual samples; no samples were dropped.

Core, mixed, uncertainty, replacement, broker outage and required-sink failure
passed. Pressure B convergence failed after95 admissions/75 outputs. Original
window start1,002,551,306,180ns, deadline1,122,551,306,180ns,
last end1,129,076,592,095ns:126.525285915s elapsed,6.525285915s overrun.
All eight predicates were false, consuming cursor262→326. Only worker20 current
CP145 joined; worker21 still awaited its authenticated current prefix, with
completion candidates171/174 retained. This is not a claim about arrival rate.

| Measured stage | Calls | Seconds | Attribution |
| --- | --- | --- | --- |
| Observe | 8 | 96.640740600 | Direct predicate child |
| Candidate capture | 16 | 24.153400716 | Direct predicate child |
| Job health | 16 | 1.380357525 | Direct predicate child |
| Evidence join | 8 | 0.847009391 | Direct predicate child |
| Kafka drain | 8 | 32.048344314 | Nested in observe |
| Kafka commit | 8 | 30.377200105 | Nested in observe |
| Signature batch | 8 | 4.144503252 | Nested in observe |
| ACK journal | 64 | 7.518903076 | Nested in observe |
| Cursor journal | 64 | 7.529660034 | Nested in observe |
| Load/replay | 41 | 22.893987030 | Overlaps inclusive parents; never add to them |

Direct children sum123.021508232s versus123.024304321s total predicates; sleeps
account for most remaining window time. Repeated drain/commit helper round trips
are the dominant measured combined category. Their internal startup/connection
shares remain unseparated. The correction amortizes these calls using an existing
bound, rather than changing resource ceilings, timeouts or accepted proofs.

## Controlled mechanics and implementation continuation

The experiment uses unchanged hash-verified production055a, producer51a,
QA7b677 and validatorf2 artifacts copied into this checkout's ignored cache. No
JAR was rebuilt or changed. Fresh Kafka-only fixtures register an actual owned
worker key, publish A then B through the normal candidate/controller path, and
sign100 old distinct-CP ACKs plus one current ACK using the existing Java signer.
A pinned Kafka console producer publishes the frozen prefix and exits before any
timed trial. Both sizes start from byte-identical private controller snapshots,
explicit offset0 and the same immutable topic/end101; no live worker producer.
One separate fixture corrupts only historical signature50. Every normal schema,
registration, signature, ACK identity, durable prefix and commit rule executes.
Generated ACKs never populate completed-checkpoint evidence.

Initial valid attempt2f701f75831c4cd4b2a238b1e029173c checked101 signatures and
records in both trials, accepted101/rejected0 and ended cursor101 with matching
semantic hashes. Bound8 took68.795265333s in13 rounds;128 took12.192873666s in
one. This first harness version verified prefix state on commit and reopened at
completion. The final harness additionally replays durable journal/ACK files in
an independent state object before every commit, under the already-held store
lock, and reruns the valid pair below. Do not transfer the first timings to it.

Invalid-signature attemptb93155e2316e47bb876fb589437331b6 used that stronger
precommit replay guard:8 took69.816809334s/13 rounds;128 took12.903929083s/one.
Both checked101 signatures/records, accepted100, rejected exactly historical
position50, ended cursor101 and reopened to identical semantic results. Both met
120s locally; neither run is a manufactured deadline red or native improvement.
The fixed order leaves order/warm-cache effects uncontrolled.

The finite-prefix regression was captured red on8: the current ACK beyond the
historical prefix was absent and convergence could not discharge. It passes at128
with the exact pre-drain current CP proof; an all-historical prefix remains unable
to discharge it. Existing changed-context/eviction/private-file/signature-failure
and strict late-truth tests remain mandatory. Independent correction review found
secondary-metrics-write exception masking and stale failure counters after durable
cursor advancement; both are corrected, with the original exception preserved and
final actual state captured even if commit fails.

Setup failures are retained separately:064551d1747e4733996fbc847f39d4bd lacked
the local logging dependency before setup;477e0f2caaf7465fbf2cabb2c03fb491 hit
Docker's fully subnetted address pools before deployment. The initial descriptor
copy script encountered the existing wrapped-config format and was corrected.
These are setup errors, not behavioral reds. Complete network/stopped-container
inspections were retained before retiring exactly three verified empty networks
from stopped attempt9c04211de14a4e66. No container, volume or source evidence was
deleted. Original root files, deployments, dirty docs/tests and handoffs stay intact.

The final valid-pair replay used byte-identical frozen wires/initial stores from
attempt2f701f75831c4cd4b2a238b1e029173c, fresh clone roots and the stronger
precommit replay guard. Bound8 took69.872175291s/13 rounds;128 took12.602132834s/
one. Both checked101 records/signatures, accepted101/rejected0, ended cursor101
and had identical semantic hashes. Report source hashes for the runtime,
qualifier and mechanics module match the current correction files. Final valid
report SHA-256 is
`6a5c2b40d120684ffc0f8293a756eb8bc21d59dc10dc4900e67acaade0ea6d1a`.
Negative attempt summary SHA-256 is
`92babc1975d1a017c248d7281f052b92a00619b9e7ee579a0e4ae537ee2f75c5`;
its executable checks precede the failure-reporting-only refinements, and retain
their actual source hashes. Both cases remain local ARM64 mechanics, with fixed
trial order, no live worker and no native performance claim.

Final applicable `tools/dev.py check` passed442 Python tests with no skips,
all contract/repository/secret/workflow checks, Ruff/formatting and mypy for119
files plus adapter checks. The copied hash-verified original evaluator allowed
the previously unavailable lifecycle class to run. The first correction check
passed442 tests then failed one formatting check; formatting was corrected and
the full command rerun successfully. The prior focused run also found three old
8-record/mock-step assumptions requiring explicit128/additional-step expectations;
the corrected52-case focused suite passed. No behavioral expectation was derived
from evaluator output. No Gradle/JAR build or native AMD64 qualification ran here.

Complete metadata was preserved before retiring the two new, stopped, empty
mechanics networks to make room for focused real worker qualification. Their
containers, volumes, private wires/keys and original snapshots remain retained.
Protected root dirty docs/tests and eight handoff/doc hashes remain unchanged.
The optional native mechanics report preserves failure-stage state and counts,
and secondary report persistence cannot replace an original experiment error.

## Focused actual recovery on corrected source

Local ARM64 attempt39207cdc6840416f9e42d759f64dc003 passed all four selected
`production-faults` scenarios: publisher uncertainty, registered replacement,
broker outage and required-sink failure. Its result is `partial_passed`,
`full_gate:false`:3 actual journal admissions,9 logical/physical outputs, no
unexpected job/oracle failures, no diagnostic drops and all owned runtime stopped.
At least one real observe consumed27 ACKs through the new128 bound. This is
actual selected worker recovery, separate from generated101-wire mechanics; the
ten remaining mandatory scenarios and native AMD64 benefit are not established.

Command used the existing qualifier with `--scenario-group production-faults`,
`--skip-build`, explicit verified runtime/probe hashes and copied producer/
validator artifacts. No JAR test/build is claimed for this attempt. Runtime055a,
producer51a, QA7b677 and validator packetf2 were unchanged; local validator image
was `sha256:a1dc0587e767d537d8488ff20ce1b50c47ae160fa34a4eb1f319bea011cfc827`.
Working source was079e969 plus this tracked correction; runtime, qualifier and
mechanics module source hashes in its report match the final correction files.
Summary SHA-256 is
`9d545a2c8e13cdd743d78590c1598383cffed91b702be2fdd0f5166350fec586`.
Full static-check log SHA-256 is
`7f26f1eee6ef53211f98f262a86a517fd5a541b94e7f971cec21b36ab1bf6e8f`.
Finite-prefix behavioral red log SHA-256 is
`91eb078e5700b40a75d22a8efff18bb57e6f54ffe8c9c7e4c9ec700368e472e2`.

The next pushed CI-only correction must receive exact native all14 qualification.
Dispatch optional `activation-diagnostic=true` on the same branch/head to collect
native signed-backlog pairs and focused production faults; default all14 still
runs. Preserve both old failed runs and any new failure with source/artifact
identities. Do not claim native benefit or complete CI-01 from local passes or
composed partial cases. Parent owns the existing PR watch; the child never watches.

## c42 native outcomes — ACK correction supported, CI still blocked

PR run44648419237 passed every applicable job and aggregate, with six deliberate
opt-in skips. Activation used test-merge15332998e208bab606be2c93e59563147bf4f100,
attempt5fd3de26f01e4c96b3d80848b09e8dff: all14 actual cases passed,
103 admissions,232 logical/233 physical outputs and owned runtime stopped.
Summary SHA-256:
`cd7fa04bc2b7124837b8633d3e38f207370ba254887052b87d91b862b5eb7fad`;
ZIP `c26df09d00c2c7b1cd3ca6b3fa73950a991facb631644035e60fbe3ef6c3b14b`.

Same-head dispatch44648665426 used direct sourcec42ac20525fa31bda6fe2d4d6bc3ea3877712ed9.
All recorded source hashes, runtime055a and QA7b matched the PR pass. Activation
job135998510608 failed `lifecycle_oracle_unexpected_event`, attempt
643375091b0a485381bed03e1c82e286:101 admissions,222 logical/226 physical outputs,
eight cases passed through pressure, then open-group closure failed. Owned runtime
stopped; no prior unexpected job/query/oracle-helper failure explains the strict
semantic failure. Summary SHA-256:
`1f0b44480518bb8087a429bd7a316c04ee24c8600ee83e8813efa7dcfa6a2018`;
ZIP `3a47af368c58725f9fafb5203aff296de3d83144d745d0ef857fabb2f958477f`.
Both outcomes remain retained; one green run does not establish CI stability.

The same dispatch's dedicated diagnostic passed both native101-wire pairs. Each
size checked every signature/record and durable prefix through101. Valid had
101 accepted/0 rejected; invalid had100 accepted/1 rejected. Bound8 elapsed
119.889s valid and117.461s invalid;128 elapsed19.614s and19.655s. Fixed order and
warm-cache caveats remain; these are generated transport mechanics. Dedicated
actual production-faults attempt900f8ca5565a474facffb7bb3677ff2c passed all four
selected cases,3 admissions/9 outputs, owned runtime stopped. Its summary hash:
`1724de1b9c4a900a4e91d522679d42be0cd7d6470c7eaaf74a6852c6542f7139`;
ZIP `524303ba611ee24ae928aa43ca766687438e80f6252445d2770592606e06ed82`.
The bounded ACK startup/call-count correction is now supported by native evidence;
these results do not discharge the distinct open-group or search failures.

## Open-group scheduling failure — observed critical path

The retained safe actual-output summary identifies controlled run
715b0000-0000-4000-8000-000000000205: five-member tagged output plus eligible
manifest closed by `timeout`, followed by the sixth EOE receipt. The frozen expected
six-member `source_boundary` and literal A closure remain mandatory. Actual
COMPLETED worker21 CP149 has exactly five B members, opened1795136928063 and
deadline1795136958063 (original30000ms). No raw decoded records are copied into
this ledger. Mixed-worker proof passed28.858s; that does not qualify this case.

An independent read-only agent reproduced these regions from native diagnostics
and source ordering (seconds relative to the report's monotonic origin):

| Region | Start | End | Duration |
| --- | --- | --- | --- |
| Five-member admission | 1056.231601 | 1064.035414 | 7.803813 |
| Completed open-group proof wait | 1064.035513 | 1071.756574 | 7.721061 |
| Rollback publication | 1071.845166 | 1094.306234 | 22.461068 |
| Last/EOE admission | 1094.306638 | 1101.460877 | 7.154239 |

Three publication network spans consumed5.553641s,5.974037s and5.524490s,
17.052168s total, corresponding by source order to manifest, plan and control.
Publication plus last admission alone consume at least29.615306431s (unspanned
store/caller work is omitted); proof collection already
aged the real30s group. The monotonic trace does not precisely map worker wall
`opened` to controller origin, so no invented exact remaining-age value is given.
This is a harness scheduling race, not renewed ACK convergence. Existing locks
and adopted-pending A prevent callback admission; no unlock/guard bypass is allowed.
A reviewed decision packet is in [the design](ci-01-design.md#open-group-deadline-decision-packet).

## Separate search-CI triage — unresolved raw cause

Dispatch search job135998510906 failed at phase`blocked_failure_publication`,
category`writer_helper_failure-policy_writer_failed_IllegalStateException`.
Read-only independent triage locates the failure at healthy-policy restoration
in search_writer_qualification.py581, after block, BACKPRESSURED and uncommitted
position assertions completed. Subsequent accounting and later cases did not run.
The source has an explicit `IllegalStateException("fault_readback")` for an immediate
Kafka policy-readback mismatch, but that fixed category is not allowlisted and the
retained report lacks the requested/observed pair and throw location. It remains
a hypothesis, not a proven raw cause. No retry, waiver or P13 semantic change is made.

Only a321-byte sanitized report was uploaded; helper stderr was reduced to a
category/class, helper logging disabled and runtime teardown removed the original
cause. A separate search-CI diagnostic item/PR is recommended to retain bounded
policy intent/alter/readback/throw-phase evidence. This CI-01 PR remains activation
only; no separate issue/PR has been created without parent scope coordination.
Summary hash `87db825f50426d6f626bec686d21b51f75e09e9478334023ff40556e6d19a3ef`;
job log `60809ce3483106a4dcb7bc2b9f49a9b2f8d5e0fbe61085a497dd0a8da46bdc43`;
ZIP `3205474aec799d3c8f644a8ef7afe112033dff4035b56484fa800e2f0ce7d4a6`.
PR63 remains Draft and CI-01 blocked despite the first native pass.

A single final-state read of dispatch44648665426 found it completed with failure:
integration-verification succeeded; activation and search failed; the dedicated
diagnostic succeeded; required-checks failed. No PR wait/poll loop or unchanged
rerun was used. Retained final run metadata SHA-256:
`c7b4ee20c5ccb7fe2aba53d89b8b9180b6396ca1b75b2fdc32746c331538fcf2`.

The next local freeze records the newly observed deadline case and concrete
publication-boundary options before implementation. This additional commit is
required after published c42 native evidence; existing published commits are not
rewritten to meet the normal1–3-commit target. No option is accepted merely by
recording it. No runtime/capability claim follows from this documentation update.

Independent read-only review of the concrete options confirmed A changes an opt-in
controller boundary and needs owner agreement. The packet now specifies opaque
capability lifecycle, prior-B CAS/resulting-A-intent binding, actual worker
artifact-cursor/rejection readiness outside the30s window, retained-availability
negative coverage, and request-bound (not cryptographic) QA result wording. No
option has been implemented or treated as accepted. All local heavy tools remain
idle while the owner chooses the boundary.

## Owner-approved A implementation

The owner explicitly selected A after local freeze4339ff4; the stale pending-choice
notice is not the current authorization. [ADR 0015](decisions/0015-qualification-artifact-preparation.md)
records the accepted CI-only boundary. Approval does not authorize merge/release,
P15 resumption, alternative B or P13 search changes.

The scope validates staged closure/proposal/member/broker/context/CAS under normal
locks, signs/transfers the exact existing artifact packets, then releases locks
between completed operations. It creates no A adoption/control. Every worker must
supply actual COMPLETED artifact-cursor/rejection/B-selection readiness before
five-record admission. Actual existing worker_inventory results alone feed the
internal proof observations. The later exact-five-B proof authorizes only the
opaque instance token; publication rechecks context/CAS/bytes and binds the exact
new A intent/revision/command before durable adoption. Only duplicate artifact
transfers are omitted. Normal control signing/send/receipt and guarded EOE
admission remain ordinary; the six-member literal A/source_boundary oracle stays.

Single-use/failure/finally invalidation includes early API errors and successful
context-mutating operations. Default publication without a scope still sends
artifacts then control. No persistent controller format, worker wire/state, QA JAR,
clock or resource ceiling changes. Private original wires and attempt metadata
are durable before any preparation send; actual receipts follow acknowledgments.
Original baseline/readiness proofs are retained privately with bounded64-proof/
32MiB evidence storage, below existing finite storage bounds. No new private
preparation directory is included in uploaded artifact globs. Fixed monotonic
preparation/readiness/authorization/publication/admission/proof spans add no
logging queries; readiness queries establish the newly required correctness fact.

Independent guard implementation/review found and corrected None-token omission,
missing explicit resulting-intent binding and early-error invalidation gaps.
The three early-error regressions actually failed by permitting later reuse, then
passed after complete API-boundary invalidation. Explicit intent replacement,
partial-send uncertainty and unavailable/truncated-prefix transport doubles remain
negative cases, not real Kafka truncation qualification. Twenty-seven guard cases
pass with real controller proof plumbing and explicit transport/crypto doubles;
they do not claim real worker execution. No missing-API/setup error is called red.

First actual focused attempt3c3d31116024412a98cf2ef11f115924 stopped fail-closed
at artifact readiness, before any case admission/output:0 admissions/0 outputs,
owned runtime stopped. Summary hash:
`5749a362690eb74792281023fb4327c5dbfa3790ad82925b7013aeae0b4d86c9`.
The existing checkpoints() API journals rolling completed_restore_paths via start
records during ordinary observation. Comparing the entire job record incorrectly
classified that metadata progress as a job change. A genuine focused unit red
captured it; identity now excludes only completed_restore_paths while retaining
all other job fields, including actual job/incarnation/state. Changed-job guards
still fail. The next fresh attempt uses that demonstrated correction; this is not
an unchanged rerun-to-green. All failed evidence and private prepared wires remain.

Complete inspections preceded retirement of only the three verified empty,
stopped-owned networks from prior local attempt39207 and then the failed3c3d
attempt to free exhausted Docker pools. No container, volume, original deployment,
raw evidence or original-root document/stash was deleted or changed.

## A focused actual qualification and final local checks

Fresh corrected ARM64 attempta86ebb18120e4c918232bb5b5807c460 passed the selected
actual `open-group` case:6 admissions,9 logical/physical outputs,
`partial_passed`, `full_gate:false`, no unexpected job/oracle failures, all owned
runtime stopped. Both workers supplied actual COMPLETED artifact readiness
(worker20 CP13, worker21 CP9) before the first-five admission. Worker21 CP11 then
proved exactly five B members and the original30000ms deadline. Final strict
oracle checks required all six exact members, eligible source_boundary, tagged/
detection output and literal A closure. Neither readiness nor publication ACK was
substituted for actual application/closure evidence.

The final publication contained one network helper (control); local publication
was2.879586584s and completed-proof-to-EOE-return5.533703041s. Preparation6.241389917s
and readiness polling occurred before the30s group. These are local ARM64 timing
observations, not a native speedup comparison or capacity claim. Original20s proof
wait and120s convergence guard remained. Runtime, qualifier and preparation module
hashes in this report match the final implementation files. Source was4339ff4 plus
the tracked implementation; no pass is transferred to a different commit by fiat.
Runtime055a, producer51a, QA7b677 and validator packetf2 remain unchanged; explicit
`--skip-build` hashes were verified. No Gradle/JAR build was run locally.

Summary SHA-256:
`faa5fe2e9638856f352cdf35b60978f881bdbcbebfef882bd6bed49c25f7dbc6`;
run log `2b28efdc27004d6ecb101bc823e99cd24d1eee3d8e9dc7777f84bd0e289fc5eb`.
Final `tools/dev.py check` passed469 Python tests with no skips, contract/hygiene/
secret/workflow checks, Ruff/formatting and mypy for121 source files, plus adapter
checks. Full log hash:
`3d3e580f560855b476b6ffb2898315a078ec623c647b848dc4e472b2f1768f80`.
The27 preparation guard cases include simulated truncation/unavailability,
per-worker readiness, member/context/CAS/intent changes, private token misuse,
partial/uncertain send retention, ordinary metadata progression and cleanup.
An intermediate retention assertion incorrectly expected no first receipt when
the injected uncertainty occurred on the second send; it was corrected to require
first receipt plus second original wire/attempt and no fabricated second receipt.
It is not a runtime red. Guard suite hash:
`b21a7f7eaa43f4b76f6261a15fc56e13321e13229ef30dd344121eafb89ec491`.
Early-error red hash:
`0b66a1e7e18ecd491ef059a93992795512620679bfe55eec62d55ff86ce2b122`;
checkpoint-metadata red:
`9d35400cbab6aa88c6be649cfa0ab090e552efdd92dcd1aece7571a574fb5156`.

The next exact-head native all14 and repeat optional diagnostic are mandatory.
The latter now additionally runs fresh actual open-group qualification after both
signed-backlog cases and production faults; default all14/aggregate are unchanged.
PR63 remains Draft; same-head historical activation/search failures are retained,
search diagnostics remain separate, and CI stability/review readiness are unclaimed.
Parent owns native evidence collection/watch after push; the child never watches.
