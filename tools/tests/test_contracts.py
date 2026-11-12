"""Contract acceptance cases use synthetic evidence and independent identity vectors."""

import copy
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_contracts import CONTRACTS, ContractValidator, load_json
from contract_identity import event_id, identity_hash, record_id


class ContractTests(unittest.TestCase):
    validator: ContractValidator

    @classmethod
    def setUpClass(cls):
        cls.validator = ContractValidator()

    def setUp(self):
        folder = CONTRACTS / "examples"
        self.raw = load_json(folder / "windows-security-4688.raw.json")
        self.event = load_json(folder / "windows-security-4688.event.json")
        self.profile = load_json(folder / "windows-security-4688.source.json")

    def errors(self, value, kind="normalized-event", profile=None):
        return self.validator.validate(kind, value, source_contract=profile or self.profile)

    def test_examples_and_quality_outcomes(self):
        folder = CONTRACTS / "examples"
        for entry in load_json(folder / "index.json"):
            value = load_json(folder / entry["path"])
            profile = None
            if entry["kind"] == "normalized-event":
                profile = load_json(
                    folder / (value["detectbridge"]["source_contract"]["id"] + ".source.json")
                )
            with self.subTest(path=entry["path"]):
                self.assertFalse(self.errors(value, entry["kind"], profile))

    def test_independent_identity_vectors(self):
        vectors = load_json(CONTRACTS / "identity-vectors.json")
        for vector in vectors:
            self.assertEqual(
                identity_hash(json.loads(vector["canonical_utf8"])), vector["expected_id"]
            )
        self.assertEqual(
            record_id(
                {"namespace": "test", "instance": "host-a"}, {"kind": "native", "value": "record-1"}
            ),
            vectors[0]["expected_id"],
        )
        self.assertEqual(
            record_id(
                {"namespace": "test", "instance": "host-a"},
                {"kind": "dataset", "artifact_sha256": "a" * 64, "position": 0},
            ),
            vectors[1]["expected_id"],
        )
        self.assertEqual(
            event_id(
                {"namespace": "test", "instance": "host-a"},
                ["sha256:" + "b" * 64, "sha256:" + "a" * 64],
            ),
            vectors[3]["expected_id"],
        )

    def test_positions_runs_and_versions(self):
        cursor = copy.deepcopy(self.raw["cursor"])
        cursor["position"] += 1
        self.assertNotEqual(record_id(self.raw["source"], cursor), self.raw["record_id"])
        self.assertNotEqual(self.event["event"]["code"], self.event["event"]["id"])
        before = self.event["event"]["id"]
        self.event["detectbridge"]["run_id"] = "00000000-0000-4000-8000-000000000099"
        self.event["detectbridge"]["processing"]["mapping"] = "new-mapping/2.0.0"
        self.event["detectbridge"]["time"]["received"] = "2030-01-01T00:00:00Z"
        self.assertFalse(self.errors(self.event))
        self.assertEqual(self.event["event"]["id"], before)

    def test_identity_rejects_floating_and_boolean_positions(self):
        for value in (1.0, True, -1):
            self.raw["cursor"]["position"] = value
            self.assertTrue(self.errors(self.raw, "raw-record"))
        for parts in ([1.0], [True], [{"key": "value"}]):
            with self.assertRaises(ValueError):
                identity_hash(parts)

    def test_identity_tampering_and_duplicate_membership(self):
        self.raw["record_id"] = "sha256:" + "0" * 64
        self.assertTrue(self.errors(self.raw, "raw-record"))
        self.event["event"]["id"] = "sha256:" + "0" * 64
        self.assertTrue(self.errors(self.event))
        self.event["detectbridge"]["evidence"] *= 2
        self.assertTrue(self.errors(self.event))

    def test_inline_and_reference_evidence(self):
        evidence = self.raw["evidence"]
        evidence["reference"] = {
            "uri": "urn:sha256:" + evidence["sha256"],
            "object_sha256": evidence["sha256"],
        }
        self.assertTrue(self.errors(self.raw, "raw-record"))
        del evidence["inline"]
        self.assertFalse(self.errors(self.raw, "raw-record"))
        evidence["reference"]["object_sha256"] = "0" * 64
        self.assertTrue(self.errors(self.raw, "raw-record"))
        evidence["reference"]["object_sha256"] = evidence["sha256"]
        for uri in (
            "https://user:password@example.invalid/object",
            "https://example.invalid/object?token=private",
            "https://example.invalid/object#secret",
        ):
            evidence["reference"]["uri"] = uri
            self.assertTrue(self.errors(self.raw, "raw-record"))

    def test_checksums_and_encoding(self):
        self.raw["evidence"]["sha256"] = "0" * 64
        self.assertTrue(self.errors(self.raw, "raw-record"))
        self.raw["evidence"]["sha256"] = "invalid"
        self.assertTrue(self.errors(self.raw, "raw-record"))
        self.raw["evidence"].update(sha256="0" * 64, encoding="base64", inline="not-base64!")
        self.assertTrue(self.errors(self.raw, "raw-record"))

    def test_required_types_versions_categories_and_extensions(self):
        mutations = [
            lambda e: e.pop("ecs"),
            lambda e: e["process"].update(pid="100"),
            lambda e: e["process"].update(pid=100.0),
            lambda e: e["process"].update(pid=2**63),
            lambda e: e["process"].update(pid=None),
            lambda e: e.update(unknown="value"),
            lambda e: e["detectbridge"].update(contract_version="1.1.0"),
            lambda e: e["ecs"].update(version="8.0.0"),
            lambda e: e["detectbridge"].update(run_id="not-a-uuid"),
            lambda e: e["event"].update(category=["unknown"]),
            lambda e: e["event"].update(category="process"),
            lambda e: e["detectbridge"].update(extensions={"unqualified": {}}),
        ]
        for mutate in mutations:
            value = copy.deepcopy(self.event)
            mutate(value)
            self.assertTrue(self.errors(value))
        self.event["detectbridge"]["extensions"] = {"example.context": {"optional": None}}
        self.event["source_fields"]["vendor.optional"] = None
        self.assertFalse(self.errors(self.event))

    def test_missing_fields_are_not_blanket_rule_failures(self):
        self.event["process"].pop("args")
        self.event["detectbridge"]["quality"]["diagnostics"] = [
            {"code": "legitimately_absent", "field": "/process/command_line"}
        ]
        self.assertFalse(self.errors(self.event))
        self.event["detectbridge"]["quality"]["diagnostics"] = [
            {"code": "extraction_failed", "field": "/process/command_line"}
        ]
        self.assertTrue(self.errors(self.event))
        self.event["detectbridge"]["quality"].update(
            integrity="insufficient", eligibility="skipped"
        )
        self.assertFalse(self.errors(self.event))
        self.event["host"].pop("id")
        self.assertFalse(self.errors(self.event))  # skipped evidence remains representable
        self.event["detectbridge"]["quality"].update(
            integrity="sufficient", eligibility="eligible", diagnostics=[]
        )
        self.assertTrue(self.errors(self.event))

    def test_source_contract_and_classification(self):
        self.event["detectbridge"]["source_contract"]["id"] = "unknown"
        self.assertTrue(self.errors(self.event))
        self.event["detectbridge"]["source_contract"]["id"] = self.profile["id"]
        self.event["event"]["category"] = ["authentication"]
        self.assertTrue(self.errors(self.event))
        self.profile["quality_policy"]["warning_codes"].append("extraction_failed")
        self.assertTrue(self.errors(self.profile, "source-contract"))

    def test_timestamps_preserve_precision_and_allow_skew(self):
        self.event["event"]["ingested"] = "2000-01-01T00:00:00Z"
        self.assertFalse(self.errors(self.event))
        self.assertTrue(self.event["@timestamp"].endswith("123456789Z"))
        for invalid in ("2026-02-30T00:00:00Z", "2026-11-12T00:00:00", "2026-11-12T00:00:00+00:00"):
            self.event["@timestamp"] = invalid
            self.assertTrue(self.errors(self.event))

    def test_fallback_consistency(self):
        self.event = load_json(CONTRACTS / "examples/windows-security-4688.missing.json")
        self.assertFalse(self.errors(self.event))
        self.event["@timestamp"] = "2026-11-12T12:00:09Z"
        self.assertTrue(self.errors(self.event))
        self.event["@timestamp"] = self.event["detectbridge"]["time"]["first_observed"]
        self.event["detectbridge"]["time"]["quality"] = "unparseable"
        self.assertTrue(self.errors(self.event))

    def test_diagnostics_do_not_echo_values(self):
        self.event["process"]["pid"] = "SENSITIVE-PAYLOAD"
        errors = self.errors(self.event)
        self.assertTrue(errors)
        self.assertNotIn("SENSITIVE-PAYLOAD", repr(errors))
        self.assertEqual(errors[0].pointer, "/process/pid")

    def test_cli_errors_are_value_free(self):
        self.event["process"]["pid"] = "SENSITIVE-PAYLOAD"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text(json.dumps(self.event))
            result = subprocess.run(
                [
                    sys.executable,
                    str(CONTRACTS.parents[1] / "tools/check_contracts.py"),
                    "--kind",
                    "normalized-event",
                    "--document",
                    str(path),
                    "--source-contract",
                    str(CONTRACTS / "examples/windows-security-4688.source.json"),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("SENSITIVE-PAYLOAD", result.stdout + result.stderr)
            diagnostic = json.loads(result.stdout.strip())
            self.assertEqual(diagnostic["category"], "schema_type")
            self.assertEqual(diagnostic["pointer"], "/process/pid")

    def test_remote_unknown_and_broken_refs_fail_without_network(self):
        for uri in ("https://example.invalid/schema", "urn:unknown:schema", "#/$defs/missing"):
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                for source in CONTRACTS.glob("*.schema.json"):
                    (directory / source.name).write_bytes(source.read_bytes())
                path = directory / "raw-record.schema.json"
                value = load_json(path)
                value["properties"]["unused"] = {"$ref": uri}
                path.write_text(json.dumps(value))
                with patch.object(
                    socket, "create_connection", side_effect=AssertionError("network forbidden")
                ) as network:
                    with self.assertRaises(Exception):
                        ContractValidator(directory)
                    network.assert_not_called()
