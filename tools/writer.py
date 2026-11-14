"""Local-only OpenSearch writer lifecycle and isolated qualification."""

import argparse
import base64
import io
import json
import re
import secrets
import shutil
import signal
import tarfile
import time
import uuid

import replay
from check_contracts import load_json
from check_writer import require
from stack import (
    DEPLOY,
    GIB,
    ROOT,
    Stack,
    StackError,
    private_text,
    project_lock,
    retry_daemon_control,
    run,
    save,
)
from transport import Transport, digest, java_env, sha

CACHE = ROOT / ".cache/writer"
BUILDS = ROOT / ".cache/writer-build"
FAILURES = "detectbridge.opensearch.writer-failures.v1"
REPLAY = "detectbridge-replay-v1"
DIAGNOSTICS = "detectbridge-diagnostics-v1"


def build():
    run(
        [
            ROOT / "gradlew",
            "--console=plain",
            ":transport-writer:test",
            ":transport-writer:shadowJar",
        ],
        env=java_env(),
        timeout=600,
    )
    jar = ROOT / "packages/transport-writer/build/libs/writer.jar"
    dockerfile = DEPLOY / "writer.Dockerfile"
    if dockerfile.read_text().splitlines()[0] != "FROM " + Stack().image("flink"):
        raise StackError("writer_base_image_changed")
    jar_sha = sha(jar.read_bytes())
    fingerprint = sha(jar_sha.encode() + dockerfile.read_bytes())
    folder = BUILDS / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(jar, folder / "writer.jar")
    shutil.copyfile(dockerfile, folder / "Dockerfile")
    run(
        [
            "docker",
            "build",
            "--label",
            "io.detectbridge.writer.bundle_sha256=" + fingerprint,
            "--tag",
            "detectbridge-writer:" + fingerprint,
            folder,
        ],
        timeout=600,
    )
    metadata = json.loads(
        run(["docker", "image", "inspect", "detectbridge-writer:" + fingerprint]).stdout
    )[0]
    bundle = {
        "jar_sha256": jar_sha,
        "bundle_sha256": fingerprint,
        "image_id": metadata["Id"],
        "platform": "linux/" + metadata["Architecture"],
    }
    save(BUILDS / "bundle.json", bundle)
    return {"status": "built", "bundle": bundle}


