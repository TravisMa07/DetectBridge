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
from check_contracts import StrictValidator, load_json
from detection_compile import compile_rules, encoded, sha
from jsonschema import FormatChecker
from stack import DEPLOY, ROOT, Stack, StackError, project_lock, run, save
from transport import Transport, digest, java_env

CACHE = ROOT / ".cache/detection-runtime"
BUILDS = ROOT / ".cache/detection-build"
INPUT = "detectbridge.detection.input.v1"
OUTPUT = "detectbridge.detection.results.v1"
QUARANTINE = "detectbridge.detection.quarantine.v1"
TOPICS = [INPUT, OUTPUT, QUARANTINE]
VERSION = "1.0.0"
FIXTURES = ROOT / "contracts/detection/v1/fixtures"


def failure_category(error):
    """Emit fixed operational categories only; never exception text or input values."""
    if isinstance(error, StackError):
        category = str(error)
        known = {
            "command_timeout",
            "command_failed",
            "docker_unavailable",
            "docker_daemon_api_failure",
            "docker_setup_failure",
            "job_terminated_before_checkpoint",
            "completed_checkpoint_timeout",
            "missing_submitted_job_id",
            "job_already_active",
            "unknown_checkpoint_owner",
            "unsafe_checkpoint_uri",
            "detection_accounting_timeout",
            "independent_expectation_failed",
            "quarantine_reference_mismatch",
            "detection_input_reference_mismatch",
            "detection_output_schema_invalid",
            "detection_output_key_mismatch",
            "mapped_version_attribution_mismatch",
            "unstable_duplicate_result",
            "result_identity_collision",
            "unexpected_detection_output",
            "qualified_bundle_changed",
            "missing_detection_metrics",
            "payload_leaked_to_logs",
            "replay_isolation_failed",
            "input_checkpoint_progress_timeout",
            "job_cancellation_timeout",
            "incompatible_restore_not_rejected",
            "unrelated_incompatible_restore_failure",
            "checkpoint_crossed_failed_sink",
        }
        if category in known:
            return category
        command = re.fullmatch(
            r"command_failed(?:_(?:job_submission|checkpoint_metadata|internal_http|topic_configuration))?_exit_([0-9]{1,3})",
            category,
        )
        if command and 1 <= int(command[1]) <= 255:
            return category
    if isinstance(error, KeyError):
        return "unexpected_document_shape"
    if isinstance(error, json.JSONDecodeError):
        return "invalid_json"
    if isinstance(error, OSError):
        return "io_error"
    return "detection_operation_failed"


def build(mapped=False):
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
    plan = ROOT / (".cache/detection/mapped-plan.json" if mapped else ".cache/detection/plan.json")
    builds = ROOT / ".cache/detection-v2-build" if mapped else BUILDS
    jar = ROOT / "packages/detection-job/build/libs/detection-job.jar"
    dockerfile = DEPLOY / "detection.Dockerfile"
    logger = DEPLOY / "transport-log4j.properties"
    if dockerfile.read_text().splitlines()[0] != "FROM " + Stack().image("flink"):
        raise StackError("detection_base_image_mismatch")
    fingerprint = sha(
        jar.read_bytes() + plan.read_bytes() + dockerfile.read_bytes() + logger.read_bytes()
    )
    folder = builds / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    for source, name in [
        (jar, "detection-job.jar"),
        (plan, "plan.json"),
        (dockerfile, "Dockerfile"),
        (logger, "log4j-console.properties"),
    ]:
        shutil.copyfile(source, folder / name)
    image = ("detectbridge-detection-v2:" if mapped else "detectbridge-detection:") + fingerprint
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
    save(builds / "bundle.json", bundle)
    return {"status": "built", "bundle": bundle}


