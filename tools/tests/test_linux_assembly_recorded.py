"""Synthetic oracle regressions; these never require the reviewed local payload."""

import base64
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linux_assembly_cases import ROOT, cases, encoded, identity
from linux_assembly_recorded import expectations, qualify, retained_event, reviewed_rows
from linux_assembly_verify import Oracle
from stack import StackError


class RecordedAssemblyTests(unittest.TestCase):
    def event(self):
        row = cases()["auth"]
        ctx, raw = row["context"], row["raw"]
        expected = dict(
            disposition="normalized",
            sha256=raw["evidence"]["sha256"],
            outcome="success",
            user="alice",
            source_ip="192.0.2.1",
            source_port=2222,
            timestamp="2026-01-01T00:00:00Z",
        )
        oracle = Oracle({}, "a" * 64)
        expectations(oracle, [row], dict(expectations=[expected]))
        doc = json.loads(
            (
                ROOT
                / "packages/linux-adapters/contracts/openssh-authentication-p12a.contract-example.event.json"
            ).read_bytes()
        )
        doc["@timestamp"] = expected["timestamp"]
        doc["event"]["created"] = ctx["first_observed"]
        doc["event"]["id"] = identity(
            [raw["source"]["namespace"], raw["source"]["instance"], [raw["record_id"]]]
        )
        doc["host"]["id"] = ctx["host_binding"]["host_id"]
        doc["user"]["name"] = "alice"
        doc["source"] = dict(ip="192.0.2.1", port=2222)
        doc["source_fields"] = dict(rfc5424=dict(timestamp=expected["timestamp"]))
        db = doc["detectbridge"]
        db["source"] = raw["source"]
        db["run_id"] = ctx["run_id"]
        db["evidence"] = [dict(record_id=raw["record_id"], evidence=raw["evidence"])]
        db["time"] = dict(
            basis="source",
            quality="valid",
            first_observed=ctx["first_observed"],
            source_value=expected["timestamp"],
            source_utc=expected["timestamp"],
        )
        db["processing"] = dict(
            parser="openssh-password/1.0.0",
            mapping=ctx["mapping_profile"]["id"] + "/1.0.0",
            normalizer="linux-p12a/1.0.0",
        )
        return oracle, row, expected, doc

    def wire(self, doc):
        return (
            "event",
            dict(
                key=base64.b64encode(doc["event"]["id"].encode()).decode(),
                value=base64.b64encode(encoded(doc)).decode(),
                headers={
                    "detectbridge.runtime.binding": "a" * 64,
                    "detectbridge.intent.kind": "event",
                    "detectbridge.intent.sequence": "0",
                },
            ),
            doc,
        )

    def test_same_count_changed_semantics_or_scope_fail(self):
        oracle, _, _, doc = self.event()
        self.assertTrue(oracle.check([self.wire(doc)]))
        for path, value in (
            (("user", "name"), "someone-else"),
            (("source", "port"), 2223),
            (("event", "outcome"), "failure"),
            (("detectbridge", "run_id"), "00000000-0000-4000-8000-000000000099"),
            (("detectbridge", "time", "source_value"), "2026-01-01T00:00:01Z"),
            (("detectbridge", "processing", "parser"), "fixture-only/1.0.0"),
        ):
            changed = copy.deepcopy(doc)
            target = changed
            for name in path[:-1]:
                target = target[name]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(StackError):
                oracle.check([self.wire(changed)])

    def test_recorded_expectations_do_not_change_synthetic_auth_defaults(self):
        oracle, row, expected, doc = self.event()
        expected["user"] = "bridgeauth"
        oracle.auth(row, expectation=expected)
        with self.assertRaises(StackError):
            oracle.check([self.wire(doc)])
        oracle.auth(row)
        self.assertTrue(oracle.check([self.wire(doc)]))

    def test_retained_checkpoint_intent_must_bind_original_recording_event(self):
        oracle, row, _, doc = self.event()
        intent = dict(
            kind="event",
            key=doc["event"]["id"],
            run_id=row["context"]["run_id"],
            members=[
                dict(
                    record_id=row["raw"]["record_id"],
                    evidence_sha256=row["raw"]["evidence"]["sha256"],
                )
            ],
        )
        self.assertEqual(retained_event(dict(outbox=[intent]), oracle), intent)
        for changed in (dict(intent, key="sha256:" + "0" * 64), dict(intent, members=[])):
            with self.assertRaises(StackError):
                retained_event(dict(outbox=[changed]), oracle)
        with self.assertRaises(StackError):
            retained_event(dict(outbox=[]), oracle)

    def test_catalog_mismatch_or_unknown_disposition_fails_before_injection(self):
        oracle, row, expected, _ = self.event()
        for changes in (dict(sha256="0" * 64), dict(disposition="invented")):
            with self.assertRaises(StackError):
                expectations(oracle, [row], dict(expectations=[dict(expected, **changes)]))
        with self.assertRaises(StackError):
            expectations(oracle, [], dict(expectations=[expected]))

    def test_missing_originals_fail_before_runtime_initialization(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("linux_assembly_recorded.Assembly") as runtime,
        ):
            with self.assertRaises(FileNotFoundError):
                qualify(Path(directory))
            runtime.assert_not_called()

    def test_changed_original_fails_before_envelope_preparation(self):
        from linux_assembly_recorded import recording_verifier

        verifier = recording_verifier()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "auth.rfc5424").write_bytes(b"changed")
            with patch.object(verifier, "prepare") as prepare:
                with self.assertRaises(ValueError):
                    reviewed_rows(root, root / "input.ndjson")
                prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
