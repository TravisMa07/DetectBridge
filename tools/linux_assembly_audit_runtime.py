"""Opt-in real audit checkpoint, deadline, required-sink and isolated replay qualification."""

import argparse
import base64
import copy
import json
import re
import traceback
import uuid
from pathlib import Path

from linux_assembly import (
    INPUT,
    Assembly,
    checkpoint_inventory,
    runtime_binding,
    wait_failure,
    wait_outputs,
)
from linux_assembly_audit_recording import (
    CATALOG,
    artifacts,
    expected_documents,
    prepared,
    verify_event,
)
from linux_assembly_cases import ROOT, digest, encoded
from linux_assembly_recorded import retain, retained_event
from linux_assembly_verify import Oracle, require
from stack import project_lock, run, save


class AuditOracle(Oracle):
    def __init__(self, config, binding, catalog):
        super().__init__(config, binding)
        self.catalog = catalog
        self.audit_groups = {}

    def reviewed_group(self, rows, group, closure):
        group = dict(group, closure=closure)
        expected = self.group(
            rows,
            closure,
            group["findings"],
            execution=self.catalog["execution"] if not group["findings"] else None,
        )
        key = (rows[0]["context"]["run_id"], expected["event_id"])
        self.audit_groups[key] = (copy.deepcopy(group), copy.deepcopy(rows))
        return expected

    def remainder(self, rows):
        for group in self.catalog["groups"]:
            if group["findings"]:
                self.reviewed_group(
                    [rows[i] for i in group["member_positions"]], group, "dataset_end"
                )
        for row, expected in zip(rows, self.catalog["records"]):
            if expected["disposition"] != "group_member":
                require(expected["disposition"] == "extraction_failed")
                self.diagnostic(row, "extraction_failed")

    def check(self, outputs, *, complete=True):
        ready = super().check(outputs, complete=complete)
        for kind, _, document in outputs:
            if kind == "event":
                key = (document["detectbridge"]["run_id"], document["event"]["id"])
                require(key in self.audit_groups)
                group, rows = self.audit_groups[key]
                verify_event(self.catalog, group, rows, document)
        return ready


def controls(rows, kind):
    ctx = rows[0]["context"]
    result = dict(
        version="1.0.0",
        kind=kind,
        control_id=str(uuid.uuid4()),
        run_id=ctx["run_id"],
        provenance=["recording:linux-audit-execve-lab-v1:reviewed-runtime-control"],
    )
    if kind == "source_boundary":
        result.update(
            source=ctx["source"],
            host_id=ctx["host_binding"]["host_id"],
            generation=ctx["source_generation"]["id"],
        )
    return result


def eligible_group(catalog):
    eligible = [group for group in catalog["groups"] if not group["findings"]]
    require(len(eligible) == 1)
    return eligible[0]


def open_group(inventory, expected, rows):
    expected_members = [
        dict(
            record_id=row["raw"]["record_id"],
            evidence_sha256=row["raw"]["evidence"]["sha256"],
            raw_sha256=digest(row["raw"]),
            context_sha256=digest(row["context"]),
        )
        for row in rows
    ]
    require(
        any(
            group["key"] == expected["key"] and group["members"] == expected_members
            for group in inventory["groups"]
        )
    )


