"""Fail-closed integration gating and independent transport-oracle regressions."""

import base64
import copy
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_gate import CONDITIONAL, gate_passes
from check_integration import check
from classify_changes import needs_integration
from integration import INPUT, TOPICS, Integration
from integration_cases import digest, encoded
from integration_oracle import Oracle, identity
from integration_verify import exception_classes
from linux_assembly_verify import transport_id


class IntegrationTests(unittest.TestCase):
    def test_failure_log_retains_only_bounded_exception_class_names(self):
        detail = {
            "root-exception": "org.apache.flink.FlinkException: private-body-sentinel\n"
            "Caused by: java.util.concurrent.TimeoutException: sensitive source"
        }
        self.assertEqual(
            ["java.util.concurrent.TimeoutException", "org.apache.flink.FlinkException"],
            exception_classes(detail),
        )
        self.assertNotIn("private-body-sentinel", str(exception_classes(detail)))
        self.assertLessEqual(
            len(
                exception_classes(
                    {"root": " ".join(f"example.Failure{i}Exception" for i in range(100))}
                )
            ),
            64,
        )

    def test_real_contracts_and_project_isolation(self):
        check()
        self.assertEqual(8, len(TOPICS))
        for project in ("detectbridge-dev", "detectbridge-p12-test", "detectbridge-p09-test"):
            with self.assertRaises(Exception):
                Integration(project)
        self.assertIn("integration-runtime", str(Integration("detectbridge-p13-test").folder))

    def test_shared_paths_select_actual_integration_and_gate_fails_closed(self):
        for path in (
            "packages/integration-job/src/main/java/IntegrationJob.java",
            "contracts/integration-runtime/v1/integration-state.schema.json",
            "packages/windows-adapters/src/main/java/WindowsAdapter.java",
            "packages/linux-adapters/src/main/java/Assembler.java",
            "packages/detection-evaluator/src/main/java/Evaluator.java",
            "contracts/integration/v1.1/tagged-event.schema.json",
            "deploy/local/integration.Dockerfile",
            "tools/integration_oracle.py",
        ):
            self.assertTrue(needs_integration([path]), path)
        self.assertFalse(needs_integration(["docs/p13b-design.md"]))
        needs: dict[str, Any] = {
            "classify-changes": dict(
                result="success", outputs={field: "false" for field in CONDITIONAL.values()}
            ),
            "repository-hygiene": dict(result="success"),
            "secret-scan": dict(result="success"),
        }
        needs.update({job: dict(result="skipped") for job in CONDITIONAL})
        needs["classify-changes"]["outputs"]["integration"] = "true"
        for state in ("failure", "cancelled", "skipped", None):
            needs["integration-verification"]["result"] = state
            self.assertFalse(gate_passes(needs))
        needs["integration-verification"]["result"] = "success"
        self.assertTrue(gate_passes(needs))
        del needs["classify-changes"]["outputs"]["integration"]
        self.assertFalse(gate_passes(needs))

    def test_semantic_identity_uses_canonical_nested_metadata(self):
        import json

        vectors = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "contracts/integration/v1/fixtures/identity-vectors.json"
            ).read_text()
        )
        for vector in vectors:
            self.assertEqual(vector["expected"], identity(vector["preimage"]))

    def test_literal_receipt_requires_original_input_location_hash_key_and_header(self):
        binding = "a" * 64
        config = dict(broker=dict(cluster_id="synthetic", topics={INPUT: dict(id="input-id")}))
        oracle = Oracle(config, binding, {})
        row = dict(
            version="1.0.0",
            kind="run_end",
            run_id="00000000-0000-4000-8000-000000000001",
            control_id="00000000-0000-4000-8000-000000000002",
            provenance=["original synthetic test"],
        )
        sha = digest(row)
        oracle.register([row], [dict(offset=0, partition=0, value_sha256=sha)])
        location = dict(
            cluster_id="synthetic",
            topic_id="input-id",
            topic=INPUT,
            partition=0,
            offset=0,
            value_sha256=sha,
        )
        document = dict(
            version="1.0.0",
            kind="input_receipt",
            action="run_end",
            input=location,
            id=transport_id(binding, location, "receipt"),
        )
        wire: dict[str, Any] = dict(
            key=base64.b64encode(document["id"].encode()).decode(),
            value=base64.b64encode(encoded(document)).decode(),
            headers={
                "detectbridge.runtime.binding": binding,
                "detectbridge.intent.kind": "receipt",
                "detectbridge.intent.sequence": "0",
            },
        )
        self.assertTrue(oracle.check([("receipt", wire, document)]))
        for mutation in ("input", "key", "header"):
            changed = copy.deepcopy(document)
            bad = copy.deepcopy(wire)
            if mutation == "input":
                changed["input"]["value_sha256"] = "b" * 64
            if mutation == "key":
                bad["key"] = base64.b64encode(b"unrelated").decode()
            if mutation == "header":
                bad["headers"]["detectbridge.runtime.binding"] = "b" * 64
            with self.assertRaises(Exception):
                oracle.check([("receipt", bad, changed)])


if __name__ == "__main__":
    unittest.main()
