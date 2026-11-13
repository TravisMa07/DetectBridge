"""Bounded local infrastructure lifecycle; Docker access is trusted administration."""

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from check_contracts import load_json

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/local"
CACHE = ROOT / ".cache/stack"
LOCKS = ROOT / ".cache/stack-locks"
GIB = 1024**3
LIMITS = {
    "kafka": (GIB, 1),
    "jobmanager": (GIB, 0.5),
    "taskmanager": (2 * GIB, 1.5),
    "opensearch": (2 * GIB, 1.5),
}
CORE = ["kafka", "jobmanager", "taskmanager"]
VOLUMES = ["kafka-data", "flink-state", "opensearch-data", "opensearch-config"]


class StackError(Exception):
    pass


def run(args, *, env=None, data=None, timeout=120, check=True):
    try:
        result = subprocess.run(
            [str(a) for a in args],
            input=data,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StackError("command_timeout") from exc
    except OSError as exc:
        raise StackError("docker_unavailable") from exc
    if check and result.returncode:
        raise StackError("command_failed")
    return result


def project_name(value):
    if not re.fullmatch(r"detectbridge-[a-z0-9][a-z0-9-]{0,47}", value):
        raise StackError("invalid_project_name")
    return value


def version_tuple(value):
    match = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        raise StackError("unrecognized_runtime_version")
    return tuple(int(n or 0) for n in match.groups())


def capacity_errors(memory, available, profile, kernel):
    errors = []
    if memory < (7 if profile == "full" else 5) * GIB:
        errors.append("insufficient_docker_memory")
    if available < 10 * GIB:
        errors.append("insufficient_docker_disk")
    if profile == "full" and kernel < 262144:
        errors.append("vm_max_map_count_too_low")
    return errors


@contextmanager
def project_lock(project):
    LOCKS.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = LOCKS / (project_name(project) + ".lock")
    if path.is_symlink():
        raise StackError("unsafe_lock")
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StackError("project_busy") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def save(path, value):
    temp = path.with_suffix(".tmp")
    with os.fdopen(
        os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8"
    ) as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def private_text(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


class Stack:
    def __init__(self, project="detectbridge-dev", port=None):
        self.project = project_name(project)
        self.folder = CACHE / self.project
        if self.folder.is_symlink():
            raise StackError("unsafe_project_state")
        self.port = port
        self.lock = load_json(DEPLOY / "images.lock.json")

    def image(self, name):
        item = self.lock["images"][name]
        return item["tag"] + "@sha256:" + item["index"]

    def helper(
        self, name, command, *, mounts=(), user="1000:1000", network="none", data=None, timeout=120
    ):
        args = [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
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
            user,
            "--entrypoint",
            "bash",
        ]
        if user == "0:0":
            args += ["--cap-add", "DAC_OVERRIDE", "--cap-add", "CHOWN", "--cap-add", "FOWNER"]
        if data is not None:
            args.append("-i")
        for mount in mounts:
            args += ["--mount", mount]
        return run([*args, self.image(name), "-ceu", command], data=data, timeout=timeout).stdout

    def volume(self, name):
        return self.project + "_" + name

    def owned_volume(self, name, create=False):
        volume = self.volume(name)
        result = run(["docker", "volume", "inspect", volume], check=False)
        if result.returncode:
            if not create:
                return False
            run(
                [
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    f"com.docker.compose.project={self.project}",
                    "--label",
                    f"com.docker.compose.volume={name}",
                    "--label",
                    "io.detectbridge.managed=true",
                    volume,
                ]
            )
            return True
        labels = json.loads(result.stdout)[0].get("Labels") or {}
        if (
            labels.get("com.docker.compose.project") != self.project
            or labels.get("io.detectbridge.managed") != "true"
            or labels.get("com.docker.compose.volume") != name
        ):
            raise StackError("volume_ownership_mismatch")
        return True

    def load(self):
        if not (self.folder / "state.json").is_file():
            raise StackError("missing_state_run_init")
        state = load_json(self.folder / "state.json")
        if (
            state.get("version") != 1
            or state.get("project") != self.project
            or state.get("images") != self.lock["images"]
        ):
            raise StackError("state_version_or_image_change_requires_review")
        cluster = state.get("cluster_id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{22}", cluster):
            raise StackError("invalid_persisted_cluster_id")
        if self.port is not None and self.port != state["port"]:
            raise StackError("port_is_frozen_reinitialize_unused_project")
        if state.get("security"):
            for name, expected in state["security"].items():
                path = self.folder / name
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected
                ):
                    raise StackError("missing_or_changed_security_material")
        return state

    def compose(self, *args, profile=None, timeout=240, check=True, data=None):
        state = self.load()
        env = dict(
            os.environ,
            KAFKA_CLUSTER_ID=state["cluster_id"],
            STACK_DIR=str(self.folder),
            OPENSEARCH_PORT=str(state["port"]),
        )
        # Do not inherit variables that can redirect Compose to another deployment.
        for key in list(env):
            if key.startswith("COMPOSE_"):
                del env[key]
        command = [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--file",
            DEPLOY / "compose.yml",
        ]
        if profile:
            command += ["--profile", profile]
        return run([*command, *args], env=env, timeout=timeout, check=check, data=data)

    def containers(self):
        ids = run(
            ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={self.project}"]
        ).stdout.split()
        if not ids:
            return []
        values = json.loads(run(["docker", "inspect", *ids]).stdout)
        for item in values:
            if item["Config"].get("Labels", {}).get("com.docker.compose.service") not in LIMITS:
                raise StackError("unexpected_project_container")
        return values

    def doctor(self, profile, check_port=True, strict=True):
        info = json.loads(run(["docker", "info", "--format", "{{json .}}"]).stdout)
        compose = run(["docker", "compose", "version", "--short"]).stdout.strip()
        engine = info["ServerVersion"]
        if version_tuple(engine) < (28, 0, 0) or version_tuple(compose) < (2, 32, 0):
            raise StackError("require_docker_28_compose_2_32_or_newer")
        arch = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "amd64", "amd64": "amd64"}.get(
            info["Architecture"]
        )
        if info.get("OSType") != "linux" or arch is None:
            raise StackError("unsupported_docker_platform")
        probe = self.helper(
            "flink", "df -Pk / | tail -1 | awk '{print $4}'; cat /proc/sys/vm/max_map_count"
        )
        try:
            free, kernel = map(int, probe.strip().splitlines())
        except ValueError as exc:
            raise StackError("docker_capacity_measurement_unavailable") from exc
        free *= 1024
        errors = capacity_errors(info["MemTotal"], free, profile, kernel)
        if not info.get("MemoryLimit") or not info.get("CpuCfsQuota"):
            errors.append("docker_cannot_enforce_resource_limits")
        if errors and strict:
            raise StackError(",".join(errors))
        if profile == "full" and check_port and not self.containers():
            port = self.port or (
                self.load()["port"] if (self.folder / "state.json").exists() else 9200
            )
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError as exc:
                    raise StackError("loopback_port_in_use_choose_another_project_port") from exc
        return {
            "engine": engine,
            "compose": compose,
            "platform": "linux/" + arch,
            "docker_memory_bytes": info["MemTotal"],
            "docker_disk_available_bytes": free,
            "disk_warning": free < 20 * GIB,
            "vm_max_map_count": kernel,
            "capacity_errors": errors,
        }

    def init(self, profile):
        state_path = self.folder / "state.json"
        if state_path.exists():
            state = self.load()
        else:
            if (
                any(self.owned_volume(name) for name in VOLUMES)
                or self.containers()
                or self.folder.exists()
            ):
                raise StackError("existing_resources_without_state_restore_original_metadata")
            self.folder.mkdir(parents=True, mode=0o700)
            state = {
                "version": 1,
                "project": self.project,
                "cluster_id": base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("="),
                "port": self.port or 9200,
                "images": self.lock["images"],
                "security": {},
            }
            save(state_path, state)
        for name in ["kafka-data", "flink-state"] + (
            ["opensearch-data", "opensearch-config"] if profile == "full" else []
        ):
            self.owned_volume(name, create=True)
            # Root is restricted to initializing this project's volume; no application runs as root.
            # CHOWN/DAC_OVERRIDE are granted only to this bounded one-shot helper.
            run(
                [
                    "docker",
                    "run",
                    "--rm",
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
                    f"type=volume,src={self.volume(name)},dst=/target",
                    "--entrypoint",
                    "bash",
                    self.image("flink"),
                    "-ceu",
                    "chmod 700 /target; chown "
                    + ("9999:9999" if name == "flink-state" else "1000:1000")
                    + " /target",
                ]
            )
        if profile == "full":
            self.init_security(state)
        return {"project": self.project, "status": "initialized", "profile": profile}

    def init_security(self, state):
        if state["security"]:
            self.load()  # refuse missing or changed credentials rather than rotating beside data
            self.publish_security()
            return
        security = self.folder / "security"
        if security.exists():
            raise StackError("partial_security_initialization_restore_or_reset_unused_project")
        security.mkdir(mode=0o700)
        for name in ("operator-password", "health-password", "keystore-password"):
            private_text(security / name, secrets.token_urlsafe(32))
        script = (DEPLOY / "generate-security.sh").read_text()
        self.helper(
            "opensearch",
            script + f"\nchown -R {os.getuid()}:{os.getgid()} /output/security\n",
            user="0:0",
            mounts=[f"type=bind,src={self.folder},dst=/output"],
            timeout=180,
        )
        password = (security / "keystore-password").read_text().strip()
        operator = (security / "operator-hash").read_text().strip().splitlines()[-1]
        health = (security / "health-hash").read_text().strip().splitlines()[-1]
        # Keep schema metadata but remove every upstream demo user/backend.
        save(
            security / "internal_users.yml",
            {
                "_meta": {"type": "internalusers", "config_version": 2},
                "operator": {"hash": operator, "backend_roles": ["admin"]},
                "health": {"hash": health, "backend_roles": ["detectbridge_health"]},
            },
        )
        save(
            security / "config.yml",
            {
                "_meta": {"type": "config", "config_version": 2},
                "config": {
                    "dynamic": {
                        "http": {"anonymous_auth_enabled": False},
                        "authc": {
                            "basic_internal_auth_domain": {
                                "http_enabled": True,
                                "transport_enabled": True,
                                "order": 0,
                                "http_authenticator": {"type": "basic", "challenge": True},
                                "authentication_backend": {"type": "intern"},
                            }
                        },
                        "authz": {},
                    }
                },
            },
        )
        roles = {
            "_meta": {"type": "roles", "config_version": 2},
            "detectbridge_health": {
                "cluster_permissions": ["cluster:monitor/health"],
                "index_permissions": [],
                "tenant_permissions": [],
            },
            "detectbridge_operator": {
                "cluster_permissions": ["cluster_all"],
                "index_permissions": [
                    {"index_patterns": ["*"], "allowed_actions": ["indices_all"]}
                ],
                "tenant_permissions": [],
            },
        }
        save(security / "roles.yml", roles)
        save(
            security / "roles_mapping.yml",
            {
                "_meta": {"type": "rolesmapping", "config_version": 2},
                "detectbridge_operator": {"backend_roles": ["admin"]},
                "detectbridge_health": {"backend_roles": ["detectbridge_health"]},
            },
        )
        health_password = (security / "health-password").read_text().strip()
        private_text(security / "health.curl", 'user = "health:' + health_password + '"\n')
        # The node only receives its identity and health credential; CA/admin private keys stay host-side.
        config = {
            "cluster.name": self.project,
            "node.name": "opensearch",
            "network.host": "0.0.0.0",
            "discovery.type": "single-node",
            "plugins.security.ssl.transport.keystore_type": "PKCS12",
            "plugins.security.ssl.transport.keystore_filepath": "node.p12",
            "plugins.security.ssl.transport.keystore_password": password,
            "plugins.security.ssl.transport.truststore_type": "PKCS12",
            "plugins.security.ssl.transport.truststore_filepath": "truststore.p12",
            "plugins.security.ssl.transport.truststore_password": password,
            "plugins.security.ssl.transport.enforce_hostname_verification": True,
            "plugins.security.ssl.http.enabled": True,
            "plugins.security.ssl.http.keystore_type": "PKCS12",
            "plugins.security.ssl.http.keystore_filepath": "node.p12",
            "plugins.security.ssl.http.keystore_password": password,
            "plugins.security.ssl.http.truststore_type": "PKCS12",
            "plugins.security.ssl.http.truststore_filepath": "truststore.p12",
            "plugins.security.ssl.http.truststore_password": password,
            "plugins.security.nodes_dn": ["CN=detectbridge-node"],
            "plugins.security.authcz.admin_dn": ["CN=detectbridge-admin"],
            "plugins.security.allow_default_init_securityindex": True,
        }
        save(self.folder / "opensearch.yml", config)
        # Bind-mounted host config must be readable by the image UID on Linux.
        # Publish it to the owned read-only config volume alongside the node material instead.
        private_text(security / "opensearch.yml", (self.folder / "opensearch.yml").read_text())
        state["security"] = {
            str(path.relative_to(self.folder)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in security.iterdir()
            if path.is_file()
        }
        save(self.folder / "state.json", state)
        self.publish_security()

    def publish_security(self):
        self.load()
        source = self.folder / "security"
        command = "set -e; cp -R /usr/share/opensearch/config/. /target/; cp /input/node.p12 /input/truststore.p12 /input/ca.pem /input/health.curl /input/opensearch.yml /target/; for name in internal_users config roles roles_mapping; do cp /input/$name.yml /target/opensearch-security/; done; if [ ! -f /target/opensearch.keystore ]; then OPENSEARCH_PATH_CONF=/target /usr/share/opensearch/bin/opensearch-keystore create >/dev/null; fi; chmod -R u=rX,go= /target; chown -R 1000:1000 /target"
        run(
            [
                "docker",
                "run",
                "--rm",
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
                f"type=bind,src={source},dst=/input,readonly",
                "--mount",
                f"type=volume,src={self.volume('opensearch-config')},dst=/target",
                "--entrypoint",
                "bash",
                self.image("opensearch"),
                "-ceu",
                command,
            ]
        )
        self.helper(
            "opensearch",
            "test -r /config/node.p12; test -r /config/opensearch.yml; test ! -e /config/ca.p12; test ! -e /config/admin.p12",
            mounts=[f"type=volume,src={self.volume('opensearch-config')},dst=/config,readonly"],
        )

    def check_cluster(self):
        result = self.helper(
            "flink",
            "if [ -f /data/meta.properties ]; then grep '^cluster.id=' /data/meta.properties | cut -d= -f2; fi",
            mounts=[f"type=volume,src={self.volume('kafka-data')},dst=/data,readonly"],
        )
        if result.strip() and result.strip() != self.load()["cluster_id"]:
            raise StackError("kafka_cluster_identity_mismatch")

    def up(self, profile):
        if profile == "core" and any(
            v["Config"]["Labels"]["com.docker.compose.service"] == "opensearch"
            for v in self.containers()
        ):
            raise StackError("profile_change_requires_down")
        environment = self.doctor(profile)
        state = self.load()
        if profile == "full" and not state["security"]:
            raise StackError("missing_security_run_init_full")
        for name in ["kafka-data", "flink-state"] + (
            ["opensearch-data", "opensearch-config"] if profile == "full" else []
        ):
            if not self.owned_volume(name):
                raise StackError("missing_persistent_volume_run_init")
        self.check_cluster()
        started = time.monotonic()
        self.compose("up", "-d", "--wait", "--wait-timeout", "180", profile=profile, timeout=210)
        return {
            "project": self.project,
            "profile": profile,
            "status": "ready",
            "readiness_seconds": round(time.monotonic() - started, 3),
            "environment": environment,
            "services": self.inspect(profile),
        }

    def inspect(self, profile):
        values = self.containers()
        expected = set(CORE + (["opensearch"] if profile == "full" else []))
        if {v["Config"]["Labels"]["com.docker.compose.service"] for v in values} != expected:
            raise StackError("unexpected_service_set")
        result = []
        for item in values:
            name = item["Config"]["Labels"]["com.docker.compose.service"]
            host = item["HostConfig"]
            if (
                (host["Memory"], host["NanoCpus"]) != (LIMITS[name][0], int(LIMITS[name][1] * 1e9))
                or item["Config"]["User"]
                != ("9999:9999" if name in ("jobmanager", "taskmanager") else "1000:1000")
                or host["Privileged"]
                or host["PidsLimit"] != 256
                or "no-new-privileges:true" not in host["SecurityOpt"]
                or host.get("CapAdd")
                or host.get("LogConfig")
                != {"Type": "json-file", "Config": {"max-size": "10m", "max-file": "3"}}
                or item["Config"]["Image"]
                != self.image("flink" if name in ("jobmanager", "taskmanager") else name)
            ):
                raise StackError("runtime_resource_or_user_policy_mismatch")
            if item["State"].get("Health", {}).get("Status") != "healthy":
                raise StackError("service_not_healthy")
            published = host.get("PortBindings") or {}
            wanted = (
                {"9200/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(self.load()["port"])}]}
                if name == "opensearch"
                else {}
            )
            if published != wanted:
                raise StackError("runtime_port_policy_mismatch")
            image = json.loads(run(["docker", "image", "inspect", item["Image"]]).stdout)[0]
            arch = self.doctor_platform()
            if image["Architecture"] != arch:
                raise StackError("emulated_image_rejected")
            for network in item["NetworkSettings"]["Networks"]:
                net = json.loads(run(["docker", "network", "inspect", network]).stdout)[0]
                label = net.get("Labels", {}).get("com.docker.compose.network")
                if (
                    label not in (["internal", "access"] if name == "opensearch" else ["internal"])
                    or net["Internal"] != (label == "internal")
                    or net.get("Labels", {}).get("com.docker.compose.project") != self.project
                ):
                    raise StackError("runtime_network_policy_mismatch")
            result.append(
                {
                    "service": name,
                    "healthy": True,
                    "memory_limit": host["Memory"],
                    "cpus": host["NanoCpus"] / 1e9,
                    "image_id": item["Image"],
                    "architecture": image["Architecture"],
                }
            )
        return sorted(result, key=lambda v: v["service"])

    def doctor_platform(self):
        value = run(["docker", "info", "--format", "{{.Architecture}}"]).stdout.strip()
        return "arm64" if value in ("arm64", "aarch64") else "amd64"

    def status(self):
        state = self.load()
        profile = (
            "full"
            if any(
                v["Config"]["Labels"]["com.docker.compose.service"] == "opensearch"
                for v in self.containers()
            )
            else "core"
        )
        return {
            "project": self.project,
            "services": [
                {
                    "service": v["Config"]["Labels"]["com.docker.compose.service"],
                    "state": v["State"]["Status"],
                    "health": v["State"].get("Health", {}).get("Status", "unknown"),
                }
                for v in self.containers()
            ],
            "environment": self.doctor(profile, check_port=False, strict=False),
            "limits": LIMITS,
            "state_directory": str(self.folder),
            "volumes": [self.volume(n) for n in VOLUMES if self.owned_volume(n)],
            "opensearch_port": state["port"] if state["security"] else None,
        }

    def down(self):
        self.containers()  # reject unexpected project membership before mutation
        self.compose("down", "--timeout", "30", profile="full")
        return {"project": self.project, "status": "stopped", "volumes": "retained"}

    def reset(self, confirm):
        if confirm != self.project:
            raise StackError("reset_requires_exact_project_confirmation")
        self.load()
        for name in VOLUMES:
            self.owned_volume(name)
        self.down()
        for name in VOLUMES:
            if self.owned_volume(name):
                run(["docker", "volume", "rm", self.volume(name)])
        shutil.rmtree(self.folder)
        return {"project": self.project, "status": "reset"}

    def exec(self, service, *args, data=None):
        return self.compose("exec", "-T", service, *args, data=data).stdout

    def request(self, method, path, body=None, credential="operator"):
        state = self.load()
        context = ssl.create_default_context(cafile=self.folder / "security/ca.pem")
        headers = {"Content-Type": "application/json"}
        if credential is not None:
            password = (
                (self.folder / "security/operator-password").read_text().strip()
                if credential == "operator"
                else "deliberately-wrong-synthetic-password"
            )
            headers["Authorization"] = (
                "Basic " + base64.b64encode(("operator:" + password).encode()).decode()
            )
        request = Request(
            f"https://127.0.0.1:{state['port']}" + path,
            data=None if body is None else json.dumps(body).encode(),
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, context=context, timeout=15) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, None

    def verify(self, profile):
        # Never use the selected development project for destructive qualification.
        test_project = "detectbridge-test-" + uuid.uuid4().hex
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        test = Stack(test_project, port)
        report = {"project": test_project, "profile": profile, "status": "failed"}
        with project_lock(test_project):
            try:
                test.doctor(profile)
                test.init(profile)
                before = (test.folder / "state.json").read_bytes()
                test.init(profile)
                if before != (test.folder / "state.json").read_bytes():
                    raise StackError("initialization_not_idempotent")
                ready = test.up(profile)
                token = uuid.uuid4().hex
                topic = "p06-" + token
                test.exec(
                    "kafka",
                    "/opt/kafka/bin/kafka-topics.sh",
                    "--bootstrap-server",
                    "kafka:9092",
                    "--create",
                    "--topic",
                    topic,
                    "--partitions",
                    "1",
                    "--replication-factor",
                    "1",
                )
                test.exec(
                    "kafka",
                    "/opt/kafka/bin/kafka-console-producer.sh",
                    "--bootstrap-server",
                    "kafka:9092",
                    "--topic",
                    topic,
                    data=token + "\n",
                )
                test.exec(
                    "jobmanager",
                    "bash",
                    "-ceu",
                    "mkdir -p /state/checkpoints /state/savepoints; printf '%s' "
                    + token
                    + " > /state/checkpoints/p06-marker",
                )
                if (
                    test.exec("taskmanager", "cat", "/state/checkpoints/p06-marker").strip()
                    != token
                ):
                    raise StackError("flink_shared_state_unreadable")
                test.exec(
                    "taskmanager",
                    "bash",
                    "-ceu",
                    "printf '%s' " + token + " > /state/savepoints/p06-marker",
                )
                if profile == "full":
                    if any(
                        test.request("GET", "/", credential=c)[0] != 401 for c in (None, "wrong")
                    ):
                        raise StackError("opensearch_unauthenticated_access")
                    code, _ = test.request(
                        "PUT", "/p06-proof/_doc/1?refresh=true", {"marker": token}
                    )
                    if code not in (200, 201):
                        raise StackError("opensearch_authenticated_write_failed")
                test.down()
                restart = test.up(profile)
                consumed = test.exec(
                    "kafka",
                    "/opt/kafka/bin/kafka-console-consumer.sh",
                    "--bootstrap-server",
                    "kafka:9092",
                    "--topic",
                    topic,
                    "--from-beginning",
                    "--max-messages",
                    "1",
                    "--timeout-ms",
                    "15000",
                )
                if consumed.strip() != token:
                    raise StackError("kafka_persistence_failure")
                if (
                    test.exec("jobmanager", "cat", "/state/savepoints/p06-marker").strip() != token
                    or test.exec("taskmanager", "cat", "/state/checkpoints/p06-marker").strip()
                    != token
                ):
                    raise StackError("flink_state_persistence_failure")
                if profile == "full":
                    code, value = test.request("GET", "/p06-proof/_doc/1")
                    if code != 200 or value.get("_source", {}).get("marker") != token:
                        raise StackError("opensearch_persistence_failure")
                ids = [v["Id"] for v in test.containers()]
                idle = run(
                    ["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids]
                ).stdout
                report.update(
                    status="qualified",
                    environment=ready["environment"],
                    services=ready["services"],
                    readiness_seconds=ready["readiness_seconds"],
                    restart_seconds=restart["readiness_seconds"],
                    idle_stats=[json.loads(line) for line in idle.splitlines()],
                    persistence={
                        "kafka": True,
                        "flink_shared_files": True,
                        "opensearch": profile == "full",
                    },
                )
            finally:
                # SIGINT/TERM are deferred only during bounded cleanup of this unique project.
                old = {
                    sig: signal.signal(sig, signal.SIG_IGN)
                    for sig in (signal.SIGINT, signal.SIGTERM)
                }
                try:
                    if (test.folder / "state.json").exists():
                        test.reset(test_project)
                finally:
                    for sig, handler in old.items():
                        signal.signal(sig, handler)
        if test.containers() or any(test.owned_volume(n) for n in VOLUMES) or test.folder.exists():
            raise StackError("qualification_cleanup_incomplete")
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-dev")
    parser.add_argument("--port", type=int)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["doctor", "init", "up", "verify"]:
        commands.add_parser(name).add_argument(
            "--profile", choices=["core", "full"], default="core"
        )
    commands.add_parser("status")
    commands.add_parser("down")
    commands.add_parser("reset").add_argument("--confirm", required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if args.port is not None and not 1024 <= args.port <= 65535:
            raise StackError("invalid_loopback_port")
        stack = Stack(args.project, args.port)
        with project_lock(stack.project):
            if args.command == "reset":
                result = stack.reset(args.confirm)
            elif args.command in ("status", "down"):
                result = getattr(stack, args.command)()
            else:
                result = getattr(stack, args.command)(args.profile)
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "status": "interrupted",
                    "hint": "Resources retained unless isolated verification cleaned its own project.",
                }
            )
        )
        return 130
    except StackError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "category": str(exc),
                    "hint": "See docs/local-stack.md; existing data is retained.",
                }
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "category": "invalid_state_or_runtime_response",
                    "hint": "See docs/local-stack.md; no automatic repair performed.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
