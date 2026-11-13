# Third-party code, rules, and datasets

Apache 2.0 applies to DetectBridge's original work, not automatically to imported
dependencies or content. This seed bundles no third-party application code,
detection rules, or datasets. LICENSE contains the official Apache 2.0 terms.

Before importing or redistributing material, record its upstream URL, exact
version/commit, artifact path, checksum where relevant, license, attribution,
modifications, and required notices. Preserve upstream notices and review nested
or artifact-specific terms. Missing or conflicting terms require resolution
before redistribution. A link alone does not establish permission.

## Planned dependencies and reference material

- pySigma: parsing/validation dependency; its LGPL terms and distribution
  obligations are reviewed against the pinned version in its owning PR.
- SigmaHQ rules: detection content is licensed separately from tooling. Preserve
  rule authorship, source, modifications, and applicable content terms.
- Public datasets: prefer selective acquisition into an ignored local cache.
  Keep acquisition manifests and provenance in Git. Downloading separately does
  not waive license obligations for use or redistribution.

## Candidate replay sources, not bundled content

| Source | Intended role | Review requirement |
| --- | --- | --- |
| [Splunk Attack Data](https://github.com/splunk/attack_data) | Windows/Linux recorded scenarios | Verify artifact terms, upstream revision, LFS object/checksum |
| [OTRF Security Datasets](https://github.com/OTRF/Security-Datasets) | Additional malicious/benign scenarios | Resolve README/license discrepancies for selected artifacts |
| [EVTX Attack Samples](https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES) | Windows parsing/regression cases | Review GPL terms before copying or redistributing |

Each dataset manifest must include provenance, capture context, timestamp
handling, transformations, labels, and checksums. Distinguish malicious,
documented benign, and unknown evidence. Controlled attack recordings are not
proof of real-world false-positive rates.

Small redistributable fixtures need an accompanying provenance record. Generated
edge cases must be labeled synthetic. Do not add an upstream NOTICE file unless
it actually applies; add applicable notices when introducing the material.

Release qualification produces a license inventory and SBOM for the exact
artifacts being released.

## Repository hygiene dependencies

P01 installs development-only tooling rather than bundling third-party application
code: markdownlint-cli2 0.24.1 (npm lockfile), PyYAML 6.0.3 (root uv.lock),
actionlint 1.7.12 and Gitleaks 8.30.1 (checksum-verified release executables).
Dependency package metadata and upstream license files remain authoritative;
GitHub Actions are pinned by full commit revision in the workflow.

The npm manifest overrides KaTeX to 0.18.2 to address
[GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7),
a transitive markdownlint dependency. Verification includes markdownlint and
`npm audit`; no vulnerability suppression was added.
Keep this override until upstream dependency constraints permit the patched
version without it, then remove it in a reviewed dependency update.

## Development toolchains

The Gradle Wrapper and scripts originate from Gradle 9.9.1 (Apache 2.0).
The Wrapper JAR and distribution SHA-256 are verified against Gradle's published
checksums. Temurin 17.0.21+9 comes from Eclipse Adoptium official releases under
GPLv2 with the Classpath Exception; downloaded archives retain their license and
notice files locally. Node 24.22.3 official archives retain their MIT and bundled
third-party notices. Only the Wrapper is committed; JDK/Node archives are local.

Origins and checksums are recorded in `tools/toolchains.json`. Development-only
Python/npm packages retain their package licenses and locked provenance. No
application framework or detection content is added in P02.

## Event-contract definitions

P03 follows selected field names/types and categorization values from ECS 9.5.0
(Apache 2.0). Its applicable upstream notice is retained at `contracts/v1/NOTICE`;
the schemas are a DetectBridge-specific subset, not a complete ECS redistribution.
Validation uses jsonschema 4.26.0 and its format dependencies, pinned in uv.lock;
package metadata retains dependency licenses. Examples are original synthetic
fixtures, not third-party recordings. Authoritative source references live in the
source-contract documents. P04 owns recorded dataset acquisition and licensing.

## Recorded corpus catalog

P04 pins four Splunk Attack Data artifacts at
`4b19e4b6824a8ba91b0f5345a3a8de488619e823`. Manifests in `catalog/datasets/` record
payload/LFS hashes, author metadata, root Apache 2.0 terms and applicable ancestor
review. Verified license and metadata objects are retained with downloaded local
evidence. No third-party log bytes are redistributed in Git. Scenario labels are
not per-record verdicts; record labels remain unknown. See the
[acquisition guide](docs/datasets.md) for limitations and integrity policy.

## Local infrastructure images

P06 uses Apache Kafka 4.2.1, Apache Flink 2.2.1 (Java 17), and OpenSearch 3.9.0,
each Apache-2.0 for its primary project. The [image lock](deploy/local/images.lock.json)
records upstream sources, multiarchitecture digests and compatibility references.
Image contents also include their upstream base OS/JVM and transitive license
notices; retain those distributions and their license material. The images are
consumed from upstream without committing their binaries or copied configuration
to this repository. Runtime-generated security configuration preserves upstream
files locally; original wrapper scripts in this repository use the project license.
