# P13d recorded acceptance and recovery qualification

Status: pre-implementation design and independent-expectation freeze. Base
`0f6d758b8228a3ccce35f1af83174addc4835126`. Preserve A02–A07, all existing
contracts, source policies, checkpoint bindings and writer ordering. P14 remains
unimplemented and blocked until P13 acceptance, resolved review, authorized merge
and successful merged-commit checks.

## Recorded inputs and oracle

Reuse only the accepted catalogs `windows-process-lab-v1`,
`linux-audit-execve-lab-v1` and `openssh9-password-lab-v1`. Before runtime creation,
validate every original artifact, terms, native framing/action relations and actual
capture/host/generation evidence with the owning recording verifiers. Freeze
catalog/source/mapping/rule hashes and complete prepared input contexts locally.
Missing originals fail explicitly; never synthesize replacements or infer identity
in older public Windows recordings. Private originals and generated evidence stay
ignored. Explicit directory arguments permit reuse of accepted local caches.

Compile the existing nine P13b fixture rules plus the three committed P11
controlled-recording rules into a separate immutable qualification bundle, retaining
original rule provenance. The deployment artifact binds the actual plan bytes;
ordinary synthetic qualification keeps its existing nine-rule plan and assertions.
The twelve-rule order is four `71100000` rules, three `71110000` rules, then five
`72000000` rules, sorted by UUID. Expectations below follow literal predicates and
source capability/quality policies, never observed evaluator results.

| Recorded event | matched | unmatched | inapplicable | configuration blocked | quality skipped | evaluation error |
| --- | --- | --- | --- | --- | --- | --- |
| Security/Sysmon cmd (two) | 1 | 4 | 7 | 0 | 0 | 0 |
| Security/Sysmon hostname (two) | 0 | 5 | 7 | 0 | 0 | 0 |
| Eligible audit probe (one) | 1 | 4 | 6 | 1 | 0 | 0 |
| Insufficient audit groups (nine) | 0 | 0 | 6 | 1 | 5 | 0 |
| Password success/failure (two) | 0 | 1 | 11 | 0 | 0 | 0 |

Matches are precisely `71110000-0000-4000-8000-000000000001` for cmd and
`72000000-0000-4000-8000-000000000005` for the audit probe. Unsupported audit
CommandLine is bit 9 (`200` hex), including skipped groups; skipped Image
membership is bits 2,6,7,8,11 (`9c4` hex). Sysmon service-state is preserved
unsupported; nine auth rows are preserved unsupported; three native audit rows
are extraction failures. No fabricated event/outcome is expected for them.

The baseline per run is 46 original records, 16 logical events, ten manifests,
13 preservation documents and three detections. Explicit run-end controls close
original audit membership. A duplicate of an already admitted record must remain deduplicated. A separately
identified qualification admission reuses one original audit body with an explicit
new dataset cursor at position 1000; it must link the closed original manifest as
late evidence. That cursor is a controlled qualification input, not an original
recorded occurrence or a new capture. Two full runs retain event/evidence identity and
isolate all processing/detection identities. Duplicate physical deliveries must
have identical bytes and keys; every acknowledged input has one logical receipt
and independently verified original Kafka retrieval hash.

Reuse the independent Windows source assertions and exhaustive audit token/source
verifier; retain native auth expectations. Check full output versions, attribution,
counts, rule metadata, immutable memberships, quality and search projection fields,
not counts alone. Add same-count semantic mutations against actual observations.
Recorded evidence does not cover all six nonzero outcomes: error/budget, malformed,
missing identity and other edge coverage remains the separate synthetic suites.

## Recovery and delivery

Diagnose merged-main integration failure from original diagnostics before assigning
cause. Artifact 14358080606 (ZIP SHA-256
`b9fb795f149d3792ca938df11704f3abbf16e2dbd0ff90f50eb67c07625f290b`)
records an integration failure during the incompatible-restore phase. Its
exception handler retrieved the tracked original job, not the separately submitted
probe. The retained TaskManager heartbeat exception therefore cannot establish
the probe failure cause; it may reflect the earlier intentional kill. All three
containers were running without OOM at observation. Never count that failure as the
required incompatible-binding rejection or weaken the assertion to accept it.
Collect more diagnostics/reproduce before deciding a runtime correction.

Recorded qualification must exercise checkpoint/deadline recovery and a real
required-sink rejection retaining exact original recorded members, healthy restore,
two isolated replays and source-to-search retrieval. Existing full integration and
assembly suites retain every sink, incompatible restore, broker pause and recovery
assertion. Existing writer suite retains duplicate/conflict handling, failure
acknowledgement before commit and crash-after-indexing-before-commit ordering.
Run heavy Docker suites serially; record exact artifacts and platform separately.
Native AMD64 ordinary CI is synthetic unless the actual private originals are
explicitly available. No opt-in skip establishes recorded qualification.

