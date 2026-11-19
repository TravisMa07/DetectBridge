"""Scoped managed-reader profiles for immutable historical/current controllers.

The owning controller must hold its private operation lock and supply both exact
managed-JAR verification and an operation-scoped container adapter. No fallback to
legacy catalog-scoped orphan recovery is allowed here. These wrappers select an
explicit managed reader; they do not upgrade old catalogs or alter build bundles.
"""

import contextlib
import fcntl
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import current_replay as current_controller
import historical as history
from archive_profiles import PINS as PINNED
from check_contracts import StrictValidator, load_json
from jsonschema import FormatChecker

ROOT = history.ROOT
_ACTIVE_LEASES: dict[int, object] = {}
_PROFILE_LOCK = threading.Lock()
_LEGACY_CONTAINER = history.container


def fail(valid, category):
    if not valid:
        raise ValueError("managed_replay_" + category)


def main_thread():
    fail(threading.current_thread() is threading.main_thread(), "controller_thread")


@dataclass(frozen=True, eq=False)
class CatalogLease:
    root: Path
    owner: int


def live(lease: object) -> Path:
    if not isinstance(lease, CatalogLease):
        raise ValueError("managed_replay_catalog_lease")
    fail(
        _ACTIVE_LEASES.get(id(lease)) is lease and lease.owner == threading.get_ident(),
        "catalog_lease",
    )
    return lease.root


def catalog_binding(root):
    fail(root.is_dir() and (root / "catalog.json").is_file(), "catalog_missing")
    fail(
        history.verified(root / "catalog.json")
        == dict(version="1.0.0", limits=history.LIMITS, destination=str(root)),
        "catalog_binding",
    )
    fail(not (root / "helper.active").exists(), "legacy_helper")
    allowed = {"catalog.json", "catalog.sha256", ".lock", "artifacts", "pins", "runs", "failures"}
    fail(
        all(
            p.name in allowed or re.fullmatch(r"\.partial-[0-9a-f]{32}", p.name)
            for p in root.iterdir()
        ),
        "catalog_contents",
    )
    for name in ("artifacts", "pins", "runs"):
        fail(history.safe(root / name).is_dir(), "catalog_contents")
    history.reserve(root, 0)


@contextlib.contextmanager
def catalog_lease(catalog_path):
    """Acquire the exact existing catalog's flock, without cleanup or adoption."""
    main_thread()
    root = history.safe(catalog_path)
    catalog_binding(root)
    path = history.safe(root / ".lock")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    lease = CatalogLease(root, threading.get_ident())
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("managed_replay_catalog_locked") from None
        catalog_binding(root)
        _ACTIVE_LEASES[id(lease)] = lease
        yield lease
    finally:
        _ACTIVE_LEASES.pop(id(lease), None)
        os.close(descriptor)


@dataclass(frozen=True)
class BuildOverlay:
    """Resolve a tiny temporary bundle plus unchanged physical immutable artifacts."""

    manifest: Path
    artifacts: dict[str, Path]

    def __truediv__(self, name):
        fail(name == "bundle.json" or name in self.artifacts, "artifact_name")
        return self.manifest if name == "bundle.json" else self.artifacts[name]


def artifact(folder, digest):
    fail(re.fullmatch("[a-f0-9]{64}", digest) is not None, "artifact_identity")
    path = history.safe(folder / digest)
    fail(history.sha(history.read(path, 32 * history.MIB)) == digest, "artifact_integrity")
    return path


def artifacts(historical_build, current_build, reader, reader_sha):
    paths = {}
    for field in ("producer", "historical"):
        paths[PINNED[field]] = artifact(historical_build, PINNED[field])
    paths[PINNED["current"]] = artifact(current_build, PINNED["current"])
    paths[reader_sha] = reader
    history.verify_executor(paths[PINNED["historical"]])
    current_controller.verify_executor(paths[PINNED["current"]])
    return paths


def bundle_bindings(historical_build, current_build):
    for folder, executor in ((historical_build, "historical"), (current_build, "current")):
        value = history.document(folder / "bundle.json")
        fail(
            value
            == dict(
                executor=PINNED[executor],
                producer=PINNED["producer"],
                reader=PINNED["reader"],
                image=PINNED["image"],
            ),
            "legacy_build_profile",
        )


def registration(archive, catalog, control, reader, verify_managed):
    document = history.verified(archive / "maintenance/registration.json")
    schema = load_json(ROOT / "contracts/archive-maintenance/v1/registration.schema.json")
    fail(
        next(StrictValidator(schema, format_checker=FormatChecker()).iter_errors(document), None)
        is None,
        "registration_schema",
    )
    fail(
        (document["destination"], document["catalog_destination"], document["control_destination"])
        == (str(archive), str(catalog), str(control)),
        "registration_destination",
    )
    fail(
        document["group"] == "detectbridge-archive-managed-v1-" + document["managed_id"],
        "registration_group",
    )
    creator = history.verified(archive / "archive.json")
    fail(
        history.sha(history.encoded(creator)) == document["archive_binding_sha256"],
        "archive_binding",
    )
    reader_sha = history.sha(history.read(reader, 32 * history.MIB))
    fail(
        reader_sha == document["implementation_sha256"] and reader_sha != PINNED["reader"],
        "managed_artifact",
    )
    fail(verify_managed(reader) is not False, "managed_verification")
    return document


