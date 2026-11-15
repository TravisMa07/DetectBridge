"""Validate Linux profiles, reviewed locks and production resource boundaries."""

import argparse
import json
import zipfile
from pathlib import Path

from check_contracts import ContractValidator, load_json
from detection_mapping import validate_profiles

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "packages/linux-adapters"


def check(artifacts=False):
    validator = ContractValidator()
    sources, mappings = [], []
    for family in ("linux-audit-execution-p12a", "openssh-authentication-p12a"):
        source = load_json(MODULE / "contracts" / (family + ".source.json"))
        if validator.validate("source-contract", source):
            raise ValueError("linux_source_invalid")
        event = load_json(MODULE / "contracts" / (family + ".contract-example.event.json"))
        if validator.validate("normalized-event", event, source_contract=source):
            raise ValueError("linux_example_contract_invalid")
        sources.append(source)
        mappings.append(load_json(MODULE / "contracts" / (family + ".mapping.json")))
    validate_profiles(mappings, sources)
    catalog = load_json(ROOT / "catalog/recordings/openssh9-password-lab-v1.json")
    import hashlib

    capture = ROOT / catalog["acquisition"]["capture_path"]
    if hashlib.sha256(capture.read_bytes()).hexdigest() != catalog["acquisition"]["capture_sha256"]:
        raise ValueError("linux_recording_capture_review_outdated")
    if sorted(
        row.get("outcome", "")
        for row in catalog["expectations"]
        if row["disposition"] == "normalized"
    ) != ["failure", "success"]:
        raise ValueError("linux_recording_expectations_invalid")
    inventory = load_json(ROOT / "docs/linux-dependencies.json")
    if inventory["lockfiles"] != {
        "packages/linux-adapters/gradle.lockfile": (MODULE / "gradle.lockfile").read_text()
    }:
        raise ValueError("linux_dependency_review_outdated")
    coordinates = sorted(
        line.split("=", 1)[0]
        for line in (MODULE / "gradle.lockfile").read_text().splitlines()
        if line and not line.startswith(("#", "empty="))
    )
    reviewed = {
        row["coordinate"]
        for row in load_json(ROOT / "docs/transport-dependencies.json")["artifacts"]
    }
    if inventory["coordinates"] != coordinates or not set(coordinates) <= reviewed:
        raise ValueError("linux_dependency_coordinates_unreviewed")
    if artifacts:
        with zipfile.ZipFile(MODULE / "build/libs/linux-adapters.jar") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or any(
                "fixtures/" in n
                or n.endswith((".contract-example.event.json", ".yml"))
                or n.endswith("Test.class")
                for n in names
            ):
                raise ValueError("linux_runtime_contains_test_content")
            for resource in (MODULE / "contracts").glob("*.json"):
                if resource.name.endswith(".contract-example.event.json"):
                    continue
                if json.loads(archive.read(resource.name)) != load_json(resource):
                    raise ValueError("linux_resource_packaging_mismatch")
            if "io/detectbridge/linux/AuthReplay.class" not in names:
                raise ValueError("linux_auth_replay_missing")
            if archive.read("META-INF/LICENSE") != (ROOT / "LICENSE").read_bytes():
                raise ValueError("linux_project_license_missing")
            if archive.read("META-INF/ECS-NOTICE") != (ROOT / "contracts/v1/NOTICE").read_bytes():
                raise ValueError("linux_ecs_notice_missing")
        distribution = MODULE / "build/install/linux-adapters"
        if not (distribution / "bin/linux-adapters").is_file():
            raise ValueError("linux_auth_runner_missing")
        for target, original in (
            ("LICENSE", ROOT / "LICENSE"),
            ("ECS-NOTICE", ROOT / "contracts/v1/NOTICE"),
        ):
            if (distribution / target).read_bytes() != original.read_bytes():
                raise ValueError("linux_distribution_notice_missing")
    print(
        "PASS: Linux profiles, reviewed dependencies"
        + ("; production artifacts" if artifacts else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
