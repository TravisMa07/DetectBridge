# CI-02 evidence ledger

## Pre-implementation checkpoint

Managed isolated branch `t3/ci02-failure-diagnostics` fast-forwarded from clean
6e1ed1c to approved integration e2bec696d998dd152d609f8727ed366fdf9b27c6
before source edits. Original root and old worktrees/stashes were not edited.
Both preservation manifests were verified read-only: all twelve entries match.
Independent expectations were prepared before this session and reviewed read-only
by a native agent; primary/close exception preservation and strict legacy error
allowlists were incorporated before freeze.

CI-01 #63 owner-authorized merge e2 passed direct native44667068167: all14,
103 admissions,232 logical/233 physical, owned stopped. PR61 testmerge44667000920
is separate evidence on cbe6ce1960afd472263d9665975f097899d19f39.
Issue62 is closed/Done in feature integration scope; no main/P15 merge follows.

Original failure report SHA256 87db825f50426d6f626bec686d21b51f75e09e9478334023ff40556e6d19a3ef;
ZIP3205474aec799d3c8f644a8ef7afe112033dff4035b56484fa800e2f0ce7d4a6;
joblog60809ce3483106a4dcb7bc2b9f49a9b2f8d5e0fbe61085a497dd0a8da46bdc43.
The old raw cause remains unknown; no successful later run proves it.

Implementation, component/runtime/native checks, review, owner acceptance and
merge remain open. No behavioral stabilization or completed CI-02 claim.

## Diagnostic implementation and review

Freeze8551088 precedes implementation777e039. Final source implements closed
policy context, exact envelope validation and per-error revalidation into the
existing sanitized failure report. No Kafka operation/order/get timeout, retry,
resource limit, source admission/commit/accounting or CI classification changed.
The independent review's envelope/category findings were corrected. Final review
found a preexisting null-message allowlist crash; its actual focused regression
failed with NPE before the null guard and passed afterward. Unknown class/message
text remains suppressed; safe legacy error strings are preserved.

Original e2 summary was read directly and SHA256 matched
`d8f579a918ae165104173b37040590e4176ee0d20f3d0da7d61f9657079712a7`;
ZIP matched `10af8102f4ba6f425e99ef26e11379e10011429b80544ad7ec7217833615da80`.
Its metadata snapshot said in_progress historically; a read-only GitHub check now
confirms native44667068167 completed success on exacte2. #61 remains Draft/open,
unmerged. Original c42 report/ZIP/joblog hashes were independently verified.

## Actual checks and artifacts (macOS ARM64 / Docker Linux ARM64)

- Meaningful red: original helper lost valid trace and exposed regex-safe sentinel
  category text; both assertions failed, then passed with the closed parser.
  System Python3.9 first failed import; that setup failure is not behavioral red.
- Java: committed Wrapper, pinned JDK17, strict verified/offline dependencies;
  13 existing search tests plus9 diagnostic tests passed, including one actual
  unchanged15-second timeout. Final helper shadow JAR built and artifact-boundary
  check passed. Two initial test harness compilation failures (result constructor,
  then mistaken Broker import) were fixed without production call changes;
  original Gradle daemon logs retain those failures in ignored cache.
- Python: all20 search tests passed, including actual qualification report save/
  rethrow, invalid/tampered context, duplicate/malformed/oversized/secret inputs,
  legacy errors, timeout cleanup and stdout/close-failure separation.
- Actual final packaged JAR: five malformed/missing/nonstring/null/unknown intent
  invocations exited1, produced validated parse-intent traces with no Admin progress
  or sentinel leak. These are helper rejection tests, not broker qualification.
- Repository hygiene/content/Markdown/workflows/secret scanning and full450 Python
  tests passed at the earlier diagnostic checkpoint (one explicit unrelated
  retained-lifecycle skip). Full Ruff lint/format and mypy passed after final code.
  Final repository recheck is recorded below.
- Dependency reuse:6666 cache files copied into this isolated ignored cache with
  per-file source/destination SHA256 equality; manifest SHA256
  `818b198507a75c588dca2e92dfb7925c8428dec909e32451e46148ff34775900`.
  Original JDK/hygiene binaries were executed read-only; original configs were not
  mutated. Both protection manifests still matched all12 entries after checks.

