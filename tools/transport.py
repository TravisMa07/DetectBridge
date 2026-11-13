"""Acknowledged replay publication and checkpointed Kafka/Flink transport."""

import argparse
import base64
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import replay
from check_contracts import load_json
from check_transport import require
from stack import DEPLOY, ROOT, Stack, StackError, project_lock, retry_daemon_control, run, save

CACHE = ROOT / ".cache/transport"
BUILDS = ROOT / ".cache/transport-build"
INPUT = "detectbridge.replay.input.v1"
OUTPUT = "detectbridge.replay.output.v1"
QUARANTINE = "detectbridge.replay.quarantine.v1"
TOPICS = [INPUT, OUTPUT, QUARANTINE]
MAX_VALUE = 1024 * 1024
VERSION = "1.0.0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(replay.encoded(value))


def java_env():
    env = dict(
        os.environ, JAVA_HOME=str(ROOT / ".cache/jdk"), GRADLE_USER_HOME=str(ROOT / ".cache/gradle")
    )
    return env


def build():
    run(
        [
            ROOT / "gradlew",
            "--console=plain",
            ":transport-contracts:test",
            ":transport-job:shadowJar",
            ":transport-publisher:shadowJar",
        ],
        env=java_env(),
        timeout=600,
    )
    run(
        ["uv", "run", "--locked", "python", ROOT / "tools/check_transport.py", "--artifacts"],
        timeout=60,
    )
    job = ROOT / "packages/transport-job/build/libs/transport-job.jar"
    publisher = ROOT / "packages/transport-publisher/build/libs/publisher.jar"
    jar_sha, publisher_sha = sha(job.read_bytes()), sha(publisher.read_bytes())
    dockerfile = (DEPLOY / "transport.Dockerfile").read_bytes()
    logger = (DEPLOY / "transport-log4j.properties").read_bytes()
    upstream = Stack().image("flink")
    if dockerfile.decode().splitlines()[0] != "FROM " + upstream:
        raise StackError("transport_base_image_mismatch")
    fingerprint = sha(jar_sha.encode() + publisher_sha.encode() + dockerfile + logger)
    folder = BUILDS / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    for path, name in [
        (job, "transport-job.jar"),
        (publisher, "publisher.jar"),
        (DEPLOY / "transport.Dockerfile", "Dockerfile"),
        (DEPLOY / "transport-log4j.properties", "log4j-console.properties"),
    ]:
        shutil.copyfile(path, folder / name)
    image = "detectbridge-transport:" + fingerprint
    run(
        [
            "docker",
            "build",
            "--label",
            "io.detectbridge.bundle_sha256=" + fingerprint,
            "--tag",
            image,
            folder,
        ],
        timeout=600,
    )
    metadata = json.loads(run(["docker", "image", "inspect", image]).stdout)[0]
    bundle = {
        "jar_sha256": jar_sha,
        "publisher_sha256": publisher_sha,
        "bundle_sha256": fingerprint,
        "image": image,
        "image_id": metadata["Id"],
        "platform": "linux/" + metadata["Architecture"],
    }
    save(BUILDS / "bundle.json", bundle)
    return {"status": "built", "bundle": bundle}


