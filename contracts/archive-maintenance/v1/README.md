# Managed archive contracts 1.0.0

Original DetectBridge definitions and synthetic inputs, Apache-2.0. These closed
contracts freeze P14c2's opt-in maintenance extension, not an implemented service.
[Owning design](../../../docs/p14c2-design.md) and
[independent cases](../../../docs/p14c2-expectations.md) define cross-document
checks, lock/lease ordering, source compatibility and publication boundaries.
Legacy archive v1 and historical/current contracts remain unchanged.

Registration binds the managed instance, creator archive, explicit catalog,
artifact, physical destination and finite limits. Holds/head records are chained
and checked; a missing head is not empty state. A plan freezes complete original
segments or a whole P05 import, current heads/holds/catalog and a caller-supplied
cutoff/reason. Retirement records make only that plan durable before deletion.
P05 import descriptors distinguish exact original files from derived framing and
capture projections. Input/segment/capture/provenance identities are retained;
no Kafka occurrence or host context is invented for P05.

Hashes use sorted compact UTF-8 JSON without a final LF unless explicitly named
as file hashes. Metadata files add one LF and carry an exact file-byte checksum.
Head checksum excludes its own checksum field. Original P05 semantic manifest
hashes include its serialized LF, unlike new metadata identities; preserve both
that digest and original file-byte hashes. All integer metadata is lossless signed
64-bit, excluding fractions and bools. Schemas have no external references.

The fixture JSON contains literal legacy configuration, original object and wire
bytes, compressed frames and segment metadata constructed before the managed
implementation. Original notice/eight-byte evidence are authored synthetic data;
no downloaded or private payload is included. Independent SHA-256/RFC1952 framing
uses the already accepted archive v1 contract. It pins the original legacy source
and source/semantic expectation files. Private catalog hashes/counts are metadata
only; the original recordings remain local under their existing terms.
