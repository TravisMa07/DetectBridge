import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classify_changes as classifier
from check_gate import CONDITIONAL


class LifecycleArchiveGateTest(unittest.TestCase):
    def test_profile_selects_consumers(self):
        for path in (
            "tools/lifecycle_archive_graph.py",
            "tools/lifecycle_replay.py",
            "packages/lifecycle-archive/build.gradle.kts",
        ):
            for check in (
                classifier.needs_integration,
                classifier.needs_activation,
                classifier.needs_archive,
                classifier.needs_historical,
                classifier.needs_current,
                classifier.needs_maintenance,
            ):
                with self.subTest(path=path, consumer=check.__name__):
                    self.assertTrue(check([path]))

    def test_native_job_required(self):
        self.assertEqual(CONDITIONAL.get("lifecycle-archive-verification"), "lifecycle_archive")
