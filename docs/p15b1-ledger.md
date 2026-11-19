# P15b1 worker runtime qualification ledger

Status: actual ARM64 attempt12 passed all fourteen required bounded runtime
scenarios on its exact recorded source and unchanged production artifacts. Later
qualification-harness refinements have static and focused runtime coverage. Initial
native PR CI failed in the mixed-worker pause; its bounded scheduling correction
awaits a new full native run. No merge, owner acceptance, P15b2 archive/replay or complete
P15/P16 gate is established. Original private evidence and build artifacts
remain ignored locally. Neither review nor a component test substitutes for an
actual Kafka/Flink scenario.

## Prerequisites and freezes

The owner accepted bounded P14 completion. P15a PR #57 was subsequently merged
with explicit authorization as `f44403e2975db46554c9c5033f87886d880c4087`.
Actual merged-main push run44472864062 attempt1 passed all nineteen applicable
jobs and required-checks on that exact commit; five opt-in jobs skipped explicitly.
The [P15a ledger](p15a-ledger.md) records original run/report/log hashes.

The runtime design, closed contracts and independently authored source/decision/
identity expectations were frozen in `0a41ee4900fb3430d4fff98b9fd9b884c383b4f1`
before production code. The owner retained S12's validly signed forged-AST rejection
requirement. The separately frozen compiler boundary is
`943333c515207a479c152ab646e2c3642c69c9f9`, before its implementation. It pins an
isolated worker-initiated compiler artifact rather than weakening that expectation.
See [runtime design](p15b-design.md), [validator addendum](p15b-validator-design.md),
[independent matrix](p15b-expectations.md) and [operator guide](worker-activation.md).

Three coordinated implementation agents owned disjoint Java runtime, Python
controller and independent oracle/qualifier file sets. Primary owned integration,
CI, the validator service/build artifact and evidence. Independent cross-review
found and corrected publication retry durability, uncertain launch incarnation reuse,
pending-policy ownership, checkpoint-ack isolation, malformed-input scope handling,
canonical helper public keys and overly broad fault/coverage assertions. Original
producer/replay source and identities remain unchanged.

## Component evidence

On dirty source based on `943333c`, the latest offline Java suite passes29 cases,
with zero failures, errors or skips. It uses
actual original source adapters/evaluator for A→B→A, queued mixed-attribution restore,
checkpoint abort isolation, signed forged AST rejection through a real local Unix
socket and unchanged compiler, protocol boundaries, chunk conflict/reordering,
revision ordering, private proof recovery and malformed-input quarantine.
The local socket peer is component evidence, separate from the Docker sidecar.

| Artifact or report | SHA-256 |
| --- | --- |
| Production lifecycle JAR | `055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d` |
| Separate qualification probe JAR | `2dbec9feebaed16a676fa0252b4033f0feb5942be2b20947b8751a8eab286d6e` |
| Original provided producer JAR | `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d` |
| Latest29-case test XML | `0edac49af8a5d64cba5c3b0faaf973638897c62b7704e67d457846a4ae507fcf` |
| Latest successful offline build log | `d919b0b3a8e966e547558a0402a0be11ef192cd013b4423323a3fb7e69beb991` |
| Reader source at provisional audit | `2881c5b1cd6f1c56f4a10fdcd8911d7eba3d24d107149c24236d07af4540e146` |
| Probe source at provisional audit | `f1a44deba143be291bacc08843a1aff7fa3c80f50b00159c35eac1c182b035bb` |

The latest XML is `packages/lifecycle-job/build/test-results/test/TEST-io.detectbridge.integration.LifecycleTest.xml`;
its timestamp is2026-11-19T17:39:03.058Z. The successful build log is
`packages/lifecycle-job/build/after-snapshot-build-final.log`; it reports23
applicable tasks, six executed and17 up-to-date. These are component/build facts,
not a full runtime pass. Source remains dirty/uncommitted; exact per-attempt source
manifests and actual artifact hashes, rather than a future commit SHA, own runtime
attribution.

Earlier28-case evidence remains historical: production `0a15e9bb...`, probe
`00db4ea4...`, XML `849719e7a5d88c5daa3f65f3c8b863d52864f4c3aaf099a7cd0b2e8beeb20699`,
original captured build log `686574650a67c841dd0c3b3ed57d9783215a8234f3f0d7d00225d0c5b959d71f`,
and subsequent probe code-source-guard build
`ef1699840510bd11ba7a9a7ba06a191e6a9feb3e631d1df224836c6c846724d3`.
No passing result transfers from those artifacts to the latest055a/2dbe pair.

Static binary inspection proves no class-name overlap between new and original
JARs, no probe in the production JAR, and the exact original producer hash.
Actual code-source and same-classloader startup guards are separately exercised
by runtime qualification. Java lock reconciliation adds usages of the same67
existing reviewed coordinates, with no new coordinate/version or remediation claim.

The genuine restore red is retained at
`packages/lifecycle-job/build/evidence/red-restore-20261119T072806/`:
test XML `3121a9287e933cb29a334512f1c3047cba023856500735e9111a3fcc5041642f`,
source manifest `bd28222dabb16472aaaa4b3684a6cd0c7333741239a2bb13fbaa34e20323deb8`.
A valid checkpoint failed restoration because parsed integer-node representation
differed from constructed metadata despite identical canonical bytes. Canonical
comparison corrected it. The genuine S12 red is retained under
`build/evidence/red-s12-signed-forged-ast/` in the same module:
XML `ad8a55deccdd4a00d39fe4c497421d105a65c4706fe7e421379de3a4bd67e3e4`,
source manifest `fab8ed0a0d4a1b9aa9efc3b01e0458a5f660f83ebbab2aba6c6d66501b772096`.
Actual A worked first; validly signed self-rehashed B with unchanged Bob YAML and
Alice AST wrongly replaced A (expected revision1, observed2). The independent
worker compiler comparison corrects this. Initial core A/B semantics passed first
time and are green-only evidence; setup/compiler failures are not semantic reds.

The latest targeted Python sets comprise57 cases: controller29, independent
oracle19, real compiler/framed-socket service6 and gate3. Controller mechanics use
explicitly labeled transport/signing doubles; these remain component evidence.
The pre-advisory aggregate captured55 passing cases in3.209s at
`.cache/p15b-prerequisites/focused-before-attempt6.log`, SHA-256
`f24b750778a7ad36fa0c58bd927220066071ed25bc66f6da0600d9109b2371cb`;
the two advisory-inventory cases passed separately afterward.

The final repository check before attempt6 passed376 Python tests in35.010s,
Ruff/static checks, formatting and mypy for115 source files. Its retained
`.cache/lifecycle-runtime-qualification/static-check-2.log` SHA-256 is
`fcdf2c85da92516ff3169d7a8640192b124f990ce60de265e5d414b03a579623`.
These supersede the earlier forty-case focused and357-case repository checks
for that source snapshot. They do not establish actual legacy-consumer runtime,
native AMD64 qualification or a complete Kafka/Flink scenario pass.

