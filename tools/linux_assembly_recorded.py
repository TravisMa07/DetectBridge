"""Opt-in real OpenSSH9 checkpoint qualification; local evidence is never a CI fixture."""

import argparse
import base64
import copy
import importlib.util
import json
import re
import traceback
import uuid
from functools import cache
from pathlib import Path

from linux_assembly import (
    INPUT,
    Assembly,
    checkpoint_inventory,
    runtime_binding,
    wait_failure,
    wait_outputs,
)
from linux_assembly_cases import ROOT, digest, encoded
from linux_assembly_verify import Oracle, require
from stack import project_lock, save


@cache
def recording_verifier():
    path = ROOT / "packages/linux-adapters/recording/qualify.py"
    spec = importlib.util.spec_from_file_location("reviewed_auth_qualification", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reviewed_rows(directory, destination):
    """Rehash every original before creating envelopes; no runtime/evaluator oracle."""
    verifier = recording_verifier()
    catalog = json.loads(verifier.CATALOG.read_bytes())
    originals = verifier.artifacts(catalog, directory)
    verifier.prepare(catalog, originals, destination)
    rows = [
        dict(version="1.0.0", kind="record", **json.loads(line))
        for line in destination.read_bytes().splitlines()
    ]
    return catalog, rows


def expectations(oracle, rows, catalog):
    require(len(rows) == len(catalog["expectations"]))
    for row, expected in zip(rows, catalog["expectations"]):
        require(row["raw"]["evidence"]["sha256"] == expected["sha256"])
        if expected["disposition"] == "normalized":
            oracle.auth(row, expectation=expected)
        else:
            require(expected["disposition"] == "unsupported_source")
            oracle.diagnostic(row, "unsupported_source")


def retained_event(inventory, oracle):
    """Require the pending intent to bind an independently expected original event."""
    for intent in inventory["outbox"]:
        if intent["kind"] != "event":
            continue
        key = (intent["run_id"], intent["key"])
        require(key in oracle.events)
        rows = oracle.events[key]["rows"]
        require(
            intent["members"]
            == [
                dict(
                    record_id=row["raw"]["record_id"],
                    evidence_sha256=row["raw"]["evidence"]["sha256"],
                )
                for row in rows
            ]
        )
        return intent
    require(False)


def retain(test, oracle, rows):
    """Retain originals and independently specified outcomes before Kafka admission."""
    with (test.folder / "independent-inputs.ndjson").open("ab") as original:
        for row in rows:
            original.write(encoded(row) + b"\n")
    save(
        test.folder / "independent-expectations.json",
        dict(
            events=[
                dict(run=key[0], id=key[1], expected=value) for key, value in oracle.events.items()
            ],
            diagnostics=list(oracle.diagnostics.values()),
        ),
    )


def qualify(directory):
    # Validate all original artifacts before any Docker initialization or publication.
    project = "detectbridge-p12-recorded-" + uuid.uuid4().hex[:12]
    reports = ROOT / ".cache/linux-assembly-reports"
    reports.mkdir(parents=True, exist_ok=True)
    report = reports / (project + ".json")
    prepared = reports / (project + "-input.ndjson")
    catalog, rows = reviewed_rows(directory, prepared)
    test = Assembly(project)
    phase = "initialization"
    with project_lock(project):
        try:
            test.init()
            job = test.start()
            config = test.config()
            oracle = Oracle(config, runtime_binding(config))
            expectations(oracle, rows, catalog)
            retain(test, oracle, rows)
            save(test.folder / "reviewed-catalog.json", catalog)
            phase = "recorded_event_sink_failure"
            print(json.dumps(dict(phase=phase, project=project)), flush=True)
            # Fault only after the job is bound to healthy topic configuration.
            test.fault("event", "2")
            try:
                # inject_rows checks healthy destination policy. Use the same
                # acknowledged publisher under the deliberately verified sink fault.
                ipc = "".join(
                    json.dumps(
                        dict(sequence=i, key=None, value=base64.b64encode(encoded(row)).decode())
                    )
                    + "\n"
                    for i, row in enumerate(rows)
                )
                response = test.helper_run(test.process_args("inject", INPUT), timeout=90, data=ipc)
                acks = [
                    json.loads(line)
                    for line in response.stdout.splitlines()
                    if '"type":"ack"' in line or '"type": "ack"' in line
                ]
                oracle.register(rows, acks)
                wait_failure(test, job, "RecordTooLarge")
                cp = test.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"]["completed"]
                inventory = checkpoint_inventory(test, cp)
                save(test.folder / "recorded-checkpoint-inventory.json", inventory)
                blocked = retained_event(inventory, oracle)
            finally:
                test.fault("event", "1")
            phase = "recorded_checkpoint_restore"
            print(json.dumps(dict(phase=phase, project=project)), flush=True)
            test.start(restore=cp["external_path"])
            wait_outputs(test, oracle)
            phase = "isolated_recorded_replay"
            print(json.dumps(dict(phase=phase, project=project)), flush=True)
            replayed = copy.deepcopy(rows)
            replay_run = str(uuid.uuid4())
            for row in replayed:
                row["context"]["run_id"] = replay_run
            expectations(oracle, replayed, catalog)
            retain(test, oracle, replayed)
            oracle.register(replayed, test.inject_rows([encoded(row) for row in replayed]))
            outputs = wait_outputs(test, oracle)
            logical = {(kind, wire["key"], encoded(doc)) for kind, wire, doc in outputs}
            result = dict(
                status="qualified",
                project=project,
                recording=catalog["id"],
                catalog_sha256=digest(catalog),
                inputs=len(oracle.inputs),
                events=len(oracle.events),
                diagnostics=len(oracle.diagnostics),
                logical_outputs=len(logical),
                physical_outputs=len(outputs),
                physical_duplicates=len(outputs) - len(logical),
                failure_marker="RecordTooLarge",
                retained_checkpoint=cp["id"],
                retained_event=blocked,
                replay_run_id=replay_run,
                bundle=config["bundle"],
            )
            save(report, result)
            return result
        except BaseException as error:
            diagnostic = dict(
                status="failed",
                phase=phase,
                project=project,
                error_type=type(error).__name__,
                locations=[
                    Path(frame.filename).name + ":" + str(frame.lineno)
                    for frame in traceback.extract_tb(error.__traceback__)[-4:]
                ],
            )
            if re.fullmatch(r"[a-z0-9_]+", str(error)):
                diagnostic["category"] = str(error)
            try:
                current = test.latest_job()
                if current:
                    checkpoints = test.rest("/jobs/" + current["job_id"] + "/checkpoints")
                    completed = checkpoints.get("latest", {}).get("completed")
                    if completed:
                        observed = checkpoint_inventory(test, completed)
                        save(test.folder / "failure-checkpoint-inventory.json", observed)
                        diagnostic["last_completed_checkpoint"] = completed["id"]
            except Exception as observation_error:
                diagnostic["observation_error_type"] = type(observation_error).__name__
            save(report, diagnostic)
            raise
        finally:
            if (test.stack.folder / "state.json").exists():
                try:
                    test.stack.down()
                finally:
                    test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(qualify(args.directory)))
    except Exception:
        # Never print arbitrary exception text, source fields or original payloads.
        print('{"status":"failed","category":"recorded_assembly_qualification_failed"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
