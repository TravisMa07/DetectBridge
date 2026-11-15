# P11 subsystem ledger

- Base: df3144822ddd5694b9244ae29eb4a3c9e2815376, verified clean before edits.
- Branch: t3/windows-adapter-qualification.
- Worktree: /Users/travisma/.t3/worktrees/DetectBridge/t3-689cf405-5fa25cc439f21f05.
- Owner: Windows implementation child; no delegated children.
- Owns: packages/windows-adapters, p11 design, ledger and Windows guide.
- Interface: exact context JSON boundary; local resolver; P03 normalized event or
  preservation diagnostic; offline output retains context and optional P10 result.
- Shared integration: minimal Gradle registration and lock resolution in separate
  commit; CI/dev-command/inventory/status integration remains orchestrator-owned.
- Acceptance blockers: recorded trusted host binding provenance, AMD64 subsystem
  execution, orchestrator integration/review. No Docker runs authorized here.
- Tests/evidence: pending implementation; no runtime or capacity claim.