The broader `uv run --locked python tools/dev.py java` check subsequently passed
all selected Java consumers, artifact checks and adapter recording tests
(`java-consumers-final.log`, SHA-256
`c04697226b2f14af87b35efeb9ea9f4d9bbed02ef37b334a068ef949e37db8e6`).
The new production/probe JAR identities remained unchanged. A separate actual
Docker broker-resume check restarted attempt6's stopped owned broker, verified
the unchanged cluster/four shared topics/two worker-input topic identities and
stopped it again, with no source admission or worker restart. Its report
`broker-resume-actual.json` has SHA-256
`80316dc907be16edaa854aeef3648e51ed9a8bcfe999ac3237643c4028154a79`;
the log has SHA-256
`772280ff1085415b0879591ede725c1fdd217cf5d220effd8b27388cf754ebd5`.
This supplements the controller's resume regression; it does not establish the
full worker-runtime gate.

After the scheduling/barrier regressions, `tools/dev.py check` passed378 Python
tests, all static checks, Ruff/formatting and mypy over115 source files.
`static-check-3.log` SHA-256 is
`22e50d1e42ed22b38e021738d24941bf59382fa23a02ed02bbe1185cebccfc8f`.
The final focused controller/oracle/validator/CI suite passes59 tests
(`focused-before-attempt7.log` under `.cache/p15b-prerequisites/`). These remain
component/static evidence, separate from attempt7's actual runtime results.

## Retained failed attempts

Validator build1 failed hash enforcement because an export incorrectly pruned
`types-PyYAML`, which pySigma itself requires. The correction retains that existing
locked dependency. No dependency version was changed and no runtime dependency
download is enabled. Original packet
`ae19d3164ac8d969dccbff9c7277febd3d3fdc8161e423c5522740516827dd54`,
build log `8b6e1f2122582eb56ab821d0924029d9d67a06a5edd340e717f1ec1118273ab3`
remain in `.cache/lifecycle-runtime-qualification/validator-build-1/`.

ARM64 runtime attempt `4458ca0be79741f8b6f96e669e4e4241` failed before admission
or scenario execution. The image copied the host's mode0600 packet as root, so
service UID9999 could not read `/opt/validator/artifact.tar` during verification.
The exact failed summary SHA is
`d05829b30ef5ad55041e0f8668c0ce22d985d4ec121acaa998807e9cc31af757`;
the subsequent isolated read-only diagnostic log SHA is
`e93d87d575bdbcfe26ce59b7c9a0aecf6e540baf56280c9c949f06b027614b6c`.
All fourteen scenarios remained unqualified and all owned containers stopped.
The correction makes the public packet mode0444 inside the image and adds an
actual service-UID/read-only installed-packet verification step to every image build.
This is startup evidence, never a successful activation or intended fault case.

One expanded Java test run also hit the macOS Unix-socket path limit in its temporary
test path. The original XML is retained under `build/evidence/bounds23-run1/`,
SHA `07f9b758095e84f2db836363f2b0fc8e79bfbc2249109a93d05d285fbb01039f`.
Shorter test paths corrected setup; this was not a behavioral red or a production
socket-path change.

Attempt2 `b97e1d563971427a8c41a95c7a60f4be` published A and submitted both jobs,
then failed in the first ACK read before source admission. Summary SHA
`8ceeff99d44cd83824ef37819459df64eb79e4e96419c0f03e40efb20c8d329c`.
A real Linux helper at UID501 lacks a passwd entry: the JDK's UnixSystem reports0
while the kernel and the nested helper output directory report501. The old JAR
rejects that correctly owned directory; the fixed JAR uses the kernel UID.
Exact nested-path negative/positive reports remain under
`packages/lifecycle-job/build/uid-helper-regression/nested-old/` and `nested-new/`,
with report hashes `0c74926e4445b31898cc5e2ee3c84e1465c4b0d1e8038efcc0f23d141a0203d6`
and `9fbaed32f1eef398333642fe4106ac4e97b57894d4c3a7e4a9c43280667e7660`.
Earlier incompatible-probe and mount-root experiments are retained separately and
do not establish the nested helper regression. Helpers now also return bounded
fixed operation/cause metadata and verify pinned Kafka namespaces before and after
read/commit operations. These helper probes are not worker-runtime qualification.

Attempt3 `642c06d2e0e64178865b5a92e2ad5f81` passed the helper boundary but both
jobs failed their first checkpoint, before source admission. Its summary SHA is
`81041d9002619f2291a56972142945aff96241f085147d8ed95f4a9a7b5f05a2`;
original exception document SHA
`155774acd564efe679189cef1fd4a4cd8f7ed9dec04bcede38366388a256df6e`.
The exact cause is `lifecycle_private_mode` at checkpoint storage reservation:
Flink's default process umask created files/directories looser than the frozen
0600/0700 contract. The correction sets inherited process umask0077 and keeps the
strict guard. This failure occurs before snapshot sealing or durable-ack creation.
All scenarios stayed unqualified and owned containers stopped. Convergence now
retains unexpected job/exception proof and fails promptly on irreversible FAILED
jobs; ordinary deadlines and process memory budgets were not increased.

## Later failed ARM64 runtime attempts

Attempt4 `9c1544ed54e24875b60005819e8013e9` remains failed. Its original summary
SHA-256 is `639b8b6b342bf7a36b42b95874f70f7d9f926643e3e91052822c771aa4399460`;
complete qualifier log SHA-256 is
`5be153e10585fb84610734308cbfd5373eae03240ab9ea9dff41a2cf87e68f9b`.
The summary accounts for14 admitted physical locations and22 logical outputs
before the failure, but records no completed required scenario. The original
helper failure has exit22 and exact stderr `curl: (22) The requested URL returned
error: 404` (stderr hash
`0fb219efe96c7b0a4962325763ebbe3324456de8ca7b7d1e71142d92a6d8eab2`).
The summary's category is `lifecycle_runtime_compose_failed`; retain this actual
query failure rather than inferring that an unavailable checkpoint was completed.

Attempt5 `079919e78fb548acab460c7b6e5dfb86` also remains failed. Its exact summary
SHA-256 is `4ce1ad614b2d230f635e0d33ae6be0c4963128d66bacf01438408bc60794d419`;
complete qualifier log SHA-256 is
`b4224867980c365e4d6733be5f82c299d93fb2a299094e6da3e8babd199bcf6a`.
On production `0a15e9bb80cab72bb5f16fdb0f73503e8a038ffcf5ce7bf1f6bf363085ae73e9`
and probe `00db4ea4d9fe446cb01f99f2257aafe72bd91c890b1d4316f5332d86d9e3040a`,
six named bounded scenarios passed before the later failure: core two-worker A→B→A,
mixed workers, publisher uncertainty, registered replacement, finite broker outage,
and actual required-sink rejection/recovery. The summary accounts for45 admitted
locations and75 logical/physical outputs. Core accounting is42 admissions and66
logical outputs across six isolated runs and effective revisions1–3. These are
partial results of this exact failed attempt, not full qualification or evidence
for another artifact.

The required-sink scenario preserves the actual
`org.apache.kafka.common.errors.RecordTooLargeException` REST exception document:
10,787 canonical JSON bytes, SHA-256
`3a0b8423804b37fa374dd837044b3b6389a0fc3cff8a84de46b709598b414b3e`.
This is a complete response-document representation, not a claim about HTTP framing.
Its original is under attempt5's `approved-fault-proofs/required-sink-failure.json`.
The later checkpoint-details query for checkpoint109 in job
`39839137c18afad817334376ae2f4c26` returned HTTP404/exit22. The summary retains its
query metadata and exact stderr hash above; it records no unexpected job failure.
All eight remaining required scenarios stayed unqualified, and owned runtime was
stopped. The absence of a query result is not proof of an abort callback, snapshot
completion or accepted checkpoint recovery.

