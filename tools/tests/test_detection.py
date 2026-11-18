"""Independent compiler expectations and rejection tests."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detection_compile import ROOT, CompileError, compile_rules, encoded, parse

FIXTURES = ROOT / "contracts/detection/v1/fixtures"
SOURCE = json.loads((ROOT / "contracts/v1/examples/windows-security-4688.source.json").read_text())
RULE = (FIXTURES / "rules/process.yml").read_text()


class CompilerTests(unittest.TestCase):
    def compile(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rule.yml"
            path.write_text(text)
            return compile_rules([path], [SOURCE])

    def test_deterministic_typed_plan(self):
        a = self.compile(RULE)
        self.assertEqual(encoded(a), encoded(self.compile(RULE)))
        expression = a["rules"][0]["expression"]
        self.assertEqual(expression["op"], "and")
        self.assertEqual(expression["args"][1]["op"], "not")
        self.assertEqual(expression["args"][0]["op"], "or")
        self.assertEqual(a["rules"][0]["yaml"], RULE)

    def test_unsupported_even_when_unused(self):
        for field, value in [
            ("Unknown", "x"),
            ("Image|re", "x"),
            ("Image|contains|all", "[a,b]"),
            ("Image", "null"),
            ("Image", "true"),
            ("Image", "1.5"),
            ("Image", "[]"),
            ("ProcessId", "9223372036854775808"),
            ("ProcessId", '"1"'),
            ("Image", "1"),
        ]:
            text = RULE.replace("  condition:", f"  unused:\n    {field}: {value}\n  condition:")
            with self.subTest(field=field, value=value), self.assertRaises(CompileError):
                self.compile(text)

    def test_unsupported_conditions_and_structures(self):
        for text in [
            RULE.replace("selection and not excluded", "1 of selection*"),
            RULE.replace("selection and not excluded", "[selection, excluded]"),
            RULE.replace("selection and not excluded", "unknown"),
            RULE + "\ncorrelation: {}\n",
            RULE.replace("category: process_creation", "definition: arbitrary"),
            RULE.replace("  excluded:", "  excluded: []\n  unused:"),
        ]:
            with self.subTest(text=text), self.assertRaises(CompileError):
                self.compile(text)

    def test_yaml_safety(self):
        for text in [
            "a: 1\na: 2",
            "a: &a [*a]",
            "a: !!python/object:os.system {}",
            "a: 1\n---\nb: 2",
            "a: " + "[" * 40 + "0" + "]" * 40,
        ]:
            with self.subTest(text=text), self.assertRaises(CompileError):
                parse(text)

    def test_count_and_size_limits(self):
        with self.assertRaises(CompileError):
            compile_rules([], [SOURCE])
        with self.assertRaises(CompileError):
            compile_rules([FIXTURES / "rules/process.yml"] * 101, [SOURCE])
        with self.assertRaises(CompileError):
            parse("x" * 262145)
        with self.assertRaises(CompileError):
            self.compile(RULE.replace("harmless", "x" * 4097))

    def test_invalid_source_snapshot(self):
        source = copy.deepcopy(SOURCE)
        source["mappings"][0]["target_path"] = "undefined.field"
        with self.assertRaises(CompileError):
            compile_rules([FIXTURES / "rules/process.yml"], [source])

    def test_integer_precision_is_preserved(self):
        import yaml

        rule = yaml.safe_load(RULE)
        rule["detection"] = {
            "selection": {"ProcessId": [9223372036854775807, -9223372036854775808]},
            "condition": "selection",
        }
        expression = self.compile(yaml.safe_dump(rule))["rules"][0]["expression"]
        self.assertEqual(
            [n["value"] for n in expression["args"]], [9223372036854775807, -9223372036854775808]
        )

    def test_failed_cli_preserves_existing_plan_and_redacts_values(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rule = folder / "bad.yml"
            rule.write_text(RULE.replace("Image|endswith", "private-secret-sentinel|re"))
            output = folder / "plan.json"
            output.write_bytes(b"previous-valid-plan")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/detection_compile.py"),
                    str(rule),
                    "--source",
                    str(ROOT / "contracts/v1/examples/windows-security-4688.source.json"),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                timeout=35,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"previous-valid-plan")
            self.assertNotIn(b"private-secret-sentinel", result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["category"], "unmapped_field")

    def test_plan_schema_closes_source_snapshots(self):
        from check_contracts import ContractValidator, StrictValidator, load_json
        from detection_compile import DIRECTORY

        plan = self.compile(RULE)
        plan["sources"][0]["unexpected"] = "value"
        validator = StrictValidator(
            load_json(DIRECTORY / "plan.schema.json"), registry=ContractValidator().registry
        )
        self.assertTrue(list(validator.iter_errors(plan)))


class DetectionGateTests(unittest.TestCase):
    def test_shared_contracts_and_gate(self):
        from check_gate import CONDITIONAL, gate_passes
        from classify_changes import needs_detection

        for path in (
            "contracts/v1/normalized-event.schema.json",
            "contracts/detection/v1/plan.schema.json",
            "packages/transport-contracts/src/main/java/X.java",
            "tools/detection.py",
            "tools/check_mapping.py",
            "tools/detection_mapping.py",
            "tools/tests/test_mapping.py",
            "contracts/detection/v2/plan.schema.json",
            "gradle/verification-metadata.xml",
            "uv.lock",
        ):
            self.assertTrue(needs_detection([path]), path)
        self.assertFalse(needs_detection(["docs/detection.md"]))
        workflow = json.loads((ROOT / ".github/workflows/hygiene.yml").read_text())
        artifact = workflow["jobs"]["detection-verification"]["steps"][-1]
        self.assertEqual("${{ failure() }}", artifact["if"])
        self.assertIn("checkpoint.json", artifact["with"]["path"])
        self.assertNotIn("inputs", artifact["with"]["path"])

        for applicable in ("true", "false"):
            needs: dict[str, Any] = {
                "classify-changes": {
                    "result": "success",
                    "outputs": {value: "false" for value in CONDITIONAL.values()},
                },
                "repository-hygiene": {"result": "success"},
                "secret-scan": {"result": "success"},
            }
            for key in CONDITIONAL:
                needs[key] = {"result": "skipped"}
            needs["classify-changes"]["outputs"]["detection"] = applicable
            for result in ("success", "skipped", "failure", "cancelled", None):
                needs["detection-verification"]["result"] = result
                self.assertEqual(
                    gate_passes(needs), result == ("success" if applicable == "true" else "skipped")
                )


class DetectionQualificationRetentionTests(unittest.TestCase):
    def test_both_modes_restore_checkpoint_selected_after_cancellation(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        import detection
        from transport import Transport

        class Lifecycle:
            retained_checkpoint = Transport.retained_checkpoint

            def __init__(self, project, mapped):
                self.project, self.mapped = project, mapped
                self.input = "synthetic-input"
                self.folder = Path(directory)
                self.running, self.current, self.offset = False, 0, 0
                self.files = set()
                self.job = dict(job_id="0" * 32)
                self.retained = []
                self.stack = SimpleNamespace(
                    folder=self.folder,
                    compose=lambda *a, **kw: None,
                    down=self.down,
                    up=lambda *a: None,
                    exec=self.metadata,
                    containers=lambda: [],
                )

            def init(self):
                pass

            def config(self):
                return dict(bundle=dict(bundle_sha256="b" * 64), consumer_group="test")

            def latest_job(self):
                return self.job

            def checkpoint(self):
                return dict(
                    id=self.current,
                    status="COMPLETED",
                    external_path=f"file:/state/checkpoints/{self.job['job_id']}/chk-{self.current}",
                )

            def wait_checkpoint(self, job):
                self.current += 1
                self.files = {self.current}
                return self.checkpoint()

            def wait_quarantine_retry_limit(self, job):
                self.running = False
                return self.wait_checkpoint(job)

            def stop(self):
                self.current += 10
                self.files = {self.current}
                self.running = False
                self.retained.append(self.current)

            def rest(self, path):
                return (
                    dict(latest=dict(completed=self.checkpoint()))
                    if path.endswith("/checkpoints")
                    else dict(state="RUNNING" if self.running else "CANCELED")
                )

            def metadata(self, service, command, flag, path):
                if int(path.split("chk-")[1].split("/")[0]) not in self.files:
                    raise detection.StackError("checkpoint_metadata_missing")

            def start(self, restore=None):
                if restore:
                    self.metadata("jobmanager", "test", "-s", restore + "/_metadata")
                self.job = dict(job_id=f"{self.current + 1:032x}")
                self.running = True
                return self.job

            def down(self):
                # A running job can retire the selected file during slow shutdown.
                if self.running:
                    self.files.clear()
                self.running = False

            def accounted(self, *args):
                return [dict(run_id=str(i)) for i in range(7 if self.mapped else 2)]

            def inject_event(self, *args):
                self.offset += 1
                return dict(offset=self.offset)

            def wait_input_checkpoint(self, *args):
                pass

            def process_args(self, *args):
                return args

            def helper_run(self, *args, **kwargs):
                return SimpleNamespace(stdout=json.dumps(dict(offset=100)))

            def private_read(self, *args, **kwargs):
                return SimpleNamespace(stdout=json.dumps(dict(offset=0)))

            def metrics(self):
                return dict(value="detectbridge_detection")

        with tempfile.TemporaryDirectory() as directory:
            instances = []

            def factory(project, mapped):
                instance = Lifecycle(project, mapped)
                instances.append(instance)
                return instance

            for mapped in (False, True):
                with (
                    patch.object(detection, "Detection", side_effect=factory),
                    patch.object(detection, "run"),
                    patch.object(detection, "save"),
                    patch.object(detection, "qualify_incompatible_restore"),
                ):
                    result = detection.qualify(mapped=mapped)
                    self.assertEqual("qualified", result["status"])
                    self.assertTrue(instances[-1].retained)


if __name__ == "__main__":
    unittest.main()
