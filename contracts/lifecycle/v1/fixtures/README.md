# Original synthetic lifecycle test suite

Original DetectBridge synthetic rule and derived test cases, Apache-2.0 under the
repository [license](../../../../LICENSE). No downloaded third-party rule or
recording is included. `rule.yml` is newly authored for P15; its revision is the
SHA-256 of its exact UTF-8 LF bytes:
`80b56d4d28e6ec60510c989b34ac4e3f708e42c14d9e5270f463dcb7afa3fc6a`.

The positive event copies the existing original synthetic
[Security normalized fixture](../../../../packages/windows-adapters/profiles/security.expected.json)
exactly. The negative case deliberately changes only normalized `user.name` to
`Bob`. It is a normalized evaluator test mutation, not a newly parsed source event
or claim that its retained original XML says Bob. Original evidence bytes and
source fixture remain unchanged; neither case establishes recorded-source coverage.

The frozen rule is one applicable Windows process-creation predicate `User: Alice`.
The existing Security mapping maps `User` to `user.name`; the source profile is
eligible and supports the field. Literal equality therefore predicts matched=1
for Alice and unmatched=1 for Bob, with all other counts zero, no diagnostics,
and exactly the declared rule ID/revision in the positive matched list. These
complete compact JSON expectations were authored before P15 implementation and
without running any evaluator. The revision above was calculated with Python
`hashlib` directly over the original YAML, not from compiler/evaluator output.

`cases.json` uses [the closed suite schema](../test-suite.schema.json). The trusted
runner must bind its exact original bytes, candidate plan/closure and pinned Java
artifact in its receipt. Two to 64 unique cases, one MiB per normalized event and
16 MiB for the complete serialized suite are finite admission limits. A caller's
`passed` flag or a receipt for a changed suite cannot satisfy testing/staging.
