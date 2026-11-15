"""Runtime mode isolation and launch contracts; no mock claims recovery qualification."""

import base64
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detection
from detection import FIXTURES, ROOT, Detection, StackError, encoded, mapped_runtime_cases, sha
from transport import digest


class RuntimeModeTests(unittest.TestCase):
    def config(self, runtime):
        result = {
            "contract_version": "1.0.0",
            "project": runtime.project,
            "bundle": {"image_id": "sha256:" + "a" * 64, "bundle_sha256": "b" * 64},
            "consumer_group": "qualified-test-group",
            "broker": {
                "cluster_id": "cluster",
                "topics": {t: {"id": "id-" + t} for t in runtime.topics},
            },
        }
        if runtime.mapped:
            result["runtime"] = "mapped/2.0.0"
        return result

    def test_projects_topics_caches_and_helpers_are_disjoint(self):
        legacy = Detection("detectbridge-p09-test")
        mapped = Detection("detectbridge-p10-test", mapped=True)
        self.assertTrue(set(legacy.topics).isdisjoint(mapped.topics))
        self.assertNotEqual(legacy.builds, mapped.builds)
        self.assertNotEqual(legacy.cache, mapped.cache)
        self.assertEqual(legacy.topics, detection.TOPICS)
        for project, mode in (
            (legacy.project, True),
            (mapped.project, False),
            ("detectbridge-dev", True),
            ("detectbridge-dev", False),
        ):
            with self.assertRaisesRegex(StackError, "dedicated_detection_project_required"):
                Detection(project, mapped=mode)
        for runtime, helper in ((legacy, "DetectionPublisher"), (mapped, "DetectionV2Publisher")):
            command = runtime.process_args("group-offset", "group", config=self.config(runtime))
            self.assertIn("io.detectbridge.detection." + helper, command)
            self.assertIn("none", command)
            self.assertIn(runtime.project + "_internal", command)

    def test_configuration_cannot_change_runtime_or_topic_boundary(self):
        runtime = Detection("detectbridge-p10-test", mapped=True)
        with tempfile.TemporaryDirectory() as directory:
            runtime.folder = Path(directory)
            for mutation in (None, "legacy-topics", "runtime"):
                config = self.config(runtime)
                if mutation == "legacy-topics":
                    config["broker"]["topics"] = {t: {"id": "id"} for t in detection.TOPICS}
                elif mutation == "runtime":
                    config["runtime"] = "legacy/1.0.0"
                (runtime.folder / "configuration.json").write_text(json.dumps(config))
                (runtime.folder / "configuration.sha256").write_text(digest(config))
                with patch.object(runtime, "bundle", return_value=config["bundle"]):
                    if mutation:
                        with self.assertRaises(StackError):
                            runtime.config()
                    else:
                        self.assertEqual(runtime.config(), config)

    def test_entrypoint_and_topic_ids_are_selected_explicitly(self):
        for mode in (False, True):
            runtime = Detection(
                "detectbridge-p10-test" if mode else "detectbridge-p09-test", mapped=mode
            )
            config = self.config(runtime)
            with tempfile.TemporaryDirectory() as directory:
                runtime.folder = Path(directory)
                with (
                    patch.object(runtime, "config", return_value=config),
                    patch.object(runtime, "verify_destination"),
                    patch.object(runtime, "latest_job", return_value=None),
                    patch.object(runtime, "rest", return_value={"jobs": []}),
                    patch.object(
                        runtime, "jobs", return_value={"contract_version": "1.0.0", "jobs": []}
                    ),
                    patch.object(runtime, "wait_checkpoint"),
                    patch.object(
                        runtime.stack, "exec", return_value="JobID " + "a" * 32
                    ) as execute,
                ):
                    runtime.start()
                    args = execute.call_args.args
                    self.assertEqual("-c" in args, mode)
                    if mode:
                        self.assertIn("io.detectbridge.detection.DetectionV2Job", args)
                    for topic in runtime.topics:
                        self.assertIn(config["broker"]["topics"][topic]["id"], args)

    def test_injection_uses_its_mode_input_and_private_ipc(self):
        runtime = Detection("detectbridge-p10-test", mapped=True)
        response = subprocess.CompletedProcess(
            [], 0, stdout='{"type":"ack","offset":0}\n{"count":1}\n'
        )
        with (
            patch.object(runtime, "config", return_value=self.config(runtime)),
            patch.object(runtime, "verify_destination"),
            patch.object(runtime, "helper_run", return_value=response) as helper,
        ):
            runtime.inject_event(b"synthetic-only", b"key")
            args = helper.call_args.args[0]
            self.assertEqual(args[-1], runtime.input)
            self.assertNotIn(detection.INPUT, args)
            self.assertIn("--log-driver", args)
            self.assertIn("data", helper.call_args.kwargs)

    def test_mapped_cases_have_distinct_runs_and_all_nonmatch_outcomes(self):
        cases = mapped_runtime_cases()
        self.assertEqual(
            [outcome for _, outcome in cases],
            [
                "configuration_blocked",
                "inapplicable",
                "quality_skipped",
                "configuration_blocked",
                "evaluation_error",
            ],
        )
        runs = [event["detectbridge"]["run_id"] for event, _ in cases]
        self.assertEqual(len(set(runs)), 5)
        self.assertTrue(
            set(runs).isdisjoint(
                {"00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"}
            )
        )
        first = copy.deepcopy(cases)
        self.assertEqual(first, mapped_runtime_cases())


