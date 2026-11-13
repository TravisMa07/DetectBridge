"""Fail closed unless all required jobs and classified applicability agree."""

import json
import os

CONDITIONAL = {"toolchain-verification": "toolchains", "local-stack-verification": "stack"}
EXPECTED = {"classify-changes", "repository-hygiene", "secret-scan", *CONDITIONAL}


def gate_passes(needs):
    if not isinstance(needs, dict) or set(needs) != EXPECTED:
        return False
    for name in EXPECTED - CONDITIONAL.keys():
        if not isinstance(needs[name], dict) or needs[name].get("result") != "success":
            return False
    outputs = needs["classify-changes"].get("outputs", {})
    for job, field in CONDITIONAL.items():
        applicable = outputs.get(field)
        if applicable not in ("true", "false") or not isinstance(needs[job], dict):
            return False
        if needs[job].get("result") != ("success" if applicable == "true" else "skipped"):
            return False
    return True


if __name__ == "__main__":
    try:
        passed = gate_passes(json.loads(os.environ.get("NEEDS_JSON", "{}")))
    except (ValueError, TypeError):
        passed = False
    print("Required checks passed." if passed else "Required checks failed or did not complete.")
    raise SystemExit(0 if passed else 1)
