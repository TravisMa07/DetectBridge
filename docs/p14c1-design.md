# P14c1 explicit current-policy replay freeze

Status: design/expectations frozen in b068b53 before production code; implementation
and qualification are tracked in the [ledger](p14c1-ledger.md).
Owner: primary agent, issue #14, branch `feat/p14c1-current-replay`.
Base: owner-merged P14b #51, `943d143eb4e5dc6d07871513f993efbddf1ab230`.
Its actual merged-main qualification subsequently passed; see the ledger. The original
handoff and local P14b completion notes are preserved. Apply A02–A07 and the
[P14 milestone design](p14-design.md); this is a bounded subdivision of P14c.

## Scope and gates

Implement explicit new-plan evaluation and deterministic offline regrouping of
original inputs from a verified P14b sealed selection. Output remains private,
local and isolated, with resumable atomic transition/state publication. Preserve
the original archive, historical pin, original contexts and historical outputs.
P14c2 owns retention plans, deletion, leases/anchors and P16 coordination. The
owner subsequently requested P14c2 as the final P14 slice, so its owning design
will also cover controlled recorded archive-to-replay reuse, P05 archive import
and the complete P14 acceptance map. Those additions do not expand P14c1. No deletion,
activation, identity repair, API/UI, live forwarding, HA or throughput claim is
introduced here. These remaining items prevent claiming P14 complete.

Require P14b's qualified merged base, this separate schema/expectation freeze,
meaningful red/green regressions, actual Java execution and publication faults,
applicable compatibility checks, owner review, authorized merge and actual
merged-commit qualification as separate gates.

## Explicit request and execution

Closed [v1 contracts](../contracts/current-replay/v1/request.schema.json) define a
current request, run, transition result and commit. A request pins a sealed
historical selection hash, exact new compiled plan bytes, supported executable
profile, original-context policy, empty external enrichment, all assembler limits
and an ordered finite schedule. The plan may change rules, supported mappings or
source definitions, subject to the existing evaluator's compatibility checks.
Source parsing still uses each original trusted context; no inferred host/boot,
new identity binding, or silent context transformation is permitted. New parser
executables need a future supported profile; explicit selection of the supported
original parser is a valid current-policy choice.

