"""Acknowledgment ambiguity and immutable publication state use synthetic replay."""

import base64
import json
import math
import sys
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_replay as replay_tests
import transport
from check_transport import require


class Crash(BaseException):
    pass


class Input:
    def __init__(self):
        self.lines = []
        self.closed = False

    def write(self, value):
        self.lines.append(value)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class Output:
    def __init__(self, child):
        self.child = child

    def readline(self, _):
        child = self.child
        if child.stdin.closed:
            return json.dumps({"type": "end", "count": child.count}) + "\n"
        value = json.loads(child.stdin.lines[-1])
        offset = len(child.broker)
        child.broker.append(
            {"offset": offset, "partition": 0, "key": value["key"], "value": value["value"]}
        )
        child.count += 1
        return (
            json.dumps(
                {
                    "type": "ack",
                    "sequence": value["sequence"],
                    "partition": 0,
                    "offset": offset,
                    "key_sha256": transport.sha(base64.b64decode(value["key"])),
                    "value_sha256": transport.sha(base64.b64decode(value["value"])),
                }
            )
            + "\n"
        )

    def close(self):
        pass


class Child:
    def __init__(self, broker):
        self.stdin = Input()
        self.stdout = Output(self)
        self.count = 0
        self.code = None
        self.broker = broker

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        self.code = 0
        return 0

    def terminate(self):
        self.code = -15

    def kill(self):
        self.code = -9


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.replay: Any = replay_tests.ReplayTests()
        self.replay.setUp()
        self.run_id = self.replay.start()["run_id"]
        self.root = Path(self.replay.temp.name)
        self.cache_patch = patch.object(transport, "CACHE", self.root / "transport")
        self.cache_patch.start()
        self.value = cast(
            Any,
            transport.Transport(
                "detectbridge-test-publication", data_cache=self.replay.cache, runs=self.replay.runs
            ),
        )
        self.value.folder.mkdir(parents=True)
        self.value.config = Mock(
            return_value={
                "pipeline_id": "00000000-0000-4000-8000-000000000001",
                "broker": {"cluster_id": "synthetic", "topics": {}},
                "bundle": {"bundle_sha256": "a" * 64},
            }
        )
        self.value.verify_destination = Mock(return_value={})
        self.value.process_args = Mock(return_value=["fake"])
        self.value.stack.cleanup_helpers = Mock()
        self.records: list[dict] = []
        self.value.read_records = lambda topic, start, stop: [
            r for r in self.records if start <= r["offset"] < stop
        ]
        self.process_patch = patch.object(
            transport.subprocess, "Popen", side_effect=lambda *a, **k: Child(self.records)
        )
        self.process = self.process_patch.start()

    def tearDown(self):
        self.process_patch.stop()
        self.cache_patch.stop()
        self.replay.tearDown()

    def test_completed_publication_verified_noop_and_run_isolation(self):
        result = self.value.publish(self.run_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["acknowledged"], 7)
        count = len(self.records)
        self.assertEqual(self.value.publish(self.run_id), result)
        self.assertEqual(len(self.records), count)
        second = self.replay.start()["run_id"]
        self.value.publish(second)
        self.assertEqual(len(self.records), count * 2)
        self.assertNotEqual(self.records[0]["key"], self.records[count]["key"])
        first_body = json.loads(base64.b64decode(self.records[0]["value"]))
        second_body = json.loads(base64.b64decode(self.records[count]["value"]))
        self.assertEqual(first_body["record"], second_body["record"])

    def test_ambiguous_ack_repeats_without_missing_logical_rows(self):
        def crash(stage):
            if stage == "after_broker_ack":
                raise Crash()

        with self.assertRaises(Crash):
            self.value.publish(self.run_id, hook=crash)
        self.assertEqual(self.value.publication(self.run_id)["acknowledged"], 0)
        self.value.publish(self.run_id)
        self.assertEqual(len(self.records), 8)
        sequences = [json.loads(base64.b64decode(r["value"]))["sequence"] for r in self.records]
        self.assertEqual(set(sequences), set(range(7)))
        self.assertEqual(sequences.count(0), 2)

    def test_crash_after_receipt_commit_does_not_resend(self):
        def crash(stage):
            if stage == "after_receipt_commit":
                raise Crash()

        with self.assertRaises(Crash):
            self.value.publish(self.run_id, hook=crash)
        self.assertEqual(self.value.publish(self.run_id)["status"], "completed")
        self.assertEqual(len(self.records), 7)

    def test_missing_acknowledged_input_and_changed_config_fail(self):
        self.value.publish(self.run_id)
        original = self.records[0]["value"]
        self.records[0]["value"] = base64.b64encode(b"changed").decode()
        with self.assertRaises(transport.StackError):
            self.value.publication(self.run_id)
        self.records[0]["value"] = original
        folder = self.value.publication_folder(self.run_id)
        path = folder / "configuration.json"
        value = json.loads(path.read_text())
        value["rate"] = 1
        path.write_text(json.dumps(value))
        with self.assertRaises(transport.StackError):
            self.value.publish(self.run_id)

    def test_invalid_rate_changed_destination_and_source_fail_preflight(self):
        for rate in (0, -1, math.inf, math.nan, 10001):
            with self.assertRaises(transport.StackError):
                self.value.publish(self.run_id, rate=rate)
        self.process.assert_not_called()
        self.value.publish(self.run_id)
        with self.assertRaises(transport.StackError):
            self.value.publish(self.run_id, rate=100)
        self.value.config.return_value["broker"]["cluster_id"] = "changed"
        with self.assertRaises(transport.StackError):
            self.value.publication(self.run_id)

    def test_publication_lock_and_corrupt_replay_rejected(self):
        with transport.replay.locked(self.value.folder / ".publication.lock"):
            with self.assertRaises(ValueError):
                self.value.publish(self.run_id)
        segment = next((self.replay.runs / self.run_id / "segments").glob("*/records.ndjson"))
        segment.write_bytes(segment.read_bytes() + b"tamper")
        with self.assertRaises(Exception):
            self.value.publish(self.run_id)
        self.process.assert_not_called()

    def test_quarantine_retry_limit_accepts_only_the_injected_failure(self):
        newest = {"id": 9, "external_path": "file:///state/checkpoints/" + "a" * 32 + "/chk-9"}
        # An earlier cached path can have been evicted while the job was still running.
        (self.value.folder / "checkpoint.json").write_text(json.dumps({"checkpoint": {"id": 1}}))
        self.value.rest = Mock(
            side_effect=[
                {"state": "FAILED"},
                {"root-exception": "topic_config_mismatch"},
                {"latest": {"completed": newest}},
            ]
        )
        self.assertEqual(self.value.wait_quarantine_retry_limit("a" * 32), newest)
        self.value.rest = Mock(
            side_effect=[{"state": "FAILED"}, {"root-exception": "unrelated_failure"}]
        )
        with self.assertRaisesRegex(transport.StackError, "unrelated_failure"):
            self.value.wait_quarantine_retry_limit("a" * 32)
        self.value.rest = Mock(return_value={"state": "CANCELED"})
        with self.assertRaisesRegex(transport.StackError, "unexpected_termination"):
            self.value.wait_quarantine_retry_limit("a" * 32)

    def test_unknown_transport_versions_and_refs_rejected(self):
        with self.assertRaises(ValueError):
            require("publication", {"contract_version": "9.0.0"})
        with self.assertRaises(ValueError):
            require("unknown", {})

    def test_payload_ipc_is_unlogged_and_helpers_have_explicit_lifetime(self):
        args = transport.Transport.process_args(
            self.value,
            "read",
            transport.INPUT,
            0,
            1,
            config={"bundle": {"image_id": "sha256:" + "a" * 64}},
        )
        self.assertEqual(args[args.index("--log-driver") + 1], "none")
        self.assertNotIn("--rm", args)
        self.assertNotIn("-i", args)
        publisher = transport.Transport.process_args(
            self.value,
            "publish",
            transport.INPUT,
            config={"bundle": {"image_id": "sha256:" + "a" * 64}},
        )
        self.assertIn("-i", publisher)
        logger = (transport.DEPLOY / "transport-log4j.properties").read_text()
        self.assertIn("alwaysWriteExceptions = false", logger)
        self.assertNotIn("%m", logger)
        self.assertNotIn("%ex", logger)
        self.assertEqual(args[args.index("--network") + 1], self.value.project + "_internal")
        self.assertEqual(args[args.index("--user") + 1], "9999:9999")
        self.assertEqual(args[args.index("--memory") + 1], "512m")
        self.assertTrue(args[args.index("--name") + 1].startswith(self.value.project + "-helper-"))

    def test_read_helpers_retry_only_docker_setup_failures(self):
        for category in ("docker_setup_failure", "docker_daemon_api_failure"):
            self.value.helper_run = Mock(side_effect=[transport.StackError(category), "ok"])
            with patch.object(transport.time, "sleep"):
                self.assertEqual(transport.Transport.private_read(self.value, [], 10), "ok")
            self.assertEqual(self.value.helper_run.call_count, 2)
        self.value.helper_run = Mock(side_effect=transport.StackError("broker_operation_failed"))
        with self.assertRaisesRegex(transport.StackError, "broker_operation_failed"):
            transport.Transport.private_read(self.value, [], 10)
        self.value.helper_run.assert_called_once()

    def test_versioned_job_history_rejects_bundle_mismatch(self):
        path = self.value.folder / "jobs.json"
        job = {
            "job_id": "a" * 32,
            "bundle_sha256": "b" * 64,
            "restored_from": None,
            "from_beginning": False,
        }
        path.write_text(json.dumps({"contract_version": "1.0.0", "jobs": [job]}))
        with self.assertRaises(transport.StackError):
            self.value.jobs()
        job["bundle_sha256"] = "a" * 64
        path.write_text(json.dumps({"contract_version": "1.0.0", "jobs": [job]}))
        self.assertEqual(self.value.jobs()["jobs"], [job])
        path.write_text(json.dumps({"contract_version": "9.0.0", "jobs": [job]}))
        with self.assertRaises(ValueError):
            self.value.jobs()

    def test_transport_classification_and_gate_fail_closed(self):
        from check_gate import gate_passes
        from classify_changes import needs_transport

        self.assertFalse(needs_transport(["docs/transport.md", "README.md"]))
        for path in (
            "packages/transport-job/src/main/java/RelayJob.java",
            "contracts/v1/common.schema.json",
            "contracts/replay/v1/envelope.schema.json",
            "gradle/libs.versions.toml",
            "settings-gradle.lockfile",
            "gradlew",
            "tools/datasets.py",
            "tools/check_datasets.py",
            "catalog/datasets/example.json",
            "tools/transport.py",
            ".github/workflows/hygiene.yml",
        ):
            self.assertTrue(needs_transport([path]), path)
        for applicable in ("true", "false"):
            for result in ("success", "failure", "cancelled", "skipped", None):
                needs = {
                    "classify-changes": {
                        "result": "success",
                        "outputs": {
                            "toolchains": "false",
                            "stack": "false",
                            "transport": applicable,
                        },
                    },
                    "repository-hygiene": {"result": "success"},
                    "secret-scan": {"result": "success"},
                    "toolchain-verification": {"result": "skipped"},
                    "local-stack-verification": {"result": "skipped"},
                    "transport-verification": {"result": result},
                }
                self.assertEqual(
                    gate_passes(needs), result == ("success" if applicable == "true" else "skipped")
                )

    def test_restore_accepts_flink_file_uri_and_rejects_foreign_state(self):
        job = {
            "job_id": "a" * 32,
            "bundle_sha256": "a" * 64,
            "restored_from": None,
            "from_beginning": False,
        }
        self.value.jobs = Mock(return_value={"contract_version": "1.0.0", "jobs": [job]})
        self.value.rest = Mock(return_value={"jobs": []})
        self.value.config.return_value["consumer_group"] = "synthetic-group"
        self.value.config.return_value["broker"]["topics"] = {
            topic: {"id": "synthetic-topic"} for topic in transport.TOPICS
        }
        self.value.stack.exec = Mock(
            side_effect=["", "Job has been submitted with JobID " + "b" * 32]
        )
        self.value.wait_checkpoint = Mock()
        result = self.value.start(restore="file:/state/checkpoints/" + "a" * 32 + "/chk-1")
        self.assertEqual(
            result["restored_from"], "file:///state/checkpoints/" + "a" * 32 + "/chk-1"
        )
        for path in (
            "file://foreign/state/checkpoints/" + "a" * 32 + "/chk-1",
            "file:///state/checkpoints/" + "c" * 32 + "/chk-1",
            "file:///state/checkpoints/" + "a" * 32 + "/../outside",
        ):
            with self.assertRaises(transport.StackError):
                self.value.start(restore=path)
