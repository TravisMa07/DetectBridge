"""Managed archive contracts and real fail-closed native qualification selection."""

import copy
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_contracts import load_json
from check_gate import CONDITIONAL, EXPECTED, gate_passes

ROOT = Path(__file__).resolve().parents[2]


class MaintenanceGateTests(unittest.TestCase):
    def test_real_native_job_requires_prepared_cache_and_safe_summary(self):
        workflow = load_json(ROOT / ".github/workflows/hygiene.yml")
        self.assertIn("maintenance", workflow["jobs"]["classify-changes"]["outputs"])
        name = "archive-maintenance-verification"
        self.assertIn(name, workflow["jobs"]["required-checks"]["needs"])
        job = workflow["jobs"][name]
        self.assertIn("toolchain-verification", job["needs"])
        self.assertIn("outputs.maintenance", job["if"])
        steps = job["steps"]
        commands = "\n".join(s.get("run", "") for s in steps)
        self.assertIn("uv run --locked python tools/dev.py maintenance", commands)
        self.assertIn("uv run --locked python tools/archive_maintenance_verify.py", commands)
        restore = next(i for i, s in enumerate(steps) if s.get("id") == "prepared-gradle-cache")
        guard = next(
            i for i, s in enumerate(steps) if s.get("id") == "require-prepared-gradle-cache"
        )
        bootstrap = next(
            i for i, s in enumerate(steps) if s.get("name") == "Install pinned development tools"
        )
        self.assertLess(restore, guard)
        self.assertLess(guard, bootstrap)
        summary = next(s for s in steps if s.get("name") == "Retain synthetic maintenance summary")
        self.assertEqual(summary["with"]["path"], ".cache/archive-maintenance-reports/*.json")

    def test_affected_consumers(self):
        from classify_changes import needs_maintenance

        for path in (
            "tools/archive_maintenance.py",
            "tools/archive_profiles.py",
            "tools/archive_maintenance_verify.py",
            "tools/archive_maintenance_faults.py",
            "tools/tests/test_archive_maintenance.py",
            "tools/tests/test_archive_maintenance_faults.py",
            "tools/tests/test_managed_replay.py",
            "tools/check_archive_maintenance.py",
            "tools/managed_replay.py",
            "tools/p05_archive.py",
            "catalog/datasets/manifest.schema.json",
            "tools/replay.py",
            "tools/replay_time.py",
            "tools/datasets.py",
            "tools/contract_identity.py",
            "tools/tests/test_maintenance_gate.py",
            "tools/tests/test_p05_archive.py",
            "packages/archive-maintenance/gradle.lockfile",
            "packages/archive-writer/build.gradle.kts",
            "tools/historical.py",
            "tools/current_replay.py",
            "contracts/archive-maintenance/v1/plan.schema.json",
            "tools/dev.py",
            "uv.lock",
            ".github/workflows/hygiene.yml",
        ):
            self.assertTrue(needs_maintenance([path]), path)
        self.assertFalse(needs_maintenance(["docs/p14c2-design.md", "README.md"]))
        self.assertFalse(needs_maintenance(["tools/writer.py"]))

    def test_aggregate_is_fail_closed(self):
        needs: dict[str, Any] = {name: dict(result="skipped") for name in EXPECTED}
        for name in ("classify-changes", "repository-hygiene", "secret-scan"):
            needs[name] = dict(result="success")
        needs["classify-changes"]["outputs"] = {field: "false" for field in CONDITIONAL.values()}
        for applicable in ("true", "false", None, "unexpected"):
            needs["classify-changes"]["outputs"]["maintenance"] = applicable
            for result in ("success", "failure", "cancelled", "skipped", None):
                needs["archive-maintenance-verification"] = dict(result=result)
                self.assertEqual(
                    gate_passes(needs),
                    (applicable == "true" and result == "success")
                    or (applicable == "false" and result == "skipped"),
                )
        needs["classify-changes"]["outputs"]["maintenance"] = "false"
        needs["archive-maintenance-verification"] = dict(result="skipped")
        self.assertTrue(gate_passes(needs))
        del needs["archive-maintenance-verification"]
        self.assertFalse(gate_passes(needs))

    def test_contract_and_literal_mutations_fail(self):
        import check_archive_maintenance as checker

        original = checker.load_json
        for mutation in ("open", "remote", "source", "identity", "counts", "payload", "legacy"):

            def changed(path):
                value = copy.deepcopy(original(path))
                if Path(path) == checker.SCHEMAS / "plan.schema.json":
                    if mutation == "open":
                        value["additionalProperties"] = True
                    if mutation == "remote":
                        value["$ref"] = "https://example.invalid/schema"
                if Path(path) == checker.SCHEMAS / "fixtures/expectations.json":
                    if mutation == "source":
                        value["sources"][0]["sha256"] = "0" * 64
                    if mutation == "identity":
                        value["identities"][0]["sha256"] = "0" * 64
                    if mutation == "counts":
                        value["recorded"]["current"]["tagged"] += 1
                    if mutation == "payload":
                        value["legacy"]["objects"][0]["original_hex"] = "00"
                    if mutation == "legacy":
                        value["legacy_artifacts"]["current"] = "0" * 64
                return value

            with (
                self.subTest(mutation=mutation),
                patch.object(checker, "load_json", side_effect=changed),
            ):
                with self.assertRaises(AssertionError):
                    checker.check()


if __name__ == "__main__":
    unittest.main()
