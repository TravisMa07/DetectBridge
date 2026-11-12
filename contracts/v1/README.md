# DetectBridge contracts 1.0.0

These contracts define data shapes and validation semantics, not parser, assembly,
archive or detection implementations. All examples are **synthetic**. They are not
captured host telemetry or positive detection ground truth. P04 owns acquisition
of recorded public datasets.

## Versions and schema registry

Schemas use JSON Schema 2020-12 and ECS 9.5.0. Stable schema IDs are
`urn:detectbridge:contracts:1.0.0:raw-record`, `normalized-event`, `source-contract`
and `common` (each prefixed with the same URN base).

The validator registers only repository-local schema resources. The default
referencing registry has no retrieval implementation. Every reference, including
unused branches, is resolved eagerly; unknown IDs, remote refs and broken
fragments fail before event validation. Format checking is explicitly enabled.
No schema or referenced evidence is fetched during validation.

Exact known versions only are accepted. Optional additive changes need a minor
contract revision and explicit reader support. Required-field, type, identity or
semantic changes need a major revision. No automatic version guessing or silent
field dropping is allowed. ECS version is independent of DetectBridge versions.

## Commands

```sh
uv run --locked python tools/check_contracts.py
uv run --locked python tools/check_contracts.py --kind raw-record --document contracts/v1/examples/binary.raw.json
uv run --locked python tools/check_contracts.py --kind normalized-event --document contracts/v1/examples/windows-security-4688.event.json --source-contract contracts/v1/examples/windows-security-4688.source.json
```

The default command checks schema definitions, the example index, source contracts,
events, fixture expectations and inline checksums. `tools/dev.py check` includes it.
Failures print document path, JSON Pointer and stable category, never event values
or exception messages. Structural categories are `schema_` plus the JSON Schema
keyword; semantic categories are fixed codes in the validator.

Invalid envelopes are validation failures, never unmatched detections. A valid
envelope can explicitly carry insufficient-integrity evidence that is skipped.

## Field reference

All defined objects reject unknown properties unless identified as extension
containers. No coercion is performed. Optional ECS fields are absent rather than
null. Integer fields use integer JSON values (not integral floats/booleans) and
are bounded to signed 64-bit maximum for JVM interoperability; raw vendor fields and extension contents can retain JSON nulls.

| Document/field | Meaning |
| --- | --- |
| Raw `contract_version` | Exact DetectBridge contract version |
| Raw `record_id` | Stable evidence occurrence identity |
| `source.namespace`, `source.instance` | Explicit origin scope; never inferred from display names |
| Raw `cursor` | Dataset artifact/position, native cursor, or persisted capture UUID |
| Raw `first_observed` | Immutable first observation of the source record |
| `evidence.sha256` | Lowercase SHA-256 of original record bytes |
| `evidence.encoding`, `media_type` | Byte representation and content type |
| `evidence.inline` | UTF-8 text or strictly decoded base64 |
| `evidence.reference` | Immutable object locator, full-object checksum and optional byte range |
| Normalized `@timestamp` | Declared source occurrence time, or explicitly labeled observation fallback |
| `ecs.version` | Pinned ECS version, currently 9.5.0 |
| `event.id` | Identity of source plus constituent record IDs |
| `event.code` | Source event type code, e.g. string `4688`, not an occurrence ID |
| `event.kind/category/type` | ECS categorization; category and type are nonempty arrays |
| `event.created` | First-observed time, if provided; must match metadata |
| `event.ingested` | Actual arrival at a central datastore, only when known |
| `event.action/outcome/provider/dataset` | Optional source context; outcomes are success/failure/unknown |
| `host.id/name/hostname/ip` | Source host identity/display/IPs; IP is an array |
| `user.id/name/domain` | Optional source identity information |
| `process.pid` | Nonnegative integer; PID is not a globally stable process identity |
| `process.entity_id/name/executable/command_line/args/working_directory` | Selected process context; repeated args are preserved |
| `process.parent` | Same selected process fields without recursive parent nesting |
| `source.ip/port` | Remote endpoint; IP string and integer port |
| `file.path/name/size` | Selected file context; byte size is a nonnegative integer |
| `source_fields` | Preserved source names/JSON values, separate from normalized fields |
| `detectbridge.source_contract` | Exact source contract ID and version |
| `detectbridge.processing` | Parser, mapping and normalizer version identifiers |
| `detectbridge.run_id` | Processing/replay UUID, independent from evidence identity |
| `detectbridge.time` | Source value, source UTC interpretation, basis, quality, first observation and stage times |
| `detectbridge.evidence` | Record identities and inline/reference evidence membership |
| `detectbridge.assembly` | Mode, closure reason, evidence quality and assembler version |
| `detectbridge.quality` | Integrity, detection eligibility and value-free diagnostics |
| `detectbridge.extensions` | Namespaced object keys such as `example.context` |

This is a documented ECS subset, not all ECS fields. Proposed new fields require
an explicit schema revision. Source-specific fields are preserved rather than
silently promoted to an undefined ECS field.

## Evidence representation

