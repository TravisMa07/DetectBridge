"""Synthetic regressions for exact recorded-audit checkpoint and replay attribution."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linux_assembly_audit_runtime import controls, eligible_group, open_group, qualify
from linux_assembly_cases import cases, digest
from linux_assembly_verify import manifest
from stack import StackError


class RecordedAuditRuntimeTests(unittest.TestCase):
    def test_open_checkpoint_requires_exact_original_members_hashes_and_scope(self):
        rows = cases()["complete"]
        expected = manifest(rows, "timeout", [])
        members = [
            dict(
                record_id=row["raw"]["record_id"],
                evidence_sha256=row["raw"]["evidence"]["sha256"],
                raw_sha256=digest(row["raw"]),
                context_sha256=digest(row["context"]),
            )
            for row in rows
        ]
        inventory = dict(groups=[dict(key=expected["key"], members=members)])
        open_group(inventory, expected, rows)
        for mutation in ("member", "context", "scope", "missing"):
            changed = copy.deepcopy(inventory)
            if mutation == "member":
                changed["groups"][0]["members"][0]["evidence_sha256"] = "0" * 64
            elif mutation == "context":
                changed["groups"][0]["members"][0]["context_sha256"] = "0" * 64
            elif mutation == "scope":
                changed["groups"][0]["key"]["generation"] = "other-generation"
            else:
                changed["groups"][0]["members"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(StackError):
                open_group(changed, expected, rows)

    def test_exactly_one_reviewed_eligible_group_and_explicit_bound_control(self):
        group = dict(findings=[], member_positions=[0, 1])
        self.assertEqual(
            eligible_group(dict(groups=[group, dict(findings=["unsupported_type"])])), group
        )
        for groups in ([], [group, group]):
            with self.assertRaises(StackError):
                eligible_group(dict(groups=groups))
        rows = cases()["complete"]
        control = controls(rows, "source_boundary")
        ctx = rows[0]["context"]
        self.assertEqual(
            (control["run_id"], control["source"], control["host_id"], control["generation"]),
            (
                ctx["run_id"],
                ctx["source"],
                ctx["host_binding"]["host_id"],
                ctx["source_generation"]["id"],
            ),
        )
        self.assertTrue(control["provenance"])

    def test_missing_or_changed_originals_cannot_initialize_a_runtime(self):
        with (
            patch(
                "linux_assembly_audit_runtime.artifacts", side_effect=ValueError("changed_original")
            ),
            patch("linux_assembly_audit_runtime.Assembly") as runtime,
        ):
            with self.assertRaises(ValueError):
                qualify(Path("absent-local-recording"))
            runtime.assert_not_called()


if __name__ == "__main__":
    unittest.main()
