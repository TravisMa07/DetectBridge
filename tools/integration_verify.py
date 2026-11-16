"""Actual isolated Kafka/Flink P13b source/evaluation, sink-fault and restore qualification."""

import base64
import copy
import hashlib
import json
import time
import traceback
import uuid
from pathlib import Path

from check_contracts import load_json
from integration import (
    INPUT,
    ROUTES,
    Integration,
    checkpoint_inventory,
    reject_incompatible,
    runtime_binding,
)
from integration_cases import ROOT, encoded, windows
from integration_oracle import Oracle
from linux_assembly import wait_failure
from linux_assembly_cases import PARTS, audit, context, record, references
from linux_assembly_verify import require
from stack import project_lock, run, save


def wait_outputs(test, oracle, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        output = test.outputs()
        if oracle.check(output):
            return output
        if test.rest("/jobs/" + test.latest_job()["job_id"])["state"] in (
            "FAILED",
            "CANCELED",
            "FINISHED",
        ):
            raise RuntimeError("integration_job_terminated")
        time.sleep(1)
    raise RuntimeError("integration_accounting_timeout")


def verify():
    project = "detectbridge-p13-test-" + uuid.uuid4().hex[:12]
    test = Integration(project)
    reports = ROOT / ".cache/integration-reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = reports / (project + ".json")
    phase = "setup"

    def stage(name):
        nonlocal phase
        phase = name
        save(report, dict(status="running", phase=phase, project=project))
        print(json.dumps(dict(phase=phase, project=project)), flush=True)

    with project_lock(project):
        try:
            stage("initialize")
            object_sha, object_bytes, reference_rows = references()
            objects = ROOT / ".cache/integration-fixtures/objects"
            objects.mkdir(parents=True, exist_ok=True)
            (objects / object_sha).write_bytes(object_bytes)
            test.init(objects=objects)
            job = test.start()
            config = test.config()
            oracle = Oracle(config, runtime_binding(config), test.qualification_plan())
            fixtures = load_json(ROOT / ".cache/integration/cases.json")

            def retain(rows):
                values = [
                    row if isinstance(row, bytes) or row is None else encoded(row) for row in rows
                ]
                with (test.folder / "independent-inputs.ndjson").open("ab") as file:
                    for value in values:
                        file.write(
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
                        events=[
                            dict(run=k[0], event_id=k[1], **v) for k, v in oracle.events.items()
                        ],
                        manifests=list(oracle.native.groups.values()),
                        preservation=list(oracle.native.diagnostics.values()),
                        literal_counts=oracle.expected,
                    ),
                )
                return values

            def send(rows):
                values = retain(rows)
                acks = test.inject_rows(values)
                oracle.register(rows, acks)
                return acks

            stage("audit_partial_checkpoint_taskmanager_restart")
            original = fixtures["complete"]
            timed = oracle.group(original[:5], "timeout")
            ack = send([*original[:5], original[0]])
            test.wait_input_checkpoint(ack[-1]["offset"])
            checkpoint = test.wait_checkpoint(job["job_id"])
            inventory = checkpoint_inventory(test, checkpoint)
            require(
                any(
                    sorted(m["record_id"] for m in g["members"])
                    == sorted(r["raw"]["record_id"] for r in original[:5])
                    for g in inventory["groups"]
                )
            )
            run(["docker", "kill", project + "-taskmanager-1"])
            test.stack.compose("up", "-d", "taskmanager", profile="core")
            wait_outputs(test, oracle)
            oracle.preservation(original[5], "late_evidence", timed)
            send([original[5]])
            stage("actual_windows_authentication_and_six_outcomes")
            rows = []
            for scenario in ("windows", "sysmon", "windows_skipped", "windows_budget", "auth"):
                row = fixtures[scenario]
                oracle.event(row, "windows" if scenario == "sysmon" else scenario)
                rows.append(row)
            send(rows)
            run2 = "00000000-0000-4000-8000-000000000013"
            replay = copy.deepcopy(original)
            for row in replay:
                row["context"]["run_id"] = run2
            replay_manifest = oracle.group(replay[:5])
            replay_rows = []
            for scenario in ("windows", "sysmon", "windows_skipped", "windows_budget", "auth"):
                row = copy.deepcopy(fixtures[scenario])
                row["context"]["run_id"] = run2
                oracle.event(row, "windows" if scenario == "sysmon" else scenario)
                replay_rows.append(row)
            boundary = dict(
                version="1.0.0",
                kind="source_boundary",
                control_id=str(uuid.uuid4()),
                provenance=["synthetic replay membership boundary"],
                run_id=run2,
                source=replay[0]["context"]["source"],
                host_id="host-a",
                generation="boot-a",
            )
            oracle.preservation(replay[5], "late_evidence", replay_manifest)
            send([*replay[:5], boundary, replay[5], *replay_rows])
            # Registered LF/range evidence traverses the actual resolver and assembler.
            for row in reference_rows:
                oracle.event(row, "auth")
            send(reference_rows)
            unsupported = record(
                fixtures["auth"]["raw"]["evidence"]["inline"].replace("password", "publickey"),
                901,
                context(True),
            )
            oracle.preservation(unsupported, "unsupported_source")
            unsupported_replay = copy.deepcopy(unsupported)
            unsupported_replay["context"]["run_id"] = run2
            oracle.preservation(unsupported_replay, "unsupported_source")
            send([unsupported, unsupported_replay, b"private-body-sentinel", None])
            wait_outputs(test, oracle)
            stage("explicit_restore_incompatible_binding_jobmanager_restart")
            checkpoint = test.wait_checkpoint(job["job_id"])
            reject_incompatible(test, checkpoint)
            job = test.start(restore=checkpoint["external_path"])
            wait_outputs(test, oracle)
            checkpoint = test.wait_checkpoint(job["job_id"])
            test.stack.down()
            test.stack.up("core")
            job = test.start(restore=checkpoint["external_path"])
            wait_outputs(test, oracle)
            stage("actual_broker_pause_retained_absolute_deadline")
            paused = record(audit(PARTS[0], "600"), 902, context())
            paused_manifest = oracle.group([paused], "timeout", ["cwd_missing"])
            ack = send([paused])
            test.wait_input_checkpoint(ack[-1]["offset"])
            checkpoint = test.wait_checkpoint(job["job_id"])
            require(
                any(
                    g["members"][0]["record_id"] == paused["raw"]["record_id"]
                    for g in checkpoint_inventory(test, checkpoint)["groups"]
                )
            )
            test.pause_broker(True)
            try:
                time.sleep(40)
                checkpoint = test.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"][
                    "completed"
                ]
                retained = checkpoint_inventory(test, checkpoint)
                require(
                    any(
                        g["members"][0]["record_id"] == paused["raw"]["record_id"]
                        for g in retained["groups"]
                    )
                    or any(
                        i["kind"] == "manifest" and i["key"] == paused_manifest["manifest_id"]
                        for i in retained["outbox"]
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
            job = test.start(restore=checkpoint["external_path"])
            wait_outputs(test, oracle)
            stage("every_required_sink_rejection_and_healthy_restore")
            faults = []
            for number, kind in enumerate(ROUTES):
                if kind == "tagged":
                    rows = [
                        record(audit(part, str(700 + number)), 1000 + number * 10 + i, context())
                        for i, part in enumerate(PARTS)
                    ]
                    oracle.group(rows)
                elif kind in ("processing", "manifest"):
                    rows = [record(audit("EOE", str(700 + number)), 1000 + number, context())]
                    oracle.group(rows, findings=["syscall_missing"])
                elif kind == "preservation":
                    rows = [
                        record(
                            fixtures["auth"]["raw"]["evidence"]["inline"].replace(
                                "password", "publickey"
                            ),
                            1000 + number,
                            context(True),
                        )
                    ]
                    oracle.preservation(rows[0], "unsupported_source")
                elif kind == "quarantine":
                    rows = [b"private-body-sentinel"]
                elif kind == "detection":
                    row = windows()
                    row["raw"]["cursor"]["value"] += "-sink-fault"
                    from linux_assembly_cases import identity

                    raw = row["raw"]
                    raw["record_id"] = identity(
                        [
                            raw["source"]["namespace"],
                            raw["source"]["instance"],
                            ["native", raw["cursor"]["value"]],
                        ]
                    )
                    rows = [row]
                    oracle.event(row, "windows")
                else:
                    rows = [
                        record(
                            fixtures["auth"]["raw"]["evidence"]["inline"],
                            1000 + number,
                            context(True),
                        )
                    ]
                    oracle.event(rows[0], "auth")
                values = retain(rows)
                test.wait_checkpoint(job["job_id"])
                test.fault(kind, "2")
                try:
                    ipc = "".join(
                        json.dumps(
                            dict(
                                sequence=i,
                                key=None,
                                value=base64.b64encode(value).decode()
                                if value is not None
                                else None,
                            )
                        )
                        + "\n"
                        for i, value in enumerate(values)
                    )
                    response = test.helper_run(
                        test.process_args("inject", INPUT), timeout=120, data=ipc
                    )
                    acks = [
                        json.loads(line)
                        for line in response.stdout.splitlines()
                        if json.loads(line).get("type") == "ack"
                    ]
                    oracle.register(rows, acks)
                    wait_failure(test, job, "RecordTooLarge", timeout=180)
                    checkpoint = test.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"][
                        "completed"
                    ]
                    evidence = checkpoint_inventory(test, checkpoint)
                    require(any(i["kind"] == kind for i in evidence["outbox"]))
                    faults.append(
                        dict(
                            kind=kind,
                            checkpoint=checkpoint["id"],
                            blocked_intents=sum(i["kind"] == kind for i in evidence["outbox"]),
                        )
                    )
                finally:
                    test.fault(kind, "1")
                job = test.start(restore=checkpoint["external_path"])
                wait_outputs(test, oracle)
            stage("metrics_original_input_hashes_and_stable_duplicates")
            require(any("detectbridge_integration" in value for value in test.metrics().values()))
            for container in test.stack.containers():
                logs = run(["docker", "logs", container["Id"]])
                require("private-body-sentinel" not in logs.stdout + logs.stderr)
            outputs = wait_outputs(test, oracle)
            # Independently retrieve and hash every admitted original Kafka value.
            read = test.private_read(
                test.process_args("read", INPUT, "0", str(len(oracle.inputs))), timeout=90
            )
            original_wires = [json.loads(line) for line in read.stdout.splitlines()]
            original_wires = [wire for wire in original_wires if "value" in wire]
            require(len(original_wires) == len(oracle.inputs))
            for wire in original_wires:
                value = base64.b64decode(wire["value"]) if wire["value"] is not None else b""
                require(
                    hashlib.sha256(value).hexdigest()
                    == oracle.inputs[wire["offset"]]["value_sha256"]
                )
            result = dict(
                status="qualified",
                project=project,
                inputs=len(oracle.inputs),
                logical_events=len(oracle.events),
                physical_outputs=len(outputs),
                logical_outputs=len({(kind, wire["key"]) for kind, wire, doc in outputs}),
                sink_failures=faults,
                broker_pause_seconds=40,
                bundle=config["bundle"],
                evaluation_bundle_sha256=config["evaluation_bundle_sha256"],
            )
            save(report, result)
            return result
        except BaseException as error:
            failure = dict(
                status="failed",
                phase=phase,
                project=project,
                error_type=type(error).__name__,
                locations=[
                    Path(f.filename).name + ":" + str(f.lineno)
                    for f in traceback.extract_tb(error.__traceback__)[-5:]
                ],
            )
            if str(error).replace("_", "").isalnum():
                failure["category"] = str(error)
            try:
                details = json.dumps(
                    test.rest("/jobs/" + test.latest_job()["job_id"] + "/exceptions")
                )
                failure["exception_sha256"] = hashlib.sha256(details.encode()).hexdigest()
                failure["known_markers"] = [
                    m
                    for m in (
                        "RecordTooLarge",
                        "incompatible_integration_restore",
                        "OutOfMemoryError",
                        "integration_schema_invalid",
                    )
                    if m in details
                ]
            except Exception:
                pass
            save(report, failure)
            print(json.dumps(failure), flush=True)
            raise
        finally:
            if (test.stack.folder / "state.json").exists():
                try:
                    test.stack.down()
                finally:
                    test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")
