# P14c2 independent expectations

Status: before production implementation. Origins: A02–A07, P14 T01–T03/Q01–Q03,
existing P03/P05/P12/P13 contracts, original archive v1 vectors, P14b/c1 freezes
and accepted controlled-recording catalogs. No expected output comes from the new
managed archive or retention implementation. Literal identity/byte/source pins
are in `contracts/archive-maintenance/v1/fixtures/expectations.json`.

## Retention and recovery

| Case | Given / intervention | Required observation and rationale |
| --- | --- | --- |
| M01 | Legacy v1 archive, old E5/32/E9 executors and an existing replay prefix | Old commands and completed/interrupted replay retain exact bytes and artifact identities. Managed work cannot silently replace the old profile. |
| M02 | Fresh managed instance or verified v1 clone | New managed UUID/group and explicit fresh catalog; creator metadata/wire/object bytes unchanged. Clone source snapshot unchanged. No shared consumer-group adoption. |
| M03 | Equal/nested/symlink roots, unknown file, missing registered catalog or changed destination | Reject before source/pin/result mutation; absent catalog is never no holds. |
| M04 | Topic segments [0,2), [2,4), [4,6); retire first two, keep third | Floor becomes 4, previous anchor is exact original second-segment metadata hash; head stays 6. Retained third segment and object bytes stay unchanged. |
| M05 | Request target 3, wrong original segment/payload hash, stale head/holds/catalog or compensated plan corruption | Reject without record publication/deletion. Only exact complete observed prefixes are eligible. |
| M06 | Inclusive cutoff 100; selected timestamp 100 versus 101, unknown -1, empty committed interval | 100 eligible, 101 and unknown denied; empty interval retains exact metadata without inventing a record. |
| M07 | Retire a complete prefix, append next [6,8), reread and reconcile Kafka | New segment chains to original preceding hash; durable-next advances to 8, retired floor stays 4, Kafka commit follows durable publication. |
| M08 | Retrieval/retry below floor or at retained boundary | Below floor is explicit retired; boundary 4 returns exact original bytes. Never count absent retired bytes as an identical retry. |
| M09 | Any selection input/output/anchor/control intersects candidate prefix | Deny and expose pin blocker. Corrupt or missing pin metadata fails closed rather than removing protection. |
| M10 | Retained manifest/late link or processing/detection refers to selected evidence identity | Deny. Shared plan/host/rule IDs alone do not create evidence links. A retained same run/source/event identity conservatively blocks. |
| M11 | Retained quarantine/writer failure or an unrecognized reference graph | Partial retirement denied; complete wire population may retire only with all holds/pins clear. Nothing is relabeled as safe source data. |
| M12 | Global registered object shared by any segment or immutable registration | Object remains protected; no speculative orphan deletion. Import-private objects can disappear only with their complete import closure. |
| M13 | Hold all/range/run/import/object; changed release revision or deleted hold/head file | Matching scope denies deletion; only compared-revision release removes a hold. Missing/corrupt history is failure, never an empty registry. |
| M14 | Shared managed reader, catalog mutator or writer overlaps apply | Actual locks deny the conflicting operation; no deletion starts while the lease is live. Test Java shared/exclusive locking, not interchangeable flock assumptions. |
| M15 | Crash during plan/record writes, before publication/sync, after durable record, around individual unlink and completion | Before durable intent no deletion; afterward resume exact committed plan, sync its authority before cleanup, finish only named owned files. No rebuilt wider plan. |
| M16 | Corrupt/truncated retirement record, last record missing with head ahead, missing head, altered anchor or chain gap | Reject before append/deletion. Stale surviving head after interrupted publication can advance only through verified contiguous records. |
| M17 | Source occurrence retired, later same identity/raw/context at a new offset; then conflicting content | Identical content remains a distinct wire occurrence; conflict remains visible from retained fingerprint summaries and never overwrites history. |
| M18 | Ordinary admission reaches withheld maintenance headroom; row/token/fingerprint/plan/segment count bounds exceeded | Visible bounded refusal/backlog. Retirement still has reserved metadata space; no dropped index, automatic eviction or increased resources. |
| M19 | Actual full tmpfs write and injected sync EIO / process kill | Retain original diagnostics, identify the actual failed operation, and verify publication/deletion boundary. Injection is not physical disk/power-loss qualification. |
| M20 | Offset/cutoff 9007199254740993 and signed-64 extrema; fractional/bool counters | Exact integral roundtrip where valid; reject overflow, negative offsets, fractions and bools. Never pass through floating point. |
| M21 | Original bytes 41 0d 0a 0a c3 a9 0a 5a; timestamp strings with 0/6/9/12 digits | Preserve all eight bytes, ranges (0,3),(3,1),(4,3),(7,1), and original strings exactly. Managed storage does not reinterpret timestamps. |
| M22 | P16 progress read / archive lag after retirement or full disk | Expose vector floors/head/committed/earliest/end, reserve/lag/blockers; issue no Kafka deletion or activation command. |

