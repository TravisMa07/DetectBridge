"""Check P15b1 closed contracts and independent fixtures; optional binary boundary checks."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from check_contracts import StrictValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/lifecycle-runtime/v1"
PRODUCER = "51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def schemas():
    resources = {}
    for directory in (
        "contracts/v1",
        "contracts/detection/v1",
        "contracts/detection/v2",
        "contracts/integration/v1",
        "contracts/integration/v1.1",
        "contracts/integration-runtime/v1",
        "contracts/lifecycle/v1",
        "contracts/lifecycle-runtime/v1",
        "packages/linux-adapters/contracts",
        "packages/windows-adapters/contracts",
    ):
        for path in (ROOT / directory).glob("*.schema.json"):
            value = load_json(path)
            Draft202012Validator.check_schema(value)
            assert value["$id"] not in resources
            resources[value["$id"]] = value
    return resources, Registry().with_resources(
        (key, Resource.from_contents(value)) for key, value in resources.items()
    )


def closed(node, path):
    if isinstance(node, dict):
        if node.get("type") == "object":
            if path not in {"state/properties/core", "output/properties/document"}:
                assert node.get("additionalProperties") is False, path
        for key, value in node.items():
            closed(value, path + "/" + key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            closed(value, path + "/" + str(index))


def check(artifacts=False):
    from build_worker_validator import BASE, check_requirements

    check_requirements()
    resources, registry = schemas()
    names = {"common", "control", "artifact", "ack", "output", "worker-config", "state"}
    assert {p.stem.removesuffix(".schema") for p in SCHEMAS.glob("*.schema.json")} == names
    for name in names:
        schema = resources["urn:detectbridge:lifecycle-runtime:1.0.0:" + name]
        closed(schema, name)

        def references(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "$ref":
                        registry.resolver(schema["$id"]).lookup(value)
                    else:
                        references(value)
            elif isinstance(node, list):
                for value in node:
                    references(value)

        references(schema)
    old = load_json(ROOT / "contracts/lifecycle/v1/request.schema.json")
    original = old["allOf"][4]["then"]["properties"]["arguments"]["properties"]["command"]
    common = resources["urn:detectbridge:lifecycle-runtime:1.0.0:common"]
    assert original == common["$defs"]["proposal"]
    validator = StrictValidator(common["$defs"]["counter"], format_checker=FormatChecker())
    for valid in (0, 1, 9223372036854775807):
        assert not list(validator.iter_errors(valid))
    for invalid in (-1, False, 1.0, 9223372036854775808):
        assert list(validator.iter_errors(invalid))

    for name in ("identity-vectors", "binding-vectors"):
        packet = load_json(SCHEMAS / "fixtures" / (name + ".json"))
        assert len(packet["vectors"]) == (5 if name == "identity-vectors" else 9)
        for vector in packet["vectors"]:
            preimage = vector["preimage"]
            expected = vector.get("output_id", vector.get("sha256"))
            assert expected in {sha(encoded(preimage)), "sha256:" + sha(encoded(preimage))}
            assert vector["canonical_utf8"].encode() == encoded(preimage)
            if isinstance(preimage, dict) and "limits" in preimage:
                assert preimage["limits"] == common["$defs"]["limits"]["const"]
                assert preimage["validator"]["base_image"] == BASE

    from lifecycle_runtime_cases import check_packet

    check_packet()
    if artifacts:
        legacy = ROOT / "packages/integration-job/build/libs/integration-job.jar"
        assert sha(legacy.read_bytes()) == PRODUCER
        jar = ROOT / "packages/lifecycle-job/build/libs/lifecycle-job.jar"
        with zipfile.ZipFile(jar) as archive, zipfile.ZipFile(legacy) as original:
            names_in_jar = archive.namelist()
            classes = {p for p in names_in_jar if p.endswith(".class")}
            assert classes and all(
                p.startswith("io/detectbridge/integration/Lifecycle") for p in classes
            )
            assert not classes.intersection(original.namelist())
            assert not any(
                p.rsplit("/", 1)[-1].startswith(
                    ("LifecycleProbe", "LifecycleQualification", "LifecycleUidProbe")
                )
                for p in classes
            )
            assert not any(p.endswith((".pk8", ".pem", ".key")) for p in names_in_jar)
            assert names_in_jar.count("lifecycle-log4j.properties") == 1
            assert (
                archive.read("lifecycle-log4j.properties")
                == (
                    ROOT / "packages/lifecycle-job/src/main/resources/lifecycle-log4j.properties"
                ).read_bytes()
            )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    args = parser.parse_args()
    try:
        check(args.artifacts)
    except Exception as error:
        print("FAIL: lifecycle runtime contract checks (" + type(error).__name__ + ")")
        return 1
    print(
        "PASS: lifecycle contracts/independent fixtures"
        + (" and actual artifact boundary" if args.artifacts else "; no runtime claim")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
