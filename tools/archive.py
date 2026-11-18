"""Bounded local archive commands on an existing private DetectBridge Kafka network."""

import argparse
import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from check_contracts import load_json
from stack import ROOT, Stack, StackError, run, save
from transport import java_env

CACHE = ROOT / ".cache/archive"
BUILDS = ROOT / ".cache/archive-build"
TOPICS = (
    "detectbridge.integration.input.v1",
    "detectbridge.tagged-events.v1",
    "detectbridge.detections.v1",
    "detectbridge.processing-diagnostics.v1",
    "detectbridge.integration.manifests.v1",
    "detectbridge.integration.preservation.v1",
    "detectbridge.integration.quarantine.v1",
    "detectbridge.integration.receipts.v1",
    "detectbridge.integration.writer-failures.v1",
)
LIMITS = dict(
    archive_bytes=2 * 1024**3,
    reserve_bytes=128 * 1024**2,
    object_bytes=32 * 1024**2,
    segment_bytes=16 * 1024**2,
    segment_rows=256,
)


def build():
    run(
        [
            ROOT / "gradlew",
            "--console=plain",
            ":archive-writer:test",
            ":archive-writer:shadowJar",
            ":archive-writer:qualificationJar",
        ],
        env=java_env(),
        timeout=600,
    )
    jar = ROOT / "packages/archive-writer/build/libs/archive-writer.jar"
    sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    folder = BUILDS / sha
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "archive-writer.jar"
    if target.exists() and target.read_bytes() != jar.read_bytes():
        raise StackError("archive_immutable_artifact_conflict")
    if not target.exists():
        shutil.copyfile(jar, target)
    probe = jar.parent / "archive-probe.jar"
    probe_sha = hashlib.sha256(probe.read_bytes()).hexdigest()
    probe_target = folder / ("archive-probe-" + probe_sha + ".jar")
    if not probe_target.exists():
        shutil.copyfile(probe, probe_target)
    bundle = dict(jar_sha256=sha, probe_sha256=probe_sha, image=Stack().image("flink"))
    save(BUILDS / "bundle.json", bundle)
    return bundle


class ArchiveFailure(StackError):
    def __init__(self, exit_code, category, failure_class=None):
        self.exit_code = exit_code
        self.category = category
        self.failure_class = failure_class
        super().__init__("archive_" + category + "_exit_" + str(exit_code))


