"""Independent recorded gates, exact probe attribution and preservation regressions."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration import TOPICS, reject_incompatible
from integration_cases import ROOT, digest
from search_writer_recorded import RecordedOracle, qualify
from stack import StackError


class RecordedSearchTests(unittest.TestCase):
    def test_missing_or_changed_originals_fail_before_build_or_initialization(self):
        for error in (FileNotFoundError(), ValueError("original_hash_changed")):
            with (
                patch("search_writer_recorded.originals", side_effect=error),
                patch("search_writer_recorded.build") as build,
                patch("search_writer_recorded.Integration") as runtime,
            ):
                with self.assertRaises(type(error)):
                    qualify(Path("missing"), Path("missing"), Path("missing"))
                build.assert_not_called()
                runtime.assert_not_called()

    def test_windows_preservation_requires_exact_original_source_and_disposition(self):
        oracle = RecordedOracle({}, "binding", {}, {}, Path("unused"))
        diagnostic = dict(code="unsupported_source", evidence_sha256="a" * 64)
        source = dict(namespace="synthetic", instance="capture")
        oracle.windows_preservation[digest(diagnostic)] = dict(diagnostic=diagnostic, source=source)
        doc = dict(diagnostic=diagnostic, source=source)
        oracle.check_windows_preservation(doc)
        for field in ("source", "diagnostic"):
            changed = copy.deepcopy(doc)
            changed[field] = dict(other="same-count-tamper")
            with self.assertRaises(StackError):
                oracle.check_windows_preservation(changed)
        self.assertEqual({digest(diagnostic)}, oracle.seen_windows)

    def test_frozen_recorded_counts_and_membership_are_independent_literals(self):
        spec = json.loads(
            (ROOT / "contracts/search-writer/v1/fixtures/recorded-expectations.json").read_bytes()
        )
        self.assertTrue(all(sum(c.values()) == 12 for c in spec["counts"].values()))
        self.assertEqual(1 << 9, int(spec["blocked_bits"], 16))
        self.assertEqual(sum(1 << i for i in (2, 6, 7, 8, 11)), int(spec["skipped_bits"], 16))
        self.assertEqual(46, spec["per_run"]["original_records"])
        self.assertEqual(["71110000-0000-4000-8000-000000000001"], spec["matches"]["windows_cmd"])
        self.assertEqual([], spec["matches"]["auth_recorded"])

    def test_probe_uses_post_cancel_checkpoint_and_retains_actual_probe_exception(self):
        for marker, passes in (
            ("incompatible_integration_restore", True),
            ("TaskManager no longer reachable", False),
            ("checkpoint missing", False),
        ):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                cp = dict(id=42, external_path="file:///state/checkpoints/old/chk-42")
                commands = []
                job = "b" * 32
                overview = iter([dict(jobs=[]), dict(jobs=[dict(jid=job)])])

                def execute(*args):
                    commands.append(args)
                    return "JobID " + job

                class Runtime:
                    folder = Path(directory)
                    stack = SimpleNamespace(exec=execute)

                    def config(self):
                        return dict(
                            consumer_group="group",
                            broker=dict(
                                cluster_id="cluster", topics={t: dict(id=t) for t in TOPICS}
                            ),
                            bundle=dict(jar_sha256="a" * 64),
                            limits_profile="default",
                            evidence_registry_sha256="c" * 64,
                        )

                    def latest_job(self):
                        return dict(job_id="original")

                    def retained_checkpoint(self, job_id):
                        self.retained_job = job_id
                        return cp

                    def rest(self, path):
                        if path == "/jobs/overview":
                            return next(overview)
                        if path == "/jobs/" + job:
                            return dict(state="FAILED")
                        if path == "/jobs/" + job + "/exceptions":
                            return dict(exception=marker)
                        raise AssertionError("wrong diagnostic target: " + path)

                runtime = Runtime()
                if passes:
                    self.assertEqual(cp, reject_incompatible(runtime))
                else:
                    with self.assertRaisesRegex(
                        StackError, "integration_unrelated_restore_failure"
                    ):
                        reject_incompatible(runtime)
                self.assertEqual("original", runtime.retained_job)
                self.assertIn(cp["external_path"], commands[0])
                self.assertEqual(
                    dict(exception=marker),
                    json.loads(
                        (Path(directory) / "incompatible-probe-exceptions.json").read_bytes()
                    ),
                )
                self.assertEqual(
                    job,
                    json.loads((Path(directory) / "incompatible-probe.json").read_bytes())[
                        "job_id"
                    ],
                )


if __name__ == "__main__":
    unittest.main()
