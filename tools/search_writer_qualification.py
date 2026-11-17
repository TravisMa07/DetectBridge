"""Actual P13b adapter/Flink/Kafka to isolated TLS search writer qualification."""

import base64
import copy
import hashlib
import json
import time
import traceback
import uuid
from typing import Any

from check_contracts import load_json
from integration import INPUT, ROUTES, Integration, runtime_binding
from integration_cases import encoded
from integration_oracle import Oracle
from integration_verify import wait_outputs
from linux_assembly_cases import audit, context, record
from search_writer import DIAGNOSTICS, FAILURES, REPLAY, SearchWriter
from stack import ROOT, StackError, project_lock, run, save
from writer_qualification import get_document, wait_state

DETECTIONS = "detectbridge-detections-v1"
SEARCH_TOPICS = [ROUTES[k] for k in ("tagged", "detection", "processing")] + [FAILURES]
INDICES = [REPLAY, DETECTIONS, DIAGNOSTICS]


def require(condition, category):
    if not condition:
        raise StackError(category)


def content_hash(body):
    semantic = copy.deepcopy(body)
    for field in ("content_sha256", "first_input", "input_sha256", "evidence_source"):
        semantic.pop(field, None)
    if semantic.get("manifest"):
        semantic["manifest"] = {"semantic_sha256": semantic["manifest"]["semantic_sha256"]}
    return hashlib.sha256(encoded(semantic)).hexdigest()


def offsets(writer):
    result = {}
    for line in writer.kafka_offsets().splitlines():
        cells = line.split()
        if len(cells) >= 6 and cells[1] in SEARCH_TOPICS:
            result[cells[1]] = dict(committed=int(cells[3]), end=int(cells[4]), lag=int(cells[5]))
    return result


def accounted(writer, timeout=180):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        current = offsets(writer)
        if len(current) == 4 and all(v["lag"] == 0 for v in current.values()):
            return current
        time.sleep(1)
    raise StackError("search_accounting_timeout")


class SourceView:
    """Original producer observations; controlled probes require exact acknowledged bytes."""

    def __init__(self, pipeline, binding):
        self.pipeline = pipeline
        self.binding = binding
        self.manual: dict[tuple[str, int], dict[str, Any]] = {}
        self.verified: set[tuple[str, int]] = set()

    def __getattr__(self, name):
        return getattr(self.pipeline, name)

    def outputs(self):
        info = self.pipeline.broker()
        result = []
        observed = set()
        for kind, topic in ROUTES.items():
            end = info["end_offsets"][topic]
            if not end:
                continue
            response = self.pipeline.private_read(
                self.pipeline.process_args("read", topic, "0", str(end)), timeout=90
            )
            for line in response.stdout.splitlines():
                wire = json.loads(line)
                if "value" not in wire:
                    continue
                location = (topic, wire["offset"])
                if location in self.manual:
                    expected = self.manual[location]
                    require(
                        wire["key"] == expected["key"]
                        and wire["value"] == expected["value"]
                        and wire["partition"] == 0,
                        "search_controlled_probe_changed",
                    )
                    require(
                        wire["headers"].get("detectbridge.runtime.binding") == self.binding,
                        "search_controlled_probe_binding_changed",
                    )
                    observed.add(location)
                else:
                    result.append((kind, wire, json.loads(base64.b64decode(wire["value"]))))
        self.verified = observed
        return result


def inject(writer, topic, key, value, view, reason=None):
    row = dict(
        topic=topic,
        key=base64.b64encode(key).decode() if key is not None else None,
        value=base64.b64encode(value).decode() if value is not None else None,
    )
    with (writer.folder / "controlled-probe-inputs.ndjson").open("ab") as file:
        file.write(encoded(dict(row=row, reason=reason, copies=2)) + b"\n")
    result = writer.helper("inject-batch", json.dumps([row, row]), timeout=60)
    require(
        result.get("status") == "acknowledged" and len(result["receipts"]) == 2,
        "search_injection_unacknowledged",
    )
    for ack in result["receipts"]:
        require(
            ack["partition"] == 0 and (topic, ack["offset"]) not in view.manual,
            "search_probe_acknowledgement_invalid",
        )
        view.manual[(topic, ack["offset"])] = {**row, "reason": reason}
        with (writer.folder / "controlled-probe-acks.ndjson").open("ab") as file:
            file.write(
                encoded(
                    dict(topic=topic, **ack, value_sha256=hashlib.sha256(value or b"").hexdigest())
                )
                + b"\n"
            )
    return result["receipts"]


