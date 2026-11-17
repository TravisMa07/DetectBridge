"""Exclusive P12b Kafka/Flink lifecycle and independent failure qualification."""

import argparse
import base64
import copy
import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from check_contracts import load_json
from detection import Detection
from jsonschema import Draft202012Validator, FormatChecker
from linux_assembly_cases import (
    ROOT,
    digest,
    encoded,
)
from stack import DEPLOY, StackError, project_lock, run, save
from transport import Transport, java_env

CACHE = ROOT / ".cache/linux-assembly-runtime"
BUILDS = ROOT / ".cache/linux-assembly-build"
INPUT = "detectbridge.assembly.input.v1"
ROUTES = {
    "event": "detectbridge.assembly.results.v1",
    "manifest": "detectbridge.assembly.manifests.v1",
    "diagnostic": "detectbridge.assembly.diagnostics.v1",
    "quarantine": "detectbridge.assembly.quarantine.v1",
    "receipt": "detectbridge.assembly.receipts.v1",
}
TOPICS = [INPUT, *ROUTES.values()]


def build():
    run(
        [
            ROOT / "gradlew",
            ":linux-adapters:test",
            ":linux-assembly-job:test",
            ":linux-assembly-job:shadowJar",
        ],
        env=java_env(),
        timeout=600,
    )
    jar = ROOT / "packages/linux-assembly-job/build/libs/linux-assembly-job.jar"
    dockerfile, logger = DEPLOY / "assembly.Dockerfile", DEPLOY / "transport-log4j.properties"
    from stack import Stack

    if dockerfile.read_text().splitlines()[0] != "FROM " + Stack().image("flink"):
        raise StackError("assembly_base_image_mismatch")
    fingerprint = hashlib.sha256(
        jar.read_bytes() + dockerfile.read_bytes() + logger.read_bytes()
    ).hexdigest()
    directory = BUILDS / fingerprint
    directory.mkdir(parents=True, exist_ok=True)
    for source, name in (
        (jar, "linux-assembly-job.jar"),
        (dockerfile, "Dockerfile"),
        (logger, "log4j-console.properties"),
    ):
        shutil.copyfile(source, directory / name)
    image = "detectbridge-linux-assembly:" + fingerprint
    run(
        [
            "docker",
            "build",
            "--label",
            "io.detectbridge.bundle_sha256=" + fingerprint,
            "--tag",
            image,
            directory,
        ],
        timeout=600,
    )
    metadata = json.loads(run(["docker", "image", "inspect", image]).stdout)[0]
    sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    bundle = dict(
        bundle_sha256=fingerprint,
        jar_sha256=sha,
        publisher_sha256=sha,
        image=image,
        image_id=metadata["Id"],
        platform="linux/" + metadata["Architecture"],
    )
    save(BUILDS / "bundle.json", bundle)
    return dict(status="built", bundle=bundle)


