# P15 — Rule lifecycle, activation and rollback

Status: owning design proposal before implementation. Base is independently
qualified merged main `f44c9f91e10414cd2b03481951a2e2a1c7b2a4a0`.
The owner accepted bounded P14 semantic/completeness completion in this session;
the owning P14 reconciliation records that disposition separately. The owning [expectations](p15-expectations.md)
are derived before new implementation. Preserve A02–A07 and all accepted P09–P14
bounds. No P15 runtime is implemented or qualified by this document.

## Delivery boundaries and ownership

P15a is one reviewable, useful candidate-lifecycle slice: import an immutable
complete bundle, validate its closure and compatible declarations, test its plan
with the actual Java evaluator against separately supplied frozen expectations,
and stage the exact tested bundle. It may prepare immutable activation-request
bytes for inspection. Preparation is not publication, desired-state installation,
worker application, activation or convergence. P15a does not simulate those facts
or accept fabricated acknowledgments. It has no live deployment mutation command.

P15b owns the additive worker runtime, private Kafka control publication, durable
membership and acknowledgment protocol, actual application/checkpoint boundaries,
convergence, rollback and runtime fault qualification. P15 completion requires both
slices, evidence for the roadmap acceptance, owner dispositions, authorized merges
and actual merged-commit checks. P15b dependent implementation waits for P15a's
qualified owner merge; no previous permission to stack P14 PRs applies here.
P16 discovery may proceed, but its dependent implementation follows P14/P15 gates.

The primary owns shared contracts, design integration, CI classification, dependency
locks, status and final evidence. Candidate-store implementation, additive Java
runtime implementation and independent qualification have disjoint ownership when
assigned. Serialize heavy Docker/Flink/Kafka suites with a named slot owner and
isolated project/data/control roots. Agent review does not establish owner acceptance.

## Existing interfaces and compatibility

`tools/detection_compile.py` emits mapped v2 immutable plans containing source
snapshots, mappings, original YAML/revisions and P10 candidate provenance. Reuse its
validation and budgets, not a second permissive compiler. The actual Java
`Evaluator` independently validates the plan/hash and executes bounded matching.
`IntegrationOutputs` records actual source, mapping, parser, compiler, evaluator,
selector, enrichment and decision-context versions. Those semantics stay accepted.

The old `integration/1.0.0` deployment fixes one evaluator in its deployment
binding and restores only an exact binding. Its one-partition, parallelism-one
job is not a hot-swap runtime or proof of mixed-worker convergence. Keep its
checkpoint descriptor, UIDs, output contracts and restore guards unchanged.

P15b is additive: separate package, deployment identity, control topics, checkpoint
state/version, cache/build namespace and output envelope/domain. It may depend on
unchanged existing Java libraries but must not modify their source/resources in a
way that changes the pinned legacy producer. Qualify every actual new artifact.
Do not adopt old integration checkpoints as lifecycle checkpoints.

