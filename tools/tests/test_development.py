"""Toolchain policy regressions without downloading runtimes in unit tests."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_repo import content_errors
from classify_changes import needs_toolchains
from dev import checked_digest, expect_version


class DevelopmentTests(unittest.TestCase):
    def test_version_and_download_mismatch(self):
        expect_version("Node", "24.22.3", "24.22.3")
        with self.assertRaisesRegex(RuntimeError, "expected"):
            expect_version("Node", "22.0.0", "24.22.3")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            checked_digest(b"changed", "0" * 64)

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
