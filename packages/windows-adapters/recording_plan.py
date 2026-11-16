"""Compile and verify committed original rules for the controlled Windows capture."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from detection_compile import compile_rules  # noqa: E402

MODULE = Path(__file__).resolve().parent


def rule_inputs():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = sorted((MODULE / "recording/rules").glob("*.yml"))
    provenance = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if (
            subprocess.check_output(["git", "show", f"{revision}:{relative}"], cwd=ROOT)
            != path.read_bytes()
        ):
            raise ValueError("recording_rule_not_committed")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        provenance.append(
            dict(
                version="1.0.0",
                rule_id=yaml.safe_load(path.read_bytes())["id"],
                revision=digest,
                kind="synthetic",
                repository="https://github.com/TravisMa07/DetectBridge",
                repository_revision=revision,
                path=relative,
                original_sha256=digest,
                authors=["DetectBridge contributors"],
                license="Apache-2.0",
                notices=[],
                modifications=[],
            )
        )
    return paths, provenance


def prepare():
    paths, provenance = rule_inputs()
    sources = [
        json.loads((MODULE / f"profiles/{f}.source.json").read_bytes())
        for f in ("security", "sysmon")
    ]
    mappings = [
        json.loads((MODULE / f"profiles/{f}.mapping.json").read_bytes())
        for f in ("security", "sysmon")
    ]
    return compile_rules(paths, sources, mappings=mappings, provenance=provenance)


def validate_rules(plan):
    expected = prepare()
    # Compilation is deterministic for the pinned source revision. Complete tree,
    # source snapshots and provenance must agree, not only outcome counts.
    if plan != expected:
        raise ValueError("controlled_recording_plan_mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(prepare(), ensure_ascii=False) + "\n")