P14 historical/current replay still uses producer
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`
and the original reader/executor pins in `tools/archive_profiles.py`. Verify those
hashes and all old consumers on the actual revision. Never update a pin merely to
accept a new build. New runtime output does not enter old topics as if it were a
known P14 processing graph. Existing managed-archive unknown-graph blocking stays
fail-closed. A supported archive/replay profile for lifecycle output requires an
explicit separately versioned, independently qualified artifact/graph boundary in
P15b before P15 can claim retained historical reproducibility for that output.
P15a does not produce source-event output and does not change archive profiles.

## Immutable bundle and P15a lifecycle

A bundle is an explicit manifest plus bounded files addressed by SHA-256, never an
executable import archive. The closed manifest fields are `version` (1.0.0),
`bundle_sha256`, `plan` (`sha256`, `bundle_sha256`, `bytes`), `profile`,
`compatibility_sha256` and `members` (exactly one `name`, `sha256`, `bytes` entry for `plan.json`).
The profile fixes executable artifact hashes, versions and source/mapping hashes.
The sole logical closure file `plan.json` already includes original YAML,
provenance and source/mapping snapshots. P15a adds no Java module and does not
copy or run a candidate-supplied executable.
All hashes are lowercase 64-digit hexadecimal; sizes are exact nonnegative integers.
The manifest binds:

- The exact mapped plan file hash and its semantic `bundle_sha256` separately.
- Rule original revisions/provenance/license declarations already bound by the
  plan; retain upstream/local modification history and original YAML.
- Source and mapping snapshots, parser/adapter/assembler policy identities,
  evaluator/selector/enrichment versions and executable artifact identity.
- Compatibility identity, fixed finite limits and closure member hashes/sizes.

The bundle identity is SHA-256 over canonical manifest bytes excluding its own
identity field; every member uses its exact-byte hash. Canonicalization is the
existing deterministic JSON convention, with duplicate keys, invalid Unicode,
trailing tokens, nonfinite numbers and unknown fields rejected. Paths are fixed
logical member names, never user-directed extraction paths. Missing, extra,
corrupt, symlinked or conflicting closure members fail. No URL fetch or arbitrary
Python/Java execution is permitted by a manifest.

For this supported profile parser/source/mapping/assembler/enrichment policy and
runtime artifact are fixed across live swaps. Rule content and compatible plan
identity can change. Compatibility hashes include the source/mapping declarations,
parser/assembler profiles, executable/evaluator/selector/enrichment identities and
limits. The worker recomputes compatibility, rather than trusting a supplied hash.
The P15a initial parser/assembly profile names are `windows-xml/1.0.0`,
`windows-normalizer/1.0.0`, `linux-audit/1.0.0`,
`openssh-password/1.0.0`, `linux-p12a/1.0.0` and
`execution-evidence/1.0.0`; selection is `source-index/1.0.0`, mapped evaluation
is `detectbridge-java/2.0.0`, and enrichment is
`coverage-and-rule-metadata/1.0.0`. Bind parser/assembler executable code to its
containing legacy producer hash above, plus hashes of the exact source/mapping
declarations. Bind Java test execution to the same retained producer hash above, which contains
`io.detectbridge.detection.Evaluate`. The trusted CLI `--evaluator-jar` argument
selects an existing local regular file matching that exact hash; neither manifest
nor candidate content supplies an executable path, classpath or entry point.
Verify this external retained artifact on every operation. It is not copied into
the 8 MiB candidate closure. The new P15b parser-containing runtime
artifact hash will be measured and qualified in its owning freeze/evidence;
no P14 qualification transfers to it.
A change to those fixed inputs needs a separately designed deployment/restore
migration; it cannot become compatible because an administrator relabeled it.

Commands operate on one private local store: `import`, `validate`, `test`, `stage`,
`prepare`, `status` and `retire`. Their concrete CLI spellings belong to the owning
implementation; the observable transitions are frozen here:

1. Import copies and verifies the complete closure into an immutable candidate;
   it neither compiles untrusted code nor activates anything. Exact reimport returns
   the same identity. A conflicting object never overwrites retained bytes.
2. Validate checks schema, all hashes, provenance, fixed compatible profile and
   actual executable artifact binding. Failure preserves the candidate for
   inspection with a fixed sanitized category; it does not establish readiness.
3. Test loads the candidate with the actual pinned Java evaluator and compares
   complete compact outcomes to expectations frozen independently of this run.
   Record expectation/input hashes, evaluator artifact, command/result and report
   identity. A result from another plan/artifact/input suite cannot satisfy this
   candidate. The test receipt is generated only by the trusted runner and binds
   exact plan/closure, installed profile/JAR, original normalized-case bytes,
   expected complete compact JSON and observed result/report hashes. The runner
   uses the existing `io.detectbridge.detection.Evaluate` compact interface, with
   pinned Java invocation, no shell expansion and private bounded temporary files.
   Caller-supplied `passed` receipts cannot satisfy this transition. Expectations
   are never regenerated from evaluator output. At least one positive and one negative supported eligible case are
   required; the independently authored suite covers relevant candidate sources.
4. Stage requires successful validation and actual passing tests for the unchanged
   bundle/profile. Tests are evidence of the declared cases, not universal rule
   correctness. Failed retests never erase earlier results or make an untested
   mutation ready. Stage is not deployment selection.
5. Prepare requires staged content and produces inspectable immutable proposed
   command bytes. Preparation compares an explicit expected preparation revision
   and reserves exactly its successor in the preparation journal; competing
   preparations cannot reserve the same revision. This local proposal sequence
   is distinct from published desired state, and P15b must reconcile it with
   actual publication before adoption. It does not write desired state, publish
   Kafka, accept a worker acknowledgment or report activation complete.
6. Retire marks a candidate unavailable for new selection only after references
   permit it. Retained content/history are not silently deleted. P15a has no
   automatic garbage collection or history compaction.

The private store has a checked identity/profile root, immutable `objects/<sha256>`
and `bundles/<sha256>` content, `journal/<sequence>` operation records and one
checked atomic head. A journal record has `version`, `store_id`, `sequence`,
`previous_sha256`, `request_id`, `request_sha256`, `request`, `operation`, `bundle_sha256`
and `result`; its canonical record hash is stored with the head. Status derives
lifecycle state from the verified chain rather than mutable caller flags.
P15a request objects have the closed fields `version` (1.0.0), `authority_id`,
`request_id`, `operation`, `bundle_sha256`, and `arguments`. The operation is one
of `import`, `validate`, `test`, `stage`, `prepare`, `retire`; `arguments` is
operation-specific, never an unconstrained options object. Import arguments bind
exact manifest and plan content hashes; validation/staging/retirement have no
additional arguments; test arguments bind a frozen test-suite file hash; preparation
arguments are the complete closed command shape below plus
`expected_preparation_revision`. Status is read-only and needs no request identity.
CLI file paths are local input locations, excluded from immutable content identity;
read bytes must match request-bound hashes. No request field supplies subprocess
code or a command string. The owning contract schema is authoritative for the
wire syntax; validation rejects extra keys and booleans as integers.

The root is owned by the invoking OS UID with mode 0700; reject symlinked,
foreign-owned or permissive roots. The authority UUID is an identity, not a secret.
Private OS-account access is the local authentication boundary. No shared bearer
secret is invented or exposed by P15a. Store configuration binds `version`,
`store_id`, `authority_id`, fixed trusted profile and retained external evaluator
artifact identity. Reopening with another authority/profile fails before mutation.
The store must be disjoint from candidate-input directories, suite-input files
and the external evaluator JAR: neither may contain or be contained by the store.
Reject symlinks in every supplied path component and nonregular files. The CLI
never adopts a preexisting foreign/nonempty directory as a fresh store.

A successful record stores the full canonical request and immutable result in
addition to their hashes. The head binds `version`, `store_id`, `sequence` and
`record_sha256`. Every record binds its exact predecessor hash; genesis has null
predecessor. Successful retries return the original stored result, including its
original preparation revision or test report identity. Recover only a complete
valid immediate successor of the checked head, never an arbitrary later file.
Gaps, conflicting successors, unknown files, corrupted object/history/head bytes
and foreign store identities block mutation; never initialize over them.

Every mutation has a UUID request ID and canonical request hash. The first
successful committed result is retained: exact retries return it without a second
transition; reuse with different content fails. A failed operation never partially
promotes a bundle. Mutation records are append-only, hash-linked and monotonically
numbered; store identity and profile are checked on each open. Write/force immutable
objects and record before atomically replacing and forcing the checked head.
On restart verify the full retained chain. A complete valid next record can repair
a stale head; conflicting, missing or corrupt history blocks mutation. Private
temporary files are not successful lifecycle evidence. Concurrent writers are
serialized by an exclusive operation lock; never break an active lock on timeout.

## P15a implementation interface and transition details

`tools/lifecycle_validation.py` owns `encoded(value)`, `sha(bytes)`, `require(kind,
value)`, `profile(plan)`, `bundle(plan_bytes)` returning a manifest,
`verify_bundle(directory)` returning `(manifest, plan_bytes)`,
`verify_artifact(path)` and `run_suite(plan_bytes, suite_path, jar_path, temporary_root)`.
The latter returns a bounded report with `passed`, `suite_sha256`,
`plan_sha256`, `evaluator_sha256`, per-case input/expected/observed hashes and fixed
result category; it never accepts a caller's passing receipt. It must validate
all expected compact-result documents before executing any Java process and require
at least one eligible positive and one eligible negative case.

`tools/lifecycle.py` owns `Store.initialize(root, authority_id, evaluator_jar,
profile)` and `Store(root, authority_id, evaluator_jar)`; `execute(request,
bundle_directory=None, suite_path=None)` returns the committed result;
`status()` returns only candidate facts and preparation revision. Initialization
requires a new root and explicit validated compatible profile (normally from a
candidate manifest). The complete fixed profile, including source/mapping hashes,
is immutable store configuration. Every imported candidate must match it.
The store has one local preparation sequence and one deployment identity fixed by
its first preparation; a different deployment requires a fresh disjoint store.

Import and validate are separate facts: import verifies the closed manifest and
exact member bytes; validate recompiles embedded YAML with P10's original compiler,
provenance, sources and mappings and requires complete plan equality. Test requires
validation. Test reports, including unequal-outcome failure, are committed facts;
failed tests never produce `tested` readiness. Stage requires the **latest** test
report for that bundle to pass. A failed retest removes test readiness and stage
readiness for new preparation until another actual test passes and explicit stage
occurs; it never erases an earlier preparation. Retire marks an unreferenced
candidate unavailable, including staged candidates, but any prepared command
reference blocks retirement permanently in P15a (no release protocol). Retired
content cannot be revived by import under another request.

Before import journal publication, newly published but not yet referenced immutable
content may survive a crash. Such exact verified objects are reusable by an
identical later import; they do not constitute imported/staged lifecycle facts.
They count toward all byte/count limits and are not automatically discarded.
The journal remains the authority for lifecycle state. A head rename that survives
without successful parent sync must be forced on recovery before any successful
status/mutation return. Temporary files use a fixed owned namespace and never
become authoritative records. All publication fault outcomes remain failures until
a fresh recovery verifies authoritative state; no power-loss claim follows.

## Bounds

Limits apply before expensive work and before committing any transition. MiB means
1,048,576 bytes; KiB means 1,024 bytes. At the limit is valid when all other
conditions hold; one byte/item beyond it fails without partial promotion.

| Resource | Supported maximum |
| --- | --- |
| Canonical bundle manifest | 64 KiB |
| Complete bundle closure | 8 MiB |
| Exact mapped plan | 4 MiB, 100 rules, 16 sources; existing AST/string budgets retained |
| Retained bundles in a store | 64 |
| Entire store, including records, bundles and partials | 512 MiB |
| Required filesystem free reserve | 128 MiB after conservative transaction reservation |
| One journal record | 64 KiB |
| Test temporary files per operation | 24 MiB, under the store byte budget |
| Committed lifecycle request/history records | 4,096 |
| One canonical control command or acknowledgment | 64 KiB |
| Participating workers in one deployment | 16 |
| Revision or journal number | Signed 64-bit nonnegative; commands begin at 1 |
| Candidate test suite | 64 normalized cases, 1 MiB each, 16 MiB total inputs |
| One Java test process | 10 seconds, 2 MiB captured stdout |
| One prepared command | One existing staged bundle and one explicit membership snapshot |

Test suites remain external frozen inputs; journal reports retain input/expectation/
observed hashes and bounded counts/categories, never full source bodies. Temporary
input/output files remain private under the store, are counted before admission,
and are removed on normal completion. Owned interrupted temporary state is not
a lifecycle fact and may be removed only under the exclusive store lock.
Standard error is discarded; standard output capture is capped during execution,
not collected unboundedly and checked afterward. Reserve the maximum 24 MiB test
temporary allowance before launching Java; actual write/sync failure remains a
visible operation failure even if external disk use races preflight.

A test process timeout, nonzero exit, oversized output, invalid output or unequal
complete outcome fails the test. Capture bounded sanitized status and hashes;
original source/event bodies remain private. Do not return arbitrary subprocess
stderr as an operational diagnostic. Fixed capacity exhaustion stops mutation or
admission visibly; it does not evict active/recovery/held artifacts. The store
requires capacity planning or a separately designed migration when history is
full. No unbounded outage, throughput or disk-failure guarantee is made.

## P15b control protocol and authority

One locally authenticated administrator authority owns a deployment. The CLI has
no listening endpoint. Store roots/credentials are private to the owner; broker
administration and control paths remain private network services. A second
unrecognized authority cannot write a deployment's desired state. P17 API/UI is
not a prerequisite and will reuse these validators later.

The closed command carries `version`, `authority_id`, `deployment_id`, `request_id`,
`revision`, `previous_sha256`, `action`, `bundle_sha256`, `compatibility_sha256` and
`participants`. Actions are `activate`, `rollback` or `membership`. Participants
are explicit unique `{worker_id, incarnation}` pairs, canonically ordered. Genesis
has revision 1 and null previous hash; subsequent revisions are exactly previous
plus one and bind the previous command hash. The authority publishes to one
ordered private control partition keyed by deployment. Topic/cluster identity and
authority binding are pinned; ordinary source-input rows cannot become controls.

Exact request retries return the original command/result. Same request ID with
different content, conflicting same revision, wrong previous hash, stale authority,
reordered/skipped revision or incompatible bundle is rejected without rewinding.
A worker missing earlier commands catches up from the verified durable sequence;
it cannot treat a later number as proof that preceding state was applied. Revision
overflow fails closed. Publication records broker acknowledgment separately from
local preparation. Uncertain publication is retried only with identical identity
and bytes; it never creates a different revision to hide ambiguity.

The authority retains desired command and participating membership durably before
reporting publication. Publication, receipt, validation, application, durable
application and overall convergence are separate states. Failed distribution or
validation leaves prior valid worker state; partial application is explicitly
mixed. A deadline exposes incomplete convergence; it does not turn missing workers
into implicit success or roll back revisions.

## Workers, atomic selection and recovery

Each worker has stable deployment-scoped identity and an explicitly registered
incarnation. Replacement/restart requires a new incarnation registration; old
acks cannot satisfy the current participant. Membership changes require a new
ordered authority command and remain visible. No automatic timeout silently
removes a participant. A joining worker stays unready for new work until it has
resolved/validated the intended bundle and restored or initialized compatible
state. Membership alone is not proof that the process is running.

Selection changes atomically between source/assembly transitions. One transition
captures one immutable evaluator reference and command identity before producing
its complete projected result. The committed transition and all resulting intents
carry that actual identity. An audit group already open at activation preserves
its original raw membership, source/quality policy and late links; it evaluates
with the active compatible evaluator at its closure transition. This matches the
existing closure-time projection structure, rather than retroactively changing
source assembly or freezing an unobserved opening-time detection decision.

An already committed outbox intent is never re-evaluated after activation or
rollback. An uncommitted capacity-blocked proposal is discarded and retried under
the policy active when the transition actually commits. Do not report abandoned
proposals as processing decisions. Each event, detection and diagnostic records
actual plan/bundle, command revision, worker/incarnation and fixed processing
versions. Intended global state is not substituted for the actual local decision.
Temporary mixed workers remain inspectable with their different actual versions.

The new checkpoint binds deployment/runtime/profile/source identities and stores
last verified command, applied selection, inbox, assembler state, immutable outbox,
sequence counters and the reference set required to recover it. Restore validates
all identities, hashes, bounds and artifact availability before processing.
Never restore a new runtime from old P13 checkpoint bytes or another worker's
incompatible state. Control replay cannot overwrite newer restored state with an
older command. A compatible restart restores old decisions exactly, then catches
up in ordered revisions before readiness.

The worker acknowledgment names authority/deployment, worker/incarnation, command
revision/hash, actual bundle/compatibility, phase and applicable checkpoint ID.
An applied acknowledgment describes real selection; a durable acknowledgment is
released only after the checkpoint containing that selection completes. It is
not a receipt-only ack. Broker-acknowledged publication of that acknowledgment is
another fact. Checkpoint abort, process crash or sink failure cannot fabricate it.
Convergence requires durable acknowledgments for the intended command and bundle
from every current explicit participant incarnation, with no unresolved conflict.
A prior command's acknowledgments cannot satisfy a later rollback or membership
revision even when the selected bundle is identical.

## Rollback, retention and preservation

Rollback is a new increasing revision selecting an earlier retained, staged,
compatible immutable bundle. It does not rewind desired history, worker counters,
source offsets, assembler membership, event identities or historical evidence.
It cannot resurrect an incompatible checkpoint. A missing, corrupt, retired or
incompatible target fails before publication/application; old valid selection is
preserved. Partial rollback remains mixed until the explicit participants durably
acknowledge the rollback revision.

Retain closure objects reachable from staged/active bundles, prepared or pending
commands, all actual participating worker versions, inbox/transition/outbox state,
retained checkpoints/recovery records, historical/current replay pins and explicit
holds. Unknown references block deletion. P15a's conservative nondeleting store
satisfies this boundary without pretending to implement cross-service garbage
collection. P15b must demonstrate pin acquisition before making a dependency
reachable and release only after durable replacement/recovery evidence. Reference
scan and retirement share an operation exclusion boundary; no check/delete race.
P14 archive evidence holds/pins remain authoritative for their own catalogs; a
lifecycle request does not remove or rewrite them.

P16 will qualify combined broker outage, disk pressure, archive lag and admission
limits using these explicit facts. It may tighten operational stop-admission
thresholds, but cannot reinterpret Kafka acceptance, archive durability, processing
completion and indexing as one acknowledgment. No silent shedding is permitted.

## Qualification, gates and architecture disposition

Before P15a production code, commit this owning design and the independent case
matrix as a distinct freeze. Demonstrate meaningful behavioral red for missing
lifecycle transitions rather than a missing-import/setup error. Run focused
positive/negative/boundary/failure tests, actual Java candidate tests, applicable
Python/Java/contracts/hygiene checks and unchanged old-consumer compatibility.
Record exact source/dirty state, executable/plan/bundle/report hashes, commands,
platform, retained failures and coverage limits. Test oracle expectations remain
independent of the implementation being run.

P15b additionally needs actual mixed-worker publication/application/ack failures,
incarnation replacement, joining/restart, broker outage, checkpoint abort/restore,
resource exhaustion, closure-time old/new work and rollback qualification on the
actual artifacts. A controller model/unit test cannot establish these runtime
claims. Preserve all old source detection/replay regressions; no generic retry,
resource expansion, fault-marker relaxation or expected-output regeneration is
justified by a failed runtime attempt.

The chosen additive version boundary, closure-time compatible evaluator selection,
explicit membership and nondeleting P15a store refine accepted A05/A06. They do
not require a new architecture decision. True consequential alternatives would
include dropping open groups on activation, using timeout to remove participants
silently, sharing local filesystems as a distributed requirement, permitting
unauthenticated remote administration, or weakening old artifact/restore guards.
Do not implement those alternatives without owner discussion and an ADR.

P14 acceptance, P15 semantic/completeness acceptance, merge authorization and
release authorization remain distinct gates. This design grants none of them.
