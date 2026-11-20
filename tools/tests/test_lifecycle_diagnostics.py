"""Independent CI-01 observation contracts; no native timing/corrective claim."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle_diagnostics as diagnostic
from lifecycle_runtime_verify import Qualification


class DiagnosticTests(unittest.TestCase):
    def test_disabled_is_transparent_and_does_not_read_clock(self):
        @diagnostic.measured("observe")
        def operation(value):
            return value

        with patch.object(diagnostic.time, "monotonic_ns", side_effect=AssertionError):
            marker = object()
            self.assertIs(operation(marker), marker)

    def test_nested_spans_and_durable_cursor_snapshots(self):
        clock = iter([100, 110, 120, 140, 160])
        owner = SimpleNamespace(state=dict(ack_cursor=0, sequence=4, acks={}))
        with patch.object(diagnostic.time, "monotonic_ns", side_effect=lambda: next(clock)):
            timings = diagnostic.Timings()
            with timings.activate(), diagnostic.span("observe", owner):
                diagnostic.note(requested=8, fetched=1)
                with diagnostic.span("journal_ack_cursor", owner):
                    owner.state.update(ack_cursor=1, sequence=5)
                diagnostic.note(processed=1)
        inner, outer = timings.samples
        self.assertEqual((inner["start_ns"], inner["end_ns"]), (20, 40))
        self.assertEqual((outer["start_ns"], outer["end_ns"]), (10, 60))
        self.assertEqual(inner["parent"], outer["id"])
        self.assertEqual(outer["start_state"]["ack_cursor"], 0)
        self.assertEqual(outer["end_state"]["ack_cursor"], 1)
        self.assertEqual(outer["counters"], dict(requested=8, fetched=1, processed=1))
        self.assertIn("inclusive", timings.report()["attribution"])
        self.assertIsNone(diagnostic.ACTIVE.get())

    def test_failures_propagate_and_values_are_filtered(self):
        secret = "PRIVATE_SENTINEL_payload_key_path_exception"
        failure = RuntimeError(secret)
        timings = diagnostic.Timings()
        with self.assertRaises(RuntimeError) as caught:
            with timings.activate(), diagnostic.span("record_validation"):
                diagnostic.note(
                    payload=secret,
                    command_sha256=secret,
                    worker_id=secret,
                    checkpoint_id=-1,
                    fetched=True,
                    wire_sha256="a" * 64,
                )
                raise failure
        self.assertIs(caught.exception, failure)
        self.assertNotIn(secret, json.dumps(timings.report()))
        self.assertFalse(timings.samples[0]["success"])
        self.assertEqual(timings.samples[0]["context"], dict(wire_sha256="a" * 64))
        self.assertEqual(timings.totals["record_validation"]["failures"], 1)

    def test_sample_and_byte_bounds_preserve_aggregate_call_counts(self):
        timings = diagnostic.Timings()
        timings.MAX_SAMPLES = 2
        with timings.activate():
            for _ in range(7):
                with diagnostic.span("signature_batch"):
                    pass
        self.assertEqual(len(timings.samples), 2)
        self.assertEqual(timings.dropped, 5)
        self.assertEqual(timings.totals["signature_batch"]["calls"], 7)
        timings.MAX_BYTES = timings.bytes
        with timings.activate(), diagnostic.span("observe"):
            pass
        self.assertEqual(len(timings.samples), 2)
        self.assertEqual(timings.dropped, 6)
        self.assertTrue(timings.report()["last_by_stage"]["observe"]["success"])
        with self.assertRaisesRegex(ValueError, "unknown_diagnostic_stage"):
            with timings.activate(), diagnostic.span("arbitrary_payload"):
                pass

    def test_late_truth_is_recorded_but_original_deadline_still_fails(self):
        qualifier = object.__new__(Qualification)
        timings = diagnostic.Timings()
        timings.MAX_SAMPLES = 0
        # Separate deterministic ns event clock and existing float deadline clock.
        with (
            timings.activate(),
            patch("lifecycle_runtime_verify.time.monotonic", side_effect=[0.0, 0.1, 120.001]),
            patch.object(
                diagnostic.time, "monotonic_ns", side_effect=[100_000_000, 120_001_000_000]
            ),
            patch("lifecycle_runtime_verify.time.sleep") as sleep,
            self.assertRaisesRegex(ValueError, "lifecycle_qualification_timeout_convergence"),
        ):
            qualifier.wait(lambda: True, "convergence")
        report = timings.report()
        self.assertEqual(timings.samples, [])
        self.assertEqual(report["late_truth_count"], 1)
        row = report["last_late_truth"]
        self.assertEqual(row, report["last_predicate"])
        self.assertTrue(row["context"]["truthy"])
        self.assertEqual(row["remaining_start_ns"], 119_900_000_000)
        self.assertEqual(row["remaining_end_ns"], -1_000_000)
        self.assertTrue(row["success"])
        self.assertIsNone(timings.deadline_ns)
        sleep.assert_not_called()

    def test_deadline_restores_on_exception_and_exact_cutoff_stays_accepted(self):
        qualifier = object.__new__(Qualification)
        timings = diagnostic.Timings()
        timings.deadline_ns = 77
        with (
            timings.activate(),
            patch("lifecycle_runtime_verify.time.monotonic", side_effect=[0, 0.1, 1]),
        ):
            self.assertTrue(qualifier.wait(lambda: True, "exact", timeout=1))
        self.assertEqual(timings.deadline_ns, 77)
        with (
            timings.activate(),
            patch("lifecycle_runtime_verify.time.monotonic", side_effect=[0, 0.1]),
        ):
            with self.assertRaisesRegex(RuntimeError, "original"):
                qualifier.wait(lambda: (_ for _ in ()).throw(RuntimeError("original")), "error")
        self.assertEqual(timings.deadline_ns, 77)
        self.assertFalse(timings.samples[-1]["success"])


if __name__ == "__main__":
    unittest.main()
