"""Synthetic/opt-in recorded writer qualification, isolated from development projects."""

import base64
import json
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from typing import Any

import replay
from check_datasets import load_catalog
from check_writer import require
from stack import ROOT, Stack, StackError, project_lock, run
from transport import OUTPUT, QUARANTINE, Transport, sha
from transport_fixtures import catalog as synthetic_catalog
from writer import DIAGNOSTICS, FAILURES, REPLAY, Writer


def inject(transport, topic, key, value):
    args = transport.process_args("inject", topic)
    child = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
    )
    try:
        assert child.stdin and child.stdout
        child.stdin.write(
            json.dumps(
                {
                    "sequence": 0,
                    "key": base64.b64encode(key).decode() if key is not None else None,
                    "value": base64.b64encode(value).decode() if value is not None else None,
                }
            )
            + "\n"
        )
        child.stdin.flush()
        ack = json.loads(child.stdout.readline(4096))
        child.stdin.close()
        end = json.loads(child.stdout.readline(4096))
        if ack.get("type") != "ack" or end.get("type") != "end" or child.wait(timeout=40):
            raise StackError("qualification_injection_unacknowledged")
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
        transport.remove_helper(args)


def logical_id(pipeline, envelope):
    return replay.identity_hash(["1.0.0", pipeline, envelope["run_id"], str(envelope["sequence"])])


def get_document(stack, index, identity):
    code, value = stack.request("GET", "/" + index + "/_doc/" + identity)
    return value.get("_source") if code == 200 else None


def group_offsets(writer):
    result = {}
    for line in writer.kafka_offsets().splitlines():
        cells = line.split()
        if len(cells) >= 6 and cells[1] in (OUTPUT, QUARANTINE, FAILURES):
            try:
                result[cells[1]] = {
                    "committed": int(cells[3]),
                    "end": int(cells[4]),
                    "lag": int(cells[5]),
                }
            except ValueError:
                raise StackError("uninitialized_writer_offset") from None
    return result