class Profile:
    def __init__(self, archive, catalog, control, reader, lease, verify_managed, expected):
        self.archive, self.catalog, self.control = archive, catalog, control
        self.reader, self.lease, self.verify_managed = reader, lease, verify_managed
        self.expected, self.active = expected, True

    def check(self):
        main_thread()
        fail(self.active and live(self.lease) == self.catalog, "inactive_profile")
        fail(
            registration(self.archive, self.catalog, self.control, self.reader, self.verify_managed)
            == self.expected,
            "registration_changed",
        )

    def selection(self, selection_hash):
        self.check()
        fail(re.fullmatch("[0-9a-f]{64}", selection_hash) is not None, "selection_identity")
        selection = history.verified(self.catalog / "pins" / selection_hash / "selection.json")
        history.require("selection", selection)
        fail(history.sha(history.encoded(selection)) == selection_hash, "selection_integrity")
        fail(
            selection["reader_sha256"] == self.expected["implementation_sha256"]
            and selection["executor_sha256"] == PINNED["historical"]
            and selection["image"] == PINNED["image"]
            and selection["archive_binding_sha256"] == self.expected["archive_binding_sha256"],
            "selection_profile",
        )

    def seal(self, request, plan):
        self.check()
        return history.seal(self.archive, self.catalog, request, plan)

    def historical(self, selection, run, resume=False):
        self.selection(selection)
        return history.replay(self.archive, self.catalog, selection, run, resume)

    def current(self, workspace, request, plan, run, resume=False):
        self.check()
        workspace = history.safe(workspace)
        fail(
            all(
                workspace != root
                and workspace not in root.parents
                and root not in workspace.parents
                for root in (self.archive, self.catalog, self.control)
            ),
            "workspace_overlap",
        )
        marker = workspace / "helper.active"
        fail(not marker.exists() and not marker.is_symlink(), "legacy_workspace_helper")
        value = history.document(request, history.MIB)
        self.selection(value["selection_sha256"])
        return current_controller.replay(
            self.archive, self.catalog, workspace, request, plan, run, resume
        )


@contextlib.contextmanager
def profile(
    archive,
    catalog,
    control,
    reader_path,
    generated_dir,
    *,
    verify_managed,
    container_adapter,
    lease=None,
):
    """Select one operation's managed reader and restore every global on any exit.

    generated_dir must be an existing private directory below registered control.
    Callbacks must verify the exact managed executable/controller resources and run
    helpers under the owning operation's lock/UUID. No Docker helper is run directly.
    """
    main_thread()
    fail(
        callable(verify_managed)
        and callable(container_adapter)
        and container_adapter is not _LEGACY_CONTAINER,
        "required_callbacks",
    )
    fail(_PROFILE_LOCK.acquire(blocking=False), "profile_active")
    temporary = None
    session = None
    try:
        archive, catalog, control, reader, generated = map(
            history.safe, (archive, catalog, control, reader_path, generated_dir)
        )
        roots = (archive, catalog, control)
        fail(
            all(
                a != b and a not in b.parents and b not in a.parents
                for i, a in enumerate(roots)
                for b in roots[i + 1 :]
            ),
            "root_overlap",
        )
        fail(archive.is_dir() and control.is_dir(), "registered_root_missing")
        fail(generated.is_dir() and control in generated.parents, "generated_root")
        expected = registration(archive, catalog, control, reader, verify_managed)
        old_h, old_c = history.BUILDS, current_controller.BUILDS
        bundle_bindings(old_h, old_c)
        paths = artifacts(old_h, old_c, reader, expected["implementation_sha256"])
        manifests = {
            name: dict(
                executor=PINNED[name],
                producer=PINNED["producer"],
                reader=expected["implementation_sha256"],
                image=PINNED["image"],
            )
            for name in ("historical", "current")
        }
        size = sum(len(history.encoded(value)) + 1 for value in manifests.values())
        fail(
            history.tree_bytes(control) + size + history.MIB <= expected["limits"]["control_bytes"],
            "control_budget",
        )
        fail(
            shutil.disk_usage(control).free - size >= history.LIMITS["reserve_bytes"],
            "disk_reserve",
        )
        with contextlib.ExitStack() as stack:
            owned = stack.enter_context(catalog_lease(catalog)) if lease is None else lease
            fail(live(owned) == catalog, "catalog_lease_root")
            temporary = Path(tempfile.mkdtemp(prefix="replay-profile-", dir=generated))
            for name, manifest in manifests.items():
                history.write(temporary / (name + ".json"), history.encoded(manifest) + b"\n")
            history.sync(temporary)
            h_overlay = BuildOverlay(temporary / "historical.json", paths)
            c_overlay = BuildOverlay(temporary / "current.json", paths)
            old_catalog, old_container = history.catalog, history.container

            @contextlib.contextmanager
            def reuse(path):
                fail(history.safe(path) == live(owned), "catalog_lease_root")
                yield catalog

            try:
                setattr(history, "BUILDS", h_overlay)
                setattr(current_controller, "BUILDS", c_overlay)
                history.catalog, history.container = reuse, container_adapter
                session = Profile(
                    archive, catalog, control, reader, owned, verify_managed, expected
                )
                yield session
            finally:
                if session is not None:
                    session.active = False
                setattr(history, "BUILDS", old_h)
                setattr(current_controller, "BUILDS", old_c)
                history.catalog, history.container = old_catalog, old_container

    finally:
        try:
            if temporary is not None:
                shutil.rmtree(temporary)
        finally:
            _PROFILE_LOCK.release()
