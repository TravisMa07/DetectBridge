"""Independent current-policy boundary and isolation expectations; API work pending."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import current_replay as current
import historical as history
from current_replay_cases import request


class CurrentReplayTests(unittest.TestCase):
    def fixture(self):
        refs = [
            dict(topic=history.INPUT, offset=i, value_sha256=history.sha(str(i).encode()))
            for i in range(7)
        ]
        selected = dict(
            request=dict(
                original_run_id="00000000-0000-4000-8000-000000000001",
                units=[
                    dict(id="audit_timeout", inputs=refs[:5]),
                    dict(id="late", inputs=[refs[5]]),
                    dict(id="auth", inputs=[refs[6]]),
                ],
            )
        )
        return request("a" * 64, selected["request"], "b" * 64), selected

    def test_overlapping_roots_fail_before_any_mutable_context(self):
        value, _ = self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            request_path = root / "request.json"
            request_path.write_bytes(history.encoded(value))
            for nested, parent in ((0, 1), (1, 0), (0, 2), (2, 0), (1, 2), (2, 1)):
                paths = [root / "archive", root / "historical", root / "current"]
                paths[nested] = paths[parent] / "nested"
                before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
                with (
                    self.subTest(nested=nested, parent=parent),
                    patch.object(history, "catalog") as catalog,
                    patch.object(current, "workspace") as workspace,
                    self.assertRaisesRegex(ValueError, "current_root_overlap"),
                ):
                    current.replay(
                        paths[0],
                        paths[1],
                        paths[2],
                        request_path,
                        root / "plan",
                        "00000000-0000-4000-8000-000000000002",
                    )
                catalog.assert_not_called()
                workspace.assert_not_called()
                self.assertEqual(before, sorted(str(p.relative_to(root)) for p in root.rglob("*")))
            with self.assertRaisesRegex(ValueError, "current_root_overlap"):
                current.replay(root, root, root, request_path, root / "plan", "invalid")

    def test_frozen_schedules_select_every_original_once(self):
        base, selected = self.fixture()
        for case in ("regroup", "timeout", "deadline"):
            value = request(
                base["selection_sha256"], selected["request"], base["plan_sha256"], case
            )
            current.validate(value, selected)

    def test_missing_duplicate_foreign_or_changed_input_fails(self):
        base, selected = self.fixture()
        variants = []
        value = copy.deepcopy(base)
        del value["schedule"][0]
        variants.append(value)
        value = copy.deepcopy(base)
        value["schedule"].insert(1, copy.deepcopy(value["schedule"][0]))
        variants.append(value)
        value = copy.deepcopy(base)
        value["schedule"][0]["input"]["offset"] = 10
        variants.append(value)
        value = copy.deepcopy(base)
        value["schedule"][0]["input"]["value_sha256"] = "c" * 64
        variants.append(value)
        for value in variants:
            with self.subTest(schedule=value["schedule"]), self.assertRaises(ValueError):
                current.validate(value, selected)

    def test_schedule_and_profiles_have_no_implicit_defaults(self):
        base, selected = self.fixture()
        for field in (
            "engine_profile",
            "source_policy",
            "schedule_policy",
            "assembler_limits",
            "enrichment",
        ):
            value = copy.deepcopy(base)
            del value[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                current.validate(value, selected)
        for mutation in (
            "backward",
            "float",
            "bool",
            "early_end",
            "no_end",
            "tick_input",
            "enrichment",
            "profile",
        ):
            value = copy.deepcopy(base)
            if mutation == "backward":
                value["schedule"][1]["at_ms"] = -1
            if mutation == "float":
                value["schedule"][0]["at_ms"] = 0.0
            if mutation == "bool":
                value["schedule"][0]["at_ms"] = True
            if mutation == "early_end":
                value["schedule"][0]["action"] = "end"
            if mutation == "no_end":
                value["schedule"].pop()
            if mutation == "tick_input":
                value["schedule"][0]["action"] = "tick"
            if mutation == "enrichment":
                value["enrichment"] = ["current-network-lookup"]
            if mutation == "profile":
                value["engine_profile"] = "unreviewed-parser"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                current.validate(value, selected)

    def test_workspace_rejects_historical_root_before_mutating_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "history"
            with history.catalog(root):
                pass
            before = {
                str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
            }
            with self.assertRaises(ValueError), current.workspace(root):
                pass
            self.assertEqual(
                before,
                {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()},
            )

    def test_workspace_has_exclusive_mode_and_destination_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "current"
            with current.workspace(root):
                self.assertEqual(history.verified(root / "catalog.json")["mode"], "current")
                with self.assertRaises(BlockingIOError), current.workspace(root):
                    pass
            with self.assertRaises(ValueError), history.catalog(root):
                pass
            binding = history.verified(root / "catalog.json")
            self.assertEqual(binding["destination"], str(root))

    def test_foreign_partial_and_symlink_are_not_silently_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "current"
            with current.workspace(root):
                pass
            work = root / (".partial-" + "a" * 32)
            work.mkdir()
            sentinel = work / "foreign-evidence.txt"
            sentinel.write_text("private original")
            with self.assertRaises(ValueError), current.workspace(root):
                pass
            self.assertEqual(sentinel.read_text(), "private original")
            link = Path(folder).resolve() / "alias"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError), current.workspace(link):
                pass

    def test_frozen_contract_rejects_fractional_commit_even_when_checksum_changes(self):
        value = dict(
            version="1.0.0",
            index=0.0,
            transition_id="a" * 64,
            result_sha256="b" * 64,
            result_bytes=1,
            previous_sha256=None,
        )
        with self.assertRaises(ValueError):
            current.require("commit", value)
        value["index"] = 0
        current.require("commit", value)
        value["result_bytes"] = True
        with self.assertRaises(ValueError):
            current.require("commit", value)


if __name__ == "__main__":
    unittest.main()