def check_failures(writer, view):
    expected = {
        location: item for location, item in view.manual.items() if item["reason"] is not None
    }
    records = writer.helper("read-failures", timeout=60)["records"]
    config = writer.config()
    physical = {wire["offset"]: wire for wire in records}
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    for wire in records:
        raw = base64.b64decode(wire["value"])
        failure = json.loads(raw)
        location = (failure["input"]["topic"], failure["input"]["offset"])
        require(location in expected, "search_unexpected_writer_failure")
        item = expected[location]
        original = base64.b64decode(item["value"]) if item["value"] is not None else None
        from integration_oracle import identity

        identity_value = identity(
            [
                "p13-search-writer:1.0.0",
                config["kafka_cluster_id"],
                config["source_topics"][location[0]]["id"],
                "0",
                str(location[1]),
            ]
        )
        require(
            failure["failure_id"] == identity_value
            and base64.b64decode(wire["key"]).decode() == identity_value
            and failure["diagnostic"]["category"] == item["reason"],
            "search_failure_identity_or_reason",
        )
        require(
            failure["input"]
            == dict(
                cluster_id=config["kafka_cluster_id"],
                topic_id=config["source_topics"][location[0]]["id"],
                topic=location[0],
                partition=0,
                offset=location[1],
            )
            and failure["value_sha256"] == hashlib.sha256(original or b"").hexdigest()
            and failure["value_size"] == len(original or b"")
            and failure["value_is_null"] == (original is None),
            "search_failure_original_reference",
        )
        if location in seen:
            require(seen[location] == failure, "search_failure_duplicate_changed")
        seen[location] = failure
        doc = wait_document(writer, DIAGNOSTICS, identity_value)
        first = physical[doc["first_input"]["offset"]]
        require(
            doc["first_input"]
            == dict(
                cluster_id=config["kafka_cluster_id"],
                topic_id=config["source_topics"][FAILURES]["id"],
                topic=FAILURES,
                partition=0,
                offset=first["offset"],
            )
            and doc["input_sha256"] == hashlib.sha256(base64.b64decode(first["value"])).hexdigest(),
            "search_failure_first_copy_mismatch",
        )
        require(
            doc["kind"] == "writer_failure"
            and doc["diagnostic"] == failure
            and content_hash(doc) == doc["content_sha256"],
            "search_failure_view_mismatch",
        )
    require(set(seen) == set(expected), "search_missing_writer_failure")
    view.outputs()
    require(view.verified == set(view.manual), "search_probe_originals_not_retrieved")
    return dict(
        logical_failures=len(seen),
        physical_failures=len(records),
        controlled_admissions=len(view.manual),
    )


def wait_document(writer, index, identity, timeout=150):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        doc = get_document(writer.stack, index, identity)
        if doc is not None:
            return doc
        time.sleep(1)
    raise StackError("search_document_timeout")


