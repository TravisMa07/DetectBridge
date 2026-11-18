"""Independent archive vectors, packaging boundaries and fail-closed selection."""

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive import TOPICS, Archive
from check_archive import check, require
from check_contracts import load_json
from check_gate import CONDITIONAL, gate_passes
from classify_changes import needs_archive
from integration import TOPICS as INTEGRATION_TOPICS
from stack import ROOT, StackError


class ArchiveTests(unittest.TestCase):
    def test_all_original_producer_routes_are_archived(self):
        self.assertEqual(
            TOPICS, (*INTEGRATION_TOPICS, "detectbridge.integration.writer-failures.v1")
        )

    def test_schemas_and_independent_vectors(self):
        check()

    def test_closed_wire_lossless_integer_contract(self):
        value = dict(
            version="1.0.0",
            id="sha256:" + "1" * 64,
            topic=TOPICS[0],
            topic_id="topic-A",
            partition=0,
            offset=9007199254740993,
            timestamp=-9223372036854775808,
            timestamp_type="CreateTime",
            key=None,
            value="",
            headers=[],
            dependencies=[],
            category="opaque",
        )
        require("wire", value)
        for changed in (
            dict(value, offset=1.0),
            dict(value, offset=True),
            dict(value, offset=9223372036854775808),
            dict(value, unknown=1),
            dict(value, version="2.0.0"),
        ):
            with self.subTest(value=changed):
                with self.assertRaises(ValueError):
                    require("wire", changed)

    def test_project_boundary(self):
        for name in ("detectbridge-dev", "other", "detectbridge-p14-../escape"):
            with self.assertRaises(StackError):
                Archive(name)

    def test_archive_shared_paths_and_docs_select_real_gate(self):
        for path in (
            "packages/archive-writer/src/main/java/Test.java",
            "contracts/archive/v1/wire.schema.json",
            "tools/archive.py",
            "tools/archive_verify.py",
            "tools/check_archive.py",
            "tools/tests/test_archive.py",
            "packages/transport-contracts/src/main/java/Json.java",
            "contracts/v1/common.schema.json",
            "contracts/integration-runtime/v1/integration-input.schema.json",
            "settings.gradle.kts",
            "tools/dev.py",
            ".github/workflows/hygiene.yml",
            "docs/transport-dependencies.json",
        ):
            self.assertTrue(needs_archive([path]), path)
        self.assertFalse(needs_archive(["docs/p14a-design.md"]))
        self.assertFalse(needs_archive(["tools/unrelated.py"]))

    def test_aggregate_fails_closed_and_runtime_job_is_real(self):
        needs: dict[str, Any] = {
            "classify-changes": dict(
                result="success", outputs={v: "false" for v in CONDITIONAL.values()}
            ),
            "repository-hygiene": dict(result="success"),
            "secret-scan": dict(result="success"),
        }
        needs.update({job: dict(result="skipped") for job in CONDITIONAL})
        for applicable in ("true", "false", None, "unexpected"):
            needs["classify-changes"]["outputs"]["archive"] = applicable
            for result in ("success", "failure", "skipped", "cancelled", None):
                needs["archive-verification"]["result"] = result
                self.assertEqual(
                    gate_passes(needs),
                    (applicable == "true" and result == "success")
                    or (applicable == "false" and result == "skipped"),
                )
        missing = copy.deepcopy(needs)
        del missing["archive-verification"]
        self.assertFalse(gate_passes(missing))
        workflow = load_json(ROOT / ".github/workflows/hygiene.yml")
        self.assertIn("archive-verification", workflow["jobs"]["required-checks"]["needs"])
        job = json.dumps(workflow["jobs"]["archive-verification"])
        self.assertIn("tools/archive.py verify", job)
        self.assertIn("tools/dev.py archive", job)
        artifact = workflow["jobs"]["archive-verification"]["steps"][-1]["with"]["path"]
        self.assertIn("helper-failure-*.json", artifact)
        self.assertNotIn("records.ndjson", artifact)
        self.assertNotIn("objects/", artifact)
        self.assertNotIn("admissions.json", artifact)
