"""Explicit managed-archive operations; private state is bound to one operation UUID."""

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path

import historical as history
from archive_profiles import GRAPH_RESOURCES, PINS
from stack import ROOT, Stack, StackError, run, save
from transport import java_env

BUILDS = ROOT / ".cache/archive-maintenance-build"
MIB = 1024**2
CONTROL = 32 * MIB


def fail(valid, category):
    if not valid:
        raise StackError("maintenance_" + category)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe(path):
    try:
        result = history.safe(path)
    except ValueError as error:
        raise StackError("maintenance_unsafe_path") from error
    fail("," not in str(result), "mount_path")
    return result


def disjoint(*paths):
    roots = [safe(p) for p in paths]
    for index, first in enumerate(roots):
        for second in roots[index + 1 :]:
            fail(
                first != second and first not in second.parents and second not in first.parents,
                "overlapping_roots",
            )
    return roots


def verify_managed(path):
    """Reject a controller or compatibility proof that differs from the executing artifact."""
    path = safe(path)
    tools = (
        "archive_maintenance",
        "archive_profiles",
        "managed_replay",
        "p05_archive",
        "replay",
        "replay_time",
        "check_replay",
        "check_datasets",
        "datasets",
        "contract_identity",
        "check_contracts",
    )
    resources = {
        "META-INF/maintenance/tools/" + name + ".py": ROOT / "tools" / (name + ".py")
        for name in tools
    }
    resources["META-INF/maintenance/uv.lock"] = ROOT / "uv.lock"
    for directory in ("archive-maintenance/v1", "replay/v1", "v1"):
        for source in (ROOT / "contracts" / directory).glob("*.schema.json"):
            resources["META-INF/maintenance/contracts/" + directory + "/" + source.name] = source
    resources["META-INF/maintenance/catalog/datasets/manifest.schema.json"] = (
        ROOT / "catalog/datasets/manifest.schema.json"
    )
    for name in ("Format", "Store", "Main"):
        resources["META-INF/maintenance/legacy/" + name + ".java"] = (
            ROOT
            / "packages/archive-writer/src/main/java/io/detectbridge/archive"
            / (name + ".java")
        )
    for graph_resource in GRAPH_RESOURCES:
        resources["archive-graph/" + graph_resource] = ROOT / graph_resource
    with zipfile.ZipFile(path) as jar:
        names = jar.namelist()
        fail(len(names) == len(set(names)), "duplicate_artifact_entries")
        for name, source in resources.items():
            fail(jar.read(name) == source.read_bytes(), "controller_binding")
    return digest(path)