## P05 import and controlled originals

| Case | Given / intervention | Required observation and rationale |
| --- | --- | --- |
| I01 | Verified completed P05 run with missing/behind valid advisory checkpoint | Authoritative committed run_end controls completeness. Import exact manifest/segments/timing/capture/provenance/object bytes; checkpoint stays an advisory original. |
| I02 | Incomplete/gapped/corrupt P05 prefix, absent original, changed catalog/terms/resource, 12-digit P05 timing index | Fail before import publication using original P05 rules; P05 timing still supports at most nine digits. Never repair the source or infer host identity. |
| I03 | Identical import retry versus same bytes in another original run | Same closure verifies idempotently; different run remains a distinct import. Conflicting content never overwrites. |
| I04 | Crash in import payload/metadata/publication; restore to occupied/overlapping root | Resume or clean only owned unpublished work. Committed import verifies fully. Restore rejects unsafe destination before overwrite. |
| I05 | Fresh restore then original P05 inspection/complete resume | All source/run file hashes and framing ranges agree; original UUID/observations/time precision retained. A derived framing index is marked derived, not substituted for original evidence. |
| I06 | Import used as P13 source without trusted processing context | Explicit unsupported operation. No synthetic Kafka location, host binding or historical parser is invented. |
| Q01 | Accepted catalog hash/terms/original/capture binding differs or path missing | Fail before Docker/admission/archive mutation. Do not recapture or manufacture replacements; report unavailable coverage separately. |
| Q02 | 46 original occurrences + one exact redelivery + one controlled late cursor + run_end | Archive all 49 physical admissions with exact hashes. Account original46, control1, exact retry1, controlled cursor1 separately. |
| Q03 | Original recorded P13 processing under accepted twelve-rule plan | Independently expected 16 events, 10 manifests, 13 preservations, 3 detections; source fields/contexts/quality/membership/late links/version attribution match accepted oracles. |
| Q04 | Historical managed selection and two replay runs, interrupted resume | Original grouping and counts/matches/nonmatches reproduced through exact original producer; runs isolated and originals unchanged. Exact redelivery is not another logical source unit. |
| Q05 | Recorded current Image/Bob plan, explicit timeout tick before controlled late cursor | Eligible Linux: unmatched1/inapplicable1; skipped audit: quality_skipped1/inapplicable1; Windows: inapplicable2, other counts0. Total16 tagged,10 manifests,13 preservations,9 diagnostics,0 detections. Source-field and original-link checks still apply. |
| Q06 | Same-count mutations of field, context/host, membership, counts, match, attribution or original range | Independent checker rejects each mutation. Retrieval checks original bytes/ranges, not only emitted counts. |
| Q07 | Routine failure logs and native artifacts | Fixed categories/IDs/counts/hashes only. Private source packets, exceptions, credentials and raw evidence stay uncommitted and off public native CI. |
| Q08 | Final acceptance map | Account every P14 row by exact revision/artifact/platform and unavailable limits. Owner semantics/merge/release and actual merged qualification remain explicit; one slice cannot close P14 automatically. |

Before implementation freeze, validate closed schemas and literal vectors directly.
After implementation, retain meaningful old-behavior red, focused green and actual
fault reports. Public synthetic cases and local accepted originals are separately
attributed. Keep every failed attempt and do not claim a required fault from an
unrelated failure.
