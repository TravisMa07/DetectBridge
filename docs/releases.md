# Releases, compatibility, and maintenance

No version is released at bootstrap. The first qualified local-platform release
is `v0.1.0`. Development builds use commit identifiers rather than stability claims.

## Version policy

During 0.x development, patches preserve documented interfaces and persisted
formats. Breaking changes require a minor-version increase and migration notes.
Version event schemas, source contracts, execution plans, mappings and rule
bundles independently from the application version.

The compatibility surface includes API/configuration, Kafka records, execution
plans, archive manifests and database state. Each changing PR documents affected
producers/consumers, rejection behavior, and migration or coexistence needs.

## Release gate

1. Complete milestone acceptance; resolve or explicitly document limitations.
2. Qualify the exact candidate commit, including clean install, restart/recovery,
   upgrade/backup behavior, ARM64/AMD64 portability and resource/capacity evidence.
3. Produce release notes, compatibility details, license inventory/SBOM,
   checksums, and measured capacity with its limits.
4. Obtain the owner's explicit release authorization.
5. Publish an immutable tag and artifacts from that exact commit.

Published corrections use new releases, never replacement artifacts or moved
tags. Deployment examples use pinned image versions/digests. P21 defines the
release automation and artifact formats; none exists at bootstrap.

## Migrations and rollback

Use versioned database migrations. State-changing PRs include backup/recovery
procedures and tests. Reverting code does not imply reverting persisted state.
Rollback may select a compatible rule bundle, restore a compatible application,
or restore a backup. Document and verify the actual supported path.

Local persistence supports qualified restart scenarios, not survival of loss of
the laptop's only disk. Retention/deletion policies and recovery limits must be
visible before operators rely on them.

## Maintenance

Review dependency update PRs regularly; compiler/evaluator updates require
semantic regressions. Record defects with sanitized reproduction and add tests.
Track security findings and exceptions with ownership and removal conditions.
Reassess performance only when changes, failures, or uncertainty warrant it.

References: [Semantic Versioning](https://semver.org/) and
[GitHub Actions security](https://docs.github.com/en/actions/reference/security/secure-use).
