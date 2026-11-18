"""Independent synthetic actual-Kafka and filesystem interruption qualification."""

import base64
import gzip
import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from archive import LIMITS, TOPICS, Archive, ArchiveFailure
from check_archive import require
from check_contracts import load_json
from stack import ROOT, StackError, run, save


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def verify_archive(folder, expected):
    """Read gzip/NDJSON independently, compare exact frozen producer inputs and location IDs."""
    assert (folder / "archive.sha256").read_text() == sha(
        (folder / "archive.json").read_bytes()
    ) + "\n"
    config = load_json(folder / "archive.json")
    require("configuration", config)
    seen = {}
    for topic in config["topics"]:
        directory = folder / "segments" / topic["id"] / "0"
        if not directory.exists():
            continue
        for segment in sorted(directory.iterdir(), key=lambda p: int(p.name)):
            assert (segment / "segment.sha256").read_text() == sha(
                (segment / "segment.json").read_bytes()
            ) + "\n"
            meta = load_json(segment / "segment.json")
            require("segment", meta)
            zipped = (segment / "records.ndjson.gz").read_bytes()
            raw = gzip.decompress(zipped)
            assert sha(zipped) == meta["payload"]["compressed_sha256"]
            assert sha(raw) == meta["payload"]["uncompressed_sha256"]
            rows = [json.loads(line) for line in raw.splitlines()]
            assert len(rows) == meta["payload"]["rows"]
            for row in rows:
                require("wire", row)
                location = (row["topic"], row["offset"])
                assert location not in seen
                original = expected[location]
                for key in ("key", "value", "headers"):
                    assert row[key] == original[key], key
                assert row["timestamp"] == 1234567890
                assert row["id"] == "sha256:" + sha(
                    canonical(
                        [
                            "detectbridge.archive.wire/1",
                            config["cluster"],
                            topic["id"],
                            "0",
                            str(row["offset"]),
                        ]
                    )
                )
                seen[location] = row
    assert set(seen) == set(expected)
    return seen