Both attempts used validator packet
`f2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d`,
ARM64 validator image
`sha256:a1dc0587e767d537d8488ff20ce1b50c47ae160fa34a4eb1f319bea011cfc827`.
Original summaries remain in `.cache/lifecycle-runtime-qualification/attempts/<attempt>/summary.json`;
complete logs remain `runtime-attempt-4.log` and `runtime-attempt-5.log` in that
qualification root. Private helper outputs remain under their original work roots.
No failure or partial scenario is retroactively changed by a later correction.

## Interrupted attempt6 and checkpoint observation boundary

Attempt6 `4dcc0fa4c2c5493c8f9b962e76ee82bc` was launched with the latest production
`055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d` and probe
`2dbec9feebaed16a676fa0252b4033f0feb5942be2b20947b8751a8eab286d6e`. At this
provisional audit it was intentionally interrupted with SIGINT to tighten three
late-stage harness checks: require all five open-group members before rollback;
fence the worker and drain through a frozen ACK-topic end before accepting timeout
ACK absence; and start hostile-control inspection at the pre-injection end rather
than lifetime history. Production runtime source and artifacts remain unchanged;
no acceptance requirement or deadline was weakened. This is an interrupted
qualification, not a behavioral red or aggregate pass.

Its retained summary has status `failed`, sixteen admitted locations,27 logical/
physical outputs and one completed bounded scenario (`mixed_workers`). It records
`owned_runtime_stopped: true`, no query failures and no unexpected job failures.
The complete log ends in `KeyboardInterrupt`. Summary SHA-256 is
`4d64609fe7df757d69a861a299957e343e9aa48e105ca5406f400f7088d099d9`;
`runtime-attempt-6.log` SHA-256 is
`e91001b79dfe0c55cf512410ddc20729979e72ff78d08ed32533155537d72858`.
The report and source/artifact/platform identities remain under the attempt's own
original directory. The thirteen other required scenarios remain unqualified in
this attempt; attempt7 requires the corrected harness and separately retained
results. Cleanup is report evidence, not an independent no-container inventory.

The corrected deployment exposes each JobManager only on its worker's own internal
network; only the corresponding TaskManager joins the shared broker network. This
removes cross-cluster `jobmanager` DNS alias exposure without changing process
budgets. Checkpoint-query retry is now allowed only for an actual404 whose exact
requested ID is below the minimum retained ID in independently queried same-job
history. It preserves the failed query and waits for a fresh signed acknowledgment
and actual COMPLETED checkpoint; it never treats the unavailable old ID as complete.
Other query errors, changed jobs, empty/invalid history and unproven eviction fail.
This is a precise observation-race correction, not a generic runtime retry waiver.

The new timeout probe runs **after actual worker snapshot serialization**, recording
checkpoint ID, selected command and exact snapshot SHA-256. Bounded advisory
inventory can then demonstrate that the matching snapshot and durable-ack candidate
were constructed while the actual Flink checkpoint later expired/failed. Advisory
metadata is observation-only: it cannot authorize recovery or establish COMPLETED.
Only `worker_inventory` retains the separate actual COMPLETED-checkpoint guard.
The29-case component suite directly invokes abort handling and checks candidate
removal. A real timed-out snapshot and absence of a durable acknowledgment do not,
by themselves, prove that the task-side abort callback executed during the blocked
window. Keep those evidence claims separate in the eventual runtime record.

## Failed attempt7, release-marker correction and provisional attempt8

Attempt7 `e2fa0f627f2641f3b6592a4b6ad5e55c` failed closed with
`lifecycle_qualification_timeout_source_accounting`:95 physical source admissions
and75 logical/physical outputs. Six bounded scenarios passed before failure, the
same named core, mixed-worker, uncertainty, replacement, outage and required-sink
scenarios listed for attempt5. The pressure/release scenario and remaining required
scenarios did not pass. Exact summary SHA-256 is
`55f95be84f764d5f0f6be80df0b55bcf45b82ffd172db34559d4af8ebcc31e23`;
complete `runtime-attempt-7.log` SHA-256 is
`5735effe93a90fc9b437c08f41c60522238ccdc691edbcc5aeb07895ecaac88e`.
The summary reports owned runtime stopped and no unexpected job failures.

Two actual checkpoint110 queries returned404. Their independently retained
same-job histories had minimum IDs113 and111, respectively. The qualifier correctly
recorded `evicted_unproven_wait_for_fresh_signed_ack` and continued observation;
it did not infer that either missing checkpoint completed. These races were not
the terminal source-accounting failure. Actual approved required-sink REST evidence
remains10,789 canonical bytes, SHA-256
`59f82d71672ffeec78eab29be51e4a8df77705c1b4b44862d627f9454e209c56`.

A read-only diagnostic copied the original owned TaskManager's `/store/probes`
archive without changing its markers. Under
`.cache/lifecycle-runtime-work/e2fa0f627f2641f3b6592a4b6ad5e55c/qualification-private-evidence/`,
`probes-original.tar` SHA-256 is
`d9ebe2f7e9c52386921c7cef7fb986ba52e0671b2f5e61ec58db2f7d542ff745`;
`probe-modes.json` SHA-256 is
`8a64e5ddf2781ae5d5bb0fbf1a885da95c9741c45e80e38a92285a2700212d83`.
The actual empty `release` file is UID/GID9999, mode0644, within two UID9999
mode0700 directories. The previous Docker-exec `touch` inherited umask022 rather
than the process entrypoint's077. This conflicts with the worker's strict private
file guard on its next snapshot. The retained archive plus source support that
causal inference; an exact originating REST guard-exception message was not
retained, and is not claimed as directly observed.

The controller correction executes Bash with explicit umask077 and exclusive
noclobber creation. Retry accepts only an empty, regular, nonsymlink, single-link
mode0600 file owned by the current UID. It rejects unsafe existing markers without
chmod, replacement or content repair. The genuine pre-fix regression executes the
captured compose-exec payload locally under022 and observes0644 instead of0600.
Its retained `.cache/p15b-prerequisites/probe-release-private-red.log` SHA-256 is
`3c1f8533d82531fc2e545aeab754adba08d9367270d5adffd08d73e1f2fa599b`.
The two-case focused green log SHA-256 is
`7c9e74def8f68fd916efcaf2c1a6ba90fb979e7a9920df6bd8beb0a1a7e60916`;
the complete31-case controller log SHA-256 is
`34db2c28da8969a1a66c95471f534aec2de87ea690c68ba07b3edc17ac1db415`.
Both are adjacent `probe-release-private-green.log` and
`probe-release-controller-final.log`. Ruff and diff checks pass for these changes.
The macOS test uses native BSD stat metadata through a GNU-format adapter; it does
not claim Linux execution.

