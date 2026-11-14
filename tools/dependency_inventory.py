"""Reconcile the reviewed Java inventory with committed Gradle dependency locks."""

import argparse
import json
from datetime import date
from pathlib import Path

from check_contracts import load_json

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "docs/transport-dependencies.json"


def artifacts():
    result: dict[str, list[dict]] = {}
    paths = [*ROOT.glob("*-gradle.lockfile"), *ROOT.glob("packages/transport-*/gradle.lockfile")]
    for path in sorted(paths):
        for line in path.read_text().splitlines():
            if not line or line.startswith(("#", "empty=")):
                continue
            coordinate, configurations = line.split("=", 1)
            if len(coordinate.split(":")) != 3:
                raise ValueError("invalid_locked_coordinate")
            result.setdefault(coordinate, []).append(
                {
                    "lockfile": str(path.relative_to(ROOT)),
                    "configurations": configurations.split(","),
                }
            )
    return [{"coordinate": name, "uses": uses} for name, uses in sorted(result.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        review = load_json(REVIEW)
        current = artifacts()
        if args.write:
            review["artifacts"] = current
            REVIEW.write_text(json.dumps(review, indent=2) + "\n")
        elif review.get("artifacts") != current:
            raise ValueError("dependency_review_outdated")
        date.fromisoformat(review["reviewed_on"])
        if not isinstance(review.get("remaining_image_findings"), list):
            raise ValueError("missing_review_disposition")
    except Exception:
        print("FAIL: Java dependency inventory needs explicit review")
        return 1
    print(f"PASS: {len(current)} reviewed locked Java coordinates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
