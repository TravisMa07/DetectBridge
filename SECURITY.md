# Security policy

## Supported status

No executable release exists. DetectBridge has not been qualified for production
use. Release-specific support and security-update commitments will be documented
before `v0.1.0`.

## Reporting a suspected vulnerability

Do not post credentials, private telemetry, or sensitive vulnerability details in
public issues or PRs. GitHub private vulnerability reporting is enabled. Use the repository's Security
tab to report privately; remote enablement was verified during P01 setup.

If that option is unavailable, open a public issue containing only a request for
a private reporting channel, without vulnerability details or sensitive data.
No response-time SLA is established yet. Private reporting is part of P01's verified repository setup.

Provide privately: affected revision, impact, minimal reproduction, relevant
configuration, and sanitized evidence. Do not upload third-party private data.

## Development boundaries

- Imported events, rules, and datasets are untrusted inputs.
- Do not commit secrets or put raw telemetry in routine operational logs.
- Mutating management operations require authentication before exposure.
- CI for untrusted contributions receives no deployment credentials.
- Record security findings and their dispositions; never conceal unresolved risk
  behind a successful check.

Implementation controls and release qualification are tracked in the roadmap.
