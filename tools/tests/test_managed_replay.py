"""Pure managed-profile/lease failure tests; no archive/JVM runtime is simulated as CI evidence."""

import copy
import fcntl
import hashlib
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import current_replay as current
import historical as history
import managed_replay as managed
from check_contracts import load_json


def hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


class ManagedReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.archive, self.catalog, self.control = [
            self.root / name for name in ("archive", "catalog", "control")
        ]
        self.archive.mkdir()
        (self.archive / "maintenance").mkdir()
        self.control.mkdir()
        self.generated = self.control / "generated"
        self.generated.mkdir()
        with history.catalog(self.catalog):
            pass
        fixture = load_json(
            managed.ROOT / "contracts/archive-maintenance/v1/fixtures/expectations.json"
        )
        self.creator = fixture["legacy"]["configuration"]
        history.metadata(self.archive / "archive.json", self.creator)
        self.reader = self.root / "managed-reader.jar"
        self.reader.write_bytes(b"synthetic managed reader; component boundary only")
        self.reader_sha = history.sha(self.reader.read_bytes())
        self.registration = dict(
            version="1.0.0",
            profile="archive-managed/1.0.0",
            managed_id="00000000-0000-4000-8000-000000000051",
            archive_binding_sha256=history.sha(history.encoded(self.creator)),
            implementation_sha256=self.reader_sha,
            destination=str(self.archive),
            catalog_destination=str(self.catalog),
            control_destination=str(self.control),
            group="detectbridge-archive-managed-v1-00000000-0000-4000-8000-000000000051",
            limits=dict(
                maintenance_reserve_bytes=67108864,
                metadata_bytes=16777216,
                plan_segments=256,
                scan_rows=65536,
                identity_tokens=262144,
                source_fingerprints=131072,
                control_bytes=33554432,
            ),
            origin=dict(kind="fresh", source_scope_sha256=None),
        )
        history.metadata(self.archive / "maintenance/registration.json", self.registration)
        self.h_build, self.c_build = self.root / "historical-build", self.root / "current-build"
        self.h_build.mkdir()
        self.c_build.mkdir()
        self.paths = {self.reader_sha: self.reader}
        for name, folder in (("historical", self.h_build), ("current", self.c_build)):
            bundle = dict(
                executor=managed.PINNED[name],
                producer=managed.PINNED["producer"],
                reader=managed.PINNED["reader"],
                image=managed.PINNED["image"],
            )
            (folder / "bundle.json").write_bytes(history.encoded(bundle) + b"\n")
            for field in (name, "producer"):
                path = folder / managed.PINNED[field]
                path.write_bytes(("synthetic " + field).encode())
                self.paths[managed.PINNED[field]] = path
        # Only the artifact verification boundary is stubbed: no fake JAR is called
        # a qualified runtime. The profile, metadata, files and flock behavior are real.
        for target, name, value in (
            (history, "BUILDS", self.h_build),
            (current, "BUILDS", self.c_build),
            (managed, "artifacts", Mock(return_value=self.paths)),
        ):
            replacement = patch.object(target, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.verify = Mock(return_value=None)
        self.adapter = Mock(return_value="operation-owned-helper")

    def profile(self, **changes):
        arguments = dict(
            archive=self.archive,
            catalog=self.catalog,
            control=self.control,
            reader_path=self.reader,
            generated_dir=self.generated,
            verify_managed=self.verify,
            container_adapter=self.adapter,
        )
        arguments.update(changes)
        return managed.profile(**arguments)

    def globals(self):
        return history.BUILDS, current.BUILDS, history.catalog, history.container

    def selection(self, reader=None):
        original = "00000000-0000-4000-8000-000000000053"
        reference = dict(topic=history.INPUT, offset=0, value_sha256="a" * 64)
        output = dict(topic=history.ROUTES["tagged"], offset=0, value_sha256="b" * 64)
        request = dict(
            version="1.0.0",
            mode="historical",
            original_run_id=original,
            producer_sha256=history.PRODUCER,
            plan_sha256="c" * 64,
            units=[
                dict(
                    id="one",
                    kind="authentication",
                    inputs=[reference],
                    outputs=[output],
                    control=None,
                    anchor=None,
                )
            ],
        )
        value = dict(
            version="1.0.0",
            mode="historical",
            profile="p13-runtime-51a984de/1.0.0",
            request=request,
            archive_binding_sha256=self.registration["archive_binding_sha256"],
            executor_sha256=managed.PINNED["historical"],
            reader_sha256=reader or self.reader_sha,
            image=managed.PINNED["image"],
            objects=[],
            references=[dict(reference=reference, wire_sha256="d" * 64)],
        )
        history.require("selection", value)
        digest = history.sha(history.encoded(value))
        directory = self.catalog / "pins" / digest
        directory.mkdir()
        history.metadata(directory / "selection.json", value)
        return digest

    def rewrite_registration(self, value):
        path = self.archive / "maintenance/registration.json"
        body = history.encoded(value) + b"\n"
        path.write_bytes(body)
        path.with_suffix(".sha256").write_text(history.sha(body) + "\n")

    def test_scoped_overlay_delegation_and_exact_default_restoration(self):
        baseline = self.globals()
        before = hashes(self.h_build), hashes(self.c_build)
        selection = self.selection()
        request = self.root / "current-request.json"
        request.write_bytes(history.encoded(dict(selection_sha256=selection)))

        def delegate(*args, **kwargs):
            with history.catalog(self.catalog) as root:
                self.assertEqual(root, self.catalog)
            self.assertEqual(
                history.document(history.BUILDS / "bundle.json")["reader"], self.reader_sha
            )
            self.assertEqual(
                history.document(current.BUILDS / "bundle.json")["reader"], self.reader_sha
            )
            self.assertEqual(
                history.BUILDS / managed.PINNED["producer"], self.paths[managed.PINNED["producer"]]
            )
            self.assertEqual(history.container("image", [], []), "operation-owned-helper")
            return dict(delegated=True)

        with (
            patch.object(history, "seal", side_effect=delegate),
            patch.object(history, "replay", side_effect=delegate),
            patch.object(current, "replay", side_effect=delegate),
        ):
            with self.profile() as session:
                self.assertEqual(session.seal("request", "plan"), dict(delegated=True))
                self.assertEqual(session.historical(selection, "run", True), dict(delegated=True))
                self.assertEqual(
                    session.current(self.root / "workspace", request, "plan", "run", True),
                    dict(delegated=True),
                )
                manifest = history.BUILDS / "bundle.json"
                self.assertTrue(manifest.is_file())
                self.assertFalse(manifest.is_symlink())
            self.assertFalse(manifest.exists())
        self.assertEqual(self.globals(), baseline)
        self.assertEqual((hashes(self.h_build), hashes(self.c_build)), before)
        self.assertEqual(list(self.generated.iterdir()), [])
        with self.assertRaisesRegex(ValueError, "inactive_profile"):
            session.seal("request", "plan")

    def test_caller_failure_and_constructor_failure_restore_every_global(self):
        baseline = self.globals()
        with self.assertRaisesRegex(RuntimeError, "caller failure"):
            with self.profile():
                raise RuntimeError("caller failure")
        self.assertEqual(self.globals(), baseline)
        with patch.object(managed, "Profile", side_effect=RuntimeError("constructor failure")):
            with self.assertRaisesRegex(RuntimeError, "constructor failure"):
                with self.profile():
                    self.fail("constructor unexpectedly succeeded")
        self.assertEqual(self.globals(), baseline)
        self.assertEqual(list(self.generated.iterdir()), [])
        with self.profile():
            pass

    def test_only_live_exact_catalog_lease_can_be_reused(self):
        with managed.catalog_lease(self.catalog) as lease:
            with self.profile(lease=lease):
                with history.catalog(self.catalog) as root:
                    self.assertEqual(root, lease.root)
                with self.assertRaisesRegex(ValueError, "catalog_lease_root"):
                    with history.catalog(self.root / "typo"):
                        self.fail("foreign catalog lease bypass")
            with (self.catalog / ".lock").open("rb") as file:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with self.assertRaisesRegex(ValueError, "catalog_lease"):
            with self.profile(lease=lease):
                self.fail("expired lease reused")
        forged = managed.CatalogLease(self.catalog, threading.get_ident())
        with self.assertRaisesRegex(ValueError, "catalog_lease"):
            with self.profile(lease=forged):
                self.fail("forged lease reused")
        self.assertFalse((self.root / "typo").exists())

    def test_catalog_lock_never_runs_legacy_orphan_or_partial_cleanup(self):
        partial = self.catalog / (".partial-" + "a" * 32)
        partial.mkdir()
        (partial / "unknown-private-data").write_bytes(b"keep")
        with patch.object(history, "stop_orphans", side_effect=AssertionError("legacy cleanup")):
            with managed.catalog_lease(self.catalog):
                pass
        self.assertTrue((partial / "unknown-private-data").exists())
        marker = self.catalog / "helper.active"
        marker.write_bytes(b"1.0.0\n")
        before = hashes(self.catalog)
        with patch.object(history, "stop_orphans", side_effect=AssertionError("legacy cleanup")):
            with self.assertRaisesRegex(ValueError, "legacy_helper"):
                with managed.catalog_lease(self.catalog):
                    self.fail("legacy helper adopted")
        self.assertEqual(hashes(self.catalog), before)

    def test_catalog_absence_bad_binding_symlink_and_busy_lock_fail_closed(self):
        absent = self.root / "absent"
        with self.assertRaisesRegex(ValueError, "catalog_missing"):
            with managed.catalog_lease(absent):
                self.fail("typo catalog created")
        self.assertFalse(absent.exists())
        linked = self.root / "catalog-link"
        linked.symlink_to(self.catalog, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unsafe_path"):
            with managed.catalog_lease(linked):
                self.fail("symlink catalog accepted")
        with managed.catalog_lease(self.catalog):
            with self.assertRaisesRegex(ValueError, "catalog_locked"):
                with managed.catalog_lease(self.catalog):
                    self.fail("busy lock bypassed")

    def test_registration_destinations_artifact_and_callback_are_mandatory(self):
        baseline = self.globals()
        for field, value in (
            ("destination", "/archive"),
            ("catalog_destination", "/missing"),
            ("control_destination", "/control"),
            ("implementation_sha256", "0" * 64),
        ):
            changed = copy.deepcopy(self.registration)
            changed[field] = value
            self.rewrite_registration(changed)
            with self.assertRaises(ValueError):
                with self.profile():
                    self.fail("foreign registration accepted")
            self.assertEqual(self.globals(), baseline)
        self.rewrite_registration(self.registration)
        self.verify.side_effect = ValueError("managed resource mismatch")
        with self.assertRaisesRegex(ValueError, "managed resource mismatch"):
            with self.profile():
                self.fail("resource verification bypassed")
        self.verify.side_effect = None
        self.verify.return_value = False
        with self.assertRaisesRegex(ValueError, "managed_verification"):
            with self.profile():
                self.fail("false verification accepted")
        with self.assertRaisesRegex(ValueError, "required_callbacks"):
            with self.profile(container_adapter=None):
                self.fail("legacy container fallback")
        with self.assertRaisesRegex(ValueError, "required_callbacks"):
            with self.profile(container_adapter=managed._LEGACY_CONTAINER):
                self.fail("explicit legacy container fallback")
        self.assertEqual(self.globals(), baseline)

    def test_legacy_selections_and_control_workspace_overlap_are_rejected(self):
        selection = self.selection(managed.PINNED["reader"])
        with self.profile() as session:
            with self.assertRaisesRegex(ValueError, "selection_profile"):
                session.historical(selection, "run")
            for root in (
                self.archive,
                self.catalog,
                self.control,
                self.control / "workspace",
                self.root,
            ):
                with self.assertRaisesRegex(ValueError, "workspace_overlap"):
                    session.current(root, "unread-request", "plan", "run")

    def test_thread_and_nested_profile_never_change_global_bindings(self):
        baseline = self.globals()
        errors = []

        def worker():
            try:
                with self.profile():
                    errors.append("unexpected success")
            except ValueError as error:
                errors.append(str(error))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=5)
        self.assertEqual(errors, ["managed_replay_controller_thread"])
        self.assertEqual(self.globals(), baseline)
        with self.profile():
            with self.assertRaisesRegex(ValueError, "profile_active"):
                with self.profile():
                    self.fail("nested profile adopted mutable globals")
        self.assertEqual(self.globals(), baseline)

    def test_partial_write_failure_and_control_budget_leave_defaults_intact(self):
        baseline = self.globals()
        with patch.object(history, "write", side_effect=OSError("synthetic profile write failure")):
            with self.assertRaises(OSError):
                with self.profile():
                    self.fail("profile write failure ignored")
        self.assertEqual(self.globals(), baseline)
        self.assertEqual(list(self.generated.iterdir()), [])
        original = history.tree_bytes
        with patch.object(
            history,
            "tree_bytes",
            side_effect=lambda path: 33554432 if path == self.control else original(path),
        ):
            with self.assertRaisesRegex(ValueError, "control_budget"):
                with self.profile():
                    self.fail("control budget ignored")
        self.assertEqual(self.globals(), baseline)
        self.assertEqual(list(self.generated.iterdir()), [])

    def test_legacy_bundle_drift_and_direct_artifact_corruption_are_visible(self):
        path = self.h_build / "bundle.json"
        bundle = history.document(path)
        bundle["reader"] = self.reader_sha
        path.write_bytes(history.encoded(bundle))
        with self.assertRaisesRegex(ValueError, "legacy_build_profile"):
            with self.profile():
                self.fail("managed reader silently installed as default")
        body = b"independently hashed artifact"
        digest = hashlib.sha256(body).hexdigest()
        target = self.root / digest
        target.write_bytes(body)
        self.assertEqual(managed.artifact(self.root, digest), target)
        target.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "artifact_integrity"):
            managed.artifact(self.root, digest)

    def test_cleanup_failure_still_releases_profile_guard_and_restores_globals(self):
        baseline = self.globals()
        with patch.object(managed.shutil, "rmtree", side_effect=OSError("owned cleanup failure")):
            with self.assertRaisesRegex(OSError, "owned cleanup failure"):
                with self.profile():
                    pass
        self.assertEqual(self.globals(), baseline)
        for path in self.generated.iterdir():
            managed.shutil.rmtree(path)
        with self.profile():
            pass

    def test_real_other_catalog_lease_is_not_registered_catalog_authority(self):
        other = self.root / "other-catalog"
        with history.catalog(other):
            pass
        baseline = self.globals()
        with managed.catalog_lease(other) as lease:
            with self.assertRaisesRegex(ValueError, "catalog_lease_root"):
                with self.profile(lease=lease):
                    self.fail("other catalog unlocked registered state")
        self.assertEqual(self.globals(), baseline)
        self.assertEqual(list(self.generated.iterdir()), [])

    def test_profile_overlap_outside_control_and_symlink_reader_are_no_mutation_failures(self):
        before = hashes(self.archive), hashes(self.catalog), hashes(self.control)
        baseline = self.globals()
        with self.assertRaisesRegex(ValueError, "root_overlap"):
            with self.profile(archive=self.catalog):
                self.fail("overlap accepted")
        with self.assertRaisesRegex(ValueError, "generated_root"):
            with self.profile(generated_dir=self.root):
                self.fail("profile escaped registered control")
        linked = self.root / "reader-link"
        linked.symlink_to(self.reader)
        with self.assertRaisesRegex(ValueError, "unsafe_path"):
            with self.profile(reader_path=linked):
                self.fail("symlink executable accepted")
        self.assertEqual(before, (hashes(self.archive), hashes(self.catalog), hashes(self.control)))
        self.assertEqual(self.globals(), baseline)

    def test_current_legacy_workspace_helper_is_rejected_without_orphan_cleanup(self):
        workspace = self.root / "legacy-workspace"
        workspace.mkdir()
        marker = workspace / "helper.active"
        marker.write_bytes(b"1.0.0\n")
        before = hashes(workspace)
        with (
            patch.object(current, "replay") as replay,
            patch.object(history, "stop_orphans") as cleanup,
        ):
            with self.profile() as session:
                with self.assertRaisesRegex(ValueError, "legacy_workspace_helper"):
                    session.current(workspace, "unread-request", "plan", "run")
            replay.assert_not_called()
            cleanup.assert_not_called()
        self.assertEqual(hashes(workspace), before)
        marker.unlink()
        marker.symlink_to(self.root / "absent-marker")
        with patch.object(current, "replay") as replay:
            with self.profile() as session:
                with self.assertRaisesRegex(ValueError, "legacy_workspace_helper"):
                    session.current(workspace, "unread-request", "plan", "run")
            replay.assert_not_called()
        self.assertTrue(marker.is_symlink())


if __name__ == "__main__":
    unittest.main()
