"""Source-derived checks on the qualification oracle itself."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lifecycle_archive_verify import check_results
from lifecycle_runtime_cases import packet, phase_cases


class ReplayOracleTest(unittest.TestCase):
    def setUp(self):
        self.case = phase_cases(1)[0]
        self.event = self.case["expected"]["event_id"]
        self.replay_run = "ea06500d-6a0d-4c8b-b9c1-6c2f92e2cd1c"
        literal = next(
            c for c in packet("expectations")["cases"] if c["case_id"] == "security-alice"
        )["bundles"]["A"]
        rule = literal["matched"][0]
        self.tagged = dict(
            event=dict(
                event=dict(id=self.event),
                detectbridge=dict(run_id=self.replay_run, quality=dict(eligibility="eligible")),
            ),
            counts=literal["counts"],
            processing_id="sha256:" + "a" * 64,
            matches=[dict(**rule, detection_id="sha256:" + "b" * 64)],
            attribution=dict(bundle_sha256="c" * 64),
        )
        self.tagged["event"]["detectbridge"]["evidence"] = [
            {k: self.case["admissions"][0]["raw"][k] for k in ("record_id", "evidence")}
        ]
        self.tagged["event"]["user"] = {"name": "Alice"}
        self.tagged["event"]["source_fields"] = {"SubjectUserName": "Alice"}
        self.detection = dict(
            event_id=self.event,
            run_id=self.replay_run,
            rule=rule,
            processing_id=self.tagged["processing_id"],
            detection_id=self.tagged["matches"][0]["detection_id"],
        )

    def verify(self, tagged, detection):
        result = dict(
            run_id=self.replay_run,
            outputs=[
                dict(kind="tagged", value=tagged),
                dict(kind="detection", value=detection),
            ],
        )
        return check_results([self.case], [result], "A", self.replay_run)

    def test_count_preserving_wrong_revision_and_foreign_event_rejected(self):
        self.verify(self.tagged, self.detection)
        wrong = copy.deepcopy(self.tagged)
        wrong["matches"][0]["revision"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "derived_literal_decision"):
            self.verify(wrong, self.detection)
        with self.assertRaisesRegex(ValueError, "derived_origin"):
            self.verify(
                self.tagged,
                dict(self.detection, event_id=phase_cases(1)[1]["expected"]["event_id"]),
            )

    def test_detection_cannot_point_at_another_processing_identity(self):
        self.verify(self.tagged, self.detection)
        with self.assertRaisesRegex(ValueError, "detection_membership"):
            self.verify(self.tagged, dict(self.detection, processing_id="sha256:" + "f" * 64))


if __name__ == "__main__":
    unittest.main()
