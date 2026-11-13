"""Offline stack policy, lifecycle boundaries, and classified CI gates."""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stack
from check_contracts import load_json
from check_gate import gate_passes
from check_repo import yaml_load
from check_stack import DEPLOY, validate
from classify_changes import needs_stack


class StackTests(unittest.TestCase):
    def test_resource_preflight(self):
        self.assertEqual(stack.capacity_errors(7 * stack.GIB, 10 * stack.GIB, "full", 262144), [])
        for memory, disk, kernel, reason in [
            (6 * stack.GIB, 30 * stack.GIB, 262144, "insufficient_docker_memory"),
            (8 * stack.GIB, 9 * stack.GIB, 262144, "insufficient_docker_disk"),
            (8 * stack.GIB, 30 * stack.GIB, 65530, "vm_max_map_count_too_low"),
        ]:
            self.assertIn(reason, stack.capacity_errors(memory, disk, "full", kernel))
        self.assertEqual(stack.version_tuple("v5.5.1"), (5, 5, 1))
        with self.assertRaises(stack.StackError):
            stack.version_tuple("unknown")

    def test_policy_rejects_exposure_limits_and_unpinned_images(self):
        base = yaml_load((DEPLOY / "compose.yml").read_text())
        lock = load_json(DEPLOY / "images.lock.json")
        self.assertEqual(validate(base, lock), [])
        for field, value in [
            ("ports", ["9092:9092"]),
            ("image", "apache/kafka:latest"),
            ("mem_limit", "8g"),
            ("privileged", True),
            ("logging", {}),
            ("healthcheck", {}),
            ("volumes", ["/var/run/docker.sock:/var/run/docker.sock"]),
            ("user", "0:0"),
        ]:
            candidate = copy.deepcopy(base)
            candidate["services"]["kafka"][field] = value
            self.assertTrue(validate(candidate, lock), field)

    def test_names_locks_and_secure_state(self):
        for value in (
            "other-project",
            "detectbridge-../x",
            "detectbridge-a;echo",
            "detectbridge-A",
        ):
            with self.assertRaises(stack.StackError):
                stack.project_name(value)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(stack, "LOCKS", root / "locks"):
                with stack.project_lock("detectbridge-test-a"):
                    with self.assertRaises(stack.StackError):
                        with stack.project_lock("detectbridge-test-a"):
                            pass
            path = root / "state.json"
            stack.save(path, {"safe": True})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), {"safe": True})

    def test_reset_requires_confirmation_and_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(stack, "CACHE", Path(tmp)):
            value = stack.Stack("detectbridge-test-a")
            with patch.object(stack, "run") as run:
                with self.assertRaises(stack.StackError):
                    value.reset("detectbridge-test-b")
                run.assert_not_called()
                with self.assertRaises(stack.StackError):
                    value.reset("detectbridge-test-a")
                run.assert_not_called()

    def test_stack_classification_and_independent_aggregate(self):
        self.assertFalse(needs_stack(["docs/local-stack.md", "README.md"]))
        self.assertFalse(needs_stack(["contracts/v1/raw-record.schema.json"]))
        for name in (
            "deploy/local/compose.yml",
            "tools/stack.py",
            "tools/tests/test_stack.py",
            "uv.lock",
            ".github/workflows/hygiene.yml",
        ):
            self.assertTrue(needs_stack([name]))
        for tools in ("true", "false"):
            for selected in ("true", "false"):
                base: dict[str, Any] = {
                    "classify-changes": {
                        "result": "success",
                        "outputs": {"toolchains": tools, "stack": selected},
                    },
                    "repository-hygiene": {"result": "success"},
                    "secret-scan": {"result": "success"},
                    "toolchain-verification": {
                        "result": "success" if tools == "true" else "skipped"
                    },
                    "local-stack-verification": {
                        "result": "success" if selected == "true" else "skipped"
                    },
                }
                self.assertTrue(gate_passes(base))
                for status in (
                    "failure",
                    "cancelled",
                    "skipped" if selected == "true" else "success",
                    None,
                ):
                    value = copy.deepcopy(base)
                    value["local-stack-verification"]["result"] = status
                    self.assertFalse(gate_passes(value))
                for output in ({}, {"toolchains": tools}, {"toolchains": tools, "stack": "maybe"}):
                    value = copy.deepcopy(base)
                    value["classify-changes"]["outputs"] = output
                    self.assertFalse(gate_passes(value))