class Writer:
    def __init__(self, project="detectbridge-dev"):
        self.stack = Stack(project)
        self.project = self.stack.project
        self.transport = Transport(project)
        self.folder = CACHE / self.project
        if self.folder.is_symlink():
            raise StackError("unsafe_writer_state")

    def bundle(self, value=None):
        value = load_json(BUILDS / "bundle.json") if value is None else value
        info = json.loads(run(["docker", "image", "inspect", value["image_id"]]).stdout)[0]
        if (
            info["Config"].get("Labels", {}).get("io.detectbridge.writer.bundle_sha256")
            != value["bundle_sha256"]
            or "linux/" + info["Architecture"] != value["platform"]
        ):
            raise StackError("writer_bundle_changed")
        return value

    def config(self):
        value = load_json(self.folder / "configuration.json")
        require("configuration", value)
        if value["project"] != self.project or (
            self.folder / "configuration.sha256"
        ).read_text().strip() != digest(value):
            raise StackError("writer_configuration_changed")
        if sha((self.folder / "writer-password").read_bytes()) != value["password_sha256"]:
            raise StackError("writer_credential_changed")
        state = self.stack.load()
        if sha((self.stack.folder / "security/ca.pem").read_bytes()) != value["ca_sha256"]:
            raise StackError("writer_ca_changed")
        if state.get("writer_bundle") != value["bundle"]:
            raise StackError("writer_stack_binding_changed")
        self.bundle(value["bundle"])
        return value

    def prepare_volume(self, name, files):
        self.stack.owned_volume(name, create=True)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for filename, data in files.items():
                if not re.fullmatch(r"[a-zA-Z0-9_.-]+", filename):
                    raise StackError("unsafe_secret_name")
                member = tarfile.TarInfo(filename)
                member.size = len(data)
                member.mode = 0o400
                member.uid = member.gid = 9999
                tar.addfile(member, io.BytesIO(data))
        args = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--log-driver",
            "none",
            "--label",
            "io.detectbridge.helper.project=" + self.project,
            "--network",
            "none",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "64",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "DAC_OVERRIDE",
            "--cap-add",
            "FOWNER",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "0:0",
            "--mount",
            f"type=volume,src={self.stack.volume(name)},dst=/out",
            "--entrypoint",
            "bash",
            self.stack.image("flink"),
            "-ceu",
            "umask 077; base64 -d | tar -xf - -C /out; chown 9999:9999 /out; chmod 700 /out",
        ]
        self.stack.temporary_run(
            args, data=base64.b64encode(archive.getvalue()).decode(), timeout=60
        )

    @retry_daemon_control
    def remove_admin_volume(self):
        if self.stack.owned_volume("writer-admin"):
            run(["docker", "volume", "rm", self.stack.volume("writer-admin")])

    def admin(self, pending):
        security = self.stack.folder / "security"
        files = {
            name: (security / name).read_bytes()
            for name in ("ca.pem", "admin.p12", "keystore-password")
        }
        files["writer-password"] = (self.folder / "writer-password").read_bytes()
        files["pending.json"] = replay.encoded(pending)
        self.prepare_volume("writer-admin", files)
        args = [
            "docker",
            "run",
            "--name",
            self.project + "-helper-" + uuid.uuid4().hex[:12],
            "--log-driver",
            "none",
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
            "--user",
            "9999:9999",
            "--mount",
            f"type=volume,src={self.stack.volume('writer-admin')},dst=/admin,readonly",
            pending["bundle"]["image_id"],
            "admin",
            "/admin",
        ]
        try:
            result = run(args, check=False, timeout=180)
            if result.returncode:
                detail = json.loads(result.stderr.splitlines()[-1]) if result.stderr else {}
                reason = detail.get("reason_type", "unknown")
                if not re.fullmatch(r"[A-Za-z0-9_]{1,80}", reason):
                    reason = "unknown"
                category = detail.get("category", "unknown")
                if not re.fullmatch(r"[a-z0-9_]{1,100}", category):
                    category = "unknown"
                raise StackError("writer_administration_failed_" + category + "_" + reason)
            return json.loads(result.stdout)
        finally:
            self.transport.remove_helper(args)
            # Admin material is never retained in the runtime volume.
            self.remove_admin_volume()

    def init(self):
        state = self.stack.load()
        if not state.get("security"):
            raise StackError("prepare_full_stack_before_writer_init")
        if self.stack.doctor("full", check_port=False)["docker_memory_bytes"] < 7.5 * GIB:
            raise StackError("writer_requires_7_5_gib_docker_memory")
        self.transport.verify_destination()
        if any(
            c["Config"]["Labels"]["com.docker.compose.service"] == "writer"
            and c["State"]["Running"]
            for c in self.stack.containers()
        ):
            raise StackError("stop_writer_before_initialization")
        self.folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        existing = (self.folder / "configuration.json").exists()
        if existing:
            pending = self.config()
        elif (self.folder / "pending.json").exists():
            pending = load_json(self.folder / "pending.json")
            if not (self.folder / "writer-password").is_file():
                raise StackError("missing_writer_credential_restore_original")
        else:
            if state.get("writer_bundle") or self.stack.owned_volume("writer-secrets"):
                raise StackError("existing_writer_state_without_metadata")
            if (self.folder / "writer-password").exists():
                raise StackError("partial_writer_state_requires_review")
            private_text(self.folder / "writer-password", "Aa1!" + secrets.token_urlsafe(32) + "\n")
            pipeline = self.transport.config()
            pending = {
                "contract_version": "1.0.0",
                "project": self.project,
                "writer_id": str(uuid.uuid4()),
                "pipeline_id": pipeline["pipeline_id"],
                "consumer_group": "detectbridge-writer-v1-" + uuid.uuid4().hex,
                "kafka_cluster_id": pipeline["broker"]["cluster_id"],
                "source_topics": {
                    name: {"id": item["id"]} for name, item in pipeline["broker"]["topics"].items()
                },
                "bundle": self.bundle(),
                "password_sha256": sha((self.folder / "writer-password").read_bytes()),
                "ca_sha256": sha((self.stack.folder / "security/ca.pem").read_bytes()),
            }
            save(self.folder / "pending.json", pending)
        config = self.admin(pending)
        require("configuration", config)
        if existing and digest(config) != digest(pending):
            raise StackError("writer_binding_drift")
        self.prepare_volume(
            "writer-secrets",
            {
                "ca.pem": (self.stack.folder / "security/ca.pem").read_bytes(),
                "writer-password": (self.folder / "writer-password").read_bytes(),
                "configuration.json": replay.encoded(config),
            },
        )
        overlay = {
            "services": {
                "writer": {
                    "image": config["bundle"]["image_id"],
                    "profiles": ["writer"],
                    "user": "9999:9999",
                    "networks": ["internal"],
                    "mem_limit": "512m",
                    "cpus": 0.5,
                    "pids_limit": 128,
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "read_only": True,
                    "tmpfs": ["/tmp:rw,nosuid,size=32m"],
                    "stop_grace_period": "45s",
                    "volumes": ["writer-secrets:/secrets:ro"],
                    "logging": {
                        "driver": "json-file",
                        "options": {"max-size": "10m", "max-file": "3"},
                    },
                    "healthcheck": {
                        "test": [
                            "CMD",
                            "curl",
                            "--fail",
                            "--silent",
                            "--max-time",
                            "3",
                            "http://localhost:9250/health",
                        ],
                        "interval": "5s",
                        "timeout": "4s",
                        "retries": 3,
                    },
                }
            },
            "volumes": {"writer-secrets": {}},
        }
        save(self.stack.folder / "writer.compose.json", overlay)
        state["writer_bundle"] = config["bundle"]
        state["writer_overlay_sha256"] = sha(
            (self.stack.folder / "writer.compose.json").read_bytes()
        )
        save(self.stack.folder / "state.json", state)
        save(self.folder / "configuration.json", config)
        private_text(
            self.folder / "configuration.sha256", digest(config) + "\n"
        ) if not existing else (self.folder / "configuration.sha256").write_text(
            digest(config) + "\n"
        )
        return {"status": "initialized", "writer_id": config["writer_id"]}

    def start(self):
        config = self.config()
        if digest(self.admin(config)) != digest(config):
            raise StackError("writer_binding_drift")
        if self.stack.doctor("full", check_port=False)["docker_memory_bytes"] < 7.5 * GIB:
            raise StackError("writer_requires_7_5_gib_docker_memory")
        self.stack.compose("up", "-d", "writer", profile="full")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            services = self.stack.containers()
            writer = [
                s
                for s in services
                if s["Config"]["Labels"]["com.docker.compose.service"] == "writer"
            ]
            if writer and writer[0]["State"]["Status"] in ("exited", "dead"):
                logs = run(["docker", "logs", writer[0]["Id"]], check=False)
                category = "unknown"
                for line in (logs.stdout + logs.stderr).splitlines():
                    try:
                        detail = json.loads(line)
                        candidate = detail.get("category", "")
                        if re.fullmatch(r"[a-z0-9_]{1,100}", candidate):
                            category = candidate
                    except (ValueError, AttributeError):
                        pass
                raise StackError("writer_exited_before_readiness_" + category)
            try:
                result = self.runtime("health")
                if (
                    result.get("state") == "READY"
                    and writer
                    and writer[0]["State"].get("Health", {}).get("Status") == "healthy"
                ):
                    self.stack.inspect("full")
                    return {"status": "ready", **result}
            except StackError:
                pass
            time.sleep(1)
        raise StackError("writer_readiness_timeout")

    def runtime(self, path):
        if path not in ("health", "metrics"):
            raise StackError("invalid_writer_probe")
        value = self.stack.exec(
            "writer",
            "curl",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            "http://localhost:9250/" + path,
        )
        return json.loads(value) if path == "health" else value

    def stop(self):
        self.config()
        containers = [
            c
            for c in self.stack.containers()
            if c["Config"]["Labels"]["com.docker.compose.service"] == "writer"
            and c["State"].get("Running")
        ]
        if containers:
            run(["docker", "stop", "--time", "35", containers[0]["Id"]], timeout=45)
        return {"status": "stopped", "offsets": "retained"}

    def status(self):
        config = self.config()
        try:
            health = self.runtime("health")
        except StackError:
            health = {"state": "STOPPED_OR_UNAVAILABLE"}
        try:
            offsets = self.kafka_offsets()
        except StackError as exc:
            offsets = {"status": "unavailable", "category": str(exc)}
        return {
            "writer_id": config["writer_id"],
            "consumer_group": config["consumer_group"],
            "indices": config["indices"],
            "health": health,
            "offsets": offsets,
        }

    def kafka_offsets(self):
        config = self.config()
        # Fixed administrative CLI output contains topic/offset metadata only.
        return self.stack.exec(
            "kafka",
            "/opt/kafka/bin/kafka-consumer-groups.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--describe",
            "--group",
            config["consumer_group"],
        )

    def helper(self, command, data=None, timeout=35):
        if command not in ("probe", "membership", "inject-batch"):
            raise StackError("invalid_writer_helper")
        config = self.config()
        args = [
            "docker",
            "run",
            "--name",
            self.project + "-helper-" + uuid.uuid4().hex[:12],
            *(["-i"] if data is not None else []),
            "--log-driver",
            "none",
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
            "--user",
            "9999:9999",
            "--mount",
            f"type=volume,src={self.stack.volume('writer-secrets')},dst=/secrets,readonly",
            config["bundle"]["image_id"],
            command,
            "/secrets",
        ]
        try:
            result = run(args, data=data, timeout=timeout, check=False)
            if result.returncode:
                if result.returncode == 125:
                    raise StackError("docker_setup_failure")
                category = "unknown"
                reason = "unknown"
                for line in result.stderr.splitlines():
                    try:
                        detail = json.loads(line)
                        if re.fullmatch(r"[a-z0-9_]{1,100}", detail.get("category", "")):
                            category = detail["category"]
                        if re.fullmatch(r"[A-Za-z0-9_]{1,80}", detail.get("reason_type", "")):
                            reason = detail["reason_type"]
                    except (ValueError, AttributeError):
                        pass
                raise StackError("writer_helper_" + command + "_" + category + "_" + reason)
            return json.loads(result.stdout)
        finally:
            self.transport.remove_helper(args)

    def request(self, method, path, body=None):
        value = {"method": method, "path": path}
        if body is not None:
            value["ndjson" if isinstance(body, str) and path.startswith("/_bulk") else "body"] = (
                body
            )
        return self.helper("probe", json.dumps(value))

    def metrics(self):
        self.config()
        return {"metrics": self.runtime("metrics")}

    def verify(self, recorded=False):
        from writer_qualification import qualify

        return qualify(recorded)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-dev")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "init", "start", "stop", "status", "metrics"):
        sub.add_parser(name)
    sub.add_parser("verify").add_argument("--recorded", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        writer = Writer(args.project)
        with project_lock(args.project):
            result = (
                build()
                if args.command == "build"
                else writer.verify(args.recorded)
                if args.command == "verify"
                else getattr(writer, args.command)()
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "category": "writer_interrupted"}))
        return 130
    except Exception as exc:
        category = str(exc) if isinstance(exc, StackError) else type(exc).__name__
        print(json.dumps({"status": "failed", "category": category}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
