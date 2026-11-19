"""Operation ownership is independent of catalog and Java archive lease ownership."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_maintenance as maintenance
import historical as history
from stack import StackError

MANAGED = "00000000-0000-4000-8000-000000000061"
OPERATION = "00000000-0000-4000-8000-000000000062"


class OperationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def operation(self, identity=OPERATION):
        return maintenance.Operation(self.root, MANAGED, identity)

    def build_pointer(self):
        root = self.root / "builds"
        root.mkdir()
        history.write(
            root / "bundle.json",
            history.encoded(dict(managed="a" * 64, image=maintenance.PINS["image"])) + b"\n",
        )
        return root

    def test_live_operation_is_never_orphan_recovered(self):
        with self.operation() as first:
            history.write(first.folder / "helper.active", history.encoded(first.owner) + b"\n")
            with patch.object(maintenance, "run") as docker:
                with self.assertRaisesRegex(StackError, "operation_locked"):
                    with self.operation():
                        self.fail("live operation lease was bypassed")
                docker.assert_not_called()
            (first.folder / "helper.active").unlink()

    def test_only_exact_managed_operation_is_selected_for_orphan_cleanup(self):
        with self.operation() as operation:
            history.write(
                operation.folder / "helper.active", history.encoded(operation.owner) + b"\n"
            )
        response = type("Response", (), {"stdout": "a" * 64 + "\n"})()
        with patch.object(maintenance, "run", return_value=response) as docker:
            with self.operation():
                pass
        arguments = docker.call_args_list[0].args[0]
        self.assertIn("name=^/" + operation.name + "$", arguments)
        self.assertIn("label=io.detectbridge.managed.operation=" + OPERATION, arguments)
        self.assertIn("label=io.detectbridge.managed.instance=" + MANAGED, arguments)
        self.assertEqual(docker.call_args_list[1].args[0], ["docker", "rm", "-f", "a" * 64])

    def test_foreign_marker_fails_without_stopping_any_helper(self):
        with self.operation() as operation:
            history.write(operation.folder / "helper.active", b'{"version":"foreign"}\n')
        with patch.object(maintenance, "run") as docker:
            with self.assertRaisesRegex(StackError, "helper_owner"):
                with self.operation():
                    pass
            docker.assert_not_called()
        self.assertTrue((operation.folder / "helper.active").exists())

    def test_control_budget_is_not_increased_for_diagnostics(self):
        with self.operation() as operation:
            with patch.object(history, "tree_bytes", return_value=maintenance.CONTROL - 1):
                with self.assertRaisesRegex(StackError, "control_budget"):
                    operation.reserve(2)

    def test_no_operation_action_without_a_live_lease(self):
        operation = self.operation()
        with self.assertRaisesRegex(StackError, "operation_lease_required"):
            operation.stop_orphan()
        with self.assertRaisesRegex(StackError, "helper_execution_binding"):
            operation.container(maintenance.PINS["image"], [], [])

    def test_symlink_and_ancestor_aliases_rejected(self):
        path = self.root / "original"
        path.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(path, target_is_directory=True)
        with self.assertRaises(StackError):
            maintenance.disjoint(path, alias)
        with self.assertRaisesRegex(StackError, "overlapping_roots"):
            maintenance.disjoint(path, path / "child")

    def test_only_original_operation_can_recover_its_catalog_stage(self):
        catalog = self.root / "catalog"
        catalog.mkdir()
        with self.operation() as first:
            stage = first.partial(catalog)
            history.write(stage / "engine.json", b"{}\n")
        other = "00000000-0000-4000-8000-000000000063"
        with self.operation(other) as second:
            with self.assertRaisesRegex(StackError, "foreign_stage"):
                second.recover_stages(catalog)
        self.assertTrue((stage / "engine.json").exists())
        with self.operation() as original:
            original.recover_stages(catalog)
        self.assertFalse(stage.exists())

    def test_foreign_file_is_not_deleted_from_an_owned_stage(self):
        catalog = self.root / "catalog"
        catalog.mkdir()
        with self.operation() as operation:
            stage = operation.partial(catalog)
            history.write(stage / "foreign-evidence.txt", b"retain")
            with self.assertRaisesRegex(StackError, "foreign_stage_file"):
                operation.recover_stages(catalog)
        self.assertEqual((stage / "foreign-evidence.txt").read_bytes(), b"retain")

    def test_tampered_stage_journal_does_not_authorize_cleanup(self):
        catalog = self.root / "catalog"
        catalog.mkdir()
        with self.operation() as operation:
            stage = operation.partial(catalog)
            journal = next(operation.folder.glob("stage-*.json"))
            record = history.document(journal)
            record["root"] = str(self.root)
            journal.write_bytes(history.encoded(record) + b"\n")
            with self.assertRaisesRegex(StackError, "stage_owner"):
                operation.recover_stages(catalog)
        self.assertTrue(stage.exists())

    def test_restore_cleanup_rejects_foreign_files_before_removing_anything(self):
        root = self.root / "restore"
        root.mkdir()
        (root / "manifest.json").write_bytes(b"partial")
        (root / "foreign.bin").write_bytes(b"retain")
        metadata = dict(files=[dict(path="run/manifest.json", length=100)])
        with self.assertRaisesRegex(StackError, "foreign_restore_file"):
            maintenance.discard_restore_stage(root, "run", metadata)
        self.assertEqual((root / "manifest.json").read_bytes(), b"partial")
        self.assertEqual((root / "foreign.bin").read_bytes(), b"retain")

    def test_fresh_catalog_creation_never_cleans_an_unowned_legacy_stage(self):
        catalog = self.root / "new-catalog"
        legacy_stage = self.root / ".new-catalog-historical-init-foreign"
        legacy_stage.mkdir()
        (legacy_stage / "retain.bin").write_bytes(b"retain")
        with self.operation() as operation:
            maintenance.initialize_catalog(catalog, operation.id)
        self.assertEqual((legacy_stage / "retain.bin").read_bytes(), b"retain")
        self.assertTrue((catalog / "catalog.json").is_file())
        self.assertEqual(list((catalog / "pins").iterdir()), [])

    def test_published_root_never_recreates_missing_registered_state(self):
        archive = self.root / "archive"
        archive.mkdir()
        catalog, control, registry = [
            self.root / name for name in ("catalog", "control", "registry")
        ]
        registry.mkdir()
        with (
            patch.object(maintenance, "Stack") as stack,
            patch.object(maintenance, "verify_managed", return_value="a" * 64),
            patch.object(maintenance, "BUILDS", self.build_pointer()),
        ):
            stack.return_value.load.return_value = {}
            with self.assertRaisesRegex(StackError, "registered_state_missing"):
                maintenance.initialize(
                    "detectbridge-p14-test",
                    archive,
                    catalog,
                    control,
                    registry,
                    {},
                    [],
                    MANAGED,
                    OPERATION,
                )
        self.assertFalse(catalog.exists())
        self.assertFalse(control.exists())

    def test_unpublished_archive_requires_fresh_empty_catalog_before_helper(self):
        archive = self.root / "archive"
        catalog, control, registry = [
            self.root / name for name in ("catalog", "control", "registry")
        ]
        registry.mkdir()
        maintenance.initialize_catalog(catalog, OPERATION)
        pin = catalog / "pins" / ("a" * 64)
        pin.mkdir()
        (pin / "retain.bin").write_bytes(b"retain")
        with (
            patch.object(maintenance, "Stack"),
            patch.object(maintenance, "verify_managed", return_value="a" * 64),
            patch.object(maintenance, "BUILDS", self.build_pointer()),
            patch.object(maintenance.Operation, "container") as helper,
        ):
            with self.assertRaisesRegex(ValueError, "contents"):
                maintenance.initialize(
                    "detectbridge-p14-test",
                    archive,
                    catalog,
                    control,
                    registry,
                    {},
                    [],
                    MANAGED,
                    OPERATION,
                )
            helper.assert_not_called()
        self.assertFalse(archive.exists())
        self.assertEqual((pin / "retain.bin").read_bytes(), b"retain")


if __name__ == "__main__":
    unittest.main()
