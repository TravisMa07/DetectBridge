"""Isolated replay of signed worker evidence read from the lifecycle archive."""

import argparse
import base64
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import current_replay as current
import historical as history
from archive_profiles import PINS

VERSION = "lifecycle-replay/1"
MIB = history.MIB
DEFAULT_LIMITS = dict(
    members=256,
    group_bytes=MIB,
    open_groups=1024,
    pending_bytes=32 * MIB,
    age_ms=30000,
    runs=16,
    closed_keys=100000,
    closed_bytes=32 * MIB,
)


def require(condition, category):
    if not condition:
        raise ValueError("lifecycle_replay_" + category)


def canonical_uuid(value):
    return isinstance(value, str) and str(uuid.UUID(value)) == value


def reference(ref):
    require(
        isinstance(ref, dict) and ref.keys() == {"topic", "offset", "value_sha256"}, "reference"
    )
    require(
        isinstance(ref["topic"], str)
        and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", ref["topic"])
        and type(ref["offset"]) is int
        and 0 <= ref["offset"] < 2**63
        and isinstance(ref["value_sha256"], str)
        and re.fullmatch("[a-f0-9]{64}", ref["value_sha256"]),
        "reference",
    )
    return ref["topic"], ref["offset"]


def validate(request):
    mode = request["mode"]
    fields = {"version", "mode", "worker_id", "original_run_id", "units"}
    if mode == "current":
        fields.update({"bundle_sha256", "schedule"})
    require(
        request.keys() == fields
        and request["version"] == VERSION
        and mode in {"historical", "current"},
        "request",
    )
    require(
        canonical_uuid(request["original_run_id"]) and canonical_uuid(request["worker_id"]), "scope"
    )
    require(isinstance(request["units"], list) and 1 <= len(request["units"]) <= 128, "unit_limit")
    sources = {}
    used = set()
    for unit in request["units"]:
        require(
            unit.keys() == {"kind", "inputs", "outputs"}
            and unit["kind"] in {"windows", "authentication", "audit"},
            "unit",
        )
        require(
            isinstance(unit["inputs"], list)
            and 1 <= len(unit["inputs"]) <= 256
            and (unit["kind"] == "audit" or len(unit["inputs"]) == 1)
            and isinstance(unit["outputs"], list)
            and 1 <= len(unit["outputs"]) <= 1000,
            "unit_cardinality",
        )
        for ref in unit["inputs"]:
            sources[reference(ref)] = ref
        for ref in unit["inputs"] + unit["outputs"]:
            key = reference(ref)
            require(key not in used, "duplicate_reference")
            used.add(key)
    require(len(sources) <= 256 and len(used) <= 1000, "reference_limit")
    if mode == "current":
        require(
            isinstance(request["bundle_sha256"], str)
            and re.fullmatch("[0-9a-f]{64}", request["bundle_sha256"]),
            "bundle",
        )
        schedule = request["schedule"]
        require(isinstance(schedule, list) and 2 <= len(schedule) <= 512, "schedule_size")
        seen = set()
        previous = -1
        for index, step in enumerate(schedule):
            require(
                step.keys() == {"at_ms", "action", "input"}
                and type(step["at_ms"]) is int
                and 0 <= step["at_ms"] <= 86400000
                and previous <= step["at_ms"],
                "schedule_time",
            )
            previous = step["at_ms"]
            action = step["action"]
            require(
                action in {"input", "tick", "end"}
                and (action == "end") == (index == len(schedule) - 1),
                "schedule_order",
            )
            if action == "input":
                key = reference(step["input"])
                require(key not in seen and sources.get(key) == step["input"], "schedule_input")
                seen.add(key)
            else:
                require(step["input"] is None, "schedule_control")
        require(seen == sources.keys(), "schedule_coverage")
    return sources


def digest(value):
    return history.sha(history.encoded(value))


def HOOK(phase):
    """Process interruption injection at the two result-publication boundaries."""


