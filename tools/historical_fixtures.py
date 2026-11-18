"""Original synthetic qualification inputs; literal expectations precede replay code."""

import base64
import copy
import json
import struct
import uuid
import zlib
from typing import Any

from historical import BUILDS, INPUT, PRODUCER, ROOT, ROUTES, container, encoded, sha

PACKET = ROOT / "contracts/historical-replay/v1/fixtures/expectations.json"


def original(folder, plan, edges=False):
    """Run the actual accepted producer, independently checked against prior literal tables."""
    bundle = json.loads((BUILDS / "bundle.json").read_bytes())
    assert sha((BUILDS / PRODUCER).read_bytes()) == PRODUCER
    probe = ROOT / "packages/historical-replay/build/libs/historical-probe.jar"
    packet = json.loads(PACKET.read_bytes())
    from linux_assembly_cases import context, record, references

    digest, blob, refs = references()
    evidence = folder / "evidence"
    evidence.mkdir()
    (evidence / digest).write_bytes(blob)
    for i, row in enumerate(refs):
        row = copy.deepcopy(row)
        row["context"]["run_id"] = packet["inputs"]["auth"]["value"]["context"]["run_id"]
        label = "auth_range_" + str(i)
        packet["inputs"][label] = dict(value=row, sha256=sha(encoded(row)))
        packet["cases"].append(dict(id=label, inputs=[label], scenario="auth", events=1, matches=1))
    base = packet["inputs"]["auth"]["value"]
    variants = {
        "auth_empty": record("\n", 1900, context(True)),
        "auth_crlf": record(
            base["raw"]["evidence"]["inline"].removesuffix("\n") + "\r\n", 1901, context(True)
        ),
        "auth_precision": record(base["raw"]["evidence"]["inline"], 1902, context(True)),
    }
    precise = "2026-01-01T00:00:01.123456789012Z"
    variants["auth_precision"]["raw"]["first_observed"] = precise
    variants["auth_precision"]["context"]["first_observed"] = precise
    for label, row in variants.items():
        packet["inputs"][label] = dict(value=row, sha256=sha(encoded(row)))
        packet["cases"].append(
            dict(
                id=label,
                inputs=[label],
                scenario="auth",
                events=1 if label == "auth_precision" else 0,
                matches=1 if label == "auth_precision" else 0,
            )
        )
    assert refs[0]["raw"]["evidence"]["sha256"] == refs[1]["raw"]["evidence"]["sha256"]
    assert refs[0]["raw"]["record_id"] != refs[1]["raw"]["record_id"]
    if edges:
        from linux_assembly_cases import PARTS, audit

        for prefix, serial, parts, start in [
            ("end", "30", PARTS[:5], 3000),
            ("resource", "31", PARTS[:2], 3100),
        ]:
            for i, part in enumerate(parts):
                row = record(audit(part, serial), start + i)
                packet["inputs"][prefix + "_" + str(i)] = dict(value=row, sha256=sha(encoded(row)))
        trigger = record(audit(PARTS[2], "31"), 3102)
        packet["inputs"]["resource_trigger"] = dict(value=trigger, sha256=sha(encoded(trigger)))
        packet["cases"] = [
            dict(
                id="audit_dataset_end",
                inputs=["end_" + str(i) for i in range(5)],
                scenario="audit",
                closure="dataset_end",
                findings=[],
                events=1,
                matches=1,
            ),
            dict(
                id="audit_resource",
                inputs=["resource_0", "resource_1"],
                scenario="audit_skipped",
                closure="resource_limit",
                findings=["cwd_missing", "resource_limit"],
                events=1,
                matches=0,
            ),
        ]
    variant = folder / "source-packet.json"
    variant.write_bytes(encoded(packet) + b"\n")
    container(
        bundle["image"],
        [
            (BUILDS / PRODUCER, "/producer.jar", True),
            (probe, "/probe.jar", True),
            (variant, "/packet.json", True),
            (evidence, "/objects", True),
            (plan, "/plan.json", True),
            (folder, "/out", False),
        ],
        [
            "java",
            "-Xmx320m",
            "-cp",
            "/probe.jar:/producer.jar:/opt/flink/lib/*",
            "io.detectbridge.history.OriginalProducer",
            "/packet.json",
            "/plan.json",
            "/out/original.json",
            "/objects",
        ],
    )
    units = json.loads((folder / "original.json").read_bytes())
    for expected, unit in zip(packet["cases"], units, strict=True):
        outputs = unit["original_outputs"]
        tags = [o["value"] for o in outputs if o["kind"] == "tagged"]
        assert len(tags) == expected["events"]
        if tags:
            tag = tags[0]
            assert tag["counts"] == packet["literal_counts"][expected["scenario"]]
            assert len([o for o in outputs if o["kind"] == "detection"]) == expected["matches"]
            if unit["kind"] == "audit" and not expected["findings"]:
                for key, value in packet["group_fields"].items():
                    actual = (
                        tag["event"]["process"].get(key) if key not in {"paths", "cwd"} else None
                    )
                    if key in {"executable", "args", "pid"}:
                        assert actual == value
        manifests = [o["value"] for o in outputs if o["kind"] == "manifest"]
        if manifests:
            m = manifests[0]
            assert m["closure"] == expected["closure"] and m["findings"] == expected["findings"]
            assert [v["record_id"] for v in m["members"]] == [
                v["raw"]["record_id"] for v in unit["inputs"]
            ]
    return units