The separate actual Linux smoke executes the corrected payload at UID9999 in an
isolated pinned Flink container, without broker, worker-key or stored-evidence
mounts. It proves fresh0600, accepted existing retry and unchanged rejection of an
unsafe0644 marker. `.cache/lifecycle-runtime-qualification/probe-release-linux.json`
SHA-256 is `cb32badfdf60a3fb365ffbecea8347d2e11de42a3062d6225fe23546c31e7ee5`;
its adjacent `.log` SHA-256 is
`eb350023d422b146b1a3b21498c96c670f20c3ae4835b6c0260812e6dd12472d`.
The report pins the actual script SHA-256
`319c76b51b19911342d014161cecf1a673d1f9f05233dededd97e610cb2ead6c`.
This is controller-boundary evidence, not a completed pressure/recovery scenario.

Attempt8 `429b1974810148688624e7ea0b078d6b` failed closed with
`lifecycle_qualification_timeout_group_closure_apply`. Exact summary SHA-256 is
`09376c74b94a52d31810a8a2084561e76352fa5b1e67ce0b699b1f63c6b7de62`;
`runtime-attempt-8.log` SHA-256 is
`0855b626e41a3422a6b2dca591fc6e436992b43581d3d1360d1528db11eaadd9`.
Eight named bounded scenarios passed: the earlier six plus finite backpressure
and old-outbox/new-selection attribution. Finite pressure accounts for50 source
locations and142 logical outputs at the unchanged128-intent bound. The whole
failed attempt accounts for217 logical/physical outputs. Its durable controller journal contains100 `admit` records, each with an actual
broker receipt. The summary's independent oracle receipt count is95: the last
five group-member admissions preceded the failed closure barrier, and their
post-closure `add_case` accounting did not execute. These five broker-acknowledged
admissions are not claimed source-complete. The exact100-versus95 accounting
scopes remain distinct. Six required scenarios remain
unqualified; owned runtime is reported stopped. No full pass is claimed.

After fencing, the actual retained ACK tail from321 through frozen end343 contains
22 records, including revision8 observed/applied/durable phases for both workers.
The public diagnostic `.cache/lifecycle-runtime-qualification/attempt8-ack-diagnostic.log`
SHA-256 is `dacb1a16daeef0ac60c7ebbcb4e4dccd938fda206f75662b987b11561685ce7f`.
Complete original records remain privately at the attempt work root's
`qualification-private-evidence/ack-tail-after-group-timeout.json`, SHA-256
`0f974bf1ab17f9e0b3591eafe61bac3979439b06be23e7175c9905c98b1c6680`.
This proves those ACKs existed by the frozen end, without establishing the exact
policy-application timestamp during the earlier failed barrier.

Independent review accepted a stronger direct closure precondition: within the
existing15-second window, require an actual independently COMPLETED checkpoint
inventory selecting new A while retaining the same exact five open-group member
IDs. Prepare the proposal before admitting members, publish after proving the
open group, and admit the end-of-evidence record immediately after that inventory
proof; signed ACK convergence follows outside this critical closure window. The
harness correction is being implemented separately and does not retroactively
qualify attempt8. No production artifact, deadline, resource or semantic limit
changes. The production055a/probe2dbe/original51 JARs and validator packet/image
remain unchanged; completed Java component and legacy-consumer checks retain their
original exact-artifact scope.

The subsequent full repository static check passed381 Python tests in34.604s,
Ruff/static checks, formatting and mypy for115 source files. Exact retained
`.cache/lifecycle-runtime-qualification/static-check-4.log` SHA-256 is
`961982208f830ce39f651fa6fb2aa028b6534264c9373e6f5a2c2b57f49c4680`.
The62-case focused pre-attempt8 suite passed in3.586s;
`.cache/p15b-prerequisites/focused-before-attempt8.log` SHA-256 is
`ce54affdd3dfed5a35c56a3ab6f2af900fa89b68526d8c1d1b8eeeef7de086ae`.
These include the release-marker guard corrections; later harness edits require
applicable rechecks. Neither check substitutes for the remaining actual scenarios.

## Attempt9 infrastructure failure and provisional attempt10

Attempt9 `4673b552d1f5414f8600ca9e0b966475` failed during isolated worker startup
with `lifecycle_runtime_compose_failed`, before source admission or any named
scenario qualification. Its exact summary SHA-256 is
`cbe6c69f4b879a686b57f772288008ae9d0a687e59ec59eb42d5cd0c17d1f927`;
`runtime-attempt-9.log` SHA-256 is
`5407cd2449bacbe28ef390047cb162116d823763119c086d22ebc3bfc0da53f9`.
Original helper stderr remains at the attempt's private work root under
`deployment/failures/76b137feba7544299d290ae388637182/stderr.bin`, SHA-256
`5b2bf8d3ac098f339e86d86da58674a5a2bd2ac2204c27a6be5b711a21dc12b1`.
It records Docker's actual “all predefined address pools have been fully subnetted”
network-creation error. Owned runtime was stopped. This is infrastructure/setup
failure, not a detection, activation or recovery semantic red.

Before retry,25 unused networks were verified against source-recorded exact
`<project>_internal` names, matching Compose project/internal labels, associated
containers' exact expected ownership and stopped states, and zero active network
endpoints. The original complete network-inspection documents are retained in
`.cache/lifecycle-runtime-qualification/stopped-owned-network-retirement.json`,
SHA-256 `eb697a593f54cb3d84ebc5b2b83754775830b91b5c1000a3ae7ce9d03114f3ee`.
Only those verified networks were removed; no container, volume, store, evidence
or unrelated network was deleted. No resource limit or Docker address-pool
configuration was increased.

Attempt10 `cf0876ba891b4dd9a1d1a4495f143a16` failed closed at the same
`lifecycle_qualification_timeout_group_closure_apply` barrier. Summary SHA-256 is
`76a7c9e408b561f972bb53be972a63d3d1a4940b82c2fafbcda81b5833d994e2`;
`runtime-attempt-10.log` SHA-256 is
`c2d85ea975ff1f5815d19317ab7ddb1914db62f51b2782095aec755c84539490`.
The same eight bounded scenarios passed, with217 logical/physical outputs.
Independently counted durable controller `admit` journal records total100 actual
broker receipts; the oracle accounts for95 because the last five open-group
admissions preceded the failed barrier and were never added after closure.
Those five are not claimed source-complete. The same six required scenarios remain
unqualified, and the summary reports owned runtime stopped. Production JARs,
validator identity and all resource/semantic limits remain unchanged.

Following two independent reviews, the extra new-A/open-group COMPLETED checkpoint
observer introduced after attempt8 was found unnecessary for the frozen T04/T16
contract. It delayed end-of-evidence admission behind an additional observation
barrier; neither failed attempt establishes the required closure outcome. The next
minimal harness correction retains the actual COMPLETED initial-B checkpoint proof
of all exact five open members, prepares A before those admissions, then publishes
A and immediately admits end-of-evidence. Signed ACK convergence follows afterward.
The fixed independent oracle still requires the first five receipts under B, the
end-of-evidence receipt under A, the complete six-member eligible end-of-evidence
closure, and A's tag/detection. If end-of-evidence races ahead of actual control
application, the oracle must fail; expected attribution cannot adapt to observation.

This correction is being implemented separately, without changing production
artifacts, deadlines, resources or expected outputs. Retaining a numerical deadline
in component/harness code is not evidence that actual new-A application met that
deadline. No post-correction runtime result is yet claimed. The earlier stronger
observer and its failed results remain preserved as historical evidence rather
than retroactively treated as frozen-contract requirements or qualified passes.

