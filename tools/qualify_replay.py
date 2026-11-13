"""Opt-in recorded-data qualification; prints administrative totals only."""

import hashlib
import json

from check_contracts import load_json
from check_datasets import load_catalog
from datasets import CACHE, object_path, verify_file
from replay import RUNS, execute, start


def records(run_id):
    for path in sorted((RUNS / run_id / "segments").glob("*/records.ndjson")):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                value = json.loads(line)
                if value["type"] == "record":
                    yield value


def qualify():
    catalog = load_catalog()
    ids = list(catalog)
    expected = sum(m["framing"]["record_count"] for m in catalog.values())
    runs = [start(ids, rate=None) for _ in range(2)]
    if runs[0]["run_id"] == runs[1]["run_id"]:
        raise ValueError("run_collision")
    identities = []
    for result in runs:
        if result["status"] != "completed" or result["next_sequence"] != expected + len(ids) + 1:
            raise ValueError("qualification_count_failure")
        if execute(result["run_id"]) != result:
            raise ValueError("completed_resume_changed")
        found = []
        for envelope in records(result["run_id"]):
            raw = envelope["record"]
            manifest = catalog[envelope["dataset_id"]]
            evidence = raw["evidence"]
            byte_range = evidence["reference"]["byte_range"]
            with object_path(CACHE, manifest["payload"]).open("rb") as stream:
                stream.seek(byte_range["offset"])
                data = stream.read(byte_range["length"])
            if (
                len(data) != byte_range["length"]
                or hashlib.sha256(data).hexdigest() != evidence["sha256"]
            ):
                raise ValueError("qualification_range_failure")
            found.append((raw["record_id"], raw["first_observed"], raw))
        if len(found) != expected:
            raise ValueError("qualification_record_count_failure")
        identities.append(found)
        config = load_json(RUNS / result["run_id"] / "manifest.json")
        for entry in config["datasets"]:
            verify_file(
                object_path(CACHE, entry["manifest"]["payload"]), entry["manifest"]["payload"]
            )
    if identities[0] != identities[1]:
        raise ValueError("capture_identity_changed")
    print(
        json.dumps(
            {"status": "qualified", "records_per_run": expected, "runs": runs}, sort_keys=True
        )
    )


def main():
    try:
        qualify()
    except Exception:
        print(json.dumps({"status": "failed", "category": "recorded_replay_qualification_failure"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
