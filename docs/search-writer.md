# P13c derived search writer

The separate search-writer/1.0.0 mode consumes actual P13b tagged events, detections
and compact diagnostics. It does not replace the P08 metadata writer, original
Kafka evidence, or the P14 archive. [Owning decisions](p13c-design.md) freeze its
contracts, mappings, identities, limits and compatibility boundary;
[qualification](p13c-ledger.md) records actual checks and remaining gates.

## Commands and isolation

Use the pinned environment in [development](development.md). Initialize a dedicated
P13b project with `tools/integration.py`; prepare its full-profile TLS OpenSearch
before search init. Build with `uv run --locked python tools/search_writer.py build`.
Then use `uv run --locked python tools/search_writer.py --project detectbridge-p13-dev`
followed by `init`, `start`, `status`, `metrics` or `stop`. Initialization never
resubmits or stops the source Flink job. Retain its checkpoint before any intentional
stack recreation and restore through the existing P13b command.

`uv run --locked python tools/dev.py search` runs actual adapter-to-projection,
protocol, TLS, schema/artifact, mode compatibility and gate checks.
`uv run --locked python tools/search_writer.py verify` runs isolated synthetic
Kafka/Flink-to-search and writer failure/recovery qualification. Build the P13b
integration image first with `tools/integration.py build`. CI's search-verification
job runs these actual commands and fails closed on unexpected skips. It does not
have access to local original recordings or imply full P13 milestone acceptance.

Host metadata/secrets live under ignored `.cache/search-writer/<project>/`;
immutable images/JARs under `.cache/search-writer-build/`. Only dedicated
`detectbridge-p13-*` projects are accepted. The full stack uses the existing bounded
writer service/secret-volume policy, with its own mode/image/credential/configuration.
Do not initialize P08 writer state alongside it in the same project. Runtime has
512 MiB, a 256 MiB heap, 0.5 CPU, 128 PIDs, read-only root, bounded temporary storage
and rotating logs. Docker must have at least 7.5 GiB. Serialize heavy projects.
`stack.py down` retains volumes and evidence; the qualification suite removes only
its own stack/volumes and retains its ignored ledgers. No adoption/reset of another
project or old checkpoint/configuration is supported.

## Search and retrieval

Exact physical indices are `detectbridge-tagged-events-v1`,
`detectbridge-detections-v1`, `detectbridge-processing-diagnostics-v1`. The last
holds distinct compact-evaluation and reference-only writer-failure kinds. There
is no index/alias wildcard, rollover, delete policy or per-run shard creation.
Runtime's dedicated `detectbridge_search_writer_v1` role cannot access P08 or
unrelated indices, delete documents/indices, or administer security/templates.
Application create-only behavior still requires content verification; the generic
index permission is not an independent immutable-storage guarantee.

Query six outcome counts, source quality, ECS fields, run/event/processing IDs,
matched-rule links, immutable metadata versions/hashes and rule-set groups. Exact
source timestamp strings and basis/quality remain beside optional date_nanos range
fields; out-of-range/greater-than-nanosecond precision is explicit. Searchable
keywords use ignore_above=4096; longer values remain exact in `_source`, while their
semantic hash and coverage/quality remain searchable. No original inline payload,
arbitrary vendor extension, rule YAML/expression or per-nonmatch document is indexed.

Evidence entries retain original record IDs/hashes and sanitized object/range
references. Inline originals remain in the immutable P13b input topic, linked by
cluster/topic ID plus record ID/hash; audit manifests retain exact manifest ID/hash
and their immutable topic link. Search is a derived view, not evidence storage.
Retrieve originals privately, verify immutable topic identity, then record/value/
object/range hashes. Never infer original raw evidence from a search projection.

Every stored document retains the original accepted Kafka value hash/location;
semantic comparison excludes copy offsets/input hash and receipt clocks. Replays
keep event/evidence identities but have isolated processing/detection identities.
Conflicts retrieve and rehash `_source` rather than trusting its claimed checksum.
Different content is durably referenced in `detectbridge.integration.writer-failures.v1`
without overwrite. Failure-topic indexing errors block without recursion. Offsets
advance only after indexed/verified duplicates or acknowledged failure publication.
Outages retain bounded backlog; TLS, identity, mapping and credential drift stop
or block visibly. Repair original bindings before restart; changing an artifact,
index, template or producer binding is not an implicit migration procedure.
