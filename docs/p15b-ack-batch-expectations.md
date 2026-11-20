# P15b qualification ACK signature batch — independent expectations

Status: pre-implementation expectations. The owning design freezes literal field
names and invocation before code. These cases derive from the accepted signed ACK,
scope, journal-prefix and checkpoint contracts in [P15b design](p15b-design.md),
the existing `LifecycleCrypto.verify("ack", ...)` implementation, and
[independent runtime expectations](p15b-expectations.md). No new verifier output
or observed worker result supplies an expected value.

This qualification-only helper amortizes signature verification startup across a
bounded read. It does not authenticate publisher adoption, deployment membership,
checkpoint completion, or source processing by itself. Production runtime055a,
original producer51 and compiler packet remain unchanged. The separate
qualification JAR gains the fixed `LifecycleAckVerifier` entrypoint; actual code
source, classloader and QA/runtime/original artifact identities must be verified
before request processing. Candidate content cannot select a verifier or key.

## Protocol and claim boundary

The canonical closed request has version1 and a dense indexed record array. Each
record binds its index, canonical SPKI public-key base64, canonical exact-wire
base64, SHA256 of decoded wire, and SHA256 of decoded public key. The owning design
specifies their literal JSON names and version representation. Bounds are1–128
records, each decoded ACK wire at most65,536 bytes, at most8 MiB total decoded wire,
at most16 MiB complete serialized request, and at most64 KiB result. Counts and
indices reject booleans, fractions, overflow, gaps and duplicates. The request is
a 0600 current-UID single-link regular file beneath a 0700 private parent, with no
symlink path component. No arbitrary command/path/class/network selection is added.

Results bind the exact request SHA, count and dense input indices. Every result
repeats the corresponding wire/key SHA and an exact boolean `verified`. True
requires the canonical verified payload SHA. False requires the fixed category
`signature_invalid` and no success payload hash. Key construction or trusted
verification infrastructure failure is a whole-operation failure, not a false
remote-signature result. Known invalid remote signatures alone may return false.
The helper has no Kafka, private signing-key, worker-state or controller-journal
effects and uses the unchanged ACK signature domain and original cryptography.

Controller `observe` and `inspect_acks` use this helper only with explicit
`qualification_batch=True`; their default path remains ordinary verification.
An ephemeral map keyed by exact `(wire_sha256, key_sha256)` exists only for the
current read. A true signature result discharges only the existing signature
check for those exact bytes and that exact key. All ordinary wire schema,
identity, namespace, registration/incarnation, deployment, command, membership,
binding, semantic duplicate/conflict, journal, admission and checked cursor rules
remain in force. Durable ACKs still require independent exact completed-checkpoint
evidence before qualification can claim convergence.

## Independent matrix

