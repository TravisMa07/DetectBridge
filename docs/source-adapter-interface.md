# Source adapter interface for P11/P12

Status: agreed implementation boundary from P10 planning. This specifies the next
adapters; it does not assert that a parser, assembly operator or production source
is implemented. P11/P12 introduce the concrete library interfaces and schemas with
real consumers, rather than unused module scaffolding. Shared changes remain
orchestrator-owned.

## Input and context

An adapter receives a validated P03 raw record, its verified exact evidence bytes,
and a fixed versioned context with these named members:

| Member | Contract |
| --- | --- |
| `version` | Exact context version 1.0.0; reject unknown versions |
| `run_id` | UUID; state and output isolation, excluded from P03 evidence identity |
| `source` | P03 namespace/instance, unchanged from the raw record |
| `first_observed` | Immutable P03 first observation, never replay receipt time |
| `source_generation` | Explicit capture/boot/generation scope with provenance; absent remains absent |
| `host_binding` | Optional reviewed host ID plus binding revision/hash and provenance references; no guessed IDs |
| `source_contract` | Exact ID/version/content hash and validated immutable snapshot |
| `mapping_profile` | Exact P10 profile ID/version/hash and validated declaration |
| `parser` | Fixed parser ID/version, not executable user configuration |
| `receipt` | Optional actual receipt/processing metadata, separate from occurrence time |

The evidence resolver is explicitly supplied by the caller. It resolves only
already acquired/retained local evidence, verifies object and record hashes and
byte ranges, and returns unchanged bytes. Do not fetch arbitrary evidence URIs or
execute transformations named by untrusted input. Resolver availability/I/O failures
remain visible retry/backlog failures; integrity mismatches are preservation
failures, never ordinary nonmatches.

Source contracts describe static capabilities; context may supply known capture
configuration with provenance. Per-event absence does not establish disabled
capture. Host display names, dataset IDs and audit serials cannot manufacture a
trusted host/generation scope. Missing identity context produces identity_missing
and skipped preservation rather than cross-host assembly.

## Output and eligibility

The result is either a P03-valid normalized event with original evidence membership,
or a bounded preservation diagnostic referencing the retained raw occurrence.
Malformed/unsupported input must not be fabricated into a valid process event.
A syntactically valid event with insufficient integrity may remain a normalized
skipped event when its identity/membership can be established. Keep parser failure,
unsupported source, disabled capture and legitimate optional absence distinct.

Normalized output carries the exact parser/mapping/normalizer versions in existing
processing metadata, source contract reference, run UUID, time interpretation and
quality diagnostics. Respect the closed P03 schemas and exact version support.
A new field or changed core semantic requires an explicit revision and all affected
readers; initial parser/assembler versions may use 1.0.0. Preserve extra vendor
attributes in source_fields. Use separately versioned, validated namespaced
extensions for non-core assembly/late-evidence links.

P10 evaluates applicable rules only after profile/capability and quality gates.
Its four aliases are Image, CommandLine, ProcessId and User. Unsupported declared
capability blocks that rule/source; conditional/available missing optional fields
retain positive=false and NOT-on-missing behavior. P11/P12 must independently
qualify the parser's actual output/transform binding. No approximate argument to
command-line conversion, fabricated host ID or parser capability claim is allowed.

## Assembly boundary

P12 assembly keys include run, namespace/instance, trusted host scope, generation
and exact source audit timestamp/serial. Emitted event identity remains P03 source
plus sorted original record IDs. The versioned membership manifest retains record
hashes/references, closure, completeness findings, policy/assembler versions,
output event link and immutable late associations. Closure is not proof of
sufficient quality; late evidence never mutates emitted events. Limits and
checkpointed failure behavior are owned by P12 under the accepted plan.

P13 owns production adapter→evaluation→writer integration and detection identities.
This interface introduces no archive, activation, management API or UI.

## Concrete context reconciliation for the first adapters

P11 and P12a retain module-local validators over the same named JSON boundary.
`source_contract` wraps id/version/sha256/snapshot; `mapping_profile` wraps
id/version/sha256/declaration. Both validators bind these to immutable module
resources. `host_binding` uses host_id/source/revision/sha256/provenance/kind,
where kind is reviewed or synthetic, and its SHA-256 covers the canonical object
without sha256. The source must match the raw envelope. Windows additionally
requires Computer binding; Linux accepts optional computer display context.
`source_generation` contains id/provenance; Windows can additionally bind known
command-line capture configuration. `receipt` contains optional actual received
and processed timestamps. Required identity remains source specific: audit
assembly requires reviewed host and generation scope, while missing scope produces
separate skipped preservation. A synthetic binding is never recorded provenance.
Linux bounds context to 64 KiB and provenance arrays to 16 entries; Windows uses
its documented parser/context bounds. Different admission limits do not rewrite
the context's meaning or P03 identities. No shared unused adapter library is added.
