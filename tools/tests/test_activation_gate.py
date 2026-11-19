"""Actual worker-runtime applicability and fail-closed native qualification wiring."""

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_gate import CONDITIONAL, gate_passes
from classify_changes import needs_activation

ROOT = Path(__file__).resolve().parents[2]


class ActivationGateTests(unittest.TestCase):
    def test_all_real_runtime_and_transitive_inputs_select_activation(self):
        for path in (
            "packages/lifecycle-job/src/main/java/io/detectbridge/lifecycle/LifecycleJob.java",
            "packages/lifecycle-job/gradle.lockfile",
            "contracts/lifecycle-runtime/v1/state.schema.json",
            "contracts/lifecycle-runtime/v1/fixtures/expectations.json",
            "contracts/lifecycle/v1/manifest.schema.json",
            "tools/lifecycle_runtime.py",
            "tools/lifecycle_diagnostics.py",
            "tools/tests/test_lifecycle_diagnostics.py",
            "tools/lifecycle_runtime_verify.py",
            "tools/check_lifecycle_runtime.py",
            "tools/build_worker_validator.py",
            "tools/lifecycle_worker_validator.py",
            "tools/tests/test_worker_validator.py",
            "deploy/lifecycle-validator/requirements.txt",
            "tools/tests/test_activation_gate.py",
            "tools/lifecycle.py",
            "tools/detection_compile.py",
            "packages/integration-job/src/main/java/io/detectbridge/integration/Machine.java",
            "packages/linux-adapters/src/main/java/io/detectbridge/linux/Assembler.java",
            "contracts/integration/v1.1/tagged-event.schema.json",
            "settings.gradle.kts",
        ):
            with self.subTest(path=path):
                self.assertTrue(needs_activation([path]))
        self.assertFalse(needs_activation(["docs/p15b-design.md"]))

    def test_selected_activation_failure_skip_or_missing_output_blocks_aggregate(self):
        baseline: dict[str, Any] = {name: {"result": "skipped"} for name in CONDITIONAL}
        baseline.update(
            {
                "classify-changes": {
                    "result": "success",
                    "outputs": {field: "false" for field in CONDITIONAL.values()},
                },
                "repository-hygiene": {"result": "success"},
                "secret-scan": {"result": "success"},
            }
        )
        baseline["classify-changes"]["outputs"]["activation"] = "true"
        baseline["activation-verification"] = {"result": "success"}
        self.assertTrue(gate_passes(baseline))
        for result in ("failure", "skipped", "cancelled"):
            value = copy.deepcopy(baseline)
            value["activation-verification"]["result"] = result
            self.assertFalse(gate_passes(value))
        value = copy.deepcopy(baseline)
        del value["classify-changes"]["outputs"]["activation"]
        self.assertFalse(gate_passes(value))

    def test_ci01_diagnostic_job_is_additional_and_feature_base_runs_required_gate(self):
        workflow = json.loads((ROOT / ".github/workflows/hygiene.yml").read_bytes())
        self.assertIn("feat/p15b-worker-activation", workflow["on"]["pull_request"]["branches"])
        self.assertFalse(
            workflow["on"]["workflow_dispatch"]["inputs"]["activation-diagnostic"]["default"]
        )
        jobs = workflow["jobs"]
        diagnostic = jobs["activation-diagnostic"]
        self.assertIn("workflow_dispatch", diagnostic["if"])
        self.assertIn("inputs.activation-diagnostic", diagnostic["if"])
        self.assertEqual(jobs["activation-verification"]["runs-on"], diagnostic["runs-on"])
        self.assertEqual(
            jobs["activation-verification"]["timeout-minutes"], diagnostic["timeout-minutes"]
        )
        step = next(
            s for s in diagnostic["steps"] if "lifecycle_runtime_verify.py" in s.get("run", "")
        )
        self.assertTrue(step["run"].endswith("--scenario-group production-faults"))
        self.assertNotIn("DETECTBRIDGE_ACTIVATION_REQUIRED", step.get("env", {}))
        self.assertNotIn("activation-diagnostic", jobs["required-checks"]["needs"])
        self.assertIn("activation-verification", jobs["required-checks"]["needs"])

    def test_runtime_job_uses_exact_seed_cache_before_real_qualification(self):
        jobs = json.loads((ROOT / ".github/workflows/hygiene.yml").read_bytes())["jobs"]
        job = jobs["activation-verification"]
        self.assertIn("outputs.activation", job["if"])
        steps = job["steps"]
        cache = next(s for s in steps if s.get("id") == "prepared-gradle-cache")
        self.assertTrue(cache["with"]["fail-on-cache-miss"])
        guard = next(
            i for i, s in enumerate(steps) if s.get("id") == "require-prepared-gradle-cache"
        )
        bootstrap = next(
            i for i, s in enumerate(steps) if "tools/dev.py bootstrap" in s.get("run", "")
        )
        actual = next(
            i
            for i, s in enumerate(steps)
            if "tools/lifecycle_runtime_verify.py" in s.get("run", "")
        )
        self.assertLess(guard, bootstrap)
        self.assertLess(bootstrap, actual)
        self.assertEqual("1", steps[actual]["env"]["DETECTBRIDGE_ACTIVATION_REQUIRED"])
        self.assertIn("activation-verification", jobs["required-checks"]["needs"])
        evidence = steps[-1]["with"]
        self.assertIn(".cache/lifecycle-runtime-qualification/summary.json", evidence["path"])
        self.assertNotIn(".cache/lifecycle-runtime-work", evidence["path"])
        self.assertEqual("error", evidence["if-no-files-found"])


if __name__ == "__main__":
    unittest.main()
