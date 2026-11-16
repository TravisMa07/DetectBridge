# P11 completion: controlled Windows capture

Status: implementation in progress; no recorded eligible or owner acceptance claim.
Base c024497 plus local prerequisite/design commit 641923a. This completes the
missing recorded-identity evidence path with a new controlled source scope under
A02/A03; it does not manufacture bindings for the old public recordings.

Use an opt-in GitHub-hosted disposable Windows 2022 AMD64 VM. Capture original
Get-WinEvent.ToXml bytes from the local Security and Sysmon channels while querying
actual MachineGuid, system-product UUID, boot time, local computer/DNS/domain and
account/SID from that same VM. Bind each selected event to independently executed
process IDs/images and the exact capture run/attempt/commit. MachineGuid is scoped
to this inspected VM invocation; no cross-clone uniqueness or live inventory claim.

Freeze action expectations before capture and native source expectations before
adapter/evaluator execution. Launch actual cmd.exe and hostname.exe successfully;
select their two Security 4688 v2 and two Sysmon 1 v5 records, plus one native
Sysmon service-state preservation record. The cmd suffix rule must match only cmd;
a literal impossible image must not match; Linux rule remains inapplicable.
Synthetic P11 tests retain all six outcomes and disabled/absent/error edge coverage.

Pin Sysmon archive SHA-256 00ecf1b46aec99299d3ae0bca79dc621458bd014b20b509d7c5c8e8c8611aa54
and retain its EULA SHA-256 8329bcbadc7f81539a4969ca13f0be5b8eb7652b912324a1926fc9bfb6ec005a.
Source: [Microsoft Sysmon archive](https://download.sysinternals.com/files/Sysmon.zip). Inspected installation
and use terms permit copies on the user's devices; no package/binary redistribution
or software-hosting service is introduced. Install only in the owned ephemeral
runner, verify Microsoft Authenticode signature and retain binary/version/signature
metadata plus terms. Retain original captured data locally for qualification only;
no payload publication or general third-party fixture license is inferred.

Microsoft references: [4688 semantics](https://learn.microsoft.com/windows/security/threat-protection/auditing/event-4688)
and [Sysmon installation/event semantics](https://learn.microsoft.com/sysinternals/downloads/sysmon).
Enable process auditing and command-line policy for the capture; preserve settings
and restore them and uninstall the newly installed Sysmon in finally. Refuse a
non-GitHub Windows host or preexisting Sysmon rather than modifying it.

The optional workflow accepts only a public RSA recipient certificate. Encrypt the
successful original archive with CMS AES-256/RSA before artifact upload. The private
key remains in ignored local storage; decrypt into ignored local evidence. No raw
XML, host details, action output, private key or source error body enters CI logs.
Only encrypted bytes are uploaded with bounded retention. Ordinary PR CI does not
acquire recordings. Capture success alone does not qualify adapter/evaluator output.

Preparation must validate original hashes, exact committed capture/expectation
bytes, run provenance, actual host/capture state and per-action image/PID/parent/account
relations, source signatures, times and capture policy. Require explicit reviewed
local catalog/provenance, not a command that silently labels arbitrary XML reviewed.
Retain full original API bytes and any framing transformation separately. Replays
keep event/evidence IDs stable and change run/result identities. Same-count tampering
of host/context/fields/outcomes/membership must fail independent verification.

Acceptance requires actual capture, frozen independent source expectations, mapped
YAML→Java matching/nonmatching on both profiles, original evidence and complete
attribution checks, atomic publication/replay and existing missing-binding regressions.
Run locked ARM64 and AMD64 checks. Owner semantic review and merge authorization
remain separate; present a concrete review packet after technical evidence exists.
