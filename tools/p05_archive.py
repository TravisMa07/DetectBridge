"""Read-only completed P05 import preparation and exact fresh-restore validation.

The caller owns archive publication and destination leases. This module acquires only
P05's original run flock, keeps it through the source context, and never executes or
repairs an original run. reviewed_catalog is injectable for pure synthetic tests only;
production callers use the current approved repository catalog without acquisition.
"""

import fcntl
import hashlib
import json
import os
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import datasets
import replay
from check_contracts import StrictValidator, load_json
from check_datasets import load_catalog
from check_replay import ReplayValidator
from jsonschema import FormatChecker
from replay_time import timestamp_ns

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024
MAX_FILE = 32 * MIB
MAX_FILES = 1024
MAX_DERIVED = 16 * MIB
MAX_SEGMENTS = 512
SCHEMA = ROOT / "contracts/archive-maintenance/v1/import.schema.json"


@dataclass(frozen=True)
class Prepared:
    metadata: dict
    sources: dict[str, Path]


def fail(valid, category):
    if not valid:
        raise ValueError("p05_" + category)


def encoded(value):
    """Maintenance identities exclude LF; P05's separate replay.digest includes it."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def safe(path):
    path = Path(os.path.abspath(path))
    fail(all(not p.is_symlink() for p in (path, *path.parents)), "unsafe_path")
    return path


def roots(run, cache, index):
    paths = tuple(map(safe, (run, cache, index)))
    fail(
        all(
            a != b and a not in b.parents and b not in a.parents
            for i, a in enumerate(paths)
            for b in paths[i + 1 :]
        ),
        "root_overlap",
    )
    fail(paths[0].is_dir() and paths[1].is_dir(), "source_missing")
    return paths


def regular(path):
    path = safe(path)
    fail(path.exists() and stat.S_ISREG(path.stat().st_mode), "source_file")
    fail(path.stat().st_size <= MAX_FILE, "file_limit")
    return path


def review(config, catalog):
    selected = {}
    for entry in config["datasets"]:
        manifest = entry["manifest"]
        ident = manifest["id"]
        fail(ident in catalog and encoded(catalog[ident]) == encoded(manifest), "catalog_changed")
        fail(manifest["terms"]["review_status"] == "approved", "terms_unreviewed")
        selected[ident] = catalog[ident]
    return digest(selected)


def children(path, cap):
    entries = []
    for entry in path.iterdir():
        entries.append(entry)
        fail(len(entries) <= cap, "directory_limit")
    return entries


def original_files(run, cache, config):
    allowed = {
        "manifest.json",
        "manifest.sha256",
        "segments",
        ".run.lock",
        "timing-index.json",
        "checkpoint.json",
    }
    fail(all(p.name in allowed for p in children(run, len(allowed))), "run_contents")
    segments = safe(run / "segments")
    fail(segments.is_dir(), "segments_missing")
    parts = sorted(children(segments, MAX_SEGMENTS))
    fail(0 < len(parts) <= MAX_SEGMENTS, "segment_limit")
    entries = []
    for name, role in (
        ("manifest.json", "manifest"),
        ("manifest.sha256", "manifest_checksum"),
        ("timing-index.json", "timing_index"),
        ("checkpoint.json", "checkpoint"),
    ):
        path = run / name
        if path.exists() or path.is_symlink():
            entries.append(("run/" + name, role, regular(path)))
    for number, segment in enumerate(parts):
        fail(segment.name == f"{number:08d}" and safe(segment).is_dir(), "segment_gap")
        fail(
            {p.name for p in children(segment, 2)} == {"records.ndjson", "commit.json"},
            "segment_contents",
        )
        for name, role in (
            ("records.ndjson", "segment_payload"),
            ("commit.json", "segment_commit"),
        ):
            entries.append((f"run/segments/{segment.name}/{name}", role, regular(segment / name)))
    for dataset in config["datasets"]:
        manifest = dataset["manifest"]
        for resource in [{**manifest["payload"], "role": "payload"}, *manifest["provenance"]]:
            path = regular(datasets.object_path(cache, resource))
            entries.append(("cache/objects/sha256/" + resource["sha256"], resource["role"], path))
    if (run / ".run.lock").exists() or (run / ".run.lock").is_symlink():
        regular(run / ".run.lock")
    return entries


def prepare(run, cache, managed_id, index, catalog):
    fail(str(uuid.UUID(managed_id)) == managed_id, "managed_identity")
    # Validate every consumed physical path before any old helper can read it.
    regular(run / "manifest.json")
    regular(run / "manifest.sha256")
    for name in ("checkpoint.json", "timing-index.json"):
        if (run / name).exists() or (run / name).is_symlink():
            regular(run / name)
    validator = ReplayValidator()
    config, lookup = replay.load_run(run, validator)
    catalog_sha = review(config, catalog)
    originals = original_files(run, cache, config)
    # P05 capture strings also need its original <=9-digit time model, including
    # preserve mode without a timing index (load_run need not parse fallback time).
    for entry in config["datasets"]:
        timestamp_ns(entry["capture"]["first_observed"])
    count = replay.checked_inputs(config, cache)
    state = replay.scan_segments(run, config, lookup, cache, validator)
    fail(state["status"] == "completed", "incomplete_run")
    fail(state["next_sequence"] == count + len(config["datasets"]) + 1, "envelope_count")
    manifest_sha = datasets.sha256_file(run / "manifest.json")
    framing = dict(version="1.0.0", derived_from_manifest_sha256=manifest_sha, datasets=[])
    captures = dict(version="1.0.0", derived_from_manifest_sha256=manifest_sha, captures=[])
    for entry in config["datasets"]:
        manifest = entry["manifest"]
        framing["datasets"].append(
            dict(
                dataset_id=manifest["id"],
                payload_sha256=manifest["payload"]["sha256"],
                framing=datasets.inventory(datasets.object_path(cache, manifest["payload"])),
            )
        )
        captures["captures"].append(dict(dataset_id=manifest["id"], capture=entry["capture"]))
    derived = {
        "index/framing.json": encoded(framing) + b"\n",
        "index/captures.json": encoded(captures) + b"\n",
    }
    fail(sum(map(len, derived.values())) <= MAX_DERIVED, "index_limit")
    descriptors: dict[str, dict] = {}
    sources: dict[str, Path] = {}
    for logical, role, path in originals:
        descriptor = dict(
            kind="original",
            role=role,
            path=logical,
            sha256=datasets.sha256_file(path),
            length=path.stat().st_size,
        )
        fail(logical not in descriptors or descriptors[logical] == descriptor, "role_conflict")
        descriptors[logical], sources[logical] = descriptor, path
    for logical, body in derived.items():
        descriptors[logical] = dict(
            kind="derived",
            role="framing_index" if "framing" in logical else "capture_projection",
            path=logical,
            sha256=hashlib.sha256(body).hexdigest(),
            length=len(body),
        )
        sources[logical] = index / logical.split("/", 1)[1]
    files = sorted(
        descriptors.values(), key=lambda f: (f["role"], f["path"], f["sha256"], f["length"])
    )
    fail(len(files) <= MAX_FILES, "descriptor_limit")
    metadata = dict(
        version="1.0.0",
        managed_id=managed_id,
        run_id=config["run_id"],
        manifest_sha256=manifest_sha,
        p05_manifest_sha256=replay.digest(config),
        reviewed_catalog_sha256=catalog_sha,
        record_count=count,
        envelope_count=state["next_sequence"],
        segment_count=state["segments"],
        files=files,
    )
    metadata["id"] = digest(
        ["detectbridge.archive.p05-import/1", managed_id, config["run_id"], manifest_sha, files]
    )
    require_metadata(metadata)
    return Prepared(metadata, sources), derived


def require_metadata(metadata):
    errors = StrictValidator(load_json(SCHEMA), format_checker=FormatChecker()).iter_errors(
        metadata
    )
    fail(next(errors, None) is None, "import_metadata")


def write_indexes(index, derived):
    fail(index.parent.is_dir(), "index_parent")
    if not index.exists():
        index.mkdir(mode=0o700)
    fail(index.is_dir(), "index_directory")
    wanted = {logical.split("/", 1)[1] for logical in derived}
    fail({p.name for p in children(index, 2)} <= wanted, "index_contents")
    for logical, body in derived.items():
        path = index / logical.split("/", 1)[1]
        if path.exists() or path.is_symlink():
            fail(regular(path).read_bytes() == body, "index_conflict")
        else:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
    replay.sync_directory(index)


@contextmanager
def source(run_dir, data_cache, managed_id, generated_dir, reviewed_catalog=None):
    """Yield exact import descriptors while holding the existing original run lock."""
    run, cache, index = roots(run_dir, data_cache, generated_dir)
    lock_path = regular(run / ".run.lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("p05_source_locked") from None
        catalog = load_catalog() if reviewed_catalog is None else reviewed_catalog
        prepared, derived = prepare(run, cache, managed_id, index, catalog)
        write_indexes(index, derived)
        yield prepared
    finally:
        os.close(descriptor)


def validate_restored(run_dir, data_cache, metadata, index_dir, reviewed_catalog=None):
    """Verify unpublished, caller-leased restore roots without creating a P05 lock.

    This function writes nothing. A successful caller may publish the fresh restored
    run; subsequent original P05 inspection can create/update its own advisory state.
    """
    require_metadata(metadata)
    run, cache, index = roots(run_dir, data_cache, index_dir)
    catalog = load_catalog() if reviewed_catalog is None else reviewed_catalog
    prepared, derived = prepare(run, cache, metadata["managed_id"], index, catalog)
    fail(prepared.metadata == metadata, "restored_closure")
    fail({p.name for p in children(cache, 1)} == {"objects"}, "restored_cache")
    objects = safe(cache / "objects")
    fail(
        objects.is_dir() and {p.name for p in children(objects, 1)} == {"sha256"}, "restored_cache"
    )
    hashes = safe(objects / "sha256")
    fail(hashes.is_dir(), "restored_cache")
    wanted = {
        entry["path"].split("/")[-1]
        for entry in metadata["files"]
        if entry["path"].startswith("cache/")
    }
    fail({p.name for p in children(hashes, MAX_FILES)} == wanted, "restored_cache")
    fail(
        index.is_dir()
        and {p.name for p in children(index, 2)} == {name.split("/", 1)[1] for name in derived},
        "restored_index",
    )
    for logical, body in derived.items():
        fail(regular(prepared.sources[logical]).read_bytes() == body, "restored_index")
    for entry in metadata["files"]:
        path = regular(prepared.sources[entry["path"]])
        fail(
            path.stat().st_size == entry["length"]
            and datasets.sha256_file(path) == entry["sha256"],
            "restored_hash",
        )
    return prepared