class Transport:
    def __init__(self, project="detectbridge-dev", data_cache=replay.DATA_CACHE, runs=replay.RUNS):
        self.stack = Stack(project)
        self.project = self.stack.project
        self.folder = CACHE / self.project
        self.runs, self.data_cache = runs, data_cache
        if self.folder.is_symlink():
            raise StackError("unsafe_transport_state")

    def bundle(self, value=None):
        value = load_json(BUILDS / "bundle.json") if value is None else value
        metadata = json.loads(run(["docker", "image", "inspect", value["image_id"]]).stdout)[0]
        if (
            metadata["Config"].get("Labels", {}).get("io.detectbridge.bundle_sha256")
            != value["bundle_sha256"]
            or "linux/" + metadata["Architecture"] != value["platform"]
        ):
            raise StackError("bundle_image_mismatch")
        return value

    def config(self):
        value = load_json(self.folder / "configuration.json")
        require("configuration", value)
        if value["project"] != self.project:
            raise StackError("project_configuration_mismatch")
        if (self.folder / "configuration.sha256").read_text().strip() != digest(value):
            raise StackError("configuration_checksum_mismatch")
        self.bundle(value["bundle"])
        return value

    def process_args(self, command, *args, config=None):
        config = self.config() if config is None else config
        return [
            "docker",
            "run",
            "--name",
            self.project + "-helper-" + uuid.uuid4().hex[:12],
            "--log-driver",
            "none",
            "-i",
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
            "--entrypoint",
            "java",
            config["bundle"]["image_id"],
            "-Xmx256m",
            "-cp",
            "/opt/detectbridge/publisher.jar",
            "io.detectbridge.transport.Publisher",
            "kafka:9092",
            command,
            *map(str, args),
        ]

    @retry_daemon_control
    def remove_helper(self, args):
        name = args[args.index("--name") + 1]
        if not name.startswith(self.project + "-helper-"):
            raise StackError("unexpected_helper_owner")
        ids = run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                "name=^/" + name + "$",
                "--filter",
                "label=io.detectbridge.helper.project=" + self.project,
            ]
        ).stdout.split()
        if ids:
            run(["docker", "rm", "-f", *ids])

    def helper_run(self, args, *, timeout, data=None):
        try:
            return run(args, timeout=timeout, data=data)
        finally:
            self.remove_helper(args)

    def private_read(self, args, timeout):
        for attempt in range(2):
            try:
                return self.helper_run(args, timeout=timeout)
            except StackError as exc:
                if str(exc) != "docker_daemon_api_failure" or attempt:
                    raise
                time.sleep(1)
        raise StackError("docker_daemon_api_failure")

    def broker(self, command="describe", config=None):
        config = self.config() if config is None else config
        result = (self.helper_run if command == "init" else self.private_read)(
            self.process_args(command, config["consumer_group"], config=config), timeout=90
        )
        value = json.loads(result.stdout)
        if value.get("status") == "failed":
            raise StackError("broker_operation_failed")
        return value

    def verify_destination(self, config=None):
        config = self.config() if config is None else config
        current = self.broker(config=config)
        if {"cluster_id": current["cluster_id"], "topics": current["topics"]} != config["broker"]:
            raise StackError("changed_cluster_topic_or_policy")
        return current

    def init(self):
        if (self.folder / "configuration.json").exists():
            config = self.config()
            self.verify_destination(config)
            return {"status": "initialized", "pipeline_id": config["pipeline_id"]}
        if self.folder.exists():
            raise StackError("partial_transport_initialization_requires_review")
        self.stack.init("core")
        bundle = self.bundle()
        state = self.stack.load()
        if state.get("transport_bundle") and state["transport_bundle"] != bundle:
            raise StackError("bundle_replacement_requires_review")
        # An idle stack must be explicitly recreated with the reviewed bundle.
        if self.stack.containers():
            raise StackError("stop_idle_stack_before_transport_initialization")
        overlay: dict[str, Any] = {"services": {}}
        base = load_json(DEPLOY / "compose.yml")
        for service in ("jobmanager", "taskmanager"):
            properties = (
                base["services"][service]["environment"]["FLINK_PROPERTIES"]
                + "metrics.reporters: prom\nmetrics.reporter.prom.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory\nmetrics.reporter.prom.port: 9249\n"
            )
            overlay["services"][service] = {
                "image": bundle["image_id"],
                "environment": {"FLINK_PROPERTIES": properties},
            }
        overlay_path = self.stack.folder / "transport.compose.json"
        save(overlay_path, overlay)
        state.update(
            transport_bundle=bundle, transport_overlay_sha256=sha(overlay_path.read_bytes())
        )
        save(self.stack.folder / "state.json", state)
        self.stack.up("core")
        pipeline = str(uuid.uuid4())
        initial = {"bundle": bundle, "consumer_group": "detectbridge-transport-v1-" + pipeline}
        info = self.broker("init", config=initial)
        config = {
            "contract_version": VERSION,
            "project": self.project,
            "pipeline_id": pipeline,
            "bundle": bundle,
            "broker": {"cluster_id": info["cluster_id"], "topics": info["topics"]},
            "consumer_group": initial["consumer_group"],
            "replay_contract": VERSION,
            "raw_contract": VERSION,
        }
        require("configuration", config)
        self.folder.mkdir(parents=True, mode=0o700)
        replay.atomic_json(self.folder / "configuration.json", config)
        (self.folder / "configuration.sha256").write_text(digest(config) + "\n")
        replay.atomic_json(self.folder / "jobs.json", {"contract_version": VERSION, "jobs": []})
        return {"status": "initialized", "pipeline_id": pipeline}

    def rest(self, path, method="GET", data=None):
        if not path.startswith("/") or ".." in path:
            raise StackError("unsafe_rest_path")
        result = self.stack.exec(
            "jobmanager",
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "15",
            "-X",
            method,
            "http://localhost:8081" + path,
            *(
                []
                if data is None
                else ["-H", "Content-Type: application/json", "--data", json.dumps(data)]
            ),
        )
        return {} if not result.strip() else json.loads(result)

    def jobs(self):
        value = load_json(self.folder / "jobs.json")
        require("job-history", value)
        expected_bundle = self.config()["bundle"]["bundle_sha256"]
        if any(job["bundle_sha256"] != expected_bundle for job in value["jobs"]):
            raise StackError("job_bundle_history_mismatch")
        return value

    def latest_job(self):
        jobs = self.jobs()["jobs"]
        return jobs[-1] if jobs else None

    def start(self, restore=None, from_beginning=False):
        config = self.config()
        self.verify_destination(config)
        old = self.latest_job()
        if restore is not None and from_beginning:
            raise StackError("conflicting_restore_options")
        active = self.rest("/jobs/overview").get("jobs", [])
        if any(
            item["state"] not in ("FINISHED", "FAILED", "CANCELED", "SUSPENDED") for item in active
        ):
            raise StackError("job_already_active")
        if old and restore is None and not from_beginning:
            raise StackError("explicit_restore_or_from_beginning_required")
        args = ["/opt/flink/bin/flink", "run", "-d"]
        if restore is not None:
            parsed = urlsplit(restore)
            if (
                parsed.scheme != "file"
                or parsed.netloc
                or parsed.query
                or parsed.fragment
                or not parsed.path.startswith("/")
            ):
                raise StackError("unsafe_checkpoint_uri")
            restore = "file://" + parsed.path
            import re

            match = re.fullmatch(
                r"file:///state/checkpoints/([0-9a-f]{32})/chk-[0-9]+/?(?:_metadata)?", restore
            )
            if not match or match[1] not in {j["job_id"] for j in self.jobs()["jobs"]}:
                raise StackError("unknown_checkpoint_owner")
            path = restore.removeprefix("file://").rstrip("/")
            if not path.endswith("_metadata"):
                path += "/_metadata"
            self.stack.exec("jobmanager", "test", "-s", path)
            args += ["-s", "file://" + path]
        args += [
            "/opt/detectbridge/transport-job.jar",
            "kafka:9092",
            config["consumer_group"],
            config["broker"]["cluster_id"],
            *[config["broker"]["topics"][t]["id"] for t in TOPICS],
        ]
        result = self.stack.exec("jobmanager", *args)
        import re

        match = re.search(r"JobID ([0-9a-f]{32})", result)
        if not match:
            raise StackError("missing_submitted_job_id")
        job = {
            "job_id": match[1],
            "bundle_sha256": config["bundle"]["bundle_sha256"],
            "restored_from": restore,
            "from_beginning": from_beginning,
        }
        history = self.jobs()
        history["jobs"].append(job)
        replay.atomic_json(self.folder / "jobs.json", history)
        self.wait_checkpoint(job["job_id"])
        return {"status": "running", **job}

    def wait_checkpoint(self, job_id, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.rest("/jobs/" + job_id)
            if status["state"] in ("FAILED", "CANCELED", "FINISHED"):
                raise StackError("job_terminated_before_checkpoint")
            checkpoint = self.rest("/jobs/" + job_id + "/checkpoints")
            if status["state"] == "RUNNING" and checkpoint.get("latest", {}).get("completed"):
                replay.atomic_json(
                    self.folder / "checkpoint.json",
                    {
                        "job_id": job_id,
                        "bundle_sha256": self.config()["bundle"]["bundle_sha256"],
                        "checkpoint": checkpoint["latest"]["completed"],
                    },
                )
                return checkpoint["latest"]["completed"]
            time.sleep(1)
        raise StackError("completed_checkpoint_timeout")

    def stop(self):
        self.config()
        job = self.latest_job()
        if job is None:
            raise StackError("job_not_started")
        self.rest("/jobs/" + job["job_id"] + "?mode=cancel", method="PATCH")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.rest("/jobs/" + job["job_id"])["state"] in ("CANCELED", "FAILED", "FINISHED"):
                return {"status": "stopped", "job_id": job["job_id"]}
            time.sleep(1)
        raise StackError("job_cancellation_timeout")

    def status(self):
        config = self.config()
        info = self.verify_destination(config)
        job = self.latest_job()
        overview = self.rest("/jobs/overview").get("jobs", [])
        result = {
            "pipeline_id": config["pipeline_id"],
            "broker": info,
            "job": job,
            "observed_jobs": [{"job_id": j["jid"], "state": j["state"]} for j in overview],
        }
        if job and job["job_id"] not in {j["jid"] for j in overview}:
            result["job_state"] = "ABSENT_FROM_JOBMANAGER"
        elif job:
            result["job_state"] = self.rest("/jobs/" + job["job_id"])["state"]
            result["checkpoints"] = self.rest("/jobs/" + job["job_id"] + "/checkpoints")
        return result

    def metrics(self):
        self.config()
        return {
            name: self.stack.exec(
                name,
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "10",
                "http://localhost:9249/metrics",
            )
            for name in ("jobmanager", "taskmanager")
        }

    def read_records(self, topic, start, stop):
        result = self.private_read(self.process_args("read", topic, start, stop), timeout=60)
        values = [json.loads(line) for line in result.stdout.splitlines()]
        if not values or values[-1].get("type") != "end":
            raise StackError("incomplete_kafka_read")
        return values[:-1]

    def replay_rows(self, run_id):
        for path in sorted((self.runs / run_id / "segments").glob("*/records.ndjson")):
            with path.open("rb") as stream:
                for line in stream:
                    # NDJSON delimiter is framing, not the Kafka value.
                    value = line[:-1]
                    if len(value) > MAX_VALUE:
                        raise StackError("transport_value_limit")
                    yield json.loads(value), value

    def publication_folder(self, run_id):
        if str(uuid.UUID(run_id)) != run_id:
            raise StackError("invalid_run_id")
        folder = self.folder / "publications" / run_id
        if folder.is_symlink():
            raise StackError("unsafe_publication_state")
        return folder

    def publication(self, run_id, verify=True):
        config = self.config()
        if verify:
            self.verify_destination(config)
            if (
                replay.execute(run_id, runs=self.runs, data_cache=self.data_cache, inspect=True)[
                    "status"
                ]
                != "completed"
            ):
                raise StackError("replay_not_completed")
        folder = self.publication_folder(run_id)
        publication = load_json(folder / "configuration.json")
        require("publication", publication)
        if (folder / "configuration.sha256").read_text().strip() != digest(publication):
            raise StackError("publication_configuration_changed")
        if publication["run_id"] != run_id or publication["project"] != self.project:
            raise StackError("publication_identity_mismatch")
        if (
            publication["pipeline_id"] != config["pipeline_id"]
            or publication["destination_sha256"] != digest(config["broker"])
            or publication["bundle_sha256"] != config["bundle"]["bundle_sha256"]
        ):
            raise StackError("publication_destination_changed")
        if publication["run_manifest_sha256"] != replay.digest(
            load_json(self.runs / run_id / "manifest.json")
        ):
            raise StackError("publication_run_changed")
        rows = list(self.replay_rows(run_id))
        if publication["envelope_count"] != len(rows):
            raise StackError("publication_count_mismatch")
        receipts: list[dict] = []
        for number, path in enumerate(sorted((folder / "receipts").glob("*.json"))):
            if path.name != f"{number:08d}.json":
                raise StackError("noncontiguous_ack_segments")
            segment = load_json(path)
            require("receipts", segment)
            if segment["configuration_sha256"] != digest(publication) or segment[
                "first_sequence"
            ] != len(receipts):
                raise StackError("ack_configuration_mismatch")
            for receipt in segment["receipts"]:
                sequence = len(receipts)
                if sequence >= len(rows):
                    raise StackError("ack_prefix_out_of_range")
                row, raw = rows[sequence]
                if (
                    receipt["sequence"] != sequence
                    or receipt["key_sha256"] != sha(run_id.encode())
                    or receipt["value_sha256"] != sha(raw)
                ):
                    raise StackError("ack_receipt_mismatch")
                if receipts and receipt["offset"] <= receipts[-1]["offset"]:
                    raise StackError("nonincreasing_ack_offsets")
                receipts.append(receipt)
        if verify and receipts:
            found = {
                r["offset"]: r
                for r in self.read_records(INPUT, receipts[0]["offset"], receipts[-1]["offset"] + 1)
            }
            for receipt in receipts:
                item = found.get(receipt["offset"])
                if (
                    item is None
                    or item["key"] is None
                    or item["value"] is None
                    or sha(base64.b64decode(item["key"])) != receipt["key_sha256"]
                    or sha(base64.b64decode(item["value"])) != receipt["value_sha256"]
                ):
                    raise StackError("acknowledged_input_missing_or_changed")
        return {
            "run_id": run_id,
            "acknowledged": len(receipts),
            "envelope_count": publication["envelope_count"],
            "status": "completed"
            if len(receipts) == publication["envelope_count"]
            else "interrupted",
        }

    def publish(self, run_id, rate="inherit", hook=lambda _: None):
        config = self.config()
        self.verify_destination(config)
        validation = replay.execute(
            run_id, runs=self.runs, data_cache=self.data_cache, inspect=True
        )
        if validation["status"] != "completed":
            raise StackError("replay_not_completed")
        rows = list(self.replay_rows(run_id))  # bound by P05's 512 MiB completed output cap
        manifest = load_json(self.runs / run_id / "manifest.json")
        folder = self.publication_folder(run_id)
        with replay.locked(self.folder / ".publication.lock"):
            if (folder / "configuration.json").exists():
                publication = load_json(folder / "configuration.json")
                if rate != "inherit" and rate != publication["rate"]:
                    raise StackError("publication_rate_frozen")
            else:
                selected_rate = manifest["rate"] if rate == "inherit" else rate
                if selected_rate is not None and (
                    not math.isfinite(selected_rate) or not 0 < selected_rate <= 10000
                ):
                    raise StackError("invalid_publication_rate")
                publication = {
                    "contract_version": VERSION,
                    "project": self.project,
                    "pipeline_id": config["pipeline_id"],
                    "run_id": run_id,
                    "run_manifest_sha256": replay.digest(manifest),
                    "destination_sha256": digest(config["broker"]),
                    "bundle_sha256": config["bundle"]["bundle_sha256"],
                    "rate": selected_rate,
                    "envelope_count": len(rows),
                }
                require("publication", publication)
                folder.mkdir(parents=True, mode=0o700)
                (folder / "receipts").mkdir()
                replay.atomic_json(folder / "configuration.json", publication)
                (folder / "configuration.sha256").write_text(digest(publication) + "\n")
            progress = self.publication(run_id)
            first = progress["acknowledged"]
            if first == len(rows):
                return progress
            pacer = replay.Pacer(publication["rate"])
            child = subprocess.Popen(
                self.process_args("publish", INPUT),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            batch: list[dict] = []
            segment = len(list((folder / "receipts").glob("*.json")))

            def commit():
                nonlocal segment, batch
                if batch:
                    replay.atomic_json(
                        folder / "receipts" / f"{segment:08d}.json",
                        {
                            "contract_version": VERSION,
                            "configuration_sha256": digest(publication),
                            "first_sequence": batch[0]["sequence"],
                            "receipts": batch,
                        },
                    )
                    segment += 1
                    batch = []
                    hook("after_receipt_commit")

            try:
                assert child.stdin and child.stdout
                for row, raw in rows[first:]:
                    pacer.wait()
                    child.stdin.write(
                        json.dumps(
                            {
                                "sequence": row["sequence"],
                                "key": base64.b64encode(run_id.encode()).decode(),
                                "value": base64.b64encode(raw).decode(),
                            }
                        )
                        + "\n"
                    )
                    child.stdin.flush()
                    line = child.stdout.readline(4096)
                    ack = json.loads(line)
                    if (
                        ack.get("type") != "ack"
                        or ack.get("sequence") != row["sequence"]
                        or ack.get("key_sha256") != sha(run_id.encode())
                        or ack.get("value_sha256") != sha(raw)
                    ):
                        raise StackError("invalid_broker_acknowledgment")
                    batch.append(ack)
                    hook("after_broker_ack")
                    if len(batch) == 100:
                        commit()
                child.stdin.close()
                end = json.loads(child.stdout.readline(4096))
                if (
                    end.get("type") != "end"
                    or end.get("count") != len(rows) - first
                    or child.wait(timeout=40)
                ):
                    raise StackError("publisher_incomplete")
                commit()
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=40)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)
                if child.stdin and not child.stdin.closed:
                    child.stdin.close()
                if child.stdout:
                    child.stdout.close()
                self.stack.cleanup_helpers()
            return self.publication(run_id)

    def inject(self, key, value):
        line = {
            "sequence": 0,
            "key": None if key is None else base64.b64encode(key).decode(),
            "value": None if value is None else base64.b64encode(value).decode(),
        }
        args = self.process_args("inject", INPUT)
        child = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            assert child.stdin and child.stdout
            child.stdin.write(json.dumps(line) + "\n")
            child.stdin.flush()
            ack = json.loads(child.stdout.readline(4096))
            if (
                ack.get("type") != "ack"
                or ack.get("key_sha256") != sha(b"" if key is None else key)
                or ack.get("value_sha256") != sha(b"" if value is None else value)
            ):
                raise StackError("fault_injection_ack_failed")
            child.stdin.close()
            end = json.loads(child.stdout.readline(4096))
            if end.get("type") != "end" or end.get("count") != 1 or child.wait(timeout=40):
                raise StackError("fault_injection_failed")
            return ack
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
            if child.stdin and not child.stdin.closed:
                child.stdin.close()
            if child.stdout:
                child.stdout.close()
            self.remove_helper(args)

    @retry_daemon_control
    def pause_broker(self, paused):
        values = [
            v
            for v in self.stack.containers()
            if v["Config"]["Labels"]["com.docker.compose.service"] == "kafka"
        ]
        if len(values) != 1:
            raise StackError("missing_project_broker")
        if values[0]["State"].get("Paused", False) != paused:
            run(["docker", "pause" if paused else "unpause", values[0]["Id"]])
        observed = json.loads(run(["docker", "inspect", values[0]["Id"]]).stdout)[0]
        if observed["State"].get("Paused", False) != paused:
            raise StackError("broker_pause_state_mismatch")

    def wait_input_checkpoint(self, offset, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self.broker()
            if info["committed_input_offset"] > offset:
                return
            time.sleep(1)
        raise StackError("input_checkpoint_progress_timeout")

    def wait_quarantine_retry_limit(self, job_id, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.rest("/jobs/" + job_id)["state"]
            if state == "FAILED":
                # Examine known fault signatures in memory; never print exception text.
                detail = json.dumps(self.rest("/jobs/" + job_id + "/exceptions"))
                if not any(
                    signature in detail
                    for signature in ("topic_config_mismatch", "NotEnoughReplicas")
                ):
                    raise StackError("unrelated_failure_during_quarantine_fault")
                return
            if state in ("CANCELED", "FINISHED"):
                raise StackError("unexpected_termination_during_quarantine_fault")
            time.sleep(1)
        raise StackError("bounded_quarantine_retries_not_exhausted")

    def await_accounted(self, expected, quarantine, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self.broker()
            outputs = self.read_records(OUTPUT, 0, info["end_offsets"][OUTPUT])
            seen: dict[tuple[str, int], int] = {}
            for record in outputs:
                if record["key"] is None or record["value"] is None:
                    raise StackError("unexpected_output_tombstone")
                value = base64.b64decode(record["value"])
                body = json.loads(value)
                identity = (body["run_id"], body["sequence"])
                if identity not in expected or expected[identity] != (
                    base64.b64decode(record["key"]),
                    value,
                ):
                    raise StackError("output_bytes_or_identity_mismatch")
                seen[identity] = seen.get(identity, 0) + 1
            rejected = self.read_records(QUARANTINE, 0, info["end_offsets"][QUARANTINE])
            found: dict[int, int] = {}
            for record in rejected:
                value = json.loads(base64.b64decode(record["value"]))
                require("quarantine", value)
                location = value["input"]
                offset = location["offset"]
                if offset not in quarantine:
                    raise StackError("unexpected_quarantine_location")
                original = quarantine[offset]
                raw = b"" if original is None else original
                expected_id = replay.identity_hash(
                    [info["cluster_id"], info["topics"][INPUT]["id"], "0", str(offset)]
                )
                if (
                    location["cluster_id"] != info["cluster_id"]
                    or location["topic_id"] != info["topics"][INPUT]["id"]
                    or value["value_sha256"] != sha(raw)
                    or value["value_size"] != len(raw)
                    or value["value_is_null"] != (original is None)
                    or value["quarantine_id"] != expected_id
                    or base64.b64decode(record["key"]).decode() != expected_id
                ):
                    raise StackError("quarantine_reference_mismatch")
                retained = self.read_records(INPUT, offset, offset + 1)
                if len(retained) != 1 or (
                    retained[0]["value"] is not None
                    if original is None
                    else retained[0]["value"] is None
                    or base64.b64decode(retained[0]["value"]) != raw
                ):
                    raise StackError("quarantine_input_unavailable")
                found[offset] = found.get(offset, 0) + 1
            if set(seen) == set(expected) and set(found) == set(quarantine):
                return {
                    "unique_output": len(seen),
                    "output_records": len(outputs),
                    "duplicates": len(outputs) - len(seen),
                    "unique_quarantine": len(found),
                    "quarantine_records": len(rejected),
                    "quarantine_duplicates": len(rejected) - len(found),
                }
            time.sleep(1)
        raise StackError("transport_accounting_timeout")

    def verify(self, recorded=False):
        self.bundle()
        from check_datasets import load_catalog
        from transport_fixtures import catalog as synthetic_catalog

        project = "detectbridge-test-" + uuid.uuid4().hex
        temporary = tempfile.TemporaryDirectory(prefix="detectbridge-transport-")
        temp = Path(temporary.name)
        data_cache = replay.DATA_CACHE if recorded else temp / "data"
        selections = load_catalog() if recorded else synthetic_catalog(data_cache)
        test = Transport(project, data_cache=data_cache, runs=temp / "runs")
        reports = ROOT / ".cache/transport-reports"
        reports.mkdir(parents=True, exist_ok=True)

        def stage(name):
            replay.atomic_json(
                reports / (project + ".json"),
                {"project": project, "phase": name, "status": "running"},
            )
            print(json.dumps({"project": project, "phase": name}), file=sys.stderr, flush=True)
            return name

        phase = stage("initialization")
        report = {}
        with project_lock(project):
            try:
                test.init()
                submitted = test.start()
                expected = {}
                runs = []
                for _ in range(2):
                    result = replay.start(
                        list(selections),
                        catalog=selections,
                        runs=test.runs,
                        captures=temp / "captures",
                        data_cache=data_cache,
                        rate=None,
                    )
                    runs.append(result["run_id"])
                    for row, raw in test.replay_rows(result["run_id"]):
                        expected[(row["run_id"], row["sequence"])] = (row["run_id"].encode(), raw)
                phase = stage("ambiguous_publication")

                class SimulatedCrash(BaseException):
                    pass

                def crash(point):
                    if point == "after_broker_ack":
                        raise SimulatedCrash()

                try:
                    test.publish(runs[0], hook=crash)
                except SimulatedCrash:
                    pass
                test.publish(runs[0])
                before = test.broker()["end_offsets"][INPUT]
                test.publish(runs[0])
                if test.broker()["end_offsets"][INPUT] != before:
                    raise StackError("completed_publication_resent")
                phase = stage("broker_outage")
                paused = [False]
                pause_lock = threading.Lock()
                timers: list[threading.Timer] = []

                def unpause():
                    with pause_lock:
                        if paused[0]:
                            test.pause_broker(False)
                            paused[0] = False

                def outage(point):
                    if point == "after_broker_ack" and not timers:
                        test.pause_broker(True)
                        paused[0] = True
                        timer = threading.Timer(3, unpause)
                        timers.append(timer)
                        timer.start()

                try:
                    test.publish(runs[1], hook=outage)
                finally:
                    unpause()
                    for timer in timers:
                        timer.join(timeout=10)
                phase = stage("invalid_input")
                malformed = b'{"private-body-sentinel":'
                rejected: dict[int, bytes | None] = {
                    test.inject(b"invalid-key", malformed)["offset"]: malformed
                }
                rejected[test.inject(b"invalid-key", None)["offset"]] = None
                rejected[test.inject(b"invalid-key", b'{"contract_version":"9.0.0"}')["offset"]] = (
                    b'{"contract_version":"9.0.0"}'
                )
                baseline = test.await_accounted(expected, rejected)
                phase = stage("taskmanager_recovery")
                run(["docker", "kill", project + "-taskmanager-1"])
                test.stack.compose("up", "-d", "taskmanager", profile="core")
                first_key, first_value = next(iter(expected.values()))
                probe = test.inject(first_key, first_value)
                test.wait_input_checkpoint(probe["offset"])
                test.await_accounted(expected, rejected)
                phase = stage("quarantine_backpressure")
                recovery_checkpoint = test.wait_checkpoint(submitted["job_id"])
                try:
                    test.stack.exec(
                        "kafka",
                        "/opt/kafka/bin/kafka-configs.sh",
                        "--bootstrap-server",
                        "kafka:9092",
                        "--alter",
                        "--entity-type",
                        "topics",
                        "--entity-name",
                        QUARANTINE,
                        "--add-config",
                        "min.insync.replicas=2",
                    )
                    invalid = b"not-json-private-body-sentinel"
                    invalid_offset = test.inject(b"invalid-key", invalid)["offset"]
                    rejected[invalid_offset] = invalid
                    time.sleep(12)
                    committed = json.loads(
                        test.private_read(
                            test.process_args("group-offset", test.config()["consumer_group"]),
                            timeout=45,
                        ).stdout
                    )["offset"]
                    if committed > invalid_offset:
                        raise StackError("checkpoint_advanced_past_unavailable_quarantine")
                    # Keep the declared fault active until the finite retry policy stops
                    # the job. Both retained backlog and explicit recovery are qualified.
                    test.wait_quarantine_retry_limit(submitted["job_id"])
                    phase = stage("quarantine_retry_exhausted")
                finally:
                    test.stack.exec(
                        "kafka",
                        "/opt/kafka/bin/kafka-configs.sh",
                        "--bootstrap-server",
                        "kafka:9092",
                        "--alter",
                        "--entity-type",
                        "topics",
                        "--entity-name",
                        QUARANTINE,
                        "--add-config",
                        "min.insync.replicas=1",
                    )
                phase = stage("quarantine_checkpoint_restore")
                submitted = test.start(restore=recovery_checkpoint["external_path"])
                test.await_accounted(expected, rejected)
                phase = stage("jobmanager_restore")
                checkpoint = test.wait_checkpoint(submitted["job_id"])
                path = checkpoint["external_path"]
                if path.startswith("file:/") and not path.startswith("file:///"):
                    path = "file:///" + path[len("file:/") :]
                test.stack.down()
                test.stack.up("core")
                test.start(restore=path)
                accounting = test.await_accounted(expected, rejected)
                phase = stage("metrics_and_logs")
                metrics = test.metrics()
                if not any("detectbridge_transport" in value for value in metrics.values()):
                    raise StackError("missing_transport_metrics")
                for value in test.stack.containers():
                    logs = run(["docker", "logs", value["Id"]]).stdout
                    if "private-body-sentinel" in logs:
                        raise StackError("payload_leaked_to_logs")
                report = {
                    "status": "qualified",
                    "recorded": recorded,
                    "project": project,
                    "runs": runs,
                    "bundle": test.config()["bundle"],
                    "accounting": accounting,
                    "initial_accounting": baseline,
                    "environment": test.stack.doctor("core"),
                    "taskmanager_recovery": True,
                    "jobmanager_explicit_restore": True,
                    "broker_outage": True,
                    "quarantine_backpressure": True,
                    "quarantine_recovery": "explicit_checkpoint_after_bounded_retries",
                }
            except Exception as exc:
                category = str(exc) if isinstance(exc, StackError) else type(exc).__name__
                raise StackError("qualification_" + phase + "_" + category) from exc
            finally:
                pending_error = sys.exc_info()[1]
                old = {
                    sig: signal.signal(sig, signal.SIG_IGN)
                    for sig in (signal.SIGINT, signal.SIGTERM)
                }
                try:
                    test.stack.cleanup_helpers()
                    if (test.stack.folder / "state.json").exists():
                        test.stack.reset(project)
                    if test.folder.exists():
                        shutil.rmtree(test.folder)
                except Exception as cleanup_error:
                    pending = (
                        str(pending_error)
                        if isinstance(pending_error, StackError)
                        else "interrupted_or_unknown"
                    )
                    raise StackError("cleanup_failed_after_" + pending) from cleanup_error
                finally:
                    temporary.cleanup()
                    for sig, handler in old.items():
                        signal.signal(sig, handler)
        if test.stack.containers() or test.folder.exists() or test.stack.folder.exists():
            raise StackError("qualification_cleanup_incomplete")
        replay.atomic_json(reports / (project + ".json"), report)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-dev")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "init", "stop", "status", "metrics"):
        sub.add_parser(name)
    start = sub.add_parser("start")
    mode = start.add_mutually_exclusive_group()
    mode.add_argument("--restore")
    mode.add_argument("--from-beginning", action="store_true")
    publish = sub.add_parser("publish")
    publish.add_argument("run_id")
    speed = publish.add_mutually_exclusive_group()
    speed.add_argument("--rate", type=float)
    speed.add_argument("--unpaced", action="store_true")
    sub.add_parser("publication").add_argument("run_id")
    sub.add_parser("verify").add_argument("--recorded", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        transport = Transport(args.project)
        with project_lock(args.project):
            if args.command == "build":
                result = build()
            elif args.command == "start":
                result = transport.start(args.restore, args.from_beginning)
            elif args.command == "publish":
                result = transport.publish(
                    args.run_id,
                    None if args.unpaced else args.rate if args.rate is not None else "inherit",
                )
            elif args.command == "publication":
                result = transport.publication(args.run_id)
            elif args.command == "verify":
                result = transport.verify(args.recorded)
            else:
                result = getattr(transport, args.command)()
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "category": "transport_interrupted"}))
        return 130
    except StackError as exc:
        print(json.dumps({"status": "failed", "category": str(exc)}))
        return 1
    except Exception:
        print(json.dumps({"status": "failed", "category": "transport_validation_or_io_failure"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
