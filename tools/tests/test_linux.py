"""Linux contract consumer selection and fail-closed component gating."""

import copy
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_linux
from check_contracts import load_json
from check_gate import CONDITIONAL, gate_passes
from classify_changes import needs_linux


class LinuxIntegrationTests(unittest.TestCase):
    def test_linux_and_shared_consumer_paths_select_real_gate(self):
        for path in (
            "packages/linux-adapters/src/main/java/Test.java",
            "packages/linux-adapters/contracts/openssh-authentication-p12a.mapping.json",
            "packages/linux-adapters/fixtures/prepare_cases.py",
            "contracts/v1/common.schema.json",
            "contracts/detection/v2/plan.schema.json",
            "tools/detection_compile.py",
            "tools/detection_mapping.py",
            "packages/detection-evaluator/src/main/java/Evaluator.java",
            "packages/transport-contracts/src/main/java/Json.java",
            "gradle/verification-metadata.xml",
            "tools/check_linux.py",
            "settings.gradle.kts",
            "uv.lock",
            "docs/linux-dependencies.json",
            "docs/transport-dependencies.json",
        ):
            self.assertTrue(needs_linux([path]), path)
        self.assertFalse(needs_linux(["docs/linux-adapters.md"]))
        self.assertFalse(needs_linux(["tools/writer.py"]))

    def test_aggregate_requires_applicable_linux_success(self):
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
            needs["classify-changes"]["outputs"]["linux"] = applicability
            for result in ("success", "failure", "skipped", "cancelled", None):
                needs["linux-verification"]["result"] = result
                self.assertEqual(
                    gate_passes(needs),
                    (applicability == "true" and result == "success")
                    or (applicability == "false" and result == "skipped"),
                )
        needs["classify-changes"]["outputs"]["linux"] = "true"
        needs["linux-verification"]["result"] = "success"
        self.assertTrue(gate_passes(needs))
        missing_output = copy.deepcopy(needs)
        del missing_output["classify-changes"]["outputs"]["linux"]
        self.assertFalse(gate_passes(missing_output))
        missing_job = copy.deepcopy(needs)
        del missing_job["linux-verification"]
        self.assertFalse(gate_passes(missing_job))
        workflow = load_json(check_linux.ROOT / ".github/workflows/hygiene.yml")
        self.assertIn("linux-verification", workflow["jobs"]["required-checks"]["needs"])
        self.assertIn(
            "tools/dev.py linux", workflow["jobs"]["linux-verification"]["steps"][-1]["run"]
        )

    def test_inventory_rejects_a_coordinate_without_review(self):
        original = check_linux.load_json

        def changed(path):
            value = original(path)
            if path.name == "linux-dependencies.json":
                value = copy.deepcopy(value)
                value["coordinates"].append("unreviewed:dependency:1.0")
            return value

        with patch.object(check_linux, "load_json", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "linux_dependency_coordinates_unreviewed"):
                check_linux.check()


if __name__ == "__main__":
    unittest.main()
