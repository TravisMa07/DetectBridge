"""Recorded-accounting guards: false classification and changed originals fail closed."""

import hashlib
import tempfile
import unittest
from pathlib import Path

import qualify


class RecordingVerifierTests(unittest.TestCase):
    def test_equal_counts_cannot_substitute_a_preservation_for_expected_auth(self):
        expected = {"disposition": "normalized"}
        for published in (
            {"preservation": {"code": "unsupported_source"}},
            {"event": {}, "evaluation": {}, "preservation": {}},
            {"event": {}},
        ):
            with self.assertRaises(ValueError):
                qualify.disposition(expected, published)

    def test_unsupported_original_cannot_be_promoted_to_an_event(self):
        expected = {"disposition": "unsupported_source"}
        with self.assertRaises(ValueError):
            qualify.disposition(expected, {"event": {}, "evaluation": {}})
        with self.assertRaises(ValueError):
            qualify.disposition(expected, {"preservation": {"code": "extraction_failed"}})

    def test_original_byte_tampering_and_path_escape_are_rejected_before_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "original").write_bytes(b"changed")
            catalog = {
                "version": "1.0.0",
                "kind": "local-controlled-recording",
                "artifacts": [
                    {
                        "filename": "original",
                        "size_bytes": 7,
                        "sha256": hashlib.sha256(b"initial").hexdigest(),
                    }
                ],
            }
            with self.assertRaises(ValueError):
                qualify.artifacts(catalog, root)
            catalog["artifacts"][0]["filename"] = "../original"
            with self.assertRaises(ValueError):
                qualify.artifacts(catalog, root)


if __name__ == "__main__":
    unittest.main()