def check_views(writer, original_outputs):
    config = writer.config()
    found = {}
    physical = {
        (kind, wire["offset"]): (wire, document) for kind, wire, document in original_outputs
    }
    for kind, wire, document in original_outputs:
        if kind not in ("tagged", "detection", "processing"):
            continue
        identity = document[
            {"tagged": "processing_id", "detection": "detection_id", "processing": "diagnostic_id"}[
                kind
            ]
        ]
        index = {"tagged": REPLAY, "detection": DETECTIONS, "processing": DIAGNOSTICS}[kind]
        doc = wait_document(writer, index, identity)
        require(
            doc["kind"] == kind and content_hash(doc) == doc["content_sha256"],
            "search_content_hash_mismatch",
        )
        require(
            doc["processing_id"] == document["processing_id"]
            and doc["attribution"] == document["attribution"],
            "search_attribution_mismatch",
        )
        require(
            doc["versions"]["bundle_sha256"] == config["evaluation_bundle_sha256"],
            "search_bundle_mismatch",
        )
        require(
            doc["first_input"]["topic"] == ROUTES[kind]
            and doc["first_input"]["topic_id"] == config["source_topics"][ROUTES[kind]]["id"],
            "search_location_mismatch",
        )
        # Verify precisely the first retained physical copy, including its immutable topic.
        require(
            doc["first_input"]["cluster_id"] == config["kafka_cluster_id"]
            and doc["first_input"]["partition"] == 0,
            "search_first_input_scope_mismatch",
        )
        first_wire, first_document = physical[(kind, doc["first_input"]["offset"])]
        require(
            first_document == document
            and doc["input_sha256"]
            == hashlib.sha256(base64.b64decode(first_wire["value"])).hexdigest(),
            "search_original_value_hash_mismatch",
        )
        if kind == "tagged":
            event = document["event"]
            require(
                doc["event_id"] == event["event"]["id"]
                and doc["run_id"] == event["detectbridge"]["run_id"],
                "search_event_link_mismatch",
            )
            for field in ("counts", "tags", "matches"):
                require(doc[field] == document[field], "search_compact_output_mismatch")
            for field in ("host", "process", "user"):
                require(doc.get(field) == event.get(field), "search_ecs_field_mismatch")
            require(
                doc["original_timestamp"] == event["@timestamp"],
                "search_original_timestamp_mismatch",
            )
            require(
                doc["eligibility"] == event["detectbridge"]["quality"]["eligibility"],
                "search_quality_mismatch",
            )
            findings = [d["code"] for d in event["detectbridge"]["quality"]["diagnostics"]]
            findings += (
                event["detectbridge"]
                .get("extensions", {})
                .get("linux.context", {})
                .get("findings", [])
            )
            require(
                doc["source_findings"] == list(dict.fromkeys(findings)),
                "search_source_findings_mismatch",
            )
            require(
                doc["record_ids"] == [e["record_id"] for e in event["detectbridge"]["evidence"]],
                "search_membership_mismatch",
            )
            require(
                doc["evidence_hashes"]
                == [e["evidence"]["sha256"] for e in event["detectbridge"]["evidence"]],
                "search_evidence_hash_mismatch",
            )
            require(
                doc["evidence_source"]
                == dict(
                    cluster_id=config["kafka_cluster_id"],
                    topic=INPUT,
                    topic_id=config["source_topics"][INPUT]["id"],
                ),
                "search_evidence_source_mismatch",
            )
            require(
                all("inline" not in e for e in doc["evidence"]) and "extensions" not in doc,
                "search_original_leak",
            )
        elif kind == "detection":
            require(
                doc["rule"] == document["rule"]
                and doc["rule_id"] == document["rule"]["id"]
                and doc["rule_revision"] == document["rule"]["revision"],
                "search_rule_metadata_mismatch",
            )
        else:
            require(
                doc["rule_set"] == document["rule_set"] and doc["category"] == document["category"],
                "search_rule_set_mismatch",
            )
        if document.get("manifest"):
            manifest_topic = ROUTES["manifest"]
            require(
                doc["manifest"]["location"]
                == dict(
                    cluster_id=config["kafka_cluster_id"],
                    topic=manifest_topic,
                    topic_id=config["source_topics"][manifest_topic]["id"],
                ),
                "search_manifest_location_mismatch",
            )
            require(
                all(doc["manifest"][k] == v for k, v in document["manifest"].items()),
                "search_manifest_mismatch",
            )
        found[(index, identity)] = doc
    return found


