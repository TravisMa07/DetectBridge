"""Validate P10 contracts and prepare versioned compatibility fixtures."""

import argparse
import copy
import json
import subprocess
import tempfile
from pathlib import Path

import yaml
from check_contracts import load_json
from detection import prepare
from detection_compile import compile_rules, encoded
from detection_mapping import DIRECTORY, ROOT, content_hash, sha
from jsonschema import Draft202012Validator

FIXTURES = DIRECTORY / "fixtures"


def prepare_mapped():
    prepare()
    for path in DIRECTORY.glob("*.schema.json"):
        Draft202012Validator.check_schema(load_json(path))
    profiles = [load_json(p) for p in sorted(FIXTURES.glob("*.mapping.json"))]
    sources = [
        load_json(ROOT / "contracts/v1/examples" / (p["source"]["id"] + ".source.json"))
        for p in profiles
    ]
    plan = compile_rules(
        [ROOT / "contracts/detection/v1/fixtures/rules/process.yml"],
        sources,
        mappings=profiles,
        provenance=load_json(FIXTURES / "candidates.json"),
    )
    path = ROOT / ".cache/detection/mapped-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(plan) + b"\n")


def check_mapped(jar):
    # Literal expected outcomes/rationales were independently reasoned before implementation.
    cases = load_json(FIXTURES / "compatibility-cases.json")
    source = load_json(ROOT / "contracts/v1/examples/windows-security-4688.source.json")
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for case in cases:
            profile = load_json(FIXTURES / "windows-security-4688.mapping.json")
            command = next(f for f in profile["fields"] if f["alias"] == "CommandLine")
            command["capability"] = case["capability"]
            if case["capability"] == "unsupported":
                command.pop("source_path")
            profile["sha256"] = content_hash(profile)
            rule = {
                "title": "Original synthetic P10 capability expectation",
                "id": "70000000-0000-4000-8000-000000000001",
                "license": "Apache-2.0",
                "logsource": {"product": case.get("product", "windows")},
                "detection": {
                    "selection": {"CommandLine": "x"},
                    "image": {"Image|endswith": "cmd.exe"},
                    "condition": case["condition"],
                },
            }
            rule_path = folder / "rule.yml"
            rule_path.write_text(yaml.safe_dump(rule))
            candidate = copy.deepcopy(load_json(FIXTURES / "candidates.json")[0])
            candidate["revision"] = sha(rule_path.read_bytes())
            candidate["modifications"] = [
                {
                    "input_sha256": candidate["original_sha256"],
                    "output_sha256": candidate["revision"],
                    "description": "Original synthetic semantic case: " + case["name"],
                }
            ]
            plan = compile_rules([rule_path], [source], mappings=[profile], provenance=[candidate])
            (folder / "plan.json").write_bytes(encoded(plan))
            event = load_json(ROOT / "contracts/detection/v1/fixtures/positive.event.json")
            if case["missing"]:
                event["process"].pop("command_line", None)
            if case.get("quality"):
                event["detectbridge"]["quality"]["eligibility"] = case["quality"]
            if case.get("unknown_source"):
                event["detectbridge"]["source_contract"]["id"] = "unknown-source"
            if case.get("invalid"):
                event["process"]["command_line"] = None
            if case.get("capture_warning"):
                event["detectbridge"]["quality"]["diagnostics"].append(
                    {"code": "capture_unavailable", "field": "/process/command_line"}
                )
            (folder / "event.json").write_bytes(encoded(event))
            result = subprocess.run(
                [
                    str(ROOT / ".cache/jdk/bin/java"),
                    "-jar",
                    str(jar),
                    str(folder / "plan.json"),
                    str(folder / "event.json"),
                ],
                capture_output=True,
                timeout=30,
            )
            if case["expected"] == "invalid":
                valid = result.returncode != 0
            else:
                value = json.loads(result.stdout) if result.returncode == 0 else {}
                valid = (
                    value.get("counts", {}).get(case["expected"]) == 1
                    and value.get("version") == "2.0.0"
                    and value.get("evaluator") == "detectbridge-java/2.0.0"
                    and value.get("mapping_sha256") == sha(encoded(plan["mapping_profiles"]))
                )
            if not valid:
                raise ValueError("mapping_semantic_failure_" + case["name"])
    print(f"PASS: {len(cases)} independent P10 mapping YAML-to-Java cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="Prepare legacy and P10 test plans")
    parser.parse_args()
    prepare_mapped()
