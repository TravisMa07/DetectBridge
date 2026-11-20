# CI-01 qualification ledger

Current status: native diagnosis supports a bounded128 qualification-read correction;
local signed mechanics and independent review support it. Native correction
qualification remains open. Earlier diagnostic-only gates below are historical.

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
