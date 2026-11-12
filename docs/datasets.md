# Recorded dataset acquisition

P04 adds selective acquisition and provenance, not parsing, record assembly,
normalization, raw-envelope emission or detection labels. P03 contracts are unchanged.
Downloaded bytes are retained exactly as published. All seed data comes from
controlled attack simulations, not representative benign production traffic.

## Catalog and commands

Manifests and their schema live in `catalog/datasets/`. Version 1.0.0 currently
allows four reviewed Splunk Attack Data artifacts at revision
`4b19e4b6824a8ba91b0f5345a3a8de488619e823`:

| Catalog ID | Bytes | LF records | Content |
| --- | ---: | ---: | --- |
| windows-security-4688 | 11,176 | 8 | Windows Security 4688 XML |
| windows-sysmon-mixed | 12,883,992 | 7,010 | Multiple Sysmon event types |
| linux-audit-whoami | 1,510 | 3 | Raw Linux audit records |
| linux-audit-network-tools | 12,321 | 25 | Raw Linux audit records |

```sh
uv run --locked python tools/check_datasets.py
uv run --locked python tools/datasets.py list
uv run --locked python tools/datasets.py fetch windows-security-4688 linux-audit-whoami
uv run --locked python tools/datasets.py fetch --all
uv run --locked python tools/datasets.py verify --all
```

`list` and `verify` do not access the network. Fetch requires explicit IDs or
`--all`; unknown IDs or ambiguous selection fail before downloading. Verification
checks existing objects and never repairs through network access. Each selected
artifact gets a result; any failure produces a nonzero exit code. Output contains
IDs, hashes, resource outcomes and counts, never event bodies.

The offline catalog check is included in `tools/dev.py check`. Public download
availability is not a standard PR merge dependency. Catalog schema validation is
separate from the fixed P03 event-contract registry.

## Provenance and terms

Each manifest pins repository revision/path, payload and LFS pointer hashes/sizes,
scenario metadata and license objects, attribution, ancestor review and limitations.
The license review at the pinned revision found root Apache 2.0 terms and no
additional applicable ancestor/artifact license or NOTICE. Acquisition retains
that license and the author/scenario metadata as verified local objects.

Scenario ATT&CK associations are context only. Record-level labels remain unknown.
Metadata dates are not asserted to be event capture times. The Sysmon recording
must not be classified wholesale as process creation. Linux audit excerpts do not
establish complete assemblies or stable host identity. Dataset capture identity
identifies provenance, not a fabricated host. Later parsers must retain these gaps.

OTRF and EVTX sources are deferred pending separate artifact/terms review. Unknown
licenses, additional notices or new sources require a reviewed catalog extension.
No payload or copied telemetry sample is committed. Synthetic unit fixtures are
created temporarily and are not claimed to be recorded security events.

## Transport and integrity

Downloads use actual GitHub media payloads, not LFS pointer text or whole-repository
clones. Only HTTPS on raw.githubusercontent.com and media.githubusercontent.com is
allowed, with no user information, query credentials, fragments or nonstandard ports.
Manifest URLs must match the pinned repository/revision/path. Every redirect is
validated, with at most three redirect hops per attempt.

Transfers stream through SHA-256 checking and exact-size bounds, with 30-second
network-operation timeouts, a shared 120-second artifact deadline, and at most three
attempts for transient failures. Backoff is 1 then 2 seconds, bounded by deadline.
Integrity failures are not retried. Each read checks remaining time and updates the
underlying socket timeout where the standard library exposes it. DNS resolution
and OS filesystem calls remain subject to OS behavior rather than a hard process
kill deadline. No untrusted transfer exception text is printed.

Maximum object size is 32 MiB and selected batch size is 64 MiB, including
provenance objects conservatively counted per selection. Oversized, truncated,
corrupt, unexpected encoded or pointer-only payloads fail. Archives (ZIP, gzip,
bzip2, xz and tar signatures) are rejected; no extraction is implemented. New
compression support requires a reviewed extension and extraction safety tests.

## Cache and reports

Objects live in ignored `.cache/datasets/objects/sha256/<digest>`. Reports live in
`.cache/datasets/reports/`. Existing objects are rehashed before reuse. Offline
verification exposes corruption; fetch replaces a corrupt object only after a
new temporary download verifies, reporting repaired_corrupt_cache explicitly.

Objects use unique temporary files followed by atomic replacement. Concurrent
writers publish only verified bytes; completed reports are also atomically
published. No partial file is treated as a complete object/report. Files are
flushed/fsynced before publication; this is not a replicated archive or a guarantee
against whole-disk loss. Existing verified payloads can be shared across manifests.

Reports record tool version, catalog ID, canonical manifest SHA-256 (sorted keys,
compact UTF-8 JSON), payload hash, verification/acquisition time, verified
provenance object hashes/outcomes and framing inventory. Report timestamps are
administrative observations, not historical first-observed or occurrence time.
Reports differ by timestamp/outcome on repeated fetch; original payload bytes do not.
No record-level malicious/benign judgment or normalization is produced.

## Byte framing

`lf-byte-records-v1` assigns zero-based physical record positions and byte offsets.
LF remains part of its record; CR in CRLF is preserved. Blank records are included;
a final unterminated record is included; a terminal LF does not create a fictitious
extra record. Offsets and lengths partition the complete original byte stream.
UTF-8 is validated without decode/re-encode transformations. Record count must
match the pinned manifest before payload publication.

P05 will use these positions and artifact hashes for raw-record cursors and replay.
P11/P12 own format parsing, event eligibility and source-specific assembly. Framing
is not a claim that each Linux audit line is an independently complete event.

## Linux opt-in qualification

After merge, dispatch **Recorded dataset qualification** (`acquire-datasets.yml`)
from Actions. It fetches all four artifacts twice and verifies them offline using
read-only permissions and a bounded job. Results are in workflow logs; payloads
are not uploaded as artifacts.

Before that workflow exists on the default branch, dispatch the existing workflow
against this PR branch using its explicit opt-in input:

```sh
gh workflow run hygiene.yml --ref feat/p04-dataset-catalog-acquisition -f acquire-datasets=true
```

The optional acquisition job is deliberately not a dependency of required-checks.
It never runs on ordinary PR events. Review its own conclusion separately from
required-checks. No secrets or deployment credentials are passed.
