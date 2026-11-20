"""CI-01 secondary evidence failure must not replace the actual mechanics failure."""

import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle_ack_backlog as mechanics


class MechanicsEvidenceTests(unittest.TestCase):
    def test_secondary_metrics_write_preserves_original_failure_and_safe_progress(self):
        original = RuntimeError("private original failure sentinel")
        progress: dict[str, Any] = {}
        with (
            patch.object(mechanics, "_trial", side_effect=original),
            patch.object(mechanics.local, "write_exclusive", side_effect=OSError("private io")),
            self.assertRaises(RuntimeError) as caught,
        ):
            mechanics.trial(None, None, None, 8, Path("unused"), None, progress)
        self.assertIs(caught.exception, original)
        self.assertEqual(
            progress, dict(status="failed", limit=8, secondary_metrics_write_failed=True)
        )


if __name__ == "__main__":
    unittest.main()
