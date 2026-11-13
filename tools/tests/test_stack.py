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
                        "outputs": {"toolchains": tools, "stack": selected, "transport": "false"},
                    },
                    "repository-hygiene": {"result": "success"},
                    "secret-scan": {"result": "success"},
                    "toolchain-verification": {
                        "result": "success" if tools == "true" else "skipped"
                    },
                    "transport-verification": {"result": "skipped"},
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

    def test_cluster_and_security_tampering_fail_without_reformatting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(stack, "CACHE", Path(tmp)):
            value = stack.Stack("detectbridge-test-a")
            value.folder.mkdir(mode=0o700)
            state = {
                "version": 1,
                "project": value.project,
                "cluster_id": "a" * 22,
                "port": 9200,
                "images": value.lock["images"],
                "security": {},
            }
            stack.save(value.folder / "state.json", state)
            self.assertEqual(value.load(), state)
            with (
                patch.object(value, "helper", return_value="different-cluster\n"),
                patch.object(stack, "run") as run,
            ):
                with self.assertRaises(stack.StackError):
                    value.check_cluster()
                run.assert_not_called()
            state["security"] = {"security/ca.pem": "0" * 64}
            stack.save(value.folder / "state.json", state)
            with self.assertRaises(stack.StackError):
                value.load()
            state["security"] = {}
            state["images"] = {}
            stack.save(value.folder / "state.json", state)
            with self.assertRaises(stack.StackError):
                value.load()

    def test_reset_refuses_unowned_volume_before_stopping_services(self):
        value = stack.Stack("detectbridge-test-a")
        with (
            patch.object(value, "load", return_value={}),
            patch.object(
                value, "owned_volume", side_effect=stack.StackError("volume_ownership_mismatch")
            ),
            patch.object(value, "down") as down,
        ):
            with self.assertRaises(stack.StackError):
                value.reset(value.project)
            down.assert_not_called()

    def test_verification_interrupt_cleans_only_exclusive_test_project(self):
        from unittest.mock import Mock

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(stack, "LOCKS", Path(tmp) / "locks"),
        ):
            caller = stack.Stack("detectbridge-dev")
            fake = Mock()
            fake.folder = Path(tmp) / "exclusive"
            fake.folder.mkdir()
            (fake.folder / "state.json").write_text("{}")
            fake.up.side_effect = KeyboardInterrupt()
            with (
                patch.object(stack, "Stack", return_value=fake) as factory,
                patch.object(stack.socket, "socket") as sock,
            ):
                sock.return_value.__enter__.return_value.getsockname.return_value = (
                    "127.0.0.1",
                    19200,
                )
                with self.assertRaises(KeyboardInterrupt):
                    caller.verify("core")
            selected = factory.call_args.args[0]
            self.assertTrue(selected.startswith("detectbridge-test-"))
            self.assertNotEqual(selected, caller.project)
            fake.reset.assert_called_once_with(selected)

    def test_up_failure_retains_existing_state(self):
        value = stack.Stack("detectbridge-test-a")
        with (
            patch.object(value, "containers", return_value=[]),
            patch.object(value, "doctor", return_value={}),
            patch.object(value, "load", return_value={"security": {}}),
            patch.object(value, "owned_volume", return_value=True),
            patch.object(value, "check_cluster"),
            patch.object(
                value, "compose", side_effect=stack.StackError("readiness_deadline_exceeded")
            ),
            patch.object(value, "reset") as reset,
        ):
            with self.assertRaises(stack.StackError):
                value.up("core")
            reset.assert_not_called()

    def test_occupied_loopback_port_fails_preflight(self):
        from unittest.mock import Mock

        value = stack.Stack("detectbridge-test-a", 19200)
        info = {
            "ServerVersion": "28.0.4",
            "Architecture": "aarch64",
            "OSType": "linux",
            "MemTotal": 8 * stack.GIB,
            "MemoryLimit": True,
            "CpuCfsQuota": True,
        }
        results = [Mock(stdout=json.dumps(info)), Mock(stdout="2.38.2")]
        with (
            patch.object(stack, "run", side_effect=results),
            patch.object(value, "containers", return_value=[]),
            patch.object(value, "helper", return_value=str(30 * stack.GIB // 1024) + "\n262144\n"),
            patch.object(stack.socket, "socket") as sock,
        ):
            sock.return_value.__enter__.return_value.bind.side_effect = OSError()
            with self.assertRaisesRegex(stack.StackError, "loopback_port_in_use"):
                value.doctor("full")

    def test_readiness_deadline_and_exited_service_fail_closed(self):
        value = stack.Stack("detectbridge-test-a")
        with (
            patch.object(value, "doctor", return_value={}),
            patch.object(value, "load", return_value={"security": {}}),
            patch.object(value, "owned_volume", return_value=True),
            patch.object(value, "check_cluster"),
            patch.object(value, "compose"),
            patch.object(value, "containers", return_value=[]),
            patch.object(stack.time, "monotonic", side_effect=[0, 181]),
        ):
            with self.assertRaisesRegex(stack.StackError, "readiness_deadline_exceeded"):
                value.up("core")
        with (
            patch.object(value, "doctor", return_value={}),
            patch.object(value, "load", return_value={"security": {}}),
            patch.object(value, "owned_volume", return_value=True),
            patch.object(value, "check_cluster"),
            patch.object(value, "compose"),
            patch.object(value, "containers", side_effect=[[], [{"State": {"Status": "exited"}}]]),
        ):
            with self.assertRaisesRegex(stack.StackError, "service_exited_before_readiness"):
                value.up("core")

    def test_administrative_failures_identify_operation_without_values(self):
        import subprocess

        cases = [
            (["test", "-s", "/private/checkpoint"], "checkpoint_metadata"),
            (["curl", "https://private/value"], "internal_http"),
            (["/opt/flink/bin/flink", "run"], "job_submission"),
            (["/opt/kafka/bin/kafka-configs.sh"], "topic_configuration"),
        ]
        for args, category in cases:
            failed = subprocess.CompletedProcess([], 22, "sensitive-output", "sensitive-error")
            with patch.object(stack.subprocess, "run", return_value=failed):
                with self.assertRaises(stack.StackError) as raised:
                    stack.run(["docker", "exec", "owned-container", *args])
                self.assertEqual(str(raised.exception), "command_failed_" + category + "_exit_22")

    def test_daemon_read_retry_never_retries_mutating_execution(self):
        import subprocess

        failed = subprocess.CompletedProcess(
            [], 1, "", "request returned 500 Internal Server Error for API route and version"
        )
        success = subprocess.CompletedProcess([], 0, "{}", "")
        with (
            patch.object(stack.subprocess, "run", side_effect=[failed, success]) as execute,
            patch.object(stack.time, "sleep"),
        ):
            self.assertEqual(stack.run(["docker", "info"]).returncode, 0)
            self.assertEqual(execute.call_count, 2)
        with patch.object(stack.subprocess, "run", return_value=failed) as execute:
            with self.assertRaisesRegex(stack.StackError, "docker_daemon_api_failure"):
                stack.run(["docker", "exec", "owned-container", "operation"])
            execute.assert_called_once()
