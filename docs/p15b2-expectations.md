# P15b2 independent archive and replay expectations

Derived on P15b1 main `3fe77bbf570e59521633a218288f2144e2159113` before
P15b2 implementation. A02–A07 and the [P15b freeze](p15b-expectations.md)
define preservation, worker attribution, closure-time policy and isolated replay.
The source packet, original rule YAML and documented key formulas determine the
following results. Each row is an acceptance criterion awaiting execution.

## Exact inputs, memberships and decisions

The [source packet](../contracts/lifecycle-runtime/v1/fixtures/source-cases.json)
has SHA-256 `7d7275281e2883d8a3d459d7bf71780e55e19b11a7259d7d0b914e5f57e50be8`.
The [independent six-run expectations](../contracts/lifecycle-runtime/v1/fixtures/expectations.json)
have SHA-256 `4d66ed2ac69e1ecbeeb6c2ffd78a838a04312c254fe60850177118c91dc14b8a`.
Use their literal cursors, inline evidence including LF, original physical
admission order, per-phase context hashes, sorted member IDs, revisions and full
compact outcomes. An independent standard-library hash calculation over the
packet verified all fourteen evidence hashes, native cursor IDs, four sorted
memberships and four source event IDs against the frozen literals.

| Case | Native cursors and original assembly | Expected source event ID (after `sha256:`) | Bundle A match | Bundle B match |
| --- | --- | --- | --- | --- |
| Security Alice | `p15b-security-alice`, standalone | `e71956dcadd561f4805c39154a6bb4717677e84c7eb5f40b262dbb5061bfaf30` | Windows A | None |
| Security Bob | `p15b-security-bob`, standalone | `b83097a4ca34933784fb2679198435e1a64b5a94912481ade19833827bcaee15` | None | Windows B |
| Audit whoami | `p15b-audit-whoami-0` through `-5`, EOE boundary | `4461669b568b6bcb62155b2165b0bfe00a75b2203ef3c2a8912ecf8ecb8ac68c` | Linux A | None |
| Audit false | `p15b-audit-false-0` through `-5`, EOE boundary | `0cea10f8d1cf66ff49def818762b7d989ab259c9ca5fed781e357ad96068cc49` | None | Linux B |

Windows compares SubjectUserName. Linux compares the actual executable in the
six-member SYSCALL, EXECVE, CWD, PATH 0, PATH 1, EOE group. Require the original
empty middle argument, both PATH items, eligible quality and source-boundary
closure. Each matched case has counts (1,0,1,0,0,0), each nonmatch (0,1,1,0,0),
in matched/unmatched/inapplicable/blocked/skipped/error order. The match array
contains only the exact ID and YAML revision in the packet. Diagnostics are empty.
A case loses its historical proof if its raw ID, ordered member sequence, linked
manifest or bound original context changes, even if the counts stay identical.

| Selection | Output-specific attribution | Independently predicted detections |
| --- | --- | --- |
| Phase 1 | Windows run 101 on worker 20 and Linux run 201 on worker 21, original A command revision 1 | Alice and whoami |
| Mixed worker selection | Windows run 102 on worker 20 under B2 and Linux run 201 on worker 21 under A1 | Bob and whoami |
| Phase 2 complete | Windows run 102 and Linux run 202, original B command revision 2 | Bob and false |
| Rollback | Windows run 103 and Linux run 203, new forward command revision 3 selecting the original A closure | Alice and whoami |
| Explicit current B over original phase 1 or rollback | Replay Windows and Linux inputs in fresh isolated runs with selected B | Bob and false |

Run and worker numbers abbreviate the UUIDs in the packet. The mixed selection
joins committed A decisions with B decisions made during the mixed interval.
The paused audit worker produces no fresh decision during its pause. Preserve its
last completed A selection and actual B output from the active Windows worker.
Each original worker/phase run receives its own fresh current run when testing
all phases. Repeated source IDs across phases would exercise same-run
deduplication if submitted to a single new run. Keep an explicit current schedule
with the six members in order before any deadline and one final end.

The original three phases yield 42 raw admissions, 42 receipts, 12 tagged events,
six detections and six manifests, or 66 logical output envelopes. The mixed
selection reuses a subset of these physical records. All six A1/B2/A3 detections
and all six nonmatching tagged decisions require independent comparison. Under
current B across those six distinct selections there are again six matches, but
eight of twelve tagged decisions change relative to historical A/B/A. Verify
each match and nonmatch by event, original run and revision. Aggregate match
counts alone would accept an implementation that ignored the bundle selection.

## Immutable artifacts and source provenance

Artifact identities come from original files and the prior B1 inventory.
Their hashes identify bytes. Decision expectations above come from the source
and rules. Qualification records the actual artifacts used by each execution.

