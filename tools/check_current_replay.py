"""Closed current replay contracts, frozen source lineage and thin artifact boundary."""

import argparse
import zipfile
from typing import Any

from check_contracts import StrictValidator, load_json
from historical import PRODUCER, ROOT, encoded, sha
from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = ROOT / "contracts/current-replay/v1"


def closed_local(node):
    if isinstance(node, dict):
        assert "$ref" not in node and "$dynamicRef" not in node
        if "properties" in node:
            assert node.get("additionalProperties") is False
        for value in node.values():
            closed_local(value)
    elif isinstance(node, list):
        for value in node:
            closed_local(value)


def request_boundaries(schema):
    validator = StrictValidator(schema, format_checker=FormatChecker())
    value: dict[str, Any] = dict(
        version="1.0.0",
        mode="current",
        selection_sha256="a" * 64,
        plan_sha256="b" * 64,
        engine_profile="p13-runtime-51a984de/1.0.0",
        source_policy="preserve-original-context/1.0.0",
        schedule_policy="explicit-offline-clock/1.0.0",
        enrichment=[],
        assembler_limits=dict(
            members=256,
            group_bytes=1048576,
            open_groups=1024,
            pending_bytes=33554432,
            age_ms=30000,
            runs=16,
            closed_keys=100000,
            closed_bytes=33554432,
        ),
        schedule=[
            dict(
                at_ms=0,
                action="input",
                input=dict(
                    topic="detectbridge.integration.input.v1",
                    offset=9223372036854775807,
                    value_sha256="c" * 64,
                ),
            ),
            dict(at_ms=1, action="end", input=None),
        ],
    )
    assert not list(validator.iter_errors(value))
    for invalid in (-1, 9223372036854775808, 0.0, False):
        value["schedule"][0]["input"]["offset"] = invalid
        assert list(validator.iter_errors(value))


def check(artifacts=False):
    for name in ("request", "run", "result", "commit"):
        schema = load_json(SCHEMAS / (name + ".schema.json"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == "urn:detectbridge:current-replay:1.0.0:" + name
        assert schema["additionalProperties"] is False
        if name != "commit":
            assert schema["properties"]["mode"] == dict(const="current")
        closed_local(schema)
        if name == "request":
            request_boundaries(schema)
    packet = load_json(SCHEMAS / "fixtures/expectations.json")
    assert packet["version"] == "1.0.0"
    for source in packet["sources"]:
        assert sha((ROOT / source["path"]).read_bytes()) == source["sha256"]
    identity = packet["identity"]
    assert identity["preimage"][0] == "detectbridge.current.transition/1"
    assert sha(encoded(identity["preimage"])) == identity["sha256"]
    counts = packet["counts"]
    assert all(type(count) is int for group in counts.values() for count in group.values())
    assert counts == dict(
        auth=dict(
            matched=0,
            unmatched=1,
            inapplicable=1,
            configuration_blocked=0,
            quality_skipped=0,
            evaluation_error=0,
        ),
        audit=dict(
            matched=1,
            unmatched=0,
            inapplicable=1,
            configuration_blocked=0,
            quality_skipped=0,
            evaluation_error=0,
        ),
    )
    original = load_json(ROOT / "contracts/historical-replay/v1/fixtures/expectations.json")
    assert {case["id"] for case in packet["cases"]} == {"regroup", "timeout", "deadline"}
    for case in packet["cases"]:
        assert len(case["inputs"]) == len(case["milliseconds"])
        assert len(set(case["inputs"])) == len(case["inputs"])
        assert set(case["inputs"]) <= set(original["inputs"])
        assert case["milliseconds"] == sorted(case["milliseconds"])
        assert all(type(value) is int and 0 <= value <= 86400000 for value in case["milliseconds"])
    if artifacts:
        path = ROOT / "packages/current-replay/build/libs/current-replay.jar"
        resources = {
            "META-INF/current/tools/current_replay.py": ROOT / "tools/current_replay.py",
            "META-INF/current/tools/historical.py": ROOT / "tools/historical.py",
            "META-INF/current/tools/check_contracts.py": ROOT / "tools/check_contracts.py",
            "META-INF/current/uv.lock": ROOT / "uv.lock",
            **{"META-INF/current/schemas/" + p.name: p for p in SCHEMAS.glob("*.schema.json")},
            **{
                "META-INF/current/historical-schemas/" + p.name: p
                for p in (ROOT / "contracts/historical-replay/v1").glob("*.schema.json")
            },
        }
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            assert len(names) == len(set(names))
            assert "io/detectbridge/currentreplay/Bootstrap.class" in names
            assert "io/detectbridge/currentreplay/Engine.class" in names
            assert all(
                not n.endswith(".class") or n.startswith("io/detectbridge/currentreplay/")
                for n in names
            )
            assert not any("Probe" in n or "OriginalProducer" in n for n in names)
            allowed = {*resources, "META-INF/MANIFEST.MF", "META-INF/DetectBridge-LICENSE"}
            assert all(n.endswith(("/", ".class")) or n in allowed for n in names)
            assert jar.read("META-INF/DetectBridge-LICENSE") == (ROOT / "LICENSE").read_bytes()
            for name, source in resources.items():
                assert jar.read(name) == source.read_bytes(), name
        assert (
            sha((ROOT / "packages/integration-job/build/libs/integration-job.jar").read_bytes())
            == PRODUCER
        )
    summary = "PASS: current replay closed contracts and frozen source/count/identity expectations"
    if artifacts:
        summary += "; thin JAR resources/classes and pinned producer"
    print(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
