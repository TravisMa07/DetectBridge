"""Validate Windows profiles, reviewed dependencies and optional installed artifacts."""

import argparse
import json
import zipfile
from pathlib import Path

from check_contracts import ContractValidator, load_json
from detection_mapping import validate_profiles

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "packages/windows-adapters"


def check(artifacts=False):
    validator = ContractValidator()
    sources, mappings = [], []
    for family in ("security", "sysmon"):
        source = load_json(MODULE / "profiles" / (family + ".source.json"))
        if validator.validate("source-contract", source):
            raise ValueError("windows_source_invalid")
        event = load_json(MODULE / "profiles" / (family + ".expected.json"))
        if validator.validate("normalized-event", event, source_contract=source):
            raise ValueError("windows_expectation_contract_invalid")
        sources.append(source)
        mappings.append(load_json(MODULE / "profiles" / (family + ".mapping.json")))
    validate_profiles(mappings, sources)
    inventory = load_json(ROOT / "docs/windows-dependencies.json")
    if inventory["lockfiles"] != {
        "packages/windows-adapters/gradle.lockfile": (MODULE / "gradle.lockfile").read_text()
    }:
        raise ValueError("windows_dependency_review_outdated")
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
        raise ValueError("windows_dependency_coordinates_unreviewed")
    if artifacts:
        jar = MODULE / "build/install/windows-adapters/lib/windows-adapters.jar"
        with zipfile.ZipFile(jar) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or any(
                "/fixtures/" in n or n.endswith((".expected.json", ".xml", ".yml")) for n in names
            ):
                raise ValueError("windows_runtime_contains_test_content")
            for family in ("security", "sysmon"):
                for kind in ("source", "mapping"):
                    name = family + "." + kind + ".json"
                    if json.loads(archive.read(name)) != load_json(MODULE / "profiles" / name):
                        raise ValueError("windows_profile_packaging_mismatch")
        distribution = MODULE / "build/install/windows-adapters"
        if (distribution / "LICENSE").read_bytes() != (ROOT / "LICENSE").read_bytes():
            raise ValueError("windows_project_license_missing")
        if (distribution / "ECS-NOTICE").read_bytes() != (
            ROOT / "contracts/v1/NOTICE"
        ).read_bytes():
            raise ValueError("windows_ecs_notice_missing")
        if not (MODULE / "build/install/windows-adapters/bin/windows-adapters").is_file():
            raise ValueError("windows_runner_missing")
    print(
        "PASS: Windows profiles, mapping declarations and reviewed dependency lock"
        + ("; installed artifacts" if artifacts else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