@contextlib.contextmanager
def workspace(path):
    root = history.safe(path)
    binding = dict(version=VERSION, destination=str(root), limits=history.LIMITS)
    if not root.exists():
        require(root.parent.is_dir(), "workspace_parent")
        with tempfile.TemporaryDirectory(dir=root.parent, prefix=".lifecycle-replay-init-") as temp:
            stage = Path(temp) / "workspace"
            stage.mkdir(mode=0o700)
            for name in ("artifacts", "runs"):
                (stage / name).mkdir(mode=0o700)
                history.sync(stage / name)
            history.metadata(stage / "catalog.json", binding)
            history.publish(stage, root)
    require(history.verified(root / "catalog.json") == binding, "workspace_binding")
    fd = os.open(root / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        history.reserve(root, 0)
        for p in root.iterdir():
            require(
                p.name
                in {
                    "artifacts",
                    "runs",
                    "catalog.json",
                    "catalog.sha256",
                    ".lock",
                    "helper.active",
                    "failures",
                }
                or re.fullmatch(r"\.partial-[0-9a-f]{32}", p.name),
                "workspace_contents",
            )
        history.stop_orphans(root)
        for stage in root.glob(".partial-*"):
            shutil.rmtree(stage)
        history.sync(root)
        yield root
    finally:
        os.close(fd)


def archive_command(reader, args, target, root, cap):
    """Cap reader stdout even while running; never consume partial helper output."""
    import resource

    def output_limit():
        resource.setrlimit(resource.RLIMIT_FSIZE, (cap + 1, cap + 1))

    history.reserve(root, cap)
    java = history.ROOT / ".cache/jdk/bin/java"
    with target.open("xb") as out:
        result = subprocess.run(
            [str(java) if java.is_file() else "java", "-jar", str(reader), *map(str, args)],
            stdout=out,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=False,
            preexec_fn=output_limit,
        )
    require(result.returncode == 0 and target.stat().st_size <= cap, "archive_reader")


def snapshot(root, stage, archive, reader):
    from lifecycle_archive_graph import verify

    export = stage / "export.ndjson"
    archive_command(reader, ["export", archive], export, root, 128 * MIB)
    with export.open("rb") as stream:
        first = json.loads(stream.readline(8 * MIB + 1))
        require(
            first.keys() == {"type", "manifest", "heads"} and first["type"] == "manifest",
            "archive_header",
        )
        rows: list[dict[str, Any]] = []
        for line in stream:
            require(len(rows) < 4096 and len(line) <= 8 * MIB + 1, "archive_row_limit")
            rows.append(json.loads(line))
    objects = stage / "objects"
    objects.mkdir(mode=0o700)
    for obj in first["manifest"]["objects"]:
        sha = obj["sha256"]
        require(isinstance(sha, str) and re.fullmatch("[a-f0-9]{64}", sha), "object_identity")
        path = objects / sha
        cap = (32 if obj["kind"] == "original" else 64) * MIB
        if not path.exists():
            archive_command(reader, ["object", archive, sha], path, root, cap)
        require(history.sha(history.read(path, cap)) == sha, "object_integrity")
    graph = verify(first["manifest"], rows, objects)
    return first, rows, objects, graph


def selected(request, manifest, rows, graph):
    worker = request["worker_id"]
    original = request["original_run_id"]
    input_topics = [w["input_topic"] for w in manifest["workers"] if w["worker_id"] == worker]
    require(len(input_topics) == 1, "worker")
    topic = input_topics[0]
    by_position = {(r["topic"], r["offset"]): r for r in rows}
    require(len(rows) == len(by_position), "duplicate_position")
    receipts: dict[tuple[str, int], dict[str, Any]] = {}
    for envelope in graph["outputs"].values():
        if envelope["kind"] == "receipt" and envelope["worker_id"] == worker:
            doc = envelope["document"]
            location = doc["input"]
            key = (location["topic"], location["offset"])
            require(key not in receipts or envelope == receipts[key], "conflicting_receipt")
            receipts[key] = envelope

    def wire(ref):
        key = reference(ref)
        require(key in by_position, "missing_reference")
        row = by_position[key]
        require(
            row["value"] is not None
            and history.sha(base64.b64decode(row["value"], validate=True)) == ref["value_sha256"],
            "wire_integrity",
        )
        return key

    seen = set()
    result = []
    for unit in request["units"]:
        inputs = []
        for ref in unit["inputs"]:
            key = wire(ref)
            require(
                key[0] == topic["name"] and key in graph["inputs"] and key in receipts,
                "source_binding",
            )
            value = graph["inputs"][key]
            require(
                value.get("kind") in {"record", "windows_record"}
                and value["context"]["run_id"] == original,
                "source_run",
            )
            record = value["raw"]["record_id"]
            require(record not in seen, "duplicate_occurrence")
            seen.add(record)
            receipt = receipts[key]["document"]
            require(
                receipt["action"] == value["kind"]
                and receipt["record_id"] == record
                and receipt["input"]
                == dict(
                    **ref,
                    topic_id=topic["id"],
                    cluster_id=manifest["common"]["cluster_id"],
                    partition=0,
                ),
                "receipt_binding",
            )
            inputs.append(value)
        envelopes = []
        for ref in unit["outputs"]:
            key = wire(ref)
            require(key in graph["outputs"], "output_reference")
            doc = graph["outputs"][key]
            require(doc["worker_id"] == worker and doc["kind"] in history.ROUTES, "output_binding")
            envelopes.append(doc)
        control_hash = envelopes[0]["command_sha256"]
        require(all(e["command_sha256"] == control_hash for e in envelopes), "mixed_unit_command")
        command = graph["commands"][control_hash]
        member = [m for m in command["registrations"] if m["worker_id"] == worker]
        require(
            len(member) == 1
            and member[0]["input_topic"] == topic["name"]
            and member[0]["input_topic_id"] == topic["id"]
            and original in member[0]["assigned_runs"]
            and all(e["origin_incarnation"] == member[0]["incarnation"] for e in envelopes),
            "membership",
        )
        bundle = graph["bundles"][command["proposal"]["bundle_sha256"]]
        require(
            all(
                e["revision"] == command["revision"]
                and e["plan_sha256"] == history.sha(bundle["plan"])
                and e["bundle_sha256"] == bundle["manifest"]["bundle_sha256"]
                and e["compatibility_sha256"] == bundle["manifest"]["compatibility_sha256"]
                for e in envelopes
            ),
            "output_policy",
        )
        output_ids = [e["output_id"] for e in envelopes]
        require(len(set(output_ids)) == len(output_ids), "duplicate_output")
        result.append((inputs, envelopes, bundle))
    return result


def install_bytes(root, stage, filename, data):
    sha = history.sha(data)
    path = stage / filename
    if not path.exists():
        history.write(path, data)
    history.install(root, path, sha)
    return sha


def historical_result(root, selection, unit, verified, original, run, objects):
    inputs, envelopes, bundle = verified
    # The legacy adapter expects its own logical routes. These aliases exist only in
    # the helper invocation; request and result references keep actual archive coordinates.
    index = {}
    inner_refs = []
    for i, e in enumerate(envelopes):
        role = history.ROUTES[e["kind"]]
        inner_refs.append(dict(topic=role, offset=i))
        index[(role, i)] = e["document"]
    input_refs = []
    for i, row in enumerate(inputs):
        input_refs.append(dict(topic=history.INPUT, offset=i))
        index[(history.INPUT, i)] = row
    adapted = dict(
        kind=unit["kind"], inputs=input_refs, outputs=inner_refs, anchor=None, control=None
    )
    helper = dict(
        request=dict(original_run_id=original, plan_sha256=history.sha(bundle["plan"])),
        executor_sha256=PINS["historical"],
        image=PINS["image"],
    )
    result = history.engine(root, helper, adapted, index, objects, run)
    return dict(
        inputs=unit["inputs"],
        original_outputs=[
            dict(reference=ref, **{k: v for k, v in envelope.items() if k != "document"})
            for ref, envelope in zip(unit["outputs"], envelopes, strict=True)
        ],
        outputs=result["outputs"],
        selection_sha256=selection,
    )


def generated_results(root, stage, objects, graph, request, selection, run, units):
    original = request["original_run_id"]
    mode = request["mode"]
    for unit, verified in zip(request["units"], units, strict=True):
        _, _, bundle = verified
        sha = history.sha(bundle["plan"])
        install_bytes(root, stage, sha, bundle["plan"])
        result = historical_result(
            root,
            selection,
            unit,
            verified,
            original,
            run if mode == "historical" else original,
            objects,
        )
        if mode == "historical":
            yield result
    if mode == "current":
        target = request["bundle_sha256"]
        require(target in graph["bundles"], "current_bundle")
        bundle = graph["bundles"][target]
        require(
            all(
                bundle["manifest"]["compatibility_sha256"]
                == old["manifest"]["compatibility_sha256"]
                for _, _, old in units
            ),
            "current_compatibility",
        )
        plan_sha = history.sha(bundle["plan"])
        install_bytes(root, stage, plan_sha, bundle["plan"])
        inner = dict(
            version="1.0.0",
            mode="current",
            selection_sha256=selection,
            plan_sha256=plan_sha,
            engine_profile="p13-runtime-51a984de/1.0.0",
            source_policy="preserve-original-context/1.0.0",
            schedule_policy="explicit-offline-clock/1.0.0",
            enrichment=[],
            assembler_limits=DEFAULT_LIMITS,
            schedule=request["schedule"],
        )
        spec = dict(
            request=inner,
            original_run_id=original,
            run_id=run,
            request_sha256=digest(inner),
            executor_sha256=PINS["current"],
            image=PINS["image"],
        )
        generated, files = current.execute(root, spec, graph["inputs"], objects)
        try:
            for i, step in enumerate(request["schedule"]):
                result = history.document(files / f"{i:06d}.json", 24 * MIB)
                require(result.keys() == {"outputs", "state"}, "current_result")
                yield dict(
                    step=step,
                    bundle_sha256=target,
                    plan_sha256=plan_sha,
                    selection_sha256=selection,
                    **result,
                )
        finally:
            shutil.rmtree(generated)


def stage_results(root, stage, mode, results):
    """Verify every selected unit and bounded result before the first durable transition."""
    paths = []
    cap = (32 if mode == "historical" else 24) * MIB
    with contextlib.closing(results):
        for index, result in enumerate(results):
            data = history.encoded(result)
            require(len(data) <= cap, "result_limit")
            history.reserve(root, len(data) + MIB)
            path = stage / f"prepared-{index:06d}.json"
            history.write(path, data)
            paths.append(path)
    return (history.document(path, cap) for path in paths)


def publish_results(root, spec, resume, results):
    run = spec["run_id"]
    dest = root / "runs" / run
    if dest.exists():
        history.contents(dest, {"run.json", "run.sha256", "units"})
        require(resume and history.verified(dest / "run.json") == spec, "resume_binding")
    else:
        require(not resume, "run_missing")
        fresh = history.partial(root)
        history.metadata(fresh / "run.json", spec)
        (fresh / "units").mkdir(mode=0o700)
        history.sync(fresh / "units")
        history.publish(fresh, dest)
    units = dest / "units"
    names = sorted(p.name for p in units.iterdir())
    expected = len(
        spec["request"]["units"] if spec["mode"] == "historical" else spec["request"]["schedule"]
    )
    require(
        names == [f"{i:06d}" for i in range(len(names))] and len(names) <= expected,
        "committed_prefix",
    )
    previous = None
    count = 0
    for i, result in enumerate(results):
        require(i < expected, "result_count")
        body = (
            history.encoded(dict(version=VERSION, mode=spec["mode"], run_id=run, index=i, **result))
            + b"\n"
        )
        cap = (32 if spec["mode"] == "historical" else 24) * MIB
        require(len(body) <= cap, "result_limit")
        commit = dict(
            index=i,
            run_id=run,
            spec_sha256=digest(spec),
            result_sha256=history.sha(body),
            result_bytes=len(body),
            previous_sha256=previous,
        )
        target = units / f"{i:06d}"
        if i < len(names):
            history.contents(target, {"result.json", "commit.json", "commit.sha256"})
            require(
                history.verified(target / "commit.json") == commit
                and history.read(target / "result.json", cap) == body,
                "committed_result_conflict",
            )
            history.sync(target)
            history.sync(units)
        else:
            history.reserve(root, len(body) + MIB)
            stage = history.partial(root)
            with (stage / "result.json").open("xb") as file:
                middle = len(body) // 2
                file.write(body[:middle])
                file.flush()
                HOOK("during_result")
                file.write(body[middle:])
                file.flush()
                os.fsync(file.fileno())
            history.metadata(stage / "commit.json", commit)
            history.publish(stage, target)
            HOOK("after_result_publication")
        previous = digest(commit)
        count += 1
    require(count == expected, "result_count")
    return dict(status="complete", mode=spec["mode"], run_id=run, units=count)


def replay(
    archive,
    workspace_path,
    request_path,
    run_id,
    *,
    reader,
    reader_sha256,
    historical_jar,
    current_jar,
    resume=False,
):
    from lifecycle_archive_graph import __file__ as graph_source

    archive, workspace_path, reader = map(history.safe, (archive, workspace_path, reader))
    require(
        archive.is_dir()
        and archive != workspace_path
        and archive not in workspace_path.parents
        and workspace_path not in archive.parents,
        "root_overlap",
    )
    request = history.document(request_path, MIB)
    validate(request)
    require(canonical_uuid(run_id) and run_id != request["original_run_id"], "run_identity")
    require(
        re.fullmatch("[a-f0-9]{64}", reader_sha256)
        and history.sha(history.read(reader, 128 * MIB)) == reader_sha256,
        "reader_identity",
    )
    with workspace(workspace_path) as root:
        stage = history.partial(root)
        try:
            immutable_reader = stage / "reader.jar"
            history.reserve(root, reader.stat().st_size + MIB)
            history.write(immutable_reader, history.read(reader, 128 * MIB))
            require(
                history.sha(history.read(immutable_reader, 128 * MIB)) == reader_sha256,
                "reader_identity",
            )
            header, rows, objects, graph = snapshot(root, stage, archive, immutable_reader)
            original_runs = {
                run
                for command in graph["commands"].values()
                for worker in command["registrations"]
                for run in worker["assigned_runs"]
            }
            require(run_id not in original_runs, "run_reuse")
            units = selected(request, header["manifest"], rows, graph)
            history.install(root, objects / PINS["producer"], PINS["producer"])
            for key, path, verifier in (
                ("historical", historical_jar, history.verify_executor),
                ("current", current_jar, current.verify_executor),
            ):
                artifact = history.install(root, history.safe(path), PINS[key])
                verifier(artifact)
            selection = digest(
                dict(
                    worker_id=request["worker_id"],
                    original_run_id=request["original_run_id"],
                    units=request["units"],
                    archive_manifest_sha256=digest(header["manifest"]),
                )
            )
            spec = dict(
                version=VERSION,
                mode=request["mode"],
                request=request,
                run_id=run_id,
                archive=str(archive),
                workspace=str(root),
                heads=header["heads"],
                selection_sha256=selection,
                archive_prefix_sha256=history.sha(history.read(stage / "export.ndjson", 128 * MIB)),
                request_sha256=digest(request),
                archive_manifest_sha256=digest(header["manifest"]),
                historical_sha256=PINS["historical"],
                current_sha256=PINS["current"],
                producer_sha256=PINS["producer"],
                archive_reader_sha256=reader_sha256,
                controller_sha256=history.sha(Path(__file__).read_bytes()),
                graph_sha256=history.sha(Path(graph_source).read_bytes()),
                graph_signature_helper_sha256=history.sha(
                    (history.ROOT / "tools/LifecycleArchiveSignatures.java").read_bytes()
                ),
                image=PINS["image"],
            )
            dest = root / "runs" / run_id
            if resume:
                require(dest.is_dir(), "run_missing")
                require(history.verified(dest / "run.json") == spec, "resume_binding")
            else:
                require(not dest.exists(), "run_exists")
            # The pinned current executor registers every file in its evidence directory.
            # Give both executors exactly the original objects from the verified registry.
            originals = stage / "registered-originals"
            originals.mkdir(mode=0o700)
            for item in header["manifest"]["objects"]:
                if item["kind"] == "original":
                    (objects / item["sha256"]).rename(originals / item["sha256"])
            results = generated_results(
                root, stage, originals, graph, request, selection, run_id, units
            )
            prepared = stage_results(root, stage, spec["mode"], results)
            return publish_results(root, spec, resume, prepared)
        finally:
            shutil.rmtree(stage)
            history.sync(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "resume"))
    for name in (
        "archive",
        "workspace",
        "request",
        "run-id",
        "reader",
        "reader-sha256",
        "historical-jar",
        "current-jar",
    ):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        receipt = replay(
            args.archive,
            args.workspace,
            args.request,
            args.run_id,
            reader=args.reader,
            reader_sha256=args.reader_sha256,
            historical_jar=args.historical_jar,
            current_jar=args.current_jar,
            resume=args.action == "resume",
        )
    except Exception as exc:
        category = (
            str(exc)
            if isinstance(exc, ValueError)
            and re.fullmatch(r"(lifecycle_replay|historical|current)_[a-z_]{1,80}", str(exc))
            else "replay_failed"
        )
        parser.exit(1, f"{category} ({type(exc).__name__})\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
