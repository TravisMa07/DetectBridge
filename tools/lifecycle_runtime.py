"""Private signed P15b controller. Broker publication is separate from worker convergence."""

import argparse
import base64
import contextlib
import copy
import fcntl
import json
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import Any

import lifecycle as local
import lifecycle_validation as candidate
from check_contracts import StrictValidator, load_json
from jsonschema import FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/lifecycle-runtime/v1"
LIMITS = load_json(SCHEMAS / "common.schema.json")["$defs"]["limits"]["const"]
IMAGE = "flink:2.2.1-scala_2.12-java17@sha256:55ccb2ad4b98362c3f3503c5a6d7cd00b92eb25e38815ddaf0be5903ade54ffe"
KAFKA_IMAGE = load_json(ROOT / "deploy/local/compose.yml")["services"]["kafka"]["image"]
MIB = 1024 * 1024
DOMAINS = {name: "detectbridge.p15b." + name + "/1" for name in ("control", "artifact", "ack")}
encoded = candidate.encoded
sha = candidate.sha


class RuntimeError(ValueError):
    """Sanitized fixed controller category."""


class IntegrityError(RuntimeError):
    """Local executable/configuration failure, never an invalid remote acknowledgment."""


def require(condition, category):
    if not condition:
        raise RuntimeError("lifecycle_runtime_" + category)


def HOOK(name):
    """Fixed implementation fault boundary; never selected by candidate content."""
    return None


def identity(value):
    return sha(encoded(value))


def canonical_uuid(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value, "uuid")
    return value


def schema(kind, value):
    resources = []
    for folder in (SCHEMAS, ROOT / "contracts/lifecycle/v1"):
        for path in folder.glob("*.schema.json"):
            item = load_json(path)
            resources.append((item["$id"], Resource.from_contents(item)))
    validator = StrictValidator(
        load_json(SCHEMAS / (kind + ".schema.json")),
        registry=Registry().with_resources(resources),
        format_checker=FormatChecker(),
    )
    require(not list(validator.iter_errors(value)), "schema_" + kind)


def private_file(path, maximum=65536):
    path = local.regular(path)
    info = path.stat()
    require(info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o600, "private_file")
    return local.read(path, maximum)


def save(path, value):
    data = local.wrapped(value)
    require(len(data) <= 65536, "record_limit")
    temporary = path.parent / (".partial-" + uuid.uuid4().hex)
    local.write_exclusive(temporary, data)
    os.replace(temporary, path)
    local.sync_directory(path.parent)


def checked(path):
    private_file(path)
    return local.checked(path)


def topic_limits(topics):
    return {
        descriptor["name"]: {
            "control": 128 * 1024,
            "ack": 128 * 1024,
            "artifact": MIB,
            "output": 4 * MIB,
            "input": 2 * MIB + 65536,
        }[role]
        for role, descriptor in topics.items()
    }


def runtime_binding(config):
    return identity(
        {
            key: config[key]
            for key in (
                "version",
                "deployment_id",
                "authority_id",
                "authority_key_sha256",
                "cluster_id",
                "runtime_sha256",
                "producer_sha256",
                "image",
                "compatibility_sha256",
                "limits",
                "validator",
            )
        }
        | {
            "topics": {
                role: config["topics"][role] for role in ("control", "artifact", "ack", "output")
            }
        }
    )


def worker_binding(config):
    return identity(
        dict(
            version="1.0.0",
            runtime_binding_sha256=config["runtime_binding_sha256"],
            worker_id=config["worker_id"],
            input_topic=config["topics"]["input"],
            evidence_registry_sha256=config["evidence_registry_sha256"],
            state_codec="lifecycle-worker/1.0.0",
        )
    )


