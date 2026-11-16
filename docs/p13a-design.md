# P13a output contracts and offline consumer

Status: implementation design recorded before code, 2026-11-16. Base 4ac31fa.
This routine refinement preserves A02–A07, P03 and legacy result 1/2. P13b owns
Kafka/Flink integration; P13c owns search. No new runtime deployment is introduced.

## Concrete wire and bounds

Integration contracts each start at 1.0.0 and reject other versions/unknown fields.
`compact-evaluation` contains version, six counts, ordered matched id/revision
pairs and at most three category/rule_set groups. `tagged-event` wraps `event` (unchanged P03), `processing_id`, `attribution`, six
`counts`, ordered `matches` (id/revision/detection_id), `tags` and `manifest`
(null for standalone, otherwise manifest_id, content sha256 and semantic_sha256). `detection`
contains detection_id, processing_id, event_id, run_id, rule (pinned plan rule
metadata excluding YAML/expression), attribution and manifest. `diagnostic` has
diagnostic_id, processing_id, event_id, run_id, category, rule_set and attribution.
The offline row adds `integration` containing tagged, detections and diagnostics;
legacy output is the default. Source-quality findings remain in the wrapped event,
separate from coverage categories. Preservation rows never receive integration.

P10 already bounds bundles to 4 MiB and 100 rules. Compact evaluation admits only
mapped v2 plans, retains <=100 matches and three diagnostic accumulators. Each
accumulator is a 100-bit membership set over serialized bundle rule positions,
encoded as exactly 25 lowercase hex digits (bit i = rule i, least significant bit
first numerically). Its immutable reference contains version `bundle-bits/1.0.0`,
bundle_sha256, bits, count and sha256 of the canonical reference without sha256.
The retained bundle resolves membership; no per-rule diagnostics are allocated.
No field-presence pruning, reordering or budget reset: one <=1,000,000-operation
budget per event, shared by the same predicate loop. At most three diagnostic
and 100 detection documents; no unmatched/inapplicable documents. Bounds are
serialized limits, not measured heap claims: input event <=1 MiB, tagged <=2 MiB,
each detection <=128 KiB, diagnostic <=32 KiB, complete integration <=16 MiB.
Overflow fails the complete offline transaction visibly, retaining prior output;
no truncation, silent match loss or downgrade to nonmatch. Rule metadata excludes
unbounded original YAML but retains ID, logsource, revision and provenance.

Attribution contains the original source namespace/instance, pipeline `p13-offline/1.0.0`, bundle hash, source reference
with actual canonical snapshot hash and parser mapping reference/hash from the
validated adapter context, including when the evaluator bundle lacks that source.
Normalized-only callers without context use bundle references (null when unknown).
The context_sha256 covers the original adapter context excluding receipt clocks;
Linux context is extracted from its validated extension, Windows supplies it explicitly.
Attribution also contains actual event processing versions, compiler,
evaluator, selector, mapping-set hash and fixed enrichment policy/hash plus empty
external_inputs. The enrichment policy emits ordered nonzero `coverage:<outcome>`
tags and `quality:<eligibility>`; pinned rule metadata is enrichment. There are no
network lookups. The complete immutable plan remains required retained evidence.
Unknown source remains configuration-blocked; supplied known processing mapping
must match the selected profile. Audit callers supply a validated original manifest;
verify its hash, event/run/source/mapping and exact member IDs/evidence hashes.
The original module validates context/manifests and retains raw/context rows.

## Canonical identities and conflicts

Canonical JSON uses sorted object keys, compact UTF-8, original array order and
integer values, identical to Contracts.canonical. Identity is `sha256:` plus SHA256
of canonical JSON array `[domain, ...parts]`, with domains
`detectbridge.p13.processing/1`, `detectbridge.p13.detection/1`, and
`detectbridge.p13.diagnostic/1`. Processing parts: pipeline, run_id, P03 event_id,
semantic event hash, attribution, semantic manifest reference
(null or {semantic_sha256}). Detection parts: processing_id,
rule_id, revision. Diagnostic parts: processing_id, category, rule_set.sha256.
Semantic event removes event.ingested, detectbridge.time.received/processed and
the receipt member of the validated linux.context extension's original context.
All decision context versions, source/mapping snapshots, host/generation binding
and completeness metadata in that extension stay bound.
The manifest semantic hash removes manifest_id and per-member context_sha256
because P12 hashes the entire context, including receipt clocks. All other manifest
content (raw/evidence membership, source/mapping, assembler/policy, quality and scope
provenance) stays bound. The original manifest ID/hash remain retrieval attribution;
semantic content comparison substitutes {semantic_sha256} for each manifest link.
The tagged wrapper retains the unchanged event, including original receipt fields.
`IntegrationOutputs.contentHash` excludes those same clocks for semantic duplicate/
conflict comparisons. Kafka locations are outside these documents. Decision content
changes therefore alter the semantic hash while identical logical processing has
identical semantic content regardless of location/receipt time. Run changes
and all decision-affecting attribution changes alter processing/detection IDs.

Literal identity vectors and independent compact count/match expectations are
committed before implementation in contracts/integration/v1/fixtures. Vectors
use a standalone Python hashlib calculation, never evaluator-produced truth.
Existing P10 selection expectations cover ordered budget exhaustion; P11/P12
fixtures provide independent source expectations. Compact comparisons additionally
use exhaustive evaluation as a supplementary oracle. Audit closure is never proof
of completeness; the original manifest and quality policy remain authoritative.
