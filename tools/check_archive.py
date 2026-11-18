"""Closed archive schemas, literal vector consistency and packaged artifact checks."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from check_contracts import StrictValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/archive/v1"
KINDS = ("configuration", "wire", "chunk", "object", "segment")


def no_refs(node):
    if isinstance(node, dict):
        if "$ref" in node or "$dynamicRef" in node:
            raise ValueError("archive_nonlocal_reference")
        for value in node.values():
            no_refs(value)
    elif isinstance(node, list):
        for value in node:
            no_refs(value)


def require(kind, value):
    if kind not in KINDS:
        raise ValueError("archive_unknown_schema")
    schema = load_json(SCHEMAS / (kind + ".schema.json"))
    Draft202012Validator.check_schema(schema)
    no_refs(schema)
    if schema["$id"] != "urn:detectbridge:archive:1.0.0:" + kind:
        raise ValueError("archive_schema_identity")
    if next(StrictValidator(schema, format_checker=FormatChecker()).iter_errors(value), None):
        raise ValueError("archive_schema_invalid")


def check(artifacts=False):
    for kind in KINDS:
        schema = load_json(SCHEMAS / (kind + ".schema.json"))
        Draft202012Validator.check_schema(schema)
        no_refs(schema)
    vectors = load_json(SCHEMAS / "fixtures/vectors.json")
    for value, expected in (
        (vectors["canonical_value"], vectors["canonical_sha256"]),
        (vectors["wire_preimage"], vectors["wire_id"].removeprefix("sha256:")),
    ):
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        if hashlib.sha256(encoded).hexdigest() != expected:
            raise ValueError("archive_vector_mismatch")
    if artifacts:
        with zipfile.ZipFile(ROOT / "packages/archive-writer/build/libs/archive-writer.jar") as jar:
            names = jar.namelist()
            if len(names) != len(set(names)):
                raise ValueError("archive_duplicate_resource")
            if "io/detectbridge/archive/Main.class" not in names or any(
                "KafkaProbe" in n or "/fixtures/" in n or n.startswith("org/apache/flink/")
                for n in names
            ):
                raise ValueError("archive_runtime_boundary")
            if jar.read("META-INF/DetectBridge-LICENSE") != (ROOT / "LICENSE").read_bytes():
                raise ValueError("archive_license_missing")
            if jar.read("META-INF/ECS-NOTICE") != (ROOT / "contracts/v1/NOTICE").read_bytes():
                raise ValueError("archive_ecs_notice_missing")
            for kind in KINDS:
                if (
                    jar.read("archive/v1/" + kind + ".schema.json")
                    != (SCHEMAS / (kind + ".schema.json")).read_bytes()
                ):
                    raise ValueError("archive_packaged_schema_drift")
    print("PASS: archive schemas, independent vectors and selected artifact checks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
