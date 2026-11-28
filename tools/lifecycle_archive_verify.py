"""Qualify an actual two-worker deployment, durable archive and isolated JVM replays."""

import base64
import collections
import copy
import hashlib
import ipaddress
import json
import os
import platform
import re
import subprocess
import traceback
import uuid
from typing import Any
from unittest.mock import patch

from archive_profiles import PINS
from lifecycle_runtime import Runtime
from lifecycle_runtime_cases import (
    AUTHORITY,
    DEPLOYMENT,
    FIXTURES,
    ROOT,
    WORKERS,
    check_packet,
    digest,
    encoded,
    packet,
    phase_cases,
    prepare,
    require,
    sha,
)
from lifecycle_runtime_verify import Qualification, stage_candidates

REPORTS = ROOT / ".cache/lifecycle-archive-qualification"
JARS = {
    k: ROOT / "packages" / module / "build/libs" / name
    for k, module, name in (
        ("runtime", "lifecycle-job", "lifecycle-job.jar"),
        ("probe", "lifecycle-job", "lifecycle-probe.jar"),
        ("producer", "integration-job", "integration-job.jar"),
        ("reader", "lifecycle-archive", "lifecycle-archive.jar"),
        ("historical", "historical-replay", "historical-replay.jar"),
        ("current", "current-replay", "current-replay.jar"),
    )
}