class Runtime:
    @classmethod
    def initialize(
        cls,
        root,
        authority_id,
        deployment_id,
        runtime_jar,
        producer_jar,
        compatibility_sha256,
        project=None,
        *,
        validator_artifact,
        validator_descriptor,
        qualification_jar=None,
    ):
        root = local.path_safe(root)
        validator_artifact = local.regular(validator_artifact)
        local.disjoint(root, validator_artifact)
        validator_bytes = local.read(validator_artifact, 64 * MIB)
        validator_descriptor = local.document(encoded(validator_descriptor))
        validator_schema = load_json(SCHEMAS / "common.schema.json")["$defs"]["validator"]
        require(
            not list(StrictValidator(validator_schema).iter_errors(validator_descriptor)),
            "validator_descriptor",
        )
        require(
            sha(validator_bytes) == validator_descriptor["artifact_sha256"], "validator_artifact"
        )
        cls._verify_validator_image(validator_descriptor)
        canonical_uuid(authority_id)
        canonical_uuid(deployment_id)
        require(re.fullmatch(r"[a-f0-9]{64}", compatibility_sha256), "compatibility")
        runtime_jar, producer_jar = local.regular(runtime_jar), local.regular(producer_jar)
        for path in (runtime_jar, producer_jar):
            local.disjoint(root, path)
        candidate.verify_artifact(producer_jar)
        runtime_bytes = local.read(runtime_jar, 32 * MIB)
        require(runtime_bytes, "runtime_artifact")
        qualification_bytes = None
        if qualification_jar is not None:
            qualification_jar = local.regular(qualification_jar)
            local.disjoint(root, qualification_jar)
            qualification_bytes = local.read(qualification_jar, 32 * MIB)
            require(qualification_bytes, "probe_artifact")
        require(not root.exists() and root.parent.is_dir(), "fresh_root")
        require(
            shutil.disk_usage(root.parent).free >= LIMITS["reserve_bytes"] + 64 * MIB,
            "disk_reserve",
        )
        project = project or "detectbridge-p15b-" + uuid.UUID(deployment_id).hex[:16]
        require(re.fullmatch(r"detectbridge-p15b-[a-z0-9-]{1,28}", project), "project")
        root.mkdir(mode=0o700)
        for name in (
            "artifacts",
            "authority",
            "workers",
            "publications",
            "bundles",
            "journal",
            "acks",
            "temporary",
        ):
            (root / name).mkdir(mode=0o700)
        local.write_exclusive(root / ".lock", b"")
        local.write_exclusive(root / "artifacts/compiler.tar", validator_bytes)
        local.write_exclusive(root / "artifacts/runtime.jar", runtime_bytes)
        local.write_exclusive(root / "artifacts/producer.jar", local.read(producer_jar, 64 * MIB))
        if qualification_bytes is not None:
            local.write_exclusive(root / "artifacts/qualification.jar", qualification_bytes)
        local.sync_directory(root / "artifacts")
        configuration = dict(
            version="1.0.0",
            authority_id=authority_id,
            deployment_id=deployment_id,
            project=project,
            runtime_sha256=sha(runtime_bytes),
            producer_sha256=candidate.PIN,
            image=IMAGE,
            kafka_image=KAFKA_IMAGE,
            compatibility_sha256=compatibility_sha256,
            limits=LIMITS,
            validator=validator_descriptor,
            qualification_sha256=sha(qualification_bytes)
            if qualification_bytes is not None
            else None,
            authority_public_key=None,
            authority_key_sha256=None,
        )
        # Bootstrap key generation is fixed local Java, before deployment state is published.
        cls._local_java(
            root, "keygen", root / "authority/private.der", root / "authority/public.der"
        )
        for name in ("private.der", "public.der"):
            (root / "authority" / name).chmod(0o600)
        public = private_file(root / "authority/public.der", 64)
        configuration.update(
            authority_public_key=base64.b64encode(public).decode(), authority_key_sha256=sha(public)
        )
        save(root / "config.json", configuration)
        save(root / "head.json", dict(sequence=0, sha256=None))
        local.sync_directory(root)
        local.sync_directory(root.parent)
        return cls(root)

    @staticmethod
    def _verify_validator_image(descriptor):
        inspected = local.document(
            Runtime._command(["docker", "image", "inspect", descriptor["image_id"]]).encode()
        )
        require(
            len(inspected) == 1 and inspected[0]["Id"] == descriptor["image_id"], "validator_image"
        )
        labels = inspected[0]["Config"].get("Labels") or {}
        require(
            labels.get("io.detectbridge.p15b.validator.artifact") == descriptor["artifact_sha256"]
            and labels.get("io.detectbridge.p15b.validator.base") == descriptor["base_image"],
            "validator_image_labels",
        )

    @staticmethod
    def _local_java(root, *args):
        logging = candidate.logging_api()
        command = [
            ROOT / ".cache/jdk/bin/java",
            "-Xmx256m",
            "-cp",
            os.pathsep.join(
                map(str, (root / "artifacts/runtime.jar", root / "artifacts/producer.jar", logging))
            ),
            "io.detectbridge.integration.LifecycleTool",
            *args,
        ]
        return Runtime._command(command)

    @staticmethod
    def _command(command, timeout=120):
        # Fixed helper arguments never become shell source; stderr stays private and value-free outside.
        result = subprocess.run(
            list(map(str, command)),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        require(
            len(result.stdout) <= 2 * MIB and len(result.stderr) <= 2 * MIB, "helper_output_limit"
        )
        if result.returncode:
            failure: Any = RuntimeError("lifecycle_runtime_helper_failed")
            failure.stdout = result.stdout
            failure.stderr = result.stderr
            failure.returncode = result.returncode
            raise failure
        return result.stdout.decode("utf-8", errors="strict")

    def __init__(self, root):
        self.root = local.path_safe(root)
        self._private()
        self.config = checked(self.root / "config.json")
        require(
            self.config["version"] == "1.0.0" and self.config["limits"] == LIMITS, "configuration"
        )
        with self._locked():
            self._load()

    def _verify_immutable_inputs(self):
        try:
            self._verify_immutable_inputs_checked()
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as failure:
            category = (
                str(failure)
                if isinstance(failure, RuntimeError)
                else "lifecycle_runtime_immutable_input_invalid"
            )
            raise IntegrityError(category) from None

    def _verify_immutable_inputs_checked(self):
        require(checked(self.root / "config.json") == self.config, "configuration_changed")
        allowed = {"runtime.jar", "producer.jar", "compiler.tar", "worker-logging.properties"}
        if self.config.get("qualification_sha256") is not None:
            allowed.add("qualification.jar")
            require(
                sha(private_file(self.root / "artifacts/qualification.jar", 32 * MIB))
                == self.config["qualification_sha256"],
                "probe_artifact_integrity",
            )
        require(
            {path.name for path in (self.root / "artifacts").iterdir()} <= allowed,
            "artifact_entries",
        )
        for role in ("runtime", "producer"):
            require(
                sha(private_file(self.root / "artifacts" / (role + ".jar"), 64 * MIB))
                == self.config[role + "_sha256"],
                "artifact_integrity",
            )
        require(
            sha(private_file(self.root / "artifacts/compiler.tar", 64 * MIB))
            == self.config["validator"]["artifact_sha256"],
            "validator_artifact",
        )
        require(
            sha(private_file(self.root / "authority/public.der", 64))
            == self.config["authority_key_sha256"],
            "authority_key",
        )
        logging = self.root / "artifacts/worker-logging.properties"
        if logging.exists():
            require(local.read(logging, 65536) == self._logging_bytes(), "logging_integrity")

    def _logging_bytes(self):
        with zipfile.ZipFile(self.root / "artifacts/runtime.jar") as archive:
            require(archive.namelist().count("lifecycle-log4j.properties") == 1, "logging_resource")
            entry = archive.getinfo("lifecycle-log4j.properties")
            require(0 < entry.file_size <= 65536, "logging_resource")
            return archive.read(entry)

    def _logging_file(self):
        self._verify_immutable_inputs()
        path = self.root / "artifacts/worker-logging.properties"
        data = self._logging_bytes()
        if not path.exists():
            self._reserve(len(data) + 65536)
            local.write_exclusive(path, data)
            path.chmod(0o444)
            with path.open("rb") as source:
                os.fsync(source.fileno())
            local.sync_directory(path.parent)
        require(local.read(path, 65536) == data, "logging_integrity")
        return path

    def _private(self):
        info = self.root.lstat()
        require(
            self.root.is_dir() and info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o700,
            "private_root",
        )

    @contextlib.contextmanager
    def _locked(self):
        self._private()
        descriptor = os.open(
            local.regular(self.root / ".lock"), os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("lifecycle_runtime_locked") from None
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _usage(self):
        size, entries = 0, 0
        for directory, folders, files in os.walk(self.root, followlinks=False):
            relative = Path(directory).relative_to(self.root).parts
            if (
                len(relative) == 3
                and relative[0] == "qualification-batches"
                and relative[2] in ("attempts", "acknowledgments", "receipts")
            ):
                # Count but never enter/resolve untrusted metadata members. Their private
                # regular-file checks occur in prefix order before any API use, so a bad
                # later directory or symlink cannot suppress an earlier certified fact.
                for name in [*folders, *files]:
                    info = (Path(directory) / name).lstat()
                    size += info.st_size
                    entries += 1
                    require(size <= LIMITS["store_bytes"] and entries <= 65536, "store_limit")
                folders[:] = []
                continue
            for name in folders:
                item = local.path_safe(Path(directory) / name)
                info = item.lstat()
                require(
                    item.is_dir() and info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o700,
                    "private_directory",
                )
                entries += 1
            for name in files:
                item = Path(directory) / name
                item = local.regular(item)
                info = item.stat()
                mode = 0o444 if item == self.root / "artifacts/worker-logging.properties" else 0o600
                require(info.st_uid == os.getuid() and info.st_mode & 0o777 == mode, "private_file")
                size += info.st_size
                entries += 1
                require(size <= LIMITS["store_bytes"] and entries <= 65536, "store_limit")
        self._entry_count = entries
        return size

    def _reserve(self, amount, recovery=False):
        headroom = 0 if recovery else LIMITS["controller_recovery_headroom_bytes"]
        require(
            self._usage() + amount + headroom <= LIMITS["store_bytes"]
            and self._entry_count + 4 <= 65536,
            "store_limit",
        )
        require(
            shutil.disk_usage(self.root).free >= LIMITS["reserve_bytes"] + amount, "disk_reserve"
        )

    def _load(self):
        self._verify_immutable_inputs()
        self._usage()
        allowed = {
            "artifacts",
            "authority",
            "workers",
            "publications",
            "bundles",
            "journal",
            "acks",
            "temporary",
            "qualification-batches",
            ".lock",
            "config.json",
            "head.json",
            "broker.compose.json",
            "failures",
        }
        for item in self.root.iterdir():
            if re.fullmatch(r"\.partial-[a-f0-9]{32}", item.name):
                private_file(item)
                item.unlink()
            else:
                require(item.name in allowed, "unknown_store_entry")
        local.sync_directory(self.root)
        self.state: dict[str, Any] = dict(
            sequence=0,
            sha256=None,
            workers={},
            publications=[],
            acks={},
            ack_cursor=0,
            ack_bytes=0,
            ack_rejections=0,
            ack_rejected_positions={},
            run_owners={},
            incarnation_keys={},
            incarnation_workers={},
            broker=None,
            jobs={},
            admissions=0,
            qualification_batches={},
        )
        head = checked(self.root / "head.json")
        require(set(head) == {"sequence", "sha256"} and type(head["sequence"]) is int, "head")
        entries = sorted((self.root / "journal").iterdir())
        require(
            len(entries) <= 524288 and len(entries) in (head["sequence"], head["sequence"] + 1),
            "journal_count",
        )
        for index, path in enumerate(entries, 1):
            require(path.name == f"{index:020d}.json", "journal_gap")
            record = checked(path)
            require(
                set(record) == {"sequence", "previous_sha256", "kind", "value"}
                and type(record["sequence"]) is int
                and record["sequence"] == index
                and record["previous_sha256"] == self.state["sha256"],
                "journal_chain",
            )
            self._apply(record["kind"], record["value"])
            self.state.update(sequence=index, sha256=identity(record))
            if index == head["sequence"]:
                require(head["sha256"] == self.state["sha256"], "head_binding")
        require(head["sequence"] != 0 or head["sha256"] is None, "head_binding")
        local.sync_directory(self.root / "journal")
        if len(entries) == head["sequence"] + 1:
            save(self.root / "head.json", {key: self.state[key] for key in ("sequence", "sha256")})
        local.sync_directory(self.root)
        # Verify every referenced immutable payload on every open.
        for item in self.state["publications"]:
            require(
                identity(checked(self.root / "publications" / (str(item["revision"]) + ".json")))
                == item["intent_sha256"],
                "publication_integrity",
            )
        for ack_id, descriptor in self.state["acks"].items():
            require(
                sha(private_file(self.root / "acks" / (ack_id[7:] + ".json")))
                == descriptor["wire_sha256"],
                "ack_integrity",
            )

        for operation, batch in list(self.state["qualification_batches"].items()):
            if batch["status"] == "pending":
                self._fence_qualification_batch(operation)
                try:
                    self._qualification_batch_prefix(batch)
                finally:
                    self._append(
                        "qualification_batch_result",
                        dict(operation_id=operation, status="recovered"),
                        recovery=True,
                    )
            else:
                self._qualification_batch_prefix(batch, journal=batch["status"] != "complete")

        batches_root = self.root / "qualification-batches"
        if batches_root.exists():
            folders = list(batches_root.iterdir())
            require(len(folders) <= 64, "qualification_batch_count")
            for folder in folders:
                canonical_uuid(folder.name)
                require(folder.is_dir(), "qualification_batch_layout")
                if folder.name not in self.state["qualification_batches"]:
                    # A pre-intent crash may leave source/request bytes, but no helper
                    # may have run. Effect metadata without a journal intent is invalid.
                    for role in ("attempts", "acknowledgments", "receipts"):
                        metadata = folder / role
                        if metadata.exists() or metadata.is_symlink():
                            require(
                                metadata.is_dir() and not any(metadata.iterdir()),
                                "qualification_batch_orphan_metadata",
                            )

    def _apply(self, kind, value):
        if kind == "broker":
            require(self.state["broker"] is None, "broker_reinitialization")
            self.state["broker"] = value
        elif kind == "broker_topics":
            require(
                self.state["broker"] is not None and not self.state["broker"]["topics"],
                "broker_topics",
            )
            self.state["broker"]["topics"] = value["topics"]
        elif kind == "worker":
            key = value["incarnation"]
            require(key not in self.state["incarnation_keys"], "incarnation_conflict")
            require(
                len(self.state["incarnation_keys"]) < LIMITS["incarnations"], "incarnation_limit"
            )
            self.state["incarnation_keys"][key] = value["public_key"]
            self.state["incarnation_workers"][key] = value["worker_id"]
            self.state["workers"][value["worker_id"]] = value
        elif kind == "adopt":
            require(value["revision"] == len(self.state["publications"]) + 1, "publication_order")
            self.state["publications"].append({**value, "receipt": None})
            for registration in value["registrations"]:
                for run in registration["assigned_runs"]:
                    require(
                        self.state["run_owners"].get(run, registration["worker_id"])
                        == registration["worker_id"],
                        "run_owner",
                    )
                    self.state["run_owners"][run] = registration["worker_id"]
                self.state["workers"][registration["worker_id"]]["assigned_runs"] = registration[
                    "assigned_runs"
                ]
        elif kind == "published":
            entry = self.state["publications"][value["revision"] - 1]
            require(
                entry["command_sha256"] == value["command_sha256"] and entry["receipt"] is None,
                "publication_receipt",
            )
            entry["receipt"] = value["receipt"]
        elif kind == "ack":
            require(value["ack_id"] not in self.state["acks"], "ack_duplicate")
            self.state["acks"][value["ack_id"]] = value
            self.state["ack_bytes"] += value["bytes"]
        elif kind == "ack_rejected":
            key = str(value["location"]["offset"])
            require(key not in self.state["ack_rejected_positions"], "ack_rejection_duplicate")
            self.state["ack_rejected_positions"][key] = value["location"]["value_sha256"]
            self.state["ack_rejections"] += 1
            self.state["ack_bytes"] += value["bytes"]
        elif kind == "ack_cursor":
            require(
                type(value["next_offset"]) is int
                and value["next_offset"] >= self.state["ack_cursor"],
                "ack_cursor",
            )
            self.state["ack_cursor"] = value["next_offset"]
        elif kind in ("start", "stop", "launch"):
            self.state["jobs"][value["worker_id"]] = value
        elif kind == "injection":
            pass
        elif kind == "qualification_batch_intent":
            require(
                set(value)
                == {
                    "operation_id",
                    "worker_id",
                    "incarnation",
                    "command_sha256",
                    "request_sha256",
                    "cluster_id",
                    "topic",
                    "topic_id",
                    "count",
                }
                and value["operation_id"] not in self.state["qualification_batches"]
                and len(self.state["qualification_batches"]) < 64
                and type(value["count"]) is int
                and 1 <= value["count"] <= 128,
                "qualification_batch_intent",
            )
            canonical_uuid(value["operation_id"])
            self.state["qualification_batches"][value["operation_id"]] = {
                **value,
                "status": "pending",
                "admitted": [],
            }
        elif kind == "qualification_batch_result":
            require(
                set(value) == {"operation_id", "status"}
                and value["status"] in ("complete", "failed", "recovered"),
                "qualification_batch_result",
            )
            batch = self.state["qualification_batches"][value["operation_id"]]
            require(batch["status"] == "pending", "qualification_batch_terminal")
            if value["status"] == "complete":
                require(len(batch["admitted"]) == batch["count"], "qualification_batch_incomplete")
            batch["status"] = value["status"]
        elif kind == "admit":
            marker = value.get("qualification_batch")
            if marker is not None:
                require(
                    set(marker) == {"operation_id", "index", "request_sha256", "receipt_sha256"}
                    and type(marker["index"]) is int,
                    "qualification_batch_admit",
                )
                batch = self.state["qualification_batches"][marker["operation_id"]]
                require(
                    batch["worker_id"] == value["worker_id"]
                    and batch["request_sha256"] == marker["request_sha256"]
                    and 0 <= marker["index"] < batch["count"],
                    "qualification_batch_admit",
                )
                digest = identity(value)
                if marker["index"] < len(batch["admitted"]):
                    require(
                        batch["admitted"][marker["index"]] == digest,
                        "qualification_batch_admit_conflict",
                    )
                    return
                require(
                    marker["index"] == len(batch["admitted"])
                    and batch["status"] in ("pending", "failed", "recovered"),
                    "qualification_batch_admit_order",
                )
                batch["admitted"].append(digest)
            self.state["admissions"] += 1
        else:
            raise RuntimeError("lifecycle_runtime_unknown_record")

    def _append(self, kind, value, recovery=False):
        record = dict(
            sequence=self.state["sequence"] + 1,
            previous_sha256=self.state["sha256"],
            kind=kind,
            value=value,
        )
        data = local.wrapped(record)
        require(len(data) <= 65536, "record_limit")
        self._reserve(len(data) + 65536, recovery)
        path = self.root / "journal" / f"{record['sequence']:020d}.json"
        local.write_exclusive(path, data)
        local.sync_directory(path.parent)
        HOOK("after_record_publication")
        save(self.root / "head.json", dict(sequence=record["sequence"], sha256=identity(record)))
        self._apply(kind, value)
        self.state.update(sequence=record["sequence"], sha256=identity(record))

    def _retain_failure(self, failure):
        """Best effort exact original helper output; never replace the underlying failure."""
        try:
            stdout = getattr(failure, "stdout", b"") or b""
            stderr = getattr(failure, "stderr", b"") or b""
            if isinstance(stdout, str):
                stdout = stdout.encode()
            if isinstance(stderr, str):
                stderr = stderr.encode()
            require(len(stdout) + len(stderr) <= 4 * MIB, "diagnostic_limit")
            self._reserve(len(stdout) + len(stderr) + 65536, recovery=True)
            base = self.root / "failures"
            if not base.exists():
                base.mkdir(mode=0o700)
            folder = base / uuid.uuid4().hex
            folder.mkdir(mode=0o700)
            local.write_exclusive(folder / "stdout.bin", stdout)
            local.write_exclusive(folder / "stderr.bin", stderr)
            local.write_exclusive(
                folder / "failure.json",
                encoded(
                    dict(
                        exception_class=type(failure).__name__,
                        returncode=getattr(failure, "returncode", None),
                        stdout_sha256=sha(stdout),
                        stderr_sha256=sha(stderr),
                    )
                ),
            )
            local.sync_directory(folder)
            local.sync_directory(base)
        except (OSError, ValueError):
            pass

    def _local(self, *args):
        self._verify_immutable_inputs()
        try:
            return self._local_java(self.root, *args)
        except (OSError, ValueError, subprocess.TimeoutExpired) as failure:
            self._retain_failure(failure)
            raise

    def _verify_signature(self, kind, public_path, path, payload):
        proof = local.document(self._local("verify", DOMAINS[kind], public_path, path).encode())
        require(isinstance(proof, dict), "helper_invalid_result")
        if proof.get("verified") is False and proof.get("category") == "signature_invalid":
            raise RuntimeError("lifecycle_runtime_signature_invalid")
        require(
            proof.get("verified") is True
            and proof.get("payload") == payload
            and proof.get("payload_sha256") == identity(payload),
            "helper_invalid_result",
        )
        return proof

    def _sign(self, kind, payload, directory):
        schema_kind = kind
        source = directory / (kind + "-payload.json")
        target = directory / (kind + "-signed.json")
        local.write_exclusive(source, encoded(payload))
        self._local(
            "sign",
            DOMAINS[kind],
            self.root / "authority/private.der",
            self.root / "authority/public.der",
            source,
            target,
        )
        target.chmod(0o600)
        wire = private_file(
            target, LIMITS["artifact_record_bytes"] if kind == "artifact" else 65536
        )
        signed = local.document(wire)
        schema(schema_kind, signed)
        require(signed["payload"] == payload, "signed_payload")
        self._verify_signature(kind, self.root / "authority/public.der", target, payload)
        return wire

    def _network(self, *args, timeout=120):
        self._verify_immutable_inputs()
        broker = self.state["broker"]
        require(broker is not None, "broker_required")
        operation = uuid.uuid4().hex
        name = self.config["project"] + "-helper-" + operation[:12]
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--label",
            "io.detectbridge.p15b.operation=" + operation,
            "--label",
            "io.detectbridge.p15b.owner=" + self.config["deployment_id"],
            "--network",
            self.config["project"] + "_internal",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
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
            "--mount",
            f"type=bind,src={self.root},dst=/io",
            "--entrypoint",
            "java",
            IMAGE,
            "-Xmx256m",
            "-cp",
            "/io/artifacts/runtime.jar:/io/artifacts/producer.jar:/opt/flink/lib/*",
            "io.detectbridge.integration.LifecycleTool",
            *args,
        ]
        try:
            return local.document(self._command(command, timeout).encode())
        except (OSError, ValueError, subprocess.TimeoutExpired) as failure:
            self._retain_failure(failure)
            self._cleanup_helper(name, operation)
            raise

    def _cleanup_helper(self, name, operation):
        """Only the exact operation-owned helper may be stopped after a failed call."""
        require(
            name.startswith(self.config["project"] + "-helper-")
            and re.fullmatch(r"[a-f0-9]{32}", operation),
            "helper_owner",
        )
        result = subprocess.run(
            ["docker", "inspect", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        if result.returncode:
            require(
                isinstance(result.stderr, bytes)
                and len(result.stderr) <= 65536
                and re.search(rb"(?:No such object|No such container):", result.stderr, re.I),
                "helper_fence_unconfirmed",
            )
            return
        require(len(result.stdout) <= 2 * MIB, "diagnostic_limit")
        items = local.document(result.stdout)
        require(len(items) == 1, "helper_owner")
        labels = items[0]["Config"].get("Labels", {})
        require(
            labels.get("io.detectbridge.p15b.owner") == self.config["deployment_id"]
            and labels.get("io.detectbridge.p15b.operation") == operation,
            "helper_owner",
        )
        container_id = items[0].get("Id")
        require(
            isinstance(container_id, str) and re.fullmatch(r"[a-f0-9]{64}", container_id),
            "helper_owner",
        )
        self._command(["docker", "rm", "-f", container_id], timeout=30)

    def _path(self, path):
        path = local.path_safe(path)
        require(path == self.root or self.root in path.parents, "helper_path")
        return "/io/" + str(path.relative_to(self.root))

    def _compose(self, project, file, *args, timeout=180):
        require(
            project == self.config["project"]
            or any(w["flink_project"] == project for w in self.state["workers"].values()),
            "foreign_project",
        )
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")
        }
        result = subprocess.run(
            ["docker", "compose", "--project-name", project, "--file", str(file), *map(str, args)],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            failure: Any = RuntimeError("lifecycle_runtime_compose_failed")
            failure.stdout, failure.stderr, failure.returncode = (
                result.stdout,
                result.stderr,
                result.returncode,
            )
            self._retain_failure(failure)
            raise failure
        require(
            len(result.stdout) < 2 * MIB and len(result.stderr) < 2 * MIB, "helper_output_limit"
        )
        return result.stdout.decode()

    def _broker_definition(self, cluster):
        kafka = copy.deepcopy(load_json(ROOT / "deploy/local/compose.yml")["services"]["kafka"])
        kafka.pop("profiles", None)
        kafka["environment"]["CLUSTER_ID"] = cluster
        kafka["volumes"] = ["kafka-data:/var/lib/kafka/data"]
        kafka["labels"] = {"io.detectbridge.p15b.owner": self.config["deployment_id"]}
        return dict(
            services=dict(kafka=kafka),
            volumes={
                "kafka-data": {"external": True, "name": self.config["project"] + "_kafka-data"}
            },
            networks={"internal": {"internal": True}},
        )

    def up(self):
        with self._locked():
            self._load()
            self._verify_broker_owner(allow_missing=True)
            if self.state["broker"] and self.state["broker"]["topics"]:
                file = self.root / "broker.compose.json"
                require(
                    local.document(private_file(file))
                    == self._broker_definition(self.state["broker"]["cluster_id"]),
                    "broker_configuration",
                )
                self._compose(self.config["project"], file, "up", "-d", "--wait", "kafka")
                topics = dict(self.state["broker"]["topics"])
                for worker, registration in self.state["workers"].items():
                    topics[worker] = dict(
                        name=registration["input_topic"], id=registration["input_topic_id"]
                    )
                with self._temporary(recovery=True) as temporary:
                    request = temporary / "topics.json"
                    local.write_exclusive(
                        request, encoded({value["name"]: 1 for value in topics.values()})
                    )
                    observed = self._network("inspect", "kafka:9092", self._path(request))
                require(
                    observed["cluster_id"] == self.state["broker"]["cluster_id"], "cluster_identity"
                )
                require(
                    all(
                        observed["topics"][value["name"]]["id"] == value["id"]
                        for value in topics.values()
                    ),
                    "topic_identity",
                )
                return copy.deepcopy(self.state["broker"])
            file = self.root / "broker.compose.json"
            if file.exists():
                compose = local.document(private_file(file))
                cluster = compose["services"]["kafka"]["environment"]["CLUSTER_ID"]
                require(compose == self._broker_definition(cluster), "broker_configuration")
            else:
                cluster = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")
                compose = self._broker_definition(cluster)
                local.write_exclusive(file, encoded(compose))
                local.sync_directory(self.root)
            require(re.fullmatch(r"[A-Za-z0-9_-]{22}", cluster), "cluster_identity")
            if self.state["broker"] is None:
                self._append("broker", dict(cluster_id=cluster, topics={}))
            require(self.state["broker"]["cluster_id"] == cluster, "cluster_identity")
            volume = self.config["project"] + "_kafka-data"
            inspected = subprocess.run(
                ["docker", "volume", "inspect", volume], capture_output=True, check=False
            )
            if inspected.returncode == 0:
                info = local.document(inspected.stdout)[0]
                require(
                    (info.get("Labels") or {}).get("io.detectbridge.p15b.owner")
                    == self.config["deployment_id"],
                    "foreign_volume",
                )
            else:
                self._command(
                    [
                        "docker",
                        "volume",
                        "create",
                        "--label",
                        "io.detectbridge.p15b.owner=" + self.config["deployment_id"],
                        volume,
                    ]
                )
            self._command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--user",
                    "0:0",
                    "--cap-drop",
                    "ALL",
                    "--cap-add",
                    "CHOWN",
                    "--cap-add",
                    "DAC_OVERRIDE",
                    "--cap-add",
                    "FOWNER",
                    "--memory",
                    "128m",
                    "--mount",
                    f"type=volume,src={volume},dst=/target",
                    "--entrypoint",
                    "bash",
                    IMAGE,
                    "-ceu",
                    "chmod 700 /target; chown 1000:1000 /target",
                ]
            )
            self._compose(self.config["project"], file, "up", "-d", "--wait", "kafka")
            prefix = self.config["project"] + "."
            names = {
                role: dict(name=prefix + role, id="pending", partition=0)
                for role in ("control", "artifact", "ack", "output")
            }
            with self._temporary() as temp:
                request = temp / "topics.json"
                local.write_exclusive(request, encoded(topic_limits(names)))
                observed = self._network("create", "kafka:9092", self._path(request))
            require(observed["cluster_id"] == cluster, "cluster_identity")
            # Store topic identity registration in a distinct durable record without rewriting genesis.
            self._append(
                "broker_topics",
                dict(
                    topics={
                        role: dict(
                            name=desc["name"],
                            id=observed["topics"][desc["name"]]["id"],
                            partition=0,
                        )
                        for role, desc in names.items()
                    }
                ),
            )
            return self.state["broker"]

    @contextlib.contextmanager
    def _temporary(self, recovery=False):
        self._reserve(2 * MIB, recovery=recovery)
        folder = self.root / "temporary" / uuid.uuid4().hex
        folder.mkdir(mode=0o700)
        try:
            yield folder
        finally:
            shutil.rmtree(folder)
            local.sync_directory(folder.parent)

    def _common(self):
        broker = self.state["broker"]
        require(
            broker is not None
            and set(broker["topics"]) == {"control", "artifact", "ack", "output"},
            "broker_required",
        )
        return {**self.config, "cluster_id": broker["cluster_id"], "topics": broker["topics"]}

    def worker(self, worker_id, assigned_runs=None, replacement=False):
        canonical_uuid(worker_id)
        runs = sorted(canonical_uuid(run) for run in (assigned_runs or []))
        require(len(runs) <= 16 and len(runs) == len(set(runs)), "run_limit")
        with self._locked():
            self._load()
            existing = self.state["workers"].get(worker_id)
            if existing and not replacement:
                return {
                    **{key: value for key, value in existing.items() if key != "flink_project"},
                    "assigned_runs": runs
                    if assigned_runs is not None
                    else existing["assigned_runs"],
                }
            require(existing is not None or len(self.state["workers"]) < 16, "worker_limit")
            require(len(self.state["incarnation_keys"]) < 256, "incarnation_limit")
            if replacement:
                require(existing is not None, "worker_missing")
                if assigned_runs is None:
                    runs = list(existing["assigned_runs"])
                self._verify_stopped(existing)
            common = self._common()
            incarnation = str(uuid.uuid4())
            folder = self.root / "workers" / worker_id
            if not folder.exists():
                folder.mkdir(mode=0o700)
            incarnation_root = folder / incarnation
            incarnation_root.mkdir(mode=0o700)
            self._local("keygen", incarnation_root / "private.der", incarnation_root / "public.der")
            for name in ("private.der", "public.der"):
                (incarnation_root / name).chmod(0o600)
            public = private_file(incarnation_root / "public.der", 64)
            topic_name = (
                existing["input_topic"]
                if existing
                else self.config["project"] + ".input." + uuid.UUID(worker_id).hex
            )
            with self._temporary() as temp:
                source = temp / "topics.json"
                local.write_exclusive(source, encoded({topic_name: 2 * MIB + 65536}))
                observed = self._network("create", "kafka:9092", self._path(source))
            require(observed["cluster_id"] == common["cluster_id"], "cluster_identity")
            if existing:
                require(
                    observed["topics"][topic_name]["id"] == existing["input_topic_id"],
                    "input_topic_identity",
                )
            registration = dict(
                worker_id=worker_id,
                incarnation=incarnation,
                public_key=base64.b64encode(public).decode(),
                input_topic=topic_name,
                input_topic_id=observed["topics"][topic_name]["id"],
                assigned_runs=runs,
            )
            self._control_syntax_example(registration)
            registration["flink_project"] = (
                self.config["project"] + "-" + sha(worker_id.encode())[:12]
            )
            self._append("worker", registration)
            return {key: value for key, value in registration.items() if key != "flink_project"}

    def _control_syntax_example(self, registration):
        # Validate reusable registration schema directly, not fabricated policy proof.
        item = load_json(SCHEMAS / "common.schema.json")
        validator = StrictValidator(item["$defs"]["registration"], format_checker=FormatChecker())
        require(not list(validator.iter_errors(registration)), "registration")
        return registration

    def _registrations(self, registrations):
        registrations = local.document(encoded(registrations))
        require(isinstance(registrations, list) and 1 <= len(registrations) <= 16, "membership")
        workers, keys, topics, runs = set(), set(), set(), {}
        result = []
        for supplied in registrations:
            registration = {key: value for key, value in supplied.items() if key != "flink_project"}
            self._control_syntax_example(registration)
            worker = self.state["workers"].get(registration["worker_id"])
            require(
                worker is not None
                and all(
                    worker[key] == registration[key]
                    for key in ("incarnation", "public_key", "input_topic", "input_topic_id")
                ),
                "worker_registration",
            )
            require(
                registration["worker_id"] not in workers
                and registration["public_key"] not in keys
                and registration["input_topic_id"] not in topics,
                "membership_unique",
            )
            require(
                registration["assigned_runs"] == sorted(set(registration["assigned_runs"])),
                "run_order",
            )
            for run in registration["assigned_runs"]:
                require(
                    run not in runs
                    and self.state["run_owners"].get(run, registration["worker_id"])
                    == registration["worker_id"],
                    "run_owner",
                )
                runs[run] = registration["worker_id"]
            owned = {
                run
                for run, owner in self.state["run_owners"].items()
                if owner == registration["worker_id"]
            }
            require(len(owned | set(registration["assigned_runs"])) <= 16, "lifetime_run_limit")
            workers.add(registration["worker_id"])
            keys.add(registration["public_key"])
            topics.add(registration["input_topic_id"])
            result.append(registration)
        require(len(set(self.state["run_owners"]) | set(runs)) <= 256, "deployment_run_limit")
        require([r["worker_id"] for r in result] == sorted(workers), "membership_order")
        return result

    def publish(self, store, proposal, registrations, expected_revision, expected_hash):
        require(isinstance(store, local.Store), "candidate_store_required")
        # Hold P15a's real operation exclusion through adoption to prevent a readiness race.
        with store._locked(), self._locked():
            store._load()
            self._load()
            return self._publish_locked(
                store,
                local.document(encoded(proposal)),
                registrations,
                expected_revision,
                expected_hash,
            )

    def _publish_locked(self, store, proposal, registrations, expected_revision, expected_hash):
        candidate.require(
            "request",
            dict(
                version="1.0.0",
                authority_id=proposal["authority_id"],
                request_id=proposal["request_id"],
                operation="prepare",
                bundle_sha256=proposal["bundle_sha256"],
                arguments=dict(
                    command=proposal, expected_preparation_revision=proposal["revision"] - 1
                ),
            ),
        )
        common = self._common()
        registrations = [
            {key: value for key, value in item.items() if key != "flink_project"}
            for item in local.document(encoded(registrations))
        ]
        prior = self.state["publications"]
        existing = next(
            (entry for entry in prior if entry["request_id"] == proposal["request_id"]), None
        )
        adoption = dict(
            proposal=proposal,
            registrations=registrations,
            runtime_binding_sha256=runtime_binding(common),
        )
        if existing:
            require(existing["adoption_sha256"] == identity(adoption), "adoption_conflict")
            return self._finish_publication(existing)
        registrations = self._registrations(registrations)
        require(
            proposal["authority_id"] == self.config["authority_id"]
            and proposal["deployment_id"] == self.config["deployment_id"],
            "proposal_authority",
        )
        pairs = [{key: r[key] for key in ("worker_id", "incarnation")} for r in registrations]
        require(proposal["participants"] == pairs, "proposal_membership")
        target = proposal["bundle_sha256"]
        state = store.bundles.get(target)
        require(
            state is not None and state["staged"] and state["tested"] and not state["retired"],
            "candidate_not_staged",
        )
        prepared = store.requests.get(proposal["request_id"])
        require(
            prepared is not None and prepared[1].get("command") == proposal, "unprepared_proposal"
        )
        manifest = store.available[target]
        require(
            manifest["compatibility_sha256"]
            == self.config["compatibility_sha256"]
            == proposal["compatibility_sha256"],
            "compatibility",
        )
        require(
            type(expected_revision) is int
            and expected_revision == len(prior)
            and expected_hash == (prior[-1]["command_sha256"] if prior else None),
            "publication_cas",
        )
        require(
            len(prior) < 4096 and (not prior or prior[-1]["receipt"] is not None),
            "publication_pending",
        )
        published_bundles = {
            entry["bundle_sha256"] for entry in prior if entry["receipt"] is not None
        }
        if proposal["action"] == "rollback":
            require(target in published_bundles, "rollback_history")
        if proposal["action"] == "membership":
            require(prior and target == prior[-1]["bundle_sha256"], "membership_target")
        source = store.root / "bundles" / target
        manifest_bytes = local.read(source / "manifest.json", 65536)
        plan_bytes = local.read(source / "plan.json", 4 * MIB)
        destination = self.root / "bundles" / target
        if not destination.exists():
            require(len(list((self.root / "bundles").iterdir())) < 64, "bundle_limit")
            self._reserve(len(manifest_bytes) + len(plan_bytes) + 131072)
            destination.mkdir(mode=0o700)
            local.sync_directory(destination.parent)
        require(
            destination.is_dir()
            and {item.name for item in destination.iterdir()} <= {"manifest.json", "plan.json"},
            "bundle_contents",
        )
        for name, data in (("manifest.json", manifest_bytes), ("plan.json", plan_bytes)):
            path = destination / name
            if path.exists():
                require(private_file(path, 4 * MIB) == data, "bundle_conflict")
                descriptor = os.open(path, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            else:
                self._reserve(len(data) + 131072)
                local.write_exclusive(path, data)
            HOOK("after_bundle_member_" + name.split(".")[0])
        local.sync_directory(destination)
        local.sync_directory(destination.parent)
        candidate.verify_bundle(self.root / "bundles" / target)
        revision = len(prior) + 1
        payload = dict(
            version="1.0.0",
            deployment_id=self.config["deployment_id"],
            authority_id=self.config["authority_id"],
            proposal=proposal,
            proposal_sha256=identity(proposal),
            revision=revision,
            previous_control_sha256=expected_hash,
            runtime_binding_sha256=runtime_binding(common),
            registrations=registrations,
        )
        with self._temporary() as temporary:
            control_wire = self._sign("control", payload, temporary)
        intent = dict(
            version="1.0.0",
            control=local.document(control_wire),
            wire_base64=base64.b64encode(control_wire).decode(),
            command_sha256=identity(payload),
            adoption_sha256=identity(adoption),
            bundle_sha256=target,
            revision=revision,
        )
        require(len(local.wrapped(intent)) <= 65536, "publication_record_limit")
        intent_path = self.root / "publications" / (str(revision) + ".json")
        if intent_path.exists():
            require(checked(intent_path) == intent, "uncommitted_intent_conflict")
            descriptor = os.open(intent_path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            local.sync_directory(intent_path.parent)
        else:
            self._reserve(len(local.wrapped(intent)) + 131072)
            local.write_exclusive(intent_path, local.wrapped(intent))
            local.sync_directory(intent_path.parent)
        event = dict(
            revision=revision,
            intent_sha256=identity(intent),
            request_id=proposal["request_id"],
            adoption_sha256=intent["adoption_sha256"],
            command_sha256=intent["command_sha256"],
            bundle_sha256=target,
            registrations=registrations,
        )
        self._append("adopt", event)
        HOOK("after_adoption")
        return self._finish_publication(self.state["publications"][-1])

    def _finish_publication(self, entry):
        if entry["receipt"] is not None:
            return copy.deepcopy(entry)
        intent = checked(self.root / "publications" / (str(entry["revision"]) + ".json"))
        common = self._common()
        target = self.root / "bundles" / entry["bundle_sha256"]
        manifest, _ = candidate.verify_bundle(target)
        require(
            manifest["compatibility_sha256"] == self.config["compatibility_sha256"], "compatibility"
        )
        # Artifact sends may be physically repeated after uncertainty; every signature is deterministic.
        for name in ("manifest.json", "plan.json"):
            content = local.read(target / name, 4 * MIB)
            count = (len(content) + 262143) // 262144
            for index in range(count):
                block = content[index * 262144 : (index + 1) * 262144]
                payload = dict(
                    version="1.0.0",
                    deployment_id=self.config["deployment_id"],
                    authority_id=self.config["authority_id"],
                    runtime_binding_sha256=runtime_binding(common),
                    bundle_sha256=entry["bundle_sha256"],
                    member=name,
                    member_sha256=sha(content),
                    member_bytes=len(content),
                    chunk_index=index,
                    chunk_count=count,
                    chunk_sha256=sha(block),
                    data_base64=base64.b64encode(block).decode(),
                )
                with self._temporary(recovery=True) as temporary:
                    wire = self._sign("artifact", payload, temporary)
                    self._send_bytes("artifact", entry["bundle_sha256"], wire, temporary)
        with self._temporary(recovery=True) as temporary:
            wire = base64.b64decode(intent["wire_base64"], validate=True)
            require(local.document(wire) == intent["control"], "intent_wire")
            HOOK("before_control_publication")
            receipt = self._send_bytes("control", str(entry["revision"]), wire, temporary)
        HOOK("after_control_broker_ack")
        self._append(
            "published",
            dict(
                revision=entry["revision"], command_sha256=entry["command_sha256"], receipt=receipt
            ),
            recovery=True,
        )
        return copy.deepcopy(self.state["publications"][entry["revision"] - 1])

    def _send_bytes(self, role, key, wire, temporary, topic=None):
        descriptor = topic or self.state["broker"]["topics"][role]
        maximum = {
            "artifact": 524288,
            "control": 65536,
            "ack": 65536,
            "input": 2 * MIB,
            "output": 4 * MIB,
        }[role]
        require(len(wire) <= maximum, "wire_limit")
        path = temporary / ("wire-" + uuid.uuid4().hex)
        local.write_exclusive(path, wire)
        result = self._network(
            "send",
            "kafka:9092",
            self.state["broker"]["cluster_id"],
            descriptor["name"],
            descriptor["id"],
            key,
            self._path(path),
        )
        require(
            result["topic"] == descriptor["name"]
            and result["partition"] == 0
            and type(result["offset"]) is int
            and result["offset"] >= 0
            and result["value_sha256"] == sha(wire),
            "broker_ack",
        )
        return {
            **result,
            "topic_id": descriptor["id"],
            "cluster_id": self.state["broker"]["cluster_id"],
        }

    def _ack_payload(self, wire, path, temporary):
        signed = local.document(wire)
        schema("ack", signed)
        ack = signed["payload"]
        require(
            ack["deployment_id"] == self.config["deployment_id"]
            and ack["authority_id"] == self.config["authority_id"],
            "ack_deployment",
        )
        publication = (
            self.state["publications"][ack["revision"] - 1]
            if 0 < ack["revision"] <= len(self.state["publications"])
            else None
        )
        require(publication is not None, "ack_command")
        assert publication is not None
        require(
            publication["command_sha256"] == ack["command_sha256"]
            and publication["bundle_sha256"] == ack["bundle_sha256"]
            and ack["compatibility_sha256"] == self.config["compatibility_sha256"],
            "ack_command",
        )
        registration = next(
            (
                r
                for r in publication["registrations"]
                if r["worker_id"] == ack["worker_id"] and r["incarnation"] == ack["incarnation"]
            ),
            None,
        )
        require(registration is not None, "ack_registration")
        assert registration is not None
        return self._verify_ack_wire(wire, registration, temporary)

    def observe(self, limit=64):
        require(type(limit) is int and 1 <= limit <= 128, "read_limit")
        with self._locked():
            self._load()
            descriptor = self._common()["topics"]["ack"]
            group = self.config["project"] + ".controller-acks"
            self._reserve(limit * 128 * 1024 + 2 * MIB, recovery=True)
            with self._temporary(recovery=True) as temporary:
                batch = self._network(
                    "drain",
                    "kafka:9092",
                    group,
                    self.state["broker"]["cluster_id"],
                    descriptor["name"],
                    descriptor["id"],
                    str(self.state["ack_cursor"]),
                    str(limit),
                    self._path(temporary),
                )
                self._batch_scope(batch, descriptor)
                for record in batch["records"]:
                    require(
                        record["topic"] == descriptor["name"]
                        and record["partition"] == 0
                        and record["offset"] >= self.state["ack_cursor"],
                        "ack_location",
                    )
                    path = temporary / record["value_file"]
                    require(
                        path.parent == temporary and re.fullmatch(r"[0-9]{20}\.value", path.name),
                        "ack_file",
                    )
                    path.chmod(0o600)
                    wire = private_file(path, 128 * 1024)
                    require(sha(wire) == record["value_sha256"], "ack_wire")
                    try:
                        require(len(wire) <= 65536, "ack_limit")
                        ack = self._ack_payload(wire, path, temporary)
                    except ValueError as failure:
                        if isinstance(failure, IntegrityError):
                            raise
                        # Infrastructure errors never masquerade as a cryptographic rejection.
                        if str(failure) in {
                            "lifecycle_runtime_helper_failed",
                            "lifecycle_runtime_helper_invalid_result",
                            "lifecycle_runtime_helper_output_limit",
                        }:
                            raise
                        previous_rejection = self.state["ack_rejected_positions"].get(
                            str(record["offset"])
                        )
                        if previous_rejection is not None:
                            require(previous_rejection == sha(wire), "ack_rejection_conflict")
                        else:
                            require(
                                self.state["ack_rejections"] + len(self.state["acks"])
                                < LIMITS["ack_observations"]
                                and self.state["ack_bytes"] + len(wire)
                                <= LIMITS["ack_observation_bytes"],
                                "ack_budget",
                            )
                            category = str(failure)
                            if not re.fullmatch(r"lifecycle(?:_runtime)?_[a-z_]{1,64}", category):
                                category = "lifecycle_runtime_ack_invalid"
                            self._append(
                                "ack_rejected",
                                dict(
                                    location={
                                        key: record[key]
                                        for key in ("topic", "partition", "offset", "value_sha256")
                                    }
                                    | dict(
                                        cluster_id=batch["cluster_id"], topic_id=batch["topic_id"]
                                    ),
                                    category=category,
                                    bytes=len(wire),
                                ),
                                recovery=True,
                            )
                    else:
                        previous = self.state["acks"].get(ack["ack_id"])
                        if previous:
                            require(previous["wire_sha256"] == sha(wire), "ack_conflict")
                        else:
                            require(
                                self.state["ack_rejections"] + len(self.state["acks"])
                                < LIMITS["ack_observations"]
                                and self.state["ack_bytes"] + len(wire)
                                <= LIMITS["ack_observation_bytes"],
                                "ack_budget",
                            )
                            destination = self.root / "acks" / (ack["ack_id"][7:] + ".json")
                            self._reserve(len(wire) + 131072, recovery=True)
                            if destination.exists():
                                require(private_file(destination) == wire, "ack_orphan_conflict")
                            else:
                                local.write_exclusive(destination, wire)
                            with destination.open("rb") as persisted:
                                os.fsync(persisted.fileno())
                            local.sync_directory(destination.parent)
                            self._append(
                                "ack",
                                dict(
                                    ack_id=ack["ack_id"],
                                    wire_sha256=sha(wire),
                                    bytes=len(wire),
                                    payload=ack,
                                    location={
                                        key: record[key]
                                        for key in ("topic", "partition", "offset", "value_sha256")
                                    }
                                    | dict(
                                        cluster_id=batch["cluster_id"], topic_id=batch["topic_id"]
                                    ),
                                ),
                                recovery=True,
                            )
                    self._append(
                        "ack_cursor",
                        dict(next_offset=record["offset"] + 1, value_sha256=sha(wire)),
                        recovery=True,
                    )
                # Every individual proof/cursor is durable before this contiguous-prefix commit.
                if self.state["ack_cursor"] > 0:
                    committed = self._network(
                        "commit",
                        "kafka:9092",
                        group,
                        self.state["broker"]["cluster_id"],
                        descriptor["name"],
                        descriptor["id"],
                        str(self.state["ack_cursor"]),
                    )
                    self._batch_scope(committed, descriptor)
            return self.status_locked()

    def _batch_scope(self, batch, descriptor):
        require(
            isinstance(batch, dict)
            and batch.get("cluster_id") == self.state["broker"]["cluster_id"]
            and batch.get("topic_id") == descriptor["id"],
            "batch_topic_identity",
        )

    def status_locked(self):
        publications = self.state["publications"]
        current: Any = publications[-1] if publications else None
        participants = []
        for registration in current["registrations"] if current else []:
            proofs = [
                value["payload"]
                for value in self.state["acks"].values()
                if value["payload"]["worker_id"] == registration["worker_id"]
                and value["payload"]["incarnation"] == registration["incarnation"]
                and value["payload"]["command_sha256"] == current["command_sha256"]
            ]
            durable = any(
                item["phase"] == "durable" and item["category"] == "ok" for item in proofs
            )
            rejected = bool(proofs and proofs[-1]["phase"] == "rejected")
            participants.append(
                dict(
                    worker_id=registration["worker_id"],
                    incarnation=registration["incarnation"],
                    durable=durable,
                    rejected=rejected,
                    phases=sorted({p["phase"] for p in proofs}),
                )
            )
        return dict(
            version="1.0.0",
            deployment_id=self.config["deployment_id"],
            revision=current["revision"] if current else 0,
            command_sha256=current["command_sha256"] if current else None,
            publication="broker_published"
            if current and current["receipt"]
            else "adopted_pending"
            if current
            else "none",
            participants=participants,
            converged=bool(
                current
                and current["receipt"]
                and participants
                and all(p["durable"] and not p["rejected"] for p in participants)
            ),
            ack_cursor=self.state["ack_cursor"],
            run_owners=self.state["run_owners"],
            workers=self.state["workers"],
            admissions=self.state["admissions"],
            journal_sequence=self.state["sequence"],
        )

    def status(self):
        with self._locked():
            self._load()
            return copy.deepcopy(self.status_locked())

    def topic_status(self, role, worker=None):
        """Actual pinned broker watermarks; inspection is not processing completion."""
        require(role in ("control", "artifact", "ack", "output", "input"), "topic_role")
        with self._locked():
            self._load()
            if role == "input":
                registration = self.state["workers"].get(worker)
                require(registration is not None, "worker_missing")
                descriptor = dict(
                    name=registration["input_topic"], id=registration["input_topic_id"], partition=0
                )
            else:
                descriptor = self._common()["topics"][role]
            with self._temporary() as temporary:
                request = temporary / "topics.json"
                local.write_exclusive(request, encoded({descriptor["name"]: 1}))
                observed = self._network("inspect", "kafka:9092", self._path(request))
            info = observed["topics"][descriptor["name"]]
            require(
                observed["cluster_id"] == self.state["broker"]["cluster_id"]
                and info["id"] == descriptor["id"]
                and info["partitions"] == 1
                and type(info["earliest"]) is int
                and type(info["end"]) is int
                and 0 <= info["earliest"] <= info["end"],
                "topic_identity",
            )
            return dict(
                cluster_id=observed["cluster_id"],
                topic=descriptor["name"],
                topic_id=descriptor["id"],
                partition=0,
                **info,
            )

    def tool(self, *args, timeout=120):
        """Trusted low-level qualifier/admin helper; never invoked from imported content."""
        with self._locked():
            self._load()
            return self._network(*args, timeout=timeout)

    def inject(self, role, wire, key="qualification"):
        """Explicit owned-topic fault admission, retaining its real Kafka receipt."""
        require(role in ("control", "artifact", "ack"), "injection_role")
        require(
            isinstance(wire, bytes) and isinstance(key, str) and len(key) <= 128, "injection_input"
        )
        with self._locked():
            self._load()
            with self._temporary() as temporary:
                receipt = self._send_bytes(role, key, wire, temporary)
            self._append("injection", dict(role=role, receipt=receipt), recovery=True)
            return receipt

    def _verify_broker_owner(self, allow_missing=False):
        ids = self._command(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + self.config["project"],
            ]
        ).split()
        require(ids or allow_missing, "broker_container_missing")
        if not ids:
            return []
        containers = local.document(self._command(["docker", "inspect", *ids]).encode())
        for item in containers:
            labels = item["Config"].get("Labels", {})
            require(
                labels.get("io.detectbridge.p15b.owner") == self.config["deployment_id"]
                and labels.get("com.docker.compose.service") == "kafka",
                "foreign_broker",
            )
        return containers

    def fault(self, action, worker=None):
        """Explicit operator fault controls, scoped to this registered deployment only."""
        with self._locked():
            self._load()
            return self._fault_locked(action, worker)

    def _fault_locked(self, action, worker=None):
        """Owned operator fault while the caller already holds the deployment lock."""
        if action in ("broker_pause", "broker_resume", "output_reject", "output_restore"):
            self._verify_broker_owner()
            file = self.root / "broker.compose.json"
            if action.startswith("broker_"):
                self._compose(
                    self.config["project"],
                    file,
                    "pause" if action == "broker_pause" else "unpause",
                    "kafka",
                )
            else:
                descriptor = self._common()["topics"]["output"]
                self._compose(
                    self.config["project"],
                    file,
                    "exec",
                    "-T",
                    "kafka",
                    "/opt/kafka/bin/kafka-configs.sh",
                    "--bootstrap-server",
                    "kafka:9092",
                    "--alter",
                    "--entity-type",
                    "topics",
                    "--entity-name",
                    descriptor["name"],
                    "--add-config",
                    "max.message.bytes=" + ("1" if action == "output_reject" else str(4 * MIB)),
                )
        elif action in ("worker_pause", "worker_resume", "worker_kill"):
            registration = self.state["workers"].get(worker)
            require(registration is not None, "worker_missing")
            targets = [
                item
                for item in self._containers(registration)
                if item["Config"]["Labels"]["com.docker.compose.service"] == "taskmanager"
            ]
            require(len(targets) == 1, "worker_container_missing")
            command = (
                "pause"
                if action == "worker_pause"
                else "unpause"
                if action == "worker_resume"
                else "kill"
            )
            self._command(["docker", command, targets[0]["Id"]])
        else:
            raise RuntimeError("lifecycle_runtime_unknown_fault")
        return dict(action=action, worker_id=worker, status="executed")

    def evidence(self, worker_id):
        """Retain original owned container state/logs privately before destructive recovery."""
        with self._locked():
            self._load()
            worker = self.state["workers"].get(worker_id)
            require(worker is not None, "worker_missing")
            self._reserve(8 * MIB)
            base = self.root / "failures"
            if not base.exists():
                base.mkdir(mode=0o700)
            folder = base / uuid.uuid4().hex
            folder.mkdir(mode=0o700)
            descriptors = self._containers(worker)
            local.write_exclusive(folder / "containers.json", encoded(descriptors))
            for item in descriptors:
                # Docker's own max-size/max-file bound keeps retained source logs finite.
                result = subprocess.run(
                    ["docker", "logs", "--tail", "1000", item["Id"]],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                    check=False,
                )
                require(len(result.stdout) <= 3 * MIB, "diagnostic_limit")
                local.write_exclusive(folder / (item["Id"] + ".log"), result.stdout)
            local.sync_directory(folder)
            local.sync_directory(base)
            return dict(path=str(folder), containers=len(descriptors))

    def _worker_config(self, worker):
        common = self._common()
        configuration = {
            key: common[key]
            for key in (
                "version",
                "deployment_id",
                "authority_id",
                "authority_public_key",
                "authority_key_sha256",
                "cluster_id",
                "producer_sha256",
                "runtime_sha256",
                "image",
                "compatibility_sha256",
                "limits",
                "validator",
            )
        }
        configuration.update(
            worker_id=worker["worker_id"],
            incarnation=worker["incarnation"],
            worker_public_key=worker["public_key"],
            worker_key_sha256=sha(base64.b64decode(worker["public_key"], validate=True)),
            validator_socket_path="/validation/compiler.sock",
            private_key_path="/opt/detectbridge/private.der",
            bootstrap="kafka:9092",
            topics={
                **common["topics"],
                "input": dict(name=worker["input_topic"], id=worker["input_topic_id"], partition=0),
            },
            consumer_group=self.config["project"] + ".worker." + uuid.UUID(worker["worker_id"]).hex,
            store_root="/store",
            state_root="/state",
            flink_project=worker["flink_project"],
            evidence_registry_sha256=identity(dict(version="1.0.0", objects=[])),
            runtime_binding_sha256=runtime_binding(common),
        )
        configuration["worker_checkpoint_binding_sha256"] = worker_binding(configuration)
        schema("worker-config", configuration)
        return configuration

    def _worker_compose(self, worker):
        services = {}
        label = {
            "io.detectbridge.p15b.owner": self.config["deployment_id"],
            "io.detectbridge.p15b.worker": worker["worker_id"],
        }
        for name, memory, cpus, process in (
            ("jobmanager", "1g", 0.5, "768m"),
            ("taskmanager", "2g", 1.5, "1536m"),
        ):
            properties = (
                "\n".join(
                    [
                        "jobmanager.rpc.address: jobmanager",
                        "rest.bind-address: 0.0.0.0",
                        ("jobmanager" if name == "jobmanager" else "taskmanager")
                        + ".memory.process.size: "
                        + process,
                        "taskmanager.numberOfTaskSlots: 1",
                        "restart-strategy.type: none",
                        "state.checkpoints.dir: file:///state/checkpoints",
                        "state.savepoints.dir: file:///state/savepoints",
                        "execution.checkpointing.num-retained: 3",
                        "env.log.dir: /tmp/flink-logs",
                        "pipeline.classpaths: file:///opt/detectbridge/integration-job.jar",
                    ]
                )
                + "\n"
            )
            service = dict(
                image=IMAGE,
                user="9999:9999",
                entrypoint=["bash", "-ceu", 'umask 077; exec /docker-entrypoint.sh "$@"', "--"],
                command=name,
                mem_limit=memory,
                cpus=cpus,
                pids_limit=256,
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                labels=label,
                networks=["internal"] if name == "jobmanager" else ["internal", "broker"],
                volumes=[
                    "runtime:/opt/detectbridge:ro",
                    "store:/store",
                    "state:/state",
                    "validation:/validation:ro",
                    dict(
                        type="bind",
                        source=str(self.root / "artifacts/worker-logging.properties"),
                        target="/opt/flink/conf/log4j-console.properties",
                        read_only=True,
                    ),
                ],
                environment=dict(FLINK_PROPERTIES=properties),
                logging=dict(driver="json-file", options={"max-size": "10m", "max-file": "3"}),
                stop_grace_period="30s",
            )
            if name == "jobmanager":
                service["healthcheck"] = dict(
                    test=["CMD", "curl", "--fail", "--silent", "http://localhost:8081/overview"],
                    interval="5s",
                    timeout="5s",
                    retries=30,
                    start_period="15s",
                )
            else:
                service["depends_on"] = {"jobmanager": {"condition": "service_healthy"}}
            services[name] = service
        descriptor = self.config["validator"]
        services["validator"] = dict(
            image=descriptor["image_id"],
            user="9999:9999",
            network_mode="none",
            read_only=True,
            working_dir="/opt/validator",
            entrypoint=["python", "tools/lifecycle_worker_validator.py"],
            mem_limit="512m",
            cpus=1,
            pids_limit=64,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            labels=label,
            volumes=["validation:/validation"],
            tmpfs=["/tmp:rw,noexec,nosuid,size=33554432,mode=700,uid=9999,gid=9999"],
            environment=dict(
                DETECTBRIDGE_VALIDATOR_ARTIFACT=descriptor["artifact_sha256"],
                DETECTBRIDGE_VALIDATOR_IMAGE_ID=descriptor["image_id"],
                DETECTBRIDGE_VALIDATOR_BASE_IMAGE=descriptor["base_image"],
                DETECTBRIDGE_VALIDATOR_SOCKET="/validation/compiler.sock",
            ),
            logging=dict(driver="json-file", options={"max-size": "10m", "max-file": "3"}),
            stop_grace_period="15s",
        )
        return dict(
            services=services,
            volumes={
                name: {"external": True, "name": worker["flink_project"] + "_" + name}
                for name in ("runtime", "store", "state", "validation")
            },
            networks=dict(
                internal=dict(internal=True),
                broker=dict(external=True, name=self.config["project"] + "_internal"),
            ),
        )

    def _containers(self, worker):
        result = self._command(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "label=com.docker.compose.project=" + worker["flink_project"],
            ]
        )
        ids = result.split()
        if not ids:
            return []
        require(all(re.fullmatch(r"[a-f0-9]{12,64}", item) for item in ids), "container_id")
        containers = local.document(self._command(["docker", "inspect", *ids]).encode())
        for item in containers:
            labels = item["Config"].get("Labels", {})
            require(
                labels.get("io.detectbridge.p15b.owner") == self.config["deployment_id"]
                and labels.get("io.detectbridge.p15b.worker") == worker["worker_id"]
                and labels.get("com.docker.compose.project") == worker["flink_project"]
                and labels.get("com.docker.compose.service")
                in ("jobmanager", "taskmanager", "validator"),
                "foreign_container",
            )
        return containers

    def _verify_stopped(self, worker):
        require(
            not any(item["State"]["Running"] for item in self._containers(worker)),
            "old_worker_running",
        )

    def _logging_proof(self, worker):
        expected = sha(self._logging_bytes())
        proofs = {}
        for item in self._containers(worker):
            service = item["Config"]["Labels"]["com.docker.compose.service"]
            if service not in ("jobmanager", "taskmanager"):
                continue
            checksum = self._command(
                [
                    "docker",
                    "exec",
                    item["Id"],
                    "sha256sum",
                    "/opt/flink/conf/log4j-console.properties",
                ]
            ).split()
            require(checksum and checksum[0] == expected, "logging_mount_integrity")
            process = self._command(["docker", "exec", item["Id"], "cat", "/proc/1/cmdline"])
            require(
                "-Dlog4j.configurationFile=file:/opt/flink/conf/log4j-console.properties"
                in process.split("\0"),
                "logging_backend_selection",
            )
            output = self._command(["docker", "logs", "--tail", "200", item["Id"]])
            samples = []
            for line in output.splitlines():
                try:
                    value = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if (
                    isinstance(value, dict)
                    and value.get("category") == "runtime_log"
                    and {"throw_class", "throw_method", "throw_line"} <= value.keys()
                ):
                    samples.append(sha(line.encode()))
            require(samples, "logging_backend_not_observed")
            proofs[service] = dict(
                resource_sha256=expected,
                process_arguments_sha256=sha(process.encode()),
                backend_record_sha256=samples[0],
            )
        require(set(proofs) == {"jobmanager", "taskmanager"}, "logging_backend_inventory")
        return proofs

    def _initialize_worker_volumes(self, worker):
        folder = self.root / "workers" / worker["worker_id"] / worker["incarnation"]
        configuration = self._worker_config(worker)
        config_file = folder / "worker-config.json"
        if config_file.exists():
            require(
                local.document(private_file(config_file)) == configuration, "worker_configuration"
            )
        else:
            local.write_exclusive(config_file, encoded(configuration))
        registration_file = folder / "object-registration.json"
        if not registration_file.exists():
            local.write_exclusive(registration_file, encoded(dict(version="1.0.0", objects=[])))
        logging_file = folder / "log4j-console.properties"
        logging_bytes = local.read(self._logging_file(), 65536)
        if not logging_file.exists():
            local.write_exclusive(logging_file, logging_bytes)
        require(private_file(logging_file) == logging_bytes, "logging_integrity")
        project = worker["flink_project"]
        for name in ("runtime", "store", "state", "validation"):
            volume = project + "_" + name
            existing = subprocess.run(
                ["docker", "volume", "inspect", volume], capture_output=True, check=False
            )
            if existing.returncode == 0:
                info = local.document(existing.stdout)[0]
                labels = info.get("Labels") or {}
                require(
                    labels.get("io.detectbridge.p15b.owner") == self.config["deployment_id"]
                    and labels.get("io.detectbridge.p15b.worker") == worker["worker_id"],
                    "foreign_volume",
                )
            else:
                self._command(
                    [
                        "docker",
                        "volume",
                        "create",
                        "--label",
                        "io.detectbridge.p15b.owner=" + self.config["deployment_id"],
                        "--label",
                        "io.detectbridge.p15b.worker=" + worker["worker_id"],
                        volume,
                    ]
                )
        command = [
            "docker",
            "run",
            "--rm",
            "--label",
            "io.detectbridge.p15b.owner=" + self.config["deployment_id"],
            "--network",
            "none",
            "--user",
            "0:0",
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
            "--memory",
            "128m",
            "--pids-limit",
            "64",
            "--mount",
            f"type=bind,src={folder},dst=/input,readonly",
            "--mount",
            f"type=bind,src={self.root / 'artifacts'},dst=/artifacts,readonly",
        ]
        for name in ("runtime", "store", "state", "validation"):
            command += ["--mount", f"type=volume,src={project}_{name},dst=/{name}"]
        command += [
            "--entrypoint",
            "bash",
            IMAGE,
            "-ceu",
            "cp /input/worker-config.json /runtime/worker-config.json; cp /input/private.der /runtime/private.der; "
            "cp /input/object-registration.json /runtime/object-registration.json; "
            "cp /input/log4j-console.properties /runtime/log4j-console.properties; "
            "cp /artifacts/runtime.jar /runtime/lifecycle-job.jar; cp /artifacts/producer.jar /runtime/integration-job.jar; "
            "if [ -f /artifacts/qualification.jar ]; then cp /artifacts/qualification.jar /runtime/qualification.jar; fi; "
            "mkdir -p /runtime/objects; chmod 700 /runtime /runtime/objects /store /state /validation; "
            "find /runtime -type f -exec chmod 600 {} +; chown -R 9999:9999 /runtime; chown 9999:9999 /store /state /validation",
        ]
        self._command(command)
        compose_file = self.root / "workers" / worker["worker_id"] / "compose.json"
        compose = self._worker_compose(worker)
        if compose_file.exists():
            require(local.document(private_file(compose_file)) == compose, "worker_compose")
        else:
            local.write_exclusive(compose_file, encoded(compose))
        return compose_file

    def start(self, worker_id, restore=None, *, _probe=None):
        with self._locked():
            self._load()
            worker = self.state["workers"].get(worker_id)
            require(worker is not None, "worker_missing")
            self._verify_stopped(worker)
            prior = self.state["jobs"].get(worker_id)
            attempted = prior is not None and prior.get("ever_attempted", False)
            if attempted:
                require(
                    prior["incarnation"] != worker["incarnation"], "incarnation_already_attempted"
                )
                require(restore is not None, "explicit_restore_required")
            if restore is not None:
                require(
                    isinstance(restore, str)
                    and re.fullmatch(
                        r"file:///state/(checkpoints|savepoints)/[A-Za-z0-9/_-]+(?:/_metadata)?",
                        restore,
                    ),
                    "restore_uri",
                )
                require(
                    prior is not None and restore in prior.get("completed_restore_paths", []),
                    "unverified_completed_restore",
                )
            launch = dict(
                worker_id=worker_id,
                incarnation=worker["incarnation"],
                job_id=None,
                state="launch_pending",
                ever_attempted=True,
                restored_from=restore,
                completed_restore_paths=prior.get("completed_restore_paths", []) if prior else [],
            )
            self._append("launch", launch)
            HOOK("after_launch_intent")
            self._verify_validator_image(self.config["validator"])
            compose = self._initialize_worker_volumes(worker)
            self._compose(worker["flink_project"], compose, "up", "-d", "--wait")
            if _probe is not None:
                self._compose(
                    worker["flink_project"],
                    compose,
                    "exec",
                    "-T",
                    "taskmanager",
                    "mkdir",
                    "-m",
                    "700",
                    "-p",
                    "/store/probes/" + _probe["operation_id"],
                )

            args = ["exec", "-T", "jobmanager", "/opt/flink/bin/flink", "run", "-d"]
            if restore:
                args += ["-s", restore]
            args += ["-C", "file:///opt/detectbridge/integration-job.jar"]
            if _probe is None:
                args += [
                    "-c",
                    "io.detectbridge.integration.LifecycleJob",
                    "/opt/detectbridge/lifecycle-job.jar",
                    "/opt/detectbridge/worker-config.json",
                ]
            else:
                args += [
                    "-C",
                    "file:///opt/detectbridge/lifecycle-job.jar",
                    "-c",
                    "io.detectbridge.integration.LifecycleQualificationJob",
                    "/opt/detectbridge/qualification.jar",
                    "/opt/detectbridge/worker-config.json",
                    _probe["mode"],
                    _probe["operation_id"],
                    _probe["sha256"],
                ]
            output = self._compose(worker["flink_project"], compose, *args)
            job_match = re.search(r"JobID ([a-f0-9]{32})", output)
            require(job_match is not None, "job_submission")
            assert job_match is not None
            logging = self._logging_proof(worker)
            value = dict(
                worker_id=worker_id,
                incarnation=worker["incarnation"],
                job_id=job_match[1],
                state="submitted",
                logging=logging,
                ever_attempted=True,
                restored_from=restore,
                completed_restore_paths=prior.get("completed_restore_paths", []) if prior else [],
            )
            self._append("start", value)
            return value

    def _verify_ack_wire(self, wire, registration, temporary):
        signed = local.document(wire)
        schema("ack", signed)
        payload = signed["payload"]
        require(
            payload["deployment_id"] == self.config["deployment_id"]
            and payload["authority_id"] == self.config["authority_id"]
            and payload["compatibility_sha256"] == self.config["compatibility_sha256"],
            "ack_deployment",
        )
        require(
            payload["worker_id"] == registration["worker_id"]
            and payload["incarnation"] == registration["incarnation"]
            and self.state["incarnation_keys"].get(payload["incarnation"])
            == registration["public_key"]
            and self.state["incarnation_workers"].get(payload["incarnation"])
            == payload["worker_id"],
            "ack_registration",
        )
        public = base64.b64decode(registration["public_key"], validate=True)
        require(sha(public) == signed["key_sha256"], "ack_key")
        key = temporary / (uuid.uuid4().hex + ".der")
        message = temporary / (uuid.uuid4().hex + ".json")
        local.write_exclusive(key, public)
        local.write_exclusive(message, wire)
        self._verify_signature("ack", key, message, payload)
        preimage = [
            DOMAINS["ack"],
            *[
                payload[name]
                for name in (
                    "deployment_id",
                    "authority_id",
                    "worker_id",
                    "incarnation",
                    "revision",
                    "command_sha256",
                    "bundle_sha256",
                    "compatibility_sha256",
                    "phase",
                    "checkpoint_id",
                    "category",
                )
            ],
        ]
        require(payload["ack_id"] == "sha256:" + identity(preimage), "ack_identity")
        return payload

    def verify_ack_wire(self, wire, registration):
        """Read-only signature/identity proof, independent of publisher adoption history."""
        require(isinstance(wire, bytes) and len(wire) <= 65536, "ack_limit")
        with self._locked():
            self._load()
            with self._temporary() as temporary:
                return self._verify_ack_wire(wire, registration, temporary)

    def inspect_acks(self, start=0, limit=16):
        require(
            type(start) is int and start >= 0 and type(limit) is int and 1 <= limit <= 128,
            "read_limit",
        )
        with self._locked():
            self._load()
            descriptor = self._common()["topics"]["ack"]
            self._reserve(limit * 128 * 1024 + 2 * MIB)
            with self._temporary() as temporary:
                batch = self._network(
                    "drain",
                    "kafka:9092",
                    self.config["project"] + ".ack-inspect",
                    self.state["broker"]["cluster_id"],
                    descriptor["name"],
                    descriptor["id"],
                    str(start),
                    str(limit),
                    self._path(temporary),
                )
                self._batch_scope(batch, descriptor)
                records = []
                for record in batch["records"]:
                    path = temporary / record["value_file"]
                    require(
                        path.parent == temporary and re.fullmatch(r"[0-9]{20}\.value", path.name),
                        "ack_file",
                    )
                    path.chmod(0o600)
                    wire = private_file(path, 128 * 1024)
                    require(sha(wire) == record["value_sha256"], "ack_wire")
                    verified, payload, category = False, None, "invalid_ack"
                    try:
                        require(len(wire) <= 65536, "ack_limit")
                        signed = local.document(wire)
                        schema("ack", signed)
                        incarnation = signed["payload"]["incarnation"]
                        registration = dict(
                            worker_id=signed["payload"]["worker_id"],
                            incarnation=incarnation,
                            public_key=self.state["incarnation_keys"].get(incarnation),
                        )
                        payload = self._verify_ack_wire(wire, registration, temporary)
                        verified, category = True, "ok"
                    except ValueError as failure:
                        if isinstance(failure, IntegrityError):
                            raise
                        if str(failure) in {
                            "lifecycle_runtime_helper_failed",
                            "lifecycle_runtime_helper_invalid_result",
                            "lifecycle_runtime_helper_output_limit",
                        }:
                            raise
                    records.append(
                        dict(
                            wire=record,
                            value_base64=base64.b64encode(wire).decode(),
                            payload=payload,
                            signature_verified=verified,
                            category=category,
                        )
                    )
                return dict(records=records, next_offset=batch["next_offset"])

    def sign_injection(self, kind, payload):
        """Explicit trusted qualifier operation, never a candidate-selected signing endpoint."""
        require(kind in ("control", "artifact"), "signing_role")
        with self._locked():
            self._load()
            with self._temporary() as temporary:
                return self._sign(kind, payload, temporary)

    def start_probe(self, worker_id, restore, probe_jar, mode, operation_root):
        require(mode in ("hold-release", "checkpoint-timeout", "partial-sink"), "probe_mode")
        operation_id = canonical_uuid(str(operation_root))
        probe_jar = local.regular(probe_jar)
        local.disjoint(self.root, probe_jar)
        data = local.read(probe_jar, 32 * MIB)
        require(data, "probe_artifact")
        with self._locked():
            self._load()
            target = self.root / "artifacts/qualification.jar"
            require(self.config.get("qualification_sha256") == sha(data), "probe_not_registered")
            require(private_file(target, 32 * MIB) == data, "probe_artifact_conflict")
        return self.start(
            worker_id, restore, _probe=dict(mode=mode, operation_id=operation_id, sha256=sha(data))
        )

    def _worker_file(self, worker_id, path, maximum=65536):
        require(
            re.fullmatch(
                r"/store/(inventory/[a-f0-9-]{36}/[0-9]{20}\.json|probes/[a-f0-9-]{36}/(?:snapshot-start\.json|sink-ack\.json|release))",
                path,
            ),
            "worker_file",
        )
        worker = self.state["workers"].get(worker_id)
        require(worker is not None, "worker_missing")
        self._containers(worker)
        file = self.root / "workers" / worker_id / "compose.json"
        text = self._compose(
            worker["flink_project"],
            file,
            "exec",
            "-T",
            "taskmanager",
            "bash",
            "-ceu",
            'if test -s "$1"; then head -c "$2" "$1"; else printf null; fi',
            "--",
            path,
            str(maximum + 1),
        )
        require(len(text.encode()) <= maximum, "worker_file_limit")
        return local.document(text.encode())

    def advisory_inventory(self, worker_id, checkpoint_id):
        """Observe owned snapshot metadata only; never establish completion or recovery authority."""
        require(type(checkpoint_id) is int and 0 <= checkpoint_id <= 2**63 - 1, "checkpoint_id")
        with self._locked():
            self._load()
            worker = self.state["workers"].get(worker_id)
            job = self.state["jobs"].get(worker_id)
            require(worker is not None and job is not None and job.get("job_id"), "job_missing")
            incarnation = worker["incarnation"]
            value = self._worker_file(
                worker_id,
                f"/store/inventory/{incarnation}/{checkpoint_id:020d}.json",
                maximum=2 * MIB,
            )
            require(
                value is not None and value.get("checkpoint_id") == checkpoint_id,
                "inventory_missing",
            )
            return dict(inventory=value)

    def worker_inventory(self, worker_id, checkpoint_id):
        require(type(checkpoint_id) is int and 0 <= checkpoint_id <= 2**63 - 1, "checkpoint_id")
        with self._locked():
            self._load()
            job = self.state["jobs"].get(worker_id)
            require(job is not None and job.get("job_id"), "job_missing")
            observed = self.rest(
                worker_id, "/jobs/" + job["job_id"] + "/checkpoints/details/" + str(checkpoint_id)
            )
            require(observed.get("status") == "COMPLETED", "checkpoint_not_completed")
            incarnation = self.state["workers"][worker_id]["incarnation"]
            value = self._worker_file(
                worker_id,
                f"/store/inventory/{incarnation}/{checkpoint_id:020d}.json",
                maximum=2 * MIB,
            )
            require(
                value is not None and value.get("checkpoint_id") == checkpoint_id,
                "inventory_missing",
            )
            return dict(checkpoint=observed, inventory=value)

    def read_probe_marker(self, worker_id, operation_root, marker):
        operation = canonical_uuid(str(operation_root))
        require(marker in ("snapshot-start.json", "sink-ack.json"), "probe_marker")
        with self._locked():
            self._load()
            return self._worker_file(worker_id, "/store/probes/" + operation + "/" + marker)

    def release_probe(self, worker_id, operation_root):
        operation = canonical_uuid(str(operation_root))
        with self._locked():
            self._load()
            worker = self.state["workers"].get(worker_id)
            require(worker is not None, "worker_missing")
            self._containers(worker)
            return self._compose(
                worker["flink_project"],
                self.root / "workers" / worker_id / "compose.json",
                "exec",
                "-T",
                "taskmanager",
                "bash",
                "-ceu",
                'umask 077; marker="$1"; '
                'if [[ ! -e "$marker" && ! -L "$marker" ]]; then '
                '(set -o noclobber; : > "$marker"); fi; '
                '[[ -f "$marker" && ! -L "$marker" ]]; '
                '[[ "$(stat -c %a:%u:%h:%s -- "$marker")" == "600:$(id -u):1:0" ]]',
                "release-probe",
                "/store/probes/" + operation + "/release",
            )

    def rest(self, worker_id, path, method="GET", data=None):
        require(isinstance(path, str) and re.fullmatch(r"/[A-Za-z0-9/_?=&.-]*", path), "rest_path")
        require(method in ("GET", "POST", "PATCH"), "rest_method")
        worker = self.state["workers"].get(worker_id)
        require(worker is not None, "worker_missing")
        compose = self.root / "workers" / worker_id / "compose.json"
        args = [
            "exec",
            "-T",
            "jobmanager",
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "20",
            "-X",
            method,
        ]
        if data is not None:
            args += ["-H", "Content-Type: application/json", "--data", encoded(data).decode()]
        args += ["http://localhost:8081" + path]
        return local.document(self._compose(worker["flink_project"], compose, *args).encode())

    def checkpoints(self, worker_id):
        with self._locked():
            self._load()
            job = self.state["jobs"].get(worker_id)
            require(job is not None and re.fullmatch(r"[a-f0-9]{32}", job["job_id"]), "job_missing")
            result = self.rest(worker_id, "/jobs/" + job["job_id"] + "/checkpoints")
            completed = result.get("latest", {}).get("completed")
            if completed:
                require(completed.get("status") == "COMPLETED", "checkpoint_not_completed")
                path = completed.get("external_path")
                require(
                    isinstance(path, str)
                    and re.fullmatch(
                        r"file:/+state/checkpoints/" + job["job_id"] + r"/chk-[0-9]+/?", path
                    ),
                    "checkpoint_path",
                )
                path = "file:///state/" + path.split("/state/", 1)[1]
                if path not in job["completed_restore_paths"]:
                    updated = {
                        **job,
                        "completed_restore_paths": [*job["completed_restore_paths"], path][-3:],
                    }
                    self._append("start", updated)
            return result

    def checkpoint(self, worker_id):
        with self._locked():
            self._load()
            job = self.state["jobs"].get(worker_id)
            require(job is not None, "job_missing")
            return self.rest(worker_id, "/jobs/" + job["job_id"] + "/checkpoints", "POST", {})

    def stop(self, worker_id=None):
        with self._locked():
            self._load()
            if worker_id is None and (self.root / "broker.compose.json").exists():
                self._verify_broker_owner(allow_missing=True)
            workers = (
                [self.state["workers"][worker_id]]
                if worker_id
                else list(self.state["workers"].values())
            )
            for worker in workers:
                self._containers(worker)  # Fail before mutating any foreign project.
                compose = self.root / "workers" / worker["worker_id"] / "compose.json"
                if compose.exists():
                    self._compose(worker["flink_project"], compose, "stop")
                self._verify_stopped(worker)
                previous = self.state["jobs"].get(worker["worker_id"], {})
                self._append(
                    "stop",
                    {
                        **previous,
                        "worker_id": worker["worker_id"],
                        "incarnation": worker["incarnation"],
                        "state": "stopped",
                        "ever_attempted": previous.get("ever_attempted", False),
                    },
                )
            if worker_id is None and (self.root / "broker.compose.json").exists():
                self._compose(self.config["project"], self.root / "broker.compose.json", "stop")
            return dict(status="stopped", workers=[w["worker_id"] for w in workers])

    def replace(self, worker_id, restore):
        # Stops only the proven owned cluster; a replacement never races an unfenced predecessor.
        self.stop(worker_id)
        worker = self.worker(worker_id, replacement=True)
        return dict(
            registration=worker,
            restore=restore,
            status="replacement_registered_locally_requires_signed_membership_before_fresh_work",
        )

    def _qualification_admission_allowed(self, worker_id):
        require(
            not any(
                batch["worker_id"] == worker_id and batch["status"] != "complete"
                for batch in self.state["qualification_batches"].values()
            ),
            "qualification_batch_worker_blocked",
        )

    @staticmethod
    def _batch_document(path, maximum):
        data = private_file(path, maximum)
        value = local.document(data)
        require(isinstance(value, dict) and encoded(value) == data, "qualification_batch_canonical")
        return value, data

    def _batch_request(self, batch):
        operation = batch["operation_id"]
        folder = self.root / "qualification-batches" / operation
        request, wire = self._batch_document(folder / "request.json", 65536)
        require(
            sha(wire) == batch["request_sha256"]
            and set(request)
            == {
                "version",
                "operation_id",
                "worker_id",
                "incarnation",
                "command_sha256",
                "cluster_id",
                "topic",
                "topic_id",
                "records",
            },
            "qualification_batch_request",
        )
        require(
            request["version"] == "1.0.0"
            and all(
                request[key] == batch[key]
                for key in (
                    "operation_id",
                    "worker_id",
                    "incarnation",
                    "command_sha256",
                    "cluster_id",
                    "topic",
                    "topic_id",
                )
            ),
            "qualification_batch_scope",
        )
        records = request["records"]
        require(
            isinstance(records, list) and len(records) == batch["count"],
            "qualification_batch_records",
        )
        publication: Any = next(
            (
                item
                for item in self.state["publications"]
                if item["command_sha256"] == batch["command_sha256"]
            ),
            None,
        )
        require(
            publication is not None and publication["receipt"], "qualification_batch_publication"
        )
        registration: Any = next(
            (
                item
                for item in publication["registrations"]
                if item["worker_id"] == batch["worker_id"]
                and item["incarnation"] == batch["incarnation"]
            ),
            None,
        )
        require(
            registration is not None
            and batch["cluster_id"] == self.state["broker"]["cluster_id"]
            and batch["topic"] == registration["input_topic"]
            and batch["topic_id"] == registration["input_topic_id"],
            "qualification_batch_scope",
        )
        total = 0
        for index, record in enumerate(records):
            require(
                isinstance(record, dict)
                and set(record)
                == {"index", "run_id", "key_base64", "value_file", "value_bytes", "value_sha256"},
                "qualification_batch_record",
            )
            canonical_uuid(record["run_id"])
            require(
                record["run_id"] in registration["assigned_runs"]
                and self.state["run_owners"].get(record["run_id"]) == batch["worker_id"],
                "qualification_batch_run_owner",
            )
            require(
                type(record["index"]) is int
                and record["index"] == index
                and record["value_file"] == f"{index:020d}.value"
                and type(record["value_bytes"]) is int
                and 1 <= record["value_bytes"] <= 2 * MIB
                and isinstance(record["value_sha256"], str)
                and re.fullmatch(r"[a-f0-9]{64}", record["value_sha256"])
                and record["key_base64"] == base64.b64encode(record["run_id"].encode()).decode(),
                "qualification_batch_record",
            )
            total += record["value_bytes"]
        require(total <= 8 * MIB, "qualification_batch_bytes")
        return folder, request

    def _batch_value(self, folder, record):
        data = private_file(folder / "values" / record["value_file"], 2 * MIB)
        require(
            len(data) == record["value_bytes"] and sha(data) == record["value_sha256"],
            "qualification_batch_value",
        )
        return data

    def _qualification_batch_prefix(self, batch, journal=True):
        """Certify in order; a corrupt later member cannot erase a forced earlier admission."""
        folder, request = self._batch_request(batch)
        receipts: list[dict[str, Any]] = []
        hashes: list[str] = []
        last_offset = -1
        unreceipted = 0
        batch["uncertain_index"] = None
        for index, record in enumerate(request["records"]):
            self._batch_value(folder, record)
            name = f"{index:020d}.json"
            paths = [folder / role / name for role in ("attempts", "acknowledgments", "receipts")]
            present = [path.exists() or path.is_symlink() for path in paths]
            if not any(present):
                continue
            require(unreceipted == 0 and len(receipts) == index, "qualification_batch_prefix")
            require(present[0], "qualification_batch_missing_attempt")
            attempt, attempt_wire = self._batch_document(paths[0], 4096)
            expected = dict(
                version="1.0.0",
                operation_id=batch["operation_id"],
                request_sha256=batch["request_sha256"],
                index=index,
                cluster_id=batch["cluster_id"],
                topic=batch["topic"],
                topic_id=batch["topic_id"],
                partition=0,
                key_sha256=sha(record["run_id"].encode()),
                value_sha256=record["value_sha256"],
                value_bytes=record["value_bytes"],
            )
            require(
                attempt == expected
                and type(attempt["index"]) is int
                and type(attempt["partition"]) is int
                and type(attempt["value_bytes"]) is int,
                "qualification_batch_attempt",
            )
            acknowledgement: Any = None
            ack_wire: Any = None
            if present[1]:
                acknowledgement, ack_wire = self._batch_document(paths[1], 4096)
                require(
                    set(acknowledgement)
                    == {
                        "version",
                        "operation_id",
                        "request_sha256",
                        "index",
                        "topic",
                        "partition",
                        "offset",
                        "key_sha256",
                        "value_sha256",
                        "broker_timestamp",
                    }
                    and all(
                        acknowledgement[key] == expected[key]
                        for key in (
                            "version",
                            "operation_id",
                            "request_sha256",
                            "index",
                            "topic",
                            "partition",
                            "key_sha256",
                            "value_sha256",
                        )
                    )
                    and type(acknowledgement["index"]) is int
                    and type(acknowledgement["partition"]) is int
                    and type(acknowledgement["offset"]) is int
                    and last_offset < acknowledgement["offset"] <= 9223372036854775807
                    and type(acknowledgement["broker_timestamp"]) is int
                    and -1 <= acknowledgement["broker_timestamp"] <= 9223372036854775807,
                    "qualification_batch_acknowledgment",
                )
            if not present[2]:
                unreceipted = 1
                batch["uncertain_index"] = index
                continue  # A raw broker ACK never substitutes for post-send namespace proof.
            require(acknowledgement is not None, "qualification_batch_missing_acknowledgment")
            receipt, receipt_wire = self._batch_document(paths[2], 4096)
            require(
                receipt
                == {
                    **expected,
                    "offset": acknowledgement["offset"],
                    "broker_timestamp": acknowledgement["broker_timestamp"],
                    "acknowledgment_sha256": sha(ack_wire),
                }
                and all(
                    type(receipt[key]) is int
                    for key in ("index", "partition", "value_bytes", "offset", "broker_timestamp")
                ),
                "qualification_batch_receipt",
            )
            require(
                sha(private_file(folder / "request.json", 65536)) == batch["request_sha256"],
                "qualification_batch_request_changed",
            )
            self._batch_value(folder, record)
            # Force surviving files and namespace before any journal reference, including recovery.
            for path, original in zip(paths, (attempt_wire, ack_wire, receipt_wire), strict=True):
                require(private_file(path, 4096) == original, "qualification_batch_changed")
                with path.open("rb") as stream:
                    os.fsync(stream.fileno())
                local.sync_directory(path.parent)
            local.sync_directory(folder)
            admitted_receipt = dict(
                topic=batch["topic"],
                topic_id=batch["topic_id"],
                partition=0,
                offset=receipt["offset"],
                value_sha256=record["value_sha256"],
                cluster_id=batch["cluster_id"],
            )
            admission = dict(
                worker_id=batch["worker_id"],
                run_id=record["run_id"],
                receipt=admitted_receipt,
                qualification_batch=dict(
                    operation_id=batch["operation_id"],
                    index=index,
                    request_sha256=batch["request_sha256"],
                    receipt_sha256=sha(receipt_wire),
                ),
            )
            if index < len(batch["admitted"]):
                require(
                    batch["admitted"][index] == identity(admission),
                    "qualification_batch_admit_conflict",
                )
            elif journal:
                self._append("admit", admission, recovery=True)
            else:
                require(False, "qualification_batch_unjournaled_receipt")
            last_offset = receipt["offset"]
            receipts.append(admitted_receipt)
            hashes.append(sha(receipt_wire))
        # Closed layout is checked after the certifiable prefix has become durable facts.
        require(
            {item.name for item in folder.iterdir()}
            <= {"request.json", "values", "attempts", "acknowledgments", "receipts"}
            | {
                item.name
                for item in folder.iterdir()
                if re.fullmatch(r"\.partial-[a-f0-9-]{36}", item.name)
            },
            "qualification_batch_layout",
        )
        require(
            {item.name for item in (folder / "values").iterdir()}
            == {record["value_file"] for record in request["records"]},
            "qualification_batch_values",
        )
        for role in ("attempts", "acknowledgments", "receipts"):
            for path in (folder / role).iterdir():
                if re.fullmatch(r"\.partial-[a-f0-9-]{36}", path.name):
                    private_file(path, 4096)
                    continue
                require(
                    re.fullmatch(r"[0-9]{20}\.json", path.name) and int(path.stem) < batch["count"],
                    "qualification_batch_layout",
                )
        require(len(batch["admitted"]) == len(receipts), "qualification_batch_receipt_missing")
        return receipts, hashes

    def _fence_qualification_batch(self, operation):
        token = uuid.UUID(operation).hex
        self._cleanup_helper(self.config["project"] + "-helper-" + token[:12], token)

    def _qualification_batch_helper(self, batch, folder):
        self._verify_immutable_inputs()
        token = uuid.UUID(batch["operation_id"]).hex
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            self.config["project"] + "-helper-" + token[:12],
            "--label",
            "io.detectbridge.p15b.operation=" + token,
            "--label",
            "io.detectbridge.p15b.owner=" + self.config["deployment_id"],
            "--network",
            self.config["project"] + "_internal",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
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
            "--mount",
            f"type=bind,src={self.root},dst=/io",
            "--entrypoint",
            "java",
            IMAGE,
            "-Xmx256m",
            "-cp",
            "/io/artifacts/runtime.jar:/io/artifacts/producer.jar:/io/artifacts/qualification.jar:/opt/flink/lib/*",
            "io.detectbridge.integration.LifecycleBatchProducer",
            self.config["qualification_sha256"],
            self.config["runtime_sha256"],
            "kafka:9092",
            batch["cluster_id"],
            batch["topic"],
            batch["topic_id"],
            self._path(folder),
            batch["request_sha256"],
        ]
        return local.document(self._command(command, timeout=120).encode())

    def admit_qualification_batch(self, worker_id, rows):
        require(isinstance(rows, list) and 1 <= len(rows) <= 128, "admission_count")
        with self._locked():
            self._load()
            self._qualification_admission_allowed(worker_id)
            require(self.config.get("qualification_sha256") is not None, "probe_not_registered")
            worker = self.state["workers"].get(worker_id)
            require(
                worker is not None
                and self.state["publications"]
                and self.state["publications"][-1]["receipt"],
                "no_published_policy",
            )
            publication = self.state["publications"][-1]
            registration: Any = next(
                (r for r in publication["registrations"] if r["worker_id"] == worker_id), None
            )
            require(
                registration is not None and registration["incarnation"] == worker["incarnation"],
                "not_current_member",
            )
            records, wires = [], []
            for index, row in enumerate(rows):
                wire = row if isinstance(row, bytes) else encoded(row)
                require(1 <= len(wire) <= 2 * MIB, "raw_limit")
                value = local.document(wire)
                run = (
                    value.get("run_id")
                    if value.get("kind") in ("run_end", "source_boundary")
                    else value.get("context", {}).get("run_id")
                )
                canonical_uuid(run)
                require(
                    run in registration["assigned_runs"]
                    and self.state["run_owners"].get(run) == worker_id,
                    "unassigned_run",
                )
                records.append(
                    dict(
                        index=index,
                        run_id=run,
                        key_base64=base64.b64encode(run.encode()).decode(),
                        value_file=f"{index:020d}.value",
                        value_bytes=len(wire),
                        value_sha256=sha(wire),
                    )
                )
                wires.append(wire)
            require(sum(map(len, wires)) <= 8 * MIB, "qualification_batch_bytes")
            self._reserve(16 * MIB)
            require(self._entry_count + 16 + len(rows) * 5 <= 65536, "store_limit")
            root = self.root / "qualification-batches"
            if not root.exists():
                root.mkdir(mode=0o700)
                local.sync_directory(self.root)
            require(len(list(root.iterdir())) < 64, "qualification_batch_count")
            operation = str(uuid.uuid4())
            folder = root / operation
            request = dict(
                version="1.0.0",
                operation_id=operation,
                worker_id=worker_id,
                incarnation=worker["incarnation"],
                command_sha256=publication["command_sha256"],
                cluster_id=self.state["broker"]["cluster_id"],
                topic=worker["input_topic"],
                topic_id=worker["input_topic_id"],
                records=records,
            )
            request_wire = encoded(request)
            require(len(request_wire) <= 65536, "qualification_batch_request_limit")
            folder.mkdir(mode=0o700)
            for name in ("values", "attempts", "acknowledgments", "receipts"):
                (folder / name).mkdir(mode=0o700)
            for record, wire in zip(records, wires, strict=True):
                local.write_exclusive(folder / "values" / record["value_file"], wire)
            local.sync_directory(folder / "values")
            local.write_exclusive(folder / "request.json", request_wire)
            for directory in (
                folder / "attempts",
                folder / "acknowledgments",
                folder / "receipts",
                folder,
                root,
            ):
                local.sync_directory(directory)
            batch = {
                key: request[key]
                for key in (
                    "operation_id",
                    "worker_id",
                    "incarnation",
                    "command_sha256",
                    "cluster_id",
                    "topic",
                    "topic_id",
                )
            }
            batch.update(request_sha256=sha(request_wire), count=len(records))
            self._append("qualification_batch_intent", batch)
            batch = self.state["qualification_batches"][operation]
            error = None
            result = None
            try:
                result = self._qualification_batch_helper(batch, folder)
            except (OSError, ValueError, subprocess.TimeoutExpired) as failure:
                self._retain_failure(failure)
                error = failure
            # Fencing must finish before recovery can trust a stable receipt prefix.
            self._fence_qualification_batch(operation)
            try:
                receipts, hashes = self._qualification_batch_prefix(batch)
                require(
                    error is None
                    and result
                    == dict(
                        version="1.0.0",
                        operation_id=operation,
                        request_sha256=batch["request_sha256"],
                        completed=len(records),
                        receipt_sha256=hashes,
                    )
                    and len(receipts) == len(records)
                    and type(result["completed"]) is int
                    and not any(path.name.startswith(".partial-") for path in folder.rglob("*")),
                    "qualification_batch_incomplete",
                )
            except (OSError, ValueError, KeyError, TypeError):
                self._append(
                    "qualification_batch_result",
                    dict(operation_id=operation, status="failed"),
                    recovery=True,
                )
                raise
            self._append(
                "qualification_batch_result",
                dict(operation_id=operation, status="complete"),
                recovery=True,
            )
            return receipts

    def admit(self, worker_id, rows):
        require(isinstance(rows, list) and 1 <= len(rows) <= 128, "admission_count")
        with self._locked():
            self._load()
            self._qualification_admission_allowed(worker_id)
            worker = self.state["workers"].get(worker_id)
            require(
                worker is not None
                and self.state["publications"]
                and self.state["publications"][-1]["receipt"],
                "no_published_policy",
            )
            registration: Any = next(
                (
                    r
                    for r in self.state["publications"][-1]["registrations"]
                    if r["worker_id"] == worker_id
                ),
                None,
            )
            require(
                registration is not None and registration["incarnation"] == worker["incarnation"],
                "not_current_member",
            )
            receipts = []
            for row in rows:
                wire = row if isinstance(row, bytes) else encoded(row)
                require(len(wire) <= 2 * MIB, "raw_limit")
                value = local.document(wire)
                run = (
                    value.get("run_id")
                    if value.get("kind") in ("run_end", "source_boundary")
                    else value.get("context", {}).get("run_id")
                )
                require(
                    run in registration["assigned_runs"]
                    and self.state["run_owners"].get(run) == worker_id,
                    "unassigned_run",
                )
                self._reserve(len(wire) + 131072)
                with self._temporary() as temporary:
                    receipt = self._send_bytes(
                        "input",
                        str(run),
                        wire,
                        temporary,
                        topic=dict(
                            name=worker["input_topic"], id=worker["input_topic_id"], partition=0
                        ),
                    )
                self._append(
                    "admit", dict(worker_id=worker_id, run_id=run, receipt=receipt), recovery=True
                )
                receipts.append(receipt)
            return receipts

    def outputs(self, start=0, limit=16):
        require(
            type(start) is int and start >= 0 and type(limit) is int and 1 <= limit <= 128,
            "read_limit",
        )
        with self._locked():
            self._load()
            descriptor = self._common()["topics"]["output"]
            self._reserve((limit * 4 + 2) * MIB)
            with self._temporary() as temporary:
                batch = self._network(
                    "drain",
                    "kafka:9092",
                    self.config["project"] + ".inspect",
                    self.state["broker"]["cluster_id"],
                    descriptor["name"],
                    descriptor["id"],
                    str(start),
                    str(limit),
                    self._path(temporary),
                )
                self._batch_scope(batch, descriptor)
                values = []
                for record in batch["records"]:
                    path = temporary / record["value_file"]
                    require(
                        path.parent == temporary and re.fullmatch(r"[0-9]{20}\.value", path.name),
                        "output_file",
                    )
                    path.chmod(0o600)
                    wire = private_file(path, 4 * MIB)
                    require(sha(wire) == record["value_sha256"], "output_wire")
                    value = local.document(wire)
                    schema("output", value)
                    values.append(dict(wire=record, output=value, wire_sha256=sha(wire)))
                return dict(records=values, next_offset=batch["next_offset"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "init",
            "status",
            "up",
            "worker",
            "publish",
            "start",
            "admit",
            "observe",
            "stop",
            "checkpoint",
            "checkpoints",
            "replace",
            "outputs",
        ),
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--worker")
    parser.add_argument("--authority")
    parser.add_argument("--deployment")
    parser.add_argument("--runtime-jar", type=Path)
    parser.add_argument("--producer-jar", type=Path)
    parser.add_argument("--compatibility")
    parser.add_argument("--project")
    parser.add_argument("--validator-artifact", type=Path)
    parser.add_argument("--validator-descriptor", type=Path)
    parser.add_argument("--assigned-run", action="append", default=[])
    parser.add_argument("--replacement", action="store_true")
    parser.add_argument("--candidate-store", type=Path)
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--registrations", type=Path)
    parser.add_argument("--expected-revision", type=int, default=0)
    parser.add_argument("--expected-hash")
    parser.add_argument("--restore")
    parser.add_argument("--rows", type=Path)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=16)
    args = parser.parse_args()
    try:
        if args.operation == "init":
            require(
                all(
                    (
                        args.authority,
                        args.deployment,
                        args.runtime_jar,
                        args.producer_jar,
                        args.compatibility,
                        args.validator_artifact,
                        args.validator_descriptor,
                    )
                ),
                "initialization_arguments",
            )
            runtime = Runtime.initialize(
                args.root,
                args.authority,
                args.deployment,
                args.runtime_jar,
                args.producer_jar,
                args.compatibility,
                project=args.project,
                validator_artifact=args.validator_artifact,
                validator_descriptor=local.document(local.read(args.validator_descriptor, 65536)),
            )
            result = runtime.status()
        else:
            runtime = Runtime(args.root)
            if args.operation == "status":
                result = runtime.status()
            elif args.operation == "up":
                result = runtime.up()
            elif args.operation == "worker":
                require(args.worker is not None, "worker_required")
                result = runtime.worker(args.worker, args.assigned_run, args.replacement)
            elif args.operation == "publish":
                require(
                    all(
                        (args.candidate_store, args.producer_jar, args.proposal, args.registrations)
                    ),
                    "publication_arguments",
                )
                store = local.Store(
                    args.candidate_store, runtime.config["authority_id"], args.producer_jar
                )
                result = runtime.publish(
                    store,
                    local.document(local.read(args.proposal, 65536)),
                    local.document(local.read(args.registrations, 65536)),
                    args.expected_revision,
                    args.expected_hash,
                )
            elif args.operation == "start":
                require(args.worker is not None, "worker_required")
                result = runtime.start(args.worker, args.restore)
            elif args.operation == "admit":
                require(args.worker is not None and args.rows is not None, "admission_arguments")
                result = runtime.admit(args.worker, local.document(local.read(args.rows, 16 * MIB)))
            elif args.operation == "observe":
                result = runtime.observe(args.limit)
            elif args.operation == "checkpoint":
                result = runtime.checkpoint(args.worker)
            elif args.operation == "checkpoints":
                result = runtime.checkpoints(args.worker)
            elif args.operation == "replace":
                require(
                    args.worker is not None and args.restore is not None, "replacement_arguments"
                )
                result = runtime.replace(args.worker, args.restore)
            elif args.operation == "outputs":
                result = runtime.outputs(args.start_offset, args.limit)
            else:
                result = runtime.stop(args.worker)
        print(encoded(result).decode())
        return 0
    except Exception as error:
        category = str(error)
        if not re.fullmatch(r"lifecycle_runtime_[a-z_]{1,64}", category):
            category = "lifecycle_runtime_operation_failed"
        print(json.dumps(dict(category=category)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
