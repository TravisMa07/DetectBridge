"""Writer contracts, protected state, isolated credentials, and fail-closed CI."""

import base64
import copy
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import writer
from check_contracts import load_json
from check_gate import CONDITIONAL, gate_passes
from check_writer import SCHEMAS, no_refs, require, validate_overlay
from classify_changes import needs_writer
from stack import Stack, StackError


class WriterTests(unittest.TestCase):
    def test_examples_versions_types_and_closed_projection(self):
        for kind in ("configuration", "projection", "failure"):
            example = load_json(SCHEMAS / "examples" / (kind + ".json"))
            require(kind, example)
            for value in (
                {**example, "contract_version": "9.0.0"},
                {**example, "unexpected": True},
            ):
                with self.assertRaises(ValueError):
                    require(kind, value)
        projection = load_json(SCHEMAS / "examples/projection.json")
        for mutate in (
            lambda p: p.update(sequence=1.0),
            lambda p: p.update(first_observed=None),
            lambda p: p["evidence"].update(inline="sensitive"),
            lambda p: p.pop("record_id"),
            lambda p: p.pop("effective_time"),
        ):
            bad = copy.deepcopy(projection)
            mutate(bad)
            with self.assertRaises(ValueError):
                require("projection", bad)
        for reference in ("https://example.invalid/schema", "urn:unknown"):
            with self.assertRaises(ValueError):
                no_refs({"nested": [{"$ref": reference}]})

    def test_runtime_overlay_rejects_ports_admin_mounts_and_privilege(self):
        bundle = {"image_id": "sha256:" + "a" * 64}
        # The exact approved shape is loaded from a fixture shared with the generation test.
        overlay = load_json(writer.ROOT / "contracts/writer/v1/examples/overlay.json")
        validate_overlay(overlay, bundle)
        for field, value in (
            ("ports", ["9250:9250"]),
            ("privileged", True),
            ("user", "0:0"),
            ("environment", {"PASSWORD": "value"}),
            ("volumes", ["writer-admin:/secrets:ro"]),
        ):
            bad = copy.deepcopy(overlay)
            bad["services"]["writer"][field] = value
            with self.assertRaises(ValueError):
                validate_overlay(bad, bundle)

    def test_volume_secret_ownership_and_no_secret_in_command(self):
        value = cast(Any, writer.Writer("detectbridge-test-writer-unit"))
        value.stack.owned_volume = Mock()
        value.stack.image = Mock(return_value="approved@sha256:" + "a" * 64)
        secret = b"only-in-private-stdin"
        with patch.object(value.stack, "temporary_run") as execute:
            value.prepare_volume(
                "writer-secrets", {"writer-password": secret, "ca.pem": b"test-ca"}
            )
        args = execute.call_args.args[0]
        self.assertNotIn(secret.decode(), " ".join(map(str, args)))
        self.assertEqual(args[args.index("--log-driver") + 1], "none")
        blob = base64.b64decode(execute.call_args.kwargs["data"])
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            members = tar.getmembers()
            self.assertEqual({member.name for member in members}, {"writer-password", "ca.pem"})
            for member in members:
                self.assertEqual((member.uid, member.gid, member.mode), (9999, 9999, 0o400))
            extracted = tar.extractfile("writer-password")
            assert extracted is not None
            self.assertEqual(extracted.read(), secret)
        with self.assertRaises(StackError):
            value.prepare_volume("writer-secrets", {"../escape": b"bad"})

    def test_frozen_configuration_and_credentials_are_verified(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(writer, "CACHE", Path(temp)):
            value = cast(Any, writer.Writer("detectbridge-example"))
            value.folder.mkdir()
            secret = b"local-credential\n"
            (value.folder / "writer-password").write_bytes(secret)
            config = load_json(SCHEMAS / "examples/configuration.json")
            config["password_sha256"] = writer.sha(secret)
            value.stack = Mock()
            value.stack.load.return_value = {"writer_bundle": config["bundle"]}
            value.stack.folder = Path(temp) / "stack"
            (value.stack.folder / "security").mkdir(parents=True)
            (value.stack.folder / "security/ca.pem").write_bytes(b"public-ca")
            config["ca_sha256"] = writer.sha(b"public-ca")
            value.bundle = Mock(return_value=config["bundle"])
            (value.folder / "configuration.json").write_text(json.dumps(config))
            (value.folder / "configuration.sha256").write_text(writer.digest(config) + "\n")
            self.assertEqual(value.config(), config)
            (value.folder / "writer-password").write_bytes(b"changed")
            with self.assertRaisesRegex(StackError, "credential_changed"):
                value.config()
            (value.folder / "writer-password").write_bytes(secret)
            config["pipeline_id"] = "00000000-0000-4000-8000-000000000099"
            (value.folder / "configuration.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(StackError, "configuration_changed"):
                value.config()

    def test_reset_rejects_foreign_writer_metadata_before_deletion(self):
        with tempfile.TemporaryDirectory() as temp, patch("stack.ROOT", Path(temp)):
            stack = cast(Any, Stack("detectbridge-test-writer-reset"))
            stack.load = Mock(return_value={})
            folder = Path(temp) / ".cache/writer" / stack.project
            folder.mkdir(parents=True)
            (folder / "pending.json").write_text(json.dumps({"project": "detectbridge-foreign"}))
            stack.down = Mock()
            with self.assertRaisesRegex(StackError, "ownership_mismatch"):
                stack.reset(stack.project)
            stack.down.assert_not_called()
            self.assertTrue(folder.exists())

    def test_writer_ci_classification_and_gate_fail_closed(self):
        self.assertFalse(needs_writer(["README.md", "docs/writer.md"]))
        for path in (
            "packages/transport-writer/build.gradle.kts",
            "contracts/v1/common.schema.json",
            "contracts/writer/v1/configuration.schema.json",
            "tools/writer.py",
            "tools/writer_qualification.py",
            "tools/stack.py",
            "tools/transport.py",
            "settings-gradle.lockfile",
            "gradlew",
            ".github/workflows/hygiene.yml",
        ):
            self.assertTrue(needs_writer([path]), path)
        for applicable in ("true", "false"):
            for result in ("success", "failure", "cancelled", "skipped", None):
                outputs = {field: "false" for field in CONDITIONAL.values()}
                outputs["writer"] = applicable
                needs: dict[str, Any] = {name: {"result": "skipped"} for name in CONDITIONAL}
                needs.update(
                    {
                        "classify-changes": {"result": "success", "outputs": outputs},
                        "repository-hygiene": {"result": "success"},
                        "secret-scan": {"result": "success"},
                    }
                )
                needs["opensearch-writer-verification"] = {"result": result}
                expected = result == ("success" if applicable == "true" else "skipped")
                self.assertEqual(gate_passes(needs), expected)
                del outputs["writer"]
                self.assertFalse(gate_passes(needs))


if __name__ == "__main__":
    unittest.main()
