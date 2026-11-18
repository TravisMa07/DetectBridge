"""Opt-in original-recording qualification through actual P13 adapters and search."""

import base64
import copy
import importlib.util
import json
import re
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from check_contracts import load_json
from integration import INPUT, Integration, build, checkpoint_inventory, runtime_binding
from integration_cases import ROOT, digest, encoded, identity, prepare
from integration_oracle import FIELDS, Oracle
from integration_verify import idle_checkpoint, wait_outputs
from linux_assembly import wait_failure
from linux_assembly_audit_recording import CATALOG as AUDIT_CATALOG
from linux_assembly_audit_recording import artifacts, prepared, verify_event
from linux_assembly_audit_runtime import controls, eligible_group, open_group
from linux_assembly_recorded import reviewed_rows
from linux_assembly_verify import require
from search_writer import REPLAY, SearchWriter
from search_writer_qualification import SourceView, accounted, check_views
from stack import project_lock, run, save

EXPECTATIONS = ROOT / "contracts/search-writer/v1/fixtures/recorded-expectations.json"
WINDOWS_CATALOG = ROOT / "catalog/recordings/windows-process-lab-v1.json"


def windows_verifier():
    spec = importlib.util.spec_from_file_location(
        "p13_windows_recording", ROOT / "packages/windows-adapters/recording.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def originals(windows, audit, auth, destination):
    """Validate accepted originals, provenance and terms before any Docker operation."""
    win = windows_verifier()
    catalogs = dict(windows=load_json(WINDOWS_CATALOG), audit=load_json(AUDIT_CATALOG))
    win_rows = win.inputs(catalogs["windows"], windows, "00000000-0000-4000-8000-000000000012")
    audit_rows = prepared(catalogs["audit"], artifacts(catalogs["audit"], audit))
    catalogs["auth"], auth_rows = reviewed_rows(auth, destination)
    # Local qualification only: no recording publication is authorized by these terms.
    require(catalogs["windows"]["terms"]["payload_publication"] is False)
    require(catalogs["audit"]["terms_review"] and catalogs["auth"]["terms_review"])
    return catalogs, {
        "windows": [dict(version="1.0.0", kind="windows_record", **r) for r in win_rows],
        "audit": [dict(version="1.0.0", kind="record", **r) for r in audit_rows],
        "auth": auth_rows,
    }


def auth_fields(row, expected):
    """Independent selected-capture RFC5424 fields from originals, never Java output."""
    match = re.fullmatch(
        r"<(?P<priority>[0-9]+)>1 (?P<timestamp>\S+) (?P<hostname>\S+) (?P<app_name>\S+) "
        r"(?P<procid>\S+) (?P<msgid>\S+) (?P<structured_data>-) "
        r"(?P<decision>Accepted|Failed) password for (?P<user>\S+) from "
        r"(?P<remote_address>\S+) port (?P<port>[0-9]+) ssh2\n",
        row["raw"]["evidence"]["inline"],
    )
    require(match is not None)
    assert match is not None
    values = match.groupdict()
    require(values["app_name"] == "sshd")
    require(values["timestamp"] == expected["timestamp"])
    require(
        values["user"] == expected["user"] and values["remote_address"] == expected["source_ip"]
    )
    require(int(values["port"]) == expected["source_port"])
    require((values["decision"] == "Accepted") == (expected["outcome"] == "success"))
    return dict(
        user=expected["user"],
        remote_address=expected["source_ip"],
        rfc5424={
            key: values[key]
            for key in (
                "priority",
                "timestamp",
                "hostname",
                "app_name",
                "procid",
                "msgid",
                "structured_data",
            )
        },
    )


def check_auth_source(event, row, expected, fields):
    ctx = row["context"]
    require(event["source_fields"] == fields)
    require(event["host"] == dict(id=ctx["host_binding"]["host_id"]))
    require(event["ecs"] == dict(version=ctx["source_contract"]["snapshot"]["ecs_version"]))
    classification = dict(ctx["source_contract"]["snapshot"]["classification"])
    classification.update(
        id=event["event"]["id"],
        created=row["raw"]["first_observed"],
        code="sshd",
        provider="sshd",
        dataset=ctx["source_contract"]["id"],
        outcome=expected["outcome"],
    )
    require(event["event"] == classification)
    db = event["detectbridge"]
    require(db["quality"] == dict(integrity="sufficient", eligibility="eligible", diagnostics=[]))
    require(
        db["assembly"]
        == dict(
            mode="standalone",
            closure="not_required",
            quality="source_indicated",
            assembler_version="1.0.0",
        )
    )
    require(
        db["extensions"]
        == {
            "linux.context": dict(
                version="1.0.0",
                context=ctx,
                findings=[],
                source_sha256=ctx["source_contract"]["sha256"],
                mapping_sha256=ctx["mapping_profile"]["sha256"],
            )
        }
    )
    utc = (
        datetime.fromisoformat(expected["timestamp"])
        .astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )
    require(event["@timestamp"] == utc)
    require(
        db["time"]
        == dict(
            basis="source",
            quality="valid",
            first_observed=row["raw"]["first_observed"],
            source_value=expected["timestamp"],
            source_utc=utc,
        )
    )


class RecordedOracle(Oracle):
    def __init__(self, config, binding, plan, catalogs, windows, frozen_auth=None):
        super().__init__(config, binding, plan)
        self.catalogs, self.windows = catalogs, windows
        self.frozen_auth = frozen_auth or {}
        self.literal = load_json(EXPECTATIONS)
        self.windows_preservation: dict[str, dict[str, Any]] = {}
        self.seen_windows: set[str] = set()
        self.win = windows_verifier()

    def describe(self, key, scenario, **extra):
        self.events[key].update(
            scenario=scenario,
            counts=self.literal["counts"][scenario],
            match_ids=self.literal["matches"][scenario],
            blocked_bits=self.literal["blocked_bits"],
            skipped_bits=self.literal["skipped_bits"],
            **extra,
        )

    def windows_rows(self, rows):
        for row, item in zip(rows, self.catalogs["windows"]["records"], strict=True):
            require(row["raw"]["evidence"]["sha256"] == item["sha256"])
            if item["expected"]["disposition"] == "unsupported_source":
                raw, ctx = row["raw"], row["context"]
                diagnostic = dict(
                    version="1.0.0",
                    record_id=raw["record_id"],
                    run_id=ctx["run_id"],
                    evidence_sha256=raw["evidence"]["sha256"],
                    code="unsupported_source",
                    reason="source_signature",
                    field="",
                )
                self.windows_preservation[digest(diagnostic)] = dict(
                    diagnostic=diagnostic, source=copy.deepcopy(ctx["source"])
                )
            else:
                event = self.event(row, "windows")
                self.describe(
                    (row["context"]["run_id"], event), "windows_" + item["action"], item=item
                )

    def auth_rows(self, rows):
        for row, expected in zip(rows, self.catalogs["auth"]["expectations"], strict=True):
            require(row["raw"]["evidence"]["sha256"] == expected["sha256"])
            if expected["disposition"] == "normalized":
                event = self.event(row, "auth_negative")
                self.native.auth(row, expectation=expected)
                self.describe(
                    (row["context"]["run_id"], event),
                    "auth_recorded",
                    auth_fields=self.frozen_auth[row["raw"]["record_id"]],
                    auth_expected=copy.deepcopy(expected),
                )
            else:
                require(expected["disposition"] == "unsupported_source")
                self.preservation(row, "unsupported_source")

    def audit_group(self, rows, group, closure):
        catalog = self.catalogs["audit"]
        spec = dict(group, closure=closure)
        manifest = self.native.group(
            rows,
            closure,
            group["findings"],
            execution=catalog["execution"] if not group["findings"] else None,
        )
        key = (rows[0]["context"]["run_id"], manifest["event_id"])
        self.events[key] = dict(rows=copy.deepcopy(rows), manifest=manifest)
        self.describe(
            key, "audit_recorded_skipped" if group["findings"] else "audit_recorded", group=spec
        )
        return manifest

    def audit_remainder(self, rows):
        for group in self.catalogs["audit"]["groups"]:
            if group["findings"]:
                self.audit_group([rows[i] for i in group["member_positions"]], group, "dataset_end")
        for row, spec in zip(rows, self.catalogs["audit"]["records"], strict=True):
            if spec["disposition"] != "group_member":
                require(spec["disposition"] == "extraction_failed")
                self.preservation(row, "extraction_failed")

    def check_source(self, event, expected):
        if "item" in expected:
            self.win.verify_event(
                self.catalogs["windows"], self.windows, expected["rows"][0], expected["item"], event
            )
        elif "group" in expected:
            verify_event(self.catalogs["audit"], expected["group"], expected["rows"], event)
        elif "auth_fields" in expected:
            check_auth_source(
                event, expected["rows"][0], expected["auth_expected"], expected["auth_fields"]
            )

    def check_windows_preservation(self, document):
        diagnostic = document["diagnostic"]
        key = digest(diagnostic)
        require(key in self.windows_preservation)
        require(
            self.windows_preservation[key] == dict(diagnostic=diagnostic, source=document["source"])
        )
        self.seen_windows.add(key)

    def check(self, outputs):
        ready = super().check(outputs)
        return ready and self.seen_windows == set(self.windows_preservation)


def retain(test, oracle, rows):
    with (test.folder / "recorded-inputs.ndjson").open("ab") as file:
        for row in rows:
            file.write(encoded(row) + b"\n")
    save(
        test.folder / "recorded-expectations.json",
        dict(
            literal=oracle.literal,
            events=[dict(run=k[0], event_id=k[1], **v) for k, v in oracle.events.items()],
            manifests=list(oracle.native.groups.values()),
            preservation=list(oracle.native.diagnostics.values()),
            windows_preservation=oracle.windows_preservation,
        ),
    )


def remaining_admissions(rows, remainder):
    """run_end closes the entire replay, so every source must precede it."""
    return [*remainder, *rows["windows"], *rows["auth"], controls(rows["audit"], "run_end")]


def qualify(windows, audit, auth):
    project = "detectbridge-p13-recorded-" + uuid.uuid4().hex[:10]
    reports = ROOT / ".cache/search-writer-reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = reports / (project + ".json")
    phase = "original_validation"
    try:
        catalogs, source = originals(windows, audit, auth, reports / (project + "-auth.ndjson"))
    except Exception as error:
        save(
            report,
            dict(
                status="unavailable", project=project, phase=phase, error_type=type(error).__name__
            ),
        )
        raise
    frozen_auth = {
        row["raw"]["record_id"]: auth_fields(row, expected)
        for row, expected in zip(source["auth"], catalogs["auth"]["expectations"], strict=True)
        if expected["disposition"] == "normalized"
    }
    require(len(frozen_auth) == 2)
    save(
        reports / (project + "-source-expectations.json"),
        dict(
            version="1.0.0",
            catalog_sha256={key: digest(value) for key, value in catalogs.items()},
            auth_fields=frozen_auth,
            literal=load_json(EXPECTATIONS),
        ),
    )
    # A separately pinned actual plan/image; existing synthetic plans stay unchanged.
    prepare(recorded=True)
    build(ROOT / ".cache/integration/recorded-plan.json")
    pipeline, writer = Integration(project), SearchWriter(project)
    with project_lock(project):
        try:

            def stage(name):
                nonlocal phase
                phase = name
                print(json.dumps(dict(project=project, phase=phase)), flush=True)

            stage("initialize_recorded_runtime")
            pipeline.init()
            pipeline.stack.init("full")
            pipeline.stack.up("full")
            job = pipeline.start()
            writer.init()
            writer.start()
            config = pipeline.config()
            oracle = RecordedOracle(
                config,
                runtime_binding(config),
                pipeline.qualification_plan(),
                catalogs,
                windows,
                frozen_auth,
            )
            view = SourceView(pipeline, runtime_binding(config))
            save(pipeline.folder / "recording-catalogs.json", catalogs)
            selected = eligible_group(catalogs["audit"])
            positions = selected["member_positions"]
            runs = [str(uuid.uuid4()), str(uuid.uuid4())]
            checkpoints = []

            def send(rows, fault=False):
                retain(pipeline, oracle, rows)
                if fault:
                    ipc = "".join(
                        json.dumps(
                            dict(
                                sequence=i, key=None, value=base64.b64encode(encoded(row)).decode()
                            )
                        )
                        + "\n"
                        for i, row in enumerate(rows)
                    )
                    response = pipeline.helper_run(
                        pipeline.process_args("inject", INPUT), timeout=120, data=ipc
                    )
                    acks = [
                        json.loads(line)
                        for line in response.stdout.splitlines()
                        if json.loads(line).get("type") == "ack"
                    ]
                else:
                    acks = pipeline.inject_rows([encoded(row) for row in rows])
                oracle.register(rows, acks)
                save(pipeline.folder / "recorded-acknowledgements.json", oracle.inputs)
                return acks

            for number, run_id in enumerate(runs):
                rows = copy.deepcopy(source)
                for batch in rows.values():
                    for row in batch:
                        row["context"]["run_id"] = run_id
                execution = [rows["audit"][i] for i in positions]
                remainder = [r for i, r in enumerate(rows["audit"]) if i not in positions]
                closure = "timeout" if number == 0 else "source_boundary"
                expected = oracle.audit_group(execution, selected, closure)
                if number == 0:
                    stage("recorded_open_checkpoint_taskmanager_deadline")
                    acks = send(execution)
                    pipeline.wait_input_checkpoint(acks[-1]["offset"])
                    cp = pipeline.wait_checkpoint(job["job_id"])
                    inventory = checkpoint_inventory(pipeline, cp)
                    open_group(inventory, expected, execution)
                    save(pipeline.folder / "recorded-open-checkpoint.json", inventory)
                    run(["docker", "kill", project + "-taskmanager-1"])
                    pipeline.stack.compose("up", "-d", "taskmanager", profile="full")
                    wait_outputs(view, oracle)
                    checkpoints.append(dict(kind="deadline", checkpoint=cp["id"]))
                else:
                    stage("recorded_tagged_sink_rejection_and_restore")
                    idle_checkpoint(pipeline, job)
                    save(writer.folder / "before-source-fault-writer-state.json", writer.status())
                    # This source-producer fault deliberately changes a topic policy
                    # frozen by the independent writer. Stop it during that operator
                    # intervention, then require its normal strict healthy restart.
                    writer.stop()
                    pipeline.fault("tagged", "2")
                    try:
                        send([*execution, controls(rows["audit"], "source_boundary")], fault=True)
                        wait_failure(pipeline, job, "RecordTooLarge", timeout=180)
                        cp = pipeline.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"][
                            "completed"
                        ]
                        inventory = checkpoint_inventory(pipeline, cp)
                        blocked = [
                            i
                            for i in inventory["outbox"]
                            if i["kind"] == "tagged"
                            and i["event_id"] == expected["event_id"]
                            and i["run_id"] == run_id
                        ]
                        require(bool(blocked))
                        require(
                            blocked[0]["members"]
                            == [
                                dict(
                                    record_id=r["raw"]["record_id"],
                                    evidence_sha256=r["raw"]["evidence"]["sha256"],
                                )
                                for r in execution
                            ]
                        )
                        save(pipeline.folder / "recorded-blocked-checkpoint.json", inventory)
                    finally:
                        pipeline.fault("tagged", "1")
                    job = pipeline.start(restore=cp["external_path"])
                    writer.start()
                    wait_outputs(view, oracle)
                    checkpoints.append(dict(kind="tagged", checkpoint=cp["id"]))
                stage("recorded_remaining_sources_and_membership")
                # Exact redelivery is deduplicated. A new qualification cursor with
                # unchanged original bytes independently exercises immutable late links.
                late = copy.deepcopy(execution[-1])
                raw = late["raw"]
                raw["cursor"]["position"] = 1000
                raw["record_id"] = identity(
                    [
                        raw["source"]["namespace"],
                        raw["source"]["instance"],
                        ["dataset", raw["cursor"]["artifact_sha256"], "1000"],
                    ]
                )
                oracle.preservation(late, "late_evidence", expected)
                send([execution[0], late])
                wait_outputs(view, oracle)
                oracle.audit_remainder(rows["audit"])
                oracle.windows_rows(rows["windows"])
                oracle.auth_rows(rows["auth"])
                send(remaining_admissions(rows, remainder))
                output = wait_outputs(view, oracle)
                accounted(writer)
                documents = check_views(writer, output)

            stage("recorded_retrieval_accounting_and_replay_isolation")
            tags = [d for (index, _), d in documents.items() if index == REPLAY]
            first = {d["event_id"]: d for d in tags if d["run_id"] == runs[0]}
            second = {d["event_id"]: d for d in tags if d["run_id"] == runs[1]}
            require(set(first) == set(second) and len(first) == 16)
            require(
                {d["processing_id"] for d in first.values()}.isdisjoint(
                    d["processing_id"] for d in second.values()
                )
            )
            for event in first:
                require(
                    first[event]["evidence_hashes"] == second[event]["evidence_hashes"]
                    and first[event]["record_ids"] == second[event]["record_ids"]
                )
            read = pipeline.private_read(
                pipeline.process_args("read", INPUT, "0", str(len(oracle.inputs))), timeout=90
            )
            wires = [
                json.loads(line) for line in read.stdout.splitlines() if "value" in json.loads(line)
            ]
            require(len(wires) == len(oracle.inputs))
            from hashlib import sha256

            for wire in wires:
                require(
                    sha256(base64.b64decode(wire["value"])).hexdigest()
                    == oracle.inputs[wire["offset"]]["value_sha256"]
                )
            detections = [doc for kind, _, doc in output if kind == "detection"]
            require(
                {d["detection_id"] for d in detections if d["run_id"] == runs[0]}.isdisjoint(
                    d["detection_id"] for d in detections if d["run_id"] == runs[1]
                )
            )
            # Same-count corruptions must be rejected by the source/attribution oracle.
            mutations = []
            for field in ("host", "counts", "attribution"):
                altered = copy.deepcopy(output)
                tag = next(d for k, _, d in altered if k == "tagged")
                if field == "host":
                    tag["event"]["host"]["id"] += "-tampered"
                elif field == "counts":
                    tag["counts"]["matched"] += 1
                    tag["counts"]["unmatched"] -= 1
                else:
                    tag["attribution"]["context_sha256"] = "0" * 64
                try:
                    oracle.check(altered)
                except Exception as rejected:
                    require(str(rejected) == "assembly_independent_expectation_failed")
                    mutations.append(field)
                else:
                    raise RuntimeError("recorded_same_count_tamper_accepted")
            logical = {(kind, doc[FIELDS[kind]]) for kind, _, doc in output}
            kind_counts = {kind: sum(k == kind for k, _ in logical) for kind in FIELDS}
            require(
                kind_counts
                == dict(
                    tagged=32,
                    detection=6,
                    processing=38,
                    manifest=20,
                    preservation=28,
                    quarantine=0,
                    receipt=99,
                )
            )
            require(len(oracle.inputs) == 99 and len(documents) == 76)
            result = dict(
                status="qualified",
                project=project,
                recorded=True,
                runs=runs,
                catalog_sha256={k: digest(v) for k, v in catalogs.items()},
                expectation_sha256=digest(oracle.literal),
                inputs=len(oracle.inputs),
                logical_events=len(oracle.events),
                logical_kind_counts=kind_counts,
                logical_outputs=len(logical),
                physical_outputs=len(output),
                physical_duplicates=len(output) - len(logical),
                source_search_documents=len(documents),
                rejected_mutations=mutations,
                checkpoints=checkpoints,
                integration_bundle=config["bundle"],
                writer_bundle=writer.config()["bundle"],
                evaluation_bundle_sha256=config["evaluation_bundle_sha256"],
                source_topic_offsets=accounted(writer),
                coverage="Recorded match/nonmatch/inapplicable/blocked/skipped; errors and other edge cases require synthetic suites",
            )
            save(report, result)
            return result
        except BaseException as error:
            try:
                save(writer.folder / "recorded-failure-writer-state.json", writer.status())
                for container in writer.stack.containers():
                    if container["Config"]["Labels"].get("com.docker.compose.service") == "writer":
                        logs = run(["docker", "logs", container["Id"]], check=False)
                        save(
                            writer.folder / "recorded-failure-writer-logs.json",
                            dict(stdout=logs.stdout, stderr=logs.stderr),
                        )
            except Exception:
                pass
            try:
                save(
                    pipeline.folder / "recorded-failure-exceptions.json",
                    pipeline.rest("/jobs/" + pipeline.latest_job()["job_id"] + "/exceptions"),
                )
            except Exception:
                pass
            save(
                report,
                dict(
                    status="failed",
                    project=project,
                    phase=phase,
                    error_type=type(error).__name__,
                    locations=[
                        Path(f.filename).name + ":" + str(f.lineno)
                        for f in traceback.extract_tb(error.__traceback__)[-6:]
                    ],
                ),
            )
            raise
        finally:
            if (pipeline.stack.folder / "state.json").exists():
                pipeline.stack.down()
                pipeline.stack.compose("down", "--volumes", "--remove-orphans", profile="full")
