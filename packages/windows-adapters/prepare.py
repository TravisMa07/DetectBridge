"""Compile original P11 synthetic rules against the parser-backed declarations."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from detection_compile import compile_rules  # noqa: E402


def prepare():
    directory = Path(__file__).resolve().parent
    paths = sorted((directory / "fixtures/rules").glob("*.yml"))
    import hashlib

    import yaml

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    provenance = []
    for path in paths:
        committed = subprocess.check_output(
            ["git", "show", f"{revision}:{path.relative_to(ROOT)}"], cwd=ROOT
        )
        if committed != path.read_bytes():
            raise ValueError("synthetic_rule_revision_not_committed")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        provenance.append(
            dict(
                version="1.0.0",
                rule_id=yaml.safe_load(path.read_bytes())["id"],
                revision=digest,
                kind="synthetic",
                repository="https://github.com/TravisMa07/DetectBridge",
                repository_revision=revision,
                path=str(path.relative_to(ROOT)),
                original_sha256=digest,
                authors=["DetectBridge contributors"],
                license="Apache-2.0",
                notices=[],
                modifications=[],
            )
        )
    profiles = directory / "profiles"
    sources = [
        json.loads((profiles / f"{f}.source.json").read_text()) for f in ("security", "sysmon")
    ]
    mappings = [
        json.loads((profiles / f"{f}.mapping.json").read_text()) for f in ("security", "sysmon")
    ]
    plan = compile_rules(paths, sources, mappings=mappings, provenance=provenance)
    output = ROOT / ".cache/windows"
    output.mkdir(parents=True, exist_ok=True)
    (output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    prepare()
