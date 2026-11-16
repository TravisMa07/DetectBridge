# P12c owner review packet

Review is pending. Passing checks or merging another PR does not fill these items.
Implementation/local evidence is recorded separately in the [ledger](p12c-ledger.md).

- [ ] Review [independent action expectations](../packages/linux-adapters/audit-recording/expectations.json)
  (frozen before capture) and the [reviewed original catalog](../catalog/recordings/linux-audit-execve-lab-v1.json)
  (membership/findings frozen before replay). The selected audit claim is one
  successful native AArch64 execve of the original probe, not general source coverage.
- [ ] Review trusted identity: sole inspected guest invocation plus original boot
  ID, immutable image/kernel/initramfs and raw serial; no display-hostname or serial
  identity inference. Capture is local-use only; binary and payload publication
  is excluded by the recorded terms review.
- [ ] Review observation metadata: original capture start was mislabelled as
  first_observed. Versioned context/1.1.0 uses the retained capture-completion
  timestamp and an isolated new run; source/manifest bytes and source times stay
  unchanged. Exact per-row observation is unavailable.
- [ ] Review completeness: one SYSCALL with two PATHs, five positional arguments
  including empty/repeated/space-bearing values, CWD and PROCTITLE, enabled daemon
  with lost=0/backlog=0, exact watch and successful original action. Native EOE is
  absent; dataset_end closure alone is not the evidence of completeness. This
  bounded capture does not establish an unbounded lossless telemetry service.
- [ ] Review all 30 original dispositions: one eligible and nine skipped groups,
  plus three extraction-failed preservation documents. Non-execution and early
  boot evidence is retained. No skipped source event is presented as a nonmatch.
- [ ] Review existing P10 ordering: unsupported CommandLine is
  configuration_blocked even when the source event is quality-skipped; Image
  predicates are quality_skipped for those same source events. The eligible
  event's independently expected match/nonmatch/block remain distinct.
- [ ] Review atomic offline replay/publication boundaries and the recorded auth
  checkpoint fault/recovery evidence. The local replay file is non-resumable;
  completed Flink checkpoints remain the runtime recovery authority. Strict
  binding rejection and all required sink/broker checks remain intact.

[Existing P12a semantic cases](../packages/linux-adapters/fixtures/expectations.md)
and [P12b independent vectors](../contracts/linux-assembly/v1/fixtures/expectations.md)
remain part of the owner completeness/semantic review. Broader P11/P12 acceptance
still needs trusted Windows recording bindings and the outstanding owner reviews.
P13 production wiring stays blocked. Any PR merge or release needs separate
explicit owner authorization.
