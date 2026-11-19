"""Explicit current-policy archive replay in an exclusive private local workspace."""

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path

import historical as history
from check_contracts import StrictValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker

ROOT = history.ROOT
MIB = history.MIB
SCHEMAS = ROOT / "contracts/current-replay/v1"
BUILDS = ROOT / ".cache/current-replay-build"
LIMITS = history.LIMITS


def fail(valid, category):
    if not valid:
        raise ValueError("current_" + category)


def require(kind, value):
    schema = load_json(SCHEMAS / (kind + ".schema.json"))
    Draft202012Validator.check_schema(schema)
    fail(
        not list(StrictValidator(schema, format_checker=FormatChecker()).iter_errors(value)),
        "schema_" + kind,
    )


def validate(request, selection):
    require("request", request)
    expected = {}
    for unit in selection["request"]["units"]:
        for ref in unit["inputs"]:
            key = (ref["topic"], ref["offset"])
            fail(key not in expected, "duplicate_selected_input")
            expected[key] = ref
    fail(0 < len(expected) <= 256, "input_limit")
    seen = set()
    previous = -1
    for index, step in enumerate(request["schedule"]):
        fail(step["at_ms"] >= previous, "schedule_order")
        previous = step["at_ms"]
        if step["action"] == "input":
            ref = step["input"]
            fail(ref is not None, "missing_input")
            key = (ref["topic"], ref["offset"])
            fail(key in expected and expected[key] == ref, "foreign_input")
            fail(key not in seen, "duplicate_input")
            seen.add(key)
        else:
            fail(step["input"] is None, "control_input")
            fail(step["action"] != "end" or index == len(request["schedule"]) - 1, "early_end")
    fail(request["schedule"][-1]["action"] == "end", "missing_end")
    fail(seen == set(expected), "missing_selected_input")


