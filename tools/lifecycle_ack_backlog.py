"""CI-01 frozen signed-ACK transport mechanics; never worker checkpoint evidence."""

import base64
import copy
import shutil
import subprocess
import time
from typing import Any
from unittest.mock import patch

import lifecycle as local
import lifecycle_diagnostics as diagnostic
from lifecycle_runtime import DOMAINS, Runtime, identity, private_file
from lifecycle_runtime_cases import AUTHORITY, DEPLOYMENT, WORKERS, digest, encoded, require, sha

COUNT = 101
INVALID_OFFSET = 50


def store_manifest(root):
    return {
        str(path.relative_to(root)): sha(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def ack_payload(publication, registration, checkpoint):
    payload = dict(
        version="1.0.0",
        deployment_id=DEPLOYMENT,
        authority_id=AUTHORITY,
        worker_id=registration["worker_id"],
        incarnation=registration["incarnation"],
        revision=publication["revision"],
        command_sha256=publication["command_sha256"],
        bundle_sha256=publication["bundle_sha256"],
        compatibility_sha256=publication["compatibility_sha256"],
        phase="durable",
        checkpoint_id=checkpoint,
        category="ok",
    )
    payload["ack_id"] = "sha256:" + identity(
        [
            DOMAINS["ack"],
            *[
                payload[key]
                for key in (
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
    )
    return payload


def checked_prefix(runtime, wires, invalid_offset, cursor):
    require(runtime.state["ack_cursor"] == cursor, "mechanics_cursor")
    expected = {
        local.document(wire)["payload"]["ack_id"]: (offset, wire)
        for offset, wire in enumerate(wires[:cursor])
        if offset != invalid_offset
    }
    require(set(runtime.state["acks"]) == set(expected), "mechanics_ack_set")
    for ack_id, (offset, wire) in expected.items():
        row = runtime.state["acks"][ack_id]
        require(
            row["wire_sha256"] == sha(wire)
            and row["location"]["offset"] == offset
            and row["payload"] == local.document(wire)["payload"],
            "mechanics_ack_binding",
        )
    rejected = (
        {str(invalid_offset): sha(wires[invalid_offset])}
        if (invalid_offset is not None and invalid_offset < cursor)
        else {}
    )
    require(
        runtime.state["ack_rejected_positions"] == rejected
        and runtime.state["ack_rejections"] == len(rejected),
        "mechanics_rejection",
    )
    current = local.document(wires[-1])["payload"]["ack_id"]
    require((current in runtime.state["acks"]) == (cursor == COUNT), "mechanics_current_prefix")


def trial(snapshot, wires, invalid_offset, limit, folder, prefix, progress):
    progress.update(status="failed", limit=limit)
    try:
        result = _trial(snapshot, wires, invalid_offset, limit, folder, prefix, progress)
        progress.update(result, status="mechanics_passed")
        return progress
    finally:
        timings = progress.pop("timings", None)
        if timings is not None:
            progress["diagnostics"] = timings.report()
        try:
            local.write_exclusive(
                folder / ("trial-report-" + str(limit) + ".json"), encoded(progress)
            )
        except (OSError, ValueError):
            progress["secondary_metrics_write_failed"] = True


def _trial(snapshot, wires, invalid_offset, limit, folder, prefix, progress):
    target = folder / ("trial-" + str(limit))
    shutil.copytree(snapshot, target)
    initial = store_manifest(target)
    require(initial == store_manifest(snapshot), "mechanics_initial_store")
    runtime = Runtime(target)
    require(runtime.state["ack_cursor"] == 0 and not runtime.state["acks"], "mechanics_fresh")
    require(runtime.topic_status("ack") == prefix, "mechanics_frozen_prefix")
    original_network = runtime._network
    commits = []

    def network(*args, **kwargs):
        if args[0] == "commit":
            cursor = int(args[-1])
            # Already under observe's root lock. Replay into a separate state object
            # without reacquiring that non-reentrant filesystem lock.
            persisted = copy.copy(runtime)
            persisted._load()
            checked_prefix(persisted, wires, invalid_offset, cursor)
        result = original_network(*args, **kwargs)
        if args[0] == "commit":
            commits.append(int(args[-1]))
        return result

    timings = diagnostic.Timings()
    progress["timings"] = timings
    progress["commits"] = commits
    start = time.monotonic()
    deadline = start + 120
    timings.deadline_ns = int(deadline * 1_000_000_000)
    rounds: list[dict[str, int]] = []
    progress["rounds"] = rounds
    with (
        timings.activate(),
        patch.object(runtime, "_network", side_effect=network),
        patch.object(runtime, "_ack_payload", wraps=runtime._ack_payload) as validate,
    ):
        try:
            # Finite diagnostic completion continues to the frozen end even if late.
            # deadline_met remains false; this loop can never satisfy a worker gate.
            for _ in range(COUNT):
                before = runtime.state["ack_cursor"]
                status = runtime.observe(limit=limit, qualification_batch=True)
                cursor = status["ack_cursor"]
                checked_prefix(runtime, wires, invalid_offset, cursor)
                progress.update(cursor_end=cursor, checked_records=validate.call_count)
                require(before < cursor <= COUNT, "mechanics_progress")
                rounds.append(dict(start=before, end=cursor))
                if cursor == COUNT:
                    break
            require(runtime.state["ack_cursor"] == COUNT, "mechanics_incomplete")
            require(validate.call_count == COUNT, "mechanics_every_record_validated")
        finally:
            finished_observation = time.monotonic()
            progress.update(
                cursor_end=runtime.state["ack_cursor"],
                checked_records=validate.call_count,
                accepted=len(runtime.state["acks"]),
                rejected=runtime.state["ack_rejections"],
                elapsed_seconds=finished_observation - start,
                original_deadline_seconds=120,
                deadline_met=finished_observation <= deadline,
                deadline_remaining_seconds=deadline - finished_observation,
            )
    finished = time.monotonic()
    require(runtime.topic_status("ack") == prefix, "mechanics_prefix_changed")
    require(
        sum(
            row["counters"]["requested"]
            for row in timings.samples
            if row["stage"] == "signature_batch"
        )
        == COUNT,
        "mechanics_every_signature",
    )
    require(commits == [row["end"] for row in rounds], "mechanics_commits")
    # Reopen through full immutable/journal/referenced-ACK verification after all commits.
    reopened = Runtime(target)
    checked_prefix(reopened, wires, invalid_offset, COUNT)
    semantic = dict(
        acks={key: row["wire_sha256"] for key, row in reopened.state["acks"].items()},
        rejected=reopened.state["ack_rejected_positions"],
        cursor=reopened.state["ack_cursor"],
    )
    return dict(
        limit=limit,
        initial_store_sha256=digest(initial),
        prefix_sha256=digest(prefix),
        wire_sequence_sha256=digest([sha(wire) for wire in wires]),
        checked_records=COUNT,
        checked_signatures=COUNT,
        accepted=len(reopened.state["acks"]),
        rejected=reopened.state["ack_rejections"],
        cursor_start=0,
        cursor_end=COUNT,
        semantic_sha256=digest(semantic),
        commits=commits,
        rounds=rounds,
        elapsed_seconds=finished - start,
        original_deadline_seconds=120,
        deadline_met=finished <= deadline,
        deadline_remaining_seconds=deadline - finished,
        commit_guard="Full durable journal and ACK replay before each Kafka commit; included in mechanics timing",
    )


def run(qualification, case):
    """Fresh Kafka-only fixture; signing authority/worker keys stay under private work."""
    qualification.mechanics_report = dict(
        case=case,
        status="failed",
        full_gate=False,
        scope="Generated signed ACK-only transport mechanics; no real worker checkpoint completion",
        no_live_worker_producer=True,
        order=[8, 128],
        order_warm_cache_uncontrolled=True,
        trials=[],
    )
    runtime = qualification.runtime
    work = runtime.root.parent
    private = work / "ack-mechanics"
    private.mkdir(mode=0o700)
    registration = runtime.worker(WORKERS[0])
    qualification.registrations = [registration]
    old = qualification.publish("A")
    current = qualification.publish("B")
    require(
        not runtime.state["acks"]
        and runtime.state["ack_cursor"] == 0
        and not runtime.state["jobs"],
        "mechanics_no_worker_producer",
    )
    key_root = runtime.root / "workers" / WORKERS[0] / registration["incarnation"]
    wires = []
    for index in range(COUNT):
        publication = dict(
            old if index < 100 else current,
            compatibility_sha256=runtime.config["compatibility_sha256"],
        )
        payload = ack_payload(publication, registration, index + 1)
        source, destination = private / f"{index}.payload", private / f"{index}.signed"
        local.write_exclusive(source, encoded(payload))
        runtime._local(
            "sign", "ack", key_root / "private.der", key_root / "public.der", source, destination
        )
        destination.chmod(0o600)
        wire = private_file(destination, 65536)
        require(local.document(wire)["payload"] == payload, "mechanics_signed_payload")
        wires.append(wire)
    invalid_offset = INVALID_OFFSET if case == "invalid-signature" else None
    if invalid_offset is not None:
        wrapper = local.document(wires[invalid_offset])
        signature = bytearray(base64.b64decode(wrapper["signature"], validate=True))
        signature[0] ^= 1
        wrapper["signature"] = base64.b64encode(signature).decode()
        wires[invalid_offset] = encoded(wrapper)
    local.write_exclusive(private / "wire-hashes.json", encoded([sha(wire) for wire in wires]))
    source = private / "frozen.ndjson"
    local.write_exclusive(source, b"\n".join(wires) + b"\n")
    descriptor = runtime.state["broker"]["topics"]["ack"]
    # Existing pinned Kafka console producer exits and closes before timed draining.
    # No Flink worker is ever started in this fixture.
    command = [
        "docker",
        "compose",
        "-p",
        runtime.config["project"],
        "-f",
        str(runtime.root / "broker.compose.json"),
        "exec",
        "-T",
        "kafka",
        "env",
        "KAFKA_HEAP_OPTS=-Xmx256m",
        "/opt/kafka/bin/kafka-console-producer.sh",
        "--bootstrap-server",
        "kafka:9092",
        "--topic",
        descriptor["name"],
        "--producer-property",
        "acks=all",
        "--producer-property",
        "enable.idempotence=true",
    ]
    with source.open("rb") as input_file, (private / "producer.log").open("wb") as log:
        subprocess.run(
            command, stdin=input_file, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120
        )
    prefix = runtime.topic_status("ack")
    require(prefix["earliest"] == 0 and prefix["end"] == COUNT, "mechanics_prefix_count")
    snapshot = private / "initial-store"
    shutil.copytree(runtime.root, snapshot)
    local.write_exclusive(private / "initial-hashes.json", encoded(store_manifest(snapshot)))
    trials = qualification.mechanics_report["trials"]
    for limit in (8, 128):
        progress: dict[str, Any] = {}
        trials.append(progress)
        trial(snapshot, wires, invalid_offset, limit, private, prefix, progress)
    require(
        trials[0]["initial_store_sha256"] == trials[1]["initial_store_sha256"]
        and trials[0]["semantic_sha256"] == trials[1]["semantic_sha256"],
        "mechanics_pair",
    )
    require(
        not qualification.confirmed_ack_checkpoints and not qualification.checkpoint_evidence,
        "mechanics_not_worker_completion",
    )
    qualification.mechanics_report["status"] = "mechanics_passed"
    return qualification.mechanics_report
