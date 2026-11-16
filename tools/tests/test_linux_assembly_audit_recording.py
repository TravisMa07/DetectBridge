"""Independent synthetic regressions for guest provenance and audit accounting."""

import base64
import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from linux_assembly_audit_recording import (
    capture_module,
    expected_documents,
    observation,
    sha,
    status,
    verify_evaluation,
)
from linux_assembly_cases import RUN, cases, digest, identity
from stack import StackError


class AuditEvidenceTests(unittest.TestCase):
    def test_empty_artifact_and_serial_hashes_are_checked_without_generating_records(self):
        module = capture_module()
        serial = b"unrelated guest kernel boot output\r\n"
        for name in sorted(module.NAMES):
            data = b"" if name == "auditd.stderr" else b"original arbitrary bytes\n"
            serial += b"DB_ARTIFACT_BEGIN:" + name.encode() + b":" + sha(data).encode() + b"\r\n"
            serial += base64.b64encode(data) + b"\r\nDB_ARTIFACT_END:" + name.encode() + b"\r\n"
        serial += b"DB_CAPTURE_EXIT:0\r\n"
        self.assertEqual(module.extract(serial)["auditd.stderr"], b"")
        for changed in (
            serial.replace(b"DB_CAPTURE_EXIT:0", b"DB_CAPTURE_EXIT:1"),
            serial.replace(base64.b64encode(b"original arbitrary bytes\n"), b"Y2hhbmdlZA==", 1),
            serial + serial,
        ):
            with self.assertRaises(ValueError):
                module.extract(changed)

    def test_batch_observation_uses_retained_completion_without_rewriting_original_metadata(self):
        captured = dict(first_observed="2026-01-01T00:00:00Z", completed="2026-01-01T00:00:05Z")
        catalog: dict[str, Any] = dict(
            acquisition=dict(first_observed=captured["completed"]),
            processing_metadata=dict(
                version="1.1.0",
                correction=dict(
                    original_value=captured["first_observed"], corrected_value=captured["completed"]
                ),
            ),
        )
        observation(catalog, captured)
        self.assertEqual(captured["first_observed"], "2026-01-01T00:00:00Z")
        for incorrect in (captured["first_observed"], "2026-01-01T00:00:04Z"):
            changed = copy.deepcopy(catalog)
            changed["acquisition"]["first_observed"] = incorrect
            with self.assertRaises(StackError):
                observation(changed, captured)

    def test_loss_or_unavailable_daemon_cannot_be_called_complete(self):
        original = b"enabled 1\npid 86\nlost 0\nbacklog 0\nbacklog_limit 8192\nrate_limit 0\n"
        self.assertEqual(status(original)["pid"], 86)
        for changed in (
            original.replace(b"lost 0", b"lost 1"),
            original.replace(b"pid 86", b"pid 0"),
            original.replace(b"backlog 0", b"backlog 1"),
            original + b"lost 0\n",
        ):
            with self.assertRaises(StackError):
                status(changed)

    def test_record_membership_is_exhaustive_and_never_double_counts_an_occurrence(self):
        source = cases()["complete"]
        rows = [{k: row[k] for k in ("raw", "context")} for row in source]
        group = dict(
            member_positions=list(range(6)),
            closure="source_boundary",
            findings=[],
            audit_timestamp="1767225600.001",
            audit_serial="7",
        )
        catalog: dict[str, Any] = dict(
            groups=[group], records=[dict(disposition="group_member") for _ in rows]
        )
        manifests, events, diagnostics = expected_documents(catalog, rows)
        self.assertEqual((len(manifests), len(events), len(diagnostics)), (1, 1, 0))
        for positions in ([0, 1, 2, 3, 4], [0, 1, 2, 3, 4, 4]):
            changed = copy.deepcopy(catalog)
            changed["groups"][0]["member_positions"] = positions
            with self.assertRaises(StackError):
                expected_documents(changed, rows)

    def test_equal_counts_do_not_hide_changed_evaluation_or_input_attribution(self):
        event = dict(event=dict(id="sha256:" + "a" * 64), detectbridge=dict(run_id=RUN))
        plan = dict(
            bundle_sha256="b" * 64,
            mapping_profiles=[],
            rules=[dict(id="original-rule", revision="c" * 64)],
            compiler="detectbridge/2.0.0",
            evaluator="detectbridge-java/2.0.0",
            mapping_version="source-mappings/1.0.0",
        )
        result = dict(
            version="2.0.0",
            event_id=event["event"]["id"],
            run_id=RUN,
            result_id=identity([event["event"]["id"], RUN, plan["bundle_sha256"]]),
            bundle_sha256=plan["bundle_sha256"],
            mapping_sha256=digest([]),
            **{k: plan[k] for k in ("compiler", "evaluator", "mapping_version")},
            input=dict(
                cluster_id="offline",
                topic_id="offline",
                topic="linux-audit-offline",
                partition=0,
                offset=0,
                value_sha256=sha(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
                ),
            ),
            counts={
                k: int(k == "matched")
                for k in (
                    "matched",
                    "unmatched",
                    "inapplicable",
                    "quality_skipped",
                    "configuration_blocked",
                    "evaluation_error",
                )
            },
            matched=[dict(id="original-rule", revision="c" * 64)],
            diagnostics=[],
        )
        verify_evaluation(result, event, plan, "matched", 0)
        for mutation in ("input", "run", "outcome", "bundle"):
            changed = copy.deepcopy(result)
            if mutation == "input":
                changed["input"]["value_sha256"] = "0" * 64
            elif mutation == "run":
                changed["run_id"] = "00000000-0000-4000-8000-000000000099"
            elif mutation == "outcome":
                changed["counts"]["matched"] = 0
                changed["counts"]["unmatched"] = 1
            else:
                changed["bundle_sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(StackError):
                verify_evaluation(changed, event, plan, "matched", 0)


if __name__ == "__main__":
    unittest.main()
