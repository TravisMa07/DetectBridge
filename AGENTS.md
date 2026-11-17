# Working on DetectBridge

Read README.md, docs/architecture.md, docs/sdlc.md, and the relevant entry in
docs/roadmap.md before implementation.

- Preserve accepted architecture. Discuss consequential changes with the owner;
  resolve routine implementation details in the owning PR's design notes.
- Work on a short-lived branch. Do not merge PRs or publish releases without the
  owner's explicit authorization. The initial seed commit is the only bootstrap
  exception to the PR-only workflow; publication still requires owner review.
- Apply conservative commit discipline to all future DetectBridge development,
  across every milestone, branch and PR: normally 1–3 cohesive commits per bounded
  PR, each with a clear purpose. Batch related fixes and documentation before committing;
  preserve any required pre-implementation design/expectation freeze. See
  docs/sdlc.md for exceptions and published-history rules.
- Do not turn roadmap entries into implemented-capability claims. No services
  exist at bootstrap. Do not create passing placeholder tests or CI jobs.
- Keep original evidence, license provenance, and versioned processing metadata.
  Never substitute evaluator output for independent test expectations.
- Never commit credentials, large downloaded datasets, local evidence, or build
  artifacts. Public fixtures require provenance and usage-term review.
- Add meaningful tests for behavior changes, particularly detection semantics,
  state/recovery, contract compatibility, and replay isolation.
- Run applicable checks; report what passed, failed, or could not be run. Do not
  claim runtime or performance validation from documentation checks.
- Keep implementation, documentation, and the decision register consistent.
