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

    def test_unknown_transport_versions_and_refs_rejected(self):
        with self.assertRaises(ValueError):
            require("publication", {"contract_version": "9.0.0"})
        with self.assertRaises(ValueError):
            require("unknown", {})
