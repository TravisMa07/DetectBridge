"""Managed lifecycle retirement must run the independently pinned verifier."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lifecycle_archive_maintenance as maintenance


class LifecycleMaintenanceTest(unittest.TestCase):
    def test_untrusted_reader_never_reaches_retirement(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            reader = root / "reader.jar"
            reader.write_bytes(b"synthetic reader artifact")
            with patch.object(maintenance.subprocess, "run") as invoke:
                with self.assertRaisesRegex(ValueError, "archive_reader_identity"):
                    maintenance.retire(root / "archive", reader, "0" * 64)
                invoke.assert_not_called()

    def test_uses_private_verified_bytes_and_propagates_hold(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            reader = root / "reader.jar"
            source = b"synthetic reader artifact"
            reader.write_bytes(source)

            def invoke(command, *, check):
                self.assertFalse(check)
                self.assertEqual(command[:2], ["java", "-jar"])
                self.assertEqual(command[3:], ["retire", str(root / "archive")])
                verified = Path(command[2])
                self.assertNotEqual(verified, reader)
                reader.write_bytes(b"changed after verification")
                self.assertEqual(verified.read_bytes(), source)
                return maintenance.subprocess.CompletedProcess(command, 2)

            with patch.object(maintenance.subprocess, "run", side_effect=invoke):
                self.assertEqual(
                    maintenance.retire(
                        root / "archive", reader, hashlib.sha256(source).hexdigest()
                    ),
                    2,
                )


if __name__ == "__main__":
    unittest.main()