class Assembly(Detection):
    def __init__(self, project):
        if not re.fullmatch(r"detectbridge-p12-[a-z0-9-]+", project):
            raise StackError("dedicated_assembly_project_required")
        self.mapped, self.cache, self.builds = False, CACHE, BUILDS
        self.input, self.output, self.quarantine, self.topics = (
            INPUT,
            ROUTES["event"],
            ROUTES["quarantine"],
            TOPICS,
        )
        Transport.__init__(self, project)
        self.folder = CACHE / project
        if self.folder.is_symlink():
            raise StackError("unsafe_assembly_state")

    def config(self):
        value = load_json(self.folder / "configuration.json")
        Draft202012Validator(
            load_json(ROOT / "contracts/linux-assembly/v1/assembly-runtime.schema.json"),
            format_checker=FormatChecker(),
        ).validate(value)
        if (
            value.get("runtime") != "linux-assembly/1.0.0"
            or value["project"] != self.project
            or set(value["broker"]["topics"]) != set(TOPICS)
        ):
            raise StackError("assembly_configuration_mismatch")
        if (self.folder / "configuration.sha256").read_text().strip() != digest(value):
            raise StackError("configuration_checksum_mismatch")
        self.bundle(value["bundle"])
        return value

    def process_args(self, command, *args, config=None):
        replacements = {
            "/opt/detectbridge/detection-job.jar:/opt/flink/lib/*": "/opt/detectbridge/linux-assembly-job.jar:/opt/flink/lib/*",
            "io.detectbridge.detection.DetectionPublisher": "io.detectbridge.assembly.AssemblyPublisher",
        }
        return [
            replacements.get(str(value), value)
            for value in super().process_args(command, *args, config=config)
        ]

    def init(self, profile="default", objects=None):
        existing = (self.folder / "configuration.json").exists()
        result = super().init()
        if not existing:
            value = load_json(self.folder / "configuration.json")
            entries: list[dict[str, Any]] = []
            target = self.folder / "objects"
            target.mkdir(mode=0o755)
            target.chmod(0o755)
            if objects is not None:
                total = 0
                for original in Path(objects).resolve().iterdir():
                    if (
                        len(entries) >= 128
                        or original.is_symlink()
                        or not original.is_file()
                        or not re.fullmatch("[a-f0-9]{64}", original.name)
                    ):
                        raise StackError("assembly_invalid_object_registration")
                    with original.open("rb") as file:
                        data = file.read(32 * 1024 * 1024 + 1)
                    total += len(data)
                    if (
                        not data
                        or len(data) > 32 * 1024 * 1024
                        or total > 64 * 1024 * 1024
                        or hashlib.sha256(data).hexdigest() != original.name
                    ):
                        raise StackError("assembly_invalid_object_registration")
                    destination = target / original.name
                    destination.write_bytes(data)
                    destination.chmod(0o444)
                    entries.append(dict(sha256=original.name, size_bytes=len(data)))
            registration = dict(
                version="1.0.0", objects=sorted(entries, key=lambda entry: entry["sha256"])
            )
            manifest = self.folder / "object-registration.json"
            save(manifest, registration)
            manifest.chmod(0o444)
            overlay_path = self.stack.folder / "transport.compose.json"
            overlay = load_json(overlay_path)
            state = self.stack.load()
            for service in ("jobmanager", "taskmanager"):
                overlay["services"][service]["volumes"] = [
                    dict(
                        type="bind",
                        source=str(target.resolve()),
                        target="/opt/detectbridge/objects",
                        read_only=True,
                    ),
                    dict(
                        type="bind",
                        source=str(manifest.resolve()),
                        target="/opt/detectbridge/object-registration.json",
                        read_only=True,
                    ),
                ]
            save(overlay_path, overlay)
            state["transport_overlay_sha256"] = hashlib.sha256(
                overlay_path.read_bytes()
            ).hexdigest()
            save(self.stack.folder / "state.json", state)
            value["evidence_registry_sha256"] = digest(registration)
            self.stack.up("core")
            value.update(
                runtime="linux-assembly/1.0.0",
                limits_profile=profile,
                consumer_group="detectbridge-assembly-v1-" + value["pipeline_id"],
            )
            save(self.folder / "configuration.json", value)
            (self.folder / "configuration.sha256").write_text(digest(value) + "\n")
        elif self.config()["limits_profile"] != profile:
            raise StackError("immutable_assembly_profile")
        return result

    def start(self, restore=None, from_beginning=False):
        config = self.config()
        self.verify_destination(config)
        if from_beginning:
            raise StackError("assembly_replay_requires_explicit_new_run")
        if restore and from_beginning:
            raise StackError("conflicting_restore_options")
        if any(
            j["state"] not in ("FINISHED", "FAILED", "CANCELED", "SUSPENDED")
            for j in self.rest("/jobs/overview").get("jobs", [])
        ):
            raise StackError("job_already_active")
        if self.latest_job() and not restore and not from_beginning:
            raise StackError("explicit_restore_or_from_beginning_required")
        command = ["/opt/flink/bin/flink", "run", "-d"]
        if restore:
            match = re.fullmatch(
                r"file:/+(state/checkpoints/([0-9a-f]{32})/chk-[0-9]+)(?:/_metadata)?/?", restore
            )
            parsed = urlsplit(restore)
            if (
                not match
                or parsed.netloc
                or parsed.query
                or parsed.fragment
                or match[2] not in {j["job_id"] for j in self.jobs()["jobs"]}
            ):
                raise StackError("unsafe_checkpoint_uri")
            path = "/" + match[1] + "/_metadata"
            self.stack.exec("jobmanager", "test", "-s", path)
            command += ["-s", "file://" + path]
        command += [
            "-c",
            "io.detectbridge.assembly.AssemblyJob",
            "/opt/detectbridge/linux-assembly-job.jar",
            "kafka:9092",
            config["consumer_group"],
            config["broker"]["cluster_id"],
            *[config["broker"]["topics"][t]["id"] for t in TOPICS],
            config["bundle"]["jar_sha256"],
            config["limits_profile"],
            config["evidence_registry_sha256"],
        ]
        response = self.stack.exec("jobmanager", *command)
        match = re.search(r"JobID ([0-9a-f]{32})", response)
        if not match:
            raise StackError("missing_submitted_job_id")
        job = dict(
            job_id=match[1],
            bundle_sha256=config["bundle"]["bundle_sha256"],
            restored_from=restore,
            from_beginning=from_beginning,
        )
        history = self.jobs()
        history["jobs"].append(job)
        save(self.folder / "jobs.json", history)
        self.wait_checkpoint(job["job_id"])
        return job

    def inject_rows(self, values):
        config = self.config()
        self.verify_destination(config)
        ipc = "".join(
            json.dumps(
                dict(
                    sequence=i,
                    key=None,
                    value=base64.b64encode(value).decode() if value is not None else None,
                )
            )
            + "\n"
            for i, value in enumerate(values)
        )
        result = self.helper_run(self.process_args("inject", INPUT), timeout=120, data=ipc)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        acks = [row for row in rows if row.get("type") == "ack"]
        if len(acks) != len(values) or rows[-1].get("count") != len(values):
            raise StackError("assembly_missing_ack")
        return acks

    def outputs(self):
        info = self.broker()
        result = []
        for kind, topic in ROUTES.items():
            end = info["end_offsets"][topic]
            if not end:
                continue
            read = self.private_read(self.process_args("read", topic, "0", str(end)), timeout=90)
            for line in read.stdout.splitlines():
                wire = json.loads(line)
                if "value" in wire:
                    result.append((kind, wire, json.loads(base64.b64decode(wire["value"]))))
        return result

    def fault(self, kind, value):
        self.helper_run(
            self.process_args("sink-policy", ROUTES[kind], "1" if value == "2" else "2097152"),
            timeout=90,
        )


