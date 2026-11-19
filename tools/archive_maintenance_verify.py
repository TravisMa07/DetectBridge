"""Actual synthetic managed-JAR/Kafka and publication recovery qualification.

The frozen archive packet is independent of the planner. Opaque import closure
checks do not claim P05 semantic coverage; actual sealed replay is checked separately.
"""

import base64
import contextlib
import copy
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from unittest.mock import patch

import historical as history
from archive import LIMITS, TOPICS
from archive_maintenance import BUILDS, ManagedArchive, Operation, digest, verify_managed
from check_archive_maintenance import PINS
from check_contracts import load_json
from stack import ROOT, Stack, StackError, project_lock, run, save

CACHE = ROOT / ".cache/archive-maintenance-runtime"
REPORTS = ROOT / ".cache/archive-maintenance-reports"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def ensure_image(diagnostics):
    """Resolve the pinned execution image before any qualification helper starts."""
    named, digest_pin = PINS["image"].split("@")
    canonical = named.rsplit(":", 1)[0] + "@" + digest_pin
    diagnostics.mkdir(parents=True, exist_ok=True)
    sequence = 0

    def execute(stage, args):
        nonlocal sequence
        response = run(args, check=False, timeout=600 if stage == "pull" else 30)
        record = dict(
            command=args,
            exit_code=response.returncode,
            stdout=response.stdout,
            stderr=response.stderr,
        )
        history.write(diagnostics / f"{sequence:02d}-{stage}.json", history.encoded(record) + b"\n")
        history.sync(diagnostics)
        sequence += 1
        return response

    def missing(response):
        return response.returncode != 0 and "No such image:" in response.stderr

    def inspect(response):
        if response.returncode:
            raise StackError("maintenance_image_inspection_failed")
        metadata = json.loads(response.stdout)
        if len(metadata) != 1:
            raise StackError("maintenance_image_binding")
        image = metadata[0]
        aliases = {canonical, "docker.io/library/" + canonical}
        if (
            not any(value in aliases for value in image.get("RepoDigests", []))
            or image.get("Os") != "linux"
            or image.get("Architecture") not in {"arm64", "amd64"}
        ):
            raise StackError("maintenance_image_binding")
        return image

    response = execute("canonical-inspect", ["docker", "image", "inspect", canonical])
    if missing(response):
        pulled = execute("pull", ["docker", "pull", PINS["image"]])
        if pulled.returncode:
            raise StackError("maintenance_pinned_image_acquisition_failed")
        response = execute("canonical-after-pull", ["docker", "image", "inspect", canonical])
    verified = inspect(response)
    tagged = execute("pinned-inspect", ["docker", "image", "inspect", PINS["image"]])
    if missing(tagged):
        restored = execute("restore-tag", ["docker", "image", "tag", canonical, named])
        if restored.returncode:
            raise StackError("maintenance_pinned_image_alias_failed")
        tagged = execute("pinned-after-tag", ["docker", "image", "inspect", PINS["image"]])
    result = inspect(tagged)
    if result.get("Id") != verified.get("Id"):
        raise StackError("maintenance_image_binding")
    return result


