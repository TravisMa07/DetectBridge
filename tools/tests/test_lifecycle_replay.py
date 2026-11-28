"""Checks for lifecycle replay selection and crash-safe file publication."""

import copy
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle_replay as replay


def request():
    return dict(
        version=replay.VERSION,
        mode="historical",
        worker_id="71500000-0000-4000-8000-000000000020",
        original_run_id="71500000-0000-4000-8000-000000000101",
        units=[
            dict(
                kind="windows",
                inputs=[dict(topic="raw-one", offset=0, value_sha256="1" * 64)],
                outputs=[dict(topic="output", offset=0, value_sha256="2" * 64)],
            )
        ],
    )


class ReplayTests(unittest.TestCase):
    def test_occurrence_cannot_be_assigned_to_two_units(self):
        req = request()
        req["units"].append(copy.deepcopy(req["units"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_reference"):
            replay.validate(req)


class ReplayPublicationTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "replay"
        req = request()
        req["units"].append(copy.deepcopy(req["units"][0]))
        self.spec = dict(
            run_id="71510000-0000-4000-8000-000000000001", mode="historical", request=req
        )
        self.results = [dict(outputs=[{"kind": "tagged", "value": {"example": n}}]) for n in (1, 2)]

    def run_results(self, resume=False):
        with replay.workspace(self.root) as root:
            return replay.publish_results(root, self.spec, resume, iter(self.results))

    def unit(self, index):
        return self.root / "runs" / self.spec["run_id"] / "units" / f"{index:06d}"

    def test_interrupt_before_publication_and_verified_resume(self):
        from unittest.mock import patch

        def fault(phase):
            if phase == "during_result":
                raise InterruptedError()

        with patch.object(replay, "HOOK", fault), self.assertRaises(InterruptedError):
            self.run_results()
        self.assertFalse(self.unit(0).exists())
        self.assertEqual(self.run_results(True)["units"], 2)
        result = self.unit(0) / "result.json"
        before = result.stat().st_mtime_ns
        self.assertEqual(self.run_results(True)["status"], "complete")
        self.assertEqual(before, result.stat().st_mtime_ns)

    def test_tamper_after_durable_publication_rejects_before_append(self):
        from unittest.mock import patch

        def fault(phase):
            if phase == "after_result_publication":
                raise InterruptedError()

        with patch.object(replay, "HOOK", fault), self.assertRaises(InterruptedError):
            self.run_results()
        (self.unit(0) / "result.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "committed_result_conflict"):
            self.run_results(True)
        self.assertFalse(self.unit(1).exists())
        self.assertEqual((self.unit(0) / "result.json").read_bytes(), b"changed")

    def test_changed_resume_binding_and_gapped_prefix(self):
        self.run_results()
        self.spec["changed"] = True
        with self.assertRaisesRegex(ValueError, "resume_binding"):
            self.run_results(True)
        del self.spec["changed"]
        self.unit(0).rename(self.unit(3))
        with self.assertRaisesRegex(ValueError, "committed_prefix"):
            self.run_results(True)


class ReplaySelectionTests(unittest.TestCase):
    def setUp(self):
        import base64

        self.req = request()
        unit = self.req["units"][0]
        sid, run = self.req["worker_id"], self.req["original_run_id"]
        topic = dict(id="topic-id", name="raw-one", partition=0)
        self.manifest = dict(
            workers=[dict(worker_id=sid, input_topic=topic)], common=dict(cluster_id="cluster")
        )
        source = dict(kind="windows_record", context=dict(run_id=run), raw=dict(record_id="id"))
        plan = b"plan bytes"
        selection = dict(
            worker_id=sid,
            origin_incarnation="inc",
            kind="tagged",
            revision=3,
            command_sha256="new-A",
            bundle_sha256="A",
            compatibility_sha256="compatible",
            plan_sha256=replay.history.sha(plan),
            output_id="output-id",
            document={"kind": "example"},
        )
        self.rows = []
        for ref, document in zip(
            unit["inputs"] + unit["outputs"], [source, selection], strict=True
        ):
            raw = replay.history.encoded(document)
            ref["value_sha256"] = replay.history.sha(raw)
            self.rows.append(dict(**ref, value=base64.b64encode(raw).decode("ascii")))
        receipt = dict(
            worker_id=sid,
            kind="receipt",
            document=dict(
                input=dict(
                    **unit["inputs"][0], topic_id="topic-id", cluster_id="cluster", partition=0
                ),
                action="windows_record",
                record_id="id",
            ),
        )
        member = dict(
            worker_id=sid,
            input_topic="raw-one",
            input_topic_id="topic-id",
            assigned_runs=[run],
            incarnation="inc",
        )
        command = dict(registrations=[member], revision=3, proposal=dict(bundle_sha256="A"))
        self.graph: dict[str, Any] = dict(
            inputs={("raw-one", 0): source},
            outputs={("output", 0): selection, ("output", 42): receipt},
            commands={"new-A": command},
            bundles={
                "A": dict(
                    plan=plan, manifest=dict(bundle_sha256="A", compatibility_sha256="compatible")
                )
            },
        )

    def select(self):
        return replay.selected(self.req, self.manifest, self.rows, self.graph)

    def test_rollback_selects_original_plan_and_distinct_command(self):
        [(_, outputs, bundle)] = self.select()
        self.assertEqual((outputs[0]["command_sha256"], bundle["plan"]), ("new-A", b"plan bytes"))
        self.graph["commands"]["new-A"]["revision"] = 1
        with self.assertRaisesRegex(ValueError, "output_policy"):
            self.select()

    def test_missing_or_foreign_receipt(self):
        receipt = self.graph["outputs"][("output", 42)]
        receipt["document"]["input"]["cluster_id"] = "cloned-cluster"
        with self.assertRaisesRegex(ValueError, "receipt_binding"):
            self.select()
        self.graph["outputs"].pop(("output", 42))
        with self.assertRaisesRegex(ValueError, "source_binding"):
            self.select()

    def test_wrong_run_assignment_for_recorded_command(self):
        self.graph["commands"]["new-A"]["registrations"][0]["assigned_runs"] = []
        with self.assertRaisesRegex(ValueError, "membership"):
            self.select()

    def test_invalid_current_schedule_rejected(self):
        source = self.req["units"][0]["inputs"][0]
        self.req.update(
            mode="current",
            bundle_sha256="b" * 64,
            schedule=[
                dict(at_ms=0, action="input", input=source),
                dict(at_ms=1, action="end", input=None),
            ],
        )
        replay.validate(self.req)
        self.req["schedule"][0]["input"] = {**source, "topic": "foreign-source"}
        with self.assertRaisesRegex(ValueError, "schedule_input"):
            replay.validate(self.req)