## Review and completion

Produce an acceptance map and refreshed prerequisite dispositions with exact heads,
merge SHAs, runs and limitations. Preserve historical failed attempts. Carry the
standing commit-policy edits into this documentation change. Use a freeze commit,
one cohesive implementation/regression commit and one consolidated evidence commit
where possible; later published corrections preserve history. Owner semantic/
completeness acceptance and merge permission remain separate final gates.

## Qualification coordination and diagnostic refinement

Runtime inspection of the first recorded attempt established that `run_end` closes
the entire run, including Windows/authentication. All original sources must be
admitted before that control. Literal source/count expectations are unchanged;
a regression requires the global ordering. The controlled late-cursor and original
duplicate admissions remain separate from the 46-record original population.

The source tagged-route fault changes a Kafka topic policy frozen by the
independent writer. Stop the writer during that deliberate operator intervention,
restore the original topic policy, then require its ordinary strict healthy start
before search catch-up. This does not relax any producer rejection, source intent,
search field, failure acknowledgement or writer commit assertion. Retain original
writer health/offsets/logs privately before cleanup on any later failure.

Native correction run 44177420786 passed search but failed processing-sink
qualification. Original artifact 14371921401 has ZIP SHA-256
`10464b27abdb3509d21e8b8c81ff627d489c2af85b24d79283340c6e0aa9179b`.
Its TaskExecutor shutdown/NoResourceAvailableException and exited-1/non-OOM
container state do not establish the process exit cause. Add bounded original
container logs, service labels and TaskManager/slot observations to the synthetic
failure artifact; retain the exact producer-failure requirement. Separate probe
and subsequent healthy-restore diagnostic targets so an earlier expected probe
exception cannot be mistaken for a later failure. No speculative runtime, retry,
heap, resource-budget or failure-marker change is justified by those observations.

The published CI correction/diagnostic collection requires an additional cohesive
commit before native reproduction, followed by a consolidated final evidence
commit. Preserve published freeze/implementation/fix IDs under the SDLC exception;
do not rewrite history to force the original 1–3 planning target.

## Message-free native throw-site diagnostics

Native 1bf1183 run 44181348320 reproduced the TaskManager exit during healthy
processing-sink restore, after the exact required rejection had passed. Original
artifact 14373263043 has ZIP SHA-256
`d9cc5d46552c9daa5c26c0792e13a1c7937919d0cfa4962254060539abc940d0`.
It confirms taskmanager exited 1 without container OOM, but the console layout
intentionally omits all messages/throwables. Retaining those existing logs cannot
recover an exception origin that was never emitted. The cause remains unassigned.