def write(path, value):
    path.write_bytes(encoded(value) + b"\n")
    path.chmod(0o600)


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def contents(root):
    return {
        str(p.relative_to(root)): file_hash(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


def archive_command(work, operation, *args, runtime=None, crash=None, expected=0):
    arguments = [
        "docker",
        "run",
        "--rm",
        "--network",
        runtime.config["project"] + "_internal" if runtime else "none",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--memory",
        "512m",
        "--pids-limit",
        "128",
        "--cpus",
        "1",
        "--mount",
        f"type=bind,src={work},dst=/archive-work",
        "--mount",
        f"type=bind,src={JARS['reader']},dst=/reader.jar,readonly",
    ]
    if crash:
        arguments += ["--env", "DETECTBRIDGE_LIFECYCLE_ARCHIVE_CRASH=" + crash]
    command = [
        *arguments,
        "--entrypoint",
        "java",
        PINS["image"],
        "-Xmx320m",
        "-jar",
        "/reader.jar",
        operation,
        *args,
    ]
    result = subprocess.run(command, capture_output=True, timeout=180)
    if result.returncode != expected:
        (work / ("failure-" + uuid.uuid4().hex + ".stderr")).write_bytes(result.stderr)
        raise ValueError(f"lifecycle_archive_{operation}_exit_{result.returncode}")
    if operation == "retire":
        require(
            result.stderr.strip().endswith(b"lifecycle_archive_permanent_hold"),
            "retirement_blocker",
        )
    return result.stdout


def register_objects(work, validator):
    objects = work / "objects"
    objects.mkdir(mode=0o700)
    entries = []
    for kind, data in [
        ("runtime", JARS["runtime"].read_bytes()),
        ("producer", JARS["producer"].read_bytes()),
        ("validator", validator.read_bytes()),
        ("registry", encoded(dict(version="1.0.0", objects=[]))),
        ("provenance", (FIXTURES / "provenance.json").read_bytes()),
        ("provenance", (FIXTURES / "source-references.json").read_bytes()),
    ]:
        key = sha(data)
        (objects / key).write_bytes(data)
        (objects / key).chmod(0o600)
        entries.append(dict(kind=kind, sha256=key))
    return entries


def capture(work, runtime, objects, name, report, *, interrupt):
    from lifecycle_archive_graph import manifest_for

    manifest = manifest_for(runtime, str(uuid.uuid4()), objects)
    archive = "/archive-work/" + name
    write(work / (name + ".json"), manifest)
    archive_command(work, "init", archive, archive + ".json", "/archive-work/objects")

    def status():
        return json.loads(archive_command(work, "status", archive, "kafka:9092", runtime=runtime))

    if interrupt:
        before = status()
        require(all(h == 0 for h in before["heads"].values()), "initial_archive_heads")
        archive_command(
            work,
            "drain",
            archive,
            "kafka:9092",
            runtime=runtime,
            crash="before_segment_publish",
            expected=86,
        )
        unpublished = status()
        require(before == unpublished, "before_archive_publication")
        archive_command(
            work,
            "drain",
            archive,
            "kafka:9092",
            runtime=runtime,
            crash="before_kafka_commit",
            expected=86,
        )
        published = status()
        require(
            published["committed"] == before["committed"]
            and any(v > 0 for v in published["heads"].values()),
            "durability_before_kafka_commit",
        )
        report.update(before=before, unpublished=unpublished, published=published)
    archive_command(work, "drain", archive, "kafka:9092", runtime=runtime)
    final = status()
    require(
        len(final["heads"]) == 6
        and final["committed"] == final["heads"]
        and all(v > 0 for v in final["heads"].values()),
        "archive_recovery_commit",
    )
    report.update(final=final)
    lines = archive_command(work, "export", archive).splitlines()
    prefix, *rows = [json.loads(line) for line in lines]
    require(prefix["manifest"] == manifest and prefix["heads"] == final["heads"], "export_binding")
    require(len(rows) <= 4096, "wire_selection_limit")
    keys = [(r["topic"], r["offset"]) for r in rows]
    require(keys == sorted(set(keys)), "physical_location_conflict")
    for entry in objects:
        body = archive_command(work, "object", archive, entry["sha256"])
        require(body == (work / "objects" / entry["sha256"]).read_bytes(), "archive_object")
    report.update(
        archive_id=manifest["archive_id"], wire_count=len(rows), export_sha256=digest(rows)
    )
    return manifest, rows


def compare_broker(run, rows, heads):
    """Independent Kafka formatter over the synthetic profile's UTF-8 keys and JSON values."""
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row["topic"]].append(row)
    fingerprints = {}
    for topic, head in sorted(heads.items()):
        values = grouped[topic]
        require([row["offset"] for row in values] == list(range(head)), "original_offset_set")
        expected = bytearray()
        for row in values:
            require(
                row["partition"] == 0
                and row["timestamp_type"] == "CreateTime"
                and row["headers"] == []
                and row["key"] is not None
                and row["value"] is not None,
                "original_wire_metadata",
            )
            expected.extend(
                f"CreateTime:{row['timestamp']}\tPartition:0\tOffset:{row['offset']}\tNO_HEADERS\t".encode()
                + base64.b64decode(row["key"], validate=True)
                + b"\t"
                + base64.b64decode(row["value"], validate=True)
                + b"\n"
            )
        args = [
            "docker",
            "compose",
            "--project-name",
            run.config["project"],
            "--file",
            str(run.root / "broker.compose.json"),
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-console-consumer.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            topic,
            "--partition",
            "0",
            "--offset",
            "0",
            "--max-messages",
            str(head),
            "--timeout-ms",
            "20000",
        ]
        for field in ("timestamp", "partition", "offset", "headers", "key", "value"):
            args += ["--formatter-property", f"print.{field}=true"]
        sample = subprocess.run(args, capture_output=True, timeout=90, check=True)
        require(sample.stdout == expected, "kafka_wire_comparison")
        fingerprints[topic] = dict(rows=head, sha256=sha(sample.stdout))
    return fingerprints


def ref(row):
    return dict(
        topic=row["topic"], offset=row["offset"], value_sha256=sha(base64.b64decode(row["value"]))
    )


def output_scope(kind, doc):
    if kind == "tagged":
        return doc["event"]["detectbridge"]["run_id"], doc["event"]["event"]["id"]
    if kind == "manifest":
        return doc["key"]["run_id"], doc["event_id"]
    return doc["run_id"], doc["event_id"]


def requests(manifest, rows):
    sources = collections.defaultdict(list)
    decisions = collections.defaultdict(list)
    output_topic = manifest["common"]["topics"]["output"]["name"]
    input_topics = {w["input_topic"]["name"]: w["worker_id"] for w in manifest["workers"]}
    for row in rows:
        if row["topic"] in input_topics:
            obj = json.loads(base64.b64decode(row["value"]))
            sources[
                (input_topics[row["topic"]], obj["context"]["run_id"], obj["raw"]["record_id"])
            ].append(row)
        elif row["topic"] == output_topic:
            obj = json.loads(base64.b64decode(row["value"]))
            if obj["kind"] == "receipt":
                continue
            require(
                obj["kind"] in {"tagged", "manifest", "detection"}, "unexpected_archived_output"
            )
            run, event = output_scope(obj["kind"], obj["document"])
            decisions[(obj["worker_id"], run, event)].append((row, obj))
    result = []
    for phase in (1, 2, 3):
        for worker in WORKERS:
            cases = [c for c in phase_cases(phase) if c["worker_id"] == worker]
            original = cases[0]["run_id"]
            units = []
            for case in cases:
                inputs = []
                for admitted in case["admissions"]:
                    found = sources[(worker, original, admitted["raw"]["record_id"])]
                    require(
                        len(found) == 1
                        and base64.b64decode(found[0]["value"]) == encoded(admitted),
                        "archived_input_literal",
                    )
                    inputs.append(ref(found[0]))
                outputs = []
                for wire, env in decisions[(worker, original, case["expected"]["event_id"])]:
                    require(env["revision"] == phase, "archived_revision")
                    outputs.append(ref(wire))
                require(outputs, "archive_missing_decisions")
                units.append(
                    dict(
                        kind="windows" if worker == WORKERS[0] else "audit",
                        inputs=inputs,
                        outputs=outputs,
                    )
                )
            result.append(
                (
                    cases,
                    dict(
                        version="lifecycle-replay/1",
                        mode="historical",
                        worker_id=worker,
                        original_run_id=original,
                        units=units,
                    ),
                )
            )
    return result


def check_source_fields(case, event):
    rows = case["admissions"]
    expected = case["expected"]
    evidence = [dict(record_id=r["raw"]["record_id"], evidence=r["raw"]["evidence"]) for r in rows]
    require(event["detectbridge"]["evidence"] == evidence, "derived_raw_evidence")
    if case["id"].startswith("security"):
        require(
            event["user"]["name"] == expected["user_name"]
            and event["source_fields"]["SubjectUserName"] == expected["user_name"],
            "derived_windows_subject",
        )
    else:
        require(
            event["process"]
            == dict(
                executable=expected["executable"],
                args=expected["args"],
                pid=42,
                working_directory="/tmp",
            )
            and event["source_fields"]["paths"]
            == [dict(item=0, name=expected["executable"]), dict(item=1, name="/lib/ld.so")],
            "derived_audit_execution",
        )


def check_results(cases, results, bundle, run_id):
    literal = {row["case_id"]: row["bundles"][bundle] for row in packet("expectations")["cases"]}
    by_event = {case["expected"]["event_id"]: case for case in cases}
    observed: dict[str, Any] = {}
    detections = {}
    manifests = {}
    for result in results:
        require(result["run_id"] == run_id, "derived_run")
        for entry in result["outputs"]:
            kind, body = entry["kind"], entry["value"]
            actual_run, event = output_scope(kind, body)
            require(actual_run == run_id and event in by_event, "derived_origin")
            case = by_event[event]
            expected = literal[case["id"]]
            if kind == "tagged":
                require(event not in observed, "duplicate_derived_tag")
                matches = [{k: row[k] for k in ("id", "revision")} for row in body["matches"]]
                require(
                    body["counts"] == expected["counts"] and matches == expected["matched"],
                    "derived_literal_decision",
                )
                require(
                    body["event"]["detectbridge"]["quality"]["eligibility"] == "eligible",
                    "derived_quality",
                )
                check_source_fields(case, body["event"])
                observed[event] = dict(
                    case=case["id"],
                    expected=expected,
                    actual_counts=body["counts"],
                    actual_matches=matches,
                    processing_id=body["processing_id"],
                    detection_ids=[r["detection_id"] for r in body["matches"]],
                    plan_bundle=body["attribution"]["bundle_sha256"],
                )
            elif kind == "detection":
                require(
                    event not in detections
                    and [
                        {
                            "id": body["rule"]["id"],
                            "revision": body["rule"]["revision"],
                        }
                    ]
                    == expected["matched"],
                    "derived_detection",
                )
                detections[event] = (body["processing_id"], [body["detection_id"]])
            elif kind == "manifest":
                members = [member["record_id"] for member in body["members"]]
                require(
                    event not in manifests
                    and body["closure"] == "source_boundary"
                    and members == [a["raw"]["record_id"] for a in case["admissions"]],
                    "derived_original_membership",
                )
                manifests[event] = members
            else:
                raise ValueError("lifecycle_archive_unexpected_derived_kind")
    require(set(observed) == set(by_event), "missing_derived_decision")
    require(
        {
            event: (row["processing_id"], row["detection_ids"])
            for event, row in observed.items()
            if row["detection_ids"]
        }
        == detections,
        "detection_membership",
    )
    require(
        set(manifests) == {e for e, c in by_event.items() if c["id"].startswith("audit")},
        "manifest_membership",
    )
    return dict(events=observed, ordered_members=manifests)


def run_replays(work, manifest, wires, bundles, report):
    from lifecycle_replay import replay

    archive = work / "archive"
    workspace = work / "replays"
    original = contents(archive)
    kwargs = dict(
        reader=JARS["reader"],
        reader_sha256=file_hash(JARS["reader"]),
        historical_jar=JARS["historical"],
        current_jar=JARS["current"],
    )
    source_by_ref = {(row["topic"], row["offset"]): row for row in wires}
    all_processing = set()
    changed = 0
    selections = requests(manifest, wires)
    request_path = work / "request.json"
    for number, (cases, historical) in enumerate(selections):
        historical_counts = {}
        for mode in ("historical", "current"):
            spec = copy.deepcopy(historical)
            bundle = cases[0]["bundle"] if mode == "historical" else "B"
            if mode == "current":
                schedule = [
                    dict(at_ms=i, action="input", input=r)
                    for i, r in enumerate(ref for unit in spec["units"] for ref in unit["inputs"])
                ]
                schedule.append(dict(at_ms=len(schedule), action="end", input=None))
                spec.update(
                    mode=mode,
                    bundle_sha256=bundles[bundle]["manifest"]["bundle_sha256"],
                    schedule=schedule,
                )
            write(request_path, spec)
            run = str(uuid.uuid4())
            dest = workspace / "runs" / run
            args = (archive, workspace, request_path, run)
            if number == 0:
                for fault, count in (("during_result", 0), ("after_result_publication", 1)):

                    def interrupt(phase):
                        if phase == fault:
                            raise InterruptedError(fault)

                    try:
                        with patch("lifecycle_replay.HOOK", side_effect=interrupt):
                            replay(*args, **kwargs, resume=fault == "after_result_publication")
                    except InterruptedError as exc:
                        require(str(exc) == fault, "unexpected_replay_interruption")
                    else:
                        raise ValueError("lifecycle_archive_unobserved_replay_interruption")
                    require(
                        len(list((dest / "units").glob("*/result.json"))) == count,
                        "replay_committed_prefix",
                    )
            receipt = replay(*args, **kwargs, resume=number == 0)
            paths = sorted((dest / "units").glob("*/result.json"))
            require(receipt["units"] == len(paths), "replay_count")
            results = [json.loads(p.read_bytes()) for p in paths]
            checked = check_results(cases, results, bundle, run)
            for row in checked["events"].values():
                require(row["processing_id"] not in all_processing, "isolated_processing_identity")
                require(
                    row["plan_bundle"] == bundles[bundle]["plan"]["bundle_sha256"],
                    "selected_semantic_plan",
                )
                all_processing.add(row["processing_id"])
            counts = {e: detail["actual_counts"] for e, detail in checked["events"].items()}
            if mode == "historical":
                historical_counts = counts
                for unit, result in zip(spec["units"], results, strict=True):
                    expected = []
                    for r in unit["outputs"]:
                        wire = source_by_ref[(r["topic"], r["offset"])]
                        env = json.loads(base64.b64decode(wire["value"]))
                        env.pop("document")
                        expected.append(dict(reference=r, **env))
                    require(result["original_outputs"] == expected, "original_envelope_attribution")
            else:
                changed += sum(counts[e] != historical_counts[e] for e in counts)
                require(
                    all(r["bundle_sha256"] == spec["bundle_sha256"] for r in results)
                    and results[-1]["state"]["assembler"]["runs"][run] == "ended",
                    "current_selected_bundle",
                )
            if number == 0:
                prefix = contents(dest)
                require(replay(*args, **kwargs, resume=True) == receipt, "completed_resume")
                require(contents(dest) == prefix, "completed_resume_changed")
            if number == 0 and mode == "historical":
                second = str(uuid.uuid4())
                replay(archive, workspace, request_path, second, **kwargs)
                second_outputs = [
                    json.loads(p.read_bytes())
                    for p in sorted((workspace / "runs" / second / "units").glob("*/result.json"))
                ]
                second_checked = check_results(cases, second_outputs, bundle, second)
                for event, detail in second_checked["events"].items():
                    require(
                        detail["processing_id"] != checked["events"][event]["processing_id"]
                        and detail["actual_matches"] == checked["events"][event]["actual_matches"],
                        "second_run_isolation",
                    )
                checked["second_historical_run"] = dict(run_id=second, **second_checked)
            report.append(
                dict(
                    **receipt,
                    original_run_id=spec["original_run_id"],
                    revision=cases[0]["phase"],
                    selected_bundle=bundle,
                    **checked,
                )
            )
    require(len(all_processing) == 24 and changed == 8, "individual_changed_decisions")
    require(contents(archive) == original, "archive_mutated_by_replay")
    return selections[0][1], kwargs


class ArchiveQualification(Qualification):
    """Publish through the production admission API and keep the frozen worker oracle."""

    def add_case(
        self,
        case,
        bundle_name,
        publication=None,
        receipts=None,
        registration=None,
        receipt_states=None,
    ):
        if receipts is None:
            receipts = self.runtime.admit(case["worker_id"], case["admissions"])
        return super().add_case(
            case, bundle_name, publication, receipts, registration, receipt_states
        )


class QualificationRuntime(Runtime):
    """Allow a host with exhausted automatic address pools to supply three private subnets."""

    subnets: tuple[str, ...] = ()

    def _network_definition(self, definition, index):
        if self.subnets:
            internal = definition["networks"]["internal"]
            require(internal == {"internal": True}, "isolated_internal_network")
            internal["ipam"] = {"config": [{"subnet": self.subnets[index]}]}
        return definition

    def _broker_definition(self, cluster):
        return self._network_definition(super()._broker_definition(cluster), 0)

    def _worker_compose(self, worker):
        index = WORKERS.index(worker["worker_id"]) + 1
        return self._network_definition(super()._worker_compose(worker), index)


def actual(report, folder, work):
    from build_worker_validator import build
    from transport import java_env

    check_packet()
    report["phase"] = "offline_build"
    cmd = [
        str(ROOT / "gradlew"),
        "--offline",
        "--console=plain",
        ":integration-job:shadowJar",
        ":lifecycle-job:jar",
        ":lifecycle-job:qualificationJar",
        ":lifecycle-archive:test",
        ":lifecycle-archive:shadowJar",
        ":historical-replay:jar",
        ":current-replay:jar",
    ]
    with (folder / "build.log").open("wb") as log:
        subprocess.run(
            cmd,
            cwd=ROOT,
            env=java_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=600,
            check=True,
        )
    report["artifacts"] = {k: file_hash(p) for k, p in JARS.items()}
    for kind in ("producer", "historical", "current"):
        require(report["artifacts"][kind] == PINS[kind], "frozen_semantic_executable")
    report["phase"] = "candidates_and_validator"
    bundles = prepare(work / "candidates")
    store = stage_candidates(work / "candidate-store", bundles, JARS["producer"])
    validator = build(work / "validator-build")
    report["bundles"] = {
        k: dict(
            bundle_sha256=b["manifest"]["bundle_sha256"],
            plan_sha256=sha(b["plan_bytes"]),
            compatibility_sha256=b["manifest"]["compatibility_sha256"],
        )
        for k, b in bundles.items()
    }
    report["validator"] = validator["descriptor"]
    engine = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"]))
    report["engine"] = {
        k: engine[k] for k in ("Architecture", "NCPU", "MemTotal", "ServerVersion", "OSType")
    }
    runtime = QualificationRuntime.initialize(
        work / "deployment",
        AUTHORITY,
        DEPLOYMENT,
        JARS["runtime"],
        JARS["producer"],
        bundles["A"]["manifest"]["compatibility_sha256"],
        project="detectbridge-p15b-" + report["attempt"][:16],
        validator_artifact=validator["artifact"],
        validator_descriptor=validator["descriptor"],
        qualification_jar=JARS["probe"],
    )
    subnet = os.environ.get("DETECTBRIDGE_QUALIFICATION_NETWORK_POOL")
    if subnet:
        pool = ipaddress.IPv4Network(subnet)
        require(pool.is_private and pool.prefixlen == 22, "qualification_network_pool")
        runtime.subnets = tuple(str(net) for net in list(pool.subnets(new_prefix=24))[:3])
        report["owned_internal_subnets"] = list(runtime.subnets)
    try:
        report["phase"] = "two_worker_core"
        runtime.up()
        report["images"] = {}
        for role, image in (
            ("flink", PINS["image"]),
            ("kafka", runtime.config["kafka_image"]),
            ("validator", validator["descriptor"]["image_id"]),
        ):
            value = json.loads(subprocess.check_output(["docker", "image", "inspect", image]))[0]
            report["images"][role] = {
                key: value[key] for key in ("Id", "RepoDigests", "Architecture", "Os")
            }
        qual = ArchiveQualification(folder, runtime, bundles, store, JARS["probe"])
        qual.run("core")
        report["core"] = qual.coverage
        report["phase"] = "archive_and_recover"
        capture_work = work / "capture"
        capture_work.mkdir(mode=0o700)
        objects = register_objects(capture_work, validator["artifact"])
        proof: dict[str, Any] = {}
        report["capture"] = proof
        manifest, wires = capture(capture_work, runtime, objects, "archive", proof, interrupt=True)
        report["phase"] = "compare_actual_kafka"
        report["independent_broker_reads"] = compare_broker(runtime, wires, proof["final"]["heads"])
        original = contents(capture_work / "archive")
        archive_command(capture_work, "retire", "/archive-work/archive", expected=2)
        require(contents(capture_work / "archive") == original, "retirement_mutated_evidence")
        report["phase"] = "signed_hostile_ast"
        qual.hostile_ast()
        report["s12"] = qual.coverage["signed_hostile_ast"]
        second: dict[str, Any] = {}
        report["s12_capture"] = second
        capture(capture_work, runtime, objects, "s12-archive", second, interrupt=False)
    finally:
        runtime.stop()
        report["owned_runtime_stopped"] = True
    report["phase"] = "offline_replays"
    report["replays"] = []
    request, kwargs = run_replays(capture_work, manifest, wires, bundles, report["replays"])
    report["phase"] = "s12_archive_rejection"
    from lifecycle_replay import replay

    request_path = work / "hostile-selection.json"
    write(request_path, request)
    try:
        replay(
            capture_work / "s12-archive",
            work / "hostile-replay",
            request_path,
            str(uuid.uuid4()),
            **kwargs,
        )
    except ValueError as error:
        require(str(error) == "lifecycle_archive_compiler_rejected", "s12_rejection_cause")
        report["s12_archive_error"] = str(error)
    else:
        raise ValueError("lifecycle_archive_s12_accepted")


def main():
    attempt = uuid.uuid4().hex
    folder = REPORTS / "attempts" / attempt
    folder.mkdir(mode=0o700, parents=True)
    work = ROOT / ".cache/lifecycle-archive-work" / attempt
    work.mkdir(mode=0o700, parents=True)
    report: dict[str, Any] = dict(
        attempt=attempt,
        status="failed",
        phase="source",
        source_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        host=platform.platform(),
        scope="public synthetic two-worker archive and replay",
    )
    try:
        files = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
        )
        sources = {
            path: file_hash(ROOT / path)
            for path in sorted(os.fsdecode(raw) for raw in files.split(b"\0") if raw)
            if (ROOT / path).is_file() and not (ROOT / path).is_symlink()
        }
        write(folder / "sources.json", sources)
        report["source_manifest_sha256"] = file_hash(folder / "sources.json")
        report["dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
        actual(report, folder, work)
        report.update(status="passed", phase="complete")
    except Exception as error:
        report["exception_class"] = type(error).__name__
        if re.fullmatch(r"[a-zA-Z0-9_]{1,160}", str(error)):
            report["category"] = str(error)
        (work / "private-traceback.txt").write_text(traceback.format_exc())
    finally:
        write(folder / "summary.json", report)
        write(REPORTS / "latest.json", report)
        print(
            json.dumps(
                {key: report.get(key) for key in ("attempt", "status", "phase", "category")}
            ),
            flush=True,
        )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