def zipped(raw):
    compressor = zlib.compressobj(6, zlib.DEFLATED, -15)
    return (
        bytes([31, 139, 8, 0, 0, 0, 0, 0, 0, 255])
        + compressor.compress(raw)
        + compressor.flush()
        + struct.pack("<II", zlib.crc32(raw), len(raw))
    )


def meta(path, value):
    b = encoded(value) + b"\n"
    path.write_bytes(b)
    path.with_suffix(".sha256").write_text(sha(b) + "\n")


def payload(raw, compressed, rows):
    return dict(
        compressed_sha256=sha(compressed),
        compressed_bytes=len(compressed),
        uncompressed_sha256=sha(raw),
        uncompressed_bytes=len(raw),
        rows=rows,
    )


def archive_fixture(folder, units, plan):
    """Independent format fixture, not Kafka qualification or substitute private evidence."""
    root = folder / "archive"
    root.mkdir()
    (root / "objects").mkdir()
    (root / "segments").mkdir()
    from archive import LIMITS as ARCHIVE_LIMITS
    from archive import TOPICS

    provenance = (
        encoded(
            dict(
                kind="synthetic",
                license="Apache-2.0",
                origin="Original DetectBridge P11/P12/P13 fixture packet",
            )
        )
        + b"\n"
    )
    object_sha = sha(provenance)
    originals = (
        {p.name: p.read_bytes() for p in (folder / "evidence").iterdir()}
        if (folder / "evidence").exists()
        else {}
    )
    originals[object_sha] = provenance
    object_hashes = sorted(originals)
    archive_id = str(uuid.uuid4())
    binding = dict(
        version="1.0.0",
        archive_id=archive_id,
        cluster="synthetic-history",
        bootstrap="kafka:9092",
        group="detectbridge-archive-v1-" + archive_id,
        implementation_sha256=json.loads((BUILDS / "bundle.json").read_bytes())["reader"],
        limits=ARCHIVE_LIMITS,
        topics=[
            dict(name=t, id="history-" + str(i), partition=0, start=0) for i, t in enumerate(TOPICS)
        ],
        objects=object_hashes,
        provenance=[object_sha],
    )
    meta(root / "archive.json", binding)
    for digest, data in originals.items():
        obj = root / "objects" / digest
        obj.mkdir()
        raw = encoded(dict(offset=0, bytes=base64.b64encode(data).decode())) + b"\n"
        compressed = zipped(raw)
        (obj / "bytes.ndjson.gz").write_bytes(compressed)
        meta(
            obj / "object.json",
            dict(
                version="1.0.0",
                codec="gzip-ndjson/1.0.0",
                sha256=digest,
                length=len(data),
                payload=payload(raw, compressed, 1),
            ),
        )
    rows: dict[str, list[Any]] = {t: [] for t in TOPICS}
    manifest_refs = {}

    def append(topic, value):
        offset = len(rows[topic])
        data = encoded(value)
        topic_id = next(t["id"] for t in binding["topics"] if t["name"] == topic)
        row = dict(
            version="1.0.0",
            id="sha256:"
            + sha(
                encoded(
                    ["detectbridge.archive.wire/1", binding["cluster"], topic_id, "0", str(offset)]
                )
            ),
            topic=topic,
            topic_id=topic_id,
            partition=0,
            offset=offset,
            timestamp=9223372036854775807,
            timestamp_type="CreateTime",
            key=None,
            value=base64.b64encode(data).decode(),
            headers=[],
            dependencies=object_hashes,
            category=(
                "control" if value.get("kind") in {"run_end", "source_boundary"} else "source"
            )
            if topic == INPUT
            else "derived",
        )
        rows[topic].append(row)
        return dict(topic=topic, offset=offset, value_sha256=sha(data))

    selected = []
    for unit in units:
        inputs = [append(INPUT, row) for row in unit["inputs"]]
        outputs = [append(ROUTES[o["kind"]], o["value"]) for o in unit["original_outputs"]]
        for o, ref in zip(unit["original_outputs"], outputs, strict=True):
            if o["kind"] == "manifest":
                manifest_refs[o["value"]["manifest_id"]] = ref
        for row in unit.get("extra_inputs", []):
            append(INPUT, row)
        for output in unit.get("extra_outputs", []):
            append(ROUTES[output["kind"]], output["value"])
        selected.append(
            dict(
                id=unit["label"],
                kind=unit["kind"],
                inputs=inputs,
                outputs=outputs,
                anchor=manifest_refs[unit["anchor"]["manifest_id"]] if unit["anchor"] else None,
                control=None,
            )
        )
    for topic, values in rows.items():
        if not values:
            continue
        topic_id = values[0]["topic_id"]
        directory = root / "segments" / topic_id / "0" / "0"
        directory.mkdir(parents=True)
        raw = b"".join(encoded(v) + b"\n" for v in values)
        compressed = zipped(raw)
        (directory / "records.ndjson.gz").write_bytes(compressed)
        meta(
            directory / "segment.json",
            dict(
                version="1.0.0",
                codec="gzip-ndjson/1.0.0",
                binding_sha256=sha(encoded(binding)),
                topic_id=topic_id,
                partition=0,
                first=0,
                next=len(values),
                previous=None,
                dependencies=object_hashes,
                payload=payload(raw, compressed, len(values)),
            ),
        )
    request = dict(
        version="1.0.0",
        mode="historical",
        original_run_id=units[0]["inputs"][0]["context"]["run_id"],
        producer_sha256=PRODUCER,
        plan_sha256=sha(plan.read_bytes()),
        units=selected,
    )
    (folder / "request.json").write_bytes(encoded(request) + b"\n")
    return root, folder / "request.json"
