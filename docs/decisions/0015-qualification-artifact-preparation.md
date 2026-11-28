# ADR 0015 — Qualification-only pre-window artifact preparation

Status: accepted by the owner for CI-01 implementation; qualification pending.
Owning issue/PR: [CI-01 #62](https://github.com/TravisMa07/DetectBridge/issues/62),
[PR #63](https://github.com/TravisMa07/DetectBridge/pull/63).

## Context

Same-source c42 has one native all14 pass and a dispatch failure: the open-group
harness spent at least29.615s after the actual completed-five-B proof on rollback
publication/EOE admission, excluding existing group age. The original30s worker
timeout was truthful. [Freeze4339ff4 and reviewed options](../ci-01-design.md#open-group-deadline-decision-packet)
precede implementation. The owner explicitly selected A, pre-window preparation.

## Alternatives

A moves exact signed artifact transport/readiness before the group timer, retaining
ordinary control adoption/publication after the completed proof. B would retain
publication ordering but add a new multi-topic QA helper/artifact/recovery protocol.
The owner chose A's smaller scope. Pausing, widening deadlines, callback admission
under publication locks, fake receipts and accepting timeout are excluded.

## Decision

Add only an explicit qualification scope with one opaque, instance-owned,
single-use preparation capability. Transfer existing signed artifact messages,
verify every current worker's actual COMPLETED artifact-cursor/rejection readiness
before admission, and bind context/CAS before adoption plus resulting A intent.
Normal locks, guarded admission, control signing/publication, actual five-B proof,
exact six-member A source_boundary and original30s/20s/120s checks remain.
All failures/context changes/finally invalidate reuse; no persistent journal format,
worker wire/state, default publication behavior, resource ceiling or QA JAR changes.

## Consequences

Preparation ACKs prove transport only; actual worker readiness is required and
truncation/context/rejection negatives must fail visibly. The scope releases locks
only between separate completed operations, never inside an adopted transaction.
Private evidence and a bounded value-free timing summary remain retained. This
accepts implementation scope, not CI stability, P15 acceptance, merge or release.

## Validation

Guard/failure tests, actual focused open-group qualification, exact native all14
and repeated diagnostic evidence are required. Known same-source search failure
remains a separate search-CI diagnostic concern. See [ledger](../ci-01-ledger.md).

## Revisit conditions

Revisit if artifact readiness/availability cannot be established without changing
worker semantics, if the unchanged deadline still fails, or if broader production
publication reuse/persistent preparation is proposed. Those are not authorized here.
