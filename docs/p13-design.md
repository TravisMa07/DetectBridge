# P13 bounded design and acceptance plan

Status (2026-11-18 UTC): P13 is Done within owner-accepted bounded scope.
P13a–c and P13d #49 are owner-merged; final head 8581887 and actual merge 07e5382
passed every applicable check in 44202078968 and 44206958555 respectively.
The [acceptance map](p13-acceptance.md) records explicit owner acceptance, exact
artifacts, historical failures and limits, including unavailable private recorded
AMD64 qualification. Issue #13 is closed; P14 is Ready for design/freeze.
The earlier planning/review checkpoints below remain historical.
P08/P11/P12 prerequisites are complete within their owner-accepted bounded scope.
This plan preserves A02–A07 and ADR 0008. Concrete P13a contracts, numerical bounds
and identity preimages are in [owning notes](p13a-design.md).

## Refreshed prerequisite evidence — 2026-11-16

Fetched origin/main is 4ac31fa50cf8f3a23db89afc7436710bfe7a9a93. P11 completion
[PR #45](https://github.com/TravisMa07/DetectBridge/pull/45) is owner-merged after
explicit bounded semantic acceptance. Actual merged-main
[run 43900545102](https://github.com/TravisMa07/DetectBridge/actions/runs/43900545102)
succeeded, including Windows, Linux, assembly, detection, writer, transport and
required-checks; recorded/acquisition jobs were expected opt-in skips. P12c #43
records completed owner semantic/completeness review and explicit merge authorization.
Historical pending text below does not reopen those accepted prerequisites. Older
public Windows missing bindings remain a preservation limit of that corpus.

## Historical prerequisite inspection — before P11 completion

The initial inspection used `c02449745ddb87605d0bd85841f77fdad2fb382a`.
P11 #38, P12a #39, P12b #42 and P12c #43 are merged.

| Dependency | Observed evidence | Remaining gate |
| --- | --- | --- |
| P08 | Merge `430609a`; [merged-main run 43652317692](https://github.com/TravisMa07/DetectBridge/actions/runs/43652317692) passed actual writer qualification and required-checks; recorded ARM64 evidence in writer guide | Metadata writer only; P13 must implement its own compatible projections/configuration/index permissions |
| P11 | Merged #38; old public recordings remain skipped. New controlled Windows capture and eligible offline qualification are in [completion review](p11-recording-review.md) | Owner accepted the new bounded source scope; final-head qualification and separately authorized integration remain; old public bindings are still unavailable |
| P12 | [PR #43](https://github.com/TravisMa07/DetectBridge/pull/43) records completed owner semantic/completeness review and separate merge authorization; exact head `adf71f8`, AMD64 run 43812450381 attempt 2 passed | [Merged-main run 43873905332](https://github.com/TravisMa07/DetectBridge/actions/runs/43873905332) passed including actual linux-assembly-verification and required-checks; optional recorded jobs and unaffected Windows job skipped |

The initial P12c assembly attempt failed before tests on Maven Central HTTP 429;
the unchanged failed-job rerun passed without relaxing verification. Local recorded
ARM64 evidence and earlier failures remain in the P12c ledger. Earlier pending
review/merge text in committed documents describes historical checkpoints.

## Exact missing Windows evidence

Rehashed original Security payload `81e1d4e381f4dc38b97c48f9fa5b0ab0b098810c321b7d4599029a9f22530259`
and Sysmon payload `ee1c7cd9fa20013c82da17f8cb1998197c117ab4c209ab56203290bc90739fda`.
The Security Computer value is `win-dc-mhaag-attack-range-602.attackrange.local`;
Sysmon uses `win-dc-8537412.attackrange.local`. These display values do not prove
stable host identity or that the recordings share a host.

Rehashed metadata `eebac0c9661cabf3b1bf36f200880516e19db43a1c3680ef17e6db43c78ac4f8`
(1,259 bytes) supplies scenario/author/environment/collector paths, with no stable
host ID or authoritative capture-scoped binding. The owner reports no additional
evidence. P08 search projections have no host-binding registry; rule bundles and
synthetic fixtures cannot establish recorded identity.

Needed for each selected recorded source: authoritative capture/inventory evidence
linking its exact Computer value and source namespace/instance to a stable host ID
within the actual capture scope; original artifact hashes, origin/terms and review
references; and a reviewed binding revision/hash. Generation or known capture
configuration needs its own provenance where used. Do not infer scope from a
hostname, dataset/scenario ID, metadata date, or another recording's display name.
A canonical hash checks integrity; it does not authenticate a binding.

Then freeze independent expected normalized fields, source/quality dispositions,
and mapped rule outcomes before running the recorded adapter/evaluator. Qualify
eligible Windows matches and actual nonmatches as well as preservation cases, and
obtain separate owner semantic acceptance. Existing 7,018-row evidence remains
361 identity-missing skipped events and 6,657 unsupported preservation rows.

If original capture evidence cannot be obtained, a new controlled Windows recording
with real host/capture provenance and reviewed usage terms can be proposed. That
would qualify that new source scope; it would not repair identity in the old data.
That new controlled recording now exists with technical qualification in the
[P11 review packet](p11-recording-review.md). The owner accepted that bounded
source scope on 2026-11-16. Final-head PR qualification and separately authorized
integration remain; old recordings are unchanged.

## Integration boundary

Use a separate P13 deployment/project, versioned Kafka topics, consumer groups and
checkpoint directory. Keep P07, P08, P09, P10 and P12 qualification deployments and
contracts compatible. Reuse actual WindowsAdapter, Linux authentication adapter,
transactional audit assembler and mapped Java Evaluator; no fixture normalization
or per-event Python. Compile and validate the immutable mapped bundle once.

A bounded raw/context admission contract must bind run/source, immutable first
observation, exact retained evidence and reviewed context/snapshot hashes. Evidence
resolution uses only registered local objects and verified ranges; unavailable
objects cause retry/backlog, integrity failures cause preservation diagnostics.
Preserve P12 prepared transitions, checkpoint-prefix intents, absolute deadlines,
original membership, late links and run/host/generation isolation in the integrated
job. Do not assemble on display names or nearby timestamps. Keep record/control
admission receipts and membership outputs attributable through the new boundary.

After adaptation, evaluate P03-valid normalized events with the mapped evaluator.
Unsupported/malformed raw input remains preservation output without fabricated
normalized events or rule outcomes. Unknown context/configuration must not become
an ordinary nonmatch. Preserve source-quality diagnostics independently of rule
coverage and retain existing applicability → configuration → quality → predicate
precedence, including configuration blocking on quality-skipped Linux events.

## Versioned output and enrichment

Introduce separately versioned tagged-event, detection and compact-diagnostic
schemas with actual consumers and compatibility regressions. Wrap unchanged P03
events rather than extending the closed core implicitly. Tagged events carry
run/event IDs, six exact outcome counts, matched rule ID/revision links, original
evidence/member/manifest references, source-quality findings and actual parser,
normalizer, source, mapping, compiler, evaluator and selector attribution.

Produce one linked detection per actual match. Retain original rule provenance,
revision, bundle and mapped source attribution. Unmatched/inapplicable rules emit
counts, not one document per rule. Group blocked/skipped/error diagnostics by
category/source/bundle and a versioned immutable rule-set reference with hash and
count. Do not serialize unbounded per-rule diagnostic lists into tagged outputs;
add a compact evaluator API sharing the existing semantics and operation budget.
Keep legacy result APIs unchanged and prove exact count/match equivalence against
independently expected cases and the exhaustive evaluator.

Enrichment in this slice consists of deterministic match/coverage/quality tags and
pinned rule metadata. Carry an explicit enrichment-policy ID/version/hash and
empty external-input attribution when no lookup occurs. Future decision-affecting
lookups require pinned snapshots and historical replay support; do not add live
network lookups, AI, archive, activation, API or UI here.

Define canonical domain-separated SHA-256 identities before implementation:
processing identity includes pipeline, run, P03 event ID and complete semantic
attribution fingerprint; detection identity additionally includes rule ID/revision.
Grouped diagnostic identity adds category and immutable rule-set reference. Keep
physical Kafka offsets and transient processing timestamps out of semantic IDs.
Retain physical location/hash as provenance. Exact repeated processing must produce
stable content; replay run or decision-affecting version changes must not collide.
Freeze literal identity vectors independently before writing identity code.

## P08-compatible search integration

P08 currently accepts only replay/quarantine/failure topics and freezes exactly two
indices in its configuration. Normalized/detection outputs cannot simply be sent
to that writer. Implement a separate versioned P13 mode with new configuration,
schema validation, topics, strict templates and binding checks, reusing the existing
bulk-window/retry/create-and-verify machinery where compatible. Reject cross-mode
configuration/restore; preserve existing P08 documents, identities and permissions.

Proposed physical indices: `detectbridge-tagged-events-v1`,
`detectbridge-detections-v1`, `detectbridge-processing-diagnostics-v1`.
Project searchable ECS common fields, outcome counts, quality, versions and links;
exclude inline originals and arbitrary dynamic vendor fields. Preserve exact time
strings beside range/precision-aware search projections. References must retain
hashes and retrieval locations; OpenSearch remains a derived view, not evidence
storage or an archive. Freeze final field mappings in owning implementation notes.

Use a dedicated P13 runtime user restricted to those exact indices: required bulk
item writes, duplicate gets and identity/mapping inspection only, plus the narrow
cluster identity/bulk dispatch actions. Initialization alone uses the bounded admin
helper. No wildcard index grants, security/template administration or deletion at
runtime. Test denied access to P08 and unrelated indices and management APIs.

Retain per-item retries, content-conflict quarantine, acknowledged Kafka failure
publication before source offset commits, bounded windows, outage backpressure,
TLS/hostname verification and exact cluster/topic/index/template/artifact bindings.
Failure-topic indexing failures block; never recursively generate diagnostics.

## Acceptance and bounded delivery slices

1. P08/P11/P12 bounded prerequisites are complete as refreshed above;
   optional-recorded skips do not establish new recorded qualification.
2. Freeze schemas, identity vectors, independent source/rule expectations and
   exact numerical payload/state/diagnostic limits; implement compact evaluation
   and attribution with real adapter/evaluator consumers and legacy regressions.
3. Implement separate integrated Kafka/Flink adapter/assembly/evaluation outputs.
   Qualify six outcomes, quality distinctions, retained memberships and compact
   output cardinality using handwritten positive/negative/edge expectations.
4. Implement actual P13 writer projections/configuration/templates/permissions;
   exercise partial bulk failure, conflict verification, denied permissions,
   blocked failure publication and outage/recovery before offset advancement.
5. Qualify Windows and Linux source-to-search paths with original recorded evidence,
   frozen expectations, exact logical/physical accounting and retrieval hashes.
   Cover audit and selected authentication plus supported Security/Sysmon scope;
   ordinary CI uses original synthetic cases, local recordings remain opt-in.
6. On exact artifacts, exercise TaskManager/JobManager/explicit checkpoint restore,
   every required Kafka sink failure, incompatible binding rejection, original
   audit deadline/member recovery, duplicates and two isolated replay runs.
   Same event/evidence IDs survive replay; processing/detection IDs stay isolated.
7. Run applicable locked component/contract/integration checks on ARM64 and AMD64;
   report failures and unavailable evidence. Review semantics and authorize each
   implementation PR merge separately. No throughput, archive or release claim.

Split output/compact-evaluator, integrated-runtime and search/qualification work into
normal bounded implementation PRs if needed, with P13 acceptance held across all
slices. No PR is opened merely to publish this prerequisite handoff/design.
