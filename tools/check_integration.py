"""Check implemented P13 schemas, source fixtures, reviewed dependencies and packaged job."""

import argparse
import json
import zipfile
from pathlib import Path

from check_contracts import load_json
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


def registry():
    paths = [
        *(ROOT / "contracts/v1").glob("*.schema.json"),
        *(ROOT / "contracts/detection/v2").glob("*.schema.json"),
        *(ROOT / "contracts/integration/v1.1").glob("*.schema.json"),
        *(ROOT / "contracts/integration-runtime/v1").glob("*.schema.json"),
        *(ROOT / "packages/linux-adapters/contracts").glob("*.schema.json"),
    ]
    schemas = {load_json(p)["$id"]: load_json(p) for p in paths}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    return schemas, Registry().with_resources(
        (key, Resource.from_contents(value)) for key, value in schemas.items()
    )


def validate(kind, value):
    schemas, resources = registry()
    Draft202012Validator(
        schemas[kind], registry=resources, format_checker=FormatChecker()
    ).validate(value)


def check(artifacts=False):
    registry()
    from integration_cases import windows

    for family in ("security", "sysmon"):
        validate("urn:detectbridge:integration-runtime:1.0.0:input", windows(family))
    coordinates = {
        line.split("=")[0]
        for line in (ROOT / "packages/integration-job/gradle.lockfile").read_text().splitlines()
        if line and not line.startswith(("#", "empty="))
    }
    reviewed = {
        r["coordinate"] for r in load_json(ROOT / "docs/transport-dependencies.json")["artifacts"]
    }
    if not coordinates <= reviewed:
        raise ValueError("integration_unreviewed_dependency")
    if artifacts:
        with zipfile.ZipFile(
            ROOT / "packages/integration-job/build/libs/integration-job.jar"
        ) as archive:
            names = archive.namelist()
            for cls in (
                "IntegrationJob",
                "IntegrationPublisher",
                "IntegrationBroker",
                "Machine",
                "LocalEvidence",
            ):
                if f"io/detectbridge/integration/{cls}.class" not in names:
                    raise ValueError("integration_missing_runtime_class")
            for path in (ROOT / "contracts/integration-runtime/v1").glob("*.schema.json"):
                if path.name.endswith("runtime.schema.json"):
                    continue
                if json.loads(archive.read(path.name)) != load_json(path):
                    raise ValueError("integration_schema_packaging")
            if any("/fixtures/" in p or p.endswith("Test.class") for p in names):
                raise ValueError("integration_fixture_leak")
            if archive.read("META-INF/DetectBridge-LICENSE") != (ROOT / "LICENSE").read_bytes():
                raise ValueError("integration_license_missing")
            if archive.read("META-INF/ECS-NOTICE") != (ROOT / "contracts/v1/NOTICE").read_bytes():
                raise ValueError("integration_ecs_notice_missing")
    print(
        "PASS: real integration schemas/source inputs, reviewed dependency coordinates"
        + (" and packaged job" if artifacts else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
