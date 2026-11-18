# P14c1 current-policy replay ledger

Owning [design and independent expectations](p14c1-design.md) precede code.
Base: owner merge P14b #51 as `943d143eb4e5dc6d07871513f993efbddf1ab230`.
Actual merged-main run 44326278636 is pending. No P14c1 production code has begun.
The next PR implements current-policy replay only; retention/deletion, recorded
qualification, P05 archive import and complete milestone acceptance remain open.

The base run's OpenSearch writer job 134878372291 failed during `gradlew help`
bootstrap: Gradle could not find ten plugin classpath artifacts via the Gradle
Plugin Portal. Original full log is retained at
`.cache/p14b-merge-ci-44326278636/opensearch-writer-verification.log`.
This log does not report HTTP 429, so it is not labeled a verified 429 failure.
No runtime qualification started in that job. Preserve the failed attempt and
qualify an unchanged retry independently before dependent implementation.

The first local freeze check stopped on a Gitleaks false positive: a synthetic
fixture path containing `auth` was used as a JSON key for a source-file SHA-256.
The redacted report `.cache/p14c1-gitleaks-redacted.json` identifies only that
public rule-file hash; no credential was present. Store source pins as explicit
`path` / `sha256` entries instead. The unpublished freeze is organized before its
first push; independent source bytes and expectations are unchanged.