def qualify(directory):
    catalog = json.loads(CATALOG.read_bytes())
    originals = artifacts(catalog, directory)  # Original integrity before runtime mutation.
    supplied = prepared(catalog, originals)
    expected_documents(catalog, supplied)  # Freeze exhaustive reviewed membership before Docker.
    rows = [dict(version="1.0.0", kind="record", **row) for row in supplied]
    selected = eligible_group(catalog)
    positions = selected["member_positions"]
    execution = [rows[i] for i in positions]
    remainder = [row for i, row in enumerate(rows) if i not in positions]
    project = "detectbridge-p12-audit-" + uuid.uuid4().hex[:12]
    test = Assembly(project)
    report = ROOT / ".cache/linux-assembly-reports" / (project + ".json")
    phase = "initialization"
    with project_lock(project):
        try:
            test.init()
            job = test.start()
            config = test.config()
            oracle = AuditOracle(config, runtime_binding(config), catalog)
            save(test.folder / "reviewed-catalog.json", catalog)

            def stage(name):
                nonlocal phase
                phase = name
                print(json.dumps(dict(phase=phase, project=project)), flush=True)

            def send(batch, fault=False):
                retain(test, oracle, batch)
                values = [encoded(row) for row in batch]
                if fault:
                    ipc = "".join(
                        json.dumps(
                            dict(sequence=i, key=None, value=base64.b64encode(value).decode())
                        )
                        + "\n"
                        for i, value in enumerate(values)
                    )
                    result = test.helper_run(
                        test.process_args("inject", INPUT), timeout=90, data=ipc
                    )
                    acks = [
                        json.loads(line)
                        for line in result.stdout.splitlines()
                        if json.loads(line).get("type") == "ack"
                    ]
                else:
                    acks = test.inject_rows(values)
                oracle.register(batch, acks)
                save(test.folder / "acknowledged-inputs.json", oracle.inputs)
                return acks

            stage("recorded_open_group_checkpoint_taskmanager_and_deadline")
            expected = oracle.reviewed_group(execution, selected, "timeout")
            acks = send(execution)
            test.wait_input_checkpoint(acks[-1]["offset"])
            cp = test.wait_checkpoint(job["job_id"])
            inventory = checkpoint_inventory(test, cp)
            open_group(inventory, expected, execution)
            save(test.folder / "open-group-checkpoint.json", inventory)
            run(["docker", "kill", project + "-taskmanager-1"])
            test.stack.compose("up", "-d", "taskmanager", profile="core")
            wait_outputs(test, oracle)
            oracle.remainder(rows)
            send([*remainder, controls(rows, "run_end")])
            wait_outputs(test, oracle)

            stage("recorded_eligible_event_sink_failure")
            replayed = copy.deepcopy(rows)
            replay_run = str(uuid.uuid4())
            for row in replayed:
                row["context"]["run_id"] = replay_run
            replay_execution = [replayed[i] for i in positions]
            expected_replay = oracle.reviewed_group(replay_execution, selected, "source_boundary")
            test.fault("event", "2")
            try:
                send([*replay_execution, controls(replayed, "source_boundary")], fault=True)
                wait_failure(test, job, "RecordTooLarge")
                cp_fault = test.rest("/jobs/" + job["job_id"] + "/checkpoints")["latest"][
                    "completed"
                ]
                inventory = checkpoint_inventory(test, cp_fault)
                save(test.folder / "blocked-event-checkpoint.json", inventory)
                eligible_intents = [
                    intent
                    for intent in inventory["outbox"]
                    if intent["kind"] == "event"
                    and intent["run_id"] == replay_run
                    and intent["key"] == expected_replay["event_id"]
                ]
                blocked = retained_event(dict(outbox=eligible_intents), oracle)
            finally:
                test.fault("event", "1")
            stage("recorded_checkpoint_restore_and_complete_replay")
            test.start(restore=cp_fault["external_path"])
            wait_outputs(test, oracle)
            oracle.remainder(replayed)
            send(
                [
                    *[row for i, row in enumerate(replayed) if i not in positions],
                    controls(replayed, "run_end"),
                ]
            )
            outputs = wait_outputs(test, oracle)
            first_run = rows[0]["context"]["run_id"]
            require(
                {key[1] for key in oracle.events if key[0] == first_run}
                == {key[1] for key in oracle.events if key[0] == replay_run}
            )
            logical = {(kind, wire["key"], encoded(doc)) for kind, wire, doc in outputs}
            result = dict(
                status="qualified",
                project=project,
                recording=catalog["id"],
                catalog_sha256=digest(catalog),
                processing_metadata=catalog["processing_metadata"],
                inputs=len(oracle.inputs),
                groups=len(oracle.groups),
                events=len(oracle.events),
                diagnostics=len(oracle.diagnostics),
                logical_outputs=len(logical),
                physical_outputs=len(outputs),
                physical_duplicates=len(outputs) - len(logical),
                open_group_checkpoint=cp["id"],
                blocked_event_checkpoint=cp_fault["id"],
                blocked_event=blocked,
                original_run_id=first_run,
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
            if re.fullmatch(r"[A-Za-z0-9_]+", str(error)):
                diagnostic["category"] = str(error)
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
        print('{"status":"failed","category":"recorded_audit_runtime_qualification_failed"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