| ID | Input or interruption | Required observation |
| --- | --- | --- |
| K01 | One exact valid ACK and its recorded worker public key | True plus exact original wire/key/payload hashes; ordinary controller validation produces the same bounded result as legacy verification. No checkpoint claim from this result alone. |
| K02 | Ordered mixture of valid ACKs and known bad signatures | Dense per-index true/false results in original order. Bad signature is ordinary `signature_invalid`, not helper failure; unrelated valid signatures remain valid. |
| K03 | 128 entries and8 MiB total exact wire, within serialized caps | Protocol-admissible if every other contract holds; bounded result and no omitted/duplicated index. This is not a throughput claim. |
| K04 | Count0/129, wire65,537 bytes, total wire8 MiB+1, request16 MiB+1 or result64 KiB+1 | Reject at the corresponding boundary before accepting any batch proof. No oversized result can become partial trusted success. |
| K05 | Boolean/fractional/negative/overflow index/count, duplicate/gapped/reordered index, missing/extra field, unsupported version or noncanonical request | Whole-operation fail closed. Do not reinterpret input, silently reindex or accept a matching subset. |
| K06 | Invalid/noncanonical base64, wire/key hash mismatch or changed request SHA | Whole-operation integrity failure before controller journal effects. Hashes bind decoded exact bytes, not their text spelling. |
| K07 | Invalid SPKI, wrong algorithm, noncanonical key encoding or key-construction exception | Infrastructure/registration failure; never ordinary remote `signature_invalid`, never false proof that a recorded key was usable. |
| K08 | Valid key but wrong signature bytes or valid signature under another recorded key | False only under unchanged verifier's recognized invalid-signature condition. Cross-key positive proof cannot be reused. |
| K09 | Signature or wrapper malformed outside the helper's recognized invalid-signature condition | Preserve the established malformed-wire rejection boundary; no arbitrary exception is relabeled a clean negative signature. Controller may send schema-invalid/unknown-registration records through its ordinary rejection path. |
| K10 | Control/artifact-domain signature presented as ACK, or one-bit payload change with old signature | No true ACK proof. Domain separation and exact payload bytes remain mandatory. |
| K11 | True result with absent/wrong payload hash, false result with success hash, wrong category or nonboolean verified field | Reject complete helper response before journaling any item based on it. No truthiness coercion. |
| K12 | Result has wrong request SHA/count/index/wire SHA/key SHA, missing/extra/duplicate result, unknown field or trailing protocol content | Whole-operation fail closed before journal/cursor advancement. Never align responses by position alone or consume a prefix of an invalid response. |
| K13 | Same wire twice under same key versus same wire under different key | Exact duplicate signature work may share only the same per-call pair. Distinct key hashes require separate proof; per-record controller duplicate/conflict rules still execute. |
| K14 | New `observe`/`inspect_acks` call repeats a previous pair | No cross-call positive cache. Verify under this call's actual registration and exact bytes; old helper output is not reusable authority. |
| K15 | Verified signature but wrong deployment/worker/incarnation, stale membership, wrong runtime binding, incompatible command or foreign topic scope | Ordinary controller rejection, exactly as legacy path. A true signature never skips identity or processing-binding checks. |
| K16 | Verified durable ACK without independently confirmed matching checkpoint | No convergence qualification. Exact ACK-named completed proof remains required; latest unrelated inventory is insufficient. |
| K17 | Malformed ACK or unknown registration mixed with valid registered ACKs | Malformed/unknown items retain ordinary rejection behavior. They cannot obtain a helper true proof from an inferred key, hide valid-prefix facts, or turn unknown key lookup into fabricated membership. |
| K18 | Helper crashes, times out, exits nonzero, uses wrong JAR/class origin, wrong classloader, or returns malformed/oversized output | Visible whole-operation infrastructure failure before journal effects. Do not downgrade it to all-signatures-invalid or manufacture per-item results. |
| K19 | Request/private parent wrong UID/mode, hardlink, symlink, file mutation or wrong anchored hash | Reject before trusting request/result. No follow of a foreign path or silent repair of anchored bytes. |
| K20 | Complete response verified, controller processes valid prefix then crashes before/after checked-cursor publication or broker commit | Preserve normal durable journal-prefix and idempotent recovery rules. A batch proof is not a cursor commit; no jump across unchecked records, invented ACK or duplicate conflicting admission. |
| K21 | Infrastructure/protocol failure while a prior read already has durable checked prefix | Preserve prior actual prefix; do not rewind it, erase evidence, or claim the new failed read advanced. A later retry retains exact original wire identities. |
| K22 | Read-only `inspect_acks` in qualification mode | Same signature/identity inspection result as legacy; no journal, checked cursor, broker commit, private key access or worker/control mutation. |
| K23 | Ordinary `observe`/`inspect_acks` without explicit qualification flag | Existing legacy verifier behavior and artifact requirements remain unchanged; qualification artifact availability is not silently required for normal use. |
| K24 | A signed hostile ACK with arbitrary exception/private/source strings | Unknown content stays private or hashed under existing diagnostic rules; no raw payload/exception value leaks into helper fixed failure metadata or public summaries. |

## Evidence and delivery discipline

Use original synthetic signing keys and independent literal payloads for focused
mechanics tests. Verify valid, altered payload/signature, wrong key/domain, strict
response binding, ephemeral scope, journal-before-commit ordering and failures
separately. Test doubles establish their mechanics only. Actual pinned helper
execution and actual Kafka/Flink qualification remain required, followed by the
unchanged default all14 gate; focused successes cannot be combined into a full
pass. Preserve original failed native attempts and record exact new qualification
artifact/source/request/result hashes. No timeout, resource, checkpoint history,
assembler age, source membership or independent semantic expectation is relaxed.
