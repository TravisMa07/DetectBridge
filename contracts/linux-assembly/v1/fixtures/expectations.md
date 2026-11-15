# Independent P12b qualification expectations

Original synthetic cases, Apache-2.0, specified before wrapper implementation.
Use the P12a original raw execution facts: execve x86_64 syscall 59 succeeds,
exe /usr/bin/whoami, arguments [whoami, empty, whoami], CWD /tmp, PATH indices
0=/usr/bin/whoami and 1=/lib/ld.so. EOE after these five members yields six-member
source_boundary closure and eligible output; early EOE yields skipped incomplete
closure and every later member is immutable late evidence. Never join args.

- A prepared transition leaves its original assembler snapshot byte-identical.
- Closing two due groups requires two independently staged closures; input/control
  stays unconsumed until preceding required closure work finishes.
- Before a completed checkpoint, no staged output is externally emitted.
- Restoring that completed checkpoint emits exactly its durable intent set,
  including pending auth/diagnostic/control outcomes; no newly staged suffix leaks.
- Failure after one output collection may repeat that output on restore; repeated
  IDs must have identical bytes, membership, quality and links.
- A completion notification for an aborted/unsealed checkpoint emits nothing.
- Wrong runtime/source/mapping/policy/limits or malformed/corrupt state rejects
  before input/output; generic submission failure alone is not proof.
- Same original occurrence retry within one run contributes one member. Equal
  bytes at a different native position remain separate occurrences. Runs, host
  bindings, generations and exact audit timestamp/serial never cross-assemble.
- Timed-out partial groups retain original age through restart; late EOE links to
  the prior manifest and never makes it eligible. Idle input still fires timers.
- Missing host/generation yields identity_missing preservation; unsupported auth
  remains unsupported_source; malformed wire bytes use bounded hash/location-only
  quarantine, never a fabricated process/auth event.
- A valid Accepted/Failed password for alice yields success/failure respectively;
  no P10 evaluation or writer output is implied by P12b.
- Every original input is accounted by original ID/hash as emitted membership,
  durable pending intent, retained assembly/inbox or visible source backlog.
  Never use evaluator/generated output as the expectation oracle.

Runtime scenarios must independently record exact original record IDs, member
sets, hashes, run scope, closure/eligibility and late links before submission.
Counters supplement these facts; physical at-least-once duplicates are counted
separately from logical outputs. All numeric/byte bounds receive exact/one-over
checks and failure must leave a usable prior checkpoint or retained source backlog.