def wait_state(writer, state, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if writer.runtime("health")["state"] == state:
                return
        except StackError:
            pass
        time.sleep(1)
    raise StackError("writer_state_timeout_" + state.lower())


def await_accounted(writer, expected, diagnostic_count, timeout=180):
    pipeline_id = writer.config()["pipeline_id"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        offsets = group_offsets(writer)
        if len(offsets) == 3 and all(item["lag"] == 0 for item in offsets.values()):
            docs = {}
            ids = list(expected)
            for start in range(0, len(ids), 100):
                code, response = writer.stack.request(
                    "POST", "/" + REPLAY + "/_mget", {"ids": ids[start : start + 100]}
                )
                if code != 200:
                    raise StackError("qualification_document_read_failed")
                for item in response["docs"]:
                    if not item.get("found"):
                        break
                    source = item["_source"]
                    identity = item["_id"]
                    original = expected[identity]
                    require("projection", source)
                    if (
                        source["input_sha256"] != sha(original)
                        or logical_id(pipeline_id, json.loads(original)) != identity
                    ):
                        raise StackError("qualification_projection_identity_or_hash_mismatch")
                    stable = {
                        k: v
                        for k, v in source.items()
                        if k not in ("content_sha256", "first_input")
                    }
                    canonical = json.dumps(
                        stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode()
                    if sha(canonical) != source["content_sha256"] or "inline" in source.get(
                        "evidence", {}
                    ):
                        raise StackError("qualification_projection_content_mismatch")
                    docs[identity] = source
            if len(docs) == len(expected):
                writer.stack.request("POST", "/" + REPLAY + "," + DIAGNOSTICS + "/_refresh")
                code, search = writer.stack.request("GET", "/" + DIAGNOSTICS + "/_search?size=1000")
                if code != 200:
                    raise StackError("qualification_diagnostics_read_failed")
                count_status, count = writer.stack.request("GET", "/" + REPLAY + "/_count")
                if count_status != 200 or count["count"] != len(expected):
                    raise StackError("unexpected_replay_documents")
                hits = search["hits"]["hits"]
                if len(hits) == diagnostic_count:
                    retained = {}
                    for hit in hits:
                        doc = hit["_source"]
                        require("projection", doc)
                        diagnostic = doc["diagnostic"]
                        reference = diagnostic["input"]
                        name = reference["topic"]
                        records = writer.transport.read_records(
                            name, reference["offset"], reference["offset"] + 1
                        )
                        if len(records) != 1:
                            raise StackError("qualification_reference_missing")
                        value = records[0]["value"]
                        raw = b"" if value is None else base64.b64decode(value)
                        if (
                            sha(raw) != diagnostic["value_sha256"]
                            or len(raw) != diagnostic["value_size"]
                            or (value is None) != diagnostic["value_is_null"]
                        ):
                            raise StackError("qualification_reference_mismatch")
                        retained[hit["_id"]] = reference
                    return {
                        "logical_documents": len(docs),
                        "diagnostics": len(hits),
                        "retrievable_references": len(retained),
                        "offsets": offsets,
                    }
        time.sleep(1)
    raise StackError("writer_accounting_timeout")


def qualify(recorded=False):
    project = "detectbridge-test-" + uuid.uuid4().hex
    with (
        tempfile.TemporaryDirectory(prefix="detectbridge-writer-") as temporary,
        project_lock(project),
    ):
        from pathlib import Path

        temp = Path(temporary)
        data_cache = replay.DATA_CACHE if recorded else temp / "data"
        catalog = load_catalog() if recorded else synthetic_catalog(data_cache)
        transport = Transport(project, data_cache=data_cache, runs=temp / "runs")
        writer = Writer(project)
        writer.transport = transport
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        transport.stack = writer.stack = Stack(project, port=port)
        phase = "initialization"
        report = {}
        body: object

        def stage(value):
            nonlocal phase
            phase = value
            print(json.dumps({"project": project, "phase": phase}), file=sys.stderr, flush=True)

        try:
            stage("initialization")
            transport.init()
            stage("full_profile")
            transport.stack.init("full")
            transport.stack.up("full")
            stage("transport_start")
            transport.start()
            stage("writer_init")
            writer.init()
            config = writer.config()
            stage("writer_start")
            writer.start()
            writer.stack.inspect("full")
            # Idempotent administration must preserve every existing binding.
            stage("writer_init_idempotency")
            writer.stop()
            if writer.init()["writer_id"] != config["writer_id"]:
                raise StackError("writer_initialization_not_idempotent")
            writer.start()
            expected = {}
            runs = []
            for _ in range(2):
                result = replay.start(
                    list(catalog),
                    catalog=catalog,
                    runs=transport.runs,
                    captures=temp / "captures",
                    data_cache=data_cache,
                    rate=None,
                )
                runs.append(result["run_id"])
                for envelope, raw in transport.replay_rows(result["run_id"]):
                    expected[logical_id(config["pipeline_id"], envelope)] = raw
            stage("first_run")
            transport.publish(runs[0])
            first_expected = {
                identity: raw
                for identity, raw in expected.items()
                if json.loads(raw)["run_id"] == runs[0]
            }
            await_accounted(writer, first_expected, 0)
            stage("timestamp_projection")
            template = json.loads(next(iter(expected.values())))
            time_run = str(uuid.uuid4())
            time_ids = []
            for sequence, timestamp in enumerate(
                ("2026-01-01T00:00:00.123456789Z", "1900-01-01T00:00:00.123456789Z")
            ):
                sample = json.loads(json.dumps(template))
                sample.update(run_id=time_run, sequence=sequence)
                sample["timing"] = {
                    "basis": "timing_index",
                    "original_time": timestamp,
                    "effective_time": timestamp,
                }
                value = replay.encoded(sample)
                identity = logical_id(config["pipeline_id"], sample)
                inject(transport, OUTPUT, time_run.encode(), value)
                expected[identity] = value
                first_expected[identity] = value
                time_ids.append(identity)
            await_accounted(writer, first_expected, 0)
            code, values = writer.stack.request(
                "POST",
                "/" + REPLAY + "/_search",
                {
                    "query": {"ids": {"values": [time_ids[0]]}},
                    "docvalue_fields": [
                        {"field": "effective_time", "format": "strict_date_optional_time_nanos"}
                    ],
                },
            )
            if (
                code != 200
                or values["hits"]["hits"][0]["fields"]["effective_time"][0]
                != "2026-01-01T00:00:00.123456789Z"
            ):
                raise StackError("nanosecond_docvalue_changed")
            outlier = get_document(writer.stack, REPLAY, time_ids[1])
            if (
                "effective_time" in outlier
                or outlier.get("time_projection_reason") != "outside_nanos_range"
            ):
                raise StackError("out_of_range_time_lost")
            stage("opensearch_outage")
            writer.stack.compose("stop", "opensearch", profile="full")
            transport.publish(runs[1])
            wait_state(writer, "BACKPRESSURED")
            if group_offsets(writer)[OUTPUT]["lag"] <= 0:
                raise StackError("outage_input_not_retained")
            writer.stack.compose("up", "-d", "opensearch", profile="full")
            await_accounted(writer, expected, 0)
            stage("kafka_outage")
            writer.stop()
            retained_control = {
                "contract_version": "1.0.0",
                "run_id": str(uuid.uuid4()),
                "sequence": 0,
                "type": "run_end",
                "record_count": 0,
                "dataset_count": 0,
            }
            inject(
                transport,
                OUTPUT,
                str(retained_control["run_id"]).encode(),
                replay.encoded(retained_control),
            )
            expected[logical_id(config["pipeline_id"], retained_control)] = replay.encoded(
                retained_control
            )
            transport.pause_broker(True)
            timer = threading.Timer(3, lambda: transport.pause_broker(False))
            timer.start()
            try:
                writer.start()
            finally:
                timer.join(timeout=10)
                transport.pause_broker(False)
            await_accounted(writer, expected, 0)
            stage("duplicates_and_quarantine")
            first_value = next(iter(expected.values()))
            first_envelope = json.loads(first_value)
            inject(transport, OUTPUT, first_envelope["run_id"].encode(), first_value)
            conflicting = json.loads(first_value)
            conflicting["dataset_id"] = "conflicting-dataset"
            inject(
                transport, OUTPUT, first_envelope["run_id"].encode(), replay.encoded(conflicting)
            )
            inject(transport, OUTPUT, b"private-key-sentinel", b"invalid-private-body-sentinel")
            transport.inject(b"invalid-key", b"relay-private-body-sentinel")
            await_accounted(writer, expected, 3)
            stage("partial_bulk_and_acknowledgment_crash")
            writer.stop()
            code, _ = writer.stack.request(
                "PUT", "/" + REPLAY + "/_settings", {"index.blocks.write": True}
            )
            if code != 200:
                raise StackError("qualification_write_block_failed")
            run_id = str(uuid.uuid4())
            good = {
                "contract_version": "1.0.0",
                "run_id": run_id,
                "sequence": 0,
                "type": "run_end",
                "record_count": 0,
                "dataset_count": 0,
            }
            poison = {
                "contract_version": "1.0.0",
                "run_id": run_id,
                "sequence": 1,
                "type": "dataset_end",
                "dataset_id": "mapping-overflow",
                "record_count": 2**63,
            }
            batch = writer.helper(
                "inject-batch",
                json.dumps(
                    [
                        {
                            "key": base64.b64encode(run_id.encode()).decode(),
                            "value": base64.b64encode(replay.encoded(envelope)).decode(),
                        }
                        for envelope in (good, poison)
                    ]
                ),
                timeout=45,
            )
            if batch.get("status") != "acknowledged" or len(batch.get("receipts", [])) != 2:
                raise StackError("qualification_batch_not_acknowledged")
            good_ack = batch["receipts"][0]
            expected[logical_id(config["pipeline_id"], good)] = replay.encoded(good)
            writer.stack.compose("up", "-d", "writer", profile="full")
            wait_state(writer, "BACKPRESSURED")
            stage("rebalance_with_unresolved_window")
            membership = writer.helper("membership", timeout=40)
            if membership.get("status") != "membership_checked":
                raise StackError("writer_membership_check_failed")
            wait_state(writer, "BACKPRESSURED")
            stage("partial_bulk_and_acknowledgment_crash")
            transport.pause_broker(True)
            try:
                writer.stack.request(
                    "PUT", "/" + REPLAY + "/_settings", {"index.blocks.write": False}
                )
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    if get_document(writer.stack, REPLAY, logical_id(config["pipeline_id"], good)):
                        break
                    time.sleep(1)
                else:
                    raise StackError("partial_success_not_observed")
                containers = [
                    c
                    for c in writer.stack.containers()
                    if c["Config"]["Labels"]["com.docker.compose.service"] == "writer"
                ]
                run(["docker", "kill", containers[0]["Id"]])
            finally:
                transport.pause_broker(False)
            if group_offsets(writer)[OUTPUT]["committed"] > good_ack["offset"]:
                raise StackError("unresolved_window_was_committed")
            writer.start()
            crash_accounting = await_accounted(writer, expected, 4)
            if (
                get_document(writer.stack, REPLAY, logical_id(config["pipeline_id"], poison))
                is not None
            ):
                raise StackError("permanent_failure_indexed")
            stage("authorization_and_persistence")
            for method, path, body in [
                ("DELETE", "/" + REPLAY, None),
                ("PUT", "/unrelated-index", {}),
                ("GET", "/_plugins/_security/api/internalusers", None),
            ]:
                response = writer.request(method, path, body)
                if response["status"] != 403:
                    raise StackError("writer_permission_boundary_failed")
            writer.stack.request(
                "PUT",
                "/p08-authorization-proof",
                {"settings": {"number_of_shards": 1, "number_of_replicas": 0}},
            )
            forbidden_bulk = (
                json.dumps({"create": {"_index": "p08-authorization-proof", "_id": "forbidden"}})
                + "\n"
                + json.dumps({"marker": "proof"})
                + "\n"
            )
            response = writer.request("POST", "/_bulk", forbidden_bulk)
            if response["status"] != 403 and not (
                response["status"] == 200
                and response["body"]["items"][0]["create"]["status"] == 403
            ):
                raise StackError("writer_can_write_unrelated_index")
            if (
                writer.request("DELETE", "/" + REPLAY + "/_doc/" + next(iter(expected)))["status"]
                != 403
            ):
                raise StackError("writer_can_delete_documents")
            for credential in (None, "wrong"):
                if writer.stack.request("GET", "/_cluster/health", credential=credential)[0] != 401:
                    raise StackError("opensearch_authentication_boundary_failed")
            stage("graceful_stop_with_unresolved_input")
            writer.stack.request("PUT", "/" + REPLAY + "/_settings", {"index.blocks.write": True})
            drain_control = {
                "contract_version": "1.0.0",
                "run_id": str(uuid.uuid4()),
                "sequence": 0,
                "type": "run_end",
                "record_count": 0,
                "dataset_count": 0,
            }
            drain_ack = inject(
                transport,
                OUTPUT,
                str(drain_control["run_id"]).encode(),
                replay.encoded(drain_control),
            )
            expected[logical_id(config["pipeline_id"], drain_control)] = replay.encoded(
                drain_control
            )
            wait_state(writer, "BACKPRESSURED")
            started_stop = time.monotonic()
            writer.stop()
            shutdown_seconds = round(time.monotonic() - started_stop, 3)
            stopped_writers = [
                item
                for item in writer.stack.containers()
                if item["Config"]["Labels"]["com.docker.compose.service"] == "writer"
            ]
            if len(stopped_writers) != 1:
                raise StackError("shutdown_writer_missing")
            shutdown_state = stopped_writers[0]["State"]
            if (
                shutdown_state.get("Running")
                or shutdown_state.get("OOMKilled")
                or shutdown_state.get("ExitCode") not in (0, 143)
                or shutdown_seconds > 35
            ):
                raise StackError("shutdown_not_graceful_or_bounded")
            if group_offsets(writer)[OUTPUT]["committed"] > drain_ack["offset"]:
                raise StackError("shutdown_committed_unresolved_input")
            writer.stack.request("PUT", "/" + REPLAY + "/_settings", {"index.blocks.write": False})
            writer.start()
            accounting = await_accounted(writer, expected, 4)
            writer.stop()
            stage("full_stack_recreation")
            writer.stack.down()
            writer.stack.up("full")
            writer.start()
            persistence = await_accounted(writer, expected, 4)
            writer.stack.inspect("full")
            if "detectbridge_writer_" not in writer.metrics()["metrics"]:
                raise StackError("writer_metrics_missing")
            for container in writer.stack.containers():
                captured = run(["docker", "logs", container["Id"]])
                logs = captured.stdout + captured.stderr
                password = (writer.folder / "writer-password").read_text().strip()
                encoded_auth = base64.b64encode(
                    ("detectbridge_writer_v1:" + password).encode()
                ).decode()
                if any(
                    secret in logs
                    for secret in (
                        "private-body-sentinel",
                        "private-key-sentinel",
                        password,
                        encoded_auth,
                    )
                ):
                    raise StackError("writer_payload_or_credential_leaked_to_logs")
            report = {
                "status": "qualified",
                "recorded": recorded,
                "project": project,
                "runs": runs,
                "bundle": config["bundle"],
                "environment": writer.stack.doctor("full", check_port=False),
                "accounting": accounting,
                "crash_accounting": crash_accounting,
                "rebalance_member_partitions": membership.get("assigned_partitions"),
                "persistence": persistence,
                "partial_bulk": True,
                "acknowledgment_crash": True,
                "opensearch_outage": True,
                "failure_topic_outage": True,
                "kafka_outage": True,
                "rebalance": True,
                "authorization": True,
                "timestamp_projection": True,
                "replay_envelopes": sum(
                    1 for raw in expected.values() if json.loads(raw)["run_id"] in runs
                ),
                "proof_documents": 5,
                "shutdown_seconds": shutdown_seconds,
                "shutdown_exit_code": shutdown_state["ExitCode"],
            }
        except Exception as exc:
            category = str(exc) if isinstance(exc, StackError) else type(exc).__name__
            snapshot: dict[str, Any] = {
                "status": "failed",
                "phase": phase,
                "category": category,
                "project": project,
            }
            try:
                snapshot["bundle"] = writer.config()["bundle"]
                snapshot["health"] = writer.runtime("health")
                snapshot["offsets"] = group_offsets(writer)
            except Exception as diagnostic_error:
                snapshot["diagnostic_status"] = type(diagnostic_error).__name__
            try:
                services = []
                for container in writer.stack.containers():
                    name = container["Config"]["Labels"]["com.docker.compose.service"]
                    state = container["State"]
                    service = {
                        "service": name,
                        "state": state.get("Status"),
                        "oom_killed": state.get("OOMKilled", False),
                        "exit_code": state.get("ExitCode"),
                    }
                    if name == "writer":
                        logs = run(["docker", "logs", container["Id"]], check=False)
                        errors = []
                        for line in (logs.stdout + logs.stderr).splitlines():
                            try:
                                value = json.loads(line)
                                if re.fullmatch(r"[a-z0-9_]{1,100}", value.get("category", "")):
                                    errors.append({"category": value["category"]})
                            except (ValueError, AttributeError):
                                pass
                        service["errors"] = errors
                    services.append(service)
                snapshot["services"] = services
            except Exception as diagnostic_error:
                snapshot["services_status"] = type(diagnostic_error).__name__
            reports = ROOT / ".cache/writer-reports"
            reports.mkdir(exist_ok=True)
            replay.atomic_json(reports / (project + ".failure.json"), snapshot)
            raise StackError("writer_qualification_" + phase + "_" + category) from exc
        finally:
            handlers = {
                sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)
            }
            try:
                writer.stack.cleanup_helpers()
                if (writer.stack.folder / "state.json").exists():
                    writer.stack.reset(project)
                if transport.folder.exists():
                    shutil.rmtree(transport.folder)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
        if writer.stack.containers() or writer.folder.exists() or writer.stack.folder.exists():
            raise StackError("writer_qualification_cleanup_incomplete")
        reports = ROOT / ".cache/writer-reports"
        reports.mkdir(exist_ok=True)
        replay.atomic_json(reports / (project + ".json"), report)
        return report