Support exactly P13 executable JAR
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`.
A separate thin current executor contains only its own classes and hash-bound
controller/validator/lock/schema resources. It verifies the original JAR before
loading classes and checks class origins. Reuse the original Machine, Assembler,
adapters, evaluator and LocalEvidence resolver, not a new approximate parser.
The reader runs separately so newer archive dependencies cannot shadow processing.
The trusted digest-pinned Flink image and no-network/read-only helper constraints
remain those of P14b. Arbitrary manifest-supplied Java/Python is unsupported.

Schedule entries have explicit integral milliseconds, action and nullable input
reference. Time begins at Unix epoch plus the specified millisecond value; values
are nondecreasing, between zero and one day, with list order breaking ties.
`input` consumes exactly one selected original source admission, `tick` pumps the
original machine at that explicit clock, and final `end` supplies a deterministic
new-run end control. The original Machine evaluates deadlines before admission;
an input at its deadline can therefore follow a timeout. No wall-clock sleeps or
old receipt gaps select membership. Every sealed source input must occur exactly
once; old controls are origin evidence, not implicitly replayed. End occurs once,
last, after all inputs. Ended state, empty queues and no open groups are required.

Keep original raw/context bytes in the archive. For execution only, deep-copy the
input and replace the context run UUID. Preserve original observation/occurrence
strings and precision; receipt/processing clocks belong to the new deterministic
schedule. Synthetic wire locations used internally by Machine are explicitly local
admission ordinals, not claims of Kafka acknowledgement or original offsets.
New controls derive stable UUIDs from run/request/step. New membership may include
an original late EOE before a deadline, creating a new six-member source-boundary
group instead of a five-member historical timeout plus linked preservation.

Each run pins the full request, selection, plan/executor/producer/reader/image,
absolute destination, fixed storage caps and all original physical references.
Results carry the origin selection, actual step, new run, request hash, transition
identity, actual supported P13 output documents and post-transition Machine state.
The origin pin retains original member/late-link manifests; current manifests
retain original record IDs. Their join gives explicit original-wire and original-
membership links without changing those originals. No current output is inserted
into Kafka/search or presented as a historical reproduction.

## Isolation, durability and bounded recovery

Use an explicit sibling current workspace. Its versioned binding includes current
mode and absolute root, so historical/P05/P12/P13 roots fail before mutation.
Take locks in historical-catalog then current-workspace order. Require the existing
historical catalog; a typo must not initialize a new source catalog. Keep its pin
and artifacts intact. Current work never adds unknown files inside the P14a archive
or P14b catalog. Future retention must coordinate both explicit roots; no absence
of an in-archive pin directory establishes deletion permission.

A fresh canonical UUID differs from the original run and existing historical runs;
existing current runs require explicit resume with identical bindings. Across
unrelated roots the operator must supply fresh UUIDs; there is no global registry.

Execute the bounded schedule from empty new-run state into unpublished transition
files on every start/resume. There is no checkpoint import or trusted advisory
cursor. Each transition combines its outputs and actual post-transition state;
validate native state through the supported original API and replay all prior
steps. Verify every already committed result byte-for-byte before appending any
new transition. Missing/corrupt/gapped or changed committed output fails without
replacement. This deterministic re-execution is a bounded recovery choice, not a
throughput optimization. Completed resume writes no run files.

Publish run metadata first. For each transition, fsync payload and commit metadata,
fsync staging directory, rename exclusively, then fsync parent. The immutable
contiguous transition chain is authoritative. Its commit records index, transition
ID, result SHA-256/length and previous commit identity. Atomic advisory progress
follows publication and never advances the durable cursor. Kill windows during
payload/metadata, before/after rename/sync and during advisory publication must
recover without missing or overwriting a transition. Own and stop orphan helpers
before cleanup; retained private failures count against the cap.

At most 256 source inputs, 512 schedule entries and 1000 original references;
request 1 MiB, plan 4 MiB, engine input 32 MiB, one transition 24 MiB (state at most
16 MiB), total unpublished transition output 128 MiB. Current workspace totals
512 MiB with 128 MiB filesystem reserve, including artifacts/work/results/failures.
Conservative reservations may stop earlier; no compression or future deletion is
assumed. Keep original assembler limits explicit within their accepted bounds.
The helper remains 512 MiB memory / 320 MiB heap, one CPU, 128 PIDs, no network.
Disk/permission/sync errors stop publication, retain originals and surface fixed
categories; routine logs omit source values and exception bodies. Physical power
loss, disk loss and unbounded outage are not established by process kills.

## Independent expectations frozen before implementation

The [literal packet](../contracts/current-replay/v1/fixtures/expectations.json)
references frozen P14b source bytes and two original synthetic rule files. The
new auth predicate is `User: bob`; the source says `alice`, so it must be unmatched.
The unchanged image rule matches `/usr/bin/whoami`. Expectations use source text,
existing P11/P12 field expectations and contract identity definitions, not output
from the new executor. Authoring independence is not owner semantic acceptance.

| Case | Input / operation | Required observation |
| --- | --- | --- |
| C01 | Selected original auth Alice, explicitly new Bob rule | One unmatched, one inapplicable, zero matched/errors/blocked/skipped; historical Alice match remains immutable |
| C02 | Original audit members 0–4 followed by original late EOE 5 before timeout | One eligible source-boundary manifest with exactly six ordered members, image match and auth inapplicable; new event ID differs from five-member historical group |
| C03 | Same members, tick at 30000 before EOE | Five-member timeout and late preservation linked to the new manifest; no six-member group |
| C04 | EOE exactly at the 30000 deadline | Original deadline-before-admission semantics: same timeout/late result as C03 |
| C05 | Explicit shorter age or member/resource bound | Required original closure/quality distinction and finite backlog; no ordinary match for insufficient groups |
| C06 | Two fresh runs of one current request | Stable member/event evidence identities; disjoint processing/detection IDs, pinned new attribution and original times; historical files unchanged |
| C07 | Missing/repeated/foreign reference, unknown profile/enrichment, nonmonotone/fractional schedule, absent final end, original UUID reuse | Preflight fails before a run is published; no implicit defaults or old checkpoint adoption |
| C08 | Change request/plan/artifact/image/mode/limit/root on resume | Reject before append; original committed run remains byte-identical |
| C09 | Kill in each payload/metadata/rename/sync/advisory window | Re-execution verifies committed prefix; output/state commit together, no skipped source; completed resume changes no run files |
| C10 | Corrupt/delete middle result, recompute metadata with fractional counters, orphan helper or foreign root | Explicit failure or owned-helper cleanup as applicable; no silent restart, overwrite or foreign-root mutation |
| C11 | Cap/reserve exhausted, permissions or sync fail; malformed body sentinel | Visible stop with immutable originals and no advanced durable cursor; routine logs omit sentinel |
| C12 | Existing P14b historical execution and P14a archive on new source revision | Actual historical/archival compatibility passes; no transferred old CI or fixture-only runtime claim |

Qualification uses the actual new plan/compiler and accepted original Java engine,
with independent fields/counts/membership/attribution checks, negative oracle
mutations, two isolated runs and real process interruption. Public native CI uses
only original public synthetic fixtures; controlled recordings remain a separately
scoped opt-in follow-up with catalog/terms/bindings revalidated before use.
