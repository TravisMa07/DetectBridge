# Integrated runtime contracts 1.0.0

Original DetectBridge schemas and synthetic expectations, Apache-2.0. The actual
P13b Kafka/Flink consumer uses these input, wire, receipt, quarantine, preservation,
state, evidence registration and deployment contracts. P03 and native P12
manifests remain unchanged. Native diagnostics are retained within preservation
wrappers; malformed sources do not become events or nonmatches.

[Owning decisions](../../../docs/p13b-design.md) define versions, bounds, identity,
backlog, checkpoint release and compatibility. [Qualification](../../../docs/p13b-ledger.md)
separates component tests from actual runtime/recovery evidence. No old checkpoint
or deployment is adopted. Original synthetic fixture expectations are independent
of evaluator output; original recorded payloads remain local and are not fixtures.
