# P10 compatibility and source mapping design

Status: P10a implemented for review; P10b selection and runtime qualification remain
blocked on P10a's authorized merge. Independent owner review of P09/P10 semantic
expectations remains pending. See the [accepted implementation plan](p10-p12-plan.md)
and [task ledger](implementation-ledger.md).

## Boundary and version dispatch

P10a retains P09's operators and limits. It adds mapping/candidate contracts,
compiler diagnostics and an offline Java v2 execution mode, not adapters, expanded
Sigma operators, activation, archive or production source coverage. P10b owns
optimized selection, exhaustive equivalence and v2 runtime recovery qualification.

Legacy compilation without mapping/provenance arguments produces plan 1.0.0. Its
reader runs the unchanged P09 semantic mode and produces result 1.0.0 with the
legacy compiler/evaluator/mapping identifiers. Explicit P10 compilation requires
both mappings and provenance, produces plan 2.0.0 and selects the v2 evaluator
semantic mode/result. The Java package supports both modes; their identifiers
version semantic interfaces, not the enclosing JAR. Unknown versions fail closed.
New results attribute the actual plan compiler, semantic evaluator and mapping
version, plus the hash of the complete canonical ordered mapping-profile list.

P09's existing Flink job is deliberately restricted to legacy plans at submission,
state initialization and open. It cannot publish v2 results into its v1 topic.
P10b must supply a separately versioned qualified runtime deployment. Existing
P07/P08/P09 projects, topics and retained checkpoints are not migrated or adopted.
Bundle changes alter checkpoint bindings; no state migration is introduced.

## Mapping contracts

Mapping profile 1.0.0 pins its ID, exact P03 source ID/version/content SHA-256,
ordered field declarations and its own SHA-256. Hashes use the same compact,
sorted-object-key UTF-8 representation as plans, excluding the artifact's own hash.
The plan hash additionally covers every profile and candidate provenance entry.
Hashes provide content integrity, not authenticity or proof that an AST represents
its YAML. Bundle production and review remain trusted compiler boundaries.

The bounded alias registry remains Image, CommandLine, ProcessId and User, mapped
to process.executable, process.command_line, process.pid and user.name. Every source
has exactly one declaration for each alias. Missing support is explicitly
unsupported, not silently inferred from a synthetic event. Supported declarations
must match one source-contract JSON Pointer, target and capability exactly. Targets
are the existing scalar ECS leaf fields; ProcessId is integer, other aliases are
strings. Duplicate aliases/sources/IDs, wrong types/cardinality/targets, unknown
transforms and stale hashes fail validation in both compiler and Java loader.

Transform declarations are fixed, versioned names: identity-string,
decimal-integer, hex-integer and windows-account, each at 1.0.0. Windows-account is
valid only for User; numeric transforms only for ProcessId. They describe future
parser obligations and are never executed as code by the compiler/evaluator.
P11/P12 must qualify their concrete extraction/transform binding before claiming
source support. Current mapping fixtures describe only P03's synthetic profiles.

Event structural/identity/evidence validation happens before outcome decisions.
For a valid input, precedence is unknown source → configuration_blocked; known
mismatching logsource → inapplicable; unsupported alias used anywhere in the
compiled expression → configuration_blocked; insufficient event eligibility →
quality_skipped; otherwise evaluate with P09 matched/unmatched/error semantics.
All reachable AND/OR/NOT predicates participate in static capability checks,
regardless of event short-circuiting. Unused unsupported aliases do not block a
rule. Conditional/available capability never implies a required per-event value:
missing positive predicates remain false and NOT can match absence. Capture
warnings do not independently change that rule semantics.

## Candidate provenance and analysis

Candidate provenance 1.0.0 binds rule UUID and exact YAML byte revision to original
content hash, repository URL and immutable 40-hex revision, path, authors, license,
notices and an ordered modification hash chain. Modified candidates must link the
original hash through every change to the current bytes. YAML license/author
metadata, where present, must agree with the manifest. Original synthetic fixtures
are labelled Apache-2.0; no upstream rule content is imported by P10a.

Schema validation is not a license or terms review. Importers must retain the
original YAML/notices and substantiate the manifest under THIRD_PARTY.md before
import or redistribution. The compiler does not retrieve repository URLs, evidence
URIs or missing provenance. Source/candidate JSON reads are bounded and duplicate
keys/non-JSON numbers fail. Never put credentials in provenance.

`--analyze` emits one compiled/rejected disposition for every submitted candidate,
including per-source supported/inapplicable/configuration-blocked dispositions for
compiled candidates. Unsupported constructs remain rejected with fixed diagnostic
categories. This report is not an executable bundle or an activation instruction;
retain the original files referenced by its provenance/checksums. Invalid manifest
sets or I/O failures fail the whole operation. Compilation remains all-or-nothing
for the selected input set, even if analysis reports some candidates as supported.
Both report and plan publication use fsynced temporary files and atomic replacement;
failure preserves existing output. This is not an archive/disk-loss guarantee.

## Independent expectations and checks

The [mapping cases](../contracts/detection/v2/fixtures/compatibility-cases.json)
contain literal outcomes and rationales independently reasoned before evaluator
changes. Native child review checked missing/NOT semantics, capability-before-
quality, source-before-capability, invalid-before-outcome and OR gating. This is
agent review, not independent owner acceptance. P09's handwritten expectations
remain unchanged; supplementary pySigma output is never the sole oracle.

`tools/dev.py check` validates contracts, provenance, mapping tampering, atomic
failure preservation, candidate accounting, repository hygiene, lint and types.
`tools/dev.py java` runs legacy/new Java tests and YAML-to-Java cases, including
nested tamper checks with recomputed outer hashes and changed-mapping checkpoint
binding rejection. Shared detection changes retain existing writer/transport build
gates. Mapping checker/test paths explicitly select detection CI.

P10a does not claim v2 Flink recovery, recorded source eligibility, throughput or
complete P10 acceptance. P10b owns the remaining complete acceptance gate; P11/P12
remain dependent on it. The upstream shaded-Jackson image finding remains open.
