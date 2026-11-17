# Integrated output profile 1.1.0

Original DetectBridge schemas, Apache-2.0. These actual runtime outputs retain
P13a's shape and semantics while explicitly identifying pipeline p13-runtime/1.0.0.
The existing offline 1.0.0 schemas and pipeline remain unchanged. The default
IntegrationOutputs constructor still emits offline 1.0.0; the explicit known
runtime constructor emits these 1.1.0 contracts. Compact evaluation remains 1.0.0.

[Decisions](../../../docs/p13b-design.md) and [qualification](../../../docs/p13b-ledger.md)
record compatibility and acceptance. No P13c search or complete P13 milestone
acceptance is implied by contract/component checks.
