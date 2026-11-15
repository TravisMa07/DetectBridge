# Independent P12a expectations

Original synthetic cases, Apache-2.0, authored before implementation. No recorded
telemetry copied. Expected outcomes follow source definitions and fixed policy;
they are not generated from parser/evaluator output. Owner semantic review pending.

- Complete execution: SYSCALL arch=c000003e syscall=59 success=yes exit=0 pid=42
  items=2 exe="/usr/bin/whoami"; EXECVE argc=3 a0="whoami" a1="" a2="whoami";
  CWD cwd="/tmp"; PATH item=0 name="/usr/bin/whoami", item=1 name="/lib/ld.so".
  At EOE, eligible, args exactly [whoami, empty, whoami], both paths retained,
  PID 42, no command_line/file.path. This is successful execve plus complete counts.
- Hex/split: argc=2 a0=77686F616D69 a1_len=8 a1[0]=6162 a1[1]=6364.
  Args [whoami, abcd]. Hex length is 8 emitted digits for four bytes. Reordering
  fragment arrival does not change positions. a1_len=4 is inconsistent and skips.
- Distinct positions with identical EXECVE bytes remain two members and conflict
  in argument slots; exact same record-ID retry contributes one member.
- Missing SYSCALL, argc/argument holes, sparse PATH items, conflicting counts,
  unsuccessful syscall, unknown ABI/syscall/type: skipped independently of EOE.
- EOE first closes an incomplete immutable group. All following records are late,
  individually preserved/linked/skipped. No later eligible event replaces it.
- Runs, trusted hosts, generations and source instances with identical timestamp
  and serial form different groups. Missing host/generation never merges records.
- Boundary/timeout/dataset_end do not fix missing evidence. A complete group at
  those closures stays eligible; resource_limit forces skipped. Absolute deadline
  is first admission+30000ms, unchanged by trickle. Overflow does not lose members.
- Persistence failure: no state/input progress. Retry commits same membership.
  Serialized roundtrip retains partial groups, absolute deadlines, receipt IDs and
  closed keys; incompatible policy/version fails, not implicit regrouping.
- Auth <38>1 2026-01-01T00:00:00Z display sshd 7 - - Accepted password for alice
  from 192.0.2.1 port 2222 ssh2: eligible, user alice, success, literal IP/port.
  Failed password with 2001:db8::1: failure with IPv6 unchanged. NIL timestamp:
  first_observed fallback with timestamp_missing warning. Invalid PRI/header,
  timestamp, IP or ports 0/65536: invalid. Publickey, invalid user, PAM, localized,
  RFC3164/journald: unsupported; no fabricated auth event.
- P10 evaluator: image equals /usr/bin/whoami matches eligible complete output;
  image equals /bin/false does not. CommandLine rule is configuration_blocked by
  unsupported capability. Incomplete output is quality_skipped. Auth User=alice
  matches accepted and failed alike; outcome does not alter username matching.

Independent identity cross-checks use the P03 compact array preimages and Python
stdlib SHA-256, without Java adapter/evaluator execution. For synthetic namespace
original-synthetic, instance a and native cursor synthetic-position-0, record ID
is `sha256:d844c75430581095cf915d0f6ccd412a21b181e79d9c525293e9bf38178ee119`.
The exact SYSCALL LF bytes above have SHA-256
`4554fb95fca6d5ed7e8f3ba562cf89bf8cec09586c526e0f6e228d59f8a5006f`.
Membership at native positions 0 through 5 (five records plus EOE) gives event ID
`sha256:45c509e3f82ee0b547bffd5b241b0f6f18bf55a81646572f673524276f3dd12f`.

Bounded descriptor case: a valid retained raw occurrence can have an 8000-character
native cursor or evidence locator. The complete cursor/locator remains in the
original retained raw envelope, bound by its canonical hash. A descriptor larger
than 2048 serialized bytes uses record ID/evidence hash/raw-envelope hash and
retention=retained_raw, with no truncated cursor or invented URI. Thus 256 member
descriptors fit below the 1 MiB manifest cap even for large original metadata.

Orchestrator review correction against RFC5424 §6.3.3: repeated parameter names
are valid, and an unknown backslash sequence is retained literally. Both preserve
the exact structured-data string and keep otherwise valid auth eligible. Repeated
SD-ID, unescaped closing bracket and unterminated parameters remain invalid. These
expectations are grounded in the RFC, independent from parser output.