def hashes(root):
    return {
        str(p.relative_to(root)): digest(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != ".lock"
    }


class Runtime:
    def __init__(self, folder, bundle, network=None):
        self.folder = folder.resolve()
        self.folder.mkdir(mode=0o700, parents=True)
        self.control = self.folder / "control"
        self.control.mkdir(mode=0o700)
        self.catalog = self.folder / "catalog"
        with history.catalog(self.catalog):
            pass
        self.archive = self.folder / "archive"
        self.managed = str(uuid.uuid4())
        self.bundle = bundle
        self.network = network

    def invoke(
        self,
        command,
        *args,
        role="managed",
        operation=None,
        crash=None,
        expected=None,
        expected_class=None,
        expected_pairs=None,
        catalog_lock=True,
        timeout=90,
        prepare=None,
        owned_operation=None,
        source_roots=(),
    ):
        identifier = operation or str(uuid.uuid4())
        lease = (
            contextlib.nullcontext(owned_operation)
            if owned_operation is not None
            else Operation(self.control, self.managed, identifier)
        )
        with lease as owned:
            failures = set(owned.folder.glob("failure-*.json"))
            classpath = str(BUILDS / self.bundle["managed"])
            main = "io.detectbridge.archive.ManagedMain"
            if role == "probe":
                classpath += ":" + str(BUILDS / self.bundle["probe"])
                main = "io.detectbridge.archive.ManagedProbe"
            elif role == "legacy":
                classpath = str(BUILDS / self.bundle["reader"])
                main = "io.detectbridge.archive.Main"

            def execute():
                return owned.container(
                    self.bundle["image"],
                    [
                        (BUILDS, BUILDS, True),
                        (self.folder, self.folder, False),
                        *((path, path, True) for path in source_roots),
                    ],
                    ["java", "-Xmx320m", "-cp", classpath, main, command, *map(str, args)],
                    network=self.network,
                    crash=crash,
                    timeout=timeout,
                )

            try:
                if catalog_lock:
                    with history.catalog(self.catalog):
                        if prepare is not None:
                            prepare()
                        if command == "retire":
                            self.snapshot(path=args[2])
                        response = execute()
                else:
                    response = execute()
            except subprocess.TimeoutExpired as error:
                save(
                    owned.folder / "timeout.json",
                    dict(
                        failure_class=type(error).__name__,
                        stdout=(error.stdout or b"").decode("utf-8", "replace"),
                        stderr=(error.stderr or b"").decode("utf-8", "replace"),
                    ),
                )
                raise
            except StackError:
                retained = set(owned.folder.glob("failure-*.json")) - failures
                if (expected is None and expected_pairs is None) or len(retained) != 1:
                    raise
                failed = load_json(retained.pop())
                observed_category = expected
                if expected == "crash":
                    assert expected_pairs is None
                    assert failed["exit_code"] == 86
                else:
                    detail = json.loads(failed["stdout"].splitlines()[-1])
                    assert failed["exit_code"] == 1
                    if expected_pairs is not None:
                        assert (detail["category"], detail["failure_class"]) in expected_pairs
                    else:
                        assert detail["category"] == expected
                        if expected_class is not None:
                            assert detail["failure_class"] == expected_class
                    observed_category = detail["category"]
                return dict(status="expected_failure", category=observed_category)
            assert expected is None and expected_pairs is None, "required failure was not observed"
            detail = json.loads(response.stdout.decode().splitlines()[-1])
            assert detail["status"] == "ok"
            return detail["result"]

    def registration(self):
        return dict(
            version="1.0.0",
            profile="archive-managed/1.0.0",
            managed_id=self.managed,
            archive_binding_sha256="0" * 64,
            implementation_sha256=self.bundle["managed"],
            group="detectbridge-archive-managed-v1-" + self.managed,
            origin=dict(kind="fresh", source_scope_sha256=None),
            destination=str(self.archive),
            catalog_destination=str(self.catalog),
            control_destination=str(self.control),
            limits=dict(
                maintenance_reserve_bytes=64 * 1024**2,
                control_bytes=32 * 1024**2,
                metadata_bytes=16 * 1024**2,
                plan_segments=256,
                scan_rows=65536,
                identity_tokens=262144,
                source_fingerprints=131072,
            ),
        )

    def clone(self, source):
        request = self.folder / "registration.json"
        save(request, self.registration())
        result = self.invoke(
            "clone", self.archive, source, request, str(uuid.uuid4()), source_roots=[source]
        )
        registration = history.verified(self.archive / "maintenance/registration.json")
        assert registration["destination"] == str(self.archive)
        assert registration["implementation_sha256"] == self.bundle["managed"]
        assert registration["group"] == "detectbridge-archive-managed-v1-" + self.managed
        return result

    def snapshot(self, pins=None, path=None):
        if pins is None:
            pins = []
            for pin_path in sorted((self.catalog / "pins").iterdir()):
                selection = history.verified(pin_path / "selection.json")
                history.require("selection", selection)
                assert sha(history.encoded(selection)) == pin_path.name
                pins.append(dict(selection_sha256=pin_path.name, selection=selection))
        value = dict(version="1.0.0", destination=str(self.catalog), pins=list(pins))
        path = path or self.folder / ("catalog-" + sha(history.encoded(value)) + ".json")
        save(path, value)
        return path

    def plan(self, next_offset, cutoff, *, pins=None, expected=None):
        identifier = str(uuid.uuid4())
        request = self.folder / ("request-" + identifier + ".json")
        output = self.folder / ("plan-" + identifier + ".json")
        save(
            request,
            dict(
                operation_id=identifier,
                cutoff_ms=cutoff,
                targets=[
                    dict(topic=topic, next=next) for topic, next in sorted(next_offset.items())
                ]
                if isinstance(next_offset, dict)
                else [dict(topic=TOPICS[0], next=next_offset)],
                reason="original synthetic runtime qualification",
            ),
        )
        catalog = self.folder / ("catalog-" + identifier + ".json")
        self.invoke(
            "plan",
            self.archive,
            request,
            catalog,
            output,
            expected=expected,
            prepare=lambda: self.snapshot(pins, catalog),
        )
        return output, catalog, identifier


def fixture_qualification(runtime, frozen, cases, stage):
    packet = runtime.folder / "frozen.json"
    save(packet, frozen)
    source = runtime.folder / "legacy"
    stage("frozen_original_materialization")
    runtime.invoke("fixture", packet, source, role="probe")
    original = hashes(source)
    runtime.clone(source)
    assert hashes(source) == original
    cases.append("actual_shared_source_lease_clone_preserves_original_fixture")
    stage("actual_public_clone_publication_crash_same_operation_retry")
    from archive_maintenance import clone_archive

    public_root = runtime.folder / "public-clone"
    public_root.mkdir()
    target, catalog_root, control_root = (
        public_root / name for name in ("archive", "catalog", "control")
    )
    identifier, managed = str(uuid.uuid4()), str(uuid.uuid4())
    original_container = Operation.container

    def crash_clone(owned, *args, **kwargs):
        kwargs["crash"] = "after_managed_publication"
        return original_container(owned, *args, **kwargs)

    with patch.object(Operation, "container", crash_clone):
        try:
            clone_archive(source, target, catalog_root, control_root, managed, identifier)
        except StackError:
            failures = list((control_root / identifier).glob("failure-*.json"))
            assert len(failures) == 1 and load_json(failures[0])["exit_code"] == 86
        else:
            raise AssertionError("public clone publication crash was not observed")
    assert target.exists()
    state = digest(control_root / "initialization.json"), digest(catalog_root / "catalog.json")
    public = clone_archive(source, target, catalog_root, control_root, managed, identifier)
    assert not (public_root / (".archive-managed-" + identifier)).exists()
    assert state == (
        digest(control_root / "initialization.json"),
        digest(catalog_root / "catalog.json"),
    )
    with public.session(str(uuid.uuid4())) as session:
        assert session.command("inspect")["durable_next"][TOPICS[0]] == 6
    assert hashes(source) == original
    cases.append("actual_public_clone_publication_crash_same_operation_cleanup_retry")
    stage("complete_prefix_and_inclusive_cutoff")
    plan, catalog, operation = runtime.plan(4, 100)
    planned = load_json(plan)
    assert len(planned["candidates"]) == 2
    assert (
        planned["candidates"][1]["segment_sha256"]
        == frozen["retirement_expected"]["previous_sha256"]
    )
    runtime.plan(3, 100, expected="managed_target_not_boundary")
    runtime.plan(4, 99, expected="managed_cutoff_timestamp")
    runtime.plan(2, 100, expected="managed_retained_identity_blocker")
    cases.append("actual_complete_prefix_cutoff_boundary_and_retained_identity_denial")
    stage("explicit_hold_compare_revision_and_release")
    hold = history.verified(runtime.archive / "maintenance/holds/00000000000000000000/holds.json")
    next_hold = dict(
        hold,
        revision=1,
        previous_sha256=sha(history.encoded(hold)),
        reason="synthetic explicit protection",
        holds=[
            dict(id=str(uuid.uuid4()), scope="all", topic=None, first=None, next=None, subject=None)
        ],
    )
    hold_file = runtime.folder / "hold.json"
    save(hold_file, next_hold)
    runtime.invoke("holds", runtime.archive, hold_file, str(uuid.uuid4()))
    runtime.plan(4, 100, expected="managed_hold_blocker")
    released = dict(
        next_hold, revision=2, previous_sha256=sha(history.encoded(next_hold)), holds=[]
    )
    save(hold_file, released)
    runtime.invoke("holds", runtime.archive, hold_file, str(uuid.uuid4()))
    cases.append("actual_explicit_hold_revision_and_release")
    stage("actual_shared_java_reader_lease")
    marker, release = runtime.folder / "reader.marker", runtime.folder / "reader.release"
    with ThreadPoolExecutor(max_workers=1) as pool:
        reader = pool.submit(
            runtime.invoke,
            "lease",
            runtime.archive,
            marker,
            release,
            role="probe",
            catalog_lock=False,
        )
        try:
            deadline = time.monotonic() + 30
            while not marker.exists() and not reader.done() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert marker.exists(), "shared Java lease was not acquired"
            runtime.invoke("recover", runtime.archive, str(uuid.uuid4()), expected="archive_locked")
        finally:
            release.write_bytes(b"release\n")
        assert reader.result(timeout=30)["released"] is True
    cases.append("actual_shared_java_reader_blocks_exclusive_mutation")
    stage("retirement_record_process_crash_and_exact_cleanup")
    plan, catalog, operation = runtime.plan(4, 100)
    retained = hashes(runtime.archive / "segments/topic-0/0/4")
    runtime.invoke(
        "retire",
        runtime.archive,
        plan,
        catalog,
        operation,
        operation=operation,
        crash="after_retirement_publication",
        expected="crash",
    )
    # Durable intent hides old data even before interrupted cleanup removes its bytes.
    assert runtime.invoke("inspect", runtime.archive)["retained_floor"][TOPICS[0]] == 4
    runtime.invoke(
        "wire",
        runtime.archive,
        TOPICS[0],
        "0",
        runtime.folder / "retired.json",
        expected="archive_retired",
    )
    runtime.invoke("retire", runtime.archive, plan, catalog, operation, operation=operation)
    assert not (runtime.archive / "segments/topic-0/0/0").exists()
    assert not (runtime.archive / "segments/topic-0/0/2").exists()
    assert hashes(runtime.archive / "segments/topic-0/0/4") == retained
    runtime.invoke(
        "object",
        runtime.archive,
        frozen["legacy"]["objects"][0]["metadata"]["sha256"],
        runtime.folder / "original.bin",
    )
    assert (runtime.folder / "original.bin").read_bytes() == bytes.fromhex("410d0a0ac3a90a5a")
    cases.append(
        "actual_retirement_process_crash_anchor_floor_idempotent_cleanup_and_original_object"
    )
    stage("actual_import_closure_publication_and_retrieval")
    run_dir, cache, index = (
        runtime.folder / name for name in ("import-run", "import-cache", "import-index")
    )
    for path in (run_dir, cache, index):
        path.mkdir()
    body = b'{"origin":"Original synthetic opaque closure; not P05 completeness"}\n'
    (run_dir / "manifest.json").write_bytes(body)
    descriptor = dict(
        kind="original",
        role="manifest",
        path="run/manifest.json",
        sha256=sha(body),
        length=len(body),
    )
    run_id = str(uuid.uuid4())
    metadata = dict(
        version="1.0.0",
        managed_id=runtime.managed,
        run_id=run_id,
        manifest_sha256=sha(body),
        p05_manifest_sha256="b" * 64,
        reviewed_catalog_sha256="c" * 64,
        record_count=0,
        envelope_count=1,
        segment_count=1,
        files=[descriptor],
    )
    metadata["id"] = sha(
        history.encoded(
            ["detectbridge.archive.p05-import/1", runtime.managed, run_id, sha(body), [descriptor]]
        )
    )
    meta_file = runtime.folder / "import.json"
    save(meta_file, metadata)
    imported = runtime.invoke(
        "import", runtime.archive, meta_file, run_dir, cache, index, str(uuid.uuid4())
    )
    assert imported == metadata
    exported = [
        runtime.folder / name for name in ("restored-run", "restored-cache", "restored-index")
    ]
    runtime.invoke("export-import", runtime.archive, metadata["id"], *exported)
    assert (exported[0] / "manifest.json").read_bytes() == body
    cases.append("actual_opaque_import_closure_exact_hash_and_fresh_export")


def kafka_qualification(runtime, cases, stage):
    stage("actual_kafka_managed_consumer")
    assert runtime.invoke("kafka", "init", "kafka:9092", role="probe")["created"] == 9
    registry = runtime.folder / "registry"
    registry.mkdir()
    body = bytes.fromhex("410d0a0ac3a90a5a")
    (registry / sha(body)).write_bytes(body)
    provenance = history.encoded(
        dict(origin="Original DetectBridge synthetic managed fixture", license="Apache-2.0")
    )
    (registry / sha(provenance)).write_bytes(provenance)
    request = runtime.folder / "init.json"
    save(
        request,
        dict(starts={topic: 0 for topic in TOPICS}, provenance=[sha(provenance)], limits=LIMITS),
    )
    legacy = runtime.folder / "legacy"
    runtime.invoke("init", legacy, "kafka:9092", request, registry, role="legacy")
    runtime.clone(legacy)
    rows = runtime.folder / "admissions.json"

    def publish_value(value):
        admission: dict[str, Any] = dict(
            topic=TOPICS[0], key=None, value=base64.b64encode(value).decode(), headers=[]
        )
        save(rows, [admission])
        ack = runtime.invoke("kafka", "publish", "kafka:9092", rows, role="probe")[0]
        assert ack["value_sha256"] == sha(value)
        return ack, admission

    def publish(index):
        value = history.encoded(
            dict(
                version="1.0.0",
                kind="run_end",
                run_id=str(uuid.uuid4()),
                control_id=str(uuid.uuid4()),
                provenance=["original synthetic managed Kafka packet"],
                signed=[-9223372036854775808, 9007199254740993, 9223372036854775807],
                source_time="2020-01-01T00:00:00.123456789012Z",
                occurrence=index,
            )
        )
        return publish_value(value)

    original_config = history.verified(runtime.archive / "archive.json")
    registration = history.verified(runtime.archive / "maintenance/registration.json")
    group = registration["group"]
    assert group != original_config["group"]

    def offsets():
        return runtime.invoke("kafka", "offsets", "kafka:9092", group, role="probe")

    first, admission = publish(0)
    progress = runtime.invoke("drain", runtime.archive, str(uuid.uuid4()))
    assert progress["durable_next"][TOPICS[0]] == first["offset"] + 1
    assert offsets()[TOPICS[0]] == first["offset"] + 1
    exported = runtime.folder / "original-wire.json"
    runtime.invoke("wire", runtime.archive, TOPICS[0], str(first["offset"]), exported)
    wire = load_json(exported)
    assert wire["value"] == admission["value"] and wire["timestamp"] == 1234567890
    assert json.loads(base64.b64decode(wire["value"]))["signed"][1] == 9007199254740993
    cases.append("actual_kafka_group_distinct_durable_commit_and_exact_wire_roundtrip")
    for index, phase in enumerate(
        ("during_payload", "after_rename", "before_kafka_commit", "after_kafka_commit"), 1
    ):
        stage("actual_kafka_crash_" + phase)
        ack, _ = publish(index)
        identifier = str(uuid.uuid4())
        runtime.invoke(
            "drain",
            runtime.archive,
            identifier,
            operation=identifier,
            crash=phase,
            expected="crash",
        )
        durable = runtime.invoke("inspect", runtime.archive)["durable_next"]
        committed = offsets()
        assert all(committed[t] is None or committed[t] <= durable[t] for t in TOPICS)
        wanted = ack["offset"] + 1
        assert durable[TOPICS[0]] == (wanted - 1 if phase == "during_payload" else wanted)
        if phase == "after_kafka_commit":
            assert committed[TOPICS[0]] == wanted
        else:
            assert committed[TOPICS[0]] < wanted
        runtime.invoke("drain", runtime.archive, identifier, operation=identifier)
        assert offsets()[TOPICS[0]] == ack["offset"] + 1
        cases.append("actual_kafka_process_crash_" + phase)
    stage("actual_kafka_archive_retirement_then_append")
    source: dict[str, Any] = dict(
        kind="record",
        raw=dict(
            record_id="sha256:" + "1" * 64,
            evidence=dict(
                encoding="base64", inline=base64.b64encode(body).decode(), sha256=sha(body)
            ),
        ),
        context=dict(
            run_id=str(uuid.uuid4()),
            host_id="synthetic-host-a",
            receipt=dict(received="2020-01-01T00:00:00.123456789012Z"),
        ),
    )
    publish_value(history.encoded(source))
    runtime.invoke("drain", runtime.archive, str(uuid.uuid4()))
    head = runtime.invoke("inspect", runtime.archive)["durable_next"][TOPICS[0]]
    plan, catalog, identifier = runtime.plan(head, 1234567890)
    runtime.invoke("retire", runtime.archive, plan, catalog, identifier, operation=identifier)
    next_ack, _ = publish(99)
    runtime.invoke("drain", runtime.archive, str(uuid.uuid4()))
    final = runtime.invoke("inspect", runtime.archive)
    assert final["retained_floor"][TOPICS[0]] == head
    assert final["durable_next"][TOPICS[0]] == next_ack["offset"] + 1
    assert offsets()[TOPICS[0]] == next_ack["offset"] + 1
    cases.append("actual_kafka_retired_anchor_append_and_monotone_durable_commit")
    stage("actual_retired_source_fingerprint_conflict_at_new_locations")
    for category in ("source", "semantic_conflict"):
        source["context"]["receipt"]["received"] = "2020-01-02T00:00:00.123456789012Z"
        if category == "semantic_conflict":
            source["context"]["host_id"] = "synthetic-host-b"
        ack, _ = publish_value(history.encoded(source))
        runtime.invoke("drain", runtime.archive, str(uuid.uuid4()))
        result = runtime.invoke(
            "wire",
            runtime.archive,
            TOPICS[0],
            str(ack["offset"]),
            runtime.folder / ("fingerprint-" + category + ".json"),
        )
        assert result["category"] == category
    cases.append("actual_retired_source_fingerprint_identical_new_occurrence_and_visible_conflict")
    stage("actual_broker_inspect_floor_durable_commit_lag_and_reserve")
    progress = runtime.invoke("inspect", runtime.archive, "--broker")
    save(runtime.folder / "broker-progress.json", progress)
    partition = progress["partitions"][TOPICS[0]]
    assert progress["retained_floor"][TOPICS[0]] == head
    assert partition["durable_next"] == partition["committed_next"] == partition["end"]
    assert partition["lag"] == 0
    assert partition["earliest"] <= head
    assert progress["reserve_bytes"] == 128 * 1024**2
    assert progress["holds_count"] == progress["pending_cleanup_count"] == 0
    assert progress["fingerprint_count"] == progress["retirement_sequence"] == 1
    assert (
        progress["live_rows"] == 3
    )  # New control, identical source, conflicting source after floor.
    assert progress["ordinary_headroom_bytes"] == max(
        0, progress["archive_bytes_cap"] - 64 * 1024**2 - progress["archive_bytes_used"]
    )
    assert progress["maintenance_headroom_bytes"] == max(
        0, progress["archive_bytes_cap"] - 32 * 1024**2 - progress["archive_bytes_used"]
    )
    cases.append("actual_broker_inspect_watermarks_zero_lag_and_finite_headroom")
    stage("actual_managed_broker_outage_preserves_durable_commit_boundary")
    pending, pending_row = publish(100)
    before_offsets = offsets()
    before_durable = runtime.invoke("inspect", runtime.archive)["durable_next"]
    identifier = str(uuid.uuid4())
    stack = Stack(runtime.network.removesuffix("_internal"))
    stack.compose("pause", "kafka", profile="core")
    try:
        try:
            runtime.invoke(
                "broker-drain",
                runtime.archive,
                identifier,
                runtime.control / identifier,
                operation=identifier,
                role="probe",
            )
        except StackError:
            failures = list((runtime.control / identifier).glob("failure-*.json"))
            assert len(failures) == 1
            failed = load_json(failures[0])
            detail = json.loads(failed["stdout"].splitlines()[-1])
            assert failed["exit_code"] == 1
            assert detail["failure_class"] in {
                "java.util.concurrent.TimeoutException",
                "java.util.concurrent.ExecutionException",
                "org.apache.kafka.common.errors.TimeoutException",
            }
            diagnostic = load_json(runtime.control / identifier / "broker-drain-error.json")
            assert diagnostic["injected"] is False
            assert "io.detectbridge.archive.Main.topicState" in diagnostic["stack"]
            assert "io.detectbridge.archive.ManagedMain.consume" in diagnostic["stack"]
        else:
            raise AssertionError("paused Kafka did not cause a broker operation failure")
    finally:
        stack.compose("unpause", "kafka", profile="core")
    assert offsets() == before_offsets
    assert runtime.invoke("inspect", runtime.archive)["durable_next"] == before_durable
    runtime.invoke("drain", runtime.archive, identifier, operation=identifier)
    recovered = runtime.folder / "outage-recovered-wire.json"
    runtime.invoke("wire", runtime.archive, TOPICS[0], str(pending["offset"]), recovered)
    assert load_json(recovered)["value"] == pending_row["value"]
    assert offsets()[TOPICS[0]] == pending["offset"] + 1
    cases.append("actual_kafka_pause_named_broker_failure_unchanged_watermarks_and_exact_resume")
    initialization_qualification(runtime, registry, sha(provenance), cases, stage)
    pressure_qualification(runtime, registry, sha(provenance), cases, stage)


def pressure_qualification(parent, registry, provenance, cases, stage):
    """Use a stricter valid creator cap through E5; never increase the managed cap to pass."""
    stage("actual_lower_creator_cap_admission_refusal_and_maintenance_headroom")
    runtime = Runtime(parent.folder / "pressure", parent.bundle, parent.network)
    observed = parent.invoke("inspect", parent.archive, "--broker")
    starts = {topic: observed["partitions"][topic]["end"] for topic in TOPICS}
    first = starts[TOPICS[0]]
    request = runtime.folder / "legacy-init.json"
    save(
        request,
        dict(
            starts=starts, provenance=[provenance], limits=dict(LIMITS, archive_bytes=80 * 1024**2)
        ),
    )
    legacy = runtime.folder / "legacy"
    runtime.invoke(
        "init", legacy, "kafka:9092", request, registry, role="legacy", source_roots=[registry]
    )
    runs = [str(uuid.uuid4()), str(uuid.uuid4())]
    admissions = runtime.folder / "admissions.json"
    for batch in range(3):
        rows: list[dict[str, Any]] = []
        for _ in range(2):
            value = history.encoded(
                dict(
                    version="1.0.0",
                    kind="run_end",
                    run_id=runs[batch // 2],
                    control_id=str(uuid.uuid4()),
                    provenance=["original synthetic lower-cap fixture"],
                )
            )
            rows.append(
                dict(topic=TOPICS[0], key=None, value=base64.b64encode(value).decode(), headers=[])
            )
        save(admissions, rows)
        acknowledgements = runtime.invoke(
            "kafka", "publish", "kafka:9092", admissions, role="probe"
        )
        assert [ack["offset"] for ack in acknowledgements] == [
            first + batch * 2,
            first + batch * 2 + 1,
        ]
        runtime.invoke("drain", legacy, role="legacy")
    original = hashes(legacy)
    creator = history.verified(legacy / "archive.json")
    assert creator["limits"]["archive_bytes"] == 80 * 1024**2
    assert creator["limits"]["reserve_bytes"] == 128 * 1024**2
    topic = next(topic for topic in creator["topics"] if topic["name"] == TOPICS[0])
    source_partition = legacy / "segments" / topic["id"] / "0"
    assert sorted(int(path.name) for path in source_partition.iterdir()) == [
        first,
        first + 2,
        first + 4,
    ]
    expected_anchor = sha(
        history.encoded(history.verified(source_partition / str(first + 2) / "segment.json"))
    )
    save(
        runtime.folder / "original-before-managed.json",
        dict(
            files=original,
            creator_sha256=sha(history.encoded(creator)),
            expected_anchor=expected_anchor,
        ),
    )
    runtime.clone(legacy)
    protected = {
        name: hashes(runtime.archive / name) for name in ("segments", "objects", "maintenance")
    }
    value = history.encoded(
        dict(
            version="1.0.0",
            kind="run_end",
            run_id=str(uuid.uuid4()),
            control_id=str(uuid.uuid4()),
            provenance=["original synthetic visible backlog"],
        )
    )
    save(
        admissions,
        [dict(topic=TOPICS[0], key=None, value=base64.b64encode(value).decode(), headers=[])],
    )
    pending = runtime.invoke("kafka", "publish", "kafka:9092", admissions, role="probe")[0]
    assert pending["offset"] == first + 6
    runtime.invoke("drain", runtime.archive, str(uuid.uuid4()), expected="managed_admission_budget")
    assert protected == {name: hashes(runtime.archive / name) for name in protected}
    assert not list(runtime.archive.glob(".partial-*"))
    before = runtime.invoke("inspect", runtime.archive, "--broker")
    partition = before["partitions"][TOPICS[0]]
    assert (
        partition["durable_next"] == first + 6
        and partition["end"] == first + 7
        and partition["lag"] == 1
    )
    assert partition["committed_next"] is None or partition["committed_next"] <= first + 6
    plan, catalog, operation = runtime.plan(first + 4, 1234567890)
    assert load_json(plan)["candidates"][1]["segment_sha256"] == expected_anchor
    runtime.invoke("retire", runtime.archive, plan, catalog, operation, operation=operation)
    after = runtime.invoke("inspect", runtime.archive, "--broker")
    assert after["retained_floor"][TOPICS[0]] == first + 4
    assert (
        after["durable_next"][TOPICS[0]] == first + 6 and after["partitions"][TOPICS[0]]["lag"] == 1
    )
    assert hashes(legacy) == original
    save(
        runtime.folder / "pressure-report.json",
        dict(
            creator_archive_bytes=80 * 1024**2,
            reserve_bytes=128 * 1024**2,
            before=before,
            after=after,
            original_source_unchanged=True,
        ),
    )
    cases.append(
        "actual_lower_creator_cap_admission_refusal_visible_backlog_and_durable_retirement"
    )


def initialization_qualification(runtime, registry, provenance, cases, stage):
    from archive_maintenance import initialize

    original_container = Operation.container
    for phase in ("before_managed_publication", "after_managed_publication"):
        stage("actual_initialization_process_crash_" + phase)
        parent = runtime.folder / ("initialization-" + phase)
        parent.mkdir()
        archive, catalog, control = (parent / name for name in ("archive", "catalog", "control"))
        managed, operation = str(uuid.uuid4()), str(uuid.uuid4())
        args = (
            runtime.network.removesuffix("_internal"),
            archive,
            catalog,
            control,
            registry,
            {topic: 0 for topic in TOPICS},
            [provenance],
            managed,
            operation,
        )

        def crash(owned, *arguments, **kwargs):
            kwargs["crash"] = phase
            return original_container(owned, *arguments, **kwargs)

        with patch.object(Operation, "container", crash):
            try:
                initialize(*args)
            except StackError:
                failures = list((control / operation).glob("failure-*.json"))
                assert len(failures) == 1 and load_json(failures[0])["exit_code"] == 86
            else:
                raise AssertionError("initialization crash marker was not observed")
        assert archive.exists() == (phase == "after_managed_publication")
        before = digest(control / "initialization.json"), digest(catalog / "catalog.json")
        identities = control.stat().st_ino, catalog.stat().st_ino
        initialize(*args)
        assert not (parent / (".archive-managed-" + operation)).exists()
        assert before == (digest(control / "initialization.json"), digest(catalog / "catalog.json"))
        assert identities == (control.stat().st_ino, catalog.stat().st_ino)
        assert history.verified(archive / "maintenance/registration.json")["managed_id"] == managed
        cases.append("actual_initialization_crash_identical_retry_owned_cleanup_" + phase)


def storage_qualification(runtime, frozen, cases, stage):
    """Fixed fault-only tmpfs; production/archive caps and normal /tmp remain unchanged."""
    stage("actual_full_tmpfs_archive_write_and_injected_metadata_sync_eio")
    packet = runtime.folder / "storage-packet.json"
    save(packet, frozen)
    with Operation(runtime.control, runtime.managed, str(uuid.uuid4())) as owned:
        owned.reserve(64 * 1024)
        marker = owned.folder / "helper.active"
        assert not marker.exists()
        history.write(marker, history.encoded(owned.owner) + b"\n")
        history.sync(owned.folder)
        # Operation.container's immutable resource profile stays untouched. This executable
        # qualification helper adds only one explicitly bounded, isolated fault filesystem.
        command = [
            "docker",
            "create",
            "--rm",
            "--log-driver=none",
            "--pull=never",
            "--name",
            owned.name,
            "--label",
            "io.detectbridge.managed.operation=" + owned.id,
            "--label",
            "io.detectbridge.managed.instance=" + owned.managed,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=128",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16777216",
            "--tmpfs",
            "/fault:rw,noexec,nosuid,size=201326592,mode=1777",
            "--mount",
            f"type=bind,source={BUILDS.resolve()},target=/artifacts,readonly",
            "--mount",
            f"type=bind,source={packet},target=/fixture.json,readonly",
            "--mount",
            f"type=bind,source={owned.folder},target=/diagnostics",
            runtime.bundle["image"],
            "java",
            "-Xmx128m",
            "-cp",
            "/artifacts/" + runtime.bundle["managed"] + ":/artifacts/" + runtime.bundle["probe"],
            "io.detectbridge.archive.ManagedProbe",
            "storage-faults",
            "/fixture.json",
            "/diagnostics",
        ]
        try:
            created = owned.execute(command, 90).stdout.decode().strip()
            assert re.fullmatch("[a-f0-9]{64}", created)
            response = owned.execute(["docker", "start", "-a", created], 90)
        finally:
            owned.stop_orphan()
        result = json.loads(response.stdout.decode().splitlines()[-1])
        assert result["status"] == "ok"
        observed = result["result"]
        assert observed["filesystem_bytes"] == 192 * 1024**2
        assert observed["reserve_bytes"] == 128 * 1024**2
        assert observed["physical_disk_loss_qualified"] is False
        assert len(observed["cases"]) == 2
        for outcome in observed["cases"]:
            assert outcome["before_next"] == 6 and outcome["after_next"] == 8
            cases.append(outcome["case"])
        save(runtime.folder / "storage-report.json", observed)


def retirement_midwrite_qualification(base, bundle, frozen, cases, stage):
    phases = (
        "during_retirement_plan",
        "before_retirement_plan_sync",
        "during_retirement_record",
        "before_retirement_record_sync",
    )
    for phase in phases:
        stage("actual_process_crash_" + phase)
        runtime = Runtime(base / phase, bundle)
        packet, source = runtime.folder / "frozen.json", runtime.folder / "legacy"
        save(packet, frozen)
        runtime.invoke("fixture", packet, source, role="probe")
        source_before = hashes(source)
        runtime.clone(source)
        protected = {name: hashes(runtime.archive / name) for name in ("segments", "objects")}
        plan, catalog, operation = runtime.plan(4, 100)
        runtime.invoke(
            "retire",
            runtime.archive,
            plan,
            catalog,
            operation,
            operation=operation,
            crash=phase,
            expected="crash",
        )
        before = runtime.invoke("inspect", runtime.archive)
        assert before["retained_floor"][TOPICS[0]] == 0 and before["durable_next"][TOPICS[0]] == 6
        assert not (runtime.archive / "maintenance/retirements/00000000000000000001").exists()
        assert protected == {name: hashes(runtime.archive / name) for name in protected}
        runtime.invoke("retire", runtime.archive, plan, catalog, operation, operation=operation)
        runtime.invoke("retire", runtime.archive, plan, catalog, operation, operation=operation)
        after = runtime.invoke("inspect", runtime.archive)
        assert after["retained_floor"][TOPICS[0]] == 4 and after["durable_next"][TOPICS[0]] == 6
        assert after["retirement_sequence"] == 1
        assert hashes(runtime.archive / "objects") == protected["objects"]
        remaining = hashes(runtime.archive / "segments")
        assert remaining == {
            name: value
            for name, value in protected["segments"].items()
            if name.startswith("topic-0/0/4/")
        }
        assert hashes(source) == source_before
        cases.append("actual_midwrite_process_crash_same_operation_resume_" + phase)


def unknown_graph_qualification(runtime, frozen, cases, stage):
    stage("actual_unknown_future_graph_blocks_partial_retirement")
    packet, source = runtime.folder / "frozen.json", runtime.folder / "legacy"
    save(packet, frozen)
    runtime.invoke("fixture", packet, source, role="probe")
    source_before = hashes(source)
    runtime.clone(source)
    selected = json.loads(base64.b64decode(frozen["legacy"]["segments"][0]["rows"][0]["value"]))[
        "run_id"
    ]
    future = dict(
        version="99.0.0",
        processing_id="sha256:" + "b" * 64,
        diagnostic=dict(future_reference=selected),
    )
    topic = TOPICS[3]
    config = frozen["legacy"]["configuration"]
    descriptor = next(value for value in config["topics"] if value["name"] == topic)
    wire = dict(
        version="1.0.0",
        topic=topic,
        topic_id=descriptor["id"],
        partition=0,
        offset=0,
        timestamp=100,
        timestamp_type="CreateTime",
        key=None,
        value=base64.b64encode(history.encoded(future)).decode(),
        headers=[],
        dependencies=config["objects"],
        category="derived",
    )
    wire["id"] = "sha256:" + sha(
        history.encoded(
            ["detectbridge.archive.wire/1", config["cluster"], descriptor["id"], "0", "0"]
        )
    )
    wire_path = runtime.folder / "future-wire.json"
    save(wire_path, wire)
    runtime.invoke("append-wire", runtime.archive, wire_path, str(uuid.uuid4()), role="probe")
    protected = hashes(runtime.archive)
    runtime.plan(4, 100, expected="managed_unknown_graph_blocker")
    assert hashes(runtime.archive) == protected
    complete, _, _ = runtime.plan({TOPICS[0]: 6, topic: 1}, 200)
    assert sum(candidate["unknown_graph"] for candidate in load_json(complete)["candidates"]) == 1
    assert hashes(source) == source_before
    cases.append("actual_retained_unknown_future_version_reference_blocks_partial_retirement")


def p05_qualification(runtime, cases, stage):
    """Injected schema-bound test catalog; none of these bytes claim upstream dataset identity."""
    import p05_archive
    import replay
    from check_datasets import load_catalog

    stage("actual_completed_p05_synthetic_import_and_semantic_restore")
    manifest = copy.deepcopy(load_catalog()["linux-audit-whoami"])
    manifest["id"] = "synthetic-p05-maintenance"
    manifest["terms"]["attribution"] = (
        "Original DetectBridge synthetic eight-byte fixture, Apache-2.0"
    )
    manifest["terms"]["review_notes"] = (
        "Injected test catalog preserving the frozen upstream schema shape; payload/provenance are synthetic, not downloaded upstream originals."
    )
    manifest["capture"]["author"] = "DetectBridge synthetic qualification"
    manifest["capture"]["source_format"] = "Literal eight-byte synthetic LF framing fixture"
    manifest["framing"]["record_count"] = 4
    reviewed = {manifest["id"]: manifest}
    cache, runs = runtime.folder / "p05-cache", runtime.folder / "p05-runs"
    body = bytes.fromhex("410d0a0ac3a90a5a")

    def put(resource, value):
        resource.update(sha256=sha(value), size_bytes=len(value))
        path = replay.object_path(cache, resource)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    put(manifest["payload"], body)
    for resource in manifest["provenance"]:
        value = (
            (ROOT / "LICENSE").read_bytes()
            if resource["role"] == "license"
            else history.encoded(dict(origin="Original synthetic qualifier", role=resource["role"]))
        )
        if resource["role"] == "lfs_pointer":
            value = f"version https://git-lfs.github.com/spec/v1\noid sha256:{sha(body)}\nsize 8\n".encode()
        put(resource, value)
    run_id = replay.start(
        list(reviewed),
        catalog=reviewed,
        runs=runs,
        captures=runtime.folder / "p05-captures",
        data_cache=cache,
        rate=None,
    )["run_id"]
    original = runs / run_id
    before = hashes(original), hashes(cache)
    identifier = str(uuid.uuid4())
    with Operation(runtime.control, runtime.managed, identifier) as owned:
        derived = owned.folder / "derived"
        with p05_archive.source(
            original, cache, runtime.managed, derived, reviewed_catalog=reviewed
        ) as prepared:
            metadata = prepared.metadata
            assert (
                metadata["record_count"],
                metadata["envelope_count"],
                metadata["segment_count"],
            ) == (4, 6, 1)
            framing = load_json(prepared.sources["index/framing.json"])
            assert [
                (r["offset"], r["length"]) for r in framing["datasets"][0]["framing"]["records"]
            ] == [(0, 3), (3, 1), (4, 3), (7, 1)]
    client = ManagedArchive(runtime.archive, runtime.catalog, runtime.control)
    assert (
        client.import_p05(str(uuid.uuid4()), original, cache, reviewed_catalog=reviewed) == metadata
    )
    assert (hashes(original), hashes(cache)) == before
    restored_parent = runtime.folder / "restored-p05-runs"
    restored_parent.mkdir()
    restored = restored_parent / run_id
    restored_cache = runtime.folder / "restored-p05-cache"
    with client.session(str(uuid.uuid4())) as session:
        assert session.restore_p05(
            metadata["id"], restored, restored_cache, reviewed_catalog=reviewed
        )["restored"]
        restored_index = session.operation.folder / "restored-index"
    p05_archive.validate_restored(
        restored, restored_cache, metadata, restored_index, reviewed_catalog=reviewed
    )
    assert hashes(restored) == {
        name: value for name, value in hashes(original).items() if name != ".run.lock"
    }
    cases.append(
        "actual_completed_p05_injected_test_catalog_import_exact_framing_and_semantic_restore"
    )
    from archive_maintenance_faults import qualify_import_retirement

    qualify_import_retirement(runtime, metadata, cases, stage)


def sealed_qualification(runtime, cases, stage):
    """Actual accepted producer and sealed managed historical replay; not Kafka delivery."""
    import current_replay
    import historical_fixtures
    from current_replay_cases import prepare_plan
    from current_replay_cases import request as current_request
    from current_replay_verify import check_current
    from historical_verify import semantic_check
    from integration_cases import prepare

    stage("actual_pinned_producer_and_managed_sealed_selection")
    prepare()
    plan = ROOT / ".cache/integration/plan.json"
    profiles = runtime.folder / "profiles"
    profiles.mkdir()
    historical_build, current_build = profiles / "historical", profiles / "current"
    for folder, executor in ((historical_build, "historical"), (current_build, "current")):
        folder.mkdir()
        for role in ("producer", "reader", executor):
            shutil.copyfile(BUILDS / runtime.bundle[role], folder / runtime.bundle[role])
        save(
            folder / "bundle.json",
            dict(
                executor=runtime.bundle[executor],
                producer=runtime.bundle["producer"],
                reader=runtime.bundle["reader"],
                image=runtime.bundle["image"],
            ),
        )
    source_folder = runtime.folder / "source"
    source_folder.mkdir()

    def adapter(owned):
        def execute(image, mounts, args, timeout=90):
            return owned.container(image, mounts, args, timeout=timeout)

        return execute

    with Operation(runtime.control, runtime.managed, str(uuid.uuid4())) as owned:
        with (
            patch.object(historical_fixtures, "BUILDS", historical_build),
            patch.object(historical_fixtures, "container", adapter(owned)),
        ):
            units = historical_fixtures.original(source_folder, plan)
            archive, request = historical_fixtures.archive_fixture(source_folder, units, plan)
    # The independent fixture omits advisory/lease files; create only the empty lease file.
    (archive / ".lock").touch()
    before = hashes(archive)
    runtime.clone(archive)
    assert hashes(archive) == before
    current_h, current_c = history.BUILDS, current_replay.BUILDS
    with (
        patch.object(history, "BUILDS", historical_build),
        patch.object(current_replay, "BUILDS", current_build),
        ManagedArchive(runtime.archive, runtime.catalog, runtime.control).session(
            str(uuid.uuid4())
        ) as session,
    ):
        with session.replay_profile() as profile:
            selected = profile.seal(request, plan)["selection_sha256"]
            for _ in range(2):
                run_id = str(uuid.uuid4())
                profile.historical(selected, run_id)
                semantic_check(runtime.catalog, units, load_json(plan), run_id)
    assert history.BUILDS == current_h and current_replay.BUILDS == current_c
    stage("actual_managed_current_regroup_timeout_and_interrupted_resume")
    historical_request = load_json(request)
    labels = {"audit_timeout", "late", "auth"}
    filtered = dict(
        historical_request,
        units=[unit for unit in historical_request["units"] if unit["id"] in labels],
    )
    filtered_units = [unit for unit in units if unit["label"] in labels]
    assert {unit["id"] for unit in filtered["units"]} == labels
    filtered_path = runtime.folder / "current-historical-request.json"
    save(filtered_path, filtered)
    new_plan_path = runtime.folder / "current-new-plan.json"
    new_plan = prepare_plan(new_plan_path)
    protected_archive = hashes(runtime.archive)
    with (
        patch.object(history, "BUILDS", historical_build),
        patch.object(current_replay, "BUILDS", current_build),
        ManagedArchive(runtime.archive, runtime.catalog, runtime.control).session(
            str(uuid.uuid4())
        ) as session,
    ):
        current_selection = session.seal(filtered_path, plan)["selection_sha256"]
    client = ManagedArchive(runtime.archive, runtime.catalog, runtime.control)

    class InterruptedCurrent(Exception):
        pass

    for case in ("regroup", "timeout"):
        spec = current_request(current_selection, filtered, digest(new_plan_path), case=case)
        request_path = runtime.folder / ("current-" + case + ".json")
        save(request_path, spec)
        workspace = runtime.folder / ("current-workspace-" + case)
        run_id, operation = str(uuid.uuid4()), str(uuid.uuid4())
        with (
            patch.object(history, "BUILDS", historical_build),
            patch.object(current_replay, "BUILDS", current_build),
        ):
            if case == "regroup":
                armed = False

                def interrupt(phase):
                    nonlocal armed
                    if phase == "during_payload":
                        armed = True
                    if armed and phase == "after_publication":
                        raise InterruptedCurrent("first actual step publication")

                with patch.object(history, "HOOK", interrupt):
                    try:
                        with client.session(operation) as session:
                            session.current(workspace, request_path, new_plan_path, run_id)
                    except InterruptedCurrent:
                        pass
                    else:
                        raise AssertionError("current interruption was not observed")
                completed = workspace / "runs" / run_id / "units"
                prefix = hashes(completed)
                assert len(list(completed.glob("*/commit.json"))) == 1
                with client.session(operation) as session:
                    session.current(workspace, request_path, new_plan_path, run_id, resume=True)
                resumed = hashes(completed)
                assert all(resumed[name] == value for name, value in prefix.items())
            else:
                with client.session(operation) as session:
                    session.current(workspace, request_path, new_plan_path, run_id)
        check_current(workspace, run_id, new_plan, filtered_units, filtered, spec, case)
        assert protected_archive == hashes(runtime.archive)
        cases.append("actual_managed_current_frozen_oracle_" + case)
    assert history.BUILDS == current_h and current_replay.BUILDS == current_c
    cases.append("actual_managed_current_same_operation_resume_preserves_first_committed_step")
    selection = history.verified(runtime.catalog / "pins" / selected / "selection.json")
    assert selection["reader_sha256"] == runtime.bundle["managed"]
    assert selection["executor_sha256"] == PINS["historical"]
    assert selection["request"]["producer_sha256"] == PINS["producer"]
    heads = runtime.invoke("inspect", runtime.archive)["durable_next"]
    runtime.plan(
        {topic: next for topic, next in heads.items() if next},
        9223372036854775807,
        expected="managed_pin_blocker",
    )
    cases.extend(
        [
            "actual_pinned_producer_managed_selection_and_two_isolated_historical_oracle_replays",
            "actual_verified_sealed_selection_blocks_whole_wire_population_retirement",
        ]
    )


def qualify():
    bundle = load_json(BUILDS / "bundle.json")
    assert bundle["image"] == PINS["image"]
    for role in ("managed", "probe", "reader", "historical", "current", "producer"):
        assert digest(BUILDS / bundle[role]) == bundle[role]
    assert verify_managed(BUILDS / bundle["managed"]) == bundle["managed"]
    image = ensure_image(ROOT / ".cache/archive-maintenance-bootstrap" / uuid.uuid4().hex)
    project = "detectbridge-p14-managed-" + uuid.uuid4().hex[:12]
    folder = CACHE / project
    folder.mkdir(parents=True, mode=0o700)
    stack = Stack(project)
    report = dict(
        status="running",
        project=project,
        bundle=bundle,
        phase="initialization",
        cases=[],
        platform="linux/" + image["Architecture"],
        image_id=image["Id"],
        source_revision=run(["git", "rev-parse", "HEAD"]).stdout.strip(),
        host_platform=platform.system() + "/" + platform.machine(),
        tools_sha256={
            name: digest(ROOT / "tools" / name)
            for name in (
                "archive_maintenance.py",
                "archive_maintenance_verify.py",
                "archive_maintenance_faults.py",
                "managed_replay.py",
                "historical_fixtures.py",
                "historical_verify.py",
            )
        },
        historical_probe_sha256=digest(
            ROOT / "packages/historical-replay/build/libs/historical-probe.jar"
        ),
    )
    path = REPORTS / (project + ".json")
    REPORTS.mkdir(parents=True, exist_ok=True)

    def stage(phase):
        report["phase"] = phase
        save(path, report)
        print(json.dumps(dict(project=project, phase=phase)), flush=True)

    with project_lock(project):
        initialized = False
        try:
            frozen = load_json(ROOT / "contracts/archive-maintenance/v1/fixtures/expectations.json")
            fixture_runtime = Runtime(folder / "fixture", bundle)
            fixture_qualification(fixture_runtime, frozen, report["cases"], stage)
            # Reuse that verified managed instance for a completed P05 closure, independently of Kafka.
            p05_qualification(fixture_runtime, report["cases"], stage)
            storage_qualification(
                Runtime(folder / "storage", bundle), frozen, report["cases"], stage
            )
            from archive_maintenance_faults import qualify_faults

            qualify_faults(Runtime, folder / "faults", bundle, frozen, report["cases"], stage)
            retirement_midwrite_qualification(
                folder / "midwrite", bundle, frozen, report["cases"], stage
            )
            unknown_graph_qualification(
                Runtime(folder / "unknown-graph", bundle), frozen, report["cases"], stage
            )
            sealed_qualification(Runtime(folder / "sealed", bundle), report["cases"], stage)
            stack.init("core")
            initialized = True
            stack.compose("up", "-d", "--wait", "kafka", profile="core", timeout=180)
            kafka_qualification(
                Runtime(folder / "kafka", bundle, project + "_internal"), report["cases"], stage
            )
            report.update(
                status="passed",
                phase="complete",
                platform="linux/" + image["Architecture"],
                image_id=image["Id"],
            )
            report["limits"] = dict(
                p05_semantic_import="synthetic injected test catalog only; no claim these are upstream dataset bytes",
                private_originals="not exercised by synthetic qualifier",
            )
            return report
        except BaseException as error:
            report.update(status="failed", failure_class=type(error).__name__)
            save(
                folder / "failure-exception.json",
                dict(failure_class=type(error).__name__, traceback=traceback.format_exc()[:65536]),
            )
            save(
                path, report
            )  # Persist the actual phase before removing this project's infrastructure.
            raise
        finally:
            save(path, report)
            if initialized:
                stack.compose("down", "-v", "--remove-orphans", profile="core", check=False)


if __name__ == "__main__":
    try:
        print(json.dumps(qualify(), sort_keys=True))
    except Exception as error:
        print(json.dumps(dict(status="failed", failure_class=type(error).__name__)))
        raise SystemExit(1) from None