def runtime_binding(config):
    profiles = []
    for family in ("linux-audit-execution-p12a", "openssh-authentication-p12a"):
        for kind in ("source", "mapping"):
            profiles.append(
                load_json(
                    ROOT / "packages/linux-adapters/contracts" / (family + "." + kind + ".json")
                )
            )
    limits = dict(
        members=256,
        groupBytes=1048576,
        openGroups=1024,
        pendingBytes=33554432,
        ageMillis=30000,
        runs=16,
        closedKeys=100000,
        closedBytes=33554432,
    )
    if config["limits_profile"] == "limits":
        limits.update(
            members=2,
            groupBytes=512,
            openGroups=2,
            pendingBytes=32768,
            runs=2,
            closedKeys=4,
            closedBytes=65536,
        )
    if config["limits_profile"] == "bytes":
        limits["pendingBytes"] = 12000
    return digest(
        dict(
            version="1.0.0",
            artifact=config["bundle"]["jar_sha256"],
            group=config["consumer_group"],
            cluster=config["broker"]["cluster_id"],
            topics={t: config["broker"]["topics"][t]["id"] for t in TOPICS},
            limits=limits,
            queue_bytes=8388608,
            queue_count=64,
            evidence_registry=config["evidence_registry_sha256"],
            profiles=profiles,
        )
    )


