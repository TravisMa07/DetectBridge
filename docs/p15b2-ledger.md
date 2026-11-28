# P15b2 archive and replay qualification

The independent design and expectations were committed in `be2369f` on verified
main `3fe77bb`. [P15 issue #15](https://github.com/TravisMa07/DetectBridge/issues/15)
tracks the work. The [requirements map](p15-acceptance.md) covers P15a, P15b1 and
the lifecycle archive. Original runtime evidence and build artifacts are private.

## Component evidence

| Area | Actual observation on macOS ARM64 |
| --- | --- |
| Storage | Nine Java tests passed, covering physical identity, nullable repeated headers, opaque bytes, interruption, prefix recovery, corrupt segments and missing originals. The storage red XML hash is `d6dd479ef53700d5473996901286fe12192c907876621e8dda0b5e00758550c3`. |
| Legacy consumers | 15 archive-writer and 53 managed-maintenance Java tests passed. 35 legacy historical, current and managed replay Python cases passed. The dependency inventory still contains 67 distinct reviewed coordinates. |
| Graph and retention | Negative graph tests cover unknown Windows context dependencies, incomplete and conflicting artifact members, missing originals and altered evidence. A six-topic catalog prepared from the earlier B1 deployment initialized and exported exact retained artifact bytes. The managed retirement command denied deletion. |
| Replay | Eight targeted component cases passed. The duplicate physical input regression failed before the fix. The pinned helper reproduced the six-member whoami audit decision, detection and manifest in a standalone ARM64 run using retained source from B1 attempt `9acc4cd3923749479f34ff02f26778b2`. |
| CI | Before CI wiring, two gate tests failed with 17 unmet assertions. After wiring they passed. The first full Python suite exposed three stale cache-consumer counts after adding the eighteenth consumer. Cache guard checks passed after updating the exact count. |

## Runtime qualification

Each invocation of `uv run --locked python tools/lifecycle_archive_verify.py`
writes its own source inventory and summary under
`.cache/lifecycle-archive-qualification/attempts/<id>/`. Only the source hashes
and public synthetic summaries are eligible for CI upload. The [expectation
matrix](p15b2-expectations.md) fixes A/B, raw memberships and decisions before
implementation.

The lifecycle archive JAR built locally with SHA-256
`4ee221bd38c55395b0308450c24119e553023998dc6e9a4eeb9a37c7b598db52`.
Both old replay helper JAR hashes, the original producer, worker runtime and
compiler packet matched their frozen values.

| ARM64 attempt | Outcome |
| --- | --- |
| `f06d59b8446c44cc80f7111a35d5f7e9` | Artifact build passed. Docker could not allocate another default network for the broker. No scenario ran. |
| `4b067f77ba224795be8f539204cae48f` | Broker started on an explicit private subnet. The qualifier was interrupted to narrow the archive helper mount to its evidence directory. |
| `8347e55d422f4fb29e6d0071ce8964b1` | Two workers reached the mixed interval. The qualification-only batch sender stopped partway through the second audit B group. Three receipts and the fourth attempted position were retained. The qualifier stopped its resources. |

The next fresh deployment used the production worker admission API with the
same source cases, expectations and deadlines.

| Completed ARM64 attempt | Source and evidence |
| --- | --- |
| `01810daca46f44bb992bf6eec86a70bd` | Passed on Docker Linux aarch64 under macOS ARM64. The worktree had changes on freeze commit `be2369f` when the attempt started. Source inventory SHA-256 `c06e84a0f13007331b560caa6cdaa804aa88dd1026e948bfbc3ac38374f655e5`, summary SHA-256 `2f5ac700ebe05720caf3c65194eec49c3c6b7590617a8e9b05d9657c71010b2f`. |

The clean rerun `444a98a8bf2d4c6fa5af0e916e1c1565` passed the complete
profile on implementation commit `6139e16`. Its source inventory SHA-256 was
`317bc07d457bb84ebedd8638ccbad0b7dbf1aac9774e312b6c02e6426ea07815`
and its summary SHA-256 was
`53937c42324d2a87994e765b7a30daa8e3698821c61cb9739f42e751ea8fa577`.
All heads started at zero. After segment publication the acknowledgment head
was four with all Kafka commits still absent. Recovery matched all six
offsets and the independent Kafka reads. The 227-record export contained
110 acknowledgments, with SHA-256
`ade383858a0716b25406283bb30476c5c2abc5854b7ba62a7615d4e67191fb85`.
All thirteen isolated replay runs and the individual decisions below passed.
The separate 268-record S12 archive had export SHA-256
`ddbdda7d9fb6952f7fd61281efa0a5efcdd152d1ff34fa35d7ca85681772ad9e`
and the compiler rejected the signed inconsistent plan. Supplemental checks
verified all thirteen published run bindings against the committed controller,
graph, signature helper and archive reader. Current mode rejected the S12
archive and an unregistered bundle selection. The managed retention CLI
refused retirement of both archives and their complete file digests stayed
identical. Supplemental report SHA-256 was
`bf76832a5c033333d932e47af8f6b7dc12edf4896e5570715e03ebdb894b4db4`.

The preceding clean ARM64 attempt, `e72917cb446d42d59de1be84f7a6897a`, built
from `6139e16` with source inventory
`317bc07d457bb84ebedd8638ccbad0b7dbf1aac9774e312b6c02e6426ea07815`.
It stopped after 16 admissions during post-mixed convergence, before archive
capture. The audit worker's Flink REST exception records a ten-second Pekko
ask timeout for `sendOperatorEventToCoordinator`. The retained exception and
attempt summary SHA-256 values are
`b6d90c0e14442c8f33fff0f2d3c6290f26b19700301884200b66369754996e52`
and `4bffdeaa270ee7e153dbaadd724dfd1ccc4acf8522d60dc948b121cd2c4fefed`.

The first completed run archived 220 physical records. An independent Kafka
consumer matched all six topics byte for byte. The archive contained 42 raw
admissions, 66 outputs, 103 acknowledgments, six artifact records and three
controls. The export SHA-256 was
`3fd3f260208f10294dc66920975df38f12fd6f613e1f0f0fc83bc4da16bf94ea`.
The first interruption kept the prior head. The second left the output head at
four with all six Kafka offsets still uncommitted. Recovery brought every
broker offset to its durable head. Both workers rejected the authority-signed
inconsistent plan. Its separate 262-record archive failed graph verification
with `lifecycle_archive_compiler_rejected`.

The workers were stopped before replay. Six historical selections and six
explicit current B selections produced these observed matches. Each cell
agreed with its corresponding frozen expectation. Each other tagged event in
the same pair was a verified nonmatch. The freeze lists six count fields, but
prints only five numbers for a nonmatch. The observed six-field nonmatch was
`(0,1,1,0,0,0)`, with empty diagnostics, consistent with the named outcomes.

| Recorded revision | Historical Windows and audit match | Explicit current B Windows and audit match |
| --- | --- | --- |
| Initial A, revision 1 | Alice, whoami | Bob, false |
| B, revision 2 | Bob, false | Bob, false |
| Rollback A, revision 3 | Alice, whoami | Bob, false |

Eight of twelve decisions changed. The second historical run had disjoint
derived identities. Recovery at both replay interruption points and completed
resume preserved the original archive and produced byte-identical results
within the resumed run.

The ARM64 Flink, Kafka and validator image SHA-256 values were
`55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe`,
`9916d60eca5d599550e2c320230808fda342124ba550bb4ac4ea8591803262a0`
and `9ba37c12416c95b01be4d6f7a64ddeb1704a4dae17ffb6d49a99c41fd3c218ea`.
Both plans and the original producer, worker and validator matched the
[artifact inventory](p15b2-expectations.md#immutable-artifacts-and-source-provenance).
The historical and current helper JARs had SHA-256
`32bad6f526e3208bf4b2684979a4d600c82b35070e39cbeb3a5fce6d5fccfcc4`
and `ea9d47406651a686546a2514f83fe59689fa38902e76b0c2c6aa129c37a511e2`.

## Native AMD64 qualification

The [native archive job](https://github.com/TravisMa07/DetectBridge/actions/runs/46102348166/job/140847856328)
passed on Linux x86_64 using Docker 28.0.4. Attempt
`ef43cf9a96814efe883e95e7daeddd23` ran on GitHub's clean test merge
`77cf66c38753700634e6d6757e5c1b4b25b4cdd6` for implementation head
`6139e16`. Its source inventory SHA-256 matched the clean ARM64 build,
`317bc07d457bb84ebedd8638ccbad0b7dbf1aac9774e312b6c02e6426ea07815`.
The [CI artifact](https://github.com/TravisMa07/DetectBridge/actions/runs/46102348166/artifacts/15246188492)
had SHA-256 `1d0154aeb87adbf5b429786467224ecd42f47f9bfa8e275c133bb29a0598d3d9`.
The summary SHA-256 was
`710991b380832940ea259243ec7a62eea6849aa0598fff8ebfe454063182c3df`.

After both interruption boundaries, the recovered native archive matched all
six independent Kafka reads. Its 270 records comprised 42 admissions, 66
outputs, 153 acknowledgments, six artifact records and three controls. Export
SHA-256 was `a5e067fe3172a62269242557b654a4510b847e484c73ade3cf0ddb1876adf57d`.
The 318-record S12 archive failed closed with
`lifecycle_archive_compiler_rejected`. Both workers stopped before replay.
All six historical and six current selections, duplicate historical run,
interrupted and completed resumes, individual outcomes in the table above
and the eight changed decisions passed. All six JARs matched the ARM64
builds. The AMD64 image IDs for Flink, Kafka and the validator were
`6b26436e8a89f49acaf0133e35f1e3715544e7c984d0f68cd8038137ab2e6be9`,
`55c1b9c10383fbe90c4cf5f68cf02e6813f645fddd553483dcc66e8c3d3c6f24`
and `7a55cb3935282f3e591e1d3ff97ac290e88210356ebc86e11bfb3c341769d427`.

## Repository and CI evidence

The [native transport job](https://github.com/TravisMa07/DetectBridge/actions/runs/46102348166/job/140847856259)
on the first implementation PR run failed during JobManager restoration with
`qualification_jobmanager_restore_command_failed_checkpoint_metadata_exit_1`.
On that attempt the transport qualification and deploy/local sources matched
the verified main baseline. The log identifies the failed metadata check. Its
underlying cause is unconfirmed. The retained log SHA-256 is
`10b6027388657caa5256bbec6964c084cad604e6628ba3589b6a599d1a20c8d3`.

The qualifier had selected a completed checkpoint from a running producer
before stack shutdown. The transport qualification now uses its existing
`retained_checkpoint` helper to cancel the producer and verify the retained
metadata before shutdown, following the [P14 qualification correction](p14-ledger.md).
The check still restarts the full stack, restores the checkpoint and verifies
accounting. All 15 transport component tests passed, including the regression
that retires a previously observed checkpoint during shutdown. The full local
repository check passed after this correction, log SHA-256
`a24083895939b1a19f3acac4423fa7bee954223f5ac4be3aaed1b86c44f594fe`.
The [native search job](https://github.com/TravisMa07/DetectBridge/actions/runs/46102348166/job/140847856317)
passed. CI-02 remains open with the original cause unknown.

The repository check on implementation commit
`6139e16f7152189689cb2cc4405cbc3fc78a6881` passed all 495 Python tests,
repository content and Markdown checks, workflow validation, secret scans, Ruff
lint and formatting, and mypy on 131 source files. The full local log SHA-256
is `5278a33d557070e870743eda37c93c932f915df870cc3a4da6027b72e596336d`.
The Windows context mutation test first accepted three unknown dependency
edges under the open P13 Windows input schema. The closed context check now
rejects all three. The original red and corrected component log hashes are
`588458d19b4e62ef9c1ea82bb54d6538b5c65920f3ab0e3a2ed6f9d77ee3b464`
and `3a6811b4013f4568f892a7ff3fe88518ba9a7c4f99cf25d58eaec4c802b505a9`.