class Archive:
    def __init__(self, project):
        if not re.fullmatch(r"detectbridge-p(?:13|14)-[a-z0-9-]+", project):
            raise StackError("archive_dedicated_project_required")
        self.project = project
        self.stack = Stack(project)
        self.folder = CACHE / project
        if self.folder.is_symlink():
            raise StackError("archive_unsafe_path")
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        tooling = self.folder / "tooling.json"
        if not tooling.exists():
            save(tooling, load_json(BUILDS / "bundle.json"))
        self.bundle = load_json(tooling)

    def command(self, *args, probe=False, crash=None, pause=False, timeout=240):
        bundle = self.bundle
        # Resumes use the exact original immutable JAR, independently of the current build pointer.
        config = self.folder / "archive/archive.json"
        sha = (
            load_json(config)["implementation_sha256"] if config.exists() else bundle["jar_sha256"]
        )
        if sha != bundle["jar_sha256"]:
            raise StackError("archive_tooling_binding_changed")
        if not re.fullmatch("[a-f0-9]{64}", sha) or not re.fullmatch(
            "[a-f0-9]{64}", bundle.get("probe_sha256", "")
        ):
            raise StackError("archive_artifact_identity_invalid")
        if bundle["image"] != self.stack.image("flink"):
            raise StackError("archive_execution_image_changed")
        directory = BUILDS / sha
        jar = directory / "archive-writer.jar"
        if hashlib.sha256(jar.read_bytes()).hexdigest() != sha:
            raise StackError("archive_artifact_changed")
        if (
            probe
            and hashlib.sha256(
                (directory / ("archive-probe-" + bundle["probe_sha256"] + ".jar")).read_bytes()
            ).hexdigest()
            != bundle["probe_sha256"]
        ):
            raise StackError("archive_probe_artifact_changed")
        self.stack.load()  # Require actual owned deployment metadata before joining its network.
        command = [
            "docker",
            "run",
            "--rm",
            "--label",
            "io.detectbridge.helper.project=" + self.project,
            "--network",
            self.project + "_internal",
            "--memory",
            "512m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,size=32m",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--mount",
            f"type=bind,src={self.folder.resolve()},dst=/work",
            "--mount",
            f"type=bind,src={directory.resolve()},dst=/app,readonly",
            "--entrypoint",
            "java",
        ]
        if pause:
            command += ["--env", "DETECTBRIDGE_ARCHIVE_PAUSE=true"]
        if crash:
            command += ["--env", "DETECTBRIDGE_ARCHIVE_CRASH=" + crash]
        command += [
            bundle["image"],
            "-Xmx320m",
            "-cp",
            "/app/archive-writer.jar:/app/archive-probe-" + bundle["probe_sha256"] + ".jar",
            "io.detectbridge.archive." + ("KafkaProbe" if probe else "Main"),
            *map(str, args),
        ]
        name = self.project + "-helper-" + uuid.uuid4().hex[:12]
        command[2:2] = ["--name", name, "--log-driver", "none"]
        try:
            response = run(command, timeout=timeout, check=False)
            if response.returncode:
                # Original helper diagnostics are private and retained before owned cleanup.
                save(
                    self.folder / ("helper-failure-" + name.rsplit("-", 1)[-1] + ".json"),
                    dict(
                        exit_code=response.returncode,
                        stdout=response.stdout,
                        stderr=response.stderr,
                    ),
                )
                try:
                    detail = json.loads(response.stdout)
                    category = detail.get("category", "helper_failed")
                    failure_class = detail.get("failure_class")
                except ValueError:
                    category = "helper_failed"
                    failure_class = None
                if not re.fullmatch(r"[a-z_]{1,80}", category):
                    category = "helper_failed"
                raise ArchiveFailure(response.returncode, category, failure_class)
            return json.loads(response.stdout)
        finally:
            self.stack.remove_temporary(name)

    def init(self, registry, starts, provenance, limits=None):
        target = self.folder / "registry"
        if target.exists() or (self.folder / "archive").exists():
            raise StackError("archive_already_initialized")
        if registry.is_symlink() or not registry.is_dir():
            raise StackError("archive_registry_invalid")
        target.mkdir(mode=0o700)
        total = 0
        for index, p in enumerate(registry.iterdir()):
            if index >= 128 or p.is_symlink() or not p.is_file():
                raise StackError("archive_registry_invalid")
            data = p.read_bytes() if p.stat().st_size <= 32 * 1024**2 else b""
            total += len(data)
            if (
                not re.fullmatch("[a-f0-9]{64}", p.name)
                or hashlib.sha256(data).hexdigest() != p.name
                or total > 64 * 1024**2
            ):
                raise StackError("archive_registry_invalid")
            (target / p.name).write_bytes(data)
        save(
            self.folder / "request.json",
            dict(starts=starts, provenance=provenance, limits=limits or LIMITS),
        )
        return self.command(
            "init", "/work/archive", "kafka:9092", "/work/request.json", "/work/registry"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-p13-dev")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("verify")
    init = sub.add_parser("init")
    init.add_argument("--objects", type=Path, required=True)
    init.add_argument("--starts", type=Path, required=True)
    init.add_argument("--provenance", type=Path, required=True)
    sub.add_parser("drain")
    sub.add_parser("register")
    sub.add_parser("run")
    sub.add_parser("metrics")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--broker", action="store_true")
    obj = sub.add_parser("object")
    obj.add_argument("sha256")
    obj.add_argument("output", help="New filename within the owned archive command directory")
    wire = sub.add_parser("wire")
    wire.add_argument("topic", choices=TOPICS)
    wire.add_argument("offset", type=int)
    wire.add_argument("output")
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build()
        elif args.command == "verify":
            from archive_verify import qualify

            result = qualify()
        else:
            archive = Archive(args.project)
            if args.command == "init":
                result = archive.init(
                    args.objects, load_json(args.starts), load_json(args.provenance)
                )
            elif args.command == "register":
                result = archive.command("register", "/work/archive", "/work/registry")
            elif args.command == "metrics":
                observed = archive.command("inspect", "/work/archive", "--broker")["result"]
                lines = [
                    f"detectbridge_archive_managed_bytes {observed['managed_bytes']}",
                    "detectbridge_archive_historical_ready 0",
                ]
                for topic, values in sorted(observed["partitions"].items()):
                    for key in ("durable_next", "earliest", "end", "lag"):
                        lines.append(f'detectbridge_archive_{key}{{topic="{topic}"}} {values[key]}')
                print("\n".join(lines))
                return 0
            elif args.command == "inspect":
                result = archive.command(
                    "inspect", "/work/archive", *(["--broker"] if args.broker else [])
                )
            elif args.command in ("object", "wire"):
                if not re.fullmatch(r"[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)?", args.output):
                    raise StackError("archive_output_filename_invalid")
                values = [args.sha256] if args.command == "object" else [args.topic, args.offset]
                result = archive.command(
                    args.command, "/work/archive", *values, "/work/" + args.output
                )
            else:
                result = archive.command(
                    args.command, "/work/archive", timeout=86400 if args.command == "run" else 240
                )
        print(json.dumps(result, sort_keys=True))
    except ArchiveFailure as error:
        print(
            json.dumps(
                dict(
                    status="blocked",
                    category=error.category,
                    exit_code=error.exit_code,
                    failure_class=error.failure_class,
                )
            )
        )
        return 1
    except Exception:
        print(json.dumps(dict(status="blocked", category="archive_command_failed")))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