class RuntimeAccountingTests(unittest.TestCase):
    def fixture(self):
        runtime = Detection("detectbridge-p10-test", mapped=True)
        event = json.loads((FIXTURES / "positive.event.json").read_text())
        plan = {
            "bundle_sha256": "a" * 64,
            "mapping_profiles": [
                json.loads(
                    (
                        ROOT / "contracts/detection/v2/fixtures/windows-security-4688.mapping.json"
                    ).read_text()
                )
            ],
        }
        location = {
            "cluster_id": "cluster",
            "topic_id": "input-id",
            "topic": runtime.input,
            "partition": 0,
            "offset": 0,
            "value_sha256": sha(encoded(event)),
        }
        expected = {
            0: {
                "event_id": event["event"]["id"],
                "run_id": event["detectbridge"]["run_id"],
                "outcome": "matched",
                "value_sha256": location["value_sha256"],
            }
        }
        identity = "sha256:" + sha(
            encoded([event["event"]["id"], event["detectbridge"]["run_id"], plan["bundle_sha256"]])
        )
        row = {
            "version": "2.0.0",
            "result_id": identity,
            "event_id": event["event"]["id"],
            "run_id": event["detectbridge"]["run_id"],
            "bundle_sha256": plan["bundle_sha256"],
            "evaluator": "detectbridge-java/2.0.0",
            "compiler": "detectbridge/2.0.0",
            "mapping_version": "source-mappings/1.0.0",
            "mapping_sha256": sha(encoded(plan["mapping_profiles"])),
            "input": location,
            "matched": [
                {
                    "id": "70000000-0000-4000-8000-000000000001",
                    "revision": sha((FIXTURES / "rules/process.yml").read_bytes()),
                }
            ],
            "counts": {
                name: int(name == "matched")
                for name in (
                    "matched",
                    "unmatched",
                    "inapplicable",
                    "configuration_blocked",
                    "quality_skipped",
                    "evaluation_error",
                )
            },
            "diagnostics": [],
        }
        return runtime, plan, expected, row

    def account(self, runtime, plan, expected, invalid, results, errors, *, wire_key=None):
        def wire(row):
            identity = row.get("result_id", row.get("quarantine_id"))
            return {
                "key": base64.b64encode(
                    identity.encode() if wire_key is None else wire_key
                ).decode(),
                "value": base64.b64encode(encoded(row)).decode(),
            }

        info = {
            "cluster_id": "cluster",
            "topics": {runtime.input: {"id": "input-id"}},
            "end_offsets": {runtime.output: len(results), runtime.quarantine: len(errors)},
        }

        def read(topic, start, stop):
            return [wire(row) for row in (results if topic == runtime.output else errors)]

        with (
            patch.object(runtime, "qualification_plan", return_value=plan),
            patch.object(runtime, "verify_destination", return_value=info),
            patch.object(runtime, "read_records", side_effect=read),
        ):
            return runtime.accounted(expected, invalid, timeout=1)

    def test_attribution_and_matches_are_checked_against_input_expectations(self):
        runtime, plan, expected, original = self.fixture()
        self.assertEqual(
            len(self.account(runtime, plan, expected, {}, [original, original], [])), 2
        )
        for mutation in (
            "event",
            "run",
            "result",
            "matches",
            "revision",
            "rule",
            "counts",
            "diagnostics",
            "schema",
            "partition",
            "mapping",
            "bundle",
            "source",
        ):
            row = copy.deepcopy(original)
            if mutation == "event":
                row["event_id"] = "wrong-event"
            elif mutation == "run":
                row["run_id"] = "00000000-0000-4000-8000-000000000009"
            elif mutation == "result":
                row["result_id"] = "sha256:" + "0" * 64
            elif mutation == "matches":
                row["matched"] = []
            elif mutation == "revision":
                row["matched"][0]["revision"] = "0" * 64
            elif mutation == "rule":
                row["matched"][0]["id"] = "other-rule"
            elif mutation == "counts":
                row["counts"]["unmatched"] = 1
            elif mutation == "diagnostics":
                row["diagnostics"] = [
                    {"rule_id": "rule", "category": "configuration_blocked", "pointer": ""}
                ]
            elif mutation == "schema":
                row["extra"] = "unsupported"
            elif mutation == "partition":
                row["input"]["partition"] = 1
            elif mutation == "mapping":
                row["mapping_sha256"] = "0" * 64
            elif mutation == "bundle":
                row["bundle_sha256"] = "0" * 64
            elif mutation == "source":
                row["input"]["topic"] = detection.INPUT
            with self.subTest(mutation=mutation), self.assertRaises(StackError):
                self.account(runtime, plan, expected, {}, [row], [])

    def test_wrong_kafka_key_cannot_pass_a_correct_result_body(self):
        runtime, plan, expected, row = self.fixture()
        with self.assertRaisesRegex(StackError, "detection_output_key_mismatch"):
            self.account(
                runtime, plan, expected, {}, [row], [], wire_key=b"wrong-result-routing-key"
            )

    def test_quarantine_identity_size_and_null_metadata_are_independent(self):
        runtime, plan, _, result = self.fixture()
        location = result["input"]
        identity = "sha256:" + sha(encoded(["cluster", "input-id", "0", "0"]))
        original = {
            "version": "1.0.0",
            "quarantine_id": identity,
            "input": location,
            "value_size": 17,
            "value_is_null": False,
            "category": "invalid_normalized_input",
        }
        invalid = {
            0: {"value_sha256": location["value_sha256"], "value_size": 17, "value_is_null": False}
        }
        self.assertEqual(self.account(runtime, plan, {}, invalid, [], [original]), [])
        for field, value in (
            ("quarantine_id", "wrong"),
            ("value_size", 18),
            ("value_is_null", True),
            ("category", "other"),
            ("extra", True),
        ):
            row = copy.deepcopy(original)
            row[field] = value
            with self.subTest(field=field), self.assertRaises(StackError):
                self.account(runtime, plan, {}, invalid, [], [row])


