# Independent P15b runtime fixture packet

Original DetectBridge synthetic fixtures and local modifications, Apache-2.0 under
[the repository license](../../../../LICENSE). No private recording, downloaded
rule, credential or generated implementation output is included. This packet was
authored before the P15b runtime using original source specifications and standalone
SHA-256/canonical JSON calculations. No compiler, evaluator or new runtime was run
to create its expected results.

## Rules, source references and provenance

[rules/a-windows.yml](rules/a-windows.yml) exactly preserves the original
[P15a Alice rule](../../../lifecycle/v1/fixtures/rule.yml).
[rules/a-linux.yml](rules/a-linux.yml) exactly preserves the original
[P12 whoami rule](../../../../packages/linux-adapters/fixtures/rules/image-match.yml).
B changes only the literal `User: Alice` to `User: Bob`, or
`Image: /usr/bin/whoami` to `Image: /bin/false`. Stable rule IDs are retained;
exact new bytes have different revisions.
[provenance.json](provenance.json) binds original paths/hashes/repository revision,
license/authors and one original-to-modified hash lineage per B rule. Nothing
suggests that B was present in the upstream original file.

[source-references.json](source-references.json) pins the exact public source and
mapping file hashes, canonical snapshot hashes and byte lengths for the same four
source families in A and B. It references existing files rather than copying
unreviewed or private originals. Pinned repository base is owner-merged P15a
`f44403e2975db46554c9c5033f87886d880c4087`; its merged-main qualification remains a
separate prerequisite record. Neither a reference nor a file hash proves runtime
compatibility.

| Rule | A exact YAML SHA-256 | B exact YAML SHA-256 |
| --- | --- | --- |
| Windows | `80b56d4d28e6ec60510c989b34ac4e3f708e42c14d9e5270f463dcb7afa3fc6a` | `62e160bea372e420a38b81e560b529f628074e5693e4275329245598efd7dfa4` |
| Linux | `6374bd348d60b359818b81c97fdaf269935a035d4e59386b2d7d55d7d8c6e15c` | `d20e34e80686615514b4ab587ad9d202b91040f6f16099beb39e3fd55d1887b6` |

## Actual source admissions and independently expected decisions

[source-cases.json](source-cases.json) contains four complete public synthetic
admission sequences. They use original trusted host/source-generation forms,
original source/mapping snapshots and explicitly synthetic provenance. Every raw
inline payload, evidence hash, source cursor, raw record ID and expected event ID
is a frozen literal; runtime tests must not regenerate those expectations from
worker output.

- `security-alice` uses unchanged original public synthetic XML bytes with an
  explicit new P15b cursor/run. `security-bob` changes only the XML subject-user
  value from Alice to Bob. The existing target user remains Bob; domain/SID and
  all other synthetic fields remain unchanged. This is a deliberate new synthetic
  source event, not a claim about recorded real identity or a normalized-field edit.
- `audit-whoami` follows the existing public P12 synthetic six-record source
  recipe: SYSCALL, EXECVE, CWD, two PATH rows and EOE. `audit-false` changes the
  executable/path from `/usr/bin/whoami` to `/bin/false`, EXECVE a0/a2 from whoami
  to false and the audit serial from 7 to 8. Its distinct cursors and raw IDs
  prevent accidentally deduplicating the two executions. It preserves the empty
  middle argument, loader path, source-defined grouping and trusted generation.

Exact evidence hash is SHA-256 of original UTF-8 inline bytes, including terminal
LF. Native record identity is `sha256:` plus SHA-256 of canonical JSON
`[namespace, instance, ["native", cursor_value]]`. Event identity is the same hash
construction over `[namespace, instance, sorted_member_record_ids]`; the Windows
standalone member set has one record. These are accepted P03/P11/P12 identity
rules, computed here independently of any new adapter or worker execution.

[expectations.json](expectations.json) contains complete compact outcomes for both
bundles. Each applicable predicate is literal equality. Alice/whoami matches only
A; Bob/false matches only B. The other product's rule is inapplicable, so eligible
cases have either matched=1 or unmatched=1 and inapplicable=1; every other count
is zero. Matches name the actual rule ID and exact A/B revision above. These
cases produce no compact diagnostics. Quality-skipped/authentication and fault
cases remain independently specified in the
[P15b expectation matrix](../../../../docs/p15b-expectations.md), not inferred from
these four eligible examples.

## Logical identity vectors and effective control ordering

[identity-vectors.json](identity-vectors.json) stores exact array preimages,
canonical compact UTF-8 bytes (as JSON strings) and independently calculated
SHA-256 identities. Repeated-digit command hashes/inner IDs are synthetic vector
inputs, not claimed runtime artifacts. Domain is `detectbridge.p15b.output/1`.
The preimage contains deployment, stable worker, effective integer control revision,
complete effective unsigned control hash, inner kind and stable inner key.
Incarnation, raw document checksum and physical sequence are excluded.

A→B→A uses effective publication revisions 1, 2, 3. These are independent from
P15a inspection-only proposal revision/predecessor fields. The new publisher
adopts exact proposal bytes and allocates authoritative effective revisions; a
skipped/unpublished proposal cannot become an implicit worker command. Vectors
cannot prove signature validity, publication, application or checkpoint durability.

Persisted intent retries preserve original incarnation, exact bytes and logical
identity. Fresh replacement-incarnation work requires a newer signed membership
revision; restart cannot relabel old intents or evaluate under an unregistered key.
Exact-body integrity and semantic duplicate/conflict projections remain separate
checks. A raw receipt-clock change must not mint another logical output identity.

