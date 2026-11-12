"""Toolchain policy regressions without downloading runtimes in unit tests."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_repo import content_errors
from classify_changes import needs_toolchains
from dev import checked_digest, expect_version, npm, run


class DevelopmentTests(unittest.TestCase):
    def test_version_and_download_mismatch(self):
        expect_version("Node", "24.22.3", "24.22.3")
        with self.assertRaisesRegex(RuntimeError, "expected"):
            expect_version("Node", "22.0.0", "24.22.3")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            checked_digest(b"changed", "0" * 64)

    def test_stale_python_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            project = dest / "pyproject.toml"
            project.write_text(
                '[project]\nname="lock-smoke"\nversion="0.0.0"\nrequires-python=">=3.12"\n[tool.uv]\npackage=false\n'
            )
            subprocess.run(
                ["uv", "lock", "--offline", "--project", tmp], check=True, capture_output=True
            )
            before = (dest / "uv.lock").read_bytes()
            project.write_text(project.read_text().replace("0.0.0", "0.1.0"))
            result = subprocess.run(
                ["uv", "lock", "--check", "--offline", "--project", tmp],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lock", result.stderr.lower())
            self.assertEqual(before, (dest / "uv.lock").read_bytes())

    def test_stale_npm_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            metadata = json.dumps({"name": "lock-smoke", "version": "1.0.0"}).encode()
            with tarfile.open(dest / "smoke.tgz", "w:gz") as archive:
                member = tarfile.TarInfo("package/package.json")
                member.size = len(metadata)
                archive.addfile(member, io.BytesIO(metadata))
            (dest / "package.json").write_text(
                json.dumps(
                    {
                        "name": "test-lock",
                        "version": "1.0.0",
                        "dependencies": {"lock-smoke": "file:smoke.tgz"},
                    }
                )
            )
            options = ["--offline", "--ignore-scripts", "--cache", str(dest / "cache")]
            run(npm("install", "--package-lock-only", *options), cwd=dest, capture=True)
            lock = json.loads((dest / "package-lock.json").read_text())
            lock["packages"].pop("node_modules/lock-smoke")
            (dest / "package-lock.json").write_text(json.dumps(lock))
            result = run(npm("ci", "--dry-run", *options), cwd=dest, capture=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("in sync", result.stderr)

    def test_binary_allowlist_requires_exact_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jar = root / "gradle/wrapper/gradle-wrapper.jar"
            jar.parent.mkdir(parents=True)
            jar.write_bytes(b"\x00\xff")
            (root / "tools").mkdir()
            (root / "tools/toolchains.json").write_text(
                json.dumps({"wrapper_sha256": hashlib.sha256(jar.read_bytes()).hexdigest()})
            )
            self.assertFalse(content_errors(root, [jar.relative_to(root)]))
            jar.write_bytes(b"\x00\xfe")
            self.assertTrue(content_errors(root, [jar.relative_to(root)]))
            (root / "unapproved.bin").write_bytes(b"\x00")
            self.assertTrue(content_errors(root, [Path("unapproved.bin")]))

    def test_docs_only_and_unknown_changes(self):
        self.assertFalse(needs_toolchains(["README.md", "docs/sdlc.md", "LICENSE"]))
        for path in (
            "pyproject.toml",
            "uv.lock",
            "package-lock.json",
            "gradlew",
            "tools/dev.py",
            ".github/workflows/hygiene.yml",
            "unknown.file",
        ):
            self.assertTrue(needs_toolchains([path]))
