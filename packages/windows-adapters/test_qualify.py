"""Synthetic regression tests for independent offline output verification."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from qualify import qualify

ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(__file__).resolve().parent


def compact(value, sorted_keys=False):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=sorted_keys, separators=(",", ":")
    ).encode()


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.input = Path(self.folder.name) / "input"
        self.output = Path(self.folder.name) / "output"
        self.plan_path = ROOT / ".cache/windows/plan.json"
        self.plan = json.loads(self.plan_path.read_bytes())
        event = json.loads((MODULE / "profiles/security.expected.json").read_bytes())
        db = event["detectbridge"]
        event["host"].pop("id")
        db["quality"] = dict(
            integrity="insufficient",
            eligibility="skipped",
            diagnostics=[dict(code="identity_missing", field="/host/id")],
        )
        raw = dict(
            contract_version="1.0.0",
            record_id=db["evidence"][0]["record_id"],
            source=db["source"],
            cursor=dict(kind="native", value="synthetic-cursor-0"),
            first_observed=db["time"]["first_observed"],
            evidence=db["evidence"][0]["evidence"],
        )
        source = json.loads((MODULE / "profiles/security.source.json").read_bytes())
        mapping = json.loads((MODULE / "profiles/security.mapping.json").read_bytes())
        context = dict(
            version="1.0.0",
            run_id=db["run_id"],
            source=raw["source"],
            first_observed=raw["first_observed"],
            source_contract=dict(
                id=source["id"],
                version="1.0.0",
                sha256=hashlib.sha256(compact(source, True)).hexdigest(),
                snapshot=source,
            ),
            mapping_profile=dict(
                id=mapping["id"], version="1.0.0", sha256=mapping["sha256"], declaration=mapping
            ),
            parser=dict(id="windows-xml", version="1.0.0"),
        )
        self.original = dict(raw=raw, context=context)
        evaluation = dict(
            version="2.0.0",
            event_id=event["event"]["id"],
            run_id=db["run_id"],
            bundle_sha256=self.plan["bundle_sha256"],
            mapping_sha256=hashlib.sha256(compact(self.plan["mapping_profiles"], True)).hexdigest(),
            result_id="sha256:"
            + hashlib.sha256(
                compact([event["event"]["id"], db["run_id"], self.plan["bundle_sha256"]])
            ).hexdigest(),
            matched=[],
            counts=dict(
                matched=0,
                unmatched=0,
                inapplicable=1,
                configuration_blocked=0,
                quality_skipped=3,
                evaluation_error=0,
            ),
            diagnostics=[
                dict(
                    rule_id="71100000-0000-4000-8000-00000000000" + str(i),
                    category="quality_skipped",
                    pointer="",
                )
                for i in (1, 2, 4)
            ],
            input=dict(
                cluster_id="offline",
                topic_id="offline",
                topic="windows-offline",
                partition=0,
                offset=0,
                value_sha256=hashlib.sha256(compact(event)).hexdigest(),
            ),
            **{k: self.plan[k] for k in ("compiler", "evaluator", "mapping_version")},
        )
        self.row = dict(
            version="1.0.0", raw=raw, context=context, event=event, evaluation=evaluation
        )
        self.input.write_bytes(compact(self.original) + b"\n")

    def verify(self, row):
        self.output.write_bytes(compact(row) + b"\n")
        return qualify(
            self.input, self.output, self.plan_path, dict(records=1, supported_skipped=1)
        )

    def test_literal_skipped_output_and_tampering(self):
        self.assertEqual(dict(records=1, supported_skipped=1), self.verify(self.row))
        for key in (
            "bundle_sha256",
            "mapping_sha256",
            "result_id",
            "evaluator",
            "compiler",
            "mapping_version",
        ):
            row = copy.deepcopy(self.row)
            row["evaluation"][key] = "tampered"
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(row)
        row = copy.deepcopy(self.row)
        row["event"]["host"]["id"] = "fabricated"
        with self.assertRaises(ValueError):
            self.verify(row)
        row = copy.deepcopy(self.row)
        row["event"]["detectbridge"]["evidence"][0]["record_id"] = "sha256:" + "0" * 64
        with self.assertRaises(ValueError):
            self.verify(row)
        row = copy.deepcopy(self.row)
        row["evaluation"]["counts"]["unmatched"] = 1
        with self.assertRaises(ValueError):
            self.verify(row)

    def test_missing_and_extra_publication_fail(self):
        self.verify(self.row)
        self.output.write_bytes(b"")
        with self.assertRaises(ValueError):
            qualify(self.input, self.output, self.plan_path)
        self.output.write_bytes((compact(self.row) + b"\n") * 2)
        with self.assertRaises(ValueError):
            qualify(self.input, self.output, self.plan_path)

    def test_supported_record_cannot_be_reported_as_unsupported(self):
        raw, context = self.original["raw"], self.original["context"]
        row = dict(
            version="1.0.0",
            raw=raw,
            context=context,
            preservation=dict(
                version="1.0.0",
                record_id=raw["record_id"],
                run_id=context["run_id"],
                evidence_sha256=raw["evidence"]["sha256"],
                code="unsupported_source",
                reason="source_signature",
                field="",
            ),
        )
        self.output.write_bytes(compact(row) + b"\n")
        with self.assertRaises(ValueError):
            qualify(self.input, self.output, self.plan_path, dict(records=1, unsupported=1))

    def test_wrong_source_signature_cannot_be_normalized(self):
        original = copy.deepcopy(self.original)
        raw = original["raw"]
        raw["evidence"]["inline"] = raw["evidence"]["inline"].replace(
            "<EventID>4688</EventID>", "<EventID>4689</EventID>"
        )
        raw["evidence"]["sha256"] = hashlib.sha256(raw["evidence"]["inline"].encode()).hexdigest()
        row = copy.deepcopy(self.row)
        row["raw"] = raw
        row["event"]["detectbridge"]["evidence"][0]["evidence"] = raw["evidence"]
        row["evaluation"]["input"]["value_sha256"] = hashlib.sha256(
            compact(row["event"])
        ).hexdigest()
        self.input.write_bytes(compact(original) + b"\n")
        with self.assertRaises(ValueError):
            self.verify(row)

    def test_incomplete_evaluation_reference_is_rejected(self):
        row = copy.deepcopy(self.row)
        row["evaluation"]["input"] = dict(offset=0)
        with self.assertRaises(ValueError):
            self.verify(row)


if __name__ == "__main__":
    unittest.main()
