"""Managed archive closed contracts, independent literal vectors and artifact bindings."""

import argparse
import base64
import gzip
import hashlib
import json
import zipfile
from pathlib import Path

from archive_profiles import GRAPH_RESOURCES, PINS
from check_contracts import load_json
from check_current_replay import closed_local
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/archive-maintenance/v1"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def literal_payload(item, rows):
    compressed = bytes.fromhex(item["gzip_hex"])
    plain = gzip.decompress(compressed)
    payload = item["metadata"]["payload"]
    assert sha(compressed) == payload["compressed_sha256"]
    assert len(compressed) == payload["compressed_bytes"]
    assert sha(plain) == payload["uncompressed_sha256"]
    assert len(plain) == payload["uncompressed_bytes"]
    assert plain == b"".join(encoded(row) + b"\n" for row in rows)
    assert payload["rows"] == len(rows)


def artifact_check():
    jar_path = ROOT / "packages/archive-maintenance/build/libs/archive-maintenance.jar"
    tools = (
        "archive_maintenance",
        "archive_profiles",
        "managed_replay",
        "p05_archive",
        "replay",
        "replay_time",
        "check_replay",
        "check_datasets",
        "datasets",
        "contract_identity",
        "check_contracts",
    )
    resources = {
        "META-INF/maintenance/tools/" + name + ".py": ROOT / "tools" / (name + ".py")
        for name in tools
    }
    resources["META-INF/maintenance/uv.lock"] = ROOT / "uv.lock"
    for directory in ("archive-maintenance/v1", "replay/v1", "v1"):
        for source in (ROOT / "contracts" / directory).glob("*.schema.json"):
            resources["META-INF/maintenance/contracts/" + directory + "/" + source.name] = source
    resources["META-INF/maintenance/catalog/datasets/manifest.schema.json"] = (
        ROOT / "catalog/datasets/manifest.schema.json"
    )
    for name in ("Format", "Store", "Main"):
        resources["META-INF/maintenance/legacy/" + name + ".java"] = (
            ROOT
            / "packages/archive-writer/src/main/java/io/detectbridge/archive"
            / (name + ".java")
        )
    for directory in ("archive/v1", "archive-maintenance/v1"):
        for source in (ROOT / "contracts" / directory).glob("*.schema.json"):
            resources[directory + "/" + source.name] = source
    for graph_resource in GRAPH_RESOURCES:
        resources["archive-graph/" + graph_resource] = ROOT / graph_resource
    with zipfile.ZipFile(jar_path) as jar:
        names = jar.namelist()
        assert len(names) == len(set(names)), "duplicate managed JAR entries"
        for name in (
            "ManagedMain",
            "ManagedStore",
            "ManagedFormat",
            "ManagedGraph",
            "ReplaySource",
        ):
            assert "io/detectbridge/archive/" + name + ".class" in names
        for name in names:
            if name.startswith("io/detectbridge/") and name.endswith(".class"):
                assert name.startswith(
                    ("io/detectbridge/archive/", "io/detectbridge/transport/")
                ), name
                assert "Probe" not in name, name
        for name, source in resources.items():
            assert jar.read(name) == source.read_bytes(), name
        assert jar.read("META-INF/DetectBridge-LICENSE") == (ROOT / "LICENSE").read_bytes()
    paths = dict(
        reader="archive-writer",
        historical="historical-replay",
        current="current-replay",
        producer="integration-job",
    )
    for role, module in paths.items():
        assert (
            sha((ROOT / "packages" / module / "build/libs" / (module + ".jar")).read_bytes())
            == PINS[role]
        ), role
    bundle = load_json(ROOT / ".cache/archive-maintenance-build/bundle.json")
    assert bundle["version"] == "1.0.0"
    assert bundle["managed"] == sha(jar_path.read_bytes())
    probe = ROOT / "packages/archive-maintenance/build/libs/archive-maintenance-probe.jar"
    assert bundle["probe"] == sha(probe.read_bytes())
    with zipfile.ZipFile(probe) as jar:
        assert "io/detectbridge/archive/ManagedProbe.class" in jar.namelist()
        assert b"Main-Class: io.detectbridge.archive.ManagedProbe" in jar.read(
            "META-INF/MANIFEST.MF"
        )
    for role, pin in PINS.items():
        assert bundle[role] == pin, role
    for role in ("managed", "probe", *paths):
        digest = bundle[role]
        assert sha((ROOT / ".cache/archive-maintenance-build" / digest).read_bytes()) == digest, (
            role
        )


