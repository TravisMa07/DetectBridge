"""Isolated P09 detection deployment and synthetic semantic qualification."""

import argparse
import base64
import json
import re
import shutil
import time
import uuid
from typing import Any
from urllib.parse import urlsplit

import replay
from check_contracts import load_json
from detection_compile import compile_rules, encoded, sha
from stack import DEPLOY, ROOT, StackError, project_lock, run, save
from transport import Transport, digest, java_env

CACHE = ROOT / ".cache/detection-runtime"
BUILDS = ROOT / ".cache/detection-build"
INPUT = "detectbridge.detection.input.v1"
OUTPUT = "detectbridge.detection.results.v1"
QUARANTINE = "detectbridge.detection.quarantine.v1"
TOPICS = [INPUT, OUTPUT, QUARANTINE]
VERSION = "1.0.0"
FIXTURES = ROOT / "contracts/detection/v1/fixtures"


def build():
    run(
        [
            ROOT / "gradlew",
            ":detection-evaluator:test",
            ":detection-evaluator:shadowJar",
            ":detection-job:shadowJar",
        ],
        env=java_env(),
        timeout=600,
    )
    plan = ROOT / ".cache/detection/plan.json"
    jar = ROOT / "packages/detection-job/build/libs/detection-job.jar"
    dockerfile = DEPLOY / "detection.Dockerfile"
    logger = DEPLOY / "transport-log4j.properties"
    fingerprint = sha(
        jar.read_bytes() + plan.read_bytes() + dockerfile.read_bytes() + logger.read_bytes()
    )
    folder = BUILDS / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    for source, name in [
        (jar, "detection-job.jar"),
        (plan, "plan.json"),
        (dockerfile, "Dockerfile"),
        (logger, "log4j-console.properties"),
    ]:
        shutil.copyfile(source, folder / name)
    image = "detectbridge-detection:" + fingerprint
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
        "bundle_sha256": fingerprint,
        "jar_sha256": sha(jar.read_bytes()),
        "publisher_sha256": sha(jar.read_bytes()),
        "image": image,
        "image_id": metadata["Id"],
        "platform": "linux/" + metadata["Architecture"],
    }
    save(BUILDS / "bundle.json", bundle)
    return {"status": "built", "bundle": bundle}


