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

The next attempt uses a fresh deployment with the normal worker admission API
and the same source cases, expectations and deadlines. Native AMD64 and owner
disposition are pending.