def check(artifacts=False):
    for name in ("registration", "plan", "retirement", "head", "holds", "import"):
        schema = load_json(SCHEMAS / (name + ".schema.json"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == "urn:detectbridge:archive-maintenance:1.0.0:" + name
        assert schema["additionalProperties"] is False
        closed_local(schema)
    packet = load_json(SCHEMAS / "fixtures/expectations.json")
    assert packet["version"] == "1.0.0"
    assert packet["legacy_artifacts"] == PINS
    assert {source["path"] for source in packet["sources"]} == {
        "packages/archive-writer/src/main/java/io/detectbridge/archive/Format.java",
        "packages/archive-writer/src/main/java/io/detectbridge/archive/Store.java",
        "packages/archive-writer/src/main/java/io/detectbridge/archive/Main.java",
        "tools/historical.py",
        "tools/current_replay.py",
        "contracts/search-writer/v1/fixtures/recorded-expectations.json",
        "contracts/current-replay/v1/fixtures/expectations.json",
    }
    for source in packet["sources"]:
        assert sha((ROOT / source["path"]).read_bytes()) == source["sha256"]
    domains = {
        "detectbridge.archive.retirement/1",
        "detectbridge.archive.p05-import/1",
        "detectbridge.archive.link/1",
    }
    assert {v["preimage"][0] for v in packet["identities"]} == domains
    for vector in packet["identities"]:
        assert sha(encoded(vector["preimage"])) == vector["sha256"]
    legacy = packet["legacy"]
    assert (
        sha(encoded(legacy["configuration"])) == legacy["segments"][0]["metadata"]["binding_sha256"]
    )
    previous = None
    for segment in legacy["segments"]:
        literal_payload(segment, segment["rows"])
        assert sha(encoded(segment["metadata"])) == segment["metadata_sha256"]
        assert segment["metadata"]["previous"] == previous
        previous = segment["metadata_sha256"]
    for obj in legacy["objects"]:
        original = bytes.fromhex(obj["original_hex"])
        assert sha(original) == obj["metadata"]["sha256"]
        assert len(original) == obj["metadata"]["length"]
        literal_payload(obj, [dict(bytes=base64.b64encode(original).decode(), offset=0)])
    expected = packet["retirement_expected"]
    assert (expected["floor"], expected["head"]) == (4, 6)
    assert expected["previous_sha256"] == legacy["segments"][1]["metadata_sha256"]
    assert expected["retained_segment_sha256"] == legacy["segments"][2]["metadata_sha256"]
    original = bytes.fromhex(expected["original_hex"])
    assert original == b"A\r\n\n\xc3\xa9\nZ"
    assert [original[start : start + length] for start, length in expected["ranges"]] == [
        b"A\r\n",
        b"\n",
        b"\xc3\xa9\n",
        b"Z",
    ]
    recorded = packet["recorded"]
    assert recorded["catalogs"] == [
        dict(
            kind="windows",
            sha256="ec277d352417bb0a99443a6fa22d3990da9ae4046f8fab480993e2a58eb570a1",
        ),
        dict(
            kind="audit", sha256="1fcdddf89e572bed765327ac21b10019683e467706850e6045fc78ed4608ae6d"
        ),
        dict(
            kind="auth", sha256="97ae15e085dfe40c5e5687ecc6a69a34be9af899089259489bb8575d60d168f7"
        ),
    ]
    for group in ("source_records", "admissions", "historical", "current"):
        assert all(type(value) is int for value in recorded[group].values())
    assert recorded["source_records"] == dict(windows=5, audit=30, auth=11)
    assert recorded["admissions"] == dict(
        originals=46, exact_redelivery=1, controlled_late_cursor=1, run_end=1, total=49
    )
    assert recorded["historical"] == dict(tagged=16, manifest=10, preservation=14, detection=3)
    assert recorded["current"] == dict(
        tagged=16, manifest=10, preservation=14, processing=9, detection=0
    )
    fields = (
        "matched",
        "unmatched",
        "inapplicable",
        "configuration_blocked",
        "quality_skipped",
        "evaluation_error",
    )
    expected_counts = dict(
        eligible_linux=(0, 1, 1, 0, 0, 0),
        skipped_audit=(0, 0, 1, 0, 1, 0),
        windows=(0, 0, 2, 0, 0, 0),
    )
    assert recorded["current_counts"] == {
        name: dict(zip(fields, values, strict=True)) for name, values in expected_counts.items()
    }
    assert all(
        type(n) is int for counts in recorded["current_counts"].values() for n in counts.values()
    )
    if artifacts:
        artifact_check()
    print(
        "PASS: maintenance closed schemas, source pins, literal bytes/identities and independent counts"
        + ("; managed JAR and legacy artifacts" if artifacts else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
