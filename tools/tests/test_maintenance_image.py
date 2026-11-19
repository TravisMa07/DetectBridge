"""Pinned-image cold starts and bootstrap failures never adopt a different image."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_maintenance_verify as verify
from stack import StackError

PIN = verify.PINS["image"]
NAMED, DIGEST = PIN.split("@")
CANONICAL = NAMED.rsplit(":", 1)[0] + "@" + DIGEST
IMAGE = dict(Id="sha256:" + "a" * 64, Os="linux", Architecture="amd64", RepoDigests=[CANONICAL])


class MaintenanceImageTests(unittest.TestCase):
    def fake(self, canonical=True, tagged=True, pull_error=None, inspect_error=None):
        state = dict(canonical=canonical, tagged=tagged)
        calls = []

        def command(args, *, check=True, **kwargs):
            calls.append(args)
            status, stdout, stderr = 0, "", ""
            if args[:3] == ["docker", "image", "inspect"]:
                if inspect_error:
                    status, stderr = 1, inspect_error
                elif not state["canonical" if args[3] == CANONICAL else "tagged"]:
                    status, stderr = 1, "Error response from daemon: No such image: " + args[3]
                else:
                    stdout = json.dumps([IMAGE])
            elif args[:2] == ["docker", "pull"]:
                if pull_error:
                    status, stderr = 1, pull_error
                else:
                    state.update(canonical=True, tagged=True)
            elif args[:3] == ["docker", "image", "tag"]:
                state["tagged"] = True
            else:
                raise AssertionError(args)
            if status and check:
                raise StackError("command_failed")
            return subprocess.CompletedProcess(args, status, stdout, stderr)

        return calls, command

    def test_cold_worker_acquires_only_exact_pin_before_inspection(self):
        calls, command = self.fake(canonical=False, tagged=False)
        with tempfile.TemporaryDirectory() as folder, patch.object(verify, "run", command):
            self.assertEqual(verify.ensure_image(Path(folder).resolve()), IMAGE)
        self.assertEqual(
            [a for a in calls if a[:2] == ["docker", "pull"]], [["docker", "pull", PIN]]
        )

    def test_existing_digest_with_missing_tag_restores_only_verified_alias(self):
        calls, command = self.fake(tagged=False)
        with tempfile.TemporaryDirectory() as folder, patch.object(verify, "run", command):
            self.assertEqual(verify.ensure_image(Path(folder).resolve()), IMAGE)
        self.assertFalse(any(a[:2] == ["docker", "pull"] for a in calls))
        self.assertIn(["docker", "image", "tag", CANONICAL, NAMED], calls)

    def test_warm_worker_does_not_pull_or_retag(self):
        calls, command = self.fake()
        with tempfile.TemporaryDirectory() as folder, patch.object(verify, "run", command):
            self.assertEqual(verify.ensure_image(Path(folder).resolve()), IMAGE)
        self.assertTrue(all(a[:3] == ["docker", "image", "inspect"] for a in calls))

    def test_http429_is_retained_and_does_not_retry_or_fallback(self):
        calls, command = self.fake(
            canonical=False, tagged=False, pull_error="HTTP 429 Too Many Requests"
        )
        with tempfile.TemporaryDirectory() as folder, patch.object(verify, "run", command):
            with self.assertRaises(StackError):
                verify.ensure_image(Path(folder).resolve())
            records = [json.loads(p.read_bytes()) for p in Path(folder).glob("*.json")]
            self.assertTrue(any("HTTP 429" in record.get("stderr", "") for record in records))
        self.assertEqual(sum(a[:2] == ["docker", "pull"] for a in calls), 1)

    def test_daemon_permission_failure_is_not_missing_image(self):
        calls, command = self.fake(inspect_error="permission denied while connecting to Docker")
        with tempfile.TemporaryDirectory() as folder, patch.object(verify, "run", command):
            with self.assertRaises(StackError):
                verify.ensure_image(Path(folder).resolve())
        self.assertFalse(any(a[:2] == ["docker", "pull"] for a in calls))

    def test_foreign_digest_is_rejected_without_pull_or_alias_overwrite(self):
        calls, command = self.fake()
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(verify, "run", command),
            patch.dict(IMAGE, RepoDigests=["foreign@sha256:" + "b" * 64]),
        ):
            with self.assertRaisesRegex(StackError, "maintenance_image_binding"):
                verify.ensure_image(Path(folder).resolve())
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
