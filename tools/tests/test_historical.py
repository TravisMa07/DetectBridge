"""Behavioral contract, immutable metadata, pin conflicts and finite-storage preflight."""

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import historical as h
from check_historical import check


class HistoricalTests(unittest.TestCase):
    def request(self):
        ref = dict(topic=h.INPUT, offset=9223372036854775807, value_sha256="a" * 64)
        return dict(
            version="1.0.0",
            mode="historical",
            original_run_id="00000000-0000-4000-8000-000000000012",
            producer_sha256=h.PRODUCER,
            plan_sha256="b" * 64,
            units=[
                dict(
                    id="unit",
                    kind="windows",
                    inputs=[ref],
                    outputs=[dict(ref, topic=h.ROUTES["tagged"])],
                    anchor=None,
                    control=None,
                )
            ],
        )

    def test_frozen_source_counts_and_identity_packet(self):
        check()

    def test_unknown_modes_fractional_bool_and_unsigned_overflow_fail(self):
        h.references(self.request())
        for number in (True, 1.0, -1, 9223372036854775808):
            request = self.request()
            request["units"][0]["inputs"][0]["offset"] = number
            with self.assertRaises(ValueError):
                h.references(request)
        request = self.request()
        request["mode"] = "current"
        with self.assertRaises(ValueError):
            h.references(request)

    def test_occurrence_conflicts_and_wrong_control_order_are_explicit(self):
        request = self.request()
        request["units"].append(copy.deepcopy(request["units"][0]))
        request["units"][1]["id"] = "another"
        with self.assertRaisesRegex(ValueError, "duplicate_input_location"):
            h.references(request)
        request = self.request()
        request["units"][0]["control"] = copy.deepcopy(request["units"][0]["inputs"][0])
        with self.assertRaisesRegex(ValueError, "control_order"):
            h.references(request)

    def test_historical_consumer_classification_and_aggregate_fail_closed(self):
        from check_gate import CONDITIONAL, gate_passes
        from classify_changes import needs_historical

        for path in [
            "contracts/v1/raw-record.schema.json",
            "contracts/archive/v1/wire.schema.json",
            "packages/linux-adapters/src/main/Assembler.java",
            "packages/historical-replay/src/main/Engine.java",
        ]:
            self.assertTrue(needs_historical([path]))
        self.assertFalse(needs_historical(["docs/p14b-design.md"]))
        outputs = {field: "false" for field in CONDITIONAL.values()}
        outputs["historical"] = "true"
        needs: dict[str, Any] = {job: dict(result="skipped") for job in CONDITIONAL}
        needs.update(
            {
                name: dict(result="success")
                for name in ["classify-changes", "repository-hygiene", "secret-scan"]
            }
        )
        needs["classify-changes"]["outputs"] = outputs
        needs["historical-replay-verification"]["result"] = "success"
        self.assertTrue(gate_passes(needs))
        for result in ["failure", "cancelled", "skipped", None]:
            needs["historical-replay-verification"]["result"] = result
            self.assertFalse(gate_passes(needs))

    def test_metadata_byte_integrity_and_unsafe_roots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            p = root / "metadata.json"
            h.metadata(p, dict(value=1))
            self.assertEqual(h.verified(p), dict(value=1))
            p.write_bytes(b'{"value":2}\n')
            with self.assertRaisesRegex(ValueError, "metadata_integrity"):
                h.verified(p)
            (root / "link").symlink_to(p)
            with self.assertRaisesRegex(ValueError, "unsafe_path"):
                h.read(root / "link", 100)

    def test_exhaustion_does_not_create_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            with h.catalog(Path(folder).resolve() / "catalog") as root:
                with patch.object(
                    h.shutil, "disk_usage", return_value=type("Disk", (), dict(free=0))()
                ):
                    with self.assertRaisesRegex(ValueError, "disk_reserve"):
                        h.reserve(root, 1)
                self.assertEqual(list((root / "pins").iterdir()), [])
                self.assertEqual(list((root / "runs").iterdir()), [])

    def test_recomputed_metadata_checksums_do_not_permit_fractional_counters(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / "commit.json"
            h.metadata(path, dict(index=0.0))
            with self.assertRaisesRegex(ValueError, "metadata_integer"):
                h.verified(path)

    def test_retained_helper_diagnostics_do_not_prevent_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / "catalog"
            with h.catalog(path) as root:
                (root / "failures").mkdir()
                (root / "failures" / "diagnostic.json").write_text('{"failure":"synthetic"}\n')
            with h.catalog(path) as root:
                self.assertTrue((root / "failures" / "diagnostic.json").exists())

    def test_original_run_uuid_cannot_be_reused_by_changing_case(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.request()
            request["original_run_id"] = "ABCDEF00-0000-4000-8000-000000000012"
            selection = dict(
                version="1.0.0",
                mode="historical",
                profile="p13-runtime-51a984de/1.0.0",
                archive_binding_sha256="c" * 64,
                request=request,
                executor_sha256="d" * 64,
                reader_sha256="e" * 64,
                image="flink@sha256:" + "f" * 64,
                references=[dict(reference=request["units"][0]["inputs"][0], wire_sha256="a" * 64)],
                objects=[],
            )
            digest = h.sha(h.encoded(selection))
            path = Path(folder).resolve() / "catalog"
            with h.catalog(path) as root:
                pin = root / "pins" / digest
                pin.mkdir()
                h.metadata(pin / "selection.json", selection)
            with self.assertRaisesRegex(ValueError, "original_run_reuse"):
                h.replay(Path(folder), path, digest, request["original_run_id"].lower())

    def test_catalog_name_is_literal_when_recovering_initialization(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder).resolve()
            other = parent / ".catalog1-historical-init-abcdefgh"
            other.mkdir()
            original = other / "catalog.json"
            original.write_text('{"unrelated":"retain"}\n')
            with h.catalog(parent / "catalog[1]"):
                pass
            self.assertTrue(original.exists())

    @unittest.skipIf(os.geteuid() == 0, "Root can traverse Unix permission bits")
    def test_unreadable_directory_cannot_disappear_from_storage_accounting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            hidden = root / "hidden"
            hidden.mkdir()
            (hidden / "bytes").write_bytes(b"original")
            hidden.chmod(0)
            try:
                with self.assertRaises(PermissionError):
                    h.tree_bytes(root)
            finally:
                hidden.chmod(0o700)

    def test_foreign_checkpoint_root_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "p05-run"
            root.mkdir()
            original = root / "manifest.json"
            original.write_text('{"original":"P05"}\n')
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            with self.assertRaises((ValueError, OSError)):
                with h.catalog(root):
                    pass
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)

    def test_corrupt_artifact_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / "source"
            source.write_bytes(b"original")
            with h.catalog(root / "catalog") as catalog:
                target = h.install(catalog, source, h.sha(b"original"))
                target.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "artifact_conflict"):
                    h.install(catalog, source, h.sha(b"original"))
                self.assertEqual(target.read_bytes(), b"changed")


if __name__ == "__main__":
    unittest.main()