The final full static check for this pre-attempt10 source passed381 Python tests
in34.649s, Ruff/static checks, formatting and mypy for115 source files. Retained
`.cache/lifecycle-runtime-qualification/static-check-5.log` SHA-256 is
`f1ce628a175eab0c80ff3d44e25ac12b3ffda2b562733bacec96a50a371badd0`.
It does not qualify any attempt9 or attempt10 scenario, or verify the later
minimal harness correction. All prior failed/interrupted attempts and their private originals remain
retained under their original identities.

## Failed attempt11 and partial-ACK source isolation

Attempt11 `5735ed2264c04588b1f609d0ad9afe4e` failed closed with
`lifecycle_oracle_unexpected_event`. Summary SHA-256 is
`13685df804919fa2f13b5c269ab6fe4d6a19ab67c419c65f77fa3f823227bcb2`;
`runtime-attempt-11.log` SHA-256 is
`22d56d9fa23fd87867552459e962483fb96f20ae1c6978280940019aec17daae`.
Nine bounded scenarios passed, including the corrected open-group closure
selection in addition to the prior eight. That establishes the226-output baseline
for this attempt. The later failed collection reports228 logical and234 physical
outputs, with107 oracle-accounted source admissions; the durable controller journal
independently contains107 actual broker-acknowledged admissions. Owned runtime is
reported stopped. The remaining five scenarios are not qualified by this attempt.

A subsequent actual broker drain retained the original records from output offset226
through frozen end240 privately at this attempt's
`qualification-private-evidence/partial-recovery-output.json`, SHA-256
`bc098fdde65a1d5f7f3e75b0aecf38ae7b8cb3a518ce9a624a9fefa55c0e1748`.
Its bounded public diagnostic
`.cache/lifecycle-runtime-qualification/attempt11-output-diagnostic.log` SHA-256 is
`20950c22a78ef8489ba841f250861182cdf6cd6a8317756b9956aa4cb877a5f8`.
The observed tail begins with A revision9 receipts; after restoration at A revision10,
partial-recovery run206 yields a two-member `timeout` manifest with `cwd_missing`,
followed by late preservation documents and receipts. The preserved30-second audit
group deadline expired during recovery. This diagnostic explains the fixed oracle's
unexpected-event rejection; it does not establish data loss or wire corruption,
and those unexpected documents are not substituted into expected output.

Both independent reviews agree the partial-ACK requirement does not require an
audit group. The next bounded harness correction changes only that fault's source
to the existing atomic Windows Alice case on worker21/run206, with three output
intents and the exact frozen A expectations. It preserves the same actual first
Kafka-ACK hook, named injected failure and original broker topic/partition/offset/
wire-hash correlation. Qualification must additionally observe an actual retry at
a greater broker offset with the same output ID and exact wire hash, then check
the complete remainder against the independent oracle. No frozen fixture, deadline,
production artifact or resource bound changes. This correction is being implemented;
no post-correction runtime pass is yet claimed.

The full pre-correction repository check passed382 Python tests in38.788s,
Ruff/static checks, formatting and mypy for115 source files. Retained
`.cache/lifecycle-runtime-qualification/static-check-6.log` SHA-256 is
`544449c74cddd00e9f167bfd42a243d955e59d64be1984b96b742b4290ffe5bd`.
The new atomic-source harness and retry proof require applicable rechecks; the
382-case check does not claim their verification or remaining runtime acceptance.

## Actual ARM64 attempt12: all fourteen required scenarios passed

Attempt12 `4c3a291f98dd43a38e35965cbd0b48f9` passed all fourteen required scenarios
in one actual two-worker Kafka/Flink run, with no missing required scenario.
It accounts for103 source admissions,232 logical outputs and233 physical output
records, including one byte-identical accepted-prefix retry. All owned runtime is
reported stopped; no unexpected job failure was recorded. One retained checkpoint
query race remains evidence, not a substituted completion proof. The exact report
and coverage belong to this attempt, not a union of earlier partial passes.

| Retained actual attempt12 evidence | SHA-256 |
| --- | --- |
| `attempts/4c3a291f98dd43a38e35965cbd0b48f9/summary.json` | `fecafe00287c0c3d1b317a633f24bef4af6e8daa723a1298769c63d5a8d181c8` |
| Same attempt's `coverage.json` | `94aae82ecba0844dd5cbaeecbe0d83c88abd9336a6de75962d6380d4ebb92f7a` |
| `runtime-attempt-12.log` | `05ffd1aad9d0ab49097c5ef5bf97508539732d0680a74c4951daa53dce34dd85` |
| Complete canonical `source_sha256` map in summary | `0b0487d6bc495ae99a85ebc1425f1dc4f1960c5a21ad4cfc05a00fd60bac67c6` |
| Canonical summary fields `platform`, `images`, `docker_engine` | `aa60863d64824be158e25fde95dbc35c1fa9c6f4e161f5c91feedda62b48c69e` |

Paths above are relative to `.cache/lifecycle-runtime-qualification/`. Canonical
map hashes use sorted-key, compact UTF-8 JSON, with no trailing newline. The source
base remains `943333c515207a479c152ab646e2c3642c69c9f9`, dirty/uncommitted;
per-file hashes in the report are the actual attribution. The run used production
JAR055a, probe2dbe, original producer51 and validator packetf2/imagea1dc with the full
hashes recorded above. It used existing hash-verified tested JARs
(`jar_tests_this_attempt: false`); the separate29-case Java/build evidence is not
misrepresented as executed again during this runtime attempt.

| Required scenario | Actual bounded result |
| --- | --- |
| Core A→B→A and mixed workers | Both pass;42 admissions,66 logical outputs, six isolated runs, revisions1–3 |
| Publisher uncertainty and registered replacement | Both pass with retained exact intent and completed-state restore evidence |
| Broker outage and required sink failure | Both pass; bounded two-second outage and named actual Kafka rejection/recovery |
| Old outbox/new selection and finite backpressure | Both pass; unchanged128-intent bound,50 source locations,142 logical outputs |
| Open-group closure selection | Pass; exact five B members in actual COMPLETED state, six-member eligible EOE closure and A attribution |
| Partial-ACK recovery | Pass; first actual Kafka ACK at226 and exact same output ID/wire hash retried at227, remainder checked by fixed oracle |
| Aborted-checkpoint ACK isolation | Pass; actual checkpoint179 FAILED with named expiry, matching advisory snapshot/candidate, no durable ACK for that checkpoint through fenced prefix |
| Signed invalid messages | Pass; actual bad signature and validly signed corrupt chunk rejected while prior selection remains |
| Retained versions | Pass; exact A/B closures preserved, prepared references cannot retire; archive/replay pins remain P15b2 scope |
| Signed hostile AST | Pass; both actual workers independently reject validly signed self-rehashed forged AST while preserving A revision12 |

Three complete approved canonical REST response documents remain in this attempt's
`approved-fault-proofs/`: required-sink-failure10,786 bytes SHA-256
`c554cee2d5549de1064b4d5fbfc049c9365c96fc4974e45688e62c693f5baf82`;
partial-after-ack9,808 bytes SHA-256
`4e3e861bdfb866114d0aebdfe9483292cbd0d431eac3d756b287ba5d861f0ec3`;
checkpoint-expired719 bytes SHA-256
`521967dcb55052eb4bbc8e3c83fc8305aa92b156c9d84715b8c8b7ae5bd6c2d6`.
These are document representations, not HTTP framing or arbitrary log-export claims.
The partial failure is named `lifecycle_qualification_after_actual_ack`; its first
and retry wire SHA-256 is
`7e676aed012e6111840cf95753dab70f158f9a73753e44cc1915da1bde658cc3`.

