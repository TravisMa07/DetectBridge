"""Independent accounting rejects false scope, location and recovery duplicates."""

import base64
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linux_assembly_cases import cases, encoded
from linux_assembly_verify import Oracle
from stack import StackError


class AssemblyOracleTests(unittest.TestCase):
    def oracle(self):
        return Oracle(
            dict(
                broker=dict(
                    cluster_id="synthetic",
                    topics={"detectbridge.assembly.input.v1": dict(id="input-id")},
                )
            ),
            "a" * 64,
        )

    def wire(self, kind, doc):
        key = doc["manifest_id"] if kind == "manifest" else doc["id"]
        wire = dict(
            key=base64.b64encode(key.encode()).decode(),
            value=base64.b64encode(encoded(doc)).decode(),
            headers={
                "detectbridge.runtime.binding": "a" * 64,
                "detectbridge.intent.kind": kind,
                "detectbridge.intent.sequence": "0",
            },
        )
        return kind, wire, doc

    def test_manifest_scope_comes_from_its_versioned_key_not_a_top_level_run(self):
        oracle = self.oracle()
        doc = oracle.group(cases()["complete"][:5], "timeout")
        self.assertNotIn("run_id", doc)
        self.assertTrue(oracle.check([self.wire("manifest", doc)], complete=False))
        changed = copy.deepcopy(doc)
        changed["key"]["run_id"] = "00000000-0000-4000-8000-000000000099"
        with self.assertRaises(StackError):
            oracle.check([self.wire("manifest", changed)], complete=False)

    def quarantine(self, oracle):
        value = b"independent-private-sentinel"
        sha = hashlib.sha256(value).hexdigest()
        oracle.register([value], [dict(partition=0, offset=0, value_sha256=sha)])
        location = dict(
            cluster_id="synthetic",
            topic_id="input-id",
            topic="detectbridge.assembly.input.v1",
            partition=0,
            offset=0,
            value_sha256=sha,
        )
        token = ["a" * 64, "synthetic", "input-id", 0, 0, sha, "invalid_input"]
        id = (
            "sha256:"
            + hashlib.sha256(json.dumps(token, separators=(",", ":")).encode()).hexdigest()
        )
        return dict(
            version="1.0.0",
            kind="quarantine",
            id=id,
            category="invalid_assembly_input",
            input=location,
            value_size=len(value),
            value_is_null=False,
        )

    def test_exact_duplicates_are_allowed_but_location_and_same_id_body_changes_fail(self):
        oracle = self.oracle()
        doc = self.quarantine(oracle)
        row = self.wire("quarantine", doc)
        self.assertTrue(oracle.check([row, row]))
        for mutation in ("location", "body", "binding"):
            changed = copy.deepcopy(row)
            if mutation == "location":
                changed[2]["input"]["offset"] = 1
                changed = self.wire("quarantine", changed[2])
            elif mutation == "body":
                changed[2]["value_size"] += 1
                changed = self.wire("quarantine", changed[2])
            else:
                changed[1]["headers"]["detectbridge.runtime.binding"] = "b" * 64
            with self.assertRaises(StackError):
                oracle.check([row, changed])