Exactly one of inline or reference is required. Inline digests are verified over
UTF-8 bytes or strictly decoded base64 bytes. Reference checksums cover the entire
object and the selected record bytes separately; byte ranges use zero-based offset
and positive byte length. For a reference without a range, both hashes describe
the entire object and retrieval must verify both.

Allowed schemes are `urn:sha256:`, HTTPS, S3 and file. URN content addresses must
match the object checksum. User information, query strings and fragments are
rejected: signed URLs and embedded credentials do not belong in the contract.
Store authorization outside evidence data. HTTPS/S3 references require a host.
A locator alone does not establish immutability; its object checksum identifies
the immutable version. Availability, byte-range bounds and referenced digests
are verified by later acquisition/archive consumers, not by this offline tool.

## Identity canonicalization

IDs are `sha256:` plus lowercase SHA-256 of UTF-8 compact JSON. Use no whitespace,
no ASCII escaping, no Unicode normalization, and fixed array positions. Identity
inputs contain strings and arrays only; cursor positions become decimal strings.
Integers cannot be replaced with floats or booleans. Names are case-sensitive.

Record preimages are:

```text
[namespace, instance, ["dataset", artifact_sha256, decimal_record_position]]
[namespace, instance, ["native", source_cursor]]
[namespace, instance, ["capture", persisted_capture_uuid]]
```

Dataset positions are zero-based record positions under the acquisition/framing
version, not guessed line numbers for multiline records. P04/P05 define each
artifact's framing. If framing changes, use an explicitly different source-instance
scope. Native cursors must identify occurrences within the instance (including
boot/channel/generation where required). Capture UUIDs are assigned once before
retry and persisted; replay never assigns a replacement.

Normalized event preimages are `[namespace, instance, sorted_record_ids]`. Sort
ASCII ID strings lexicographically and reject duplicate/empty membership. Processing
versions, wall-clock time and run UUID are excluded. Same bytes at different source
positions are different records. Different grouping changes the event ID; reprocessing
must retain links to its original evidence. Late evidence never mutates an emitted
event. Record order does not change identity.

`identity-vectors.json` contains literal preimages and expected digests computed
with the independent system SHA-256 utility. They are cross-language fixtures for
future Java implementations.

Detection identity is separate: P13 will derive it from event identity, run UUID,
rule identity/revision and processing-bundle identity. This PR deliberately does
not freeze a detection wire format or implement a detection-ID helper.

## Time policy

Normalized timestamps are calendar-valid RFC3339 UTC strings ending in `Z`, with
fractional precision preserved as supplied. Offset/local source representations
remain in `time.source_value`; parsers later produce the UTC interpretation.
This validator checks the declared interpretation, not the source parser's work.

For source time, basis is `source`, quality is `valid`, `source_value` is present,
and `source_utc` equals `@timestamp`. Missing, unparseable or timezone-ambiguous
occurrence time uses basis `first_observed`; `@timestamp` equals immutable
`time.first_observed`, and no `source_utc` is present. Preserve an available
unparseable/ambiguous original value. Never guess a timezone.

Replay preserves original evidence identity and first observation. New receipt
and processing times use `time.received/processed`, not replacement occurrence
or first-observation fields. Clock skew is not rejected through chronological
ordering assertions. Fallback does not prove trustworthy event-time ordering or
correlation eligibility; later policies must inspect its basis and quality.

## Source contracts and integrity

Source documents identify formats/provider versions, source references, ECS
classification, Sigma logsource, framing, assembly mode, mappings/capabilities,
required evidence fields and fixed quality policies. Mapping source paths are JSON
Pointers into parser-extracted source attributes; target paths are ECS dotted
names. These declarations are not executable parsers or transformation programs.

The examples scope Windows Security 4688 version 2, Sysmon process creation version
5, Linux audit execution records, and OpenSSH 9.x accepted/failed password messages
in RFC5424 framing. Different provider versions or authentication forms require
reviewed source-contract expansion. Host identity is required by these profiles;
profiles for future sources can make a different choice.

Profiles distinguish structural/integrity failures from absent collection capability.
Missing command-line capture is not automatically corrupted telemetry. A rule's
field reference does not automatically make that field required for every event.

Insufficient integrity requires skipped eligibility and a diagnostic; eligible
requires sufficient integrity. Known missing/conflicting assemblies cannot claim
sufficient integrity. Profile-required fields and blocking diagnostics prevent
eligible evaluation, while skipped envelopes can retain incomplete evidence.
Timeout/dataset-end closure does not prove completeness. Source-specific assembly
completion algorithms and timers remain P12.

Use stable diagnostic codes and JSON Pointer field paths only; never free-form
raw values in operational diagnostics. The four profiles' fixtures declare expected
integrity and eligibility. P11/P12 will validate these choices against real formats
and recordings before claiming source support.

## Provenance

Field names, types and categorization values follow
[ECS 9.5.0](https://github.com/elastic/ecs/tree/v9.5.0/schemas).
The applicable upstream notice is retained in `NOTICE`; Apache 2.0 terms are in
the repository LICENSE. Source-specific authoritative references are listed in
each source-contract example. No third-party event recordings are bundled.
