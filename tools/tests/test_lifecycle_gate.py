"""P15a consumer classification and fail-closed native qualification wiring."""

import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_gate import CONDITIONAL, gate_passes
from classify_changes import needs_lifecycle

ROOT = Path(__file__).resolve().parents[2]


class LifecycleGateTests(unittest.TestCase):
    def test_all_actual_candidate_and_shared_inputs_select_real_consumer(self):
        for path in (
            "tools/lifecycle.py",
            "tools/lifecycle_validation.py",
            "tools/lifecycle_verify.py",
            "tools/tests/test_lifecycle.py",
            "contracts/lifecycle/v1/request.schema.json",
            "tools/detection_compile.py",
            "packages/integration-job/build.gradle.kts",
            "packages/detection-evaluator/src/main/java/io/detectbridge/detection/Evaluator.java",
            "contracts/v1/normalized-event.schema.json",
            "tools/check_contracts.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(needs_lifecycle([path]))
        self.assertFalse(needs_lifecycle(["docs/p15-design.md"]))

    def test_lifecycle_is_required_when_selected_and_skips_fail(self):
        needs: dict[str, Any] = {
            "classify-changes": {"result": "success", "outputs": {}},
            "repository-hygiene": {"result": "success"},
            "secret-scan": {"result": "success"},
        }
        for job, output in CONDITIONAL.items():
            needs[job] = {"result": "success"}
            needs["classify-changes"]["outputs"][output] = "true"
        self.assertTrue(gate_passes(needs))
        for result in ("skipped", "failure", "cancelled"):
            needs["lifecycle-verification"]["result"] = result
            self.assertFalse(gate_passes(needs))

    def test_native_job_requires_exact_cache_before_build_and_actual_tests(self):
        jobs = json.loads((ROOT / ".github/workflows/hygiene.yml").read_text())["jobs"]
        job = jobs["lifecycle-verification"]
        steps = job["steps"]
        cache = next(s for s in steps if s.get("id") == "prepared-gradle-cache")
        self.assertTrue(cache["with"]["fail-on-cache-miss"])
        require = next(
            i for i, s in enumerate(steps) if s.get("id") == "require-prepared-gradle-cache"
        )
        bootstrap = next(
            i for i, s in enumerate(steps) if "tools/dev.py bootstrap" in s.get("run", "")
        )
        actual = next(
            i for i, s in enumerate(steps) if "tools/lifecycle_verify.py" in s.get("run", "")
        )
        self.assertLess(require, bootstrap)
        self.assertLess(bootstrap, actual)
        self.assertIn("lifecycle-verification", jobs["required-checks"]["needs"])


if __name__ == "__main__":
    unittest.main()