S12's forged plan SHA-256 is
`1eb25d3924b385d0392ad77ce042d5ba58b43e3ccb85a1d98a836241eb4b38a3`;
forged bundle SHA-256 is
`ac6118176aa0f272842edaa0f12e714ea571ba0f3cbc36e5d64af858526b00bc`.
Actual rejection checkpoints are247 and191, with independent snapshot hashes
`c99ff7afa4b1cc33d8e1d5c67dbef449c0f051d40ae8435fe644471f97afebd8`
and `faf9ef8b1a89daa906eea2e2ddadecdf08f86dbde45ebf5df2a406c482844dca`.
The complete fenced ACK history from482 through frozen end499 contains no applied
or durable ACK for the hostile command. This combines actual rejection, preserved
prior selection and complete bounded negative-ACK evidence; it is not inferred
merely from missing output or publisher status.

Observed host is macOS26.5.1 ARM64; Docker29.8.0 runs Linux/aarch64 with15 CPUs and
8,318,844,928 bytes reported engine memory. These are observed engine facts, not
measured reservations or capacity claims. Actual ARM64 image IDs are Flink
`sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`,
Kafka `sha256:9916d60eca5d599550e2c320230808fda342124ba550bb4ac4ea8591803262a0`
and validator `sha256:a1dc0587e767d537d8488ff20ce1b50c47ae160fa34a4eb1f319bea011cfc827`.

### Later harness source: separately scoped verification

Attempt12 actually executed qualifier SHA-256
`6f5770bfd031b011f855e13072f49e19e0394d0b7353e63f50a309814b3058e1`
and controller SHA-256
`547bdf66a3029e42057a7820a973a128700dade84dc9ebdc54918f2be36b77ca`.
The later qualifier adds independently runnable fresh two-worker groups, bounded
ACK32/output64 read batches and stricter attribution of the partial fault's first
and retry ACKs specifically to atomic run206. Its current source SHA-256 is
`823e15b6f1b0d4b9941c216a93999ba16a3f29f44567753f694a4e59380a8ff5`.
These harness changes preserve production artifacts, fixed expectations and
controller authority, but attempt12's full result does not transfer to that source.
Focused success is explicitly `partial_passed` with `full_gate: false`; native CI
requires the default all-fourteen run and rejects focused mode before deployment.
A fresh actual focused partial-recovery run on exactly this later qualifier source
passed as attempt `9a57e35853584b62a91f15b82891d71f`. Its summary SHA-256 is
`a8df9c27a7dea911cef8da2660e6bd2da43a44299b5fe901e41aa0b083e739e1`;
its `coverage.json` SHA-256 is
`77d6b13b5f81e08b3fcff2c421a3769d8177480b23f392a127cefa1e0415653b`;
`.cache/lifecycle-runtime-qualification/runtime-focused-partial.log` SHA-256 is
`026635d42eb6f0b46cdd1f92c32ca8ffa6c5c0621d0556cd0498e0b734d59d55`.
Summary and coverage remain under the attempt's original directory. The status is
`partial_passed`, `full_gate: false`: selected requirement `partial_ack_recovery`
passes, and the replacement helper also genuinely executes and records
`publisher_uncertainty`. Twelve other required scenarios remain explicitly
unqualified in this attempt; the report does not manufacture their coverage.

This actual focused run accounts for one admission, three logical outputs and four
physical records, with all owned runtime reported stopped. The strict atomic run206
attribution check passes for both first ACK at output0 and exact retry at output1,
with wire SHA-256
`3c9dc2bc96c83eedd50808d98c498bd85d8d5cb2e8f45f348b25bdc08afcced8`.
Its approved9,809-byte named partial-after-ACK REST document SHA-256 is
`62b2625f73624a08cf59fcd8b042f8aa4ac36fcb85ebf15548a8a0cb9f8b8790`.
The complete independent oracle also checks the remaining outputs. This is actual
verification of the final-source focused workflow and stricter attribution guard,
not a final-source all-fourteen pass. Native full PR qualification remains pending.
A separate read-only check applied the final guard to attempt12's original broker
records226/227 and its actual run206 admission receipt. Both belong to the expected
atomic case and contain identical complete envelopes; all owned runtime was then
stopped. This supplements attribution without relabeling the original full run.
`full-marker-scope.json` SHA-256 is
`921863b31945fa5c127011f744edaea2401fca8eabb80e0f6bcf7630e3f40b70`;
the retained log SHA-256 is
`0541b13a6db68f0e2a3017b986fff845a95096b73b46d7fcf99fe306d41b0837`.

The final later-source static check passed387 Python tests in34.364s, plus Ruff,
static checks, formatting and mypy for115 source files. Retained
`.cache/lifecycle-runtime-qualification/static-check-8.log` SHA-256 is
`a7af7572cea1954dcae6432b35dfb2d62392e0d5e280c370c6e97e01da173336`.
This verifies the later harness at component/static scope; the full native AMD64
PR run on final source and review gates remain open. Prior failed/interrupted
attempts retain their original evidence and outcomes. Actual timeout snapshot
serialization, observed durable-ACK candidate and absence of that checkpoint's
durable ACK remain distinct from direct task-side abort callback execution, and open-group application timing is not independently
claimed from a retained numerical deadline.

## Native PR failure and bounded mixed-worker scheduling correction

Actual native AMD64 GitHub run44604141541, attempt1, activation job135844572369,
executed test-merge `5905a21f04a84b2c6c583cd49fefb22e356bd6bb` associated with
PR head `1d271ef`. Its internal qualification attempt
`f06893909f264de5984b9d2d433faf5e` failed with
`lifecycle_qualification_unexpected_job_failure`, after16 admissions and22 logical/
physical outputs, before any named scenario passed. Worker21's actual job was
FAILED; public metadata records `java.util.concurrent.TimeoutException` and
`org.apache.flink.runtime.JobException`. All owned runtime was reported stopped.
This native run does not pass the activation gate.

| Retained native evidence under `.cache/lifecycle-runtime-qualification/` | SHA-256 |
| --- | --- |
| `native-44604141541-activation/summary.json` | `21cb6e29721f9deb23ffd17fec6aa0f3a1ed4eba7064d9e27bec2e7a28dfd0e7` |
| Original `native-44604141541-activation.zip` | `ae61ce60ce9b75673d2b17c44b8258dead6ce39d970e970f821eac6af4122a76` |
| Actual `native-44604141541-activation.log` | `77a276271be72e7cc9f62b40696f17a3d81a985207e5fed87ede4b55649480a5` |

The native REST exception document hash is
`ee2850823b09812ee574c1b4772b2a29464017e3d7c9acef308995a73a568b27`,
and job-state document hash is
`3a1692a66cc8059682420c99999a05616d846fc597cb9f070c603bfb3e908f31`.
Unknown raw REST documents were retained privately on the runner and were not
uploaded. Their hashes and exception classes do not establish an exact originating
native heartbeat message or root cause. No claim here retroactively reconstructs
that missing native raw evidence.