class FailureDiagnosticTests(unittest.TestCase):
    def test_only_fixed_categories_leave_failure_boundary(self):
        for category in (
            "command_failed_checkpoint_metadata_exit_1",
            "job_terminated_before_checkpoint",
            "detection_output_key_mismatch",
            "command_failed_internal_http_exit_22",
        ):
            self.assertEqual(detection.failure_category(StackError(category)), category)
        for error in (
            StackError("private-value-sentinel"),
            ValueError("private-value-sentinel"),
            StackError("command_failed_job_submission_exit_999 private-value-sentinel"),
        ):
            self.assertEqual(detection.failure_category(error), "detection_operation_failed")
        self.assertEqual(
            detection.failure_category(KeyError("private-value-sentinel")),
            "unexpected_document_shape",
        )
        self.assertEqual(detection.failure_category(OSError("private-value-sentinel")), "io_error")

    def test_cli_failure_remains_nonzero_and_redacted(self):
        for error, expected in (
            (
                StackError("command_failed_checkpoint_metadata_exit_1"),
                "command_failed_checkpoint_metadata_exit_1",
            ),
            (ValueError("private-value-sentinel"), "detection_operation_failed"),
        ):
            output = io.StringIO()
            with (
                patch.object(sys, "argv", ["detection.py", "verify"]),
                patch.object(detection, "qualify", side_effect=error),
                redirect_stdout(output),
            ):
                with self.assertRaises(SystemExit) as result:
                    detection.main()
            self.assertEqual(result.exception.code, 1)
            self.assertEqual(json.loads(output.getvalue())["category"], expected)
            self.assertNotIn("private-value-sentinel", output.getvalue())


