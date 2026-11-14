# Transport dependency review

Reviewed on 2026-11-13. The [machine-readable inventory](transport-dependencies.json)
records 67 unique resolved Maven coordinates across production, tests and build
plugins, their locked configurations, patch selections and remaining dispositions.
This is a scoped dependency review, not a complete container SBOM or certification.

## Reproduction and integrity

```sh
uv run --locked python tools/dependency_inventory.py
uv run --locked python tools/dev.py java
```

Gradle dependency locking and strict SHA-256 verification apply to the committed
artifact graph. Updating dependencies requires explicit lock/checksum review and
`tools/dependency_inventory.py --write` after reviewing the resulting graph.
Normal builds never regenerate locks. The publisher/job bundles retain dependency
licenses and notices; provided Flink runtime classes are excluded. Test fixtures
and examples are excluded from production resources.

The OSV Maven query API returned no advisory matches for the final 67 locked
coordinates on the review date. This result is time-specific and does not cover
shaded dependencies already embedded in the upstream image. The API request used
public artifact coordinates only. Release qualification must repeat this review
and produce the release-wide inventory/SBOM.

## Reviewed transitive patches

The requested primary component versions remain pinned. Explicit root resolution
constraints upgrade vulnerable transitive components in project and buildscript
configurations:

| Component | Selected version | Review reference |
| --- | --- | --- |
| LZ4 Java | 1.11.4 | [Upstream advisory](https://github.com/advisories/GHSA-343h-94h5-c4wr) |
| Snappy Java | 1.1.10.9 | [Upstream advisory](https://github.com/advisories/GHSA-q233-g92q-qxp6) |
| Legacy Jackson core/databind | 2.18.11 | [Core advisory](https://github.com/advisories/GHSA-7hhh-6rmp-j9qf), [databind advisory](https://github.com/advisories/GHSA-cxp5-3px4-pw24) |

Java tests exercise patched LZ4/Snappy native roundtrips on both supported
architectures. Transport JSON parsing uses Jackson 3.1.8, not legacy Jackson.
Compatibility still requires the full transport recovery qualification after any
patch change; a successful download/checksum alone does not establish semantics.

## Remaining upstream image finding

The approved Flink 2.2.1 image embeds shaded Jackson core/databind **2.18.2** in
`flink-dist-2.2.1.jar`. Its `PackageVersion` bytecode independently confirms the
version. The machine-readable inventory lists advisory identifiers returned for
those versions. Gradle resolution cannot replace this shaded engine dependency.
No unreviewed Flink/image substitution is made in P07.

Disposition: retain the explicitly approved image for this trusted local Docker
boundary, document the finding, and track remediation under
[P21 release qualification](https://github.com/TravisMa07/DetectBridge/issues/21).
The owner is responsible for approving a compatible patched distribution and
repeating checkpoint/restore qualification before v0.1.0 or wider exposure.
Kafka values remain bytes until application Jackson validates them; Flink REST
and metrics remain internal and Docker access is administrative. These boundaries
reduce exposure but do not establish that the embedded component is unaffected
or remediated. No required correctness check is waived by this disposition.