def wait_outputs(test, oracle, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        outputs = test.outputs()
        if oracle.check(outputs):
            return outputs
        state = test.rest("/jobs/" + test.latest_job()["job_id"])["state"]
        if state in ("FAILED", "CANCELED", "FINISHED"):
            raise StackError("assembly_job_terminated")
        time.sleep(1)
    raise StackError("assembly_accounting_timeout")


def checkpoint_inventory(test, checkpoint):
    match = re.fullmatch(
        r"file:/+state/checkpoints/([0-9a-f]{32})/chk-[0-9]+/?(?:_metadata)?",
        checkpoint["external_path"],
    )
    if not match:
        raise StackError("unsafe_checkpoint_uri")
    job = match[1]
    completed = test.rest("/jobs/" + job + "/checkpoints").get("history", [])
    if not any(c["id"] == checkpoint["id"] and c["status"] == "COMPLETED" for c in completed):
        raise StackError("unconfirmed_assembly_checkpoint")
    data = test.stack.exec(
        "jobmanager", "cat", f"/state/assembly-evidence/{job}/checkpoint-{checkpoint['id']}.json"
    )
    inventory = json.loads(data)
    if inventory["checkpoint_id"] != checkpoint["id"] or inventory["binding"] != runtime_binding(
        test.config()
    ):
        raise StackError("assembly_inventory_mismatch")
    return inventory


def reject_incompatible(test, checkpoint):
    config = test.config()
    test.stop()
    command = [
        "/opt/flink/bin/flink",
        "run",
        "-d",
        "-s",
        checkpoint["external_path"],
        "-c",
        "io.detectbridge.assembly.AssemblyJob",
        "/opt/detectbridge/linux-assembly-job.jar",
        "kafka:9092",
        config["consumer_group"] + "-incompatible",
        config["broker"]["cluster_id"],
        *[config["broker"]["topics"][t]["id"] for t in TOPICS],
        config["bundle"]["jar_sha256"],
        config["limits_profile"],
        config["evidence_registry_sha256"],
    ]
    before = {j["jid"] for j in test.rest("/jobs/overview").get("jobs", [])}
    try:
        response = test.stack.exec("jobmanager", *command)
    except StackError as error:
        if str(error) != "command_failed_job_submission_exit_1":
            raise
        response = ""
    match = re.search(r"JobID ([a-f0-9]{32})", response)
    created = {j["jid"] for j in test.rest("/jobs/overview").get("jobs", [])} - before
    if len(created) != 1 or (match and match[1] not in created):
        raise StackError("assembly_ambiguous_incompatible_job")
    job = created.pop()
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        state = test.rest("/jobs/" + job)["state"]
        if state == "FAILED":
            detail = json.dumps(test.rest("/jobs/" + job + "/exceptions"))
            if "incompatible_assembly_restore" not in detail:
                raise StackError("assembly_unrelated_restore_failure")
            return
        if state in ("FINISHED", "CANCELED", "SUSPENDED"):
            raise StackError("assembly_restore_not_rejected")
        time.sleep(1)
    raise StackError("assembly_restore_not_rejected")


def _qualify_default():
    from linux_assembly_cases import PARTS, RUN, audit, cases, context, record
    from linux_assembly_verify import Oracle, require

    project = "detectbridge-p12-test-" + uuid.uuid4().hex[:12]
    test = Assembly(project)
    reports = ROOT / ".cache/linux-assembly-reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = reports / (project + ".json")
    phase = "setup"

    def stage(name):
        nonlocal phase
        phase = name
        print(json.dumps(dict(phase=name, project=project)), flush=True)
        save(report, dict(status="running", phase=phase, project=project))

    with project_lock(project):
        try:
            stage("initialization")
            from linux_assembly_cases import references

            object_sha, object_bytes, reference_rows = references()
            objects = ROOT / ".cache/linux-assembly-fixtures/objects"
            objects.mkdir(parents=True, exist_ok=True)
            (objects / object_sha).write_bytes(object_bytes)
            test.init(objects=objects)
            job = test.start()
            config = test.config()
            oracle = Oracle(config, runtime_binding(config))
            source = cases()
            original = source["complete"]

            def retain(rows):
                values = [
                    row if isinstance(row, bytes) or row is None else encoded(row) for row in rows
                ]
                with (test.folder / "independent-inputs.ndjson").open("ab") as original:
                    for value in values:
                        original.write(
                            encoded(
                                dict(
                                    value_is_null=value is None,
                                    value_base64=base64.b64encode(value).decode()
                                    if value is not None
                                    else "",
                                )
                            )
                            + b"\n"
                        )
                save(
                    test.folder / "independent-expectations.json",
                    dict(
                        groups=list(oracle.groups.values()),
                        events=[
                            dict(run=key[0], id=key[1], expected=value)
                            for key, value in oracle.events.items()
                        ],
                        diagnostics=list(oracle.diagnostics.values()),
                    ),
                )
                return values

            def send(rows):
                values = retain(rows)
                acks = test.inject_rows(values)
                oracle.register(rows, acks)
                return acks

            def control(kind, **kwargs):
                return dict(
                    version="1.0.0",
                    kind=kind,
                    control_id=str(uuid.uuid4()),
                    provenance=["synthetic:independent-p12b-control"],
                    **kwargs,
                )

            stage("partial_group_checkpoint_and_taskmanager_recovery")
            timed = oracle.group(original[:5], "timeout")
            acks = send([*original[:5], original[0]])
            test.wait_input_checkpoint(acks[-1]["offset"])
            cp = test.wait_checkpoint(job["job_id"])
            inventory = checkpoint_inventory(test, cp)
            require(
                any(
                    sorted(m["record_id"] for m in group["members"])
                    == sorted(r["raw"]["record_id"] for r in original[:5])
                    for group in inventory["groups"]
                )
            )
            run(["docker", "kill", project + "-taskmanager-1"])
            test.stack.compose("up", "-d", "taskmanager", profile="core")
            wait_outputs(test, oracle)
            stage("immutable_late_evidence_and_interleaved_scopes")
            oracle.diagnostic(original[5], "late_evidence", timed)
            send([original[5]])
            groups = []
            for index, kwargs in enumerate(
                (
                    dict(run="00000000-0000-4000-8000-000000000002"),
                    dict(host="host-b"),
                    dict(generation="boot-b"),
                )
            ):
                rows = [
                    record(audit(part, str(8 + index)), 10 + index * 10 + i, context(**kwargs))
                    for i, part in enumerate(PARTS)
                ]
                oracle.group(rows)
                groups.append(rows)
            send([rows[i] for i in range(6) for rows in groups])
            wait_outputs(test, oracle)
            replayed = copy.deepcopy(original[:5])
            for row in replayed:
                row["context"]["run_id"] = "00000000-0000-4000-8000-000000000005"
            oracle.group(replayed)
            send(
                [
                    *replayed,
                    control(
                        "source_boundary",
                        run_id=replayed[0]["context"]["run_id"],
                        source=replayed[0]["context"]["source"],
                        host_id="host-a",
                        generation="boot-a",
                    ),
                ]
            )
            for row in reference_rows:
                oracle.auth(row)
            send(reference_rows)
            wait_outputs(test, oracle)
            stage("boundary_run_end_and_source_quality")
            boundary = record(audit(PARTS[0], "11"), 100)
            oracle.group([boundary], "source_boundary", ["cwd_missing"])
            send(
                [
                    boundary,
                    control(
                        "source_boundary",
                        run_id=RUN,
                        source=boundary["context"]["source"],
                        host_id="host-a",
                        generation="boot-a",
                    ),
                ]
            )
            wait_outputs(test, oracle)
            end_a = [record(audit(part, "12"), 110 + i) for i, part in enumerate(PARTS[:2])]
            end_b = [record(audit(PARTS[0], "13"), 120, context(host="host-b"))]
            oracle.group(end_a, "dataset_end", ["cwd_missing"])
            oracle.group(end_b, "dataset_end", ["cwd_missing"])
            after = record(audit(PARTS[0], "14"), 130)
            oracle.diagnostic(after, "after_dataset_end")
            send([*end_a, *end_b, control("run_end", run_id=RUN), after])
            run3 = "00000000-0000-4000-8000-000000000003"
            auth = record(source["auth"]["raw"]["evidence"]["inline"], 200, context(True, run=run3))
            oracle.auth(auth)
            unsupported = record(
                auth["raw"]["evidence"]["inline"].replace("password", "publickey"),
                201,
                context(True, run=run3),
            )
            oracle.diagnostic(unsupported, "unsupported_source")
            missing_context = context(run=run3)
            missing_context.pop("host_binding")
            missing = record(audit(PARTS[0], "20"), 202, missing_context)
            oracle.diagnostic(missing, "identity_missing")
            send([auth, unsupported, missing, b"private-body-sentinel", None])
            wait_outputs(test, oracle)
            stage("checkpoint_restore_binding_and_jobmanager_recovery")
            cp = test.wait_checkpoint(job["job_id"])
            reject_incompatible(test, cp)
            job = test.start(restore=cp["external_path"])
            wait_outputs(test, oracle)
            cp = test.retained_checkpoint(job["job_id"])
            test.stack.down()
            test.stack.up("core")
            job = test.start(restore=cp["external_path"])
            wait_outputs(test, oracle)
            late_restored = record(audit("EOE", "7"), 203)
            oracle.diagnostic(late_restored, "late_evidence", timed)
            send([late_restored])
            wait_outputs(test, oracle)
            stage("broker_unavailability_and_retained_deadline")
            paused_row = record(audit(PARTS[0], "60"), 700, context(run=run3))
            paused_group = oracle.group([paused_row], "timeout", ["cwd_missing"])
            paused_ack = send([paused_row])
            test.wait_input_checkpoint(paused_ack[-1]["offset"])
            before_pause = test.wait_checkpoint(job["job_id"])
            paused_inventory = checkpoint_inventory(test, before_pause)
            require(
                any(
                    g["members"][0]["record_id"] == paused_row["raw"]["record_id"]
                    for g in paused_inventory["groups"]
                )
            )
            test.pause_broker(True)
            try:
                # Exceed the original admission deadline while Kafka is actually unavailable.
                time.sleep(40)
                latest = test.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"]["completed"]
                # A racing pre-pause checkpoint may complete, but cannot retire the timed closure.
                during_pause = checkpoint_inventory(test, latest)
                require(
                    any(
                        g["members"][0]["record_id"] == paused_row["raw"]["record_id"]
                        for g in during_pause["groups"]
                    )
                    or any(
                        i["kind"] == "manifest" and i["key"] == paused_group["manifest_id"]
                        for i in during_pause["outbox"]
                    )
                )
            finally:
                test.pause_broker(False)
            if test.rest("/jobs/" + job["job_id"])["state"] not in (
                "FAILED",
                "CANCELED",
                "FINISHED",
            ):
                test.stop()
            job = test.start(restore=latest["external_path"])
            wait_outputs(test, oracle)
            broker_evidence = dict(
                checkpoint=latest["id"], paused_seconds=40, original_deadline_preserved=True
            )
            stage("required_output_sink_failures")
            fault_evidence = []
            for number, kind in enumerate(ROUTES):
                if kind == "manifest":
                    row = record(audit("EOE", str(30 + number)), 300 + number, context(run=run3))
                    oracle.group([row], "source_boundary", ["syscall_missing"])
                elif kind == "diagnostic":
                    row = record(
                        auth["raw"]["evidence"]["inline"].replace("password", "publickey"),
                        300 + number,
                        context(True, run=run3),
                    )
                    oracle.diagnostic(row, "unsupported_source")
                elif kind == "quarantine":
                    row = b"private-body-sentinel"
                else:
                    row = record(
                        auth["raw"]["evidence"]["inline"], 300 + number, context(True, run=run3)
                    )
                    oracle.auth(row)
                test.wait_checkpoint(job["job_id"])
                # Hold only the selected required sink; a completed staging checkpoint must retain its blocked intent.
                # Injection is first acknowledged by Kafka; original values remain in the dedicated input.
                config = test.config()
                value = retain([row])[0]
                test.fault(kind, "2")
                try:
                    ipc = (
                        json.dumps(
                            dict(sequence=0, key=None, value=base64.b64encode(value).decode())
                        )
                        + "\n"
                    )
                    response = test.helper_run(
                        test.process_args("inject", INPUT), timeout=90, data=ipc
                    )
                    ack = [
                        json.loads(line)
                        for line in response.stdout.splitlines()
                        if '"type":"ack"' in line or '"type": "ack"' in line
                    ]
                    require(len(ack) == 1)
                    oracle.register([row], ack)
                    wait_failure(test, job, "RecordTooLarge", timeout=180)
                    cp = test.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"]["completed"]
                    evidence = checkpoint_inventory(test, cp)
                    require(any(intent["kind"] == kind for intent in evidence["outbox"]))
                    # The latest completed checkpoint durably retains the blocked output; retirement never completed.
                    fault_evidence.append(
                        dict(
                            kind=kind,
                            checkpoint=cp["id"],
                            blocked_intents=sum(i["kind"] == kind for i in evidence["outbox"]),
                        )
                    )
                finally:
                    test.fault(kind, "1")
                job = test.start(restore=cp["external_path"])
                wait_outputs(test, oracle)
            stage("metrics_and_payload_log_isolation")
            require(any("detectbridge_assembly" in value for value in test.metrics().values()))
            for container in test.stack.containers():
                logs = run(["docker", "logs", container["Id"]])
                require("private-body-sentinel" not in logs.stdout + logs.stderr)
            outputs = wait_outputs(test, oracle)
            result = dict(
                status="qualified",
                project=project,
                inputs=len(oracle.inputs),
                logical_groups=len(oracle.groups),
                physical_outputs=len(outputs),
                logical_outputs=len(
                    {(kind, wire["key"], encoded(doc)) for kind, wire, doc in outputs}
                ),
                physical_duplicates=len(outputs)
                - len({(kind, wire["key"], encoded(doc)) for kind, wire, doc in outputs}),
                sink_failures=fault_evidence,
                broker_unavailability=broker_evidence,
                bundle=config["bundle"],
                baseline_main_run=43750911904,
            )
            save(report, result)
            return result
        except BaseException as error:
            import traceback

            diagnostic = dict(
                status="failed",
                phase=phase,
                project=project,
                error_type=type(error).__name__,
                locations=[
                    Path(frame.filename).name + ":" + str(frame.lineno)
                    for frame in traceback.extract_tb(error.__traceback__)[-4:]
                ],
            )
            if isinstance(error, StackError) and re.fullmatch(r"[A-Za-z0-9_]+", str(error)):
                diagnostic["category"] = str(error)
            try:
                current = test.latest_job()
                if current:
                    detail = json.dumps(test.rest("/jobs/" + current["job_id"] + "/exceptions"))
                    diagnostic["exception_sha256"] = hashlib.sha256(detail.encode()).hexdigest()
                    diagnostic["known_markers"] = [
                        marker
                        for marker in (
                            "incompatible_assembly_restore",
                            "NotEnoughReplicas",
                            "RecordTooLarge",
                            "OutOfMemoryError",
                            "ClassNotFoundException",
                            "NoSuchMethodError",
                            "assembly_schema_invalid",
                        )
                        if marker in detail
                    ]
            except Exception:
                pass
            save(report, diagnostic)
            print(json.dumps(diagnostic), flush=True)
            raise
        finally:
            if (test.stack.folder / "state.json").exists():
                try:
                    test.stack.down()
                finally:
                    test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")


def wait_failure(test, job, marker, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = test.rest("/jobs/" + job["job_id"])["state"]
        if state == "FAILED":
            detail = json.dumps(test.rest("/jobs/" + job["job_id"] + "/exceptions"))
            if marker not in detail:
                raise StackError("assembly_unrelated_pressure_failure")
            return
        if state in ("FINISHED", "CANCELED", "SUSPENDED"):
            raise StackError("assembly_pressure_not_rejected")
        time.sleep(1)
    raise StackError("assembly_pressure_not_rejected")


def qualify_pressure(profile):
    from linux_assembly_cases import PARTS, RUN, audit, context, record
    from linux_assembly_verify import Oracle, manifest, require

    project = "detectbridge-p12-" + profile + "-" + uuid.uuid4().hex[:12]
    test = Assembly(project)
    print(json.dumps(dict(phase="resource_profile", profile=profile, project=project)), flush=True)
    with project_lock(project):
        try:
            test.init(profile)
            job = test.start()
            oracle = Oracle(test.config(), runtime_binding(test.config()))

            def send(rows):
                with (test.folder / "independent-inputs.ndjson").open("ab") as original:
                    for row in rows:
                        original.write(
                            encoded(
                                dict(
                                    value_is_null=False,
                                    value_base64=base64.b64encode(encoded(row)).decode(),
                                )
                            )
                            + b"\n"
                        )
                save(
                    test.folder / "independent-expectations.json",
                    dict(
                        groups=list(oracle.groups.values()),
                        diagnostics=list(oracle.diagnostics.values()),
                    ),
                )
                acks = test.inject_rows([encoded(row) for row in rows])
                oracle.register(rows, acks)
                return acks

            end = dict(
                version="1.0.0",
                kind="run_end",
                control_id=str(uuid.uuid4()),
                run_id=RUN,
                provenance=["synthetic:p12b-pressure"],
            )
            if profile == "limits":
                bounded = [
                    record(audit(part, "100"), i) for i, part in enumerate([*PARTS[:3], "EOE"])
                ]
                closed = oracle.group(
                    bounded[:2], "resource_limit", ["cwd_missing", "resource_limit"]
                )
                for row in bounded[2:]:
                    oracle.diagnostic(row, "late_evidence", closed)
                rows = [record(audit(PARTS[0], str(101 + i)), 10 + i) for i in range(3)]
                rows.sort(
                    key=lambda row: digest(
                        manifest([row], "resource_limit", ["cwd_missing", "resource_limit"])["key"]
                    )
                )
                oracle.group(rows[:1], "resource_limit", ["cwd_missing", "resource_limit"])
                for row in rows[1:]:
                    oracle.group([row], "dataset_end", ["cwd_missing"])
                send([*bounded, *rows, end])
                wait_outputs(test, oracle)
                rejected = record(
                    audit("EOE", "999"), 200, context(run="00000000-0000-4000-8000-000000000099")
                )
                ack = send([rejected])[0]
                wait_failure(test, job, "closed_limit_backlog")
                info = test.broker()
                require(info["committed_input_offset"] <= ack["offset"])
                private = test.private_read(
                    test.process_args("read", INPUT, str(ack["offset"]), str(ack["offset"] + 1)),
                    timeout=90,
                )
                retained = [
                    json.loads(line) for line in private.stdout.splitlines() if '"value"' in line
                ]
                require(
                    len(retained) == 1
                    and hashlib.sha256(base64.b64decode(retained[0]["value"])).hexdigest()
                    == ack["value_sha256"]
                )
                require(oracle.check(test.outputs(), complete=False))
                result = dict(
                    profile=profile,
                    status="qualified",
                    closed_budget_rejection=True,
                    retained_source_offset=ack["offset"],
                    groups=4,
                )
            else:
                rows = [record(audit(PARTS[0], str(500 + i)), i) for i in range(2)]
                rows.sort(
                    key=lambda row: digest(
                        manifest([row], "resource_limit", ["cwd_missing", "resource_limit"])["key"]
                    )
                )
                oracle.group(rows[:1], "resource_limit", ["cwd_missing", "resource_limit"])
                oracle.group(rows[1:], "dataset_end", ["cwd_missing"])
                send([*rows, end])
                wait_outputs(test, oracle)
                result = dict(
                    profile=profile, status="qualified", serialized_pending_pressure=True, groups=2
                )
            save(ROOT / ".cache/linux-assembly-reports" / (project + ".json"), result)
            return result
        finally:
            if (test.stack.folder / "state.json").exists():
                try:
                    test.stack.down()
                finally:
                    test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")


def qualify():
    result = _qualify_default()
    result["pressure_profiles"] = [qualify_pressure(profile) for profile in ("limits", "bytes")]
    save(ROOT / ".cache/linux-assembly-reports/qualification.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-p12-dev")
    parser.add_argument(
        "command", choices=["build", "verify", "init", "start", "stop", "status", "metrics"]
    )
    parser.add_argument("--objects", type=Path)
    parser.add_argument("--restore")
    parser.add_argument("--from-beginning", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build()
        elif args.command == "verify":
            result = qualify()
        else:
            with project_lock(args.project):
                test = Assembly(args.project)
                if args.command == "init":
                    result = test.init(objects=args.objects)
                else:
                    result = (
                        test.start(args.restore, args.from_beginning)
                        if args.command == "start"
                        else getattr(test, args.command)()
                    )
        print(json.dumps(result))
    except Exception as error:
        from detection import failure_category

        category = failure_category(error)
        # No arbitrary exception text or raw evidence in console diagnostics.
        print(
            json.dumps(
                dict(
                    status="failed",
                    category=category
                    if category != "detection_operation_failed"
                    else "assembly_operation_failed",
                )
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
