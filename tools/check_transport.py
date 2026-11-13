"""Closed transport schema registry and shared Python/Java fixture expectations."""

import argparse
import base64
import json
import zipfile
from pathlib import Path

from check_contracts import StrictValidator, load_json
from check_replay import ReplayValidator
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "contracts/transport/v1"
KINDS = {"configuration", "publication", "receipts", "quarantine", "job-history"}


def require(kind, value):
    if kind not in KINDS:
        raise ValueError("unknown_transport_contract")
    schema = load_json(DIRECTORY / (kind + ".schema.json"))
    Draft202012Validator.check_schema(schema)
    if (
        schema["$id"] != "urn:detectbridge:transport:1.0.0:" + kind
        or schema["$schema"] != "https://json-schema.org/draft/2020-12/schema"
    ):
        raise ValueError("unknown_transport_schema")

    # These schemas are deliberately self-contained; no references may be introduced.
    def refs(node):
        if isinstance(node, dict):
            if "$ref" in node or "$dynamicRef" in node:
                raise ValueError("transport_schema_reference")
            for child in node.values():
                refs(child)
        elif isinstance(node, list):
            for child in node:
                refs(child)

    refs(schema)
    if next(StrictValidator(schema, format_checker=FormatChecker()).iter_errors(value), None):
        raise ValueError("invalid_transport_" + kind)


def check_artifacts():
    for module, archive, entry in [
        ("transport-job", "transport-job.jar", "RelayJob"),
        ("transport-publisher", "publisher.jar", "Publisher"),
    ]:
        path = ROOT / "packages" / module / "build/libs" / archive
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            if len(names) != len(set(names)):
                raise ValueError("duplicate_shaded_entries")
            if "io/detectbridge/transport/" + entry + ".class" not in names:
                raise ValueError("missing_entrypoint")
            if not any(name.startswith("META-INF/LICENSE") for name in names):
                raise ValueError("missing_dependency_license")
            if any(
                name.startswith(
                    (
                        "org/apache/flink/api/common/",
                        "org/apache/flink/runtime/",
                        "org/apache/flink/streaming/api/",
                    )
                )
                or "/fixtures/" in name
                or "/examples/" in name
                for name in names
            ):
                raise ValueError("bundled_provided_runtime_or_fixture")
            if any(
                name.endswith((".SF", ".RSA", ".DSA")) and name.startswith("META-INF/")
                for name in names
            ):
                raise ValueError("stale_dependency_signature")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    args = parser.parse_args()
    try:
        if args.artifacts:
            check_artifacts()
        validator = ReplayValidator()
        for path in DIRECTORY.glob("*.schema.json"):
            schema = load_json(path)
            Draft202012Validator.check_schema(schema)
        if {p.name.removesuffix(".schema.json") for p in DIRECTORY.glob("*.schema.json")} != KINDS:
            raise ValueError("unknown_transport_schema")
        cases = load_json(DIRECTORY / "fixtures/validation-cases.json")
        for case in cases:
            valid = True
            try:
                raw = base64.b64decode(case["value"], validate=True)

                def unique(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError("duplicate_key")
                        result[key] = value
                    return result

                value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
                validator.require("envelope", value)
                if base64.b64decode(case["key"]).decode() != value["run_id"]:
                    raise ValueError("key")
            except Exception:
                valid = False
            if valid != case["valid"]:
                raise ValueError("independent_fixture_mismatch")
    except Exception:
        print(json.dumps({"category": "invalid_transport_contract_or_fixture"}))
        return 1
    print("PASS: transport schemas and independent semantic cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
