"""Windows contract consumer selection and fail-closed component gating."""

import copy
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_windows
from check_contracts import load_json
from check_gate import CONDITIONAL, gate_passes
from classify_changes import needs_windows


class WindowsIntegrationTests(unittest.TestCase):
    def test_windows_and_shared_consumer_paths_select_real_gate(self):
        for path in (
            "packages/windows-adapters/src/main/java/Test.java",
            "packages/windows-adapters/profiles/security.mapping.json",
            "packages/windows-adapters/test_qualify.py",
            "contracts/v1/common.schema.json",
            "contracts/detection/v2/plan.schema.json",
            "tools/detection_compile.py",
            "tools/detection_mapping.py",
            "packages/detection-evaluator/src/main/java/Evaluator.java",
            "packages/transport-contracts/src/main/java/Json.java",
            "gradle/verification-metadata.xml",
            "tools/check_windows.py",
            "settings.gradle.kts",
            "uv.lock",
            "docs/windows-dependencies.json",
            "docs/transport-dependencies.json",
        ):
            self.assertTrue(needs_windows([path]), path)
        self.assertFalse(needs_windows(["docs/windows-adapters.md"]))
        self.assertFalse(needs_windows(["tools/writer.py"]))

    def test_aggregate_requires_applicable_windows_success(self):
        needs: dict[str, Any] = {
            "classify-changes": {
                "result": "success",
                "outputs": {v: "false" for v in CONDITIONAL.values()},
            },
            "repository-hygiene": {"result": "success"},
            "secret-scan": {"result": "success"},
        }
        needs.update({key: {"result": "skipped"} for key in CONDITIONAL})
        for applicability in ("true", "false", None, "unexpected"):
            needs["classify-changes"]["outputs"]["windows"] = applicability
            for result in ("success", "failure", "skipped", "cancelled", None):
                needs["windows-verification"]["result"] = result
                self.assertEqual(
                    gate_passes(needs),
                    (applicability == "true" and result == "success")
                    or (applicability == "false" and result == "skipped"),
                )
        needs["classify-changes"]["outputs"]["windows"] = "true"
        needs["windows-verification"]["result"] = "success"
        self.assertTrue(gate_passes(needs))
        missing_output = copy.deepcopy(needs)
        del missing_output["classify-changes"]["outputs"]["windows"]
        self.assertFalse(gate_passes(missing_output))
        missing_job = copy.deepcopy(needs)
        del missing_job["windows-verification"]
        self.assertFalse(gate_passes(missing_job))
        workflow = load_json(check_windows.ROOT / ".github/workflows/hygiene.yml")
        self.assertIn("windows-verification", workflow["jobs"]["required-checks"]["needs"])
        self.assertIn(
            "tools/dev.py windows", workflow["jobs"]["windows-verification"]["steps"][-1]["run"]
        )

    def test_inventory_rejects_a_coordinate_without_review(self):
        original = check_windows.load_json

        def changed(path):
            value = original(path)
            if path.name == "windows-dependencies.json":
                value = copy.deepcopy(value)
                value["coordinates"].append("unreviewed:dependency:1.0")
            return value

        with patch.object(check_windows, "load_json", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "windows_dependency_coordinates_unreviewed"):
                check_windows.check()


if __name__ == "__main__":
    unittest.main()
