"""Offline writer contract, image and runtime-overlay policy validation."""

import argparse
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path

from check_contracts import StrictValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/search-writer/v1"
KINDS = {"configuration", "projection", "failure"}


def no_refs(node):
    if isinstance(node, dict):
        if "$ref" in node or "$dynamicRef" in node:
            raise ValueError("writer_schema_reference")
        for child in node.values():
            no_refs(child)
    elif isinstance(node, list):
        for child in node:
            no_refs(child)


@lru_cache(maxsize=6)
def compiled_schema(kind, serialized):
    # The cache key includes the full strictly parsed schema, so edits invalidate it.
    schema = json.loads(serialized)
    Draft202012Validator.check_schema(schema)
    no_refs(schema)
    if schema["$id"] != "urn:detectbridge:search-writer:1.0.0:" + kind:
        raise ValueError("unknown_writer_schema")
    return StrictValidator(schema, format_checker=FormatChecker())


def require(kind, value):
    if kind not in KINDS:
        raise ValueError("unknown_writer_contract")
    schema = load_json(SCHEMAS / (kind + ".schema.json"))
    validator = compiled_schema(kind, json.dumps(schema, separators=(",", ":")))
    if next(validator.iter_errors(value), None):
        raise ValueError("invalid_writer_" + kind)


def validate_overlay(overlay, bundle):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", bundle.get("image_id", "")):
        raise ValueError("invalid_writer_image")
    if (
        set(overlay) != {"services", "volumes"}
        or set(overlay["services"]) != {"writer"}
        or overlay["volumes"] != {"writer-secrets": {}}
    ):
        raise ValueError("invalid_writer_overlay_boundary")
    service = overlay["services"]["writer"]
    expected = {
        "image": bundle["image_id"],
        "profiles": ["writer"],
        "user": "9999:9999",
        "networks": ["internal"],
        "mem_limit": "512m",
        "cpus": 0.5,
        "pids_limit": 128,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "read_only": True,
        "tmpfs": ["/tmp:rw,nosuid,size=32m"],
        "stop_grace_period": "45s",
        "volumes": ["writer-secrets:/secrets:ro"],
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
        "healthcheck": {
            "test": [
                "CMD",
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "3",
                "http://localhost:9250/health",
            ],
            "interval": "5s",
            "timeout": "4s",
            "retries": 3,
        },
    }
    if service != expected:
        raise ValueError("writer_runtime_policy_mismatch")


def artifacts():
    path = ROOT / "packages/integration-writer/build/libs/search-writer.jar"
    with zipfile.ZipFile(path) as jar:
        names = jar.namelist()
        if len(names) != len(set(names)) or "io/detectbridge/search/Main.class" not in names:
            raise ValueError("invalid_writer_jar")
        if not any(n.startswith("META-INF/LICENSE") for n in names):
            raise ValueError("missing_writer_notices")
        if any(
            n.startswith("org/apache/flink/") or "/examples/" in n or "/fixtures/" in n
            for n in names
        ):
            raise ValueError("writer_bundled_runtime_or_fixture")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    args = parser.parse_args()
    for kind in sorted(KINDS):
        compiled_schema(kind, json.dumps(load_json(SCHEMAS / (kind + ".schema.json"))))
    if args.artifacts:
        artifacts()
    print("PASS: separate search-writer schemas and artifact boundary")


if __name__ == "__main__":
    main()