Use a separate P13 integration logger retaining only JSON-escaped throwing stack
frame class, method and line. No message, exception body, event field or raw stack
text enters routine logs. P07/P12 and writer logging profiles remain unchanged.
An original synthetic Java probe compiles with the pinned JDK and runs against
the exact pinned Flink image's Log4j backend during integration image build. It
requires six valid metadata rows and rejects ordinary, nested and custom-toString
message leakage. A fixed root-OutOfMemoryError marker distinguishes direct and
wrapped VM errors without publishing the rendered exception text; a class-like
string inside an unrelated exception message must not set that marker. No new Maven dependency or classpath plugin is introduced.
[Log4j's exception property reference](https://logging.apache.org/log4j/2.x/manual/pattern-layout.html)
defines the selected stack-frame properties; actual-image verification is the gate.

Capture bounded VM heap/metaspace/thread metrics and actual thread dumps before
each synthetic sink case, plus existing terminal logs/state, to distinguish a
blocked cancellation from allocation/registration failures using original evidence.
These are diagnostic observations, never recovery sources, runtime or performance
acceptance. Private originals are not present in ordinary CI. Preserve every
failure assertion and resource budget; no runtime cause or speculative tune is
established by this observability change. A further published diagnostic commit
is required to collect this native evidence without exposing source messages.

## Complete accepted authentication source-field assertions

The accepted P12 design freezes preservation of RFC5424 header strings, and the
accepted catalog freezes every original framed/native byte before P13 evaluation.
Strengthen the recorded oracle to compare every retained header field, user and
remote address against those original frames, including display hostname, PRI,
PROCID, MSGID and NIL structured data. Derive these expectations independently
from the selected original password frames and catalog action expectations before
any runtime creation; never use adapter/evaluator output. No new recording value
or source policy is introduced. Freeze the derived map privately with its input
catalog hashes; keep the public twelve-rule count/membership freeze unchanged.

Also require the original context extension, declared ECS/source classification,
trusted ID-only host projection, standalone assembly and eligible/no-diagnostic
quality for the two selected valid password records. Header display names must
remain source fields, without manufacturing host identity or a normalized hostname.
Same-count header/context mutations must fail independently of processing-ID
checks. Other auth grammars and skipped/error cases remain supplemental synthetic
coverage; this oracle is bounded to the accepted original captures.

## Native broker-pause checkpoint observation

Run 44188937618 on `fdca907` failed the assertion that the first restored
completed checkpoint already contained the timer closure. Its original artifact
14376297867 has ZIP SHA-256
`6368fef22c9dfff8b3c0099ed6e0d7e60bf2e5472c831550355374ca261630e9`.
The current-job exception history was empty; this was an oracle assertion, before
required-sink interventions. This does not establish the cause of the older
TaskManager exits. No runtime resource or restart-policy change follows from it.

The operator schedules bounded ticks at 500 ms after opening. The accepted design
retains absolute deadlines across downtime; it does not order the first restored
checkpoint after that timer. The qualifier now observes completed checkpoints
until the original group closes, requiring exact unchanged membership/opened/
deadline metadata while pending and the exact frozen manifest in the durable
outbox when closed. It still pauses the actual broker for 40 seconds, restores
from the completed retained checkpoint, and checks timeout output independently.
The first/last inspected inventory is saved privately for failure diagnosis.
A regression supplies a completed snapshot before the tick, followed by closure;
a changed deadline must fail immediately. The bounded timeout remains a failure.

## Pinned Kafka writer cleanup after an already propagated send failure

Native 779c70a artifact 14377883509 (ZIP SHA-256
`64cd431f52728342989b6304d0a31b959ddcc0cf95b7ce1f4cfba8e685148597`)
and ARM64 project daac90fd3c87 reproduce TaskManager exit 1 during processing-sink
rejection. Native message-free fatal origins are KafkaWriter.checkAsyncException,
line 297, on Task, TaskExecutor and TaskManagerRunner; root-OOM is absent. Before
this case, heap used/max was 159320064/436207616, metaspace
117121712/268435456 and Java threads 52. These are observations, not capacity
qualification. No resource increase follows.

The exact pinned connector 5.0.0-2.2 bytecode clears its pending send error when
throwing it, but subsequent callbacks can re-arm it. Its close first closes and
checks the producer, clears currentProducer, then rethrows a pending send error.
Flink 2.2.1 treats a failing cleanup as fatal. This is consistent with the observed
fatal origin and [FLINK-41269](https://issues.apache.org/jira/browse/FLINK-41269),
not retrospective proof of the unretained historical exceptions. The upstream
[Flink proposal](https://github.com/apache/flink/pull/29676) remains unmerged and
maintainers intentionally retain fatal handling for unsafe resource cleanup.
No released newer connector is present in Maven metadata as inspected 2026-11-17.
Do not patch that Flink-wide safety policy, waive RecordTooLarge, or merely restart
a worker to hide this failure.

Use a narrowly scoped P13-only subclass of the unchanged pinned Kafka sink/writer.
It retains the stock at-least-once writer, serializer, state serializers, producer
properties, acknowledgements and flush/checkpoint behavior. A package-access bridge
has a unique DetectBridge class name; it does not replace an upstream class or use
production reflection. Record the first exception propagated by write, flush or
an executed mailbox action. On close, a duplicate pending-send IOException may
be attached as suppressed to that already-propagated original exception only if
the stock writer has fully closed and checked the producer and set its protected
producer field to null. Increment a bounded counter for this cleanup condition.
A first/unobserved close error, a producer cleanup failure before that proven
closed boundary, and any Error still propagate. Normal writes, flush and first
mailbox errors always propagate unchanged. The original task therefore still
fails, required output remains unacknowledged, and completed-checkpoint intent
recovery is unchanged; only the redundant error after successful cleanup avoids
TaskManager-fatal escalation.

Before runtime qualification, regress the actual pinned writer's callback/flush/
write/mailbox/close sequence deterministically: propagate first RecordTooLarge;
re-arm a second failure and require closed resources plus suppressed secondary
error/counter; reject close-only and actual cleanup errors; never suppress a JVM
Error; preserve normal close and mailbox forwarding. Use no new Maven dependency.
New job bytes intentionally change the existing artifact-bound checkpoint binding;
qualify fresh isolated projects rather than migrate an old checkpoint. Require
all seven exact required-sink failures/restores on ARM64 and native AMD64, plus
actual recorded source-to-search and writer regressions on the new artifact.
Remove/review this compatibility bridge when the pinned connector changes.
