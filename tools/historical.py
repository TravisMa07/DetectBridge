"""Pinned original-membership historical replay; private local catalog and isolated JVMs."""

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from check_contracts import StrictValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker
from stack import ROOT, Stack
from transport import java_env

PRODUCER = "51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d"
MIB = 1024**2
LIMITS = dict(storage_bytes=512 * MIB, reserve_bytes=128 * MIB)
SCHEMAS = ROOT / "contracts/historical-replay/v1"
BUILDS = ROOT / ".cache/historical-build"
INPUT = "detectbridge.integration.input.v1"
ROUTES = dict(
    tagged="detectbridge.tagged-events.v1",
    detection="detectbridge.detections.v1",
    processing="detectbridge.processing-diagnostics.v1",
    manifest="detectbridge.integration.manifests.v1",
    preservation="detectbridge.integration.preservation.v1",
)


def HOOK(phase):
    return None


def fail(valid, category):
    if not valid:
        raise ValueError("historical_" + category)


def encoded(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(kind, value):
    schema = load_json(SCHEMAS / (kind + ".schema.json"))
    Draft202012Validator.check_schema(schema)
    fail(
        not list(StrictValidator(schema, format_checker=FormatChecker()).iter_errors(value)),
        "schema_" + kind,
    )


def safe(path):
    path = Path(os.path.abspath(path))
    fail(all(not p.is_symlink() for p in (path, *path.parents)), "unsafe_path")
    return path


def read(path, cap):
    path = safe(path)
    fail(path.is_file() and path.stat().st_size <= cap, "file_limit")
    with path.open("rb") as file:
        data = file.read(cap + 1)
    fail(len(data) <= cap, "file_limit")
    return data


def document(path, cap=16 * MIB):
    data = read(path, cap)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            fail(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("historical_non_json_number")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, data, phase="file"):
    fd = os.open(safe(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as file:
            middle = len(data) // 2
            file.write(data[:middle])
            file.flush()
            HOOK("during_" + phase)
            file.write(data[middle:])
            file.flush()
            HOOK("before_" + phase + "_sync")
            os.fsync(fd)
    finally:
        os.close(fd)


def metadata(path, value):
    data = encoded(value) + b"\n"
    write(path, data, "metadata")
    write(path.with_suffix(".sha256"), (sha(data) + "\n").encode())


def verified(path, cap=16 * MIB):
    data = read(path, cap)
    fail(read(path.with_suffix(".sha256"), 65) == (sha(data) + "\n").encode(), "metadata_integrity")
    value = document(path, cap)

    def integers(node):
        if isinstance(node, dict):
            for item in node.values():
                integers(item)
        elif isinstance(node, list):
            for item in node:
                integers(item)
        elif isinstance(node, (int, float)):
            fail(type(node) is int and -(2**63) <= node <= 2**63 - 1, "metadata_integer")

    integers(value)
    fail(data == encoded(value) + b"\n", "noncanonical_metadata")
    return value


def contents(path, names):
    fail({p.name for p in safe(path).iterdir()} == set(names), "unexpected_contents")


def walk_error(error):
    raise error


def tree_bytes(path):
    total = 0
    for folder, dirs, files in os.walk(safe(path), followlinks=False, onerror=walk_error):
        for name in dirs:
            fail(not (Path(folder) / name).is_symlink(), "unsafe_path")
        for name in files:
            p = safe(Path(folder) / name)
            fail(stat.S_ISREG(p.stat(follow_symlinks=False).st_mode), "unsafe_file")
            total += p.stat().st_size
    return total


def reserve(root, amount):
    fail(tree_bytes(root) + amount <= LIMITS["storage_bytes"], "storage_budget")
    fail(shutil.disk_usage(root).free - amount >= LIMITS["reserve_bytes"], "disk_reserve")


def partial(root):
    p = root / (".partial-" + uuid.uuid4().hex)
    p.mkdir(mode=0o700)
    sync(root)
    return p


def publish(stage, destination):
    sync(stage)
    HOOK("before_publication")
    fail(not destination.exists(), "publication_conflict")
    os.rename(stage, destination)
    HOOK("after_publication")
    sync(destination.parent)
    HOOK("after_directory_sync")


@contextlib.contextmanager
def catalog(path):
    root = safe(path)
    if not root.exists():
        prefix = "." + root.name + "-historical-init-"
        for old in root.parent.iterdir():
            if not old.name.startswith(prefix):
                continue
            fail(old.is_dir() and not old.is_symlink(), "unsafe_initialization")
            tree_bytes(old)
            fail(
                all(
                    p.name in {"catalog.json", "catalog.sha256", "artifacts", "pins", "runs"}
                    for p in old.iterdir()
                ),
                "unknown_initialization",
            )
            for name in ("artifacts", "pins", "runs"):
                if (old / name).exists():
                    contents(old / name, set())
            shutil.rmtree(old)
        stage = Path(tempfile.mkdtemp(prefix=prefix, dir=root.parent))
        for name in ("artifacts", "pins", "runs"):
            (stage / name).mkdir(mode=0o700)
            sync(stage / name)
        metadata(
            stage / "catalog.json", dict(version="1.0.0", limits=LIMITS, destination=str(root))
        )
        sync(stage)
        os.rename(stage, root)
        sync(root.parent)
    # An existing foreign checkpoint/evidence root must remain byte-for-byte untouched.
    fail(
        verified(root / "catalog.json")
        == dict(version="1.0.0", limits=LIMITS, destination=str(root)),
        "catalog_binding",
    )
    fd = os.open(root / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fail(
            verified(root / "catalog.json")
            == dict(version="1.0.0", limits=LIMITS, destination=str(root)),
            "catalog_binding",
        )
        fail(
            all(
                p.name
                in {
                    "catalog.json",
                    "catalog.sha256",
                    ".lock",
                    "artifacts",
                    "pins",
                    "runs",
                    "failures",
                    "helper.active",
                }
                or re.fullmatch(r"\.partial-[0-9a-f]{32}", p.name)
                for p in root.iterdir()
            ),
            "catalog_contents",
        )
        stop_orphans(root)
        reserve(root, 0)
        for p in root.glob(".partial-*"):
            tree_bytes(p)
            allowed = {
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
            }
            for folder, _, files in os.walk(p, onerror=walk_error):
                for name in files:
                    fail(name in allowed or re.fullmatch("[0-9a-f]{64}", name), "unknown_partial")
            shutil.rmtree(p)
        for folder, _, _ in os.walk(root, topdown=False, onerror=walk_error):
            sync(folder)
        sync(root.parent)
        yield root
    finally:
        os.close(fd)


def helper_name(root):
    return "detectbridge-history-" + sha(str(root).encode())[:24]


def stop_orphans(root):
    marker = root / "helper.active"
    if not marker.exists():
        return
    read(marker, 16)
    name = helper_name(root)
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            "name=^/" + name + "$",
            "--filter",
            "label=io.detectbridge.historical.catalog=" + sha(str(root).encode()),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    ids = result.stdout.decode().split()
    fail(all(re.fullmatch("[0-9a-f]{12,64}", i) for i in ids), "helper_identity")
    if ids:
        subprocess.run(["docker", "rm", "-f", *ids], capture_output=True, check=True, timeout=30)
    marker.unlink()
    sync(root)


def command(args, timeout=90, diagnostics=None):
    result = subprocess.run(
        [str(a) for a in args], capture_output=True, timeout=timeout, check=False
    )
    if result.returncode and diagnostics is not None:
        record = encoded(
            dict(
                exit_code=result.returncode,
                stdout=result.stdout.decode("utf-8", "replace"),
                stderr=result.stderr.decode("utf-8", "replace"),
            )
        )
        for ancestor in (diagnostics, *diagnostics.parents):
            if (ancestor / "catalog.json").is_file():
                reserve(ancestor, len(record) + MIB)
                directory = ancestor / "failures"
                if not directory.exists():
                    directory.mkdir(mode=0o700)
                    sync(ancestor)
                write(directory / (uuid.uuid4().hex + ".json"), record)
                sync(directory)
                break
        else:
            write(diagnostics / ("helper-failure-" + uuid.uuid4().hex + ".json"), record)
    fail(result.returncode == 0, "helper_failed")
    return result


def container(image, mounts, args, timeout=90):
    fail(image == Stack().image("flink"), "unsupported_image")
    cmd = [
        "docker",
        "create",
        "--rm",
        "--log-driver=none",
        "--pull=never",
        "--network=none",
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
        fail("," not in str(source), "mount_path")
        cmd += [
            "--mount",
            f"type=bind,source={source},target={target}" + (",readonly" if readonly else ""),
        ]
    diagnostics = next((safe(source) for source, _, readonly in mounts if not readonly), None)
    owner = (
        next(
            (p for p in (diagnostics, *diagnostics.parents) if (p / "catalog.json").is_file()), None
        )
        if diagnostics
        else None
    )
    if owner:
        marker = owner / "helper.active"
        write(marker, b"1.0.0\n")
        sync(owner)
        cmd += [
            "--name",
            helper_name(owner),
            "--label",
            "io.detectbridge.historical.catalog=" + sha(str(owner).encode()),
        ]
    created = None
    try:
        created = command([*cmd, image, *args], timeout, diagnostics).stdout.decode().strip()
        fail(re.fullmatch("[0-9a-f]{64}", created) is not None, "helper_identity")
        command(["docker", "start", "-a", created], timeout, diagnostics)
    finally:
        if owner:
            stop_orphans(owner)
        elif created:
            subprocess.run(
                ["docker", "rm", "-f", created], capture_output=True, check=False, timeout=30
            )


def build():
    from integration_cases import prepare

    prepare()
    subprocess.run(
        [
            str(ROOT / "gradlew"),
            "--console=plain",
            ":integration-job:shadowJar",
            ":archive-writer:shadowJar",
            ":historical-replay:jar",
            ":historical-replay:qualificationJar",
            ":archive-writer:qualificationJar",
        ],
        env=java_env(),
        check=True,
    )
    image = Stack().image("flink")
    repository, digest = image.split("@")
    local = repository.rsplit(":", 1)[0] + "@" + digest
    if subprocess.run(
        ["docker", "image", "inspect", local], capture_output=True, check=False
    ).returncode:
        subprocess.run(["docker", "pull", image], check=True, timeout=600)
    paths = dict(
        producer=ROOT / "packages/integration-job/build/libs/integration-job.jar",
        reader=ROOT / "packages/archive-writer/build/libs/archive-writer.jar",
        executor=ROOT / "packages/historical-replay/build/libs/historical-replay.jar",
    )
    hashes = {name: sha(read(p, 32 * MIB)) for name, p in paths.items()}
    fail(hashes["producer"] == PRODUCER, "unsupported_producer")
    BUILDS.mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        target = BUILDS / hashes[name]
        if target.exists():
            fail(read(target, 32 * MIB) == read(path, 32 * MIB), "artifact_conflict")
        else:
            write(target, read(path, 32 * MIB))
    bundle = {**hashes, "image": Stack().image("flink")}
    (BUILDS / "bundle.json").write_bytes(encoded(bundle) + b"\n")
    return bundle


def verify_executor(path):
    with zipfile.ZipFile(path) as jar:
        expected = {
            "META-INF/historical/tools/historical.py": Path(__file__),
            "META-INF/historical/tools/check_contracts.py": ROOT / "tools/check_contracts.py",
            "META-INF/historical/uv.lock": ROOT / "uv.lock",
            **{"META-INF/historical/schemas/" + p.name: p for p in SCHEMAS.glob("*.schema.json")},
        }
        fail(
            all(jar.read(name) == source.read_bytes() for name, source in expected.items()),
            "orchestrator_incompatible",
        )


def artifact(root, digest):
    fail(re.fullmatch("[0-9a-f]{64}", digest) is not None, "artifact_identity")
    p = root / "artifacts" / digest
    fail(sha(read(p, 32 * MIB)) == digest, "artifact_integrity")
    return p


def install(root, source, digest):
    data = read(source, 32 * MIB)
    fail(sha(data) == digest, "artifact_integrity")
    target = root / "artifacts" / digest
    if target.exists():
        fail(read(target, 32 * MIB) == data, "artifact_conflict")
    else:
        reserve(root, len(data) + MIB)
        pending = partial(root)
        write(pending / digest, data)
        sync(pending)
        os.rename(pending / digest, target)
        HOOK("after_artifact_publication")
        sync(target.parent)
        pending.rmdir()
        sync(root)
    return target


def references(request):
    require("request", request)
    refs: dict[tuple[str, int], Any] = {}
    labels, occurrences = set(), set()
    for unit in request["units"]:
        fail(unit["id"] not in labels, "duplicate_label")
        labels.add(unit["id"])
        for ref in unit["inputs"]:
            fail(ref["topic"] == INPUT, "input_topic")
            location = (ref["topic"], ref["offset"])
            fail(location not in occurrences, "duplicate_input_location")
            occurrences.add(location)
        fail(all(r["topic"] in ROUTES.values() for r in unit["outputs"]), "output_topic")
        fail(
            unit["anchor"] is None or unit["anchor"]["topic"] == ROUTES["manifest"], "anchor_topic"
        )
        fail(
            unit["control"] is None
            or (
                unit["control"]["topic"] == INPUT
                and all(unit["control"]["offset"] < r["offset"] for r in unit["inputs"])
            ),
            "control_order",
        )
        for ref in [
            *unit["inputs"],
            *unit["outputs"],
            *([unit["anchor"]] if unit["anchor"] else []),
            *([unit["control"]] if unit["control"] else []),
        ]:
            location = (ref["topic"], ref["offset"])
            fail(location not in refs or refs[location] == ref, "conflicting_reference")
            refs[location] = ref
    fail(len(refs) <= 1000, "reference_limit")
    return [refs[k] for k in sorted(refs)]


def export(root, archive, request, reader, image):
    reserve(root, 192 * MIB)
    stage = partial(root)
    write(stage / "refs.json", encoded(references(request)))
    out = stage / "objects"  # Reader owns its new output subtree.
    out.mkdir(mode=0o700)
    container(
        image,
        [
            (archive, "/archive", True),
            (stage / "refs.json", "/refs.json", True),
            (reader, "/reader.jar", True),
            (out, "/out", False),
        ],
        [
            "java",
            "-Xmx320m",
            "-cp",
            "/reader.jar",
            "io.detectbridge.archive.ReplaySource",
            "/archive",
            "/refs.json",
            "/out",
        ],
        240,
    )
    proof = document(out / "export.json")
    rows = document(out / "rows.json", 96 * MIB)
    fail(set(proof) == {"archive_binding_sha256", "references", "objects"}, "export_fields")
    fail(len(rows) == len(references(request)), "export_count")
    index = {}
    for row in rows:
        ref, wire = row["reference"], row["wire"]
        value = base64.b64decode(wire["value"], validate=True)
        fail(sha(value) == ref["value_sha256"], "wire_value_integrity")
        key = (ref["topic"], ref["offset"])
        fail(key not in index, "export_duplicate")

        def unique(pairs):
            result = {}
            for name, item in pairs:
                fail(name not in result, "duplicate_json_key")
                result[name] = item
            return result

        def fractional(_):
            raise ValueError("historical_fractional_metadata")

        index[key] = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=fractional,
            parse_float=fractional,
        )
    reserve(root, 0)
    return stage, out / "objects", proof, index


def engine(root, selection, unit, index, objects, run):
    stage = partial(root)

    def get(ref):
        return index[(ref["topic"], ref["offset"])]

    outputs = [
        dict(kind=next(k for k, v in ROUTES.items() if v == ref["topic"]), value=get(ref))
        for ref in unit["outputs"]
    ]
    payload = dict(
        original_run_id=selection["request"]["original_run_id"],
        run_id=run,
        kind=unit["kind"],
        inputs=[get(r) for r in unit["inputs"]],
        original_outputs=outputs,
        anchor=get(unit["anchor"]) if unit["anchor"] else None,
        control=get(unit["control"]) if unit["control"] else None,
        plan="/plan.json",
        plan_sha256=selection["request"]["plan_sha256"],
        objects="/objects",
    )
    verify_executor(artifact(root, selection["executor_sha256"]))
    data = encoded(payload)
    fail(len(data) <= 32 * MIB, "executor_input_limit")
    reserve(root, len(data) + 33 * MIB)
    write(stage / "engine.json", data)
    container(
        selection["image"],
        [
            (artifact(root, selection["executor_sha256"]), "/executor.jar", True),
            (artifact(root, PRODUCER), "/producer.jar", True),
            (artifact(root, payload["plan_sha256"]), "/plan.json", True),
            (objects, "/objects", True),
            (stage, "/out", False),
        ],
        [
            "java",
            "-Xmx320m",
            "-cp",
            "/executor.jar:/producer.jar:/opt/flink/lib/*",
            "io.detectbridge.history.Bootstrap",
            "/producer.jar",
            "/out/engine.json",
            "/out/engine-output.json",
        ],
    )
    value = document(stage / "engine-output.json", 32 * MIB)
    fail(set(value) == {"native", "outputs"}, "executor_output")
    shutil.rmtree(stage)
    sync(root)
    return value


def seal(archive, catalog_path, request_path, plan_path):
    request = document(request_path)
    references(request)
    bundle = document(BUILDS / "bundle.json")
    fail(bundle["producer"] == PRODUCER, "unsupported_producer")
    with catalog(catalog_path) as root:
        fail(
            sum((BUILDS / bundle[k]).stat().st_size for k in ("producer", "reader", "executor"))
            + safe(plan_path).stat().st_size
            <= 64 * MIB,
            "artifact_set_limit",
        )
        for name in ("producer", "reader", "executor"):
            install(root, BUILDS / bundle[name], bundle[name])
        install(root, plan_path, request["plan_sha256"])
        verify_executor(artifact(root, bundle["executor"]))
        stage, objects, proof, index = export(
            root, safe(archive), request, artifact(root, bundle["reader"]), bundle["image"]
        )
        selection = dict(
            version="1.0.0",
            mode="historical",
            profile="p13-runtime-51a984de/1.0.0",
            request=request,
            executor_sha256=bundle["executor"],
            reader_sha256=bundle["reader"],
            image=bundle["image"],
            **proof,
        )
        require("selection", selection)
        ids = set()
        for unit in request["units"]:
            for ref in unit["inputs"]:
                row = index[(ref["topic"], ref["offset"])]
                occurrence = row["raw"]["record_id"]
                fail(occurrence not in ids, "duplicate_occurrence")
                ids.add(occurrence)
            engine(root, selection, unit, index, objects, request["original_run_id"])
        digest = sha(encoded(selection))
        target = root / "pins" / digest
        if target.exists():
            contents(target, {"selection.json", "selection.sha256"})
            fail(verified(target / "selection.json") == selection, "pin_conflict")
        else:
            pin = partial(root)
            metadata(pin / "selection.json", selection)
            publish(pin, target)
        shutil.rmtree(stage)
        sync(root)
        return dict(
            selection_sha256=digest,
            units=len(request["units"]),
            archive_binding_sha256=proof["archive_binding_sha256"],
        )


def replay(archive, catalog_path, selection_hash, run_id, resume=False):
    fail(re.fullmatch("[0-9a-f]{64}", selection_hash) is not None, "selection_identity")
    fail(str(uuid.UUID(run_id)) == run_id, "run_identity")
    with catalog(catalog_path) as root:
        pin = root / "pins" / selection_hash
        contents(pin, {"selection.json", "selection.sha256"})
        selection = verified(pin / "selection.json")
        require("selection", selection)
        fail(sha(encoded(selection)) == selection_hash, "selection_integrity")
        request = selection["request"]
        fail(uuid.UUID(run_id) != uuid.UUID(request["original_run_id"]), "original_run_reuse")
        for digest in [
            selection["executor_sha256"],
            selection["reader_sha256"],
            PRODUCER,
            request["plan_sha256"],
        ]:
            artifact(root, digest)
        verify_executor(artifact(root, selection["executor_sha256"]))
        destination = root / "runs" / run_id
        spec = dict(
            version="1.0.0",
            mode="historical",
            run_id=run_id,
            selection_sha256=selection_hash,
            executor_sha256=selection["executor_sha256"],
            producer_sha256=PRODUCER,
            plan_sha256=request["plan_sha256"],
            reader_sha256=selection["reader_sha256"],
            image=selection["image"],
            destination=str(destination),
            limits=LIMITS,
        )
        require("run", spec)
        if destination.exists():
            fail(resume, "run_exists")
            fail(
                {p.name for p in destination.iterdir()}
                in (
                    {"run.json", "run.sha256", "units"},
                    {"run.json", "run.sha256", "units", "progress.json"},
                ),
                "run_contents",
            )
            fail(verified(destination / "run.json") == spec, "resume_binding")
        else:
            fail(not resume, "run_missing")
            reserve(root, MIB)
            stage = partial(root)
            metadata(stage / "run.json", spec)
            (stage / "units").mkdir(mode=0o700)
            sync(stage / "units")
            publish(stage, destination)
        sync(destination)
        sync(destination.parent)
        stage, objects, proof, index = export(
            root,
            safe(archive),
            request,
            artifact(root, selection["reader_sha256"]),
            selection["image"],
        )
        fail(all(proof[k] == selection[k] for k in proof), "archive_selection_changed")
        units = destination / "units"
        names = sorted(p.name for p in units.iterdir())
        fail(
            names == [f"{i:06d}" for i in range(len(names))]
            and len(names) <= len(request["units"]),
            "unit_prefix",
        )
        previous = None
        for i, unit in enumerate(request["units"]):
            unit_id = sha(
                encoded(["detectbridge.historical.unit/1", run_id, selection_hash, unit["id"]])
            )
            executed = engine(root, selection, unit, index, objects, run_id)
            result = dict(
                version="1.0.0",
                mode="historical",
                selection_sha256=selection_hash,
                run_id=run_id,
                unit_id=unit_id,
                label=unit["id"],
                origin=[
                    *unit["inputs"],
                    *unit["outputs"],
                    *([unit["anchor"]] if unit["anchor"] else []),
                    *([unit["control"]] if unit["control"] else []),
                ],
                **executed,
            )
            require("result", result)
            payload = encoded(result) + b"\n"
            fail(len(payload) <= 32 * MIB, "result_limit")
            commit = dict(
                version="1.0.0",
                index=i,
                unit_id=unit_id,
                result_sha256=sha(payload),
                result_bytes=len(payload),
                previous_sha256=previous,
            )
            require("commit", commit)
            target = units / f"{i:06d}"
            if i < len(names):
                contents(target, {"result.json", "commit.json", "commit.sha256"})
                fail(
                    verified(target / "commit.json") == commit
                    and read(target / "result.json", 32 * MIB) == payload,
                    "committed_result_conflict",
                )
                sync(target)
                sync(units)
            else:
                reserve(root, len(payload) + MIB)
                pending = partial(root)
                write(pending / "result.json", payload, "payload")
                metadata(pending / "commit.json", commit)
                publish(pending, target)
                HOOK("before_advisory")
                advisory = partial(root)
                write(
                    advisory / "progress.json",
                    encoded(
                        dict(
                            version="1.0.0",
                            run_id=run_id,
                            selection_sha256=selection_hash,
                            committed_units=i + 1,
                            unit_count=len(request["units"]),
                            status="complete" if i + 1 == len(request["units"]) else "running",
                        )
                    )
                    + b"\n",
                    "advisory",
                )
                sync(advisory)
                os.replace(advisory / "progress.json", destination / "progress.json")
                HOOK("after_advisory_rename")
                sync(destination)
                advisory.rmdir()
                sync(root)
            previous = sha(encoded(commit))
        shutil.rmtree(stage)
        sync(root)
        return dict(
            run_id=run_id,
            selection_sha256=selection_hash,
            units=len(request["units"]),
            status="complete",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("build")
    for action in ("seal", "run", "resume"):
        p = sub.add_parser(action)
        p.add_argument("--archive", required=True, type=Path)
        p.add_argument("--catalog", required=True, type=Path)
        if action == "seal":
            p.add_argument("--request", required=True, type=Path)
            p.add_argument("--plan", required=True, type=Path)
        else:
            p.add_argument("--selection", required=True)
            p.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        if args.action == "build":
            result = build()
        elif args.action == "seal":
            result = seal(args.archive, args.catalog, args.request, args.plan)
        else:
            result = replay(
                args.archive, args.catalog, args.selection, args.run_id, args.action == "resume"
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as failure:
        print(
            json.dumps(
                dict(
                    status="failed",
                    category="historical_operation_failed",
                    failure_class=type(failure).__name__,
                )
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
