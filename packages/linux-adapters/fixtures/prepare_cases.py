"""Compile original synthetic P12 rules through the real locked P10 compiler."""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from detection_compile import compile_rules, encoded  # noqa: E402
from detection_mapping import sha  # noqa: E402

MODULE = ROOT / "packages/linux-adapters"


def prepare():
    sources = [
        json.loads(p.read_text()) for p in sorted((MODULE / "contracts").glob("*.source.json"))
    ]
    mappings = [
        json.loads(p.read_text()) for p in sorted((MODULE / "contracts").glob("*.mapping.json"))
    ]
    original = json.loads((ROOT / "contracts/detection/v2/fixtures/candidates.json").read_text())[0]
    destination = ROOT / ".cache/linux-adapters/plans"
    destination.mkdir(parents=True, exist_ok=True)
    for rule in sorted((MODULE / "fixtures/rules").glob("*.yml")):
        # Explicit derivative lineage retains the original synthetic bytes and provenance.
        candidate = copy.deepcopy(original)
        candidate["rule_id"] = next(
            line[4:] for line in rule.read_text().splitlines() if line.startswith("id: ")
        )
        candidate["revision"] = sha(rule.read_bytes())
        candidate["modifications"] = [
            {
                "input_sha256": original["original_sha256"],
                "output_sha256": candidate["revision"],
                "description": "Original synthetic P12 derivative at "
                + str(rule.relative_to(ROOT)),
            }
        ]
        plan = compile_rules([rule], sources, mappings=mappings, provenance=[candidate])
        (destination / (rule.stem + ".json")).write_bytes(encoded(plan) + b"\n")
    print("PASS: compiled original synthetic P12 plans; expectations are independent literals")


if __name__ == "__main__":
    prepare()
