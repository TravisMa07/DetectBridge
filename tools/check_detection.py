"""Validate P09 contracts and independently expected YAML-to-Java behavior."""

import argparse
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

import yaml
from check_contracts import load_json
from detection import FIXTURES, ROOT, prepare
from detection_compile import DIRECTORY, compile_rules, encoded
from jsonschema import Draft202012Validator


def check(java=False):
    for path in DIRECTORY.glob("*.schema.json"):
        Draft202012Validator.check_schema(load_json(path))
    inventory = load_json(ROOT / "docs/detection-dependencies.json")
    locks = {
        str(p.relative_to(ROOT)): p.read_text()
        for p in ROOT.glob("packages/detection-*/gradle.lockfile")
    }
    if inventory["java_locks"] != locks:
        raise ValueError("detection_dependency_review_outdated")
    prepare()
    cases = load_json(FIXTURES / "semantic-cases.json")
    if not java:
        return
    jar = ROOT / "packages/detection-evaluator/build/libs/evaluator.jar"
    for module, filename in [
        ("detection-evaluator", "evaluator.jar"),
        ("detection-job", "detection-job.jar"),
    ]:
        with zipfile.ZipFile(ROOT / "packages" / module / "build/libs" / filename) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or not any(
                n.startswith("META-INF/LICENSE") for n in names
            ):
                raise ValueError("invalid_detection_artifact")
            if any("/fixtures/" in n or n.startswith("sigma/") for n in names):
                raise ValueError("unexpected_runtime_content")
    source = load_json(ROOT / "contracts/v1/examples/windows-security-4688.source.json")
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for case in cases:
            rule = {
                "title": "Original synthetic semantic case",
                "id": "70000000-0000-4000-8000-000000000002",
                "license": "Apache-2.0",
                "logsource": {"category": "process_creation"},
                "detection": case["detection"],
            }
            rule_path = folder / "rule.yml"
            rule_path.write_text(yaml.safe_dump(rule, allow_unicode=True))
            plan = compile_rules([rule_path], [source])
            (folder / "plan.json").write_bytes(encoded(plan))
            event = load_json(FIXTURES / "positive.event.json")
            for path, value in case["event"].items():
                parts = path.split(".")
                node = event
                for part in parts[:-1]:
                    node = node.setdefault(part, {})
                if value == {"absent": True}:
                    node.pop(parts[-1], None)
                else:
                    node[parts[-1]] = value
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
                if result.returncode == 0:
                    raise ValueError("expected_rejection_" + case["name"])
            elif result.returncode or json.loads(result.stdout)["counts"][case["expected"]] != 1:
                raise ValueError("semantic_failure_" + case["name"])
    print(f"PASS: {len(cases)} independent YAML-to-Java semantic cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java", action="store_true")
    check(parser.parse_args().java)
