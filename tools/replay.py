"""Local resumable replay. Raw evidence is immutable; no Kafka or source parsing."""

import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
import shutil
import signal
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from check_contracts import load_json
from check_datasets import CATALOG, MAX_BATCH, load_catalog, manifest_errors
from check_replay import ReplayValidator
from contract_identity import identity_hash, record_id
from datasets import CACHE as DATA_CACHE
from datasets import object_path, process, sha256_file, verify_file
from replay_time import timestamp_ns, timestamp_text

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".cache/replay"
CAPTURES = ROOT / ".cache/replay-captures"
MAX_RECORDS = 100_000
MAX_RECORD = 1024 * 1024
MAX_SEGMENT = 8 * 1024 * 1024
SEGMENT_RECORDS = 1000
MAX_OUTPUT = 512 * 1024 * 1024
MAX_INDEX = 16 * 1024 * 1024
VERSION = "1.0.0"


def encoded(value):
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path, value):
    descriptor, name = tempfile.mkstemp(prefix=".partial-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded(value))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def locked(path, blocking=False):
    if path.is_symlink():
        raise ValueError("unsafe_lock")
    with path.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise ValueError("run_already_locked") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def source_identity(manifest):
    return {
        "namespace": "dataset:splunk/attack_data",
        "instance": manifest["capture"]["scenario_id"] + ":" + manifest["framing"]["id"],
    }


def bounded_json(path, limit=16 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("unsafe_or_oversized_state")
    return load_json(path)


def capture(manifest, folder, validator):
    folder.mkdir(parents=True, exist_ok=True)
    source = source_identity(manifest)
    key = identity_hash(
        [
            source["namespace"],
            source["instance"],
            manifest["payload"]["sha256"],
            manifest["framing"]["id"],
        ]
    ).split(":")[1]
    path = folder / (key + ".json")
    with locked(folder / (key + ".lock"), blocking=True):
        if path.exists():
            value = bounded_json(path, 65536)
        else:
            value = {
                "contract_version": VERSION,
                "source": source,
                "artifact_sha256": manifest["payload"]["sha256"],
                "framing": manifest["framing"]["id"],
                "first_observed": datetime.now(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z"),
            }
            validator.require("capture", value)
            atomic_json(path, value)
        validator.require("capture", value)
        if (
            value["source"] != source
            or value["artifact_sha256"] != manifest["payload"]["sha256"]
            or value["framing"] != manifest["framing"]["id"]
        ):
            raise ValueError("capture_identity_mismatch")
        return value


def timing_lookup(index, selections, validator):
    validator.require("timing-index", index)
    selected = {m["id"]: m for m in selections}
    datasets = set()
    lookup = {}
    for entry in index["datasets"]:
        ident = entry["dataset_id"]
        if ident not in selected or ident in datasets:
            raise ValueError("unknown_or_duplicate_timing_dataset")
        datasets.add(ident)
        manifest = selected[ident]
        if (
            entry["artifact_sha256"] != manifest["payload"]["sha256"]
            or entry["framing"] != manifest["framing"]["id"]
        ):
            raise ValueError("timing_artifact_mismatch")
        for item in entry["timestamps"]:
            position = item["position"]
            key = (ident, position)
            if position >= manifest["framing"]["record_count"] or key in lookup:
                raise ValueError("invalid_timing_position")
            timestamp_ns(item["timestamp"])
            lookup[key] = item["timestamp"]
    return lookup


def checked_inputs(config, data_cache):
    count, size = 0, 0
    for entry in config["datasets"]:
        manifest = entry["manifest"]
        schema = load_json(CATALOG / "manifest.schema.json")
        if manifest_errors(manifest, schema):
            raise ValueError("invalid_frozen_dataset_manifest")
        if digest(manifest) != entry["manifest_sha256"]:
            raise ValueError("frozen_manifest_mismatch")
        report = process(manifest, data_cache, fetch=False)
        count += report["framing"]["record_count"]
        size += manifest["payload"]["size_bytes"] + sum(
            r["size_bytes"] for r in manifest["provenance"]
        )
        if count > MAX_RECORDS or size > MAX_BATCH:
            raise ValueError("replay_input_limit")
        if any(record["length"] > MAX_RECORD for record in report["framing"]["records"]):
            raise ValueError("replay_record_limit")
        if (
            entry["capture"]["source"] != source_identity(manifest)
            or entry["capture"]["artifact_sha256"] != manifest["payload"]["sha256"]
            or entry["capture"]["framing"] != manifest["framing"]["id"]
        ):
            raise ValueError("frozen_capture_mismatch")
    return count


class Pacer:
    def __init__(self, rate, clock=time.monotonic, sleep=time.sleep):
        self.period = None if rate is None else 1 / rate
        self.clock, self.sleep = clock, sleep
        self.next = None

    def wait(self):
        if self.period is None:
            return
        if self.next is not None:
            while self.clock() < self.next:
                self.sleep(min(0.1, self.next - self.clock()))
        self.next = self.clock() + self.period


def envelopes(config, lookup, data_cache):
    sequence, total = 0, 0
    for entry in config["datasets"]:
        manifest, observed = entry["manifest"], entry["capture"]["first_observed"]
        source = entry["capture"]["source"]
        ident = manifest["id"]
        path = object_path(data_cache, manifest["payload"])
        offset, count = 0, 0
        with path.open("rb") as stream:
            for position, raw in enumerate(stream):
                if len(raw) > MAX_RECORD:
                    raise ValueError("replay_record_limit")
                cursor = {
                    "kind": "dataset",
                    "artifact_sha256": manifest["payload"]["sha256"],
                    "position": position,
                }
                original = lookup.get((ident, position), observed)
                effective = (
                    original
                    if config["time_mode"] == "preserve"
                    else timestamp_text(timestamp_ns(original) + int(config["shift_ns"]))
                )
                record = {
                    "contract_version": VERSION,
                    "record_id": record_id(source, cursor),
                    "source": source,
                    "cursor": cursor,
                    "first_observed": observed,
                    "evidence": {
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "encoding": "utf-8",
                        "media_type": "application/xml"
                        if ident.startswith("windows-")
                        else "text/plain",
                        "reference": {
                            "uri": "urn:sha256:" + manifest["payload"]["sha256"],
                            "object_sha256": manifest["payload"]["sha256"],
                            "byte_range": {"offset": offset, "length": len(raw)},
                        },
                    },
                }
                yield {
                    "contract_version": VERSION,
                    "type": "record",
                    "run_id": config["run_id"],
                    "sequence": sequence,
                    "dataset_id": ident,
                    "record": record,
                    "timing": {
                        "original_time": original,
                        "effective_time": effective,
                        "basis": "timing_index"
                        if (ident, position) in lookup
                        else "first_observed",
                    },
                }
                offset += len(raw)
                count += 1
                total += 1
                sequence += 1
        verify_file(path, manifest["payload"])
        if count != manifest["framing"]["record_count"]:
            raise ValueError("input_count_changed")
        yield {
            "contract_version": VERSION,
            "type": "dataset_end",
            "run_id": config["run_id"],
            "sequence": sequence,
            "dataset_id": ident,
            "record_count": count,
        }
        sequence += 1
    yield {
        "contract_version": VERSION,
        "type": "run_end",
        "run_id": config["run_id"],
        "sequence": sequence,
        "dataset_count": len(config["datasets"]),
        "record_count": total,
    }


def earliest_time(entries, lookup):
    values = list(lookup.values())
    for entry in entries:
        ident = entry["manifest"]["id"]
        if (
            sum(1 for dataset, _ in lookup if dataset == ident)
            < entry["manifest"]["framing"]["record_count"]
        ):
            values.append(entry["capture"]["first_observed"])
    return min(values, key=timestamp_ns)


def load_run(folder, validator):
    config = bounded_json(folder / "manifest.json")
    validator.require("run-manifest", config)
    if folder.name != config["run_id"] or (
        folder / "manifest.sha256"
    ).read_text().strip() != digest(config):
        raise ValueError("run_manifest_mismatch")
    selections = [entry["manifest"] for entry in config["datasets"]]
    if len({m["id"] for m in selections}) != len(selections):
        raise ValueError("duplicate_selection")
    path = folder / "timing-index.json"
    if config["timing_index_sha256"] is None:
        if path.exists():
            raise ValueError("unexpected_timing_index")
        index = {"contract_version": VERSION, "datasets": []}
    else:
        if (
            not path.is_file()
            or path.stat().st_size > MAX_INDEX
            or sha256_file(path) != config["timing_index_sha256"]
        ):
            raise ValueError("timing_index_changed")
        index = bounded_json(path)
    lookup = timing_lookup(index, selections, validator)
    if config["time_mode"] == "preserve":
        if config["anchor"] is not None or config["shift_ns"] != "0":
            raise ValueError("invalid_preserve_configuration")
    else:
        if config["anchor"] is None:
            raise ValueError("missing_shift_anchor")
        earliest = earliest_time(config["datasets"], lookup)
        if int(config["shift_ns"]) != timestamp_ns(config["anchor"]) - timestamp_ns(earliest):
            raise ValueError("shift_configuration_changed")
    return config, lookup


def scan_segments(folder, config, lookup, data_cache, validator):
    expected = iter(envelopes(config, lookup, data_cache))
    states = [(0, 0)]
    next_sequence, total_bytes, completed = 0, 0, False
    segments = sorted(
        p for p in (folder / "segments").iterdir() if not p.name.startswith(".partial-")
    )
    for number, segment in enumerate(segments):
        if segment.name != f"{number:08d}" or segment.is_symlink() or not segment.is_dir():
            raise ValueError("noncontiguous_segments")
        if {p.name for p in segment.iterdir()} != {"records.ndjson", "commit.json"}:
            raise ValueError("invalid_segment_contents")
        meta = bounded_json(segment / "commit.json", 65536)
        validator.require("segment", meta)
        payload = segment / "records.ndjson"
        if (
            payload.is_symlink()
            or meta["manifest_sha256"] != digest(config)
            or meta["first_sequence"] != next_sequence
            or meta["bytes"] != payload.stat().st_size
            or meta["sha256"] != sha256_file(payload)
        ):
            raise ValueError("segment_integrity_failure")
        count = 0
        with payload.open("rb") as stream:
            for line in stream:
                if len(line) > MAX_SEGMENT or completed:
                    raise ValueError("invalid_committed_output")
                wanted = next(expected, None)
                if wanted is None or line != encoded(wanted):
                    raise ValueError("committed_output_mismatch")
                validator.require("envelope", wanted)
                completed = wanted["type"] == "run_end"
                next_sequence += 1
                count += 1
        if count != meta["count"]:
            raise ValueError("segment_count_mismatch")
        total_bytes += meta["bytes"]
        if total_bytes > MAX_OUTPUT:
            raise ValueError("replay_output_limit")
        states.append((next_sequence, total_bytes))
    checkpoint = folder / "checkpoint.json"
    if checkpoint.exists():
        value = bounded_json(checkpoint, 65536)
        validator.require("checkpoint", value)
        prefix = value["segments"]
        if (
            value["manifest_sha256"] != digest(config)
            or prefix >= len(states)
            or (value["next_sequence"], value["bytes"]) != states[prefix]
            or value["status"] == "completed"
            and (not completed or prefix != len(segments))
        ):
            raise ValueError("checkpoint_inconsistent")
    return {
        "next_sequence": next_sequence,
        "segments": len(segments),
        "bytes": total_bytes,
        "status": "completed" if completed else "interrupted",
    }


def checkpoint(folder, config, state):
    atomic_json(
        folder / "checkpoint.json",
        {"contract_version": VERSION, "manifest_sha256": digest(config), **state},
    )


def publish(folder, config, state, lines, hook):
    segment = folder / "segments" / f"{state['segments']:08d}"
    temporary = Path(tempfile.mkdtemp(prefix=".partial-", dir=segment.parent))
    payload = b"".join(lines)
    with (temporary / "records.ndjson").open("wb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    meta = {
        "contract_version": VERSION,
        "manifest_sha256": digest(config),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "first_sequence": state["next_sequence"],
        "count": len(lines),
        "bytes": len(payload),
    }
    atomic_json(temporary / "commit.json", meta)
    hook("before_segment_publish")
    os.rename(temporary, segment)
    sync_directory(segment.parent)
    hook("after_segment_publish")
    state.update(
        next_sequence=state["next_sequence"] + len(lines),
        segments=state["segments"] + 1,
        bytes=state["bytes"] + len(payload),
        status="running",
    )
    checkpoint(folder, config, state)
    hook("after_checkpoint")


def execute(
    run_id,
    runs=RUNS,
    data_cache=DATA_CACHE,
    inspect=False,
    hook=lambda _: None,
    pacer_factory=Pacer,
):
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("invalid_run_id")
    folder = runs / run_id
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("missing_or_unsafe_run")
    validator = ReplayValidator()
    with locked(folder / ".run.lock"):
        config, lookup = load_run(folder, validator)
        checked_inputs(config, data_cache)
        state = scan_segments(folder, config, lookup, data_cache, validator)
        if inspect:
            return {"run_id": run_id, **state}
        for path in (folder / "segments").glob(".partial-*"):
            if path.is_symlink():
                raise ValueError("unsafe_partial_segment")
            shutil.rmtree(path)
        if state["status"] == "completed":
            desired = {"contract_version": VERSION, "manifest_sha256": digest(config), **state}
            if (
                not (folder / "checkpoint.json").exists()
                or bounded_json(folder / "checkpoint.json", 65536) != desired
            ):
                checkpoint(folder, config, state)
            return {"run_id": run_id, **state}
        pacer = pacer_factory(config["rate"])
        committed = state["next_sequence"]
        lines: list[bytes] = []
        size = 0
        try:
            for envelope in envelopes(config, lookup, data_cache):
                if envelope["sequence"] < committed:
                    continue
                validator.require("envelope", envelope)
                line = encoded(envelope)
                if len(line) > MAX_SEGMENT or state["bytes"] + size + len(line) > MAX_OUTPUT:
                    raise ValueError("replay_output_limit")
                if lines and (len(lines) >= SEGMENT_RECORDS or size + len(line) > MAX_SEGMENT):
                    publish(folder, config, state, lines, hook)
                    lines, size = [], 0
                if envelope["type"] == "record":
                    pacer.wait()
                lines.append(line)
                size += len(line)
            if lines:
                publish(folder, config, state, lines, hook)
            state["status"] = "completed"
            checkpoint(folder, config, state)
            return {"run_id": run_id, **state}
        except KeyboardInterrupt:
            state["status"] = "interrupted"
            checkpoint(folder, config, state)
            return {"run_id": run_id, **state}


def start(
    ids,
    catalog=None,
    runs=RUNS,
    captures=CAPTURES,
    data_cache=DATA_CACHE,
    timing_path=None,
    mode="preserve",
    anchor=None,
    rate=100,
    run_id=None,
    hook=lambda _: None,
    pacer_factory=Pacer,
):
    catalog = load_catalog() if catalog is None else catalog
    if not ids or len(ids) != len(set(ids)) or any(ident not in catalog for ident in ids):
        raise ValueError("invalid_selection")
    if rate is not None and (not math.isfinite(rate) or not 0 < rate <= 10000):
        raise ValueError("invalid_replay_rate")
    if mode not in ("preserve", "shift") or (mode == "shift") != (anchor is not None):
        raise ValueError("invalid_time_mode")
    validator = ReplayValidator()
    selections = [copy.deepcopy(catalog[ident]) for ident in ids]
    # Preflight before assigning capture observations or creating run output.
    total, size = 0, 0
    for manifest in selections:
        report = process(manifest, data_cache, fetch=False)
        total += report["framing"]["record_count"]
        size += manifest["payload"]["size_bytes"] + sum(
            r["size_bytes"] for r in manifest["provenance"]
        )
        if (
            total > MAX_RECORDS
            or size > MAX_BATCH
            or any(r["length"] > MAX_RECORD for r in report["framing"]["records"])
        ):
            raise ValueError("replay_input_limit")
    raw_index = None
    if timing_path is not None:
        if timing_path.stat().st_size > MAX_INDEX:
            raise ValueError("timing_index_limit")
        raw_index = timing_path.read_bytes()
        index = load_json(timing_path)
    else:
        index = {"contract_version": VERSION, "datasets": []}
    lookup = timing_lookup(index, selections, validator)
    entries = [
        {"manifest": m, "manifest_sha256": digest(m), "capture": capture(m, captures, validator)}
        for m in selections
    ]
    shift = (
        0
        if mode == "preserve"
        else timestamp_ns(anchor) - timestamp_ns(earliest_time(entries, lookup))
    )
    run_id = str(uuid.uuid4()) if run_id is None else run_id
    if str(uuid.UUID(run_id)) != run_id:
        raise ValueError("invalid_run_id")
    config = {
        "contract_version": VERSION,
        "tool_version": VERSION,
        "run_id": run_id,
        "datasets": entries,
        "timing_index_sha256": None if raw_index is None else hashlib.sha256(raw_index).hexdigest(),
        "time_mode": mode,
        "anchor": anchor,
        "shift_ns": str(shift),
        "rate": rate,
    }
    validator.require("run-manifest", config)
    if len(encoded(config)) > MAX_INDEX:
        raise ValueError("run_manifest_limit")
    output_size = 0
    for envelope in envelopes(config, lookup, data_cache):
        line = encoded(envelope)
        output_size += len(line)
        if len(line) > MAX_SEGMENT or output_size > MAX_OUTPUT:
            raise ValueError("replay_output_limit")
    runs.mkdir(parents=True, exist_ok=True)
    folder = runs / run_id
    folder.mkdir()  # exclusive: never overwrite an existing run
    (folder / "segments").mkdir()
    atomic_json(folder / "manifest.json", config)
    (folder / "manifest.sha256").write_text(digest(config) + "\n")
    with (folder / "manifest.sha256").open("rb") as stream:
        os.fsync(stream.fileno())
    if raw_index is not None:
        with (folder / "timing-index.json").open("wb") as stream:
            stream.write(raw_index)
            stream.flush()
            os.fsync(stream.fileno())
    sync_directory(folder)
    sync_directory(runs)
    checkpoint(
        folder, config, {"next_sequence": 0, "segments": 0, "bytes": 0, "status": "prepared"}
    )
    return execute(run_id, runs, data_cache, hook=hook, pacer_factory=pacer_factory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("start")
    create.add_argument("ids", nargs="+")
    create.add_argument("--timing-index", type=Path)
    create.add_argument("--time-mode", choices=["preserve", "shift"], default="preserve")
    create.add_argument("--anchor")
    speed = create.add_mutually_exclusive_group()
    speed.add_argument("--rate", type=float, default=100)
    speed.add_argument("--unpaced", action="store_true")
    for name in ("resume", "inspect"):
        commands.add_parser(name).add_argument("run_id")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if args.command == "start":
            result = start(
                args.ids,
                timing_path=args.timing_index,
                mode=args.time_mode,
                anchor=args.anchor,
                rate=None if args.unpaced else args.rate,
            )
        else:
            result = execute(args.run_id, inspect=args.command == "inspect")
        print(json.dumps(result, sort_keys=True))
        return 130 if result["status"] == "interrupted" and args.command != "inspect" else 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "category": "replay_interrupted"}))
        return 130
    except Exception:
        # Library errors can contain log values/paths. Do not print exception text.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "category": "replay_validation_or_io_failure",
                    "hint": "Verify the run and cached inputs; use datasets.py fetch for missing evidence.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
