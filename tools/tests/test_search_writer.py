"""Independent vectors, mode isolation and fail-closed real search-job applicability."""

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_gate import CONDITIONAL, gate_passes
from check_search_writer import compiled_schema, require
from check_writer import require as legacy_require
from classify_changes import needs_search
from search_writer import SearchWriter
from search_writer_qualification import content_hash

ROOT = Path(__file__).resolve().parents[2]


class SearchWriterTests(unittest.TestCase):
    def test_modes_and_projects_cannot_be_adopted(self):
        old = json.loads((ROOT / "contracts/writer/v1/examples/configuration.json").read_text())
        legacy_require("configuration", old)
        with self.assertRaises(ValueError):
            require("configuration", old)
        for project in ("detectbridge-dev", "detectbridge-p12-test", "detectbridge-p09-test"):
            with self.assertRaises(Exception):
                SearchWriter(project)
        for kind in ("configuration", "projection", "failure"):
            compiled_schema(
                kind, (ROOT / f"contracts/search-writer/v1/{kind}.schema.json").read_text()
            )

    def test_literal_content_vector_excludes_physical_copy_but_detects_decisions(self):
        vector = json.loads(
            (ROOT / "contracts/search-writer/v1/fixtures/expectations.json").read_text()
        )["content_vector"]
        value = copy.deepcopy(vector["semantic_body"])
        value.update(
            input_sha256="b" * 64,
            first_input={"offset": 99},
            evidence_source={"topic_id": "physical"},
        )
        value["manifest"].update(manifest_id="physical-link", sha256="c" * 64)
        self.assertEqual(vector["sha256"], content_hash(value))
        value["counts"]["matched"] = 2
        self.assertNotEqual(vector["sha256"], content_hash(value))

    def test_search_gate_cannot_succeed_on_skipped_failed_or_missing_results(self):
        for path in (
            "packages/integration-writer/src/main/java/Projection.java",
            "contracts/search-writer/v1/projection.schema.json",
            "tools/search_writer_qualification.py",
            "packages/windows-adapters/src/main/java/WindowsAdapter.java",
            "packages/integration-job/src/main/java/Machine.java",
        ):
            self.assertTrue(needs_search([path]), path)
        self.assertFalse(needs_search(["docs/p13c-design.md"]))
        needs: dict[str, Any] = {
            "classify-changes": {
                "result": "success",
                "outputs": {name: "false" for name in CONDITIONAL.values()},
            },
            "repository-hygiene": {"result": "success"},
            "secret-scan": {"result": "success"},
        }
        needs.update({job: {"result": "skipped"} for job in CONDITIONAL})
        needs["classify-changes"]["outputs"]["search"] = "true"
        for state in ("failure", "cancelled", "skipped", None):
            needs["search-verification"]["result"] = state
            self.assertFalse(gate_passes(needs))
        needs["search-verification"]["result"] = "success"
        self.assertTrue(gate_passes(needs))
        del needs["classify-changes"]["outputs"]["search"]
        self.assertFalse(gate_passes(needs))


if __name__ == "__main__":
    unittest.main()