@contextlib.contextmanager
def workspace(path):
    root = history.safe(path)
    binding = dict(version="1.0.0", mode="current", destination=str(root), limits=LIMITS)
    if not root.exists():
        fail(root.parent.is_dir(), "workspace_parent")
        prefix = "." + root.name + "-current-init-"
        for old in root.parent.iterdir():
            if not old.name.startswith(prefix):
                continue
            history.tree_bytes(old)
            history.contents(
                old,
                {
                    p.name
                    for p in old.iterdir()
                    if p.name in {"catalog.json", "catalog.sha256", "artifacts", "runs"}
                },
            )
            for name in ("artifacts", "runs"):
                if (old / name).exists():
                    history.contents(old / name, set())
            shutil.rmtree(old)
        stage = Path(tempfile.mkdtemp(prefix=prefix, dir=root.parent))
        history.reserve(stage, MIB)
        for name in ("artifacts", "runs"):
            (stage / name).mkdir(mode=0o700)
            history.sync(stage / name)
        history.metadata(stage / "catalog.json", binding)
        history.publish(stage, root)
    fail(history.verified(root / "catalog.json") == binding, "workspace_binding")
    fd = os.open(root / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fail(history.verified(root / "catalog.json") == binding, "workspace_binding")
        fail(
            all(
                p.name
                in {
                    "catalog.json",
                    "catalog.sha256",
                    ".lock",
                    "artifacts",
                    "runs",
                    "failures",
                    "helper.active",
                }
                or re.fullmatch(r"\.partial-[0-9a-f]{32}", p.name)
                for p in root.iterdir()
            ),
            "workspace_contents",
        )
        history.stop_orphans(root)
        history.reserve(root, 0)
        allowed = {
            "refs.json",
            "rows.json",
            "export.json",
            "engine.json",
            "registration.json",
            "failure.txt",
            "run.json",
            "run.sha256",
            "result.json",
            "commit.json",
            "commit.sha256",
            "progress.json",
        }
        for stage in root.glob(".partial-*"):
            history.tree_bytes(stage)
            for folder, dirs, files in os.walk(stage, onerror=history.walk_error):
                fail(
                    all(n in {"objects", "steps", "units"} for n in dirs),
                    "unknown_partial_directory",
                )
                fail(
                    all(
                        n in allowed or re.fullmatch(r"[0-9a-f]{64}|[0-9]{6}\.json", n)
                        for n in files
                    ),
                    "unknown_partial",
                )
            shutil.rmtree(stage)
        for folder, _, _ in os.walk(root, topdown=False, onerror=history.walk_error):
            history.sync(folder)
        history.sync(root.parent)
        yield root
    finally:
        os.close(fd)


def resources():
    return {
        "META-INF/current/tools/current_replay.py": Path(__file__),
        "META-INF/current/tools/historical.py": ROOT / "tools/historical.py",
        "META-INF/current/tools/check_contracts.py": ROOT / "tools/check_contracts.py",
        "META-INF/current/uv.lock": ROOT / "uv.lock",
        **{"META-INF/current/schemas/" + p.name: p for p in SCHEMAS.glob("*.schema.json")},
        **{
            "META-INF/current/historical-schemas/" + p.name: p
            for p in history.SCHEMAS.glob("*.schema.json")
        },
    }


def verify_executor(path):
    with zipfile.ZipFile(path) as jar:
        fail(
            all(jar.read(name) == source.read_bytes() for name, source in resources().items()),
            "orchestrator_incompatible",
        )
        fail(
            all(
                not n.endswith(".class") or n.startswith("io/detectbridge/currentreplay/")
                for n in jar.namelist()
            ),
            "executor_classes",
        )


def build():
    old = history.build()
    subprocess.run(
        [str(ROOT / "gradlew"), "--console=plain", ":current-replay:jar"],
        env=history.java_env(),
        check=True,
    )
    path = ROOT / "packages/current-replay/build/libs/current-replay.jar"
    verify_executor(path)
    digest = history.sha(history.read(path, 32 * MIB))
    BUILDS.mkdir(parents=True, exist_ok=True)
    target = BUILDS / digest
    if target.exists():
        fail(history.read(target, 32 * MIB) == path.read_bytes(), "artifact_conflict")
    else:
        history.write(target, path.read_bytes())
    result = dict(
        executor=digest, producer=old["producer"], reader=old["reader"], image=old["image"]
    )
    (BUILDS / "bundle.json").write_bytes(history.encoded(result) + b"\n")
    return result


def execute(root, spec, index, objects):
    request = spec["request"]
    payload = dict(
        run_id=spec["run_id"],
        request_sha256=spec["request_sha256"],
        request=request,
        original_run_id=spec["original_run_id"],
        inputs=[
            dict(
                reference=step["input"],
                value=index[(step["input"]["topic"], step["input"]["offset"])],
            )
            for step in request["schedule"]
            if step["action"] == "input"
        ],
        plan_sha256=request["plan_sha256"],
        plan="/plan.json",
        objects="/objects",
    )
    data = history.encoded(payload)
    fail(len(data) <= 32 * MIB, "executor_input_limit")
    history.reserve(root, len(data) + 129 * MIB)
    stage = history.partial(root)
    history.write(stage / "engine.json", data)
    try:
        history.container(
            spec["image"],
            [
                (history.artifact(root, spec["executor_sha256"]), "/executor.jar", True),
                (history.artifact(root, history.PRODUCER), "/producer.jar", True),
                (history.artifact(root, request["plan_sha256"]), "/plan.json", True),
                (objects, "/objects", True),
                (stage, "/out", False),
            ],
            [
                "java",
                "-Xmx320m",
                "-cp",
                "/executor.jar:/producer.jar:/opt/flink/lib/*",
                "io.detectbridge.currentreplay.Bootstrap",
                "/producer.jar",
                "/out/engine.json",
                "/out/steps",
            ],
            timeout=240,
        )
    except Exception:
        failure = stage / "failure.txt"
        if failure.is_file():
            data = history.read(failure, MIB)
            history.reserve(root, len(data) + MIB)
            directory = root / "failures"
            directory.mkdir(mode=0o700, exist_ok=True)
            history.write(directory / (uuid.uuid4().hex + ".txt"), data)
            history.sync(directory)
            history.sync(root)
        raise
    steps = stage / "steps"
    history.contents(steps, {f"{i:06d}.json" for i in range(len(request["schedule"]))})
    fail(sum(p.stat().st_size for p in steps.iterdir()) <= 128 * MIB, "executor_total_limit")
    return stage, steps


def advisory(root, destination, spec, count):
    history.HOOK("before_advisory")
    stage = history.partial(root)
    history.write(
        stage / "progress.json",
        history.encoded(
            dict(
                version="1.0.0",
                mode="current",
                run_id=spec["run_id"],
                committed_transitions=count,
                transition_count=len(spec["request"]["schedule"]),
            )
        )
        + b"\n",
        "advisory",
    )
    history.sync(stage)
    os.replace(stage / "progress.json", destination / "progress.json")
    history.HOOK("after_advisory_rename")
    history.sync(destination)
    stage.rmdir()
    history.sync(root)


def replay(
    archive, historical_catalog, workspace_path, request_path, plan_path, run_id, resume=False
):
    archive, source, workspace_path = map(
        history.safe, (archive, historical_catalog, workspace_path)
    )
    roots = (archive, source, workspace_path)
    fail(
        all(
            a != b and a not in b.parents and b not in a.parents
            for i, a in enumerate(roots)
            for b in roots[i + 1 :]
        ),
        "root_overlap",
    )
    request = history.document(request_path, MIB)
    require("request", request)
    fail(str(uuid.UUID(run_id)) == run_id, "run_identity")
    fail(source.is_dir() and (source / "catalog.json").is_file(), "historical_catalog_missing")
    with history.catalog(source) as historical:
        pin = historical / "pins" / request["selection_sha256"]
        history.contents(pin, {"selection.json", "selection.sha256"})
        selection = history.verified(pin / "selection.json")
        history.require("selection", selection)
        fail(
            history.sha(history.encoded(selection)) == request["selection_sha256"],
            "selection_integrity",
        )
        validate(request, selection)
        original = selection["request"]["original_run_id"]
        fail(
            uuid.UUID(run_id) != uuid.UUID(original)
            and not (historical / "runs" / run_id).exists(),
            "run_reuse",
        )
        fail(selection["profile"] == request["engine_profile"], "profile")
        history.verify_executor(history.artifact(historical, selection["executor_sha256"]))
        bundle = history.document(BUILDS / "bundle.json")
        fail(
            bundle["producer"] == history.PRODUCER
            and bundle["image"] == selection["image"]
            and bundle["reader"] == selection["reader_sha256"],
            "artifact_profile",
        )
        verify_executor(BUILDS / bundle["executor"])
        plan = history.read(plan_path, 4 * MIB)
        fail(history.sha(plan) == request["plan_sha256"], "plan_integrity")
        with workspace(workspace_path) as root:
            destination = root / "runs" / run_id
            spec = dict(
                version="1.0.0",
                mode="current",
                run_id=run_id,
                request_sha256=history.sha(history.encoded(request)),
                request=request,
                executor_sha256=bundle["executor"],
                producer_sha256=history.PRODUCER,
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
                fail(history.verified(destination / "run.json") == spec, "resume_binding")
            else:
                fail(not resume, "run_missing")
            for name in ("producer", "reader"):
                history.install(root, history.artifact(historical, bundle[name]), bundle[name])
            history.install(root, BUILDS / bundle["executor"], bundle["executor"])
            history.install(root, plan_path, request["plan_sha256"])
            verify_executor(history.artifact(root, bundle["executor"]))
            exported, objects, proof, index = history.export(
                root,
                archive,
                selection["request"],
                history.artifact(root, bundle["reader"]),
                bundle["image"],
            )
            fail(all(proof[k] == selection[k] for k in proof), "archive_selection_changed")
            engine_spec = {**spec, "original_run_id": original}
            generated, files = execute(root, engine_spec, index, objects)
            if not destination.exists():
                history.reserve(root, MIB)
                pending = history.partial(root)
                history.metadata(pending / "run.json", spec)
                (pending / "units").mkdir(mode=0o700)
                history.sync(pending / "units")
                history.publish(pending, destination)
            units = destination / "units"
            names = sorted(p.name for p in units.iterdir())
            fail(
                names == [f"{i:06d}" for i in range(len(names))]
                and len(names) <= len(request["schedule"]),
                "transition_prefix",
            )
            previous = None
            prepared = []
            for i, step in enumerate(request["schedule"]):
                executed = history.document(files / f"{i:06d}.json", 24 * MIB)
                fail(set(executed) == {"state", "outputs"}, "executor_output")
                fail(len(history.encoded(executed["state"])) <= 16 * MIB, "state_limit")
                identity = history.sha(
                    history.encoded(
                        ["detectbridge.current.transition/1", run_id, spec["request_sha256"], i]
                    )
                )
                result = dict(
                    version="1.0.0",
                    mode="current",
                    run_id=run_id,
                    request_sha256=spec["request_sha256"],
                    origin_selection_sha256=request["selection_sha256"],
                    index=i,
                    transition_id=identity,
                    step=step,
                    **executed,
                )
                require("result", result)
                payload = history.encoded(result) + b"\n"
                fail(len(payload) <= 24 * MIB, "result_limit")
                commit = dict(
                    version="1.0.0",
                    index=i,
                    transition_id=identity,
                    result_sha256=history.sha(payload),
                    result_bytes=len(payload),
                    previous_sha256=previous,
                )
                require("commit", commit)
                if i < len(names):
                    target = units / f"{i:06d}"
                    history.contents(target, {"result.json", "commit.json", "commit.sha256"})
                    require("commit", history.verified(target / "commit.json"))
                    fail(
                        history.verified(target / "commit.json") == commit
                        and history.read(target / "result.json", 24 * MIB) == payload,
                        "committed_result_conflict",
                    )
                    history.sync(target)
                    history.sync(units)
                prepared.append((commit, previous))
                previous = history.sha(history.encoded(commit))
            # Verify the entire existing prefix before any new publication.
            for i in range(len(names), len(request["schedule"])):
                executed = history.document(files / f"{i:06d}.json", 24 * MIB)
                commit = prepared[i][0]
                result = dict(
                    version="1.0.0",
                    mode="current",
                    run_id=run_id,
                    request_sha256=spec["request_sha256"],
                    origin_selection_sha256=request["selection_sha256"],
                    index=i,
                    transition_id=commit["transition_id"],
                    step=request["schedule"][i],
                    **executed,
                )
                payload = history.encoded(result) + b"\n"
                fail(history.sha(payload) == commit["result_sha256"], "unpublished_result_changed")
                history.reserve(root, len(payload) + MIB)
                pending = history.partial(root)
                history.write(pending / "result.json", payload, "payload")
                history.metadata(pending / "commit.json", commit)
                history.publish(pending, units / f"{i:06d}")
                (files / f"{i:06d}.json").unlink()
                advisory(root, destination, spec, i + 1)
            shutil.rmtree(generated)
            shutil.rmtree(exported)
            history.sync(root)
            return dict(
                status="complete",
                mode="current",
                run_id=run_id,
                transitions=len(request["schedule"]),
                request_sha256=spec["request_sha256"],
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("build")
    for action in ("run", "resume"):
        p = sub.add_parser(action)
        for name in ("archive", "historical-catalog", "workspace", "request", "plan"):
            p.add_argument("--" + name, required=True, type=Path)
        p.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        if args.action == "build":
            result = build()
        else:
            result = replay(
                args.archive,
                args.historical_catalog,
                args.workspace,
                args.request,
                args.plan,
                args.run_id,
                args.action == "resume",
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(
            json.dumps(
                dict(
                    status="failed",
                    category="current_operation_failed",
                    failure_class=type(error).__name__,
                )
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