Pinned Flink2.2.1 bytecode establishes the default heartbeat timeout is50 seconds.
The core JAR SHA-256 is
`b29b9e87c6124fefed668a4275c0c1cbfbcc1e073fdaae4e5723416814312db1`;
the runtime JAR containing the exact TaskManager heartbeat timeout template is
`cd60a8ae96d5baed7cf19a6637555cbbdc04739da8b3d26c9f828da3bb2b44e3`.
The mixed-worker case pauses only a TaskManager while its JobManager remains live;
heavy signed-ACK readback inside that window can overrun the heartbeat budget.
This is a source-supported scheduling risk, not proven native causality from the
available classes alone.

The correction preserves C07: during one shared40-second monotonic acceptance
budget, publish B, require an actual globally COMPLETED worker20 checkpoint with
exact current B command/revision/incarnation, check actual B source outputs against
the unchanged oracle, prove the same owned/current-incarnation worker21 TaskManager
remains paused before and after with its prior actual COMPLETED A state, and require
mixed status with both exact participant obligations and convergence false.
`finally` resumes worker21; only afterward does normal exact signed-ACK/named
COMPLETED checkpoint convergence run, followed by worker21 B source outputs. Core
accounting remains42 admissions/66 logical outputs. No heartbeat, checkpoint,
source-assembler or other timeout, artifact, resource or fixed expectation changed.

A diagnostic classifier recognizes only the exact pinned TimeoutException heartbeat
template with bounded valid host/port/lowercase-six-hex resource grammar. It exports
fixed categories and document/message hashes only. Unknown messages remain
unclassified failures, multiple distinct matches remain ambiguous, and arbitrary
REST/log values remain private. This adds future diagnostic evidence without
changing failure acceptance or retroclassifying the unavailable native message.

The before-fix actual focused mixed run `4d2f92023e874659ab8fa73731476931` passed
on qualifier SHA-256
`14fa62245da498cf4d306361d95d9737eb911481a7a14174c4e2d7d724dec94f`,
with15 admissions/25 logical and physical outputs, all owned runtime stopped.
Its summary SHA-256 is
`528c4c5f2a7f7b19a74e1dee397c387612c67f7dc7cc2e812147554838ad0865`;
coverage SHA-256 `da2b88ff9d0b86800cc749a4ceadea3c6a814c7c8d7d31f483b4237ddcfadb0d`;
`native-fix-mixed-before.log` SHA-256
`0b6ad2ae64585e0f975adb22b6a167b751735bf1ad7206887b64de6f9c234c7e`.
This is green-only local evidence, not a reproduced native red or proof of its cause.

The after-fix actual focused mixed run `4990a094173b490ba8ce42893101a42d` also
passed, on current qualifier SHA-256
`0a81b3b9b8290045d69e8b88e8d12498ec865e3add597e0bba000975402d24fe`.
Its summary SHA-256 is
`4304843e0a3535f330dcb520b773547e6533e3ff05eb7bdafd8016e4e6a77418`;
coverage SHA-256 `4f653beac0a3890908231b63a368844b2afaa3f21fc5e12a460629fee72b388c`;
`native-fix-mixed-after.log` SHA-256
`d4482b5de0e1fffb2146dfdd12a03266046101425fe8d78b344c2ea0ca5b66f3`.
It records15 admissions/25 logical and physical outputs, actual B checkpoint10,
matching owned paused TaskManager identity/incarnation before and after, and
22.831198208004935 seconds through resume within the40-second acceptance budget.
All owned runtime is reported stopped. Both focused reports are `partial_passed`,
`full_gate: false`; thirteen other required scenarios remain unqualified in each.
Neither report replaces the pending corrected-source full native gate.

The first correction static run passed its Python tests but failed formatting;
original `static-check-native-mixed-fix.log` SHA-256 is
`7cdb30c264360b1b262cbd69ad50764f4d1b29eb38f9b39b394ec9ee664db89b`.
After that formatting correction, the final check passed392 Python tests in34.498s,
Ruff/static checks, formatting and mypy for115 source files. Retained
`static-check-native-mixed-fix-final.log` SHA-256 is
`4f2d14f4e8a16734742f50778b0008dbe671e511f1cae624c33c4a157df4bd45`.
This correction is a fourth cohesive published-history CI commit under the SDLC
exception; earlier commits and evidence are preserved without amending published
history. Corrected full native CI and final review remain required.

## Second native failure and separately frozen qualification batch transport

Actual native run44609809010 on published head `ea89579` executed test-merge/source
`95673d2fd0b6ba4fff1c85a003587d03d2e89c56`. Internal attempt
`84bacc621b03453d8deae7bfa5154c4c` failed with
`lifecycle_oracle_unexpected_event` during initial A accounting:14 admissions,
10 logical and24 physical outputs, zero named scenario coverage, no unexpected job
failure and no checkpoint query failure. The mixed-worker case had not begun.
The exact offending decoded output batch was private on that runner and was not
uploaded. Counts alone do not establish audit expiry, wire corruption or another
specific cause. This native failure remains failed evidence.

Retained `.cache/lifecycle-runtime-qualification/native-44609809010-activation/summary.json`
SHA-256 is `51b0b6b12639f7fe261b4a4c0d55c41668e225c8d7cf96ad7102ec36040f1499`;
the original adjacent artifact ZIP SHA-256 is
`b2bacc5bc27edd5c6dd8af32ba99f65f5cfab16df6b9ad819d5c84e59230f35f`.
The download metadata file `native-44609809010-artifacts.json` SHA-256 is
`b36f194e92cc677dd76c5d3efc216c2a120291f5f3c739012cfbcba9b7aaf829`.
The downloaded artifact's `build.log` SHA-256 is
`cda85ca6168c25c6c29e2822bcb1dba1f9b1050c9e40930ddefd20f8b4b25d07`;
its `validator-build.log` SHA-256 is
`aa772c5adc0ac52b147c375ba6ddb6a9fb03832b3d3273eb97ba17fd01156543`.
Those build logs do not reconstruct the missing offending runtime body.

The new qualification-only batch artifact/recovery boundary and independent
Q01–Q20 expectations were frozen before implementation in
`9ba244176126998d773eff0e7bebe1001a877d7e`: see
[batch design](p15b-batch-design.md) and [batch expectations](p15b-batch-expectations.md).
The separately pinned qualification JAR is now
`cdab56bd62476a2d5948011681d561cfb3757a0dc2c4a55c39cfc817e30d0a9b`.
Production lifecycle055a, original producer51 and compiler packetf2 remain unchanged.
The fixed qualification entrypoint reuses actual Admin/Producer clients, with the
same per-record namespace checks/ACK timeouts. Limits remain128 records,2 MiB each,
8 MiB aggregate and64 KiB request; unchanged process budgets apply. Attempts, raw
ACKs and certified receipts are separately forced in order; only certified dense
prefixes become normal controller admissions. Operation/request/index/receipt-hash
markers make recovery idempotent. Incomplete/failed/recovered batches block further
admissions for that worker, without suffix resend. The deployment caps64 permanent
operations and reserves16 MiB before copying, within existing store/entry limits.