Final helper JAR SHA256
`24adfda2dd82639222e2a77005611371d862b165904b130c13bb5497b89ef1b3`;
bundle `0b07a4d21fe4865cd98e5f56d97d126d285ee72084d45797750628f328cf1789`;
image `sha256:89577df11fd25fc4fb4865c75c9ccb825ead530ecd20ca7e3e5776679fa4c7cb`.
Final build log SHA256
`807a6d94eb4de56b5a6fa25f0739b61edabdf02979e6bd6a3b4987fb15db7956`;
packaged-helper rejection evidence SHA256
`4152e275eaf629b5a04f1f34e371be21eb35fb2a7fd05072cf4d510bdd191695`.
Private originals remain under isolated `.cache/ci02`; no artifacts are committed.
Older artifacts retain their identities and no old qualification is transferred.

## Single stopped local runtime attempt

Preparatory integration build first failed a Linux test due to missing
`.cache/detection/mapped-plan.json`. The first preparation command prepared the
legacy plan and did not resolve it; both failed attempts remain retained. After
explicit mapped preparation, integration build/tests/image creation passed.
No check or fixture expectation was weakened.

One predeclared full search qualification then ran in fresh project
`detectbridge-p13-search-7efd94504c`. It failed `initialize` / `command_failed`
at initial core compose-up, before either policy helper call. Qualifier teardown
removed owned resources; unrelated existing containers were untouched. No runtime
retry, toggle reproduction, policy diagnostic, BACKPRESSURED/source commit proof
or data-plane success was obtained. Raw compose stderr was not retained by the
existing stack wrapper; the setup cause is unknown. This is a retained failure,
not an accepted or fixed flake. D12 remains unqualified here.

That attempt used intermediate helper JAR
`25cd438bca77e5fdb930930d131c9b30942f6c930f8fae66d1dce25fe4dfcda1`,
before the reviewed null-message diagnostic guard; it is not final-artifact
qualification. Integration JAR was
`51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d`;
plan SHA256 `39d009b9163eb97a28ca120e30c91651a2a22f59f26695067e54fbf14cfff9d0`.
Failed report SHA256 `e9c6c7096b7cbbd13bfed2fa36e3c52b638974c8d4460d9dfc511c8107dcadad`;
input/artifact manifest SHA256
`653e6b538374de5601935ecee493f63b9ac6113f001c08bd8ab2eb40338b099e`;
empty policy-trace list SHA256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
No rerun of the failed runtime was performed after review corrections.

## Parent native collection and remaining gates

Separate diagnostic-only Draft PR targets `feat/p15b-worker-activation`; refs#64,
project4. Parent owns pending checks/monitoring; this implementation child never
watches. Collect the first native PR search job's exact checkout/source SHA
(distinguish PR testmerge from head), run/attempt/job IDs, build output's new
helper JAR/bundle/image hashes, complete job log and sanitized search failure
artifact/report with its SHA256. If a helper fails, retain validated `failure_policy`
context alongside unchanged phase/category and all job/required-check results.
Stop and preserve the first failure; no rerun-to-green. A successful attempt does
not establish the old cause. Passing readiness/helper diagnostics does not prove
worker/data-plane success. Any measured behavioral stabilization needs separate
expectations and full native accounting qualification before CI-02 completion.
Original44648665426 cause remains unknown. Native final-artifact/D12 qualification,
owner review/acceptance and every merge/release gate remain open; CI-02 stays
In progress and P15/P16 remain parked.

## Final repository recheck

Final implementation777e039 passed repository content/Markdown/workflow/secret
checks and all478 Python tests, with no skips reported by this final suite.
Earlier one-skip checkpoint remains separately attributed above; preparing the
mapped/integration prerequisites made the retained evaluator available to the
existing offline tests. This does not resume P15 features or establish runtime
qualification. Final hygiene log SHA256
`995ac69a83d63a07702389c180d726a2de989fd4504a262ad7cd2c5ae195f972`.
Both original preservation manifests were reverified after final checks.
