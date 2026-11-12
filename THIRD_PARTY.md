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
code: markdownlint-cli2 0.24.1 (npm lockfile), PyYAML 6.0.3 (requirements),
actionlint 1.7.12 and Gitleaks 8.30.1 (checksum-verified release executables).
Dependency package metadata and upstream license files remain authoritative;
GitHub Actions are pinned by full commit revision in the workflow.

The npm manifest overrides KaTeX to 0.18.2 to address
[GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7),
a transitive markdownlint dependency. Verification includes markdownlint and
`npm audit --prefix tools/hygiene`; no vulnerability suppression was added.
Keep this override until upstream dependency constraints permit the patched
version without it, then remove it in a reviewed dependency update.
