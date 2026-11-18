"""Current replay contracts, affected consumers and real fail-closed CI selection."""

import copy
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_contracts import load_json
from check_gate import CONDITIONAL, EXPECTED, gate_passes
from historical import ROOT


class CurrentGateTests(unittest.TestCase):
    def test_native_job_runs_actual_verification_and_is_required(self):
        workflow = load_json(ROOT / ".github/workflows/hygiene.yml")
        self.assertIn("current", workflow["jobs"]["classify-changes"]["outputs"])
        self.assertIn("current-replay-verification", workflow["jobs"]["required-checks"]["needs"])
        job = workflow["jobs"]["current-replay-verification"]
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        self.assertIn("uv run --locked python tools/dev.py current", commands)
        self.assertIn("uv run --locked python tools/current_replay_verify.py", commands)
        self.assertIn("outputs.current", job["if"])
        paths = [
            s["with"]["path"]
            for s in job["steps"]
            if s.get("name") == "Retain synthetic current replay summary"
        ]
        self.assertEqual(paths, [".cache/current-replay-qualification-*/report.json"])

    def test_classifier_includes_current_and_shared_implementations(self):
        from classify_changes import needs_current

        for path in (
            "packages/current-replay/src/main/java/io/detectbridge/currentreplay/Engine.java",
            "packages/current-replay/gradle.lockfile",
            "tools/current_replay.py",
            "tools/current_replay_cases.py",
            "tools/current_replay_verify.py",
            "tools/check_current_replay.py",
            "tools/tests/test_current_gate.py",
            "tools/check_contracts.py",
            "tools/check_integration.py",
            "tools/detection_compile.py",
            "tools/transport.py",
            "tools/historical.py",
            "tools/historical_fixtures.py",
            "packages/archive-writer/src/main/java/io/detectbridge/archive/ReplaySource.java",
            "packages/integration-job/src/main/java/io/detectbridge/integration/Machine.java",
            "packages/linux-adapters/contracts/context.schema.json",
            "packages/windows-adapters/profiles/security.expected.json",
            "contracts/current-replay/v1/request.schema.json",
            "contracts/historical-replay/v1/selection.schema.json",
            "contracts/integration/v1.1/tagged-event.schema.json",
            "gradle/verification-metadata.xml",
            "settings.gradle.kts",
            "uv.lock",
            "docs/transport-dependencies.json",
            ".github/workflows/hygiene.yml",
        ):
            self.assertTrue(needs_current([path]), path)
        self.assertFalse(needs_current(["docs/p14c1-design.md", "README.md"]))
        self.assertFalse(needs_current(["tools/writer.py"]))

    def test_aggregate_rejects_applicable_current_failures_and_missing_state(self):
        needs: dict[str, Any] = {name: {"result": "skipped"} for name in EXPECTED}
        needs.update(
            {
                name: {"result": "success"}
                for name in ("classify-changes", "repository-hygiene", "secret-scan")
            }
        )
        needs["classify-changes"]["outputs"] = {field: "false" for field in CONDITIONAL.values()}
        for applicable in ("true", "false", None, "unexpected"):
            needs["classify-changes"]["outputs"]["current"] = applicable
            for result in ("success", "failure", "cancelled", "skipped", None):
                needs["current-replay-verification"] = dict(result=result)
                self.assertEqual(
                    gate_passes(needs),
                    (applicable == "true" and result == "success")
                    or (applicable == "false" and result == "skipped"),
                )
        needs["classify-changes"]["outputs"]["current"] = "false"
        needs["current-replay-verification"] = dict(result="skipped")
        self.assertTrue(gate_passes(needs))
        missing_output = copy.deepcopy(needs)
        del missing_output["classify-changes"]["outputs"]["current"]
        self.assertFalse(gate_passes(missing_output))
        del needs["current-replay-verification"]
        self.assertFalse(gate_passes(needs))

    def test_frozen_source_and_identity_mutations_fail_component_checks(self):
        import check_current_replay as current

        original = current.load_json
        for mutation in ("source", "identity", "reference", "open"):

            def changed(path):
                value = original(path)
                if Path(path) == current.SCHEMAS / "fixtures/expectations.json":
                    value = copy.deepcopy(value)
                    if mutation == "source":
                        value["sources"][0]["sha256"] = "0" * 64
                    if mutation == "identity":
                        value["identity"]["sha256"] = "0" * 64
                if Path(path) == current.SCHEMAS / "request.schema.json":
                    value = copy.deepcopy(value)
                    if mutation == "reference":
                        value["$ref"] = "https://example.invalid/schema.json"
                    if mutation == "open":
                        value["additionalProperties"] = True
                return value

            with (
                self.subTest(mutation=mutation),
                patch.object(current, "load_json", side_effect=changed),
            ):
                with self.assertRaises(AssertionError):
                    current.check()
