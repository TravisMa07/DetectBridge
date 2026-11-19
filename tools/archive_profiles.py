"""Immutable processing pins and closed graph resources for managed archive v1."""

PINS = dict(
    reader="e5eaea3560d150e176cb0f68e941ca22efb25fb6f16b2a1d1d76465a94ef02d0",
    historical="32bad6f526e3208bf4b2684979a4d600c82b35070e39cbeb3a5fce6d5fccfcc4",
    current="ea9d47406651a686546a2514f83fe59689fa38902e76b0c2c6aa129c37a511e2",
    producer="51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d",
    image="flink:2.2.1-scala_2.12-java17@sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe",
)

GRAPH_RESOURCES = (
    "contracts/v1/common.schema.json",
    "contracts/v1/raw-record.schema.json",
    "contracts/v1/normalized-event.schema.json",
    "contracts/detection/v2/candidate-provenance.schema.json",
    "contracts/integration/v1.1/common.schema.json",
    "contracts/integration/v1.1/tagged-event.schema.json",
    "contracts/integration/v1.1/detection.schema.json",
    "contracts/integration/v1.1/diagnostic.schema.json",
    "contracts/integration-runtime/v1/integration-input.schema.json",
    "contracts/integration-runtime/v1/integration-receipt.schema.json",
    "contracts/integration-runtime/v1/integration-preservation.schema.json",
    "packages/linux-adapters/contracts/context.schema.json",
    "packages/linux-adapters/contracts/context-extension.schema.json",
    "packages/linux-adapters/contracts/manifest.schema.json",
    "packages/linux-adapters/contracts/preservation.schema.json",
)
