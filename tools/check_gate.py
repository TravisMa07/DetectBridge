"""Fail closed unless required jobs and classified applicability agree."""

import json
import os

EXPECTED = {"classify-changes", "repository-hygiene", "secret-scan", "toolchain-verification"}


def gate_passes(needs):
    if not isinstance(needs, dict) or set(needs) != EXPECTED:
        return False
    for name in EXPECTED - {"toolchain-verification"}:
        if not isinstance(needs[name], dict) or needs[name].get("result") != "success":
            return False
    value = needs["classify-changes"].get("outputs", {}).get("toolchains")
    if value not in ("true", "false"):
        return False
    return needs["toolchain-verification"].get("result") == (
        "success" if value == "true" else "skipped"
    )


if __name__ == "__main__":
    try:
        passed = gate_passes(json.loads(os.environ.get("NEEDS_JSON", "{}")))
    except (ValueError, TypeError):
        passed = False
    print("Required checks passed." if passed else "Required checks failed or did not complete.")
    raise SystemExit(0 if passed else 1)