def qualify():
    project = "detectbridge-p14-test-" + uuid.uuid4().hex[:12]
    archive = Archive(project)
    stack = archive.stack
    report: dict[str, Any] = dict(
        project=project,
        status="running",
        phase="setup",
        cases=[],
        bundle=archive.bundle,
        tools={
            name: sha((ROOT / "tools" / name).read_bytes())
            for name in ("archive.py", "archive_verify.py")
        },
    )
    path = ROOT / ".cache/archive-reports" / (project + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = {}
    original = bytes.fromhex("410d0a0ac3a90a5a")
    provenance = canonical(
        dict(origin="Original synthetic DetectBridge eight-byte vector", license="Apache-2.0")
    )
    registry = archive.folder / "original-registry"
    registry.mkdir()
    for data in (original, provenance):
        (registry / sha(data)).write_bytes(data)
    cases: list[str] = report["cases"]

    def publish(rows, transaction=False):
        # Freeze exact bytes before publication; acknowledgements add only actual physical locations.
        save(archive.folder / "admissions.json", rows)
        acknowledgements = archive.command(
            "transaction" if transaction else "publish",
            "kafka:9092",
            "/work/admissions.json",
            probe=True,
        )
        for row, ack in zip(rows, acknowledgements, strict=True):
            assert ack["value_sha256"] == (
                None if row["value"] is None else sha(base64.b64decode(row["value"]))
            )
            expected[(ack["topic"], ack["offset"])] = row
        save(
            archive.folder / "expected-locations.json",
            [dict(r, offset=o) for (t, o), r in expected.items()],
        )

    def row(topic, data):
        return dict(
            topic=topic,
            key=None,
            value=None if data is None else base64.b64encode(data).decode(),
            headers=[dict(name="duplicate", value="AA=="), dict(name="duplicate", value=None)],
        )

    def offsets():
        group = load_json(archive.folder / "archive/archive.json")["group"]
        return archive.command("offsets", "kafka:9092", group, probe=True)

    try:
        stack.init("core")
        stack.compose("up", "-d", "--wait", "kafka", profile="core", timeout=180)
        assert archive.command("init", "kafka:9092", probe=True)["created"] == 9
        assert archive.command("init", "kafka:9092", probe=True)["created"] == 0
        report["phase"] = "freeze_and_initial_roundtrip"
        # Exact opaque originals, null/empty, two equal bodies at different locations, all nine topics.
        exact_json = canonical(
            dict(
                signed=[-9223372036854775808, 9007199254740993, 9223372036854775807],
                source_time="2020-01-01T00:00:00.123456789012Z",
                text="é",
            )
        )
        reference = canonical(
            dict(
                kind="record",
                raw=dict(
                    record_id="sha256:" + "1" * 64,
                    evidence=dict(
                        sha256=sha(original[:3]),
                        reference=dict(
                            object_sha256=sha(original), byte_range=dict(offset=0, length=3)
                        ),
                    ),
                ),
                context=dict(
                    run_id="00000000-0000-4000-8000-000000000002",
                    source="synthetic",
                    host_binding="explicit-synthetic-context",
                ),
            )
        )
        publish(
            [row(t, original) for t in TOPICS]
            + [
                row(TOPICS[0], None),
                row(TOPICS[0], b""),
                row(TOPICS[0], original),
                row(TOPICS[0], exact_json),
                row(TOPICS[0], reference),
            ]
        )
        archive.init(registry, {t: 0 for t in TOPICS}, [sha(provenance)])
        result = archive.command("drain", "/work/archive")
        verify_archive(archive.folder / "archive", expected)
        assert result["result"]["historical_ready"] is False
        archive.command("object", "/work/archive", sha(original), "/work/retrieved.bin")
        assert (archive.folder / "retrieved.bin").read_bytes() == original
        cases.append("nine_topic_exact_bytes_null_empty_headers_and_object_retrieval")
        for phase in (
            "during_payload",
            "after_payload",
            "during_metadata",
            "after_metadata",
            "before_rename",
            "after_rename",
            "after_directory_sync",
            "before_kafka_commit",
            "after_kafka_commit",
        ):
            report["phase"] = "process_crash_" + phase
            publish([row(TOPICS[0], original)])
            try:
                archive.command("drain", "/work/archive", crash=phase)
            except StackError as error:
                assert "86" in str(error), str(error)
            else:
                raise AssertionError("missing actual process crash")
            durable = archive.command("inspect", "/work/archive")["result"]["durable_next"]
            committed = offsets()
            assert all(committed[t] is None or committed[t] <= durable[t] for t in TOPICS)
            wanted = max(o for (t, o) in expected if t == TOPICS[0]) + 1
            if phase in (
                "after_rename",
                "after_directory_sync",
                "before_kafka_commit",
                "after_kafka_commit",
            ):
                assert durable[TOPICS[0]] == wanted
            else:
                assert durable[TOPICS[0]] == wanted - 1
            if phase == "after_kafka_commit":
                assert committed[TOPICS[0]] == wanted
            else:
                assert committed[TOPICS[0]] < wanted
            archive.command("drain", "/work/archive")
            verify_archive(archive.folder / "archive", expected)
            cases.append("process_crash_" + phase)
            save(path, report)
        report["phase"] = "transaction_control_offset_gap"
        publish([row(TOPICS[0], original) for _ in range(4)], transaction=True)
        archive.command("drain", "/work/archive")
        verify_archive(archive.folder / "archive", expected)
        cases.append("actual_transaction_control_offset_gap_without_fabricated_records")
        for index, phase in enumerate(
            (
                "during_payload",
                "after_payload",
                "during_metadata",
                "before_rename",
                "after_rename",
                "after_directory_sync",
            )
        ):
            report["phase"] = "object_publication_crash_" + phase
            root = "/work/object-fault-" + str(index)
            try:
                archive.command(
                    "init", root, "kafka:9092", "/work/request.json", "/work/registry", crash=phase
                )
            except ArchiveFailure as error:
                assert error.exit_code == 86
            else:
                raise AssertionError("object publication did not terminate")
            archive.command("register", root, "/work/registry")
            archive.command("object", root, sha(original), "/work/object-retrieved-" + str(index))
            assert (archive.folder / ("object-retrieved-" + str(index))).read_bytes() == original
            cases.append("object_publication_crash_" + phase)
        report["phase"] = "actual_group_reassignment"
        publish([row(TOPICS[0], original)])
        marker = archive.folder / "pause.marker"
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(archive.command, "drain", "/work/archive", pause=True)
            deadline = time.monotonic() + 40
            while not marker.exists() and time.monotonic() < deadline and not future.done():
                time.sleep(0.1)
            assert marker.exists(), "archive never reached paused durable publication"
            group = load_json(archive.folder / "archive/archive.json")["group"]
            assigned = archive.command("join", "kafka:9092", group, probe=True)
            assert assigned["assigned"] > 0
            try:
                future.result(timeout=60)
            except ArchiveFailure as error:
                assert error.category in ("kafka_commit_failed", "assignment_changed")
            # If both members completed a valid handoff, the successful commit is also legal.
        durable = archive.command("inspect", "/work/archive")["result"]["durable_next"]
        assert all(v is None or v <= durable[t] for t, v in offsets().items())
        archive.command("drain", "/work/archive")
        verify_archive(archive.folder / "archive", expected)
        cases.append("actual_group_reassignment_preserves_durable_commit_boundary")
        report["phase"] = "missing_required_object"
        publish([row(TOPICS[0], original)])
        object_payload = archive.folder / "archive/objects" / sha(original) / "bytes.ndjson.gz"
        retained_object = object_payload.read_bytes()
        before_missing = offsets()
        object_payload.unlink()
        try:
            try:
                archive.command("drain", "/work/archive")
            except ArchiveFailure as error:
                assert error.category == "archive_contents"
            else:
                raise AssertionError("missing object accepted")
        finally:
            object_payload.write_bytes(retained_object)
        assert offsets() == before_missing
        archive.command("drain", "/work/archive")
        verify_archive(archive.folder / "archive", expected)
        cases.append("actual_missing_required_object_backlog_and_recovery")
        report["phase"] = "actual_filesystem_permission_failure"
        publish([row(TOPICS[0], original)])
        config = load_json(archive.folder / "archive/archive.json")
        topic = next(t for t in config["topics"] if t["name"] == TOPICS[0])
        destination = archive.folder / "archive/segments" / topic["id"] / "0"
        before_permission = offsets()
        destination.chmod(0o500)
        try:
            try:
                archive.command("drain", "/work/archive")
            except ArchiveFailure as error:
                assert error.exit_code == 1
                assert error.failure_class == "java.nio.file.AccessDeniedException"
            else:
                raise AssertionError("write permission failure not observed")
        finally:
            destination.chmod(0o700)
        assert offsets() == before_permission
        archive.command("drain", "/work/archive")
        verify_archive(archive.folder / "archive", expected)
        cases.append("actual_filesystem_permission_failure_and_recovery")
        report["phase"] = "broker_outage"
        before = offsets()
        stack.compose("pause", "kafka", profile="core")
        try:
            try:
                archive.command("drain", "/work/archive", timeout=60)
            except StackError:
                pass
            else:
                raise AssertionError("missing broker outage failure")
        finally:
            stack.compose("unpause", "kafka", profile="core")
        assert offsets() == before
        archive.command("drain", "/work/archive")
        cases.append("actual_broker_outage_unchanged_offsets_and_recovery")
        report["phase"] = "corruption"
        segment = next((archive.folder / "archive/segments").glob("*/0/*/records.ndjson.gz"))
        retained = segment.read_bytes()
        segment.write_bytes(retained[:-1])
        try:
            archive.command("drain", "/work/archive")
        except ArchiveFailure as error:
            assert error.category == "compressed_integrity"
        else:
            raise AssertionError("corrupt segment accepted")
        # Restore test-induced corruption only; never repair production evidence automatically.
        segment.write_bytes(retained)
        assert offsets() == before
        cases.append("actual_committed_corruption_rejection")
        report["phase"] = "metadata_corruption"
        metadata = segment.parent / "segment.json"
        retained_metadata = metadata.read_bytes()
        changed = json.loads(retained_metadata)
        changed["next"] += 1
        metadata.write_bytes(canonical(changed) + b"\n")
        try:
            try:
                archive.command("drain", "/work/archive")
            except ArchiveFailure as error:
                assert error.category == "metadata_integrity"
            else:
                raise AssertionError("corrupt metadata accepted")
        finally:
            metadata.write_bytes(retained_metadata)
        assert offsets() == before
        cases.append("actual_metadata_offset_corruption_rejected")
        report["phase"] = "committed_ahead"
        group = load_json(archive.folder / "archive/archive.json")["group"]
        next_offset = archive.command("inspect", "/work/archive")["result"]["durable_next"][
            TOPICS[0]
        ]
        archive.command("advance", "kafka:9092", group, str(next_offset + 1), probe=True)
        try:
            archive.command("drain", "/work/archive")
        except ArchiveFailure as error:
            assert error.category == "committed_ahead_of_archive"
        else:
            raise AssertionError("ahead commit accepted")
        cases.append("actual_broker_commit_ahead_rejected")
        archive.command("advance", "kafka:9092", group, str(next_offset), probe=True)
        report["phase"] = "maximum_object_boundary"
        import random

        large = random.Random(14).randbytes(32 * 1024**2)
        large_registry = archive.folder / "large-registry"
        large_registry.mkdir()
        (large_registry / sha(large)).write_bytes(large)
        (large_registry / sha(provenance)).write_bytes(provenance)
        archive.command(
            "init",
            "/work/large-archive",
            "kafka:9092",
            "/work/request.json",
            "/work/large-registry",
        )
        archive.command("object", "/work/large-archive", sha(large), "/work/large-retrieved.bin")
        assert sha((archive.folder / "large-retrieved.bin").read_bytes()) == sha(large)
        cases.append("actual_32_mib_incompressible_object_boundary")
        report["phase"] = "topic_recreation"
        archive.command("recreate", "kafka:9092", probe=True)
        try:
            archive.command("drain", "/work/archive")
        except ArchiveFailure as error:
            assert error.category == "topic_changed"
        else:
            raise AssertionError("replaced topic adopted")
        cases.append("actual_topic_uuid_replacement_rejected")
        report.update(
            status="passed",
            phase="complete",
            occurrences=len(expected),
            bundle=archive.bundle,
            limits=LIMITS,
        )
        image = json.loads(run(["docker", "image", "inspect", stack.image("flink")]).stdout)[0]
        report["platform"] = image["Architecture"]
        report["image_id"] = image["Id"]
        return report
    except Exception as error:
        report.update(status="failed", failure_class=type(error).__name__)
        raise
    finally:
        save(path, report)
        # Never remove originals, ledgers or another project's resources.
        stack.compose("down", "-v", "--remove-orphans", profile="core", check=False)