class Detection(Transport):
    def __init__(self, project, *, mapped=False):
        self.mapped = mapped
        suffix = "v2" if mapped else "v1"
        self.input = "detectbridge.detection.input." + suffix
        self.output = "detectbridge.detection.results." + suffix
        self.quarantine = "detectbridge.detection.quarantine." + suffix
        self.topics = [self.input, self.output, self.quarantine]
        self.builds = ROOT / ".cache/detection-v2-build" if mapped else BUILDS
        self.cache = ROOT / ".cache/detection-v2-runtime" if mapped else CACHE
        prefix = "detectbridge-p10-" if mapped else "detectbridge-p09-"
        if not re.fullmatch(re.escape(prefix) + r"[a-z0-9-]+", project):
            raise StackError("dedicated_detection_project_required")
        super().__init__(project)
        self.folder = self.cache / self.project
        if self.folder.is_symlink():
            raise StackError("unsafe_detection_state")

    def bundle(self, value=None):
        return super().bundle(load_json(self.builds / "bundle.json") if value is None else value)

    def config(self):
        value = load_json(self.folder / "configuration.json")
        if value["project"] != self.project or set(value["broker"]["topics"]) != set(self.topics):
            raise StackError("detection_configuration_mismatch")
        if self.mapped and value.get("runtime") != "mapped/2.0.0":
            raise StackError("detection_runtime_mismatch")
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
            self.process_args("inject", self.input), timeout=60, data=json.dumps(row) + "\n"
        )
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        if len(rows) != 2 or rows[0].get("type") != "ack" or rows[1].get("count") != 1:
            raise StackError("missing_detection_ack")
        return rows[0]

    def qualification_plan(self):
        config = self.config()
        folder = self.builds / config["bundle"]["bundle_sha256"]
        material = b"".join(
            (folder / name).read_bytes()
            for name in ("detection-job.jar", "plan.json", "Dockerfile", "log4j-console.properties")
        )
        if sha(material) != config["bundle"]["bundle_sha256"]:
            raise StackError("qualified_bundle_changed")
        return load_json(folder / "plan.json")

    def accounted(self, expected, invalid, timeout=180):
        plan = self.qualification_plan()
        result_schema = (
            ROOT / "contracts/detection" / ("v2" if self.mapped else "v1") / "result.schema.json"
        )
        result_validator = StrictValidator(load_json(result_schema), format_checker=FormatChecker())
        error_validator = StrictValidator(
            load_json(ROOT / "contracts/detection/v1/quarantine.schema.json"),
            format_checker=FormatChecker(),
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = self.verify_destination()
            result_rows = self.read_records(self.output, 0, info["end_offsets"][self.output])
            error_rows = self.read_records(self.quarantine, 0, info["end_offsets"][self.quarantine])
            results: list[dict] = []
            errors: list[dict] = []
            for rows, validator, target, identity_field in (
                (result_rows, result_validator, results, "result_id"),
                (error_rows, error_validator, errors, "quarantine_id"),
            ):
                for wire in rows:
                    row = json.loads(base64.b64decode(wire["value"]))
                    if next(validator.iter_errors(row), None):
                        raise StackError("detection_output_schema_invalid")
                    if (
                        wire["key"] is None
                        or base64.b64decode(wire["key"]) != row[identity_field].encode()
                    ):
                        raise StackError("detection_output_key_mismatch")
                    target.append(row)
            for row in results + errors:
                location = row["input"]
                if (
                    location["cluster_id"] != info["cluster_id"]
                    or location["topic"] != self.input
                    or location["topic_id"] != info["topics"][self.input]["id"]
                ):
                    raise StackError("detection_input_reference_mismatch")
            stable: dict[tuple[str, str, str], dict] = {}
            identities: dict[str, tuple[str, str, str]] = {}
            for result in results:
                if result["bundle_sha256"] != plan["bundle_sha256"] or (
                    self.mapped
                    and result["mapping_sha256"] != sha(encoded(plan["mapping_profiles"]))
                ):
                    raise StackError("mapped_version_attribution_mismatch")
                key = (result["event_id"], result["run_id"], result["bundle_sha256"])
                semantic = {name: value for name, value in result.items() if name != "input"}
                if key in stable and stable[key] != semantic:
                    raise StackError("unstable_duplicate_result")
                if result["result_id"] in identities and identities[result["result_id"]] != key:
                    raise StackError("result_identity_collision")
                stable[key] = semantic
                identities[result["result_id"]] = key
            seen = {r["input"]["offset"]: r for r in results}
            bad = {r["input"]["offset"]: r for r in errors}
            if set(seen) == set(expected) and set(bad) == set(invalid):
                for offset, expectation in expected.items():
                    result = seen[offset]
                    outcome = expectation["outcome"]
                    expected_counts = {
                        name: int(name == outcome)
                        for name in (
                            "matched",
                            "unmatched",
                            "inapplicable",
                            "configuration_blocked",
                            "quality_skipped",
                            "evaluation_error",
                        )
                    }
                    rule = {
                        "id": "70000000-0000-4000-8000-000000000001",
                        "revision": sha((FIXTURES / "rules/process.yml").read_bytes()),
                    }
                    expected_matches = [rule] if outcome == "matched" else []
                    expected_diagnostics = (
                        [{"rule_id": rule["id"], "category": outcome, "pointer": ""}]
                        if outcome
                        in ("configuration_blocked", "quality_skipped", "evaluation_error")
                        else []
                    )
                    identity = "sha256:" + sha(
                        encoded(
                            [expectation["event_id"], expectation["run_id"], plan["bundle_sha256"]]
                        )
                    )
                    if (
                        result["counts"] != expected_counts
                        or result["matched"] != expected_matches
                        or result["diagnostics"] != expected_diagnostics
                        or result["event_id"] != expectation["event_id"]
                        or result["run_id"] != expectation["run_id"]
                        or result["result_id"] != identity
                        or result["input"]["partition"] != 0
                        or result["input"]["value_sha256"] != expectation["value_sha256"]
                    ):
                        raise StackError("independent_expectation_failed")
                for offset, expectation in invalid.items():
                    error = bad[offset]
                    identity = "sha256:" + sha(
                        encoded(
                            [info["cluster_id"], info["topics"][self.input]["id"], "0", str(offset)]
                        )
                    )
                    if (
                        error["input"]["value_sha256"] != expectation["value_sha256"]
                        or error["input"]["partition"] != 0
                        or error["quarantine_id"] != identity
                        or error["value_size"] != expectation["value_size"]
                        or error["value_is_null"] != expectation["value_is_null"]
                        or error["category"] != "invalid_normalized_input"
                    ):
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
            "io.detectbridge.detection.DetectionV2Publisher"
            if self.mapped
            else "io.detectbridge.detection.DetectionPublisher",
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
            raise StackError("partial_detection_initialization_requires_review")
        self.stack.init("core")
        bundle = self.bundle()
        state = self.stack.load()
        if state.get("transport_bundle") and state["transport_bundle"] != bundle:
            raise StackError("bundle_replacement_requires_review")
        # An idle stack must be explicitly recreated with the reviewed bundle.
        if self.stack.containers():
            raise StackError("stop_idle_stack_before_detection_initialization")
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
        initial = {
            "bundle": bundle,
            "consumer_group": (
                "detectbridge-detection-v2-" if self.mapped else "detectbridge-detection-v1-"
            )
            + pipeline,
        }
        info = self.broker("init", config=initial)
        config = {
            "contract_version": VERSION,
            "project": self.project,
            "pipeline_id": pipeline,
            "bundle": bundle,
            "broker": {"cluster_id": info["cluster_id"], "topics": info["topics"]},
            "consumer_group": initial["consumer_group"],
            "normalized_contract": VERSION,
        }
        if self.mapped:
            config["runtime"] = "mapped/2.0.0"
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
        if self.mapped:
            args += ["-c", "io.detectbridge.detection.DetectionV2Job"]
        args += [
            "/opt/detectbridge/detection-job.jar",
            "kafka:9092",
            config["consumer_group"],
            config["broker"]["cluster_id"],
            *[config["broker"]["topics"][t]["id"] for t in self.topics],
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


def mapped_runtime_cases():
    cases = []
    for profile, outcome in (
        ("linux-audit-execution", "configuration_blocked"),
        ("openssh-authentication", "inapplicable"),
    ):
        cases.append(
            (load_json(ROOT / "contracts/v1/examples" / (profile + ".event.json")), outcome)
        )
    skipped = load_json(FIXTURES / "positive.event.json")
    skipped["detectbridge"]["quality"]["eligibility"] = "undetermined"
    cases.append((skipped, "quality_skipped"))
    unknown = load_json(FIXTURES / "positive.event.json")
    unknown["detectbridge"]["source_contract"]["id"] = "unknown-source"
    cases.append((unknown, "configuration_blocked"))
    exhausted = load_json(FIXTURES / "positive.event.json")
    exhausted["process"]["command_line"] = "x" * 150000
    cases.append((exhausted, "evaluation_error"))
    for index, (event, _) in enumerate(cases, start=3):
        event["detectbridge"]["run_id"] = "00000000-0000-4000-8000-" + str(index).zfill(12)
    return cases


def qualify_incompatible_restore(test, checkpoint):
    """Test-only actual restore under a changed group; never rewrite valid configuration."""
    config = test.config()
    test.stop()
    command = [
        "/opt/flink/bin/flink",
        "run",
        "-d",
        "-s",
        checkpoint["external_path"],
        "-c",
        "io.detectbridge.detection.DetectionV2Job",
        "/opt/detectbridge/detection-job.jar",
        "kafka:9092",
        config["consumer_group"] + "-incompatible",
        config["broker"]["cluster_id"],
        *[config["broker"]["topics"][t]["id"] for t in test.topics],
        "/opt/detectbridge/plan.json",
    ]
    response = test.stack.exec("jobmanager", *command)
    match = re.search(r"JobID ([0-9a-f]{32})", response)
    if not match:
        raise StackError("missing_incompatible_restore_job")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if test.rest("/jobs/" + match[1])["state"] == "FAILED":
            detail = json.dumps(test.rest("/jobs/" + match[1] + "/exceptions"))
            if "incompatible_detection_restore" not in detail:
                raise StackError("unrelated_incompatible_restore_failure")
            return
        time.sleep(1)
    raise StackError("incompatible_restore_not_rejected")


def qualify(mapped=False):
    project = ("detectbridge-p10-test-" if mapped else "detectbridge-p09-test-") + uuid.uuid4().hex[
        :12
    ]
    test = Detection(project, mapped=mapped)
    expected: dict[int, dict] = {}
    invalid: dict[int, dict] = {}
    report = (
        ROOT
        / (".cache/detection-v2-reports" if mapped else ".cache/detection-reports")
        / (project + ".json")
    )

    report.parent.mkdir(parents=True, exist_ok=True)
    phase = "setup"

    def stage(name):
        nonlocal phase
        phase = name
        print(json.dumps({"phase": name, "project": project}), flush=True)
        save(report, {"status": "running", "phase": name, "project": project})

    def send(value, key, outcome):
        ack = test.inject_event(value, key)
        if outcome is None:
            invalid[ack["offset"]] = {
                "value_sha256": sha(value),
                "value_size": len(value),
                "value_is_null": False,
            }
        else:
            event = json.loads(value)
            expected[ack["offset"]] = {
                "outcome": outcome,
                "value_sha256": sha(value),
                "event_id": event["event"]["id"],
                "run_id": event["detectbridge"]["run_id"],
            }
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
            if mapped:
                for event, outcome in mapped_runtime_cases():
                    send(encoded(event), event["detectbridge"]["run_id"].encode(), outcome)
            send(b"private-body-sentinel", b"invalid", None)
            results = test.accounted(expected, invalid)
            if len({r["run_id"] for r in results}) != (7 if mapped else 2):
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
                # Idempotent test-only mutation, executed outside the broker's memory budget.
                for attempt in range(2):
                    try:
                        test.helper_run(test.process_args("quarantine-isr", value), timeout=60)
                        return
                    except StackError as error:
                        if (
                            str(error) not in ("docker_daemon_api_failure", "docker_setup_failure")
                            or attempt
                        ):
                            raise

            try:
                policy("2")
                row = {
                    "sequence": 0,
                    "key": base64.b64encode(b"invalid").decode(),
                    "value": base64.b64encode(b"outage-private-body-sentinel").decode(),
                }
                response = test.helper_run(
                    test.process_args("inject", test.input), timeout=60, data=json.dumps(row) + "\n"
                )
                offset = json.loads(response.stdout.splitlines()[0])["offset"]
                invalid[offset] = {
                    "value_sha256": sha(b"outage-private-body-sentinel"),
                    "value_size": len(b"outage-private-body-sentinel"),
                    "value_is_null": False,
                }
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
            if mapped:
                stage("incompatible_restore")
                qualify_incompatible_restore(test, checkpoint)
                resumed = test.start(restore=checkpoint["external_path"])
                test.accounted(expected, invalid)
                checkpoint = test.wait_checkpoint(resumed["job_id"])
            stage("jobmanager_shutdown")
            test.stack.down()
            stage("jobmanager_startup")
            test.stack.up("core")
            stage("jobmanager_restore_submission")
            test.start(restore=checkpoint["external_path"])
            stage("jobmanager_result_accounting")
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
                "bundle": test.config()["bundle"],
            }
            save(report, result)
            return result
        except BaseException as error:
            failure = {
                "status": "failed",
                "project": project,
                "phase": phase,
                "category": failure_category(error),
            }
            save(report, failure)
            print(json.dumps(failure), flush=True)
            raise
        finally:
            if (test.stack.folder / "state.json").exists():
                test.stack.down()
                test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mapped", action="store_true", help="P10 v2 runtime; separate projects/topics/state"
    )
    parser.add_argument("--project")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "build", "verify", "init", "stop", "status", "metrics"):
        sub.add_parser(command)
    start = sub.add_parser("start")
    start.add_argument("--restore")
    start.add_argument("--from-beginning", action="store_true")
    args = parser.parse_args()
    args.project = args.project or (
        "detectbridge-p10-dev" if args.mapped else "detectbridge-p09-dev"
    )
    try:
        if args.command in ("prepare", "build"):
            if args.mapped:
                from check_mapping import prepare_mapped

                prepare_mapped()
            else:
                prepare()
        if args.command == "prepare":
            result = {"status": "compiled"}
        elif args.command == "build":
            result = build(args.mapped)
        elif args.command == "verify":
            result = qualify(args.mapped)
        else:
            with project_lock(args.project):
                test = Detection(args.project, mapped=args.mapped)
                result = (
                    test.start(args.restore, args.from_beginning)
                    if args.command == "start"
                    else getattr(test, args.command)()
                )
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({"status": "failed", "category": failure_category(error)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