The Java component suite passes46 cases (original29 plus17 batch mechanics), zero
failures/errors/skips. Exact XML SHA-256 values are
`adec9c0bd7db372d9f7461be673a711626f7070571f591c85af3c592046115c8`
and `837469b0b899c5232385961c8aca5b9d47460a321c930ab0327ea717f3c3ae79`.
The final offline `packages/lifecycle-job/build/batch-retained-partial-final-build.log`
SHA-256 is `6825d05b2d8400a431639ca3540e6decc7ad34f194c13c5c38a080e4e63d3a7f`.
These are component/transport-mechanics results, not actual Kafka/Flink acceptance.
The qualification-local publisher retains uncommitted UUID partial files on write,
force or rename failure; they are never promoted into receipts or silently retried.
Earlier build/setup logs and failed tests remain retained separately.

The controller48-case suite passes, including original mechanics and new dense
prefix, raw-ACK uncertainty, immutable metadata, force/recovery, orphan and bounds
cases. Its final retained log SHA-256 is
`bd4dec79870e08e087ab4a16ea56f34779df46fde16e5226a8390c2152f36a17` at
`.cache/p15b-prerequisites/batch-controller-orphan-final.log`.
The separately owned oracle suite passes37 cases. The captured integrated
Python run passed90 cases in7.915s, log
`batch-controller-oracle-integrated.log` SHA-256
`10f04e835c497541d090ba1e7c9ab5e9e7a2f02cd5feae0ce8154421758b1367`;
that captured aggregate predates the final component state and is not relabeled
with an inferred larger count. The final full repository check passed413 Python tests in39.689s,
Ruff/static checks, formatting and mypy for115 source files. Its retained
`.cache/lifecycle-runtime-qualification/static-check-batch-final.log` SHA-256 is
`5d2b219354a845171b12994096b3abe898b45167a26d7129b8b14dff6fa5e095`.

The first actual focused batch-core run `417aae87fbc44509bccf5b4f1c10b431` failed
with `lifecycle_runtime_helper_fence_unconfirmed`. Its original summary reports
zero admissions and no owned-stop result; SHA-256
`67855b974496c0d70e9234acc7be635ca99af1fda936379622d7e3d5d1591220`.
Original `batch-focused-core-1.log` SHA-256 is
`dd124f84c5b7772411237cfc6368736af8083dfc4cdc70b76fd1b5849a7fbdd2`.
Actual Docker29 stderr used lowercase `error: no such object:`, which the previous
case-sensitive missing-container check rejected. The correction recognizes only
the known missing-container grammar case-insensitively; daemon errors still fail
closed and owned deletion uses the exact inspected container ID.

On subsequent open, the exact surviving certified one-record prefix was forced
and recovered into one normal admission without resending. The operation remains
`recovered`, blocking further worker admission rather than manufacturing successful
original execution. All owned runtime was then stopped. Retained
`batch-core1-cleanup.log` SHA-256 is
`a3477f349c52cee4d22618dae11c7d99e724ff4262d0ca2d15272a5ac59dcd2c`.
The original zero-admission summary is not retroactively edited to report the later
recovered admission.

Genuine controller force/recovery and malformed-metadata reds remain retained.
Metadata directories/symlinks are counted with bounded nontraversing lstat before
ordered validation, so a corrupt later member cannot erase an earlier certified
journal prefix. Orphan pre-intent operation effect directories must be empty;
legitimate input/request partials remain preserved. No cleanup deletes those
originals or repairs unsafe metadata silently. Unknown output diagnostics now
retain original decoded records privately before the fixed oracle check, exporting
only validated IDs, fixed enums/allowlisted finding codes, counts and hashes.
This does not retroactively diagnose the second native failure.

Actual focused batch-core run2 `9acc4cd3923749479f34ff02f26778b2` is **PENDING**
at this commit, using the new cdab qualification artifact and recorded new source.
`batch-focused-core-2.log` is the owned run log; no completed result or scenario pass
is claimed. Corrected full native CI is also **PENDING**. Pushing verified component/
static source allows that native job to run concurrently with local qualification;
neither is represented as already passed. The batch implementation is intended as
a sixth cohesive commit after its separate freeze, under the SDLC published-history
exception, without amending earlier commits or failed evidence.

Final-source full native AMD64 PR CI and review gates remain open. P15b2 must deliver
its separately qualified archive/replay graph before complete P15 acceptance and
dependent P16 implementation. Private recorded AMD64 remains unavailable. There
is no HA, disk-loss, physical power-loss, unbounded-outage, rescaling or throughput
claim. Owner authorization remains required for the next merge and any release.

## Focused batch completion and cold bootstrap correction

The previously pending focused run `9acc4cd3923749479f34ff02f26778b2`
completed with `partial_passed`: core two-worker A/B/A and mixed-worker cases
passed, with 42 admissions and 66 logical/physical outputs. The other 12 scenarios
remain unqualified for this source; this is not a full gate pass. All owned runtime
was stopped. Summary SHA-256 is `017388ecf729716571005adfb94d5d16361be489b72bb8e1142a530a8da23ad1`.
The recorded dirty source hashes match the corresponding files committed in
`f2911a2f88e1f0ce5abdf7090d4a596ef8ed6483`.

Native run `44617619871` on f2911a2 failed toolchain job `135890522365`
before activation: Gradle reported Shadow 9.6.1's implementation POM missing at
Central. Activation was skipped, not failed on a scenario. Both POM and module
endpoints subsequently returned HTTP 200; the original remote lookup cause is
unproven. Original job log is retained privately at
`.cache/lifecycle-runtime-qualification/native-44617619871-toolchain.log`, SHA-256
`a07efddac9596f0dc11f8f25ca63eb5d4d641044fde05116db46bcf6b86f7b30`.

The correction explicitly enables module-first metadata for only
`com.gradleup.shadow:shadow-gradle-plugin` at Central, with POM fallback.
This removes POM discovery as a prerequisite for the already pinned module.
The marker remains Portal-only; other dependencies retain their existing policy.
No dependency version, checksum, lock, retry classification or verification setting
changes. Independent read-only review found no issue in this scoped change.
Gradle's metadata source behavior is documented in its
[official manual](https://docs.gradle.org/9.9.1/userguide/supported_metadata_formats.html).

Actual Gradle 9.9.1 `--no-daemon --console=plain --info help` passed in 14 seconds
on Darwin ARM64 with an empty, isolated dependency cache; only the already verified
wrapper distribution was shared. The log confirms direct download of Shadow's
module and JAR without its POM lookup. Existing strict verification passed.
Log `.cache/lifecycle-runtime-qualification/shadow-module-cold-help.log` SHA-256
`7b20d08d30e952485e74a76d7b30ece5129b67069e3620bce611529cd5c6caf6`; cache identity/result are retained in
`shadow-module-cold-result.json`. This is bootstrap evidence, not runtime acceptance.
The full native gate remains pending; no full local runtime rerun is required for
this repository-metadata-only correction. This additional published CI correction
preserves earlier commit IDs and all failed evidence under the SDLC exception.

The correction's complete repository check passed 413 Python tests, lint,
formatting and mypy for 115 source files. Retained log
`.cache/lifecycle-runtime-qualification/shadow-module-static-check.log` SHA-256
`e54ac48b1a3ad1b35089785fcdf18d8c7773cbdf91023cb8b6d45f82845efd15`. The initial documentation check
caught an extra blank line; it was corrected before this passing run.