| Identity | SHA-256 |
| --- | --- |
| Original semantic producer/evaluator JAR | `51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d` |
| Lifecycle producer JAR | `055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d` |
| Independent compiler validator packet | `f2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d` |
| Common A/B compatibility | `ff2a1f54535aa73eec63e72717426b893c2eb9d15982e807d5b46c0ee7e736ef` |
| A bundle / exact plan file | `7828d12c4d002b0be9a18822cc1b5b2bb8ce0fb752d003e3e7b482ec97626414` / `0f4c134c2507d42fe4ebba6eb8262d3f67fab38766bc7dbcada7408de7bcadd1` |
| B bundle / exact plan file | `e4c1c66b8d7c6699dac76c0858b31d600bebe2282571562d05f79594484122e9` / `a0848ae2dbb12a3df89c7eb323183692dbc334411a126ed27ac454846254238d` |

The A and B manifest files in the retained B1 attempt12 candidate store hash to
`b4733d5947ea88a170c3053d01eae9baca4e30d0ae177e9846254a999eb22c4b` and
`abfc0c47efbf359b9ece28f7caa0e937ee9b2364e81c16a934ce4d0c779555cb`.
Verify each deployment's actual signed command, key, broker/topic IDs, worker,
incarnation, runtime binding, images and revisions. A new authority/deployment
changes effective command hashes even for identical plan bytes. Pin actual new
archive and replay executable hashes at build/qualification and bind them at
creation and resume. The [original fixture provenance](../contracts/lifecycle-runtime/v1/fixtures/README.md)
binds exact original and modified YAML, sources, license and mappings.

## Archive, replay, failure and retirement checks

| ID | Applied input or interruption | Required observable outcome |
| --- | --- | --- |
| E01 | Archive the two-worker deployment | Exactly two assigned input topics plus control, artifact, acknowledgment and output. Verify broker cluster, actual topic IDs/partitions and byte-equivalent physical keys, values, timestamp and ordered headers at every captured offset. Retain each registered original object and source binding. |
| E02 | Stop immediately before segment publication, then after durable publication before Kafka commit | First interval leaves old durable head and old commit; recover and archive it. Second leaves durable segment and old commit; reconcile the exact interval, keep the same bytes once and advance only to its verified durable next offset. |
| E03 | Same signed record at a different Kafka offset, or same offset claimed with changed bytes | Preserve both physical occurrences in the first case and one logical decision for an accepted exact intent retry. Reject a conflicting observation of the same physical position without replacement or advancing its cursor. |
| E04 | Seal original unit with absent raw member, extra member, swapped EOE, substituted output, absent plan/chunk, lost object or incompatible source mapping | Fail closed on selection or verification. Retain evidence and prior committed replay prefix; no new successful unit. Fresh evaluation must agree on complete expected output and attribution. |
| E05 | Present valid authority signature on a self-rehashed plan with AST diverging from original YAML, including P15b S12 | Keep the exact physical control/artifact/rejection evidence. Independent compiler validator rejects closure as executable in historical and current modes; prior valid policy remains available. |
| E06 | Change runtime, original producer, validator image/packet, command predecessor, original participant or broker cluster with cloned topic names | Reject incompatible/foreign bindings before emitting or accepting a successful replay result. An acknowledgment must bind its own actual command and registered participant. |
| E07 | Two fresh historical runs of identical selection; interrupt one during result write and again just after publication | Preserve original event/member/decision identity and exact original attribution in both. Derived keys are disjoint by replay run. Recover only a verified contiguous prefix, finish once, and append nothing on completed resume. |
| E08 | Tamper with a committed result or change run, selection, mode, root or executor on resume | Reject before append. Keep prior run and archive byte-identical. Verify even if advisory progress already claims completion. |
| E09 | Current run with absent/incompatible selection vs fresh explicit compatible B; workers currently rolled back to A or stopped | Reject absent/incompatible bundle. Explicit B produces the literal B decisions from archived originals and records its own references and isolated identity. No change to live worker state, historical run or original bytes. |
| E10 | Request retirement of member/input/output/command/plan/registered object reachable from sealed selection, open run or rollback closure | Block before unlinking. Keep source and complete executable closure readable. Revalidate under managed retention lock if a reference is acquired between planning and apply. |
| E11 | Unknown graph or graph version, missing catalog/hold, corrupt referenced segment or omitted inventory partition | Fail closed with no deletion. Zero matching known edges cannot establish an empty dependency set. Legacy nine-topic/archive/replay/maintenance behavior remains attributable to its original profile. |

For actual runtime results retain the original attempt, platform, source and
artifact hashes, source and broker coordinates, durable and committed offsets
around interruption, and expected-versus-observed source decisions. P14 bounded
acceptance excludes private recorded AMD64, HA, disk loss, unbounded outages and
throughput. A component pass provides no new evidence for these limits.