## Raw mutation audit and phase isolation

Windows Bob differs from Alice only in raw XML `SubjectUserName`. Existing
`TargetUserName=Bob` is unrelated to this mapping and remains unchanged;
`SubjectDomainName=LAB` and the original synthetic SID remain explicit source
fields. The independently expected normalized changes are `user.name` and
`source_fields.SubjectUserName`; normalized user domain/ID, process fields, source
contract, trusted host and evidence provenance retain their source meaning.
Evidence bytes/hash and the deliberately distinct cursor/raw/event identities
remain separately attributed. Do not infer identity from the username.

Linux false changes exactly SYSCALL `exe`, PATH item 0 `name`, EXECVE `a0` and
`a2`, and the source audit serial 7→8 on every record in that group. It preserves
syscall=59, success=yes, exit=0, pid=42, items=2, argc=3, empty a1, CWD=/tmp,
PATH items 0/1 with loader `/lib/ld.so`, the timestamp and EOE. Those facts satisfy
the same accepted source assembly completeness policy; expected normalized
executable is `/bin/false`, args are `["false", "", "false"]`, path items are
`[0,1]`, quality is eligible and closure is `source_boundary`. Every expected
member ID is independently frozen in the sorted set; no nearby-time/PID inference
creates membership. The original and modified groups use explicit distinct native
cursors and serials rather than silently replacing accepted evidence.

Fixture preparation must verify that each B YAML/source mutation actually changes
the declared field/bytes and that every declared modification input/output hash
differs. A no-op substitution cannot satisfy the B fixture. Provenance lineage
validation already rejects identical input/output revisions; fixture checks must
also reject an accidentally unchanged Bob/false source payload. This requirement
does not prohibit ordinary exact-idempotent command retries or membership commands
selecting an unchanged policy.

The A→B→A phase schedule in `expectations.json` uses six explicit worker/phase
runs. Windows stable worker `71500000-0000-4000-8000-000000000020` owns run UUID
suffixes 101, 102 and 103; audit stable worker
`71500000-0000-4000-8000-000000000021` owns suffixes 201, 202 and 203.
Override only each routed admission's `context.run_id`; original
raw bytes/cursors/record IDs, source member sets and event IDs stay unchanged.
Each phase pins its two worker/run assignments and corresponding exact context
hashes. This pre-freeze correction follows permanent signed run-to-stable-worker
ownership: one shared phase run cannot be split between Windows and audit workers.
It is a source-routing contract correction, not a response to runtime/evaluator
output. The prior draft packet is retained privately under
`.cache/p15b-prerequisites/independent-fixtures-before-run-routing-correction/`.
Distinct runs are necessary:
redelivering the same raw occurrence in the same run must remain a deduplicated
source retry, not an artificial second detection evaluation. Run-specific processing
identities remain isolated while actual effective control revisions select A/B/A.
This scenario therefore qualifies new-run policy evaluation and rollback without
weakening accepted source deduplication. Separate synthetic identity vectors cover
the logical same-inner-key A1/A3 revision distinction.

The exact underlying retained semantic documents remain unchanged inside lifecycle
output envelopes. Effective command hashes include the complete unsigned publisher
control payload, including registration snapshot and runtime execution binding;
a P15a proposal hash alone cannot stand in for that identity. The vector packet's
repeated-digit hashes are explicitly fixed synthetic effective-control inputs.

For the exact four-case core schedule, each phase has 14 source admissions and
receipts, four tagged events, two detections and two audit manifests: 22 logical
source-output envelopes. Three phases yield 42 admissions/receipts, 12 tagged,
six detections and six manifests: 66 logical source-output envelopes. There are
no core processing diagnostics, preservation or quarantine outputs. This arithmetic
follows source memberships and the literal match matrix, without runtime output.
Control/artifact/ack wires, intentional duplicate physical delivery, and any added
run-end or fault admissions require separate accounting; they are not silently
folded into these exact schedule totals.

## Runtime and checkpoint binding vectors

[binding-vectors.json](binding-vectors.json) independently pins the exact common
runtime and stable-worker checkpoint preimages in the
[contract README](../README.md). Each vector includes its complete canonical JSON
bytes, all current fixed limits and expected plain lowercase SHA-256 (no
`sha256:` prefix). Standalone Python `hashlib` calculated these results without
calling any implementation, compiler, parser or evaluator.

Authority/runtime/compatibility/evidence-registry repeated-digit hashes and broker
cluster/topic strings are explicitly synthetic inputs. The retained producer hash
and Flink image reference are existing pins, not newly observed artifacts. The
cloned-topic cluster vector changes **only** `cluster_id`: topic names/IDs,
authority, artifacts, profile and limits stay byte-equivalent. Its common binding
must differ. The worker variants independently change stable worker, input-topic
ID, input-topic name or the common binding inherited from that other cluster;
each must differ from the baseline checkpoint binding.

This catches accidental omission of broker identity before code. A correctly
signed artifact chunk must additionally match `runtime_binding_sha256`; matching
bundle bytes, authority and cloned topic IDs on another broker is insufficient.
A signed control's effective hash includes its common binding and complete
registration snapshot; a proposal-only hash cannot satisfy acknowledgment scope.
These vectors establish canonical expected hashes, not signature correctness or
successful cross-broker runtime rejection. The existing output identity vectors
remain unchanged.
