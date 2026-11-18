# Historical replay contracts 1.0.0

Original DetectBridge definitions and synthetic identity vector, Apache-2.0.
[Owning freeze](../../../docs/p14b-design.md) specifies cross-document checks,
supported executable pins, exact membership, finite bounds, publication and
compatibility. These are separate wrappers around unchanged original P03/P12/P13
contracts, not current-policy execution or production activation.

[Independent fixture packet](fixtures/expectations.json) retains original synthetic
input bytes and existing P11/P12/P13 expected counts, fields and memberships.
Its source hashes bind that prior expectation lineage; it contains no output from
the proposed historical executor. [Identity vector](fixtures/identity.json) freezes
the separate historical unit namespace.
