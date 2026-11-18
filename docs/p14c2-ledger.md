# P14c2 retention/import/final qualification ledger

Status: owning design/contracts/independent expectation freeze preparation. No
P14c2 production code or runtime qualification is claimed yet. Branch
`feat/p14c2-retention-qualification` starts at qualified P14c1 head 8e4c832 and
will target `feat/p14c1-current-replay`. The owner explicitly authorized this
stack before parent merges; merges/releases remain owner-controlled.

## Prerequisite evidence and local readiness

P14c1 run 44408227593 attempt 1 passed every applicable job/required aggregate
135184964812 on exact head `8e4c832283268897887999efe22152b2f0b41eb5`, completing
2026-11-18 22:34:01 UTC. Five explicit acquisition/recorded opt-ins were skipped.
Actual checkout was GitHub test merge `096ddc136b5769de5f8537608873647b5809df96`;
this is not actual merged-main qualification. Refreshed reviews/comments/inline
threads were empty. PR #52 is marked ready for owner review and remains unmerged.
CI repair #54 is also unmerged; its separate native pass is in the P14c1 ledger.

Native current job 135170171558 passed full synthetic source, schedule, isolation,
three fresh-JVM resumes, eleven interruption windows and integrity/storage/helper
cases on Linux AMD64. Its qualification-source aggregate matches the exact local
source set `2db4412b3b73940882252cdba342c9988b014ff009f7e095b818d7e936620f2c`.
Executor ea9d4740, reader e5eaea35 and producer 51a984de are unchanged (full hashes
in [P14c1](p14c1-ledger.md)); selected AMD64 Docker image is
`sha256:6b26436e8a89f49acaf0133e35f1e3715544e7c984d0f68cd8038137ab2e6be9`.
Metadata/current full log/threads are `.cache/p14c1-native-44408227593/`.
This supplies the owner's requested acceptance-check gate for starting P14c2;
owner semantic acceptance, merge and merged qualification remain separate.

Before designing recorded cases, the original accepted preflight functions
revalidated controlled originals, usage terms and source/capture bindings from
original-checkout paths `.cache/p11-windows-capture/attempt3/originals`,
`.cache/p12-audit-reviewed-v1` and `.cache/p12-auth-reviewed-v1`. All were available;
counts are 5 Windows/30 audit/11 auth. Private report
`.cache/p14c2-readiness/preflight.json` freezes catalog hashes and absence of Bob
among reviewed auth users. The accepted eligible audit executable is not the
synthetic whoami path; the recorded current expectation is therefore nonmatch,
not a copied synthetic match. No original payload was printed, uploaded or recaptured.
All four original public P05 payload/provenance caches and five P05 run manifests
are available in the original checkout; this presence check does not claim their
new import qualification. The importer must reverify them before use.

## Freeze preparation

[Design](p14c2-design.md), [independent cases](p14c2-expectations.md), six closed
maintenance schemas and literal byte/identity/legacy-source fixtures precede
production implementation. Initial schema-authoring script incorrectly assumed
the legacy configuration schema enumerated topic names; it actually delegates
that semantic check to Main.TOPICS. The unpublished fixture generator now takes
the nine existing names explicitly. This was an authoring/setup correction, not
a behavioral red or runtime result. The failed authoring attempt remains in session output. Direct legacy-schema
validation also rejected the draft timestamp-type spelling CREATE_TIME; use the
existing literal CreateTime. The failed validation log remains
`.cache/p14c2-freeze-validation-authoring-failure.log`. Neither authoring failure
is a required retention fault assertion.

Freeze validation, implementation red/green and actual fault/recorded results
will be recorded below with exact revisions/artifacts/platforms and unavailable
coverage. No P14 completion, owner merge or runtime pass follows from this freeze.

## Freeze validation passed

Six closed/no-reference schemas and literal identity/legacy-source pins passed
independent validation. The unchanged E5 Java reader actually verified the literal
three-segment/six-row/two-object fixture on Docker Linux ARM64, before any managed
implementation: `.cache/p14c2-freeze-validation-final.log`. Expected retirement
floor/head are 4/6 and original second-segment anchor is
`2c91f7e64a0774c6013e1103e5eb407983e5df03db7696f92072ea8c5590a7d8`.
Fixture file SHA-256 is
`45ce9bc93b5614fc301417373d8325ac978cd12f6cd6c84141d7572b59a5961d`.

Direct schema type/boundary checks passed in `.cache/p14c2-freeze-boundaries.log`,
including exact 9007199254740993/MAX_I64 cutoffs and foreign/fraction/bool/overflow
rejection. An initial generic sample generator omitted the retirement ID's sha256
prefix; that authoring failure is retained separately and is not a behavioral red.
Cross-document retirement/import semantics are still implementation work.

Locked `tools/dev.py check` passed 229 existing Python regressions, all contracts/
catalog/dependency/hygiene/secrets/workflow checks, lint/format/types in
`.cache/p14c2-freeze-final-check.log`. The first document check rejected a leading
PR number as a Markdown heading; the corrected result is separate. These checks
and the old-reader fixture run do not qualify the new managed runtime. Preserve
this design/expectation commit before writing its production code.
