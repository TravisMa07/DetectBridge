# P13d qualification ledger

Current pre-merge checkpoint (2026-11-17): implementation head
`1645359a1c7ced9efc6a5f514e671b78febb6d21` passed every applicable native AMD64
job and required-checks in run 44196952063. Final production JAR 51a984de passed
full ARM64 integration, recorded source-to-search and synthetic writer suites.
The final sections contain exact artifacts/results; earlier failures remain
historical evidence. P09–P12 prerequisite acceptance/issue dispositions are complete.
Private recorded AMD64 qualification is unavailable. Final PR-head checks after
the documentation push, owner P13 acceptance, resolved review, explicit merge
authorization and successful merged-commit checks remain mandatory; P14 is blocked.

PR: [#49](https://github.com/TravisMa07/DetectBridge/pull/49), base `0f6d758`.
Independent design/count/membership freeze: `55e9715`; implementation: `7446337`;
published CLI correction: `256c54f`; coordination/diagnostics: `1bf1183`; message-free native throw-site diagnostics: `fdca907`; timer/source assertions: `779c70a`.
The [acceptance map](p13-acceptance.md) separates bounded prerequisite completion
from remaining P13 gates. P13 remains open; P14 remains blocked.

## Original diagnostics and corrected attribution

Merged-main [44145796752](https://github.com/TravisMa07/DetectBridge/actions/runs/44145796752)
finished with integration-verification and required-checks failed. Search, assembly,
detection and every other applicable job passed. Original integration failure
artifact 14358080606 was downloaded before any cause assignment. Its ZIP SHA-256
is `b9fb795f149d3792ca938df11704f3abbf16e2dbd0ff90f50eb67c07625f290b`;
original bytes and extracted files remain at `.cache/p13d-diagnostics/`.

The public failure category is `integration_unrelated_restore_failure` during
explicit incompatible-binding restore. The retained JobMasterException reports
an unreachable TaskManager; all observed containers were running, with no OOM.
Code inspection establishes that the handler fetched the tracked original job's
exceptions, while the incompatible probe was separately submitted and untracked.
The retained exception therefore cannot identify that probe's failure cause and
may represent the suite's earlier intentional TaskManager kill. No infrastructure,
OOM, checkpoint or runtime cause is assigned without the missing probe diagnostic.

P13d separates incompatible-probe and subsequent healthy/JobManager-restore
phases, so a later failure cannot reuse an earlier successful probe's exception.
A dedicated regression verifies both diagnostic targets. P13d saves the actual
probe's job ID, selected checkpoint and original exception
before requiring the exact incompatible-binding marker. Regression probes reject
both heartbeat and missing-checkpoint errors as unrelated. It also uses the already
regressed cancellation-before-selection helper for this restore path; observing a
checkpoint before cancellation has the same independently demonstrated retention
hazard as the earlier JobManager path. This addresses that hazard without claiming
it caused the historical failure or changing runtime checkpoint semantics.

## Locked local checks

On macOS ARM64, all locked commands passed on the implementation content:
`tools/dev.py check`, `java`, `windows`, `linux`, `assembly`, `integration`, `search`.
Root checks ran 164 Python regressions; combined Java includes independent legacy/
mapped semantics and the installed production artifacts. New regressions cover
missing/changed originals before runtime creation, exact Windows preservation,
frozen literal count/membership consistency and actual probe attribution/rejection.
Logs are ignored under `.cache/p13d-{check-final,java,windows,linux,assembly,integration,search}.log`.

Initial local check found a mypy error in a test double's append-expression return;
its explicit helper now returns the fake JobID. Lint/types and the full check then
passed. This failed check is not runtime qualification. A read-only preflight
rehashed all accepted original artifacts and prepared five Windows, thirty audit
and eleven authentication rows; it does not establish end-to-end acceptance.
The auth originals were reused from the earlier local workspace's accepted cache,
then independently revalidated against the immutable catalog, never recaptured.

A separate offline preflight on implementation 7446337 ran the actual installed
Windows, audit and authentication Java consumers with the twelve-rule plan. It
produced four Windows, ten audit and two authentication events; independent Windows
source/System assertions, exhaustive audit token/membership/quality assertions and
all frozen literal counts passed. The first auth invocation used a nonexistent
convenience executable name; it ran no auth code. Using the documented
`linux-adapters` executable passed. This command error is retained separately from
runtime results. Local inputs/outputs and the bounded verified report remain at
`.cache/p13d-offline/`; this does not prove Kafka/Flink/search delivery.

A test-report isolation edit initially had invalid grouped context-manager syntax.
A check launched before that correction overlapped the subsequent check's log path;
the mixed log contains the earlier import failure and the corrected 165-test pass.
The final serial check uses a distinct log path. These development command/test
failures are not runtime qualification and no assertion was relaxed.

## Published CI correction and commit boundary

Implementation-head native run 44175724388 failed synthetic search before its
first source admission. The new optional `audit` directory argument shadowed the
imported synthetic audit-record builder, and lint removed the unused import.
Original failure artifact 14370761311 (ZIP SHA-256
`951f6c16d8bebe77ee52489e3c0797d868a774f6995986c7ce6be0c775956b44`)
locates the TypeError at search_writer_qualification.py:407. Its two additional
unavailable-recording reports came from synthetic missing/changed-original unit
regressions, not actual recording attempts; those tests now isolate report roots.
Directory argument names and the import are corrected at `256c54f`. A regression
executes synthetic audit/Windows admission with all directory arguments supplied
and requires reaching the publisher. Nine owning Python tests, lint/format and
mypy passed. No source/runtime/writer assertion changed.

The published CLI correction is a separate cohesive third commit. Native
reproduction required a fourth correction/diagnostic commit (`1bf1183`) before
another CI run could capture original process logs. A consolidated evidence
commit follows. These are necessary published-correction/evidence boundaries;
the freeze, implementation and published fix history are not rewritten merely
to force the normal 1–3 planning target.

## First original-recording runtime attempt

Project `detectbridge-p13-recorded-09a9947138` passed original-member open checkpoint,
TaskManager recovery and deadline closure. It failed the remaining-source oracle:
qualification sent global `run_end` before Windows/auth admissions. Original retained
source observations show Windows `after_dataset_end` preservation, correctly
reflecting the accepted global run-end policy. No adapter or expected eligible
source outcome is changed. The qualifier now sends every original source before
run_end; a regression requires that global ordering. Failed inputs/acks/observations,
source report and original exceptions remain in ignored project/report caches.
This failed attempt is not recorded source-to-search acceptance.

## Second original-recording runtime attempt

Project `detectbridge-p13-recorded-efcc0b6480` passed both complete source populations,
TaskManager/deadline recovery, original late links, required tagged-sink rejection
and healthy source restore. Retained observations include all 32 tagged events and
233 physical source outputs. It failed search offset accounting with
`search_accounting_timeout`. Its source exceptions/observations survive, but writer
health/logs were not retained before cleanup, so the historical writer failure
cause is not assigned. No timeout is waived or counted as acceptance.

Inspection identifies a qualification lifecycle conflict: the source-producer fault
changes a topic policy which the independent writer deliberately freezes. The next
suite explicitly stops that consumer for the operator's source-policy fault,
restores the healthy policy and requires the writer's normal strict restart before
indexing recovery. Production binding/commit behavior remains unchanged. Original
writer health/offsets/logs are now retained privately on subsequent failures, before
owned cleanup. This avoids retroactively attributing the second attempt to an
unobserved exception.

## Native processing-sink failure with original evidence

Correction-head native run 44177420786 passed actual search qualification but
integration failed at required_sink_processing. Tagged/detection sink rejection
and healthy restore passed at checkpoints 58/70. Original artifact 14371921401
was downloaded before diagnosis; ZIP SHA-256
`10464b27abdb3509d21e8b8c81ff627d489c2af85b24d79283340c6e0aa9179b`.
Its actual current-job exception reports TaskExecutor shutdown followed by
NoResourceAvailableException and exhausted fixed-delay recovery. One container
exited 1 with OOMKilled=false; its service label and original container logs were
not retained. This does not establish why the TaskManager exited, nor prove Java
heap/metaspace exhaustion or an external kill. It is an unrelated failed fault
qualification, not accepted RecordTooLarge evidence. The earlier incompatible
probe diagnostic is independently retained and contains the required rejection.

P13d now retains bounded original container logs, service identities and actual
TaskManager/slot registration before cleanup for subsequent synthetic failures.
No retry/timeout, memory budget, failure marker or runtime assertion is broadened.
The original diagnostic gap remains explicit until a new observation establishes
the actual failure cause. Private recorded failures retain writer diagnostics
locally; ordinary synthetic CI artifact paths do not include private source bodies.

## Completed ARM64 original source-to-search qualification

Project `detectbridge-p13-recorded-bec1f71056` passed the actual opt-in command.
All five Windows, thirty audit and eleven authentication originals were rehashed
and their accepted acquisition/host/boot/terms/context bindings revalidated before
runtime creation. Two full isolated replays used 92 original record occurrences,
three explicit controls, two exact redeliveries and two clearly identified
controlled late-cursor admissions: 99 acknowledged Kafka inputs in total.

Independent source fields/System attributes, audit token spellings/argument/PATH
membership, all frozen counts/matches/nonmatches, quality/capability distinctions,
complete version attribution, manifest and original late links passed. Original
event/evidence IDs were stable across runs; processing and detection IDs were
disjoint. Every original Kafka input was retrieved and rehashed. Source-derived
search fields, first physical-copy hashes, membership/evidence links and all
76 logical search documents passed. All four writer topics finished at zero lag.

| Logical output | Count |
| --- | --- |
| Tagged events | 32 |
| Linked detections | 6 |
| Grouped processing diagnostics | 38 |
| Original manifests | 20 |
| Preservation documents | 28 |
| Quarantine | 0 |
| Input receipts | 99 |
| Total | 223 |

233 physical deliveries included ten byte-identical stable-ID duplicates. Open
checkpoint 9 retained the six original execution members before TaskManager
recovery/deadline closure. Completed checkpoint 36 retained the second replay's
original tagged event/members under actual RecordTooLarge rejection; explicit
healthy source restore and strict writer restart drained every required output.
Host, same-total outcome-count and attribution mutations were all rejected.
No source expectation or runtime/failure assertion was weakened.

The recorded population has nonzero matched, unmatched, inapplicable,
configuration-blocked and quality-skipped outcomes. Evaluation-error/budget,
missing identity, malformed and other edge cases remain the separate synthetic
suites. The new late cursor is a controlled qualification input with original
body bytes, not an original capture occurrence. OpenSearch remains a derived view;
no archive, throughput, release or native-recorded AMD64 claim follows.

Exact immutable artifacts and metadata:

- Integration bundle: `ced331f728bca6d4dcebee0299e49efd6fd87350768dad1c10d3692254242b4b`.
- Integration JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- ARM64 integration image: `sha256:46e79601d113df376617ef4f2bf4f769d1fa77c5bc0cdb7704796d46e754b685`.
- Evaluation bundle: `578811003a30011a46b87dda908f9a1ebd03bb949aa11f0500eb660832396406` (committed original rule provenance at 256c54f).
- Search bundle: `d78eda0c3c632a108bd89819663c8cc1c6928a1e9c76c13e2eaa274273e05fd4`.
- Search JAR: `6f60d3589d502bee41dc926c768c130b91e6437f28d115daef8775486593a575`.
- ARM64 search image: `sha256:eef0171af4dccb0922e069190f96bce412b181b71b53926bc9d22be5935cfced`.
- Recorded runner bytes, committed in 1bf1183: `8dbd7e4b3636dacc1d423c33f2b5198d9ecb06605ad9317f98087d6a06b3a669`.
- Canonical independent expectation hash: `55af12523e5a5f9a7acf2a9f0d781c33ae85373ed2763e5c2f600bce3bb8bc2d` (raw fixture-file SHA-256 `9e5c3e3711dea7835a363828e45a25f58c4785bbfb38d682e2894d9f069644c2`).
- Canonical catalogs: Windows `ec277d352417bb0a99443a6fa22d3990da9ae4046f8fab480993e2a58eb570a1`; audit `1fcdddf89e572bed765327ac21b10019683e467706850e6045fc78ed4608ae6d`; authentication `97ae15e085dfe40c5e5687ecc6a69a34be9af899089259489bb8575d60d168f7`.

Private source inputs, expectations, acknowledgements, complete source observations,
open/blocked checkpoint inventories, writer state and bounded result report remain
under ignored project/report caches. The result is
`.cache/search-writer-reports/detectbridge-p13-recorded-bec1f71056.json`; the log is
`.cache/p13d-recorded-attempt3.log`. Only owned containers/volumes were removed.
All current source content was qualified without committing originals or credentials.

## Completed ARM64 current-helper recovery and writer regressions

On source/qualification head 1bf1183, full actual integration project
`detectbridge-p13-test-adc534207970` passed 44 inputs, 20 logical events,
103 logical outputs and 145 physical outputs. It exercised the corrected
cancel-before-selection probe, exact incompatible binding rejection, healthy
explicit/JobManager restore, TaskManager recovery, 40-second broker pause,
original deadline and all seven required sinks. Completed blocked checkpoints
were tagged 47, detection 55, processing 63, manifest 71, preservation 79,
quarantine 87 and receipt 95. Original source references and Kafka retrieval hashes,
exact output IDs/bytes, metrics and payload-log isolation passed.

- Integration bundle: `d240c8bdde5a986efd1b0fdf66376e042fc4b34671c2986dce33d1cde9c2cc0f`.
- JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- ARM64 image: `sha256:7b14adbb1b2a7bbb5f6627cb8cb2e5858cf01e9ca4c9e5be3368293514158fde`.
- Evaluation bundle: `5f7bdb820ab6a0ca630bdcf37bd66b68a6a536ac67143e7372411fbeb3582d68`.

Full assembly project `detectbridge-p12-test-9740ca9b1c60` passed 52 inputs,
ten groups, 83 logical/93 physical outputs with ten stable duplicates. All five
required sinks retained original intents at checkpoints 51/56/61/66/71;
TaskManager/JobManager/explicit/incompatible restore and 40-second broker pause
passed. The limits and byte-pressure profiles passed, including closed-budget
rejection with original source offset 8 retained. Bundle
`9cba7aed38a1dfd2a3ad57e46cb785cb7863807a13809afa41bfb0c95dad2f15`,
JAR `d341724639876de0e09a5006bf2e265172a75cd16b7d03b495dc1f4086d19a99`,
ARM64 image `sha256:0c8ca5f45215b5fd3ae9077f8993e2462635fbbf752abaf8fd0257ec604d1d72`.

Full synthetic writer project `detectbridge-p13-search-3caecc0f4d` passed
35 source admissions, 21 logical events and 48 source-derived search documents.
Ten controlled output-topic admissions produced eight independently checked
writer-failure references. Both isolated replays, all six nonzero outcome cases,
exact timestamp/doc-value cases, outage/recovery, duplicates/conflicts/tamper,
blocked failure publication/indexing, indexing-before-uncommitted-crash recovery,
partial bulk, exact denied permissions, drift/TLS and original retrieval checks
passed; all four topic lags were zero. Its integration artifact is the d240c8b
set above; writer bundle/JAR/image is the same d78eda0/6f60d35/eef0171 set in the
recorded qualification. Source population and synthetic probes are distinct.

These runs precede the dedicated throw-site logger; they are not silently
attributed to its new image fingerprint. Source processing and writer JARs remain
unchanged. The new-image recorded run below passed; native recovery remains
a separate gate. All owned stacks/volumes were
removed; reports/logs remain ignored under `.cache/p13d-final-*.log` and owning
runtime/report caches.

## Native diagnostic refinement after 1bf1183

Run 44181348320 again failed integration, this time after processing-sink
RecordTooLarge rejection passed at checkpoint 84 and during healthy source restore.
Artifact 14373263043, ZIP SHA-256
`d9cc5d46552c9daa5c26c0792e13a1c7937919d0cfa4962254060539abc940d0`,
confirms taskmanager exited 1 with OOMKilled=false and no registered workers.
Retained console logs have only logger/level fields because the existing profile
intentionally discarded exception details. They cannot establish the exit cause.

fdca907 adds a dedicated integration-only profile with message-free throw class,
method/line and a fixed root-OOM marker, plus bounded pre-fault VM/thread snapshots.
The actual pinned image passed six logging cases: missing exceptions before/after,
ordinary/nested/private messages, custom toString and direct/wrapped OOM markers.
A misleading OOM string inside an unrelated message is not a root-OOM marker.
No source body, message or raw exception text enters routine logs; no Maven pin
or runtime/failure/resource policy changes. An initial isolated probe encountered
networkless hostname/entrypoint setup noise and literal formatter spaces; fixed
helper hostname/entrypoint and explicit metadata whitespace handling passed the
strict actual-image shape/privacy assertions. That failed helper setup is not
runtime qualification or a source/parser failure.

## Runtime and platform evidence

The fresh baseline integration suite passed on the unchanged P13c production
artifact under project `detectbridge-p13-test-9c77764e8e81`: 44 inputs, 20 logical
events, 103 logical outputs and 145 physical outputs. All seven required sinks,
TaskManager/JobManager/explicit recovery, exact incompatible-binding rejection,
40-second broker pause, retained absolute deadline, original Kafka hashes and
stable duplicates passed. Its helper was loaded before the P13d cancellation/probe
correction, so it is baseline evidence, not final helper qualification.

- Bundle: `9847a1aff5b41cff2ffd684855e3079ccdb7eb7c57ba2c905eafa4ecb7e8fd39`.
- JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- Image: `sha256:682776a4065b16501c5963fb34cfee24e029a08191c5e353973ab0081cc99116`.
- Evaluation bundle: `c9c739278d7ff51491cd18d5f897882ab7fa56e430537d4eab3c6bce7099c72e`.
- Blocked checkpoints: tagged 45, detection 53, processing 61, manifest 69,
  preservation 78, quarantine 87, receipt 96.

Recorded ARM64 qualification and the complete 1bf1183 recovery/search suites
passed as attributed above. Locked checks on 779c70a passed 169 Python tests,
lint/format/types, contracts and hygiene; owning integration checks passed seven
regressions. Additional assertions reject same-count RFC5424 header mutations,
changed source context and inferred hostname; original auth outputs passed the
stronger assertions offline before the new actual recorded run. The first shell
invocation used the system Python 3.9, which cannot import datetime.UTC; it ran no
qualification. The locked interpreter passed. An intermediate root check found
an import-order issue, corrected before the complete clean pass.

Ordinary CI has no private original recordings; recorded native AMD64 qualification
is unavailable. No private recordings are uploaded under the accepted local-only
terms, and synthetic native CI is not described as recorded evidence.
Owner semantic/completeness review, resolved PR review, authorized merge and
successful merged-commit qualification remain outstanding.

## New-image recorded pass and native timer observation

Project `detectbridge-p13-recorded-c111aa03e3` passed on the dedicated message-free
logger image, with the unchanged 8dbd7e4 recorded runner and original expectation
freeze. It again verified 99 admissions, 32 logical events, 223 logical/233 physical
outputs, ten exact duplicates and 76 search documents, all four lags zero and all
three semantic mutations rejected. Deadline checkpoint 9 and tagged rejection
checkpoint 34 retained the required original memberships.

- Integration bundle: `bcecf7fea64de1fbb8d738b40c582f94e305f23550d9eb13ad993796f21b7d9b`.
- JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- ARM64 image: `sha256:7e42a42b33d355309d6ffc87de294de20165085a4a4c7e41b3c8b37cc3bf755c`.
- Evaluation bundle: `46da2a80e8972b73b85b20ea66987b643b145241dd34bb550e5bdfd8c3e2ecea`.
- Writer bundle/JAR/image remain d78eda0/6f60d35/eef0171, as fully expanded above.
- Private result: `.cache/search-writer-reports/detectbridge-p13-recorded-c111aa03e3.json`.
- Private log: `.cache/p13d-recorded-message-free.log`.

Native fdca907 run 44188937618 passed search and P08 writer verification but
integration failed at the broker-pause first-restored-checkpoint assertion, before
required-sink interventions. Original artifact 14376297867 was collected before
diagnosis; ZIP SHA-256
`6368fef22c9dfff8b3c0099ed6e0d7e60bf2e5472c831550355374ca261630e9`.
The actual job exception history was empty; no root-OOM marker appeared in actual
worker logs. This does not establish the cause of earlier TaskManager exits.
The first checkpoint need not follow the operator's 500-ms timer. The qualifier
now waits boundedly for the timer transition in completed state, requires the
original membership/opened/deadline to remain identical until closure and requires
the exact frozen manifest in the completed outbox. It saves first/latest original
inventories. The regression allows a pre-tick checkpoint and rejects deadline
reset. No production artifact, deadline, sink assertion or resource budget changed.
See the owning [design addendum](p13d-design.md).

The published sixth commit batches this qualifier correction, meaningful regressions,
stronger independently frozen original authentication assertions and diagnostic
retention. Published CI boundaries justify the additional commit; no history was
rewritten. Native run 44192849293 on 779c70a remains in progress; its results are not yet
acceptance evidence. The stronger ARM64 recorded run is complete below.

## Indirect prerequisite and P14 dependency audit

P05 #26 and P09/P10 #34/#36/#37 were also inspected, including exact PR heads,
merge artifacts, history-restored tree equality and successful applicable runs.
All four review-thread lists are empty. The acceptance map retains the exact
SHAs/run IDs without assigning historical CI to rewritten history. P05 issue #5
is closed; its bounded local replay does not establish archive implementation.
P09/P10 issues #9/#10 remain open with independent expectation review explicitly
pending in their original PR bodies/designs. Owner authorization to proceed with
P11/P12 is preserved separately. The concrete original-case/hash/rationale packet
is ready at [prerequisite review](p13-prerequisite-review.md); no acceptance or
issue closure is fabricated from successful checks or merges.

Native 779c70a run 44192849293 assembly-verification failed during bootstrap
`gradlew help`, before assembly tests/runtime, on Maven Central HTTP 429 for
`org.jdom:jdom2:2.0.6.1` through pinned plugin resolution. Original job
134426563765 log is retained at
`.cache/p13d-diagnostics/779c70a-assembly-original.log`, SHA-256
`a8c03ab11941939e88db12eb490dae0f15679a635594dc92b29f8a6b934d0878`.
No dependency/version/repository/checksum or test assertion is changed to bypass
this failure. It is not assembly runtime evidence or a successful aggregate.

## Complete original authentication/source assertions on 779c70a bytes

Project `detectbridge-p13-recorded-aa6de5f924` passed all recorded gates with the
stronger independent source checker. Before Docker creation it froze selected
RFC5424 header/user/address fields from the accepted original bytes and unchanged
catalog action expectations, then checked complete source fields, context,
classification/ECS, quality, assembly and source time against actual event output.
This supplements the original source/count/membership freeze without changing
recordings, source policies, independent outcomes or the twelve-rule plan.

Both replays passed all 99 admissions, 32 logical events, 223 logical outputs and
76 source-derived search documents, with all four writer lags zero. This execution
had 232 physical outputs with nine byte-identical stable-ID duplicates; physical
repetition depends on recovery delivery and every copy is accounted for, rather
than assuming the earlier execution's ten repeats. Logical kind counts are exactly
the unchanged 32/6/38/20/28/0/99 table above. Host/count/attribution mutations failed
with the exact independent-expectation category. Deadline checkpoint 9 and tagged
RecordTooLarge checkpoint 33 retained original memberships, followed by required
healthy explicit restore and strict writer restart.

- Recorded runner SHA-256: `08fc920a3f3828c304d0b159ff8b054f9c44869c134a0a7d731b563b7aef66f6`, committed in `779c70a708a38a259b2b335ab44c39067bca8678`.
- Integration bundle: `bcecf7fea64de1fbb8d738b40c582f94e305f23550d9eb13ad993796f21b7d9b`.
- JAR: `e1834614797a639dc5edc1d7d18b6a6b01e71581d7e6098700fe026c56fec50a`.
- Actual ARM64 image: `sha256:b82b6a561dbae37dba614349a10d6cf53118c0513df70ccb5bc7630203e2eeef`.
- Evaluation bundle: `46da2a80e8972b73b85b20ea66987b643b145241dd34bb550e5bdfd8c3e2ecea` (built before the 779c70a publication, retaining fdca907 rule provenance).
- Writer bundle/JAR/image: unchanged d78eda0/6f60d35/eef0171, fully expanded above.
- Private pre-runtime source-expectation file SHA-256: `38a13ace2d733ef4449cc5f5c4b597eb33ec9b72ff4043f0f980b833400e4bc8`.
- Private result `.cache/search-writer-reports/detectbridge-p13-recorded-aa6de5f924.json`, SHA-256 `1e0c436079b1c06cfb1ad6245a907796805f250e1d16e17a07196288bf563893`.
- Private log: `.cache/p13d-final-auth-recorded.log`; tool snapshot: `.cache/p13d-779c70a-tool-hashes.json`.

The actual-image six-case privacy probe also passed during this build. Its new
image ID is attributed separately from c111aa03e3 even though the immutable build
input bundle/JAR/plan hashes agree; no image reproducibility claim follows.
Owned runtime containers/volumes were removed. Original inputs and generated
expectations/observations remain ignored. No native AMD64 recorded acceptance,
throughput, archive or unobserved source/error outcome is claimed.

## Completed P09/P10 owner semantic prerequisite gate

On 2026-11-17, the owner reviewed the concrete 32-case expectation/rationale/hash
packet and explicitly selected “Accept bounded P09/P10 semantics and limits.”
The reviewed pre-acceptance packet hash was
`b1e5de2fe1e57ab3e4af11a14909f20d2f6d7e4597c247f8a8795f030e82210a`.
The two fixture hashes remain unchanged in the packet. Issues #9/#10 were then
closed as completed with the exact owner disposition, historical/restored artifact
and refreshed CI references in their bodies. This supersedes the initial audit's
pending-review status above and historical caveats in earlier designs/ledgers.
P11/P12 accepted scope is preserved. No P13 acceptance or merge authorization is
inferred from this separate prerequisite decision.

## Pinned connector failure reproduced and bounded cleanup correction

Final 779c70a native run 44192849293 passed every other applicable job, except
integration and the separately recorded pre-test assembly bootstrap HTTP 429;
required-checks failed closed. Original integration artifact 14377883509 was
collected before assigning a cause. Its ZIP SHA-256 is
`64cd431f52728342989b6304d0a31b959ddcc0cf95b7ce1f4cfba8e685148597`.
Tagged and detection faults passed at checkpoints 66/78; processing failed with
TaskManager exit 1, OOMKilled=false and unavailable resources. Actual message-free
Task/TaskExecutor/TaskManagerRunner fatal origins all identify
KafkaWriter.checkAsyncException line 297, with no root-OOM marker. Pre-processing
VM observations are in the owning design; no speculative resource tune followed.

Fresh ARM64 project `detectbridge-p13-test-daac90fd3c87` reproduced the same fatal
origin during processing-sink rejection. Tagged/detection passed at checkpoints
42/49. Its broker pause and corrected deadline checkpoint passed at checkpoint 36
with zero open groups and the exact retained manifest intent. This is a failed
full integration run, not superseded acceptance. Original taskmanager logs hash
`81e2a72d9442a12d369a4cbdfc0f37ec804ed3ab8f864a94188f0a535ac2cb55`;
current-job exception JSON hash
`3afc13cacf5508822ee731990d8f5fb34ef5edf7bee96387f8c420f1affefa04`.
They remain in the ignored project folder. It used bundle
`e5716219a48ab3260d10cde9d30689a5988af971ff8675a77e0fb66d482c9002`,
JAR e1834614 (fully expanded above), ARM64 image
`sha256:624ddd14eae4b7223b1084bda4e5d4904f2b796d6ec68a401a6a6e5e33810704`.

The exact pinned 5.0.0-2.2 connector callback bytecode and Flink 2.2.1 cleanup
source explain how a second send error can be re-armed after the first was thrown
and then rethrown after producer closure, making task cleanup fatal. This matches
[the upstream report](https://issues.apache.org/jira/browse/FLINK-41269), whose
proposed Flink-wide suppression remains unmerged. The historical missing original
probe/worker exceptions remain unclassified; this does not fabricate their cause.

`1645359a1c7ced9efc6a5f514e671b78febb6d21` adds a unique P13-only subclass of the
unchanged pinned sink/writer. The actual pinned writer regression deterministically
reproduces the stock secondary-close failure. Guarded write, flush and executed
mailbox actions propagate the first failure unchanged. Only a secondary send
IOException after stock producer closure, with an already-propagated first error,
is attached as suppressed and counted. First close-only, resource-cleanup and JVM
errors remain exceptions. Both checked IO and runtime cleanup failures are tested.
No acknowledgement, state serializer, original evidence, deadline, sink marker,
resource bound or OpenSearch commit behavior is weakened. The accepted deployment
remains at least once; transaction configuration is outside this bridge's scope.

All five actual-writer Java regressions and seven owning Python integration checks
passed. An initial compile used an ambiguous inherited nested Context name; the
explicit enclosing class fixed it before qualification. Locked combined Java then
passed all legacy/mapped/capability semantics and existing source/writer consumers;
search component checks passed eleven Python regressions. Root checks passed 169
Python tests, contracts, hygiene/secrets, lint/format/types. Logs are
`.cache/p13d-cleanup-{integration-final,java,search-components,final-check}.log`.

Fresh ARM64 production JAR SHA-256 is
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
Its default-plan build bundle is
`2544f8b9ab4b4690fae7210a6fa6e73ebd684f60ee4a8c670db3434a3c805b2f`,
ARM64 image `sha256:8a2a12cd940d7ed414686c78ec880764b4f0fc39ed9b560e865dc09f2ce29051`.
Full integration, recorded and synthetic search qualification are running serially
on fresh isolated projects; native run 44196952063 is in progress. Earlier e1834614
passes are not reassigned to this new artifact. Final evidence follows completion.
The seventh published commit is the necessary deterministic runtime-fix/native
qualification boundary; a consolidated evidence commit remains separate.

## Complete ARM64 integration recovery on the cleanup-guard artifact

Project `detectbridge-p13-test-6deb370fcd54` passed all full integration gates on
1645359 source bytes: 44 admissions, twenty logical events, 103 logical outputs
and 145 physical outputs. Exact incompatible-binding rejection, healthy explicit/
JobManager restore, TaskManager recovery, the actual 40-second broker pause,
original absolute deadline, all seven required sink failures, source metrics,
original Kafka hashes and stable duplicate bytes/IDs passed. Processing rejection
retained two intents at checkpoint 60; the worker stayed available for healthy
restore and the remaining fault cases. Completed blocked checkpoints were
45/52/60/68/76/84/92 for tagged/detection/processing/manifest/preservation/quarantine/
receipt respectively. No worker restart or marker waiver was added to mask a fault.

Bundle `2544f8b9ab4b4690fae7210a6fa6e73ebd684f60ee4a8c670db3434a3c805b2f`,
JAR `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`,
ARM64 image `sha256:8a2a12cd940d7ed414686c78ec880764b4f0fc39ed9b560e865dc09f2ce29051`,
evaluation bundle `6777e4e326861314c87011d0e87923850fe080d0c3a9aca8b10624b1cc8bf870`.
Private report `.cache/integration-reports/detectbridge-p13-test-6deb370fcd54.json`
has SHA-256 `268f66144ffa91e6f6dacdc582f419dfbf45805309b00113492778dcfd559b5c`;
log `.cache/p13d-cleanup-integration-runtime.log`.

A read-only inspection retained the actual failed processing job's original
RecordTooLarge exception with its suppressed secondary error before owned cleanup.
File `processing-failure-propagation.json` in that project folder has SHA-256
`3531aa339e6d807f187f84187b6e22d59589f734cb8c254293fb96df98342425`.
The first inspection queried pre-JobManager-restart historical IDs and encountered
an unavailable REST entry; querying the current JobManager's actual archived-job
overview retained the correct fault. This read error does not change qualification.
The exception/healthy-worker evidence supports the deterministic pinned-writer
regression: the primary required failure remains visible while its redundant
post-cleanup error is suppressed. All owned stack containers/volumes were removed.

## Native cleanup-guard search qualification

Run 44196952063 search-verification passed on 1645359. Project
`detectbridge-p13-search-51da874024` qualified 35 source admissions, 21 logical
events, 48 source search documents, all six nonzero outcomes and two isolated runs.
Ten controlled topic admissions produced eight logical/physical writer-failure
references. Actual outage/recovery, duplicate/conflict/tamper, failure-topic
publication/indexing backpressure, index-before-uncommitted-crash ordering,
partial bulk, denials, drift/TLS and retrieval assertions passed; all four lags zero.
This is native synthetic evidence, not private recorded qualification.

- Source bundle: `cb5cb9bac05669333fcedf489ed8b3406cc932b79ee65e395a2147eb7f16c2dc`.
- Source JAR: `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
- Native source image: `sha256:7110b236695d852a8bfa6b5f947fbc337705ab76173b6fcba30d838ea0a31c78`.
- Writer bundle: `d78eda0c3c632a108bd89819663c8cc1c6928a1e9c76c13e2eaa274273e05fd4`.
- Writer JAR: `6f60d3589d502bee41dc926c768c130b91e6437f28d115daef8775486593a575`.
- Native writer image: `sha256:315a37899498683bc6333de24eabda42087a43c568ee2f36657aeb8a8a57ca30`.
- Original decoded job log: `.cache/p13d-diagnostics/1645359-search-original.log`, SHA-256 `85b164056a8fdf573f90a69e2eadb87adf07c29baaca9cfcd7a8a59e7a034147`.

Native integration/assembly/detection remain in progress at this observation.
They and the final aggregate are not yet claimed successful.

## Complete ARM64 recorded source-to-search on the cleanup-guard artifact

Project `detectbridge-p13-recorded-8348892e80` passed all stronger original-source
and search assertions on the new 51a984de JAR. The unchanged literal freeze and
accepted catalogs were verified before runtime creation; complete selected
RFC5424 fields/context/time, Windows source/System fields, audit argument/PATH
membership, all matches/nonmatches/counts/quality and version attribution passed.
Two isolated runs retained stable event/evidence identities and disjoint processing/
detection identities. Exact source/Kafka retrieval hashes, original manifest and
controlled late links passed. Recorded coverage and supplemental synthetic/error
coverage remain separated exactly as in the frozen design.

There were 99 admissions, 32 logical events, 223 logical outputs and 76 search
documents. All logical kind counts remain 32/6/38/20/28/0/99. This execution had
233 physical outputs with ten byte-identical stable-ID duplicates. All four writer
topic lags were zero. The exact host/count/attribution mutations failed with the
independent-expectation category. Completed original-member checkpoint 8 supported
TaskManager/deadline recovery; checkpoint 35 retained the required tagged intent
under actual RecordTooLarge, followed by healthy explicit source restore and strict
writer restart. All original source/context/terms assertions remain unchanged.

- Integration bundle: `9c4fcde935e991467ac000d9ae30c690cf48c36543a5f429fadf589cbe071cfc`.
- Integration JAR: `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
- ARM64 integration image: `sha256:11355e5fbcb17fd04381d75100897891fa3e6f9ff753fc5a322f824ba107167f`.
- Evaluation bundle: `c5a59cb4996fa39424aa3b30e9d978f65ff0a92fbb34a3aace3f833dd882a11c`.
- Writer bundle: `d78eda0c3c632a108bd89819663c8cc1c6928a1e9c76c13e2eaa274273e05fd4`.
- Writer JAR: `6f60d3589d502bee41dc926c768c130b91e6437f28d115daef8775486593a575`.
- ARM64 writer image: `sha256:eef0171af4dccb0922e069190f96bce412b181b71b53926bc9d22be5935cfced`.
- Private result `.cache/search-writer-reports/detectbridge-p13-recorded-8348892e80.json`, SHA-256 `93e97c4f0e8dfd8e2c89bfd68a5f44c295038c29ddceb6b9001ee7e8516f23ec`.
- Private pre-runtime source-expectation file SHA-256: `38a13ace2d733ef4449cc5f5c4b597eb33ec9b72ff4043f0f980b833400e4bc8`.

Recorded runner bytes are the unchanged 08fc920a hash fully expanded above,
committed in 779c70a; the production cleanup guard is committed in 1645359.
Original inputs, contexts, frozen runtime expectations, source acknowledgements/
observations and checkpoint inventories remain ignored. The private log is
`.cache/p13d-cleanup-recorded-runtime.log`. Owned containers/volumes were removed.
No private original or credential was uploaded/committed; native AMD64 recorded
qualification remains unavailable. This successful recorded run is technical
evidence, not owner P13 acceptance or merge authorization.

## Native assembly prerequisite recovery on 1645359

Run 44196952063 assembly-verification passed actual native AMD64 project
`detectbridge-p12-test-3031848d3314`: 52 inputs, ten groups, 83 logical/92 physical
outputs and nine stable duplicates. All five required sinks retained original
intents at checkpoints 63/70/78/85/93. Actual 40-second broker pause retained the
original deadline at checkpoint 56; explicit/JobManager/TaskManager/incompatible
restore checks passed. Both limits and byte-pressure profiles passed, including
closed-budget rejection with original source offset 8 retained. This supplies
fresh successful assembly evidence after the earlier unrelated bootstrap HTTP 429.

Bundle `9cba7aed38a1dfd2a3ad57e46cb785cb7863807a13809afa41bfb0c95dad2f15`,
JAR `d341724639876de0e09a5006bf2e265172a75cd16b7d03b495dc1f4086d19a99`,
native image `sha256:f3a5911f15f9bd47cd2af7df029127c655e0ae95948a8a11c5f5d23db1d5fdde`.
The original decoded job log is `.cache/p13d-diagnostics/1645359-assembly-original.log`,
SHA-256 `e808f0bd3d74892a90fd03672c603bd62fcb3fd1ea5f9adbb01664f0ef9b9651`.
The unchanged assembly JAR/bundle also have the separately attributed complete
ARM64 recovery/resource evidence above. Neither execution claims archive capacity.

## Complete native integration and applicable-check aggregate

Implementation head `1645359a1c7ced9efc6a5f514e671b78febb6d21` passed every
applicable job and required-checks in
[44196952063](https://github.com/TravisMa07/DetectBridge/actions/runs/44196952063).
Optional acquisition/recorded jobs were deliberately unselected, not passing
recorded evidence. Native project `detectbridge-p13-test-2b7986986097` passed
44 inputs, twenty logical events, 103 logical/145 physical outputs, the actual
40-second broker pause, exact incompatible binding rejection, TaskManager/
JobManager/explicit restore, metrics, original hashes and all seven required sinks.
Processing rejection retained two intents at checkpoint 95. Blocked checkpoints
were 67/81/95/109/124/138/153 for tagged/detection/processing/manifest/preservation/
quarantine/receipt. The cleanup guard therefore qualifies the original strict
failure/recovery assertions on both actual architectures, with no worker restart
or unrelated-failure waiver added to the sink loop.

- Native integration bundle: `cb5cb9bac05669333fcedf489ed8b3406cc932b79ee65e395a2147eb7f16c2dc`.
- JAR: `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
- Actual native integration image: `sha256:20b9dbc5364cec23a66fb5eb643db98568b4e6dd78ba78a18260ae0fc6f3f6d0`.
- Evaluation bundle: `fee1dcd33d2bbbfd79956da9b1d0c4415563d5511186b6a415204c03910092f1`.
- Original decoded log: `.cache/p13d-diagnostics/1645359-integration-original.log`, SHA-256 `55a028e7eb5c6825369ab9eabd19f23202e52ac3ea9c7d91831817e9be7fb433`.

Native search's actual image ID is separately recorded above, despite agreeing
source bundle/JAR inputs. ARM64/native plans retain their actual source-revision
attribution and hashes; they are not assumed byte-identical across CI checkout
contexts. Native detection also passed actual legacy/mapped semantics and recovery,
P08 compatibility passed, and assembly/resource-pressure checks passed as recorded.
The success applies to the exact implementation head and artifacts, not to the
older failed merged-main commit, a future documentation head, or an authorized
future merge. A successful final PR-head run and merged-commit run remain gates.

## Complete ARM64 synthetic writer qualification on the cleanup-guard artifact

Project `detectbridge-p13-search-9ee15959ab` passed the full synthetic suite:
35 source admissions, 21 logical events, 48 source search documents and two
isolated replays. All six nonzero outcomes, exact time/doc-value cases, outage/
recovery, stable duplicates, conflicts/tamper, required failure publication and
indexing backpressure, indexing-before-uncommitted-crash recovery, actual partial
bulk, all permission denials, credentials/mapping drift, TLS, retrieval hashes,
metrics and value-free logging passed. Ten supplemental output-topic admissions
produced eight exact logical/physical failure references. All four topic lags zero.
No synthetic control admission is relabelled as an original recorded occurrence.

- Integration bundle: `2544f8b9ab4b4690fae7210a6fa6e73ebd684f60ee4a8c670db3434a3c805b2f`.
- JAR: `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
- Actual ARM64 source image: `sha256:574a6f350ea103ed6d7e45ebfe54297ec79b99dc489ccb58bbde611f771e3fb4`.
- Writer bundle: `d78eda0c3c632a108bd89819663c8cc1c6928a1e9c76c13e2eaa274273e05fd4`.
- Writer JAR: `6f60d3589d502bee41dc926c768c130b91e6437f28d115daef8775486593a575`.
- ARM64 writer image: `sha256:eef0171af4dccb0922e069190f96bce412b181b71b53926bc9d22be5935cfced`.
- Private result `.cache/search-writer-reports/detectbridge-p13-search-9ee15959ab.json`, SHA-256 `1aa9c508895e9de0ef969de09ba7931db4c5cea04e5e3efe3b1db474197cc1eb`.
- Private log: `.cache/p13d-cleanup-search-runtime.log`.

The final serial driver completed integration, recorded and synthetic writer suites
with exit zero. Only owned project containers/volumes were removed. Final source
bytes are committed in 1645359; remaining changes consolidate qualification and
owner prerequisite acceptance documentation. No original, credential or generated
evidence is committed. The consolidated evidence commit does not transfer checks
to itself: final PR-head CI must pass separately. P13 owner semantic/completeness
acceptance, resolved review, authorized merge and merged-commit success remain.
