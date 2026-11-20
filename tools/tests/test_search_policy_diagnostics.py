"""First-party CI-02 synthetic literals; independent D09–D11 expectations."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from search_writer import SearchWriter
from stack import StackError


def diagnostic(**changes):
    value = dict(
        version="1.0.0",
        operation="failure_policy",
        intent="healthy",
        phase="readback_compare",
        alter_state="acknowledged",
        readback_state="received",
        observed_policy="block",
        readback_matches_intent=False,
        known_throw="fault_readback",
        failure_type="illegal_state",
        close_state="closed",
    )
    value.update(changes)
    return value


class PolicyDiagnosticsTests(unittest.TestCase):
    def invoke(self, stderr, returncode=1, stdout='{"status":"configured"}'):
        writer = SearchWriter("detectbridge-p13-ci02-unit")
        setattr(writer, "config", lambda: {"bundle": {"image_id": "sha256:" + "a" * 64}})
        with (
            patch(
                "search_writer.run",
                return_value=SimpleNamespace(returncode=returncode, stderr=stderr, stdout=stdout),
            ),
            patch.object(writer.transport, "remove_helper") as cleanup,
        ):
            try:
                value = writer.helper("failure-policy", '{"value":"healthy"}', timeout=90)
            except StackError as error:
                value = error
            cleanup.assert_called_once()
            return value

    def test_actual_failure_context_is_forwarded_and_legacy_string_preserved(self):
        d = diagnostic()
        error = self.invoke(
            json.dumps(
                dict(
                    status="failed",
                    category="writer_failed",
                    reason_type="IllegalStateException",
                    failure_policy=d,
                )
            )
        )
        self.assertEqual(
            "writer_helper_failure-policy_writer_failed_IllegalStateException", str(error)
        )
        self.assertEqual(d, getattr(error, "failure_policy", None))

    def test_arbitrary_legacy_text_is_suppressed(self):
        error = self.invoke('{"category":"secret_sentinel","reason_type":"SecretSentinel"}')
        self.assertEqual("writer_helper_failure-policy_unknown_unknown", str(error))

    def test_invalid_protocols_never_forward_private_fields(self):
        from search_writer import policy_helper_detail, validate_policy_diagnostic

        changes: dict[str, Any]
        for changes in (
            {"intent": "secret-sentinel"},
            {"phase": []},
            {"version": "2.0.0"},
            {"readback_matches_intent": 1},
            {"known_throw": {"secret": "sentinel"}},
            {"extra": "secret"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(validate_policy_diagnostic(diagnostic(**changes)))
        base = dict(status="failed", category="writer_failed", reason_type="IllegalStateException")
        good = json.dumps(dict(base, failure_policy=diagnostic()))
        invalid = [
            good[:-1],
            good.replace('"healthy"', '"healthy", "intent":"block"'),
            good.replace('"version": "1.0.0"', '"version": "secret"'),
            good.replace('"failure_policy": {', '"failure_policy": {"secret":"sentinel",'),
            good + "\n" + good,
            "x" * 65537,
            "\n" * 129 + good,
            '{"failure_policy":' + "[" * 1500 + "0" + "]" * 1500 + "}",
            json.dumps(dict(base, failure_policy={"body": "secret" * 1000})),
            good.replace('"failed"', '["secret"]'),
        ]
        for stderr in invalid:
            with self.subTest(stderr=stderr[:80]):
                self.assertIsNone(policy_helper_detail(stderr)[2])
                error = self.invoke(stderr)
                self.assertIsNone(getattr(error, "failure_policy", None))
                self.assertNotIn("secret", str(error))
        self.assertEqual(
            ("writer_failed", "IllegalStateException", None), policy_helper_detail(json.dumps(base))
        )

    def test_configured_stdout_cannot_override_close_failure(self):
        d = diagnostic(
            phase="admin_close",
            close_state="failed",
            observed_policy="healthy",
            readback_matches_intent=True,
            known_throw="unclassified",
        )
        error = self.invoke(
            json.dumps(
                dict(
                    status="failed",
                    category="writer_failed",
                    reason_type="IllegalStateException",
                    failure_policy=d,
                )
            )
        )
        self.assertIsInstance(error, StackError)
        self.assertEqual(d, error.failure_policy)
        success = self.invoke(
            json.dumps(
                dict(
                    status="diagnostic",
                    failure_policy=diagnostic(
                        phase="completed",
                        close_state="closed",
                        observed_policy="healthy",
                        readback_matches_intent=True,
                        known_throw="none",
                        failure_type="none",
                    ),
                )
            ),
            returncode=0,
        )
        self.assertEqual("configured", success["status"])
        self.assertEqual("completed", success["failure_policy"]["phase"])

    def test_helper_timeout_keeps_owned_cleanup_and_no_context(self):
        writer = SearchWriter("detectbridge-p13-ci02-timeout")
        setattr(writer, "config", lambda: {"bundle": {"image_id": "sha256:" + "a" * 64}})
        error = StackError("command_timeout")
        with (
            patch("search_writer.run", side_effect=error),
            patch.object(writer.transport, "remove_helper") as cleanup,
        ):
            with self.assertRaises(StackError) as caught:
                writer.helper("failure-policy", '{"value":"healthy"}', timeout=90)
            self.assertIs(error, caught.exception)
            self.assertFalse(hasattr(caught.exception, "failure_policy"))
            cleanup.assert_called_once()

    def test_qualification_report_revalidates_error_context_without_raw_body(self):
        import tempfile
        from unittest.mock import MagicMock

        from search_writer_qualification import qualify

        for context in (diagnostic(), {"body": "private-secret-sentinel"}, None):
            with self.subTest(context=context), tempfile.TemporaryDirectory() as folder:
                pipeline = MagicMock()
                pipeline.stack.folder = Path(folder)
                error = StackError(
                    "writer_helper_failure-policy_writer_failed_IllegalStateException"
                )
                setattr(error, "failure_policy", context)
                pipeline.init.side_effect = error
                with (
                    patch("search_writer_qualification.ROOT", Path(folder)),
                    patch("search_writer_qualification.Integration", return_value=pipeline),
                    patch("search_writer_qualification.SearchWriter"),
                    patch("search_writer_qualification.project_lock"),
                ):
                    with self.assertRaises(StackError) as caught:
                        qualify()
                    self.assertIs(error, caught.exception)
                report = next((Path(folder) / ".cache/search-writer-reports").glob("*.json"))
                raw = report.read_text()
                value = json.loads(raw)
                self.assertEqual("failed", value["status"])
                self.assertEqual(str(error), value["category"])
                self.assertEqual(
                    context if context == diagnostic() else None, value.get("failure_policy")
                )
                self.assertNotIn("private-secret-sentinel", raw)

    def test_closed_envelopes_are_bound_to_exit_outcome(self):
        from search_writer import policy_helper_detail

        for envelope in (
            {"failure_policy": diagnostic()},
            {"status": None, "failure_policy": diagnostic()},
            {"status": "diagnostic", "failure_policy": diagnostic()},
            {"status": "failed", "failure_policy": diagnostic()},
            {"status": "failed", "category": "writer_failed", "failure_policy": diagnostic()},
        ):
            self.assertIsNone(policy_helper_detail(json.dumps(envelope))[2])
        failed = dict(
            status="failed",
            category="writer_failed",
            reason_type="IllegalStateException",
            failure_policy=diagnostic(),
        )
        self.assertIsNone(policy_helper_detail(json.dumps(failed), success=True)[2])

    def test_existing_allowlisted_category_stays_compatible(self):
        error = self.invoke(
            json.dumps(
                dict(
                    status="failed",
                    category="topic_policy_changed",
                    reason_type="IllegalStateException",
                )
            )
        )
        self.assertEqual(
            "writer_helper_failure-policy_topic_policy_changed_IllegalStateException", str(error)
        )

    def test_malformed_or_duplicate_envelope_cannot_be_hidden_by_later_valid_line(self):
        from search_writer import policy_helper_detail

        good = json.dumps(
            dict(
                status="failed",
                category="writer_failed",
                reason_type="IllegalStateException",
                failure_policy=diagnostic(),
            )
        )
        for bad in (
            '{"failure_policy":',
            '{"status":"failed","status":"failed"}',
            '{"unrecognized":"secret"}',
            "[]",
        ):
            self.assertEqual(("unknown", "unknown", None), policy_helper_detail(bad + "\n" + good))
