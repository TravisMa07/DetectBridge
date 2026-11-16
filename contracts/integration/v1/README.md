# P13a integration contracts 1.0.0

Original DetectBridge schemas and synthetic identity/count fixtures, Apache-2.0.
P03 normalized events and rule provenance retain their existing notices/terms.
No captured payloads are distributed here.

These schemas are loaded and checked by the real Java evaluator/offline consumers.
All four document kinds support exactly 1.0.0: compact-evaluation, tagged-event,
detection and diagnostic. Common definitions are local-only resources. They do
not extend P03 or replace legacy detection result 1.0.0/2.0.0. Required bounds,
identity preimages, bit ordering and overflow policy are in
[owning notes](../../../docs/p13a-design.md). Schema checks alone do not verify
identity, attribution or membership; IntegrationOutputs.verify rederives complete
content using the pinned bundle and the original audit manifest. Retain those
artifacts and original raw/context rows.

The literal fixtures were specified before implementation: generic domain-separated
SHA-256 vectors calculated independently with Python hashlib and a selection case
with independently reasoned shared-budget outcomes. Existing P10 semantic fixtures
supply absent/type/negation expectations; P11/P12 source fixtures are independently
specified adapter evidence. No evaluator output is an expected-results oracle.