class Detection(Transport):
    def __init__(self, project):
        if not re.fullmatch(r"detectbridge-p09-[a-z0-9-]+", project):
            raise StackError("dedicated_detection_project_required")
        super().__init__(project)
        self.folder = CACHE / self.project
        if self.folder.is_symlink():
            raise StackError("unsafe_detection_state")

    def bundle(self, value=None):
        return super().bundle(load_json(BUILDS / "bundle.json") if value is None else value)

    def config(self):
        value = load_json(self.folder / "configuration.json")
        if value["project"] != self.project or set(value["broker"]["topics"]) != set(TOPICS):
            raise StackError("detection_configuration_mismatch")
        if (self.folder / "configuration.sha256").read_text().strip() != digest(value):
            raise StackError("configuration_checksum_mismatch")
        self.bundle(value["bundle"])
        return value

    def verify_destination(self, config=None):
        config = self.config() if config is None else config
        info = self.broker(config=config)
        if (
            info["cluster_id"] != config["broker"]["cluster_id"]
            or info["topics"] != config["broker"]["topics"]
        ):
            raise StackError("detection_destination_changed")
        return info

    def rest(self, path, method="GET", data=None):
        for attempt in range(2):
            try:
                return super().rest(path, method, data)
            except StackError as error:
                if method != "GET" or str(error) != "docker_daemon_api_failure" or attempt:
                    raise
                time.sleep(1)

    def inject_event(self, value, key):
        config = self.config()
        self.verify_destination(config)
        row = {
            "sequence": 0,
            "key": base64.b64encode(key).decode() if key is not None else None,
            "value": base64.b64encode(value).decode() if value is not None else None,
        }
        result = self.helper_run(
            self.process_args("inject", INPUT), timeout=60, data=json.dumps(row) + "\n"
        )
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        if len(rows) != 2 or rows[0].get("type") != "ack" or rows[1].get("count") != 1:
            raise StackError("missing_detection_ack")
        return rows[0]

    def accounted(self, expected, invalid, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self.verify_destination()
            results = [
                json.loads(base64.b64decode(r["value"]))
                for r in self.read_records(OUTPUT, 0, info["end_offsets"][OUTPUT])
            ]
            errors = [
                json.loads(base64.b64decode(r["value"]))
                for r in self.read_records(QUARANTINE, 0, info["end_offsets"][QUARANTINE])
            ]
            seen = {r["input"]["offset"]: r for r in results}
            bad = {r["input"]["offset"]: r for r in errors}
            if set(seen) == set(expected) and set(bad) == set(invalid):
                for offset, (outcome, checksum) in expected.items():
                    if (
                        seen[offset]["counts"][outcome] != 1
                        or seen[offset]["input"]["value_sha256"] != checksum
                    ):
                        raise StackError("independent_expectation_failed")
                for offset, checksum in invalid.items():
                    if bad[offset]["input"]["value_sha256"] != checksum:
                        raise StackError("quarantine_reference_mismatch")
                return results
            if set(seen) - set(expected) or set(bad) - set(invalid):
                raise StackError("unexpected_detection_output")
            time.sleep(1)
        raise StackError("detection_accounting_timeout")

    def process_args(self, command, *args, config=None):
        config = self.config() if config is None else config
        return [
            "docker",
            "run",
            "--name",
            self.project + "-helper-" + uuid.uuid4().hex[:12],
            "--log-driver",
            "none",
            *(["-i"] if command in ("publish", "inject") else []),
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
            "/opt/detectbridge/detection-job.jar:/opt/flink/lib/*",
            "io.detectbridge.detection.DetectionPublisher",
            "kafka:9092",
            command,
            *map(str, args),
        ]

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
        initial = {"bundle": bundle, "consumer_group": "detectbridge-detection-v1-" + pipeline}
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
        self.folder.mkdir(parents=True, mode=0o700)
        replay.atomic_json(self.folder / "configuration.json", config)
        (self.folder / "configuration.sha256").write_text(digest(config) + "\n")
        replay.atomic_json(self.folder / "jobs.json", {"contract_version": VERSION, "jobs": []})
        return {"status": "initialized", "pipeline_id": pipeline}

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
            "/opt/detectbridge/detection-job.jar",
            "kafka:9092",
            config["consumer_group"],
            config["broker"]["cluster_id"],
            *[config["broker"]["topics"][t]["id"] for t in TOPICS],
            "/opt/detectbridge/plan.json",
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


def prepare():
    source = load_json(ROOT / "contracts/v1/examples/windows-security-4688.source.json")
    plan = compile_rules([FIXTURES / "rules/process.yml"], [source])
    path = ROOT / ".cache/detection/plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(plan) + b"\n")
    return path


def qualify():
    project = "detectbridge-p09-test-" + uuid.uuid4().hex[:12]
    test = Detection(project)
    expected: dict[int, tuple[str, str]] = {}
    invalid: dict[int, str] = {}
    report = ROOT / ".cache/detection-reports" / (project + ".json")

    report.parent.mkdir(parents=True, exist_ok=True)

    def stage(name):
        print(json.dumps({"phase": name, "project": project}), flush=True)
        save(report, {"status": "running", "phase": name, "project": project})

    def send(value, key, outcome):
        ack = test.inject_event(value, key)
        if outcome is None:
            invalid[ack["offset"]] = sha(value)
        else:
            expected[ack["offset"]] = (outcome, sha(value))
        return ack

    with project_lock(project):
        try:
            stage("initialization")
            test.init()
            job = test.start()
            stage("independent_semantics_and_replay")
            for run_id in [
                "00000000-0000-4000-8000-000000000001",
                "00000000-0000-4000-8000-000000000002",
            ]:
                for case in load_json(FIXTURES / "cases.json"):
                    event = load_json(FIXTURES / case["event"])
                    event["detectbridge"]["run_id"] = run_id
                    send(encoded(event), run_id.encode(), case["expected"])
            send(b"private-body-sentinel", b"invalid", None)
            results = test.accounted(expected, invalid)
            if len({r["run_id"] for r in results}) != 2:
                raise StackError("replay_isolation_failed")
            stage("taskmanager_recovery")
            run(["docker", "kill", project + "-taskmanager-1"])
            test.stack.compose("up", "-d", "taskmanager", profile="core")
            first = load_json(FIXTURES / "positive.event.json")
            probe = send(encoded(first), first["detectbridge"]["run_id"].encode(), "matched")
            test.wait_input_checkpoint(probe["offset"])
            test.accounted(expected, invalid)
            stage("sink_outage")
            checkpoint = test.wait_checkpoint(job["job_id"])

            def policy(value):
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
                    "min.insync.replicas=" + value,
                )

            try:
                policy("2")
                row = {
                    "sequence": 0,
                    "key": base64.b64encode(b"invalid").decode(),
                    "value": base64.b64encode(b"outage-private-body-sentinel").decode(),
                }
                response = test.helper_run(
                    test.process_args("inject", INPUT), timeout=60, data=json.dumps(row) + "\n"
                )
                offset = json.loads(response.stdout.splitlines()[0])["offset"]
                invalid[offset] = sha(b"outage-private-body-sentinel")
                checkpoint = test.wait_quarantine_retry_limit(job["job_id"])
                committed = json.loads(
                    test.private_read(
                        test.process_args("group-offset", test.config()["consumer_group"]),
                        timeout=45,
                    ).stdout
                )["offset"]
                if committed > offset:
                    raise StackError("checkpoint_crossed_failed_sink")
            finally:
                policy("1")
            stage("explicit_checkpoint_restore")
            restored = test.start(restore=checkpoint["external_path"])
            test.accounted(expected, invalid)
            test.wait_input_checkpoint(max(invalid))
            checkpoint = test.wait_checkpoint(restored["job_id"])
            stage("jobmanager_restore")
            test.stack.down()
            test.stack.up("core")
            test.start(restore=checkpoint["external_path"])
            results = test.accounted(expected, invalid)
            stage("metrics_and_logs")
            if not any("detectbridge_detection" in m for m in test.metrics().values()):
                raise StackError("missing_detection_metrics")
            for container in test.stack.containers():
                logs = run(["docker", "logs", container["Id"]])
                if "private-body-sentinel" in logs.stdout + logs.stderr:
                    raise StackError("payload_leaked_to_logs")
            result = {
                "status": "qualified",
                "project": project,
                "valid_inputs": len(expected),
                "invalid_inputs": len(invalid),
                "physical_results": len(results),
            }
            save(report, result)
            return result
        except BaseException:
            save(report, {"status": "failed", "project": project})
            raise
        finally:
            if (test.stack.folder / "state.json").exists():
                test.stack.down()
                test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-p09-dev")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "build", "verify", "init", "stop", "status", "metrics"):
        sub.add_parser(command)
    start = sub.add_parser("start")
    start.add_argument("--restore")
    start.add_argument("--from-beginning", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare()
            result = {"status": "compiled"}
        elif args.command == "build":
            prepare()
            result = build()
        elif args.command == "verify":
            result = qualify()
        else:
            with project_lock(args.project):
                test = Detection(args.project)
                result = (
                    test.start(args.restore, args.from_beginning)
                    if args.command == "start"
                    else getattr(test, args.command)()
                )
        print(json.dumps(result))
    except Exception:
        print(json.dumps({"status": "failed", "category": "detection_operation_failed"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