def qualify(recorded=False):
    if recorded:
        raise StackError("recorded_search_plan_not_qualified")
    project = "detectbridge-p13-search-" + uuid.uuid4().hex[:10]
    pipeline, writer = Integration(project), SearchWriter(project)
    reports = ROOT / ".cache/search-writer-reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = reports / (project + ".json")
    phase = "initialize"

    def stage(value):
        nonlocal phase
        phase = value
        print(json.dumps(dict(project=project, phase=phase)), flush=True)

    with project_lock(project):
        try:
            stage("initialize")
            pipeline.init()
            pipeline.stack.init("full")
            pipeline.stack.up("full")
            pipeline.start()
            writer.init()
            writer.start()
            config = pipeline.config()
            oracle = Oracle(config, runtime_binding(config), pipeline.qualification_plan())
            view = SourceView(pipeline, runtime_binding(config))
            fixtures = load_json(ROOT / ".cache/integration/cases.json")
            runs = ["00000000-0000-4000-8000-000000000012", "00000000-0000-4000-8000-000000000013"]

            time_vectors = load_json(
                ROOT / "contracts/search-writer/v1/fixtures/expectations.json"
            )["time_vectors"]
            time_records: dict[str, dict[str, Any]] = {}

            def admit(run_id):
                rows = copy.deepcopy(fixtures["complete"])
                for row in rows:
                    row["context"]["run_id"] = run_id
                oracle.group(rows)
                for name in ("windows", "sysmon", "auth", "windows_skipped", "windows_budget"):
                    row = copy.deepcopy(fixtures[name])
                    row["context"]["run_id"] = run_id
                    oracle.event(row, "windows" if name == "sysmon" else name)
                    rows.append(row)
                skipped = record(audit("EOE", "850"), 5000, context())
                skipped["context"]["run_id"] = run_id
                oracle.group([skipped], findings=["syscall_missing"])
                rows.append(skipped)
                for number, spec in enumerate(time_vectors):
                    row = record(
                        fixtures["auth"]["raw"]["evidence"]["inline"].replace(
                            "2026-01-01T00:00:00Z", spec["timestamp"]
                        ),
                        6000 + number,
                        context(True),
                    )
                    row["context"]["run_id"] = run_id
                    event_id = oracle.event(row, "auth")
                    oracle.native.auth(
                        row,
                        expectation=dict(
                            outcome="success",
                            user="alice",
                            source_ip="192.0.2.1",
                            source_port=2222,
                            timestamp=spec["timestamp"],
                        ),
                    )
                    time_records[event_id] = spec
                    rows.append(row)
                unsupported = record(
                    fixtures["auth"]["raw"]["evidence"]["inline"].replace("password", "publickey"),
                    9000,
                    context(True),
                )
                unsupported["context"]["run_id"] = run_id
                oracle.preservation(unsupported, "unsupported_source")
                rows.append(unsupported)
                # Freeze originals and independent source expectations before Kafka admission.
                with (writer.folder / "independent-inputs.ndjson").open("ab") as file:
                    for row in rows:
                        file.write(encoded(row) + b"\n")
                save(
                    writer.folder / "independent-expectations.json",
                    dict(
                        literal_counts=oracle.expected,
                        events=[
                            dict(run=k[0], event_id=k[1], **v) for k, v in oracle.events.items()
                        ],
                        manifests=list(oracle.native.groups.values()),
                    ),
                )
                acks = pipeline.inject_rows([encoded(row) for row in rows])
                oracle.register(rows, acks)
                return rows

            stage("actual_source_to_search_first_run")
            admit(runs[0])
            output = wait_outputs(view, oracle)
            accounted(writer)
            first = check_views(writer, output)
            stage("search_outage_second_isolated_replay")
            writer.stack.compose("stop", "opensearch", profile="full")
            admit(runs[1])
            output = wait_outputs(view, oracle)
            wait_state(writer, "BACKPRESSURED")
            require(
                any(v["lag"] > 0 for v in offsets(writer).values()),
                "search_outage_input_not_retained",
            )
            writer.stack.compose("up", "-d", "opensearch", profile="full")
            accounted(writer)
            documents = check_views(writer, output)
            require(len(documents) > len(first), "search_replay_not_isolated")
            tags = [doc for (index, _), doc in documents.items() if index == REPLAY]
            by_event: dict[str, list[dict[str, Any]]] = {}
            for tag in tags:
                by_event.setdefault(tag["event_id"], []).append(tag)
            require(
                all(len({t["run_id"] for t in group}) == 2 for group in by_event.values()),
                "search_event_replay_accounting",
            )
            require(
                all(len({t["processing_id"] for t in group}) == 2 for group in by_event.values()),
                "search_processing_replay_collision",
            )
            stage("exact_nanosecond_docvalues_and_outside_range")
            code, _ = writer.stack.request("POST", "/" + REPLAY + "/_refresh")
            require(code == 200, "search_refresh_failed")
            for (index, processing), doc in documents.items():
                if index != REPLAY or doc["event_id"] not in time_records:
                    continue
                spec = time_records[doc["event_id"]]
                require(
                    doc["original_timestamp"] == spec["timestamp"], "search_time_original_changed"
                )
                if spec["indexed"]:
                    code, response = writer.stack.request(
                        "POST",
                        "/" + REPLAY + "/_search",
                        {
                            "query": {"term": {"processing_id": processing}},
                            "_source": False,
                            "docvalue_fields": [
                                {"field": "@timestamp", "format": "strict_date_optional_time_nanos"}
                            ],
                        },
                    )
                    require(
                        code == 200
                        and response["hits"]["hits"][0]["fields"]["@timestamp"]
                        == [spec["timestamp"]],
                        "search_nanosecond_docvalue_changed",
                    )
                else:
                    require(
                        "@timestamp" not in doc and doc["time_projection_reason"] == spec["reason"],
                        "search_outside_range_changed",
                    )
            stage("duplicates_semantic_conflict_and_failure_acknowledgement")
            selected = next((k, w, d) for k, w, d in output if k == "detection")
            kind, wire, original = selected
            identity = original["detection_id"]
            inject(writer, ROUTES[kind], identity.encode(), encoded(original), view)
            accounted(writer)
            bad = copy.deepcopy(original)
            bad["rule"]["provenance"]["authors"] = ["tampered author"]
            inject(writer, ROUTES[kind], identity.encode(), encoded(bad), view, "identity_conflict")
            accounted(writer)
            require(
                get_document(writer.stack, DETECTIONS, identity)["rule"] == original["rule"],
                "search_conflict_overwritten",
            )
            stage("blocked_failure_publication")
            # A valid managed topic policy is restored before any subsequent commit.
            writer.helper("failure-policy", json.dumps({"value": "block"}), timeout=90)
            ack = inject(
                writer,
                ROUTES["tagged"],
                b"private-key-sentinel",
                b"private-body-sentinel",
                view,
                "invalid_json",
            )
            wait_state(writer, "BACKPRESSURED")
            require(
                offsets(writer)[ROUTES["tagged"]]["committed"] <= ack[0]["offset"],
                "search_failure_unacknowledged_commit",
            )
            writer.helper("failure-policy", json.dumps({"value": "healthy"}), timeout=90)
            accounted(writer)
            stage("failure_topic_indexing_blocks_without_recursion")
            writer.stack.request(
                "PUT", "/" + DIAGNOSTICS + "/_settings", {"index.blocks.write": True}
            )
            inject(
                writer,
                ROUTES["tagged"],
                b"private-key-sentinel",
                b"private-body-sentinel",
                view,
                "invalid_json",
            )
            wait_state(writer, "BACKPRESSURED")
            require(offsets(writer)[FAILURES]["lag"] > 0, "search_failure_index_not_blocked")
            failure_end = offsets(writer)[FAILURES]["end"]
            time.sleep(2)
            require(offsets(writer)[FAILURES]["end"] == failure_end, "search_recursive_failure")
            writer.stack.request(
                "PUT", "/" + DIAGNOSTICS + "/_settings", {"index.blocks.write": False}
            )
            accounted(writer)
            stage("actual_source_window_crash_before_commit")
            writer.stop()
            writer.stack.request("PUT", "/" + REPLAY + "/_settings", {"index.blocks.write": True})
            crash_row = copy.deepcopy(fixtures["windows"])
            crash_row["raw"]["cursor"]["value"] += "-search-crash"
            from linux_assembly_cases import identity as source_identity

            raw = crash_row["raw"]
            raw["record_id"] = source_identity(
                [
                    raw["source"]["namespace"],
                    raw["source"]["instance"],
                    ["native", raw["cursor"]["value"]],
                ]
            )
            oracle.event(crash_row, "windows")
            with (writer.folder / "independent-inputs.ndjson").open("ab") as file:
                file.write(encoded(crash_row) + b"\n")
            save(
                writer.folder / "crash-independent-expectation.json",
                dict(counts=oracle.expected["windows"], record_id=raw["record_id"]),
            )
            crash_ack = pipeline.inject_rows([encoded(crash_row)])
            oracle.register([crash_row], crash_ack)
            output = wait_outputs(view, oracle)
            crash_kind, crash_wire, crash_tag = next(
                (k, w, d)
                for k, w, d in output
                if k == "tagged"
                and raw["record_id"]
                in [e["record_id"] for e in d["event"]["detectbridge"]["evidence"]]
            )
            # Source delivery/recovery is already checked above/P13b. This phase isolates writer commits.
            stage("cancel_source_before_writer_crash")
            pipeline.stop()
            stage("writer_indexing_before_uncommitted_crash")
            writer.stack.compose("up", "-d", "writer", profile="full")
            wait_state(writer, "BACKPRESSURED")
            pipeline.pause_broker(True)
            try:
                writer.stack.request(
                    "PUT", "/" + REPLAY + "/_settings", {"index.blocks.write": False}
                )
                wait_document(writer, REPLAY, crash_tag["processing_id"])
                container = next(
                    c
                    for c in writer.stack.containers()
                    if c["Config"]["Labels"]["com.docker.compose.service"] == "writer"
                )
                run(["docker", "kill", container["Id"]])
            finally:
                pipeline.pause_broker(False)
            require(
                offsets(writer)[ROUTES["tagged"]]["committed"] <= crash_wire["offset"],
                "search_unresolved_window_committed",
            )
            stage("writer_restore_after_uncommitted_crash")
            writer.start()
            accounted(writer)
            documents = check_views(writer, output)
            stage("stored_content_tamper_is_not_a_duplicate")
            stored = get_document(writer.stack, DETECTIONS, identity)
            code, _ = writer.stack.request(
                "POST",
                "/" + DETECTIONS + "/_update/" + identity,
                {"doc": {"rule_revision": "0" * 64}},
            )
            require(code == 200, "search_tamper_setup_failed")
            inject(
                writer,
                ROUTES[kind],
                identity.encode(),
                encoded(original),
                view,
                "identity_conflict",
            )
            accounted(writer)
            require(
                get_document(writer.stack, DETECTIONS, identity)["rule_revision"] == "0" * 64,
                "search_stored_tamper_was_overwritten",
            )
            # Only the qualification operator restores its derived proof view; the runtime never updates.
            code, _ = writer.stack.request("PUT", "/" + DETECTIONS + "/_doc/" + identity, stored)
            require(code in (200, 201), "search_tamper_restore_failed")
            stage("real_partial_bulk_protocol")
            sample = next(iter(documents.values()))
            good_id, bad_id = "qualification-good", "qualification-bad"
            ndjson = "".join(
                json.dumps(row) + "\n"
                for row in [
                    {"create": {"_index": REPLAY, "_id": good_id}},
                    sample,
                    {"create": {"_index": REPLAY, "_id": bad_id}},
                    {**sample, "unexpected_field": True},
                ]
            )
            response = writer.request("POST", "/_bulk", ndjson)
            require(
                response["status"] == 200
                and [i["create"]["status"] for i in response["body"]["items"]] == [201, 400],
                "search_partial_bulk_not_proven",
            )
            stage("permissions_and_restart")
            body: dict[str, Any] | None
            for method, path, body in [
                ("DELETE", "/" + REPLAY, None),
                ("DELETE", "/" + REPLAY + "/_doc/" + good_id, None),
                ("PUT", "/unrelated-index", {}),
                ("GET", "/detectbridge-replay-v1", None),
                ("GET", "/_plugins/_security/api/internalusers", None),
                ("PUT", "/_index_template/forbidden", {}),
            ]:
                require(
                    writer.request(method, path, body)["status"] == 403,
                    "search_permissions_broadened",
                )
            writer.stop()
            writer.start()
            accounted(writer)
            check_views(writer, output)
            stage("retrieval_hashes_metrics_and_logs")
            read = pipeline.private_read(
                pipeline.process_args("read", INPUT, "0", str(len(oracle.inputs))), timeout=90
            )
            originals = [json.loads(line) for line in read.stdout.splitlines() if '"value"' in line]
            require(len(originals) == len(oracle.inputs), "search_original_retrieval_count")
            for item in originals:
                require(
                    hashlib.sha256(base64.b64decode(item["value"])).hexdigest()
                    == oracle.inputs[item["offset"]]["value_sha256"],
                    "search_original_retrieval_hash",
                )
            require(
                "detectbridge_search_writer" in writer.runtime("metrics"), "search_metrics_missing"
            )
            for container in writer.stack.containers():
                logs = run(["docker", "logs", container["Id"]])
                require(
                    "private-body-sentinel" not in logs.stdout + logs.stderr,
                    "search_log_payload_leak",
                )
            failures = check_failures(writer, view)
            stage("credential_and_mapping_drift_rejected")
            writer.stop()
            password = (writer.folder / "writer-password").read_bytes()
            try:
                (writer.folder / "writer-password").write_bytes(b"changed-qualification-password\n")
                try:
                    writer.config()
                except StackError as error:
                    require(
                        str(error) == "writer_credential_changed",
                        "search_unrelated_credential_failure",
                    )
                else:
                    raise StackError("search_changed_credential_accepted")
            finally:
                (writer.folder / "writer-password").write_bytes(password)
            code, _ = writer.stack.request(
                "PUT",
                "/" + REPLAY + "/_mapping",
                {"properties": {"qualification_drift": {"type": "keyword"}}},
            )
            require(code == 200, "search_mapping_drift_setup_failed")
            try:
                writer.start()
            except StackError as error:
                require(
                    "index_identity_or_mapping_changed" in str(error),
                    "search_unrelated_mapping_failure",
                )
            else:
                raise StackError("search_mapping_drift_accepted")
            result = dict(
                status="qualified",
                project=project,
                inputs=len(oracle.inputs),
                logical_events=len(oracle.events),
                source_search_documents=len(documents),
                bundle=writer.config()["bundle"],
                integration_bundle=config["bundle"],
                source_topic_offsets=offsets(writer),
                failure_accounting=failures,
                two_isolated_runs=True,
                all_six_outcomes=True,
            )
            save(report, result)
            return result
        except Exception as exc:
            save(
                report,
                dict(
                    status="failed",
                    project=project,
                    phase=phase,
                    error_type=type(exc).__name__,
                    locations=[
                        f.filename.rsplit("/", 1)[-1] + ":" + str(f.lineno)
                        for f in traceback.extract_tb(exc.__traceback__)[-6:]
                    ],
                    category=str(exc) if isinstance(exc, StackError) else "qualification_failed",
                ),
            )
            raise
        finally:
            if (pipeline.stack.folder / "state.json").exists():
                pipeline.stack.down()
                pipeline.stack.compose("down", "--volumes", "--remove-orphans", profile="full")