def build():
    BUILDS.mkdir(parents=True, exist_ok=True)
    command = [
        ROOT / "gradlew",
        "--console=plain",
        ":archive-writer:shadowJar",
        ":historical-replay:jar",
        ":historical-replay:qualificationJar",
        ":current-replay:jar",
        ":integration-job:shadowJar",
        ":archive-maintenance:test",
        ":archive-maintenance:shadowJar",
        ":archive-maintenance:qualificationJar",
    ]
    diagnostic = BUILDS / ("build-" + uuid.uuid4().hex + ".json")
    try:
        completed = subprocess.run(
            [str(arg) for arg in command],
            env=java_env(),
            capture_output=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        history.write(
            diagnostic,
            history.encoded(
                dict(
                    version="1.0.0",
                    category="build_timeout",
                    stdout_base64=base64.b64encode(error.stdout or b"").decode(),
                    stderr_base64=base64.b64encode(error.stderr or b"").decode(),
                )
            )
            + b"\n",
        )
        history.sync(BUILDS)
        raise StackError("maintenance_build_timeout") from None
    history.write(
        diagnostic,
        history.encoded(
            dict(
                version="1.0.0",
                category="build",
                exit_code=completed.returncode,
                stdout_base64=base64.b64encode(completed.stdout).decode(),
                stderr_base64=base64.b64encode(completed.stderr).decode(),
            )
        )
        + b"\n",
    )
    history.sync(BUILDS)
    fail(completed.returncode == 0, "build_failed")
    sources = {
        "managed": ROOT / "packages/archive-maintenance/build/libs/archive-maintenance.jar",
        "probe": ROOT / "packages/archive-maintenance/build/libs/archive-maintenance-probe.jar",
    }
    for role, module in dict(
        reader="archive-writer",
        historical="historical-replay",
        current="current-replay",
        producer="integration-job",
    ).items():
        source = ROOT / "packages" / module / "build/libs" / (module + ".jar")
        fail(digest(source) == PINS[role], "legacy_artifact_changed")
        sources[role] = source
    fail(Stack().image("flink") == PINS["image"], "execution_image_changed")
    BUILDS.mkdir(parents=True, exist_ok=True)
    bundle = dict(version="1.0.0", image=PINS["image"])
    for role, source in sources.items():
        sha = digest(source)
        target = BUILDS / sha
        if target.exists():
            fail(
                target.is_file() and not target.is_symlink() and digest(target) == sha,
                "artifact_conflict",
            )
        else:
            history.write(target, source.read_bytes())
        bundle[role] = sha
    verify_managed(sources["managed"])
    history.sync(BUILDS)
    save(BUILDS / "bundle.json", bundle)
    return bundle


class Operation:
    """A held operation lease is required before orphan cleanup or any helper execution."""

    def __init__(self, control, managed_id, operation_id):
        self.control = safe(control)
        self.managed = str(uuid.UUID(managed_id))
        self.id = str(uuid.UUID(operation_id))
        fail(self.managed == managed_id and self.id == operation_id, "operation_identity")
        fail(self.control.is_dir(), "control_missing")
        self.folder = self.control / self.id
        self.fd = None
        self.name = (
            "detectbridge-managed-" + history.sha(history.encoded([self.managed, self.id]))[:32]
        )
        self.owner = dict(version="1.0.0", managed_id=self.managed, operation_id=self.id)

    def reserve(self, amount):
        fail(type(amount) is int and amount >= 0, "control_budget")
        fail(history.tree_bytes(self.control) + amount <= CONTROL, "control_budget")

    def __enter__(self):
        self.reserve(4096)
        if not self.folder.exists():
            self.folder.mkdir(mode=0o700)
            history.sync(self.control)
        fail(self.folder.is_dir() and not self.folder.is_symlink(), "operation_directory")
        self.fd = os.open(self.folder / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise StackError("maintenance_operation_locked") from error
            owner = self.folder / "owner.json"
            if owner.exists():
                fail(history.verified(owner) == self.owner, "operation_owner")
            else:
                history.contents(self.folder, {".lock"})
                history.metadata(owner, self.owner)
                history.sync(self.folder)
            self.stop_orphan()
            for temporary in self.folder.glob(".stage-*.tmp"):
                fail(
                    re.fullmatch(r"\.stage-[a-f0-9]{32}\.tmp", temporary.name)
                    and temporary.is_file()
                    and not temporary.is_symlink()
                    and temporary.stat().st_size <= 4096,
                    "stage_journal_partial",
                )
                temporary.unlink()
            history.sync(self.folder)
            return self
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def stop_orphan(self):
        fail(self.fd is not None, "operation_lease_required")
        marker = self.folder / "helper.active"
        if not marker.exists():
            return
        fail(history.document(marker) == self.owner, "helper_owner")
        response = run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "name=^/" + self.name + "$",
                "--filter",
                "label=io.detectbridge.managed.operation=" + self.id,
                "--filter",
                "label=io.detectbridge.managed.instance=" + self.managed,
            ],
            timeout=30,
        )
        ids = response.stdout.split()
        fail(all(re.fullmatch("[a-f0-9]{12,64}", item) for item in ids), "helper_identity")
        if ids:
            run(["docker", "rm", "-f", *ids], timeout=30)
        marker.unlink()
        history.sync(self.folder)

    def partial(self, root):
        fail(self.fd is not None, "operation_lease_required")
        root = safe(root)
        identity = uuid.uuid4().hex
        path = root / (".partial-" + identity)
        record = dict(
            version="1.0.0",
            managed_id=self.managed,
            operation_id=self.id,
            root=str(root),
            name=path.name,
        )
        record["checksum_sha256"] = history.sha(history.encoded(record))
        data = history.encoded(record) + b"\n"
        self.reserve(len(data))
        temporary = self.folder / (".stage-" + identity + ".tmp")
        history.write(temporary, data)
        os.rename(temporary, self.folder / ("stage-" + identity + ".json"))
        history.sync(self.folder)
        path.mkdir(mode=0o700)
        history.sync(root)
        return path

    def recover_stages(self, root):
        fail(self.fd is not None, "operation_lease_required")
        root = safe(root)
        allowed_files = {
            "refs.json",
            "rows.json",
            "export.json",
            "engine.json",
            "engine-output.json",
            "registration.json",
            "selection.json",
            "selection.sha256",
            "result.json",
            "commit.json",
            "commit.sha256",
            "run.json",
            "run.sha256",
            "progress.json",
            "failure.txt",
        }
        owned = set()
        for record_path in sorted(self.folder.glob("stage-*.json")):
            match = re.fullmatch(r"stage-([a-f0-9]{32})\.json", record_path.name)
            fail(match is not None, "stage_identity")
            assert match is not None
            record = history.document(record_path, 4096)
            fail(
                set(record)
                == {"version", "managed_id", "operation_id", "root", "name", "checksum_sha256"},
                "stage_owner",
            )
            checksum = record.pop("checksum_sha256")
            fail(
                checksum == history.sha(history.encoded(record))
                and record["version"] == "1.0.0"
                and record["managed_id"] == self.managed
                and record["operation_id"] == self.id
                and record["name"] == ".partial-" + match[1],
                "stage_owner",
            )
            if safe(record["root"]) != root:
                continue
            path = safe(root / record["name"])
            owned.add(path.name)
            if not path.exists():
                continue
            fail(path.is_dir(), "stage_directory")
            history.tree_bytes(path)
            for folder, directories, files in os.walk(path, onerror=history.walk_error):
                fail(
                    all(
                        name in {"objects", "units", "steps"}
                        and not (Path(folder) / name).is_symlink()
                        for name in directories
                    ),
                    "foreign_stage_directory",
                )
                for name in files:
                    item = safe(Path(folder) / name)
                    fail(
                        item.is_file()
                        and (
                            name in allowed_files
                            or re.fullmatch(r"[a-f0-9]{64}|[0-9]{6}\.json", name)
                        ),
                        "foreign_stage_file",
                    )
            shutil.rmtree(path)
            history.sync(root)
        fail(all(path.name in owned for path in root.glob(".partial-*")), "foreign_stage")

    def execute(self, args, timeout):
        try:
            response = subprocess.run(
                [str(a) for a in args], capture_output=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as error:
            self.failure(
                dict(
                    exit_code=None,
                    timeout=True,
                    stdout=(error.stdout or b"").decode("utf-8", "replace"),
                    stderr=(error.stderr or b"").decode("utf-8", "replace"),
                )
            )
            raise StackError("maintenance_helper_timeout") from None
        if response.returncode:
            self.failure(
                dict(
                    exit_code=response.returncode,
                    stdout=response.stdout.decode("utf-8", "replace"),
                    stderr=response.stderr.decode("utf-8", "replace"),
                )
            )
            raise StackError("maintenance_helper_failed")
        return response

    def failure(self, record):
        encoded = history.encoded(record)
        self.reserve(len(encoded) + 1)
        history.write(self.folder / ("failure-" + uuid.uuid4().hex + ".json"), encoded + b"\n")
        history.sync(self.folder)

    def container(self, image, mounts, args, timeout=90, *, network=None, crash=None):
        fail(self.fd is not None and image == PINS["image"], "helper_execution_binding")
        self.reserve(4096)
        marker = self.folder / "helper.active"
        fail(not marker.exists(), "helper_already_active")
        history.write(marker, history.encoded(self.owner) + b"\n")
        history.sync(self.folder)
        command = [
            "docker",
            "create",
            "--rm",
            "--log-driver=none",
            "--pull=never",
            "--name",
            self.name,
            "--label",
            "io.detectbridge.managed.operation=" + self.id,
            "--label",
            "io.detectbridge.managed.instance=" + self.managed,
            "--network",
            network or "none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=128",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16777216",
        ]
        for source, target, readonly in mounts:
            source = safe(source)
            command += [
                "--mount",
                f"type=bind,source={source},target={target}" + (",readonly" if readonly else ""),
            ]
        if crash is not None:
            fail(re.fullmatch("[a-z_]{1,80}", crash), "crash_phase")
            command += ["--env", "DETECTBRIDGE_ARCHIVE_CRASH=" + crash]
        try:
            created = self.execute([*command, image, *args], timeout).stdout.decode().strip()
            fail(re.fullmatch("[a-f0-9]{64}", created), "helper_identity")
            return self.execute(["docker", "start", "-a", created], timeout)
        finally:
            self.stop_orphan()


@contextlib.contextmanager
def registered(archive, catalog, control, reader, operation_id):
    archive, catalog, control = disjoint(archive, catalog, control)
    registration = history.verified(archive / "maintenance/registration.json")
    fail(
        registration["destination"] == str(archive)
        and registration["catalog_destination"] == str(catalog)
        and registration["control_destination"] == str(control),
        "registration_destinations",
    )
    fail(registration["implementation_sha256"] == verify_managed(reader), "implementation_binding")
    with Operation(control, registration["managed_id"], operation_id) as operation:
        yield registration, operation


def catalog_snapshot(catalog, registration):
    import managed_replay

    managed_replay.catalog_binding(catalog)
    fail(
        not any(p.name.startswith(".partial-") for p in catalog.iterdir()),
        "catalog_publication_pending",
    )
    pins = []
    for path in sorted((catalog / "pins").iterdir()):
        fail(re.fullmatch("[a-f0-9]{64}", path.name), "catalog_pin_identity")
        history.contents(path, {"selection.json", "selection.sha256"})
        selection = history.verified(path / "selection.json")
        history.require("selection", selection)
        fail(history.sha(history.encoded(selection)) == path.name, "catalog_pin_hash")
        fail(
            selection["archive_binding_sha256"] == registration["archive_binding_sha256"],
            "catalog_archive_binding",
        )
        for sha in (
            selection["reader_sha256"],
            selection["executor_sha256"],
            PINS["producer"],
            selection["request"]["plan_sha256"],
        ):
            history.artifact(catalog, sha)
        pins.append(dict(selection_sha256=path.name, selection=selection))
    return dict(version="1.0.0", destination=str(catalog), pins=pins)


def discard_restore_stage(root, scope, metadata):
    """Remove only a bound operation's unpublished, descriptor-named partial files."""
    root = safe(root)
    if not root.exists():
        return
    wanted = {
        entry["path"].split("/", 1)[1]: entry["length"]
        for entry in metadata["files"]
        if entry["path"].startswith(scope + "/")
    }
    directories = {""}
    for name in wanted:
        directories.update(str(parent) for parent in Path(name).parents if str(parent) != ".")
    paths = []
    for folder, children, files in os.walk(root, onerror=history.walk_error):
        folder = safe(folder)
        relative = str(folder.relative_to(root))
        fail(relative == "." or relative in directories, "foreign_restore_directory")
        for name in children:
            fail(not (folder / name).is_symlink(), "foreign_restore_directory")
        for name in files:
            path = safe(folder / name)
            logical = str(path.relative_to(root))
            fail(
                logical in wanted and path.is_file() and path.stat().st_size <= wanted[logical],
                "foreign_restore_file",
            )
            paths.append(path)
    for path in paths:
        path.unlink()
    for folder, _, _ in os.walk(root, topdown=False, onerror=history.walk_error):
        history.sync(folder)
        Path(folder).rmdir()
    history.sync(root.parent)


class ManagedArchive:
    def __init__(self, archive, catalog, control, reader=None):
        self.archive, self.catalog, self.control = disjoint(archive, catalog, control)
        registration = history.verified(self.archive / "maintenance/registration.json")
        self.reader = safe(reader or BUILDS / registration["implementation_sha256"])

    def import_p05(self, operation_id, run_dir, data_cache, *, reviewed_catalog=None):
        import managed_replay
        import p05_archive

        run_dir, data_cache = map(safe, (run_dir, data_cache))
        disjoint(self.archive, self.catalog, self.control, run_dir, data_cache)
        with registered(self.archive, self.catalog, self.control, self.reader, operation_id) as (
            registration,
            operation,
        ):
            # Reserve before the source context writes either derived index.
            index = operation.folder / "p05-index"
            existing = history.tree_bytes(index) if index.exists() else 0
            operation.reserve(max(0, p05_archive.MAX_DERIVED - existing))
            # Source lease precedes catalog lease; both remain held through durable publication.
            with p05_archive.source(
                run_dir,
                data_cache,
                registration["managed_id"],
                operation.folder / "p05-index",
                reviewed_catalog=reviewed_catalog,
            ) as prepared:
                operation.reserve(0)
                with managed_replay.catalog_lease(self.catalog) as lease:
                    session = Session(self, registration, operation, lease, None)
                    path = session.file("p05-import.json", prepared.metadata)
                    return session.command(
                        "import",
                        path,
                        run_dir,
                        data_cache,
                        operation.folder / "p05-index",
                        operation.id,
                        extra_mounts=[
                            (run_dir, str(run_dir), True),
                            (data_cache, str(data_cache), True),
                        ],
                    )

    @contextlib.contextmanager
    def session(self, operation_id, *, project=None):
        import managed_replay

        if project is not None:
            fail(
                re.fullmatch(r"detectbridge-p(?:13|14)-[a-z0-9-]+", project),
                "dedicated_project_required",
            )
            Stack(project).load()
        with registered(self.archive, self.catalog, self.control, self.reader, operation_id) as (
            registration,
            operation,
        ):
            with managed_replay.catalog_lease(self.catalog) as lease:
                yield Session(self, registration, operation, lease, project)


class Session:
    def __init__(self, client, registration, operation, lease, project):
        self.client, self.registration, self.operation = client, registration, operation
        self.lease, self.project = lease, project

    def file(self, name, value):
        fail(re.fullmatch(r"[a-z0-9-]+\.json", name), "control_filename")
        data = history.encoded(value) + b"\n"
        fail(len(data) <= 16 * MIB, "control_metadata_limit")
        path = self.operation.folder / name
        if path.exists():
            fail(history.read(path, 16 * MIB) == data, "operation_input_conflict")
        else:
            self.operation.reserve(len(data))
            history.write(path, data)
            history.sync(path.parent)
        return path

    def command(self, command, *args, crash=None, timeout=240, extra_mounts=()):
        fail(
            command
            in {
                "inspect",
                "object",
                "wire",
                "plan",
                "plan-import",
                "retire",
                "holds",
                "recover",
                "drain",
                "run",
                "import",
                "export-import",
            },
            "command",
        )
        if command in {"drain", "run"}:
            fail(self.project is not None, "broker_project_required")
        mounts = [
            (
                self.client.archive,
                str(self.client.archive),
                command in {"inspect", "object", "wire", "plan", "plan-import", "export-import"},
            ),
            (self.client.catalog, str(self.client.catalog), True),
            (self.client.control, str(self.client.control), False),
            (self.client.reader, "/managed.jar", True),
            *extra_mounts,
        ]
        response = self.operation.container(
            PINS["image"],
            mounts,
            [
                "java",
                "-Xmx320m",
                "-cp",
                "/managed.jar",
                "io.detectbridge.archive.ManagedMain",
                command,
                str(self.client.archive),
                *map(str, args),
            ],
            timeout,
            network=(self.project + "_internal") if self.project else None,
            crash=crash,
        )
        value = json.loads(response.stdout)
        fail(value.get("status") == "ok", "managed_command_failed")
        return value["result"]

    def catalog_snapshot(self):
        self.operation.recover_stages(self.client.catalog)
        return catalog_snapshot(self.client.catalog, self.registration)

    def inspect(self, broker=False):
        pins = self.catalog_snapshot()
        if broker:
            fail(self.project is not None, "broker_project_required")
        result = self.command("inspect", *(["--broker"] if broker else []))
        result["catalog_pin_count"] = len(pins["pins"])
        return result

    def plan(self, request):
        request_path = self.file("plan-request.json", request)
        snapshot = self.file("catalog-snapshot.json", self.catalog_snapshot())
        output = self.operation.folder / "plan.json"
        fail(not output.exists(), "plan_output_exists")
        self.operation.reserve(16 * MIB)
        self.command("plan", request_path, snapshot, output)
        return history.document(output)

    def plan_import(self, request):
        request_path = self.file("import-retirement-request.json", request)
        snapshot = self.file("catalog-snapshot.json", self.catalog_snapshot())
        output = self.operation.folder / "import-retirement-plan.json"
        fail(not output.exists(), "plan_output_exists")
        self.operation.reserve(16 * MIB)
        self.command("plan-import", request_path, snapshot, output)
        return history.document(output)

    def restore_p05(self, import_id, run_dir, data_cache, *, reviewed_catalog=None):
        import p05_archive

        fail(re.fullmatch("[a-f0-9]{64}", import_id), "import_identity")
        run_dir, data_cache = map(safe, (run_dir, data_cache))
        disjoint(self.client.archive, self.client.catalog, self.client.control, run_dir, data_cache)
        metadata = history.verified(self.client.archive / "imports" / import_id / "import.json")
        p05_archive.require_metadata(metadata)
        fail(
            metadata["id"] == import_id and run_dir.name == metadata["run_id"],
            "restore_run_identity",
        )
        if not (self.operation.folder / "p05-restore-request.json").exists():
            fail(not run_dir.exists() and not data_cache.exists(), "restore_destination_exists")
        self.file(
            "p05-restore-request.json",
            dict(
                import_id=import_id,
                metadata_sha256=history.sha(history.encoded(metadata)),
                run=str(run_dir),
                cache=str(data_cache),
            ),
        )
        for path in (run_dir.parent, data_cache.parent):
            fail(path.is_dir(), "restore_parent")
        run_parent = run_dir.parent / (".managed-restore-" + self.operation.id)
        run_stage = run_parent / run_dir.name
        cache_stage = data_cache.parent / (".managed-cache-" + self.operation.id)
        index = self.operation.folder / "restored-index"
        fail(not run_dir.exists() or data_cache.exists(), "restore_publication_order")
        # An existing final destination is accepted only by this exact previously bound operation.
        if run_dir.exists():
            p05_archive.validate_restored(run_dir, data_cache, metadata, index, reviewed_catalog)
            return dict(id=import_id, run_id=metadata["run_id"], restored=True)
        if not run_parent.exists():
            run_parent.mkdir(mode=0o700)
            history.sync(run_parent.parent)
        history.contents(run_parent, {run_dir.name} if run_stage.exists() else set())
        complete = False
        if run_stage.exists():
            try:
                p05_archive.validate_restored(
                    run_stage,
                    data_cache if data_cache.exists() else cache_stage,
                    metadata,
                    index,
                    reviewed_catalog,
                )
                complete = True
            except (OSError, ValueError) as error:
                self.operation.failure(
                    dict(
                        category="restore_resume_validation_failed",
                        failure_class=type(error).__name__,
                    )
                )
        if not complete:
            for root, scope in ((run_stage, "run"), (cache_stage, "cache"), (index, "index")):
                discard_restore_stage(root, scope, metadata)
            self.operation.reserve(16 * MIB)
            self.command(
                "export-import",
                import_id,
                run_stage,
                cache_stage,
                index,
                extra_mounts=[
                    (run_parent, str(run_parent), False),
                    (data_cache.parent, str(data_cache.parent), False),
                ],
            )
        p05_archive.validate_restored(
            run_stage,
            data_cache if data_cache.exists() else cache_stage,
            metadata,
            index,
            reviewed_catalog,
        )
        if not data_cache.exists():
            os.rename(cache_stage, data_cache)
            history.sync(data_cache.parent)
        elif cache_stage.exists():
            discard_restore_stage(cache_stage, "cache", metadata)
        os.rename(run_stage, run_dir)
        history.sync(run_dir.parent)
        run_parent.rmdir()
        history.sync(run_parent.parent)
        return dict(id=import_id, run_id=metadata["run_id"], restored=True)

    def retire(self, plan):
        path = self.file("apply-plan.json", plan)
        snapshot = self.file("apply-catalog-snapshot.json", self.catalog_snapshot())
        return self.command("retire", path, snapshot, self.operation.id)

    @contextlib.contextmanager
    def replay_profile(self, workspace=None):
        import current_replay
        import managed_replay

        self.operation.recover_stages(self.client.catalog)
        original_partial, original_workspace = history.partial, current_replay.workspace
        roots = {self.client.catalog}
        if workspace is not None:
            roots.add(safe(workspace))

        def partial(root):
            fail(safe(root) in roots, "stage_root")
            return self.operation.partial(root)

        try:
            history.partial = partial
            if workspace is not None:
                current_replay.workspace = self.workspace
            with managed_replay.profile(
                self.client.archive,
                self.client.catalog,
                self.client.control,
                self.client.reader,
                self.operation.folder,
                verify_managed=verify_managed,
                container_adapter=self.operation.container,
                lease=self.lease,
            ) as profile:
                yield profile
        finally:
            history.partial, current_replay.workspace = original_partial, original_workspace

    @contextlib.contextmanager
    def workspace(self, path):
        import current_replay

        root = safe(path)
        disjoint(root, self.client.archive, self.client.catalog, self.client.control)
        binding = dict(
            version="1.0.0", mode="current", destination=str(root), limits=current_replay.LIMITS
        )
        self.file("current-workspace.json", binding)
        if not root.exists():
            fail(root.parent.is_dir(), "workspace_parent")
            stage = root.parent / ("." + root.name + "-managed-current-" + self.operation.id)
            if stage.exists():
                allowed = {"catalog.json": history.encoded(binding) + b"\n"}
                allowed["catalog.sha256"] = (history.sha(allowed["catalog.json"]) + "\n").encode()
                fail(stage.is_dir() and not stage.is_symlink(), "workspace_initialization")
                for entry in stage.iterdir():
                    if entry.name in {"artifacts", "runs"}:
                        history.contents(entry, set())
                    else:
                        fail(
                            entry.name in allowed
                            and history.read(entry, len(allowed[entry.name]))
                            == allowed[entry.name][: entry.stat().st_size],
                            "workspace_initialization",
                        )
                shutil.rmtree(stage)
            stage.mkdir(mode=0o700)
            for name in ("artifacts", "runs"):
                (stage / name).mkdir(mode=0o700)
                history.sync(stage / name)
            history.metadata(stage / "catalog.json", binding)
            history.sync(stage)
            os.rename(stage, root)
            history.sync(root.parent)
        fail(history.verified(root / "catalog.json") == binding, "workspace_binding")
        descriptor = os.open(root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise StackError("maintenance_workspace_locked") from None
            fail(history.verified(root / "catalog.json") == binding, "workspace_binding")
            fail(
                not (root / "helper.active").exists() and not (root / "helper.active").is_symlink(),
                "legacy_workspace_helper",
            )
            fail(
                all(
                    p.name
                    in {"catalog.json", "catalog.sha256", ".lock", "artifacts", "runs", "failures"}
                    or re.fullmatch(r"\.partial-[a-f0-9]{32}", p.name)
                    for p in root.iterdir()
                ),
                "workspace_contents",
            )
            self.operation.recover_stages(root)
            history.reserve(root, 0)
            for folder, _, files in os.walk(root, topdown=False, onerror=history.walk_error):
                for name in files:
                    history.sync(safe(Path(folder) / name))
                history.sync(folder)
            history.sync(root.parent)
            yield root
        finally:
            os.close(descriptor)

    def seal(self, request, plan):
        with self.replay_profile() as profile:
            return profile.seal(request, plan)

    def historical(self, selection, run_id, resume=False):
        with self.replay_profile() as profile:
            return profile.historical(selection, run_id, resume)

    def current(self, workspace, request, plan, run_id, resume=False):
        with self.replay_profile(workspace) as profile:
            return profile.current(workspace, request, plan, run_id, resume)


def initialize_catalog(root, operation_id):
    """Create only this bound operation's fresh empty catalog; never clean legacy init paths."""
    import managed_replay

    root = safe(root)
    binding = dict(version="1.0.0", limits=history.LIMITS, destination=str(root))
    if not root.exists():
        fail(root.parent.is_dir(), "catalog_parent")
        stage = root.parent / ("." + root.name + "-managed-init-" + operation_id)
        if stage.exists():
            fail(stage.is_dir() and not stage.is_symlink(), "catalog_initialization")
            expected = {"catalog.json": history.encoded(binding) + b"\n"}
            expected["catalog.sha256"] = (history.sha(expected["catalog.json"]) + "\n").encode()
            for entry in stage.iterdir():
                if entry.name in {"artifacts", "pins", "runs"}:
                    history.contents(entry, set())
                else:
                    fail(
                        entry.name in expected
                        and history.read(entry, len(expected[entry.name]))
                        == expected[entry.name][: entry.stat().st_size],
                        "catalog_initialization",
                    )
            shutil.rmtree(stage)
        stage.mkdir(mode=0o700)
        for name in ("artifacts", "pins", "runs"):
            (stage / name).mkdir(mode=0o700)
            history.sync(stage / name)
        history.metadata(stage / "catalog.json", binding)
        history.sync(stage)
        os.rename(stage, root)
        history.sync(root.parent)
    managed_replay.catalog_binding(root)


def initialize(
    project, archive, catalog, control, registry, starts, provenance, managed_id, operation_id
):
    """Create a fresh explicitly bound managed root; no pre-existing archive is adopted."""
    import archive as legacy
    import managed_replay

    archive, catalog, control, registry = disjoint(archive, catalog, control, registry)
    fail(re.fullmatch(r"detectbridge-p(?:13|14)-[a-z0-9-]+", project), "dedicated_project_required")
    Stack(project).load()
    fail(
        str(uuid.UUID(managed_id)) == managed_id and str(uuid.UUID(operation_id)) == operation_id,
        "initialization_identity",
    )
    bundle = history.document(BUILDS / "bundle.json")
    reader = safe(BUILDS / bundle["managed"])
    fail(
        verify_managed(reader) == bundle["managed"] and bundle["image"] == PINS["image"],
        "initialization_build",
    )
    request = dict(starts=starts, provenance=provenance, limits=legacy.LIMITS)
    objects = []
    total = 0
    for path in sorted(registry.iterdir()):
        fail(
            path.is_file() and not path.is_symlink() and re.fullmatch("[a-f0-9]{64}", path.name),
            "registry",
        )
        fail(path.stat().st_size <= 32 * MIB and digest(path) == path.name, "registry")
        total += path.stat().st_size
        objects.append(path.name)
    fail(len(objects) <= 128 and total <= 64 * MIB and set(provenance) <= set(objects), "registry")
    state = dict(
        version="1.0.0",
        managed_id=managed_id,
        operation_id=operation_id,
        project=project,
        archive=str(archive),
        catalog=str(catalog),
        control=str(control),
        registry=str(registry),
        objects=objects,
        request=request,
        implementation_sha256=bundle["managed"],
    )
    if archive.exists():
        fail(control.is_dir() and catalog.is_dir(), "registered_state_missing")
    if not control.exists():
        control.mkdir(mode=0o700)
        history.metadata(control / "initialization.json", state)
        history.sync(control)
        history.sync(control.parent)
    fail(history.verified(control / "initialization.json") == state, "initialization_conflict")
    with Operation(control, managed_id, operation_id) as operation:
        initialize_catalog(catalog, operation_id)
        with managed_replay.catalog_lease(catalog):
            if not archive.exists():
                for name in ("artifacts", "pins", "runs"):
                    history.contents(catalog / name, set())
            registration = dict(
                version="1.0.0",
                profile="archive-managed/1.0.0",
                managed_id=managed_id,
                archive_binding_sha256="0" * 64,
                implementation_sha256=bundle["managed"],
                destination=str(archive),
                catalog_destination=str(catalog),
                control_destination=str(control),
                group="detectbridge-archive-managed-v1-" + managed_id,
                limits=dict(
                    maintenance_reserve_bytes=64 * MIB,
                    control_bytes=CONTROL,
                    metadata_bytes=16 * MIB,
                    plan_segments=256,
                    scan_rows=65536,
                    identity_tokens=262144,
                    source_fingerprints=131072,
                ),
                origin=dict(kind="fresh", source_scope_sha256=None),
            )
            for name, value in (
                ("init-request.json", request),
                ("init-registration.json", registration),
            ):
                path = operation.folder / name
                data = history.encoded(value) + b"\n"
                if path.exists():
                    fail(history.read(path, MIB) == data, "initialization_conflict")
                else:
                    operation.reserve(len(data))
                    history.write(path, data)
            if archive.exists():
                existing = history.verified(archive / "maintenance/registration.json")
                fail(
                    all(
                        existing[key] == registration[key]
                        for key in registration
                        if key != "archive_binding_sha256"
                    ),
                    "initialization_conflict",
                )
            operation.container(
                PINS["image"],
                [
                    (archive.parent, str(archive.parent), False),
                    (control, str(control), False),
                    (registry, str(registry), True),
                    (reader, "/managed.jar", True),
                ],
                [
                    "java",
                    "-Xmx320m",
                    "-cp",
                    "/managed.jar",
                    "io.detectbridge.archive.ManagedMain",
                    "init",
                    str(archive),
                    "kafka:9092",
                    str(operation.folder / "init-request.json"),
                    str(registry),
                    str(operation.folder / "init-registration.json"),
                    operation_id,
                ],
                240,
                network=project + "_internal",
            )
    return ManagedArchive(archive, catalog, control, reader)


def clone_archive(source, archive, catalog, control, managed_id, operation_id):
    import managed_replay

    source, archive, catalog, control = disjoint(source, archive, catalog, control)
    fail(
        str(uuid.UUID(managed_id)) == managed_id and str(uuid.UUID(operation_id)) == operation_id,
        "initialization_identity",
    )
    bundle = history.document(BUILDS / "bundle.json")
    reader = safe(BUILDS / bundle["managed"])
    fail(verify_managed(reader) == bundle["managed"], "initialization_build")
    creator = history.verified(source / "archive.json")
    state = dict(
        version="1.0.0",
        kind="clone",
        managed_id=managed_id,
        operation_id=operation_id,
        source=str(source),
        source_binding_sha256=history.sha(history.encoded(creator)),
        archive=str(archive),
        catalog=str(catalog),
        control=str(control),
        implementation_sha256=bundle["managed"],
    )
    if archive.exists():
        fail(catalog.is_dir() and control.is_dir(), "registered_state_missing")
    if not control.exists():
        control.mkdir(mode=0o700)
        history.metadata(control / "initialization.json", state)
        history.sync(control)
        history.sync(control.parent)
    fail(history.verified(control / "initialization.json") == state, "initialization_conflict")
    with Operation(control, managed_id, operation_id) as operation:
        initialize_catalog(catalog, operation_id)
        with managed_replay.catalog_lease(catalog):
            if not archive.exists():
                for name in ("artifacts", "pins", "runs"):
                    history.contents(catalog / name, set())
            registration = dict(
                version="1.0.0",
                profile="archive-managed/1.0.0",
                managed_id=managed_id,
                archive_binding_sha256="0" * 64,
                implementation_sha256=bundle["managed"],
                destination=str(archive),
                catalog_destination=str(catalog),
                control_destination=str(control),
                group="detectbridge-archive-managed-v1-" + managed_id,
                limits=dict(
                    maintenance_reserve_bytes=64 * MIB,
                    control_bytes=CONTROL,
                    metadata_bytes=16 * MIB,
                    plan_segments=256,
                    scan_rows=65536,
                    identity_tokens=262144,
                    source_fingerprints=131072,
                ),
                origin=dict(kind="fresh", source_scope_sha256=None),
            )
            request = operation.folder / "clone-registration.json"
            if request.exists():
                fail(history.document(request) == registration, "initialization_conflict")
            else:
                operation.reserve(len(history.encoded(registration)) + 1)
                history.write(request, history.encoded(registration) + b"\n")
                history.sync(request.parent)
            operation.container(
                PINS["image"],
                [
                    (source, str(source), True),
                    (archive.parent, str(archive.parent), False),
                    (control, str(control), False),
                    (reader, "/managed.jar", True),
                ],
                [
                    "java",
                    "-Xmx320m",
                    "-cp",
                    "/managed.jar",
                    "io.detectbridge.archive.ManagedMain",
                    "clone",
                    str(archive),
                    str(source),
                    str(request),
                    operation_id,
                ],
                240,
            )
    return ManagedArchive(archive, catalog, control, reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    actions = (
        "inspect",
        "drain",
        "recover",
        "plan",
        "plan-import",
        "retire",
        "holds",
        "seal",
        "historical",
        "current",
        "import-p05",
        "restore-p05",
    )
    for action in actions:
        command = sub.add_parser(action)
        for name in ("archive", "catalog", "control"):
            command.add_argument("--" + name, type=Path, required=True)
        command.add_argument("--operation", required=True)
        command.add_argument("--reader", type=Path)
        if action in {"inspect", "drain"}:
            command.add_argument("--project")
        if action in {"plan", "plan-import", "retire", "holds", "seal", "current"}:
            command.add_argument("--request", type=Path, required=True)
        if action in {"seal", "current"}:
            command.add_argument("--plan", type=Path, required=True)
        if action in {"historical", "current"}:
            command.add_argument("--run", required=True)
            command.add_argument("--resume", action="store_true")
        if action == "historical":
            command.add_argument("--selection", required=True)
        if action == "current":
            command.add_argument("--workspace", type=Path, required=True)
        if action in {"import-p05", "restore-p05"}:
            command.add_argument("--run-dir", type=Path, required=True)
            command.add_argument("--data-cache", type=Path, required=True)
        if action == "restore-p05":
            command.add_argument("--import-id", required=True)
    command = sub.add_parser("initialize")
    for name in ("archive", "catalog", "control", "registry", "starts", "provenance"):
        command.add_argument("--" + name, type=Path, required=True)
    for name in ("project", "managed-id", "operation"):
        command.add_argument("--" + name, required=True)
    command = sub.add_parser("clone")
    for name in ("source", "archive", "catalog", "control"):
        command.add_argument("--" + name, type=Path, required=True)
    for name in ("managed-id", "operation"):
        command.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build()
        elif args.command == "clone":
            client = clone_archive(
                args.source,
                args.archive,
                args.catalog,
                args.control,
                args.managed_id,
                args.operation,
            )
            with client.session(args.operation) as session:
                result = session.inspect()
        elif args.command == "initialize":
            client = initialize(
                args.project,
                args.archive,
                args.catalog,
                args.control,
                args.registry,
                history.document(args.starts),
                history.document(args.provenance),
                args.managed_id,
                args.operation,
            )
            with client.session(args.operation, project=args.project) as session:
                result = session.inspect(broker=True)
        else:
            client = ManagedArchive(args.archive, args.catalog, args.control, args.reader)
            if args.command == "import-p05":
                result = client.import_p05(args.operation, args.run_dir, args.data_cache)
                result = dict(
                    id=result["id"],
                    record_count=result["record_count"],
                    envelope_count=result["envelope_count"],
                )
            else:
                with client.session(
                    args.operation, project=getattr(args, "project", None)
                ) as session:
                    action = args.command
                    if action == "inspect":
                        result = session.inspect(broker=args.project is not None)
                    elif action in {"drain", "recover"}:
                        result = session.command(action, args.operation)
                    elif action in {"plan", "plan-import"}:
                        request = history.document(args.request)
                        result = (
                            session.plan(request)
                            if action == "plan"
                            else session.plan_import(request)
                        )
                        result = dict(
                            plan_sha256=history.sha(history.encoded(result)),
                            segments=len(result["candidates"]),
                            imports=len(result["imports"]),
                        )
                    elif action == "retire":
                        result = session.retire(history.document(args.request))
                    elif action == "holds":
                        result = session.command(
                            "holds",
                            session.file("holds-request.json", history.document(args.request)),
                            args.operation,
                        )
                    elif action == "seal":
                        result = session.seal(args.request, args.plan)
                    elif action == "historical":
                        result = session.historical(args.selection, args.run, args.resume)
                    elif action == "current":
                        result = session.current(
                            args.workspace, args.request, args.plan, args.run, args.resume
                        )
                    else:
                        result = session.restore_p05(args.import_id, args.run_dir, args.data_cache)
        print(json.dumps(dict(status="ok", result=result), sort_keys=True))
    except Exception as error:
        print(
            json.dumps(
                dict(
                    status="blocked",
                    category="maintenance_operation_failed",
                    failure_class=type(error).__name__,
                )
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
