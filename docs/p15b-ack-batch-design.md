# P15b qualification ACK signature batches

This additive qualification helper removes repeated JVM startup from finite ACK
readback. It changes no worker semantics, signature algorithm, source expectations,
checkpoint proof rule, resource ceiling or deadline. Normal controller operations
retain the existing verifier unless the first-party qualifier explicitly requests
`qualification_batch=True` on `observe` or `inspect_acks`.

## Frozen boundary

The new `LifecycleAckVerifier` exists only in the hash-pinned qualification JAR.
Its four arguments are expected qualification SHA-256, expected runtime SHA-256,
private request path and expected request SHA-256. It verifies its own code origin,
unchanged runtime support and original producer/schema code origin, and the common
classloader, before processing. The runtime-first classpath prevents substitution.
It has no broker access, signing key, state mutation or publication function.

The request is canonical JSON with exactly `version` (`1.0.0`) and `records`.
Each record has exactly `index`, `public_key`, `wire_base64`, `wire_sha256` and
`key_sha256`. Indexes are dense from zero; public_key is canonical base64 DER SPKI.
The request is a private owned regular single-link file0600 under a private0700
parent, at most16MiB. There are1–128 records, each wire1–65536 bytes, total wire
bytes at most8MiB. Digests and canonical base64 must match. All request structure,
paths, bounds and key construction validate before verification. Keys come only
from the controller's existing immutable incarnation registration, never the ACK.

One existing256MiB JVM calls the unchanged `LifecycleCrypto.verify("ack", ...)`
for each wire. Known signature/wrapper invalidity returns `verified:false` with
`category:signature_invalid`, matching the existing helper's caught exception
classes. Key construction, helper, storage or protocol errors fail the batch;
they must not be relabeled as invalid remote signatures.

The canonical result is at most64KiB with exactly `version`, `request_sha256`
and `results`. Dense result rows have `index`, `wire_sha256`, `key_sha256` and
boolean `verified`, plus only `payload_sha256` if true or only fixed
`category:signature_invalid` if false. Raw ACKs, payloads and exception messages
are not printed. Every result must match the immutable request and all results
must validate before any new ACK journal/cursor effect.

## Controller and evidence discipline

The opt-in controller path prepares only schema-valid ACKs with known immutable
incarnation keys, retains the actual wire bytes and invokes one pinned helper.
Malformed or unregistered messages still traverse ordinary rejection checks.
Its proof map is local to that one readback call and cleared in finally; keys bind
wire and public-key hashes. A missing, changed, extra or malformed proof fails
closed as infrastructure integrity failure. Every normal deployment, membership,
command, compatibility, signature, identity and budget check remains mandatory.
Each accepted or rejected record and its contiguous cursor is still durable before
Kafka offset commit. No record is skipped, no uncertain input is resent, and no
checkpoint completion is inferred from signature verification.

The existing small polling quantum and exact completed-checkpoint/ACK join remain.
New qualification JAR identity gets its own attributed qualification; earlier full
passes are retained with their original artifacts. This design and the separate
[independent expectations](p15b-ack-batch-expectations.md) freeze before code.
Production runtime055a, original producer51a and validatorf2 remain unchanged.
