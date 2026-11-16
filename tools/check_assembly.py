"""Verify real P12b schemas, independent inputs, owning lock and production resources."""

import argparse
import json
import zipfile
from pathlib import Path

from check_contracts import load_json
from jsonschema import Draft202012Validator
from linux_assembly_cases import cases
from linux_assembly_verify import Oracle

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "packages/linux-assembly-job"


def check(artifacts=False):
    schemas = list((ROOT / "contracts/linux-assembly/v1").glob("*.schema.json"))
    for path in schemas:
        Draft202012Validator.check_schema(load_json(path))
    oracle = Oracle(
        dict(
            broker=dict(
                cluster_id="synthetic", topics={"detectbridge.assembly.input.v1": dict(id="input")}
            )
        ),
        "a" * 64,
    )
    source = cases()
    for row in [*source["complete"], source["auth"]]:
        oracle.schema("urn:detectbridge:assembly:1.0.0:input", row)
    lock = MODULE / "gradle.lockfile"
    review = load_json(ROOT / "docs/assembly-dependencies.json")
    if review["lockfiles"] != {str(lock.relative_to(ROOT)): lock.read_text()}:
        raise ValueError("assembly_dependency_review_outdated")
    coordinates = sorted(
        line.split("=")[0]
        for line in lock.read_text().splitlines()
        if line and not line.startswith(("#", "empty="))
    )
    existing = {
        row["coordinate"]
        for row in load_json(ROOT / "docs/transport-dependencies.json")["artifacts"]
    }
    if coordinates != review["coordinates"] or not set(coordinates) <= existing:
        raise ValueError("assembly_unreviewed_dependency")
    if artifacts:
        with zipfile.ZipFile(MODULE / "build/libs/linux-assembly-job.jar") as archive:
            names = archive.namelist()
            for name in (
                "AssemblyJob",
                "Machine",
                "AssemblyBroker",
                "AssemblyPublisher",
                "LocalEvidence",
            ):
                if "io/detectbridge/assembly/" + name + ".class" not in names:
                    raise ValueError("assembly_packaging_missing_class")
            if any(
                name.startswith("io/detectbridge/")
                and name.endswith("Test.class")
                or name.startswith("fixtures/")
                or name.endswith((".contract-example.event.json", ".yml"))
                for name in names
            ):
                raise ValueError("assembly_packaging_contains_fixtures")
            for path in schemas:
                if json.loads(archive.read(path.name)) != load_json(path):
                    raise ValueError("assembly_schema_packaging_mismatch")
            if archive.read("META-INF/DetectBridge-LICENSE") != (ROOT / "LICENSE").read_bytes():
                raise ValueError("assembly_project_license_missing")
            if archive.read("META-INF/ECS-NOTICE") != (ROOT / "contracts/v1/NOTICE").read_bytes():
                raise ValueError("assembly_ecs_notice_missing")
    print(
        "PASS: P12b schemas, independent inputs, reviewed lock"
        + ("; real production job artifacts" if artifacts else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
