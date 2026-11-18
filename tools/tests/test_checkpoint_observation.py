"""Paused-state snapshots and completed timer transitions survive observer races."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integration_verify
import transport
from stack import StackError

JOB = "a" * 32
ORIGINAL: dict[str, Any] = dict(members=[dict(record_id="original")], opened=1000, deadline=31000)
MANIFEST = dict(manifest_id="frozen-manifest")


def checkpoint(index, status="COMPLETED"):
    return dict(
        id=index, status=status, external_path=f"file:///state/checkpoints/{JOB}/chk-{index}"
    )


class PausedLifecycle(transport.Transport):
    def __init__(self, folder, state="RESTARTING"):
        self.folder = Path(folder)
        self.state = state
        self.paused = True
        self.stopped = 0
        self.waited = 0
        self.files = {1}
        self.current = 1
        self.foreign = False
        self.stack = cast(Any, SimpleNamespace(exec=self.metadata))

    def latest_job(self):
        return dict(job_id="c" * 32 if self.foreign else JOB)

    def config(self):
        return dict(bundle=dict(bundle_sha256="b" * 64))

    def wait_checkpoint(self, job_id, timeout=180):
        self.waited += 1
        raise StackError("cannot_wait_for_running_while_broker_paused")

    def stop(self):
        assert self.paused
        self.stopped += 1
        self.state = "CANCELED"
        self.current = 2
        self.files = {2}

    def rest(self, path, method="GET", data=None):
        if path.endswith("/checkpoints"):
            return dict(latest=dict(completed=checkpoint(self.current)))
        return dict(state=self.state)

    def metadata(self, service, command, flag, path):
        assert self.paused
        if int(path.split("chk-")[1].split("/")[0]) not in self.files:
            raise StackError("missing_checkpoint_metadata")
        return ""


class CheckpointObservationTests(unittest.TestCase):
    def test_paused_restart_is_canceled_before_snapshot_selection_without_waiting(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = PausedLifecycle(folder)
            selected = runtime.quiesced_checkpoint(JOB)
            self.assertEqual(selected, checkpoint(2))
            self.assertEqual(runtime.waited, 0)
            self.assertEqual(runtime.stopped, 1)
            self.assertTrue(runtime.paused)

    def test_paused_failed_job_uses_stable_completed_snapshot_without_waiting_or_cancel(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = PausedLifecycle(folder, "FAILED")
            selected = runtime.quiesced_checkpoint(JOB)
            self.assertEqual(selected, checkpoint(1))
            self.assertEqual((runtime.waited, runtime.stopped), (0, 0))

    def test_terminal_snapshot_rejects_finished_foreign_and_missing_metadata(self):
        for fault in ("finished", "foreign", "missing"):
            with tempfile.TemporaryDirectory() as folder, self.subTest(fault=fault):
                runtime = PausedLifecycle(folder, "FAILED")
                if fault == "finished":
                    runtime.state = "FINISHED"
                if fault == "missing":
                    runtime.files.clear()
                if fault == "foreign":
                    runtime.foreign = True
                with self.assertRaises(StackError):
                    runtime.quiesced_checkpoint(JOB)

    def test_broker_remains_paused_until_the_terminal_snapshot_is_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = PausedLifecycle(folder)
            runtime.paused = False
            events = []

            def pause(value):
                events.append(("pause", value))
                runtime.paused = value

            runtime.pause_broker = pause

            def observe(test, cp):
                self.assertTrue(runtime.paused)
                events.append(("observe", cp["id"]))
                return dict(groups=[copy.deepcopy(ORIGINAL)], outbox=[])

            with patch.object(transport.time, "sleep") as sleep:
                chosen = transport.broker_pause_checkpoint(
                    runtime, JOB, ORIGINAL, MANIFEST["manifest_id"], observe
                )
            self.assertEqual(chosen["id"], 2)
            self.assertEqual(
                events, [("pause", True), ("observe", 1), ("observe", 2), ("pause", False)]
            )
            sleep.assert_called_once_with(40)
            self.assertEqual(runtime.waited, 0)

    def test_quiescence_cannot_substitute_a_healthy_retired_or_mutated_snapshot(self):
        for fault in ("retired", "deadline", "membership"):
            with tempfile.TemporaryDirectory() as folder, self.subTest(fault=fault):
                runtime = PausedLifecycle(folder)
                runtime.pause_broker = lambda value: setattr(runtime, "paused", value)

                def observe(test, cp):
                    if cp["id"] == 1:
                        return dict(groups=[ORIGINAL], outbox=[])
                    changed = copy.deepcopy(ORIGINAL)
                    if fault == "deadline":
                        changed["deadline"] += 1
                    if fault == "membership":
                        changed["members"].append(dict(record_id="foreign"))
                    return dict(groups=[] if fault == "retired" else [changed], outbox=[])

                with patch.object(transport.time, "sleep"):
                    with self.assertRaisesRegex(
                        StackError, "broker_pause_terminal_state_not_retained"
                    ):
                        transport.broker_pause_checkpoint(
                            runtime, JOB, ORIGINAL, MANIFEST["manifest_id"], observe
                        )
                self.assertFalse(runtime.paused)

    def test_group_proof_requires_exact_pending_state_even_if_manifest_is_also_present(self):
        manifest = dict(kind="manifest", key=MANIFEST["manifest_id"])
        changed = dict(ORIGINAL, deadline=32000)
        self.assertTrue(
            transport.checkpoint_retains_group(
                dict(groups=[ORIGINAL], outbox=[]), ORIGINAL, MANIFEST["manifest_id"]
            )
        )
        self.assertTrue(
            transport.checkpoint_retains_group(
                dict(groups=[], outbox=[manifest]), ORIGINAL, MANIFEST["manifest_id"]
            )
        )
        self.assertFalse(
            transport.checkpoint_retains_group(
                dict(groups=[changed], outbox=[manifest]), ORIGINAL, MANIFEST["manifest_id"]
            )
        )

    def test_completed_history_preserves_an_already_drained_manifest_transition(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = SimpleNamespace(
                folder=Path(folder),
                wait_checkpoint=lambda job: checkpoint(3),
                rest=lambda path: dict(history=[checkpoint(1), checkpoint(2), checkpoint(3)]),
            )
            values = {
                1: dict(groups=[ORIGINAL], outbox=[]),
                2: dict(groups=[], outbox=[dict(kind="manifest", key="frozen-manifest")]),
                3: dict(groups=[], outbox=[]),
            }
            with patch.object(
                integration_verify,
                "checkpoint_inventory",
                side_effect=lambda test, cp: copy.deepcopy(values[cp["id"]]),
            ):
                selected = integration_verify.deadline_checkpoint(
                    runtime, dict(job_id=JOB), ORIGINAL, MANIFEST
                )
            self.assertEqual(selected["id"], 2)

    def test_history_cannot_substitute_in_progress_failed_or_wrong_manifest_observations(self):
        for status, key in (
            ("IN_PROGRESS", "frozen-manifest"),
            ("FAILED", "frozen-manifest"),
            ("COMPLETED", "wrong-manifest"),
        ):
            with tempfile.TemporaryDirectory() as folder, self.subTest(status=status, key=key):
                runtime = SimpleNamespace(
                    folder=Path(folder),
                    wait_checkpoint=lambda job: checkpoint(3),
                    rest=lambda path: dict(history=[checkpoint(2, status), checkpoint(3)]),
                )
                seen = []

                def observe(test, cp):
                    seen.append(cp["id"])
                    return dict(
                        groups=[], outbox=[dict(kind="manifest", key=key)] if cp["id"] == 2 else []
                    )

                clock = iter([0, 0.1, 0.2])
                with (
                    patch.object(integration_verify, "checkpoint_inventory", side_effect=observe),
                    patch.object(
                        integration_verify.time, "monotonic", side_effect=lambda: next(clock, 2)
                    ),
                    patch.object(integration_verify.time, "sleep"),
                ):
                    with self.assertRaises((StackError, RuntimeError)):
                        integration_verify.deadline_checkpoint(
                            runtime, dict(job_id=JOB), ORIGINAL, MANIFEST, timeout=1
                        )
                if status != "COMPLETED":
                    self.assertNotIn(2, seen)

    def test_history_rejects_changed_original_deadline_before_accepting_a_later_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            changed = dict(ORIGINAL, deadline=32000)
            runtime = SimpleNamespace(
                folder=Path(folder),
                wait_checkpoint=lambda job: checkpoint(3),
                rest=lambda path: dict(history=[checkpoint(1), checkpoint(2), checkpoint(3)]),
            )
            values = {
                1: dict(groups=[changed], outbox=[]),
                2: dict(groups=[], outbox=[dict(kind="manifest", key="frozen-manifest")]),
                3: dict(groups=[], outbox=[]),
            }
            with patch.object(
                integration_verify,
                "checkpoint_inventory",
                side_effect=lambda test, cp: values[cp["id"]],
            ):
                with self.assertRaises(StackError):
                    integration_verify.deadline_checkpoint(
                        runtime, dict(job_id=JOB), ORIGINAL, MANIFEST
                    )

    def test_history_rejects_foreign_job_and_mismatched_checkpoint_paths(self):
        for path in (
            f"file:///state/checkpoints/{'b' * 32}/chk-2",
            f"file:///state/checkpoints/{JOB}/chk-99",
        ):
            with tempfile.TemporaryDirectory() as folder, self.subTest(path=path):
                candidate = dict(checkpoint(2), external_path=path)
                runtime = SimpleNamespace(
                    folder=Path(folder),
                    wait_checkpoint=lambda job: checkpoint(3),
                    rest=lambda endpoint: dict(history=[candidate, checkpoint(3)]),
                )
                with patch.object(
                    integration_verify,
                    "checkpoint_inventory",
                    return_value=dict(groups=[], outbox=[]),
                ) as observe:
                    with self.assertRaises(StackError):
                        integration_verify.deadline_checkpoint(
                            runtime, dict(job_id=JOB), ORIGINAL, MANIFEST
                        )
                self.assertEqual(observe.call_count, 1)


if __name__ == "__main__":
    unittest.main()
