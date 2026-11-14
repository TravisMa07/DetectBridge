"""Negative fixtures are temporary; no deliberately broken content is committed."""

import secrets
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_gate import gate_passes
from check_repo import content_errors, form_errors, native, workflow_errors, yaml_load
from setup_github import contains_policy


class HygieneTests(unittest.TestCase):
    def errors(self, name, text, extra=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / name).write_text(text)
            for path, body in (extra or {}).items():
                (root / path).write_text(body)
            return content_errors(root, [Path(name)])

    def test_relative_links_and_heading_anchors(self):
        self.assertTrue(self.errors("README.md", "# Test\n\n[bad](missing.md)\n"))
        self.assertTrue(self.errors("README.md", "# Test\n\n[bad](#absent)\n"))
        self.assertFalse(self.errors("README.md", "# Test\n\n[ok](#test)\n"))
        self.assertFalse(
            self.errors(
                "README.md", "# Test\n\n[ok](other.md#example)\n", {"other.md": "# Example\n"}
            )
        )

    def test_invalid_json_and_yaml(self):
        self.assertTrue(self.errors("sample.json", "{oops}\n"))
        self.assertTrue(self.errors("sample.yml", "x: [\n"))
        self.assertTrue(self.errors("sample.yml", "x: 1\nx: 2\n"))
        self.assertEqual(yaml_load("on: push\nflag: false\n"), {"on": "push", "flag": False})

    def test_whitespace_and_encoding(self):
        self.assertTrue(self.errors("README.md", "# Test \n"))
        self.assertTrue(self.errors("README.md", "# Test"))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "bad.md").write_bytes(b"\xff")
            self.assertTrue(content_errors(root, [Path("bad.md")]))

    def test_issue_forms(self):
        self.assertTrue(form_errors({"name": "Incomplete"}, "test"))
        valid: dict[str, Any] = {
            "name": "Task",
            "description": "Task",
            "body": [
                {
                    "type": "textarea",
                    "id": "scope",
                    "attributes": {"label": "Scope"},
                    "validations": {"required": True},
                }
            ],
        }
        self.assertFalse(form_errors(valid, "test"))
        valid["body"].append(valid["body"][0])
        self.assertTrue(form_errors(valid, "test"))

    def test_action_pins_and_permissions(self):
        data: dict[str, Any] = {
            "on": {"pull_request": None},
            "permissions": {"contents": "read"},
            "jobs": {
                "check": {
                    "timeout-minutes": 5,
                    "steps": [
                        {"uses": "actions/checkout@v7", "with": {"persist-credentials": False}}
                    ],
                }
            },
        }
        self.assertTrue(workflow_errors(data, "test"))
        data["jobs"]["check"]["steps"][0]["uses"] = "actions/checkout@" + "a" * 40
        self.assertFalse(workflow_errors(data, "test"))
        data["permissions"] = {"contents": "write"}
        self.assertTrue(workflow_errors(data, "test"))

    def test_remote_policy_defaults_and_drift(self):
        desired = {
            "rules": [
                {"type": "pull_request", "parameters": {"required_approving_review_count": 0}}
            ]
        }
        actual: dict[str, Any] = {
            "rules": [
                {
                    "type": "pull_request",
                    "parameters": {"required_approving_review_count": 0, "server_default": True},
                }
            ],
            "id": 1,
        }
        self.assertTrue(contains_policy(actual, desired))
        actual["rules"][0]["parameters"]["required_approving_review_count"] = 1
        self.assertFalse(contains_policy(actual, desired))

    def test_gate_fails_closed(self):
        for applicable in ("true", "false"):
            for status in ("success", "failure", "cancelled", "skipped", None):
                needs: dict[str, Any] = {
                    "classify-changes": {
                        "result": "success",
                        "outputs": {
                            "toolchains": applicable,
                            "stack": applicable,
                            "transport": applicable,
                        },
                    },
                    "repository-hygiene": {"result": "success"},
                    "secret-scan": {"result": "success"},
                    "toolchain-verification": {"result": status},
                    "local-stack-verification": {"result": status},
                    "transport-verification": {"result": status},
                }
                self.assertEqual(
                    gate_passes(needs), status == ("success" if applicable == "true" else "skipped")
                )
                needs["classify-changes"]["result"] = "failure"
                self.assertFalse(gate_passes(needs))
        self.assertFalse(gate_passes({}))
        self.assertFalse(gate_passes(None))
        needs["classify-changes"] = {"result": "success", "outputs": {}}
        self.assertFalse(gate_passes(needs))

    def test_generated_dummy_secret_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            dummy = (
                "gh"
                + "p_"
                + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36))
            )
            (Path(folder) / "fixture.txt").write_text("token = " + dummy + "\n")
            result = subprocess.run(
                [native("gitleaks"), "dir", "--redact", "--no-banner", folder], capture_output=True
            )
            self.assertEqual(
                result.returncode, 1, "Expected Gitleaks to reject the generated dummy token"
            )
            self.assertNotIn(dummy.encode(), result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
