"""Linux contract consumer selection and fail-closed component gating."""

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_assembly
from check_contracts import load_json
from check_gate import CONDITIONAL, gate_passes
from classify_changes import needs_assembly


class AssemblyIntegrationTests(unittest.TestCase):
    def test_linux_and_shared_consumer_paths_select_real_gate(self):
        for path in (
            "packages/linux-assembly-job/src/main/java/Test.java",
            "packages/linux-adapters/src/main/java/Test.java",
            "contracts/linux-assembly/v1/assembly-state.schema.json",
            "tools/linux_assembly.py",
            "tools/linux_assembly_verify.py",
            "packages/linux-adapters/contracts/openssh-authentication-p12a.mapping.json",
            "packages/linux-adapters/fixtures/prepare_cases.py",
            "contracts/v1/common.schema.json",
            "contracts/detection/v2/plan.schema.json",
            "tools/detection_compile.py",
            "tools/detection_mapping.py",
            "packages/detection-evaluator/src/main/java/Evaluator.java",
            "packages/transport-contracts/src/main/java/Json.java",
            "gradle/verification-metadata.xml",
            "tools/check_assembly.py",
            "settings.gradle.kts",
            "uv.lock",
            "docs/assembly-dependencies.json",
            "docs/transport-dependencies.json",
        ):
            self.assertTrue(needs_assembly([path]), path)
        self.assertFalse(needs_assembly(["docs/linux-adapters.md"]))
        self.assertFalse(needs_assembly(["tools/writer.py"]))

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
            needs["classify-changes"]["outputs"]["assembly"] = applicability
            for result in ("success", "failure", "skipped", "cancelled", None):
                needs["linux-assembly-verification"]["result"] = result
                self.assertEqual(
                    gate_passes(needs),
                    (applicability == "true" and result == "success")
                    or (applicability == "false" and result == "skipped"),
                )
        needs["classify-changes"]["outputs"]["assembly"] = "true"
        needs["linux-assembly-verification"]["result"] = "success"
        self.assertTrue(gate_passes(needs))
        missing_output = copy.deepcopy(needs)
        del missing_output["classify-changes"]["outputs"]["assembly"]
        self.assertFalse(gate_passes(missing_output))
        missing_job = copy.deepcopy(needs)
        del missing_job["linux-assembly-verification"]
        self.assertFalse(gate_passes(missing_job))
        workflow = load_json(check_assembly.ROOT / ".github/workflows/hygiene.yml")
        self.assertIn("linux-assembly-verification", workflow["jobs"]["required-checks"]["needs"])
        self.assertIn(
            "tools/dev.py assembly",
            next(
                s["run"]
                for s in workflow["jobs"]["linux-assembly-verification"]["steps"]
                if s.get("name") == "Qualify checkpointed Linux assembly and real recovery"
            ),
        )

    def test_restore_diagnostics_are_retained_after_the_runtime_step(self):
        workflow = load_json(check_assembly.ROOT / ".github/workflows/hygiene.yml")
        steps = workflow["jobs"]["linux-assembly-verification"]["steps"]
        runtime = next(
            i
            for i, s in enumerate(steps)
            if s.get("name") == "Qualify checkpointed Linux assembly and real recovery"
        )
        index, upload = next(
            (i, s)
            for i, s in enumerate(steps)
            if s.get("name") == "Retain synthetic assembly failure diagnostics"
        )
        self.assertGreater(index, runtime)
        self.assertEqual(upload["if"], "${{ failure() }}")
        self.assertIn("detectbridge-p12-test-*.json", upload["with"]["path"])
        self.assertNotIn("originals", upload["with"]["path"])

    def test_inventory_rejects_a_coordinate_without_review(self):
        original = check_assembly.load_json

        def changed(path):
            value = original(path)
            if path.name == "assembly-dependencies.json":
                value = copy.deepcopy(value)
                value["coordinates"].append("unreviewed:dependency:1.0")
            return value

        with patch.object(check_assembly, "load_json", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "assembly_unreviewed_dependency"):
                check_assembly.check()


class RestoreProbeTests(unittest.TestCase):
    def fixture(self, retained=True):
        from unittest.mock import Mock

        import linux_assembly

        first = dict(id=1, external_path="file:///state/checkpoints/" + "a" * 32 + "/chk-1")
        latest = dict(id=2, external_path="file:///state/checkpoints/" + "a" * 32 + "/chk-2")
        test = Mock()
        test.project = "detectbridge-p12-test-regression"
        test.latest_job.return_value = dict(job_id="a" * 32)
        test.retained_checkpoint.return_value = latest
        test.config.return_value = dict(
            consumer_group="group",
            broker=dict(
                cluster_id="cluster", topics={t: dict(id=t) for t in linux_assembly.TOPICS}
            ),
            bundle=dict(jar_sha256="a" * 64),
            limits_profile="default",
            evidence_registry_sha256="b" * 64,
        )
        observed = []

        def submit(*args):
            observed.append(args)
            return "JobID " + "b" * 32

        test.stack.exec.side_effect = submit
        overviews = iter([dict(jobs=[]), dict(jobs=[dict(jid="b" * 32)])])

        def rest(path):
            if path == "/jobs/overview":
                return next(overviews)
            if path.endswith("/exceptions"):
                return {
                    "root-exception": "incompatible_assembly_restore"
                    if retained and latest["external_path"] in observed[0]
                    else "FileNotFoundException old checkpoint removed"
                }
            return dict(state="FAILED")

        test.rest.side_effect = rest
        return test, first, latest, observed

    def test_probe_reselects_after_cancel_before_incompatible_restore(self):
        import linux_assembly

        test, first, latest, observed = self.fixture()
        with patch.object(linux_assembly, "save"):
            selected = linux_assembly.reject_incompatible(test, first)
        self.assertEqual(selected, latest)
        self.assertIn(latest["external_path"], observed[0])
        self.assertNotIn(first["external_path"], observed[0])
        test.retained_checkpoint.assert_called_once_with("a" * 32)

    def test_unrelated_restore_failure_is_retained_and_still_fails(self):
        import linux_assembly

        test, first, latest, observed = self.fixture(retained=False)
        with patch.object(linux_assembly, "save") as save:
            with self.assertRaisesRegex(
                linux_assembly.StackError, "assembly_unrelated_restore_failure"
            ):
                linux_assembly.reject_incompatible(test, first)
            self.assertEqual(save.call_count, 1)
            value = save.call_args.args[1]
            self.assertEqual(value["job_id"], "b" * 32)
            self.assertIn("FileNotFoundException", json.dumps(value))


if __name__ == "__main__":
    unittest.main()