class IncompatibleRestoreTests(unittest.TestCase):
    def runtime(self, synchronous, *, detail="incompatible_detection_restore", created=None):
        runtime = Mock()
        config = {
            "consumer_group": "group",
            "broker": {"cluster_id": "cluster", "topics": {"input": {"id": "input-id"}}},
        }
        runtime.config.return_value = copy.deepcopy(config)
        runtime.topics = ["input"]
        old, new = "a" * 32, "b" * 32
        runtime.stack.exec.side_effect = (
            StackError("command_failed_job_submission_exit_1") if synchronous else None
        )
        runtime.stack.exec.return_value = "JobID " + new
        overview_calls = 0

        def rest(path):
            nonlocal overview_calls
            if path == "/jobs/overview":
                overview_calls += 1
                values = (
                    [old] if overview_calls == 1 else ([old, new] if created is None else created)
                )
                return {"jobs": [{"jid": value, "state": "FAILED"} for value in values]}
            if path == "/jobs/" + new:
                return {"state": "FAILED"}
            if path == "/jobs/" + new + "/exceptions":
                return {"root-exception": detail}
            raise AssertionError("unexpected REST path")

        runtime.rest.side_effect = rest
        return runtime, config

    def test_async_and_synchronous_rejection_require_the_binding_failure(self):
        for synchronous in (False, True):
            runtime, original = self.runtime(synchronous)
            detection.qualify_incompatible_restore(runtime, {"external_path": "file:///checkpoint"})
            self.assertEqual(runtime.config.return_value, original)
            runtime.stop.assert_called_once()
            runtime.stack.exec.assert_called_once()
            self.assertIn("group-incompatible", runtime.stack.exec.call_args.args)
            runtime.rest.assert_any_call("/jobs/" + "b" * 32 + "/exceptions")

    def test_unrelated_failure_and_ambiguous_job_are_not_a_pass(self):
        for synchronous in (False, True):
            runtime, _ = self.runtime(synchronous, detail="OutOfMemoryError private-value-sentinel")
            with self.assertRaisesRegex(StackError, "unrelated_incompatible_restore_failure"):
                detection.qualify_incompatible_restore(
                    runtime, {"external_path": "file:///checkpoint"}
                )
        runtime, _ = self.runtime(True, created=["a" * 32, "b" * 32, "c" * 32])
        with self.assertRaisesRegex(StackError, "ambiguous_incompatible_restore_job"):
            detection.qualify_incompatible_restore(runtime, {"external_path": "file:///checkpoint"})

    def test_no_new_job_and_daemon_errors_are_not_a_pass(self):
        runtime, _ = self.runtime(True, created=["a" * 32])
        with (
            patch.object(detection.time, "monotonic", side_effect=[0, 1, 11]),
            patch.object(detection.time, "sleep"),
        ):
            with self.assertRaisesRegex(StackError, "missing_incompatible_restore_job"):
                detection.qualify_incompatible_restore(
                    runtime, {"external_path": "file:///checkpoint"}
                )
        runtime, _ = self.runtime(True)
        runtime.stack.exec.side_effect = StackError("docker_daemon_api_failure")
        with self.assertRaisesRegex(StackError, "docker_daemon_api_failure"):
            detection.qualify_incompatible_restore(runtime, {"external_path": "file:///checkpoint"})
        runtime.stack.exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
