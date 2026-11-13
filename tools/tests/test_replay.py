"""Replay recovery uses synthetic bytes and fake clocks, never public acquisition."""

import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import replay
from check_contracts import ContractValidator, load_json
from check_datasets import load_catalog
from check_replay import ReplayValidator
from replay_time import timestamp_ns, timestamp_text


class Crash(BaseException):
    pass


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.cache, self.runs, self.captures = root / "data", root / "runs", root / "captures"
        catalog = load_catalog()
        self.ids = ["linux-audit-whoami", "windows-security-4688"]
        self.catalog = {ident: copy.deepcopy(catalog[ident]) for ident in self.ids}
        for ident in self.ids:
            manifest = self.catalog[ident]
            body = b"one\r\n\nlast" if ident.startswith("linux") else b"<Event/>\n"
            self.store(manifest["payload"], body)
            manifest["framing"]["record_count"] = len(body.splitlines())
            for resource in manifest["provenance"]:
                if resource["role"] == "lfs_pointer":
                    payload = manifest["payload"]
                    data = f"version https://git-lfs.github.com/spec/v1\noid sha256:{payload['sha256']}\nsize {payload['size_bytes']}\n".encode()
                else:
                    data = resource["role"].encode()
                self.store(resource, data)
        self.validator = ReplayValidator()

    def store(self, resource, body):
        resource["sha256"] = hashlib.sha256(body).hexdigest()
        resource["size_bytes"] = len(body)
        path = replay.object_path(self.cache, resource)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def tearDown(self):
        self.temp.cleanup()

    def start(self, ids=None, **kwargs):
        return replay.start(
            self.ids if ids is None else ids,
            catalog=self.catalog,
            runs=self.runs,
            captures=self.captures,
            data_cache=self.cache,
            rate=kwargs.pop("rate", None),
            **kwargs,
        )

    def execute(self, ident, **kwargs):
        return replay.execute(ident, self.runs, self.cache, **kwargs)

    def rows(self, ident):
        result: list[dict] = []
        for path in sorted((self.runs / ident / "segments").glob("*/records.ndjson")):
            result.extend(json.loads(line) for line in path.read_text().splitlines())
        return result

    def index(self, datasets):
        value: dict[str, Any] = {"contract_version": "1.0.0", "datasets": []}
        for ident, timestamps in datasets.items():
            value["datasets"].append(
                {
                    "dataset_id": ident,
                    "artifact_sha256": self.catalog[ident]["payload"]["sha256"],
                    "framing": "lf-byte-records-v1",
                    "timestamps": [{"position": p, "timestamp": t} for p, t in timestamps],
                }
            )
        path = Path(self.temp.name) / "timing.json"
        path.write_text(json.dumps(value))
        return path

    def test_byte_ranges_identity_and_end_markers(self):
        first = self.start()
        second = self.start()
        a, b = self.rows(first["run_id"]), self.rows(second["run_id"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual([r["sequence"] for r in a], list(range(7)))
        self.assertEqual(
            [r["type"] for r in a],
            ["record", "record", "record", "dataset_end", "record", "dataset_end", "run_end"],
        )
        self.assertEqual([r.get("record") for r in a], [r.get("record") for r in b])
        raw_validator = ContractValidator()
        for row in a:
            self.validator.require("envelope", row)
            if row["type"] != "record":
                continue
            record = row["record"]
            self.assertFalse(raw_validator.validate("raw-record", record))
            payload = self.catalog[row["dataset_id"]]["payload"]
            original = replay.object_path(self.cache, payload).read_bytes()
            span = record["evidence"]["reference"]["byte_range"]
            raw = original[span["offset"] : span["offset"] + span["length"]]
            self.assertEqual(record["evidence"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(
            [r["record"]["evidence"]["reference"]["byte_range"]["length"] for r in a[:3]], [5, 1, 4]
        )
        before = (self.runs / first["run_id"] / "checkpoint.json").read_bytes()
        self.assertEqual(self.execute(first["run_id"])["status"], "completed")
        self.assertEqual(before, (self.runs / first["run_id"] / "checkpoint.json").read_bytes())

    def test_explicit_order(self):
        run = self.start(list(reversed(self.ids)))
        self.assertEqual(self.rows(run["run_id"])[0]["dataset_id"], self.ids[1])

    def test_exact_timing_and_shift(self):
        original = "2020-01-01T00:00:00.123456789Z"
        index = self.index(
            {
                self.ids[0]: [
                    (0, original),
                    (1, "2020-01-01T00:00:00.123456790Z"),
                    (2, "2020-01-01T00:00:01Z"),
                ],
                self.ids[1]: [(0, "2020-01-01T00:00:00.000000001Z")],
            }
        )
        preserve = self.start(timing_path=index)
        shifted = self.start(timing_path=index, mode="shift", anchor="2026-01-01T00:00:00Z")
        a = [r for r in self.rows(preserve["run_id"]) if r["type"] == "record"]
        b = [r for r in self.rows(shifted["run_id"]) if r["type"] == "record"]
        self.assertEqual(a[0]["timing"]["effective_time"], original)
        deltas = {
            timestamp_ns(y["timing"]["effective_time"]) - timestamp_ns(x["timing"]["original_time"])
            for x, y in zip(a, b)
        }
        self.assertEqual(len(deltas), 1)
        self.assertEqual(b[-1]["timing"]["effective_time"], "2026-01-01T00:00:00.000000000Z")
        self.assertEqual([r["record"] for r in a], [r["record"] for r in b])
        self.assertEqual(
            (self.runs / shifted["run_id"] / "timing-index.json").read_bytes(), index.read_bytes()
        )
        self.assertEqual(self.execute(shifted["run_id"], inspect=True)["status"], "completed")

    def test_sparse_fallback_and_timestamp_validation(self):
        index = self.index({self.ids[0]: [(0, "2020-01-01T00:00:00Z")]})
        run = self.start(timing_path=index)
        rows = self.rows(run["run_id"])
        self.assertEqual(rows[0]["timing"]["basis"], "timing_index")
        self.assertEqual(rows[1]["timing"]["basis"], "first_observed")
        self.assertEqual(rows[1]["timing"]["original_time"], rows[1]["record"]["first_observed"])
        for value in (
            "2026-02-30T00:00:00Z",
            "2020-01-01T00:00:00+00:00",
            "2020-01-01T00:00:00.1234567890Z",
            "2020-01-01T00:00:60Z",
        ):
            with self.assertRaises(ValueError):
                timestamp_ns(value)
        for nanos in (-1, 0, 1, 123456789, timestamp_ns("9999-12-31T23:59:59.999999999Z")):
            self.assertEqual(timestamp_ns(timestamp_text(nanos)), nanos)

    def test_timing_index_rejections(self):
        path = self.index({self.ids[0]: [(0, "2020-01-01T00:00:00Z")]})
        base = load_json(path)
        for mutate in (
            lambda v: v["datasets"][0]["timestamps"].append(v["datasets"][0]["timestamps"][0]),
            lambda v: v["datasets"][0].update(dataset_id="unknown"),
            lambda v: v["datasets"][0].update(artifact_sha256="0" * 64),
            lambda v: v["datasets"][0].update(framing="unknown"),
            lambda v: v["datasets"][0]["timestamps"][0].update(position=999),
        ):
            value = copy.deepcopy(base)
            mutate(value)
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                self.start(timing_path=path)

    def test_rate_and_limits_and_input_failures(self):
        for rate in (0, -1, math.inf, math.nan, 10001):
            with self.assertRaises(ValueError):
                self.start(rate=rate)
        for selection in ([], self.ids * 2, ["unknown"]):
            with self.assertRaises(ValueError):
                self.start(selection)
        for name, value in [("MAX_RECORDS", 1), ("MAX_RECORD", 1), ("MAX_OUTPUT", 1)]:
            with patch.object(replay, name, value):
                with self.assertRaises(ValueError):
                    self.start()
        path = replay.object_path(self.cache, self.catalog[self.ids[0]]["payload"])
        path.write_bytes(b"corrupt")
        with self.assertRaises(Exception):
            self.start()
        path.unlink()
        with self.assertRaises(Exception):
            self.start()

    def test_resume_across_publication_windows(self):
        for stage in ("before_segment_publish", "after_segment_publish", "after_checkpoint"):
            run_id = str(uuid.uuid4())

            def crash(point):
                if point == stage:
                    raise Crash()

            with patch.object(replay, "SEGMENT_RECORDS", 2):
                with self.assertRaises(Crash):
                    self.start(run_id=run_id, hook=crash)
                result = self.execute(run_id)
            self.assertEqual(result["status"], "completed")
            rows = self.rows(run_id)
            self.assertEqual([r["sequence"] for r in rows], list(range(7)))
            self.assertEqual(sum(r["type"] == "run_end" for r in rows), 1)
            self.assertFalse(list((self.runs / run_id / "segments").glob(".partial-*")))

    def test_interrupt_lock_and_completed_noop(self):
        run_id = str(uuid.uuid4())

        def interrupt(point):
            if point == "after_segment_publish":
                raise KeyboardInterrupt()

        with patch.object(replay, "SEGMENT_RECORDS", 2):
            result = self.start(run_id=run_id, hook=interrupt)
        self.assertEqual(result["status"], "interrupted")
        with replay.locked(self.runs / run_id / ".run.lock"):
            with self.assertRaises(ValueError):
                self.execute(run_id)
        self.assertEqual(self.execute(run_id)["status"], "completed")
        with self.assertRaises(FileExistsError):
            self.start(run_id=run_id)

    def test_corruption_and_frozen_configuration(self):
        for target in (
            "manifest.json",
            "segments/00000000/records.ndjson",
            "segments/00000000/commit.json",
            "checkpoint.json",
        ):
            result = self.start()
            folder = self.runs / result["run_id"]
            path = folder / target
            path.write_bytes(path.read_bytes() + b"corruption")
            with self.assertRaises(Exception):
                self.execute(result["run_id"])
        result = self.start()
        folder = self.runs / result["run_id"]
        checkpoint = load_json(folder / "checkpoint.json")
        checkpoint["next_sequence"] += 1
        replay.atomic_json(folder / "checkpoint.json", checkpoint)
        with self.assertRaises(ValueError):
            self.execute(result["run_id"])

    def test_pacer_does_not_catch_up(self):
        now = [0.0]
        waits = []

        def sleep(delay):
            waits.append(delay)
            now[0] += delay

        pacer = replay.Pacer(10, clock=lambda: now[0], sleep=sleep)
        pacer.wait()
        pacer.wait()
        self.assertAlmostEqual(now[0], 0.1)
        now[0] = 50
        pacer.wait()
        pacer.wait()
        self.assertAlmostEqual(now[0], 50.1)
        self.assertTrue(all(delay <= 0.1 for delay in waits))

    def test_replay_schema_versions_and_git_ignore(self):
        with self.assertRaises(ValueError):
            self.validator.require("timing-index", {"contract_version": "2.0.0", "datasets": []})
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                ".cache/replay/run/segments/00000000/records.ndjson",
                ".cache/replay-captures/example.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 2)
