"""Actual isolated two-worker P15b1 qualification against frozen independent source truth."""

import argparse
import base64
import copy
import json
import os
import platform
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from lifecycle import Store, checked
from lifecycle_runtime_cases import (
    AUTHORITY,
    DEPLOYMENT,
    ROOT,
    WORKERS,
    Oracle,
    check_packet,
    digest,
    document,
    encoded,
    phase_cases,
    prepare,
    require,
    sha,
)

REQUIRED = (
    "core_two_worker_a_b_a",
    "mixed_workers",
    "publisher_uncertainty",
    "registered_replacement",
    "broker_outage",
    "required_sink_failure",
    "old_outbox_new_selection",
    "open_group_closure_selection",
    "partial_ack_recovery",
    "aborted_checkpoint_ack",
    "signed_invalid_messages",
    "signed_hostile_ast",
    "finite_backpressure",
    "retained_versions",
)


SCENARIO_GROUPS = {
    "all": REQUIRED,
    "core": ("core_two_worker_a_b_a", "mixed_workers"),
    "production-faults": (
        "publisher_uncertainty",
        "registered_replacement",
        "broker_outage",
        "required_sink_failure",
    ),
    "pressure": ("old_outbox_new_selection", "finite_backpressure"),
    "open-group": ("open_group_closure_selection",),
    "partial-recovery": ("partial_ack_recovery",),
    "checkpoint-timeout": ("aborted_checkpoint_ack",),
    "invalid-messages": ("signed_invalid_messages",),
    "hostile-ast": ("signed_hostile_ast",),
    "retention": ("retained_versions",),
}


def scenario_outcome(scenario_group, coverage):
    """Report arithmetic only; passing independent attempts never composes a full gate."""
    missing_selected = sorted(set(SCENARIO_GROUPS[scenario_group]) - set(coverage))
    require(not missing_selected, "selected_scenarios_unqualified")
    return dict(
        status="passed" if scenario_group == "all" else "partial_passed",
        full_gate=scenario_group == "all",
        executed_scenarios=sorted(coverage),
        unqualified_required_scenarios=sorted(set(REQUIRED) - set(coverage)),
    )


def expected_bindings(runtime, registration):
    """Independent documented preimages; do not call controller binding implementation."""
    common = {
        key: runtime.config[key]
        for key in (
            "version",
            "deployment_id",
            "authority_id",
            "authority_key_sha256",
            "runtime_sha256",
            "producer_sha256",
            "image",
            "compatibility_sha256",
            "limits",
            "validator",
        )
    }
    common["cluster_id"] = runtime.state["broker"]["cluster_id"]
    common["topics"] = runtime.state["broker"]["topics"]
    shared = digest(common)
    stable = digest(
        dict(
            version="1.0.0",
            runtime_binding_sha256=shared,
            worker_id=registration["worker_id"],
            input_topic=dict(
                name=registration["input_topic"], id=registration["input_topic_id"], partition=0
            ),
            evidence_registry_sha256=digest(dict(version="1.0.0", objects=[])),
            state_codec="lifecycle-worker/1.0.0",
        )
    )
    return shared, stable


class Qualification:
    def __init__(self, folder, runtime, bundles, store, probe):
        self.folder, self.runtime, self.bundles, self.store, self.probe = (
            folder,
            runtime,
            bundles,
            store,
            Path(probe),
        )
        self.registrations: list[dict[str, Any]] = []
        self.current: dict[str, Any] = {}
        self.oracle = Oracle(bundles)
        self.output_cursor = 0
        self.coverage: dict[str, Any] = {}
        self.physical_outputs = 0
        self.checkpoint_evidence: list[dict[str, Any]] = []
        self.approved_fault_proofs: dict[str, Any] = {}
        self.unexpected_job_failures: list[dict[str, Any]] = []
        self.query_failures: list[dict[str, Any]] = []
        self.confirmed_ack_checkpoints: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def record(self, name, mode, requirements, **evidence):
        self.coverage[name] = dict(
            status="passed", evidence_kind=mode, requirements=requirements, **evidence
        )
        (self.folder / "coverage.json").write_bytes(encoded(self.coverage) + b"\n")

    def wait(self, predicate, category, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            finished = time.monotonic()
            if value and finished <= deadline:
                return value
            if finished >= deadline:
                break
            time.sleep(min(0.5, deadline - finished))
        raise ValueError("lifecycle_qualification_timeout_" + category)

    @staticmethod
    def uncompleted_snapshot_observation(marker, inventory):
        checkpoint = marker.get("checkpoint_id")
        snapshot_hash = marker.get("snapshot_sha256")
        require(
            type(checkpoint) is int
            and checkpoint >= 0
            and isinstance(snapshot_hash, str)
            and re.fullmatch(r"[a-f0-9]{64}", snapshot_hash),
            "unconfirmed_snapshot_marker",
        )
        require(
            inventory.get("checkpoint_id") == checkpoint
            and inventory.get("snapshot_sha256") == snapshot_hash
            and inventory.get("selection") == marker.get("selection"),
            "unconfirmed_snapshot_inventory",
        )
        selection = marker["selection"]
        require(isinstance(selection, dict), "unconfirmed_snapshot_selection")
        candidates = inventory.get("durable_ack_candidates", [])
        require(
            any(
                row.get("checkpoint_id") == checkpoint
                and row.get("ack", {}).get("payload", {}).get("checkpoint_id") == checkpoint
                and row["ack"]["payload"].get("phase") == "durable"
                and row["ack"]["payload"].get("command_sha256") == selection["command_sha256"]
                for row in candidates
            ),
            "unconfirmed_snapshot_candidate",
        )
        return dict(
            checkpoint_id=checkpoint,
            snapshot_sha256=snapshot_hash,
            inventory_sha256=digest(inventory),
            evidence_scope="owned advisory serialization/candidate observation only; never completed-checkpoint or recovery proof",
        )

    def ack_barrier(self):
        observed = self.runtime.topic_status("ack")
        expected = self.runtime.state["broker"]["topics"]["ack"]
        require(
            observed["cluster_id"] == self.runtime.state["broker"]["cluster_id"]
            and observed["topic"] == expected["name"]
            and observed["topic_id"] == expected["id"]
            and type(observed["end"]) is int
            and observed["end"] >= 0,
            "ack_barrier_identity",
        )
        return {key: observed[key] for key in ("cluster_id", "topic", "topic_id", "end")}

    def drain_checked_acks(self, barrier, category="checked_ack_barrier", timeout=120):
        """Observe/verify a complete frozen broker prefix without inferring CP completion."""

        def drained():
            status = self.runtime.observe(limit=8)
            return status if status["ack_cursor"] >= barrier["end"] else None

        status = self.wait(drained, category, timeout)
        return {**barrier, "checked_cursor": status["ack_cursor"]}

    def fenced_ack_barrier(self, worker, category="fenced_ack_barrier"):
        self.runtime.stop(worker)
        return self.drain_checked_acks(self.ack_barrier(), category)

    @staticmethod
    def exact_open_group(inventory, case, publication):
        selection = inventory.get("selection") or {}
        if (
            selection.get("command_sha256") != publication["command_sha256"]
            or selection.get("revision") != publication["revision"]
        ):
            return None
        rows = case["admissions"][:-1]
        require(len(rows) == 5, "group_five_source_members")
        context = rows[0]["context"]
        header = re.search(r"msg=audit\(([^:]+):([0-9]+)\)", rows[0]["raw"]["evidence"]["inline"])
        if header is None:
            raise ValueError("lifecycle_oracle_group_source_header")
        key = dict(
            run_id=case["run_id"],
            source=context["source"],
            host_id=context["host_binding"]["host_id"],
            generation=context["source_generation"]["id"],
            audit_timestamp=header[1],
            audit_serial=header[2],
        )
        expected = {
            row["raw"]["record_id"]: dict(
                record_id=row["raw"]["record_id"],
                evidence_sha256=row["raw"]["evidence"]["sha256"],
                raw_sha256=digest(row["raw"]),
                context_sha256=digest(row["context"]),
            )
            for row in rows
        }
        for group in inventory.get("machine", {}).get("groups", []):
            if group.get("key") != key:
                continue
            members = group.get("members", [])
            if len(members) != 5 or {row.get("record_id") for row in members} != set(expected):
                return None
            require(
                all(row == expected[row["record_id"]] for row in members), "group_member_integrity"
            )
            require(group["deadline"] - group["opened"] == 30000, "group_original_deadline")
            return group
        return None

    def registration(self, worker):
        return next(row for row in self.registrations if row["worker_id"] == worker)

    def proposal(self, bundle_name, action="activate"):
        status = self.store.status()
        request_id = str(uuid.uuid4())
        manifest = self.bundles[bundle_name]["manifest"]
        revision = status["preparation_revision"] + 1
        command = dict(
            version="1.0.0",
            authority_id=AUTHORITY,
            deployment_id=DEPLOYMENT,
            request_id=request_id,
            revision=revision,
            previous_sha256=status["prepared_command_sha256"],
            action=action,
            bundle_sha256=manifest["bundle_sha256"],
            compatibility_sha256=manifest["compatibility_sha256"],
            participants=[
                {key: row[key] for key in ("worker_id", "incarnation")}
                for row in sorted(self.registrations, key=lambda row: row["worker_id"])
            ],
        )
        request = dict(
            version="1.0.0",
            authority_id=AUTHORITY,
            request_id=request_id,
            operation="prepare",
            bundle_sha256=manifest["bundle_sha256"],
            arguments=dict(command=command, expected_preparation_revision=revision - 1),
        )
        return self.store.execute(request)["command"]

    def publish(self, name, action="activate", uncertainty=False, prepared=None):
        proposal = self.proposal(name, action) if prepared is None else prepared
        require(
            proposal["bundle_sha256"] == self.bundles[name]["manifest"]["bundle_sha256"]
            and proposal["action"] == action,
            "prepared_publication_target",
        )
        expected = self.current["revision"] if self.current else 0
        previous = self.current["command_sha256"] if self.current else None
        if uncertainty:

            def lost_ack(phase):
                if phase == "after_control_broker_ack":
                    raise RuntimeError("qualification_after_actual_control_ack")

            with patch("lifecycle_runtime.HOOK", side_effect=lost_ack):
                try:
                    self.runtime.publish(
                        self.store, proposal, self.registrations, expected, previous
                    )
                except RuntimeError as error:
                    require(
                        str(error) == "qualification_after_actual_control_ack",
                        "uncertainty_category",
                    )
                else:
                    require(False, "uncertainty_not_injected")
            pending = self.runtime.status()
            require(
                pending["publication"] == "adopted_pending" and pending["revision"] == expected + 1,
                "pending_publication",
            )
            intent = (
                self.runtime.root / "publications" / (str(expected + 1) + ".json")
            ).read_bytes()
            published = self.runtime.publish(
                self.store, proposal, self.registrations, expected, previous
            )
            require(
                (self.runtime.root / "publications" / (str(expected + 1) + ".json")).read_bytes()
                == intent,
                "uncertainty_changed_intent",
            )
            self.record(
                "publisher_uncertainty",
                "production-runtime-with-controller-fault-hook",
                ["C02", "C03"],
                revision=published["revision"],
                command_sha256=published["command_sha256"],
                immutable_intent_sha256=sha(intent),
            )
        else:
            published = self.runtime.publish(
                self.store, proposal, self.registrations, expected, previous
            )
        require(
            published["revision"] == expected + 1 and published["receipt"], "published_revision"
        )
        self.current = published
        return published

    def converge(self, workers=None, timeout=120):
        wanted = set(workers or WORKERS)

        def ready():
            for worker in wanted:
                self.fail_on_failed_job(worker)
            status = self.runtime.observe(limit=32)
            for worker in wanted:
                if not any(
                    p["worker_id"] == worker and p["durable"] and not p["rejected"]
                    for p in status["participants"]
                ):
                    return None
                registration = self.registration(worker)
                job_id = self.runtime.state["jobs"][worker]["job_id"]
                key = (worker, registration["incarnation"], self.current["command_sha256"], job_id)
                if key in self.confirmed_ack_checkpoints:
                    continue
                proofs = [
                    row["payload"]
                    for row in self.runtime.state["acks"].values()
                    if row["payload"]["worker_id"] == worker
                    and row["payload"]["incarnation"] == registration["incarnation"]
                    and row["payload"]["command_sha256"] == self.current["command_sha256"]
                    and row["payload"]["phase"] == "durable"
                ]
                require(bool(proofs), "durable_proof_missing")
                ack = max(proofs, key=lambda row: row["checkpoint_id"])
                try:
                    checkpoint = self.runtime.worker_inventory(worker, ack["checkpoint_id"])
                except Exception as error:
                    path = "/jobs/" + job_id + "/checkpoints/details/" + str(ack["checkpoint_id"])
                    self.retain_query_failure(worker, path, error)
                    if self.checkpoint_was_evicted(worker, job_id, ack["checkpoint_id"], error):
                        # This ACK remains unproven. Poll for a fresh signed ACK,
                        # then confirm its exact named CP within the original deadline.
                        return None
                    raise
                selection = checkpoint["inventory"]["selection"]
                require(
                    selection["revision"] == self.current["revision"]
                    and selection["command_sha256"] == self.current["command_sha256"],
                    "checkpoint_selection",
                )
                private_proof = self.private_evidence(
                    "confirmed-ack-checkpoint-" + worker, checkpoint
                )
                evidence = dict(
                    worker_id=worker,
                    incarnation=registration["incarnation"],
                    job_id=job_id,
                    checkpoint_id=ack["checkpoint_id"],
                    snapshot_sha256=checkpoint["inventory"]["snapshot_sha256"],
                    command_sha256=ack["command_sha256"],
                    confirmation_sha256=private_proof,
                    evidence="exact signed ACK-named independently COMPLETED checkpoint; retained proof cache scoped to command/incarnation/job",
                )
                self.confirmed_ack_checkpoints[key] = evidence
                self.checkpoint_evidence.append(evidence)
            return status

        return self.wait(ready, "convergence", timeout)

    def checkpoint_was_evicted(self, worker, job_id, checkpoint_id, error):
        """Recognize only proven same-job history eviction; never infer completion."""
        stderr = getattr(error, "stderr", b"")
        if (
            getattr(error, "returncode", None) != 22
            or not isinstance(stderr, bytes)
            or not re.search(
                rb"curl:\s*\(22\)\s*The requested URL returned error:\s*404(?:\s|$)", stderr
            )
        ):
            return False
        require(
            self.runtime.state["jobs"][worker]["job_id"] == job_id, "checkpoint_query_job_changed"
        )
        path = "/jobs/" + job_id + "/checkpoints"
        try:
            history = self.runtime.rest(worker, path)
        except Exception as history_error:
            self.retain_query_failure(worker, path, history_error)
            self.query_failures[-1]["endpoint_family"] = "checkpoint-history"
            raise
        history_hash = self.private_evidence("checkpoint-history-" + worker, history)
        entries = history.get("history") if isinstance(history, dict) else None
        if not isinstance(entries, list):
            raise ValueError("lifecycle_oracle_checkpoint_history_shape")
        ids = []
        for entry in entries:
            require(
                isinstance(entry, dict) and type(entry.get("id")) is int and entry["id"] >= 0,
                "checkpoint_history_identity",
            )
            ids.append(entry["id"])
        metadata = self.query_failures[-1]
        metadata.update(history_sha256=history_hash, retained_history_ids=ids)
        if not ids or checkpoint_id >= min(ids):
            metadata["retry_disposition"] = "not_proven_evicted_fail"
            return False
        metadata.update(
            retry_disposition="evicted_unproven_wait_for_fresh_signed_ack",
            minimum_retained_history_id=min(ids),
        )
        return True

    def retain_query_failure(self, worker, path, error):
        """Retain bounded helper diagnostics without guessing an unavailable REST fact."""
        metadata: dict[str, Any] = dict(
            worker_id=worker,
            endpoint_family="checkpoint-details",
            path_sha256=sha(path.encode()),
            exception_class=type(error).__name__,
            process_returncode=getattr(error, "returncode", None),
        )
        match = re.fullmatch(r"/jobs/([a-f0-9]{32})/checkpoints/details/([0-9]+)", path)
        if match:
            metadata.update(job_id=match[1], checkpoint_id=int(match[2]))
        self.query_failures.append(metadata)
        for name in ("stdout", "stderr"):
            data = getattr(error, name, None)
            if not isinstance(data, bytes):
                continue
            metadata[name + "_sha256"] = sha(data)
            metadata[name + "_bytes"] = len(data)
            if name == "stderr":
                status = re.search(rb"(?:returned error:|HTTP/[0-9.]+)\s*([0-9]{3})", data[:65536])
                if status:
                    metadata["http_status"] = int(status[1])
            try:
                require(len(data) <= 2 * 1024 * 1024, "query_failure_stream_limit")
                folder = self.runtime.root.parent / "qualification-private-evidence"
                folder.mkdir(mode=0o700, exist_ok=True)
                target = folder / ("query-" + uuid.uuid4().hex + "." + name)
                with os.fdopen(
                    os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
                ) as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                metadata[name + "_retained_privately"] = True
            except Exception as diagnostic_error:
                # Preserve the original query failure even if secondary retention fails.
                metadata[name + "_retention_exception_class"] = type(diagnostic_error).__name__

    def fail_on_failed_job(self, worker):
        """Convergence cannot heal an irreversibly failed explicit-restart job."""
        from integration_verify import exception_classes

        job = self.runtime.state["jobs"].get(worker)
        require(job is not None and job.get("job_id"), "convergence_job_missing")
        job_id = job["job_id"]
        detail = self.runtime.rest(worker, "/jobs/" + job_id)
        if detail.get("state") != "FAILED":
            return
        original = self.private_evidence("unexpected-job-" + worker, detail)
        exceptions = self.runtime.rest(worker, "/jobs/" + job_id + "/exceptions")
        exception_hash = self.private_evidence("unexpected-exceptions-" + worker, exceptions)
        self.unexpected_job_failures.append(
            dict(
                worker_id=worker,
                job_id=job_id,
                actual_state="FAILED",
                job_response_sha256=original,
                exceptions_sha256=exception_hash,
                exception_classes=exception_classes(exceptions),
                evidence_scope="full canonical REST documents retained privately; unknown raw logs are not approved public fault proofs",
            )
        )
        raise ValueError("lifecycle_qualification_unexpected_job_failure")

    def completed(self, worker):
        def latest():
            result = self.runtime.checkpoints(worker)
            completed = result.get("latest", {}).get("completed")
            return completed if completed and completed["status"] == "COMPLETED" else None

        cp = self.wait(latest, "completed_checkpoint")
        proof = self.runtime.worker_inventory(worker, cp["id"])
        self.checkpoint_evidence.append(
            dict(
                worker_id=worker,
                checkpoint_id=cp["id"],
                snapshot_sha256=proof["inventory"]["snapshot_sha256"],
                selection=proof["inventory"]["selection"],
            )
        )
        return proof

    def completed_open_group(self, worker, case, publication):
        """Scheduling evidence from an exact globally completed owned snapshot, not an ACK."""
        self.fail_on_failed_job(worker)
        checkpoint = self.runtime.checkpoints(worker).get("latest", {}).get("completed")
        if not checkpoint or checkpoint.get("status") != "COMPLETED":
            return None
        proof = self.runtime.worker_inventory(worker, checkpoint["id"])
        group = self.exact_open_group(proof["inventory"], case, publication)
        if group is None:
            return None
        evidence = dict(
            worker_id=worker,
            checkpoint_id=checkpoint["id"],
            snapshot_sha256=proof["inventory"]["snapshot_sha256"],
            selection=proof["inventory"]["selection"],
            group=group,
            private_proof_sha256=self.private_evidence("open-group-" + worker, proof),
            evidence_scope="actual completed checkpoint and exact open group; subsequent convergence separately requires signed durable ACK proof",
        )
        self.checkpoint_evidence.append(evidence)
        return evidence

    def restore_path(self, worker):
        cp = self.completed(worker)["checkpoint"]
        path = cp["external_path"]
        return "file:///state/" + path.split("/state/", 1)[1]

    def collect(self, complete=True, timeout=120):
        def progress():
            for worker in WORKERS:
                self.fail_on_failed_job(worker)
            batch = self.runtime.outputs(self.output_cursor, limit=64)
            self.output_cursor = batch["next_offset"]
            self.physical_outputs += len(batch["records"])
            return self.oracle.check(batch["records"])

        if complete:
            self.wait(progress, "source_accounting", timeout)
            self.oracle.check([], complete=True)
        else:
            progress()

    def add_case(
        self,
        case,
        bundle_name,
        publication=None,
        receipts=None,
        registration=None,
        receipt_states=None,
    ):
        worker = case["worker_id"]
        registration = registration or self.registration(worker)
        publication = publication or self.current
        receipts = (
            receipts if receipts is not None else self.runtime.admit(worker, case["admissions"])
        )
        _, binding = expected_bindings(self.runtime, registration)
        self.oracle.add(
            case, bundle_name, publication, registration, receipts, binding, receipt_states
        )
        return receipts

    @staticmethod
    def extra(case_id, suffix):
        case = next(row for row in phase_cases(1) if row["id"] == case_id)
        case["run_id"] = "715b0000-0000-4000-8000-" + str(suffix).zfill(12)
        for row in case["admissions"]:
            row["context"]["run_id"] = case["run_id"]
        return case

    def replacement(self, worker, mode=None):
        if mode in ("hold-release", "partial-sink", "checkpoint-timeout"):
            self.wait(
                lambda: not self.completed(worker)["inventory"]["provenance"],
                "quiescent_checkpoint",
            )
        restore = self.restore_path(worker)
        previous = self.registration(worker)
        replacement = self.runtime.replace(worker, restore)["registration"]
        require(
            replacement["incarnation"] != previous["incarnation"]
            and replacement["public_key"] != previous["public_key"],
            "replacement_identity",
        )
        self.registrations = [
            replacement if row["worker_id"] == worker else row for row in self.registrations
        ]
        self.publish(
            "A", "membership", uncertainty=not bool(self.coverage.get("publisher_uncertainty"))
        )
        operation = str(uuid.uuid4())
        if mode:
            self.runtime.start_probe(worker, restore, self.probe, mode, operation)
        else:
            self.runtime.start(worker, restore)
        return dict(
            restore=restore, previous=previous, registration=replacement, operation=operation
        )

    def setup_workers(self):
        """Fresh real workers with signed permanent run ownership and actual A convergence."""
        for worker in WORKERS:
            suffixes = range(101, 117) if worker == WORKERS[0] else range(201, 217)
            runs = ["715b0000-0000-4000-8000-" + str(n).zfill(12) for n in suffixes]
            self.registrations.append(self.runtime.worker(worker, assigned_runs=runs))
        self.proposal("A")  # Inspection-only proposal deliberately never published.
        self.publish("A")
        for worker in WORKERS:
            self.runtime.start(worker)
        self.converge()

    def core(self):
        self.setup_workers()
        for case in phase_cases(1):
            self.add_case(case, "A")
        self.collect()
        old = self.completed(WORKERS[1])
        self.runtime.fault("worker_pause", WORKERS[1])
        try:
            self.publish("B")
            mixed = self.converge([WORKERS[0]], timeout=40)
            require(not mixed["converged"], "mixed_inferred_convergence")
            for case in phase_cases(2):
                if case["worker_id"] == WORKERS[0]:
                    self.add_case(case, "B")
            self.collect()
            require(old["inventory"]["selection"]["revision"] == 1, "prior_worker_selection")
            self.record(
                "mixed_workers",
                "production-runtime",
                ["C07"],
                paused_worker=WORKERS[1],
                paused_checkpoint_sha256=old["inventory"]["snapshot_sha256"],
                active_revision=2,
            )
        finally:
            self.runtime.fault("worker_resume", WORKERS[1])
        self.converge()
        for case in phase_cases(2):
            if case["worker_id"] == WORKERS[1]:
                self.add_case(case, "B")
        self.collect()
        self.publish("A", "rollback")
        self.converge()
        for case in phase_cases(3):
            self.add_case(case, "A")
        self.collect()
        require(len(self.oracle.seen) == 66 and len(self.oracle.receipts) == 42, "core_totals")
        self.record(
            "core_two_worker_a_b_a",
            "production-runtime",
            ["C01", "B28"],
            logical_outputs=66,
            admitted_locations=42,
            source_runs=6,
            command_revisions=[1, 2, 3],
        )

    def production_faults(self):
        worker = WORKERS[0]
        replacement = self.replacement(worker)
        self.converge()
        self.add_case(self.extra("security-alice", 104), "A")
        self.collect()
        self.record(
            "registered_replacement",
            "production-runtime",
            ["C12"],
            restored_from=replacement["restore"],
            old_incarnation=replacement["previous"]["incarnation"],
            new_incarnation=replacement["registration"]["incarnation"],
        )
        case = self.extra("security-alice", 105)
        self.runtime.fault("worker_pause", worker)
        broker_paused = False
        try:
            receipts = self.runtime.admit(worker, case["admissions"])
            self.add_case(case, "A", receipts=receipts)
            self.runtime.fault("broker_pause")
            broker_paused = True
            self.runtime.fault("worker_resume", worker)
            time.sleep(2)
        finally:
            if broker_paused:
                self.runtime.fault("broker_resume")
            # unpause is idempotent in Docker only through explicit inspected state; do not repeat.
        self.collect()
        self.record(
            "broker_outage",
            "production-runtime",
            ["P06", "F01"],
            accepted_before_fault=receipts,
            outage_seconds=2,
        )
        case = self.extra("security-alice", 106)
        self.runtime.fault("worker_pause", worker)
        receipts = self.runtime.admit(worker, case["admissions"])
        self.add_case(case, "A", receipts=receipts)
        self.runtime.fault("output_reject")
        try:
            self.runtime.fault("worker_resume", worker)
            self.wait(lambda: self.job_failed(worker), "required_sink_failure")
            failure = self.named_job_failure(
                worker, required_class="org.apache.kafka.common.errors.RecordTooLargeException"
            )
            self.runtime.evidence(worker)
        finally:
            self.runtime.fault("output_restore")
        self.replacement(worker)
        self.converge()
        self.collect()
        self.record(
            "required_sink_failure",
            "production-runtime",
            ["T12"],
            accepted_locations=receipts,
            fault="actual output topic max.message.bytes=1 then restored",
            actual_failure=failure,
        )

    def private_evidence(self, name, value):
        data = encoded(value)
        require(len(data) <= 2 * 1024 * 1024, "failure_evidence_limit")
        folder = self.runtime.root.parent / "qualification-private-evidence"
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / (name + "-" + uuid.uuid4().hex + ".json")
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return sha(data)

    def export_approved_fault(self, name, value, original_sha256):
        require(
            name in ("required-sink-failure", "partial-after-ack", "checkpoint-expired"),
            "unapproved_fault_export",
        )
        data = encoded(value)
        require(
            len(data) <= 2 * 1024 * 1024 and sha(data) == original_sha256, "approved_fault_hash"
        )
        # Export only these complete public-synthetic REST response documents.
        # Private work, arbitrary exceptions and container logs remain excluded.
        private_keys = [
            self.runtime.root / "authority/private.der",
            *(self.runtime.root / "workers").glob("*/**/private.der"),
        ]
        require(
            all(path.is_file() and not path.is_symlink() for path in private_keys),
            "fault_export_key_inventory",
        )
        for path in private_keys:
            secret = path.read_bytes()
            require(secret and len(secret) <= 4096, "fault_export_key_inventory")
            encodings = (
                secret,
                base64.b64encode(secret),
                secret.hex().encode(),
                secret.hex().upper().encode(),
            )
            require(not any(value in data for value in encodings), "private_key_in_fault_proof")
        folder = self.folder / "approved-fault-proofs"
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / (name + ".json")
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        result = dict(
            filename="approved-fault-proofs/" + path.name,
            sha256=original_sha256,
            bytes=len(data),
            representation="complete canonical JSON REST response document; no HTTP framing claim",
        )
        self.approved_fault_proofs[name] = result
        return result

    def named_job_failure(self, worker, required_class=None, required_marker=None):
        from integration_verify import exception_classes

        job = self.runtime.state["jobs"][worker]["job_id"]
        detail = self.runtime.rest(worker, "/jobs/" + job + "/exceptions")
        proof_hash = self.private_evidence("job-exceptions-" + worker, detail)
        classes = exception_classes(detail)
        if required_class:
            require(required_class in classes, "unexpected_job_failure_class")
        if required_marker:
            require(required_marker in json.dumps(detail), "missing_named_fault_marker")
        approved_name = (
            "required-sink-failure"
            if required_class == "org.apache.kafka.common.errors.RecordTooLargeException"
            else "partial-after-ack"
            if required_marker == "lifecycle_qualification_after_actual_ack"
            else None
        )
        require(approved_name is not None, "unapproved_fault_export")
        approved = self.export_approved_fault(approved_name, detail, proof_hash)
        return dict(
            job_id=job,
            approved_proof=approved,
            exceptions_sha256=proof_hash,
            exception_classes=classes,
            required_class=required_class,
            required_marker=required_marker,
        )

    def job_failed(self, worker):
        job = self.runtime.state["jobs"][worker]["job_id"]
        status = self.runtime.rest(worker, "/jobs/" + job)
        return status if status["state"] == "FAILED" else None

    def pressure(self):
        worker = WORKERS[1]
        held = self.replacement(worker, "hold-release")
        self.converge()
        old_publication = self.current
        pressure = []
        for index in range(50):
            case = self.extra("security-alice", 204)
            case["worker_id"] = worker
            raw = case["admissions"][0]["raw"]
            raw["cursor"]["value"] = "p15b-pressure-" + str(index).zfill(3)
            scope = raw["source"]
            raw["record_id"] = "sha256:" + digest(
                [scope["namespace"], scope["instance"], ["native", raw["cursor"]["value"]]]
            )
            case["expected"]["member_ids"] = [raw["record_id"]]
            case["expected"]["event_id"] = "sha256:" + digest(
                [scope["namespace"], scope["instance"], [raw["record_id"]]]
            )
            pressure.append(case)
        physical = self.runtime.admit(worker, [case["admissions"][0] for case in pressure])
        # Original queue bound128: 42 matching A proposals×3outputs=126; the next
        # 3-output proposal cannot commit. This is independent finite arithmetic.
        self.wait(
            lambda: len(self.completed(worker)["inventory"]["provenance"]) == 126,
            "finite_outbox_pressure",
        )
        self.publish("B")
        self.converge()
        inventory = self.wait(
            lambda: (
                self.completed(worker)["inventory"]
                if len(self.completed(worker)["inventory"]["provenance"]) == 128
                else None
            ),
            "full_outbox_control_progress",
        )
        require(
            any(
                row["selection"]["command_sha256"] == old_publication["command_sha256"]
                for row in inventory["provenance"]
            ),
            "old_intent_selection",
        )
        for index, (case, receipt) in enumerate(zip(pressure, physical, strict=True)):
            self.add_case(
                case,
                "A" if index < 42 else "B",
                publication=old_publication if index < 42 else self.current,
                receipts=[receipt],
            )
        self.runtime.release_probe(worker, held["operation"])
        self.collect()
        self.record(
            "old_outbox_new_selection",
            "first-party-probe",
            ["T01", "T09"],
            probe_sha256=sha(self.probe.read_bytes()),
            old_revision=old_publication["revision"],
            new_revision=self.current["revision"],
        )
        self.record(
            "finite_backpressure",
            "first-party-probe",
            ["T03", "P05"],
            accepted_locations=50,
            old_matching_proposals=42,
            maximum_data_intents=128,
            logical_source_outputs=142,
            deferred_policy="B",
            original_queue_limit=128,
        )

    def open_group(self, evidence_kind="production-runtime"):
        worker = WORKERS[1]
        old_registration = self.registration(worker)
        rollback_proposal = self.proposal("A", "rollback")
        setup_barrier = self.drain_checked_acks(self.ack_barrier(), "pre_group_ack_barrier")
        case = self.extra("audit-whoami", 205)
        before = self.current
        first = self.runtime.admit(worker, case["admissions"][:-1])

        opened_proof = self.wait(
            lambda: self.completed_open_group(worker, case, before),
            "open_audit_group",
            timeout=20,
        )
        opened_group = opened_proof["group"]
        self.publish("A", "rollback", prepared=rollback_proposal)
        last = self.runtime.admit(worker, case["admissions"][-1:])
        self.converge()
        states = [("B", before, old_registration)] * 5 + [("A", self.current, old_registration)]
        self.add_case(case, "A", receipts=first + last, receipt_states=states)
        self.collect()
        self.record(
            "open_group_closure_selection",
            evidence_kind,
            ["T04", "T16"],
            initial_revision=before["revision"],
            closure_revision=self.current["revision"],
            membership=case["expected"]["member_ids"],
            pre_admission_ack_barrier=setup_barrier,
            open_group_observation=opened_group,
            initial_completed_group_proof=opened_proof,
            closure_application_proof="actual immutable EOE receipt, six-member eligible source_boundary manifest, tagged result and detection all require A selection; publication receipt is not application proof",
            postactivation_numeric_deadline="not independently observed in this actual case; component deadline checks are separate",
            closure_expectation=case["expected"],
        )

    @staticmethod
    def require_atomic_case_output(envelope, case, receipts):
        """Bind the first actual sink ACK to this atomic source, excluding old outbox replay."""
        body = envelope["document"]
        kind = envelope["kind"]
        if kind == "receipt":
            expected = receipts[0]
            location = body.get("input", {})
            matches = body.get("record_id") == case["admissions"][0]["raw"]["record_id"] and all(
                location.get(key) == expected[key]
                for key in (
                    "cluster_id",
                    "topic_id",
                    "topic",
                    "partition",
                    "offset",
                    "value_sha256",
                )
            )
        elif kind == "tagged":
            event = body.get("event", {})
            matches = (
                event.get("detectbridge", {}).get("run_id") == case["run_id"]
                and event.get("event", {}).get("id") == case["expected"]["event_id"]
            )
        elif kind == "detection":
            matches = (
                body.get("run_id") == case["run_id"]
                and body.get("event_id") == case["expected"]["event_id"]
            )
        else:
            matches = False
        require(matches, "partial_marker_atomic_case")

    def partial_recovery(self):
        worker = WORKERS[1]
        partial = self.replacement(worker, "partial-sink")
        self.converge()
        # T12 isolates an atomic three-intent source transition from audit-group expiry.
        partial_case = self.extra("security-alice", 206)
        partial_case["worker_id"] = worker
        partial_receipts = self.add_case(partial_case, "A")
        marker = self.wait(
            lambda: self.runtime.read_probe_marker(worker, partial["operation"], "sink-ack.json"),
            "partial_output_ack",
        )
        self.wait(lambda: self.job_failed(worker), "partial_sink_failure")
        failure = self.named_job_failure(
            worker, required_marker="lifecycle_qualification_after_actual_ack"
        )
        descriptor = self.runtime.state["broker"]["topics"]["output"]
        require(
            marker["topic"] == descriptor["name"]
            and type(marker["offset"]) is int
            and marker["offset"] >= 0,
            "partial_marker_scope",
        )
        actual = self.runtime.outputs(marker["offset"], limit=1)["records"]
        require(
            len(actual) == 1
            and actual[0]["wire"]["offset"] == marker["offset"]
            and actual[0]["wire"]["topic"] == marker["topic"]
            and actual[0]["output"]["output_id"] == marker["key"]
            and actual[0]["wire_sha256"] == marker["value_sha256"],
            "partial_marker_broker_proof",
        )
        self.require_atomic_case_output(actual[0]["output"], partial_case, partial_receipts)
        self.oracle.check(actual)
        self.runtime.evidence(worker)
        self.replacement(worker)
        self.converge()
        self.collect()
        retried = self.runtime.outputs(marker["offset"] + 1, limit=16)["records"]
        retry = next(
            (
                row
                for row in retried
                if row["wire"]["offset"] > marker["offset"]
                and row["output"]["output_id"] == marker["key"]
                and row["wire_sha256"] == marker["value_sha256"]
            ),
            None,
        )
        if retry is None:
            raise ValueError("lifecycle_qualification_partial_accepted_prefix_not_replayed")
        # This evidence reread is separate from the forward accounting cursor.
        self.require_atomic_case_output(retry["output"], partial_case, partial_receipts)
        self.oracle.check([retry])
        self.record(
            "partial_ack_recovery",
            "first-party-probe",
            ["T12"],
            probe_sha256=sha(self.probe.read_bytes()),
            first_actual_output_ack=marker,
            immutable_accepted_prefix_retry=dict(
                topic=retry["wire"]["topic"],
                partition=retry["wire"]["partition"],
                offset=retry["wire"]["offset"],
                output_id=retry["output"]["output_id"],
                wire_sha256=retry["wire_sha256"],
            ),
            source_choice="original synthetic security-alice, worker21/run206; atomic receipt/tagged/detection, frozen A match",
            source_outputs=3,
            limitation="bounded atomic-intent accepted-prefix recovery; this case does not test audit-group timeout recovery",
            actual_failure=failure,
            physical_outputs=self.physical_outputs,
            logical_outputs=len(self.oracle.seen),
        )

    def checkpoint_timeout(self):
        worker = WORKERS[1]
        timed = self.replacement(worker, "checkpoint-timeout")
        marker = self.wait(
            lambda: self.runtime.read_probe_marker(
                worker, timed["operation"], "snapshot-start.json"
            ),
            "checkpoint_probe_start",
        )
        checkpoint_id = marker["checkpoint_id"]
        job = self.runtime.state["jobs"][worker]["job_id"]

        def aborted():
            cp = self.runtime.rest(
                worker, "/jobs/" + job + "/checkpoints/details/" + str(checkpoint_id)
            )
            return cp if cp["status"] == "FAILED" else None

        proof = self.wait(aborted, "actual_checkpoint_timeout", timeout=90)
        checkpoint_failure_hash = self.private_evidence("checkpoint-timeout", proof)
        failure_text = json.dumps(proof)
        require(
            "Checkpoint expired before completing." in failure_text
            or "CHECKPOINT_EXPIRED" in failure_text,
            "checkpoint_not_named_timeout",
        )
        approved_timeout = self.export_approved_fault(
            "checkpoint-expired", proof, checkpoint_failure_hash
        )
        require(
            marker["selection"]["command_sha256"] == self.current["command_sha256"]
            and marker["selection"]["origin_incarnation"]
            == self.registration(worker)["incarnation"],
            "timeout_snapshot_wrong_selection",
        )
        advisory = self.runtime.advisory_inventory(worker, checkpoint_id)
        observation = self.uncompleted_snapshot_observation(marker, advisory["inventory"])
        observation["private_inventory_sha256"] = self.private_evidence(
            "unconfirmed-snapshot-inventory", advisory
        )
        aborted_ack_barrier = self.fenced_ack_barrier(worker, "aborted_ack_barrier")
        reported_after_failure = self.runtime.status()["converged"]
        require(
            not any(
                row["payload"]["phase"] == "durable"
                and row["payload"]["worker_id"] == worker
                and row["payload"]["incarnation"] == self.registration(worker)["incarnation"]
                and row["payload"]["checkpoint_id"] == checkpoint_id
                for row in self.runtime.state["acks"].values()
            ),
            "aborted_durable_ack",
        )
        self.runtime.evidence(worker)
        self.record(
            "aborted_checkpoint_ack",
            "first-party-probe",
            ["T07", "T08"],
            actual_checkpoint_status=proof["status"],
            failure_proof_sha256=checkpoint_failure_hash,
            approved_proof=approved_timeout,
            named_failure="CHECKPOINT_EXPIRED",
            unconfirmed_snapshot_observation=observation,
            restore_source="previous independently completed checkpoint only; failed snapshot prohibited",
            fenced_worker_ack_barrier=aborted_ack_barrier,
            reported_convergence_after_failure=reported_after_failure,
            convergence_observation_scope="coordinator status only; a later completed checkpoint is permitted, never inferred from the aborted one",
            checkpoint_id=checkpoint_id,
            probe_sha256=sha(self.probe.read_bytes()),
        )
        # Worker is already fenced; recovery uses only the previously verified completed predecessor.
        replacement = self.runtime.worker(worker, replacement=True)
        self.registrations = [
            replacement if row["worker_id"] == worker else row for row in self.registrations
        ]
        self.publish("A", "membership")
        self.runtime.start(worker, timed["restore"])
        self.converge()

    def invalid_messages(self):
        publication = checked(
            self.runtime.root / "publications" / (str(self.current["revision"]) + ".json")
        )
        signed = copy.deepcopy(publication["control"])
        signature = bytearray(base64.b64decode(signed["signature"]))
        signature[0] ^= 1
        signed["signature"] = base64.b64encode(signature).decode()
        control = self.runtime.inject("control", encoded(signed))
        manifest = self.bundles["A"]["manifest"]
        content = encoded(manifest)
        shared, _ = expected_bindings(self.runtime, self.registrations[0])
        payload = dict(
            version="1.0.0",
            authority_id=AUTHORITY,
            deployment_id=DEPLOYMENT,
            runtime_binding_sha256=shared,
            bundle_sha256=manifest["bundle_sha256"],
            member="manifest.json",
            member_sha256=sha(content),
            member_bytes=len(content),
            chunk_index=0,
            chunk_count=1,
            chunk_sha256="0" * 64,
            data_base64=base64.b64encode(content).decode(),
        )
        chunk = self.runtime.inject("artifact", self.runtime.sign_injection("artifact", payload))
        for worker in WORKERS:

            def rejected():
                inventory = self.completed(worker)["inventory"]
                return (
                    inventory
                    if inventory.get("control_cursor", {}).get("next_offset", 0) > control["offset"]
                    and inventory.get("artifact_cursor", {}).get("next_offset", 0) > chunk["offset"]
                    and inventory.get("rejection_head", {}).get("count", 0) >= 2
                    else None
                )

            proof = self.wait(rejected, "durable_invalid_message_rejections")
            require(
                proof["selection"]["command_sha256"] == self.current["command_sha256"],
                "invalid_message_changed_selection",
            )
        self.record(
            "signed_invalid_messages",
            "production-runtime",
            ["S02", "S10"],
            bad_signature_location=control,
            signed_corrupt_chunk_location=chunk,
        )

    def hostile_ast(self):
        from lifecycle_validation import bundle

        self.add_case(self.extra("security-alice", 107), "A")
        self.collect()  # Establish actual healthy A before the adversarial signed transfer.
        hostile_ack_start = self.ack_barrier()
        before = copy.deepcopy(self.current)
        forged = copy.deepcopy(self.bundles["B"]["plan"])
        windows_id = "71500000-0000-4000-8000-000000000001"
        original_expression = next(
            rule["expression"]
            for rule in self.bundles["A"]["plan"]["rules"]
            if rule["id"] == windows_id
        )
        for rule in forged["rules"]:
            if rule["id"] == windows_id:
                rule["expression"] = copy.deepcopy(original_expression)
                require("User: Bob" in rule["yaml"], "hostile_original_yaml")
        forged.pop("bundle_sha256")
        forged["bundle_sha256"] = digest(forged)
        plan_bytes = encoded(forged)
        manifest = bundle(plan_bytes)  # Hash/schema packaging only, deliberately no compilation.
        shared, _ = expected_bindings(self.runtime, self.registrations[0])
        chunk_receipts = []
        for name, content in (("manifest.json", encoded(manifest)), ("plan.json", plan_bytes)):
            count = (len(content) + 262143) // 262144
            for index in range(count):
                block = content[index * 262144 : (index + 1) * 262144]
                payload = dict(
                    version="1.0.0",
                    authority_id=AUTHORITY,
                    deployment_id=DEPLOYMENT,
                    runtime_binding_sha256=shared,
                    bundle_sha256=manifest["bundle_sha256"],
                    member=name,
                    member_sha256=sha(content),
                    member_bytes=len(content),
                    chunk_index=index,
                    chunk_count=count,
                    chunk_sha256=sha(block),
                    data_base64=base64.b64encode(block).decode(),
                )
                chunk_receipts.append(
                    self.runtime.inject(
                        "artifact", self.runtime.sign_injection("artifact", payload)
                    )
                )
        current = checked(self.runtime.root / "publications" / (str(before["revision"]) + ".json"))[
            "control"
        ]["payload"]
        hostile = copy.deepcopy(current)
        hostile["revision"] = before["revision"] + 1
        hostile["previous_control_sha256"] = before["command_sha256"]
        hostile["proposal"]["request_id"] = str(uuid.uuid4())
        hostile["proposal"]["action"] = "activate"
        hostile["proposal"]["bundle_sha256"] = manifest["bundle_sha256"]
        hostile["proposal_sha256"] = digest(hostile["proposal"])
        command_hash = digest(hostile)
        control = self.runtime.inject("control", self.runtime.sign_injection("control", hostile))
        # This explicit first-party adversarial send bypasses the controller's own
        # candidate gate. Worker-side independent compilation must still reject it.
        acknowledgments: dict[str, Any] = {}
        cursor = hostile_ack_start["end"]

        def rejected_acks():
            nonlocal cursor
            batch = self.runtime.inspect_acks(cursor, limit=16)
            cursor = batch["next_offset"]
            for row in batch["records"]:
                payload = row.get("payload")
                if payload and payload.get("command_sha256") == command_hash:
                    require(row["signature_verified"], "hostile_ack_authenticity")
                    require(
                        payload.get("phase") not in ("applied", "durable"),
                        "hostile_transient_application",
                    )
                if (
                    payload
                    and payload.get("command_sha256") == command_hash
                    and payload.get("phase") == "rejected"
                ):
                    require(
                        row["signature_verified"] and payload["category"] == "application_failed",
                        "hostile_ack_authenticity",
                    )
                    registration = self.registration(payload["worker_id"])
                    require(
                        payload["incarnation"] == registration["incarnation"],
                        "hostile_ack_incarnation",
                    )
                    acknowledgments[payload["worker_id"]] = payload
            return set(acknowledgments) == set(WORKERS)

        self.wait(rejected_acks, "signed_hostile_worker_rejection")
        proofs = []
        for worker in WORKERS:

            def durable_proof():
                inventory = self.completed(worker)["inventory"]
                return (
                    inventory
                    if inventory["observed_head"]["revision"] == hostile["revision"]
                    and inventory["artifact_cursor"]["next_offset"] > chunk_receipts[-1]["offset"]
                    and inventory["control_cursor"]["next_offset"] > control["offset"]
                    else None
                )

            proof = self.wait(durable_proof, "hostile_rejection_checkpoint")
            require(
                proof["selection"]["command_sha256"] == before["command_sha256"],
                "hostile_ast_applied",
            )
            last = proof["rejection_last"]
            require(
                last["location"]["category"] == "lifecycle_compiler_mismatch"
                and digest(last) == proof["rejection_head"]["sha256"],
                "compiler_rejection_proof",
            )
            locations = {
                (
                    row["cluster_id"],
                    row["topic"],
                    row["partition"],
                    row["offset"],
                    row["value_sha256"],
                )
                for row in [*chunk_receipts, control]
            }
            location = last["location"]
            require(
                tuple(
                    location[key]
                    for key in ("cluster_id", "topic", "partition", "offset", "value_sha256")
                )
                in locations,
                "compiler_rejection_wrong_operation",
            )
            proofs.append(
                dict(
                    worker_id=worker,
                    checkpoint_id=proof["checkpoint_id"],
                    snapshot_sha256=proof["snapshot_sha256"],
                    rejection_head=proof["rejection_head"],
                )
            )
        # Fence both owned producers, then freeze the actual broker end. Drain all
        # acknowledged history through that end, not merely until two rejections.
        for worker in WORKERS:
            self.runtime.stop(worker)
        topic = self.runtime.topic_status("ack")
        descriptor = self.runtime.state["broker"]["topics"]["ack"]
        require(
            topic["cluster_id"] == self.runtime.state["broker"]["cluster_id"]
            and topic["topic"] == descriptor["name"]
            and topic["topic_id"] == descriptor["id"],
            "ack_end_identity",
        )
        frozen_end = topic["end"]
        while cursor < frozen_end:
            previous_cursor = cursor
            rejected_acks()
            require(cursor > previous_cursor and cursor <= frozen_end, "ack_barrier_progress")
        require(cursor == frozen_end, "ack_barrier_incomplete")
        self.record(
            "signed_hostile_ast",
            "production-runtime-and-pinned-validator",
            ["S12"],
            forged_plan_sha256=sha(plan_bytes),
            forged_bundle_sha256=manifest["bundle_sha256"],
            effective_control_sha256=command_hash,
            preserved_revision=before["revision"],
            independent_rejection_checkpoints=proofs,
            signed_ack_history_start=hostile_ack_start,
            signed_ack_history_drained_through=frozen_end,
            forbidden_applied_or_durable_acks=0,
        )

    def retained(self):
        values = {}
        for name, bundle in self.bundles.items():
            target = bundle["manifest"]["bundle_sha256"]
            for filename, expected in (
                ("manifest.json", encoded(bundle["manifest"])),
                ("plan.json", bundle["plan_bytes"]),
            ):
                actual = self.runtime.root / "bundles" / target / filename
                require(actual.read_bytes() == expected, "retained_closure_changed")
            request = dict(
                version="1.0.0",
                authority_id=AUTHORITY,
                request_id=str(uuid.uuid4()),
                operation="retire",
                bundle_sha256=target,
                arguments={},
            )
            facts = self.store.status()
            try:
                self.store.execute(request)
            except ValueError as error:
                require(
                    str(error) == "lifecycle_prepared_reference", "unexpected_retention_failure"
                )
            else:
                require(False, "prepared_retirement_allowed")
            require(self.store.status() == facts, "retention_changed_state")
            values[name] = target
        self.record(
            "retained_versions",
            "production-controller-and-actual-worker-recovery",
            ["P01", "P02"],
            retained_bundles=values,
            boundary="nondeleting conservative retention; no P15b2 archive/replay pin qualification",
        )

    def run(self, scenario_group="all"):
        require(scenario_group in SCENARIO_GROUPS, "unknown_scenario_group")
        if scenario_group == "all":
            self.core()
            self.production_faults()
            self.pressure()
            self.open_group("first-party-probe-after-data-release")
            self.partial_recovery()
            self.checkpoint_timeout()
            self.invalid_messages()
            self.retained()
            self.hostile_ast()
        elif scenario_group == "core":
            self.core()
        else:
            self.setup_workers()
            if scenario_group == "open-group":
                self.publish("B")
                self.converge()
            elif scenario_group == "retention":
                # Both real adopted closures plus an actual explicit completed-state restore.
                self.publish("B")
                self.converge()
                self.publish("A", "rollback")
                self.converge()
                self.replacement(WORKERS[1])
                self.converge()
            method = {
                "production-faults": self.production_faults,
                "pressure": self.pressure,
                "open-group": self.open_group,
                "partial-recovery": self.partial_recovery,
                "checkpoint-timeout": self.checkpoint_timeout,
                "invalid-messages": self.invalid_messages,
                "hostile-ast": self.hostile_ast,
                "retention": self.retained,
            }[scenario_group]
            method()
        missing = sorted(set(SCENARIO_GROUPS[scenario_group]) - set(self.coverage))
        require(not missing, "required_scenarios_unqualified_" + "_".join(missing))
        return self.coverage


def stage_candidates(root, bundles, producer):
    first = bundles["A"]["manifest"]
    store = Store.initialize(root, AUTHORITY, producer, first["profile"])
    for value in bundles.values():
        target = value["manifest"]["bundle_sha256"]
        for operation, arguments in (
            (
                "import",
                dict(
                    manifest_sha256=sha((value["directory"] / "manifest.json").read_bytes()),
                    plan_sha256=sha(value["plan_bytes"]),
                ),
            ),
            ("validate", {}),
            ("test", dict(suite_sha256=sha(value["suite"].read_bytes()))),
            ("stage", {}),
        ):
            request = dict(
                version="1.0.0",
                authority_id=AUTHORITY,
                request_id=str(uuid.uuid4()),
                operation=operation,
                bundle_sha256=target,
                arguments=arguments,
            )
            result = store.execute(
                request,
                bundle_directory=value["directory"] if operation == "import" else None,
                suite_path=value["suite"] if operation == "test" else None,
            )
            if operation == "test":
                require(result["report"]["passed"], "actual_candidate_test")
    return store


def retain_validator_build(folder, reports, build_folder, artifact=None, descriptor_path=None):
    """Export only public first-party builder logs/descriptor and exact packet hashes."""
    result: dict[str, Any] = {
        "scope": "first-party validator build inputs/logs only; no private work or keys"
    }
    for source_name, public_name in (
        ("build.log", "validator-build.log"),
        ("packet-check.log", "validator-packet-check.log"),
    ):
        source = build_folder / source_name
        if source.is_file():
            require(
                not source.is_symlink() and source.stat().st_size <= 32 * 1024 * 1024,
                "validator_build_log_limit",
            )
            destination = folder / public_name
            shutil.copyfile(source, destination)
            shutil.copyfile(source, reports / public_name)
            result[source_name] = dict(
                filename=public_name,
                sha256=sha(destination.read_bytes()),
                bytes=destination.stat().st_size,
            )
    descriptor_file = descriptor_path or build_folder / "descriptor.json"
    if descriptor_file.is_file():
        data = descriptor_file.read_bytes()
        require(
            len(data) <= 65536 and not descriptor_file.is_symlink(), "validator_build_descriptor"
        )
        value = json.loads(data)
        require(
            isinstance(value, dict)
            and set(value) == {"version", "artifact_sha256", "image_id", "base_image"},
            "validator_build_descriptor",
        )
        (folder / "validator-descriptor.json").write_bytes(data)
        result["descriptor"] = value
        result["descriptor_file"] = dict(filename="validator-descriptor.json", sha256=sha(data))
    packet_file = artifact or build_folder / "artifact.tar"
    if packet_file.is_file():
        import hashlib

        digestor = hashlib.sha256()
        with packet_file.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digestor.update(block)
        result["packet_sha256"] = digestor.hexdigest()
        result["packet_bytes"] = packet_file.stat().st_size
        if "descriptor" in result:
            require(
                result["packet_sha256"] == result["descriptor"]["artifact_sha256"],
                "validator_build_packet_hash",
            )
            result["packet_matches_descriptor"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-jar",
        type=Path,
        default=ROOT / "packages/lifecycle-job/build/libs/lifecycle-job.jar",
    )
    parser.add_argument(
        "--probe-jar",
        type=Path,
        default=ROOT / "packages/lifecycle-job/build/libs/lifecycle-probe.jar",
    )
    parser.add_argument(
        "--producer-jar",
        type=Path,
        default=ROOT / "packages/integration-job/build/libs/integration-job.jar",
    )
    parser.add_argument("--validator-artifact", type=Path)
    parser.add_argument("--validator-descriptor", type=Path)
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use explicitly hash-verified already-tested local artifacts",
    )
    parser.add_argument(
        "--scenario-group",
        choices=tuple(SCENARIO_GROUPS),
        default="all",
        help="Fresh real setup for a bounded group; only default all qualifies the full gate",
    )
    parser.add_argument("--runtime-sha256")
    parser.add_argument("--probe-sha256")
    args = parser.parse_args(argv)
    if os.environ.get("DETECTBRIDGE_ACTIVATION_REQUIRED") == "1" and args.scenario_group != "all":
        parser.error("required activation qualification must execute --scenario-group all")
    attempt = uuid.uuid4().hex
    reports = ROOT / ".cache/lifecycle-runtime-qualification"
    folder = reports / "attempts" / attempt
    folder.mkdir(parents=True)
    work = ROOT / ".cache/lifecycle-runtime-work" / attempt
    work.mkdir(parents=True, mode=0o700)
    report: dict[str, Any] = dict(
        version="1.0.0",
        status="failed",
        full_gate=False,
        scenario_group=args.scenario_group,
        selected_required_scenarios=list(SCENARIO_GROUPS[args.scenario_group]),
        result_interpretation="Focused partial_passed qualifies only selected bounded cases; default all14 remains mandatory for the full gate",
        scope="P15b1 synthetic local worker runtime; no P15b2 archive/replay, recorded completeness, throughput or HA claim",
        platform=platform.platform(),
        attempt=attempt,
        source_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        tracked_dirty=bool(
            subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=ROOT)
        ),
        phase="packet",
        coverage={},
        source_sha256={},
    )
    source_paths = {
        ROOT / "tools/lifecycle_runtime_cases.py",
        ROOT / "tools/lifecycle_runtime_verify.py",
        ROOT / "tools/lifecycle_runtime.py",
        ROOT / "tools/tests/test_lifecycle_runtime_oracle.py",
        ROOT / "tools/lifecycle_worker_validator.py",
        ROOT / "tools/build_worker_validator.py",
        ROOT / "packages/lifecycle-job/build.gradle.kts",
        *[path for path in (ROOT / "packages/lifecycle-job/src").rglob("*") if path.is_file()],
        *[path for path in (ROOT / "contracts/lifecycle-runtime/v1").rglob("*") if path.is_file()],
    }
    report["source_sha256"] = {
        str(path.relative_to(ROOT)): sha(path.read_bytes())
        for path in sorted(source_paths)
        if path.is_file()
    }
    runtime = None
    qualification = None
    try:
        check_packet()
        report["phase"] = "offline_build"
        if args.skip_build:
            require(
                args.runtime_sha256 is not None and args.probe_sha256 is not None,
                "skip_build_hashes_required",
            )
            require(
                sha(args.runtime_jar.read_bytes()) == args.runtime_sha256
                and sha(args.probe_jar.read_bytes()) == args.probe_sha256,
                "skip_build_artifact_mismatch",
            )
            report["build_mode"] = "explicit_hash_verified_existing_artifacts"
            report["jar_tests_this_attempt"] = False
        else:
            from transport import java_env

            command = [
                str(ROOT / "gradlew"),
                "--offline",
                "--console=plain",
                ":integration-job:shadowJar",
                ":lifecycle-job:test",
                ":lifecycle-job:jar",
                ":lifecycle-job:qualificationJar",
            ]
            with (folder / "build.log").open("wb") as log:
                subprocess.run(
                    command,
                    cwd=ROOT,
                    env=java_env(),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=600,
                    check=True,
                )
            report["build_mode"] = "locked_offline_gradle_build_and_tests"
            report["jar_tests_this_attempt"] = True
            report["build_command"] = [str(value) for value in command]
        report["phase"] = "candidate_stage"
        bundles = prepare(work / "candidates")
        store = stage_candidates(work / "candidate-store", bundles, args.producer_jar)
        report["bundles"] = {
            name: {key: value["manifest"][key] for key in ("bundle_sha256", "compatibility_sha256")}
            | dict(plan_sha256=sha(value["plan_bytes"]))
            for name, value in bundles.items()
        }
        from lifecycle_runtime import Runtime

        if args.validator_artifact is None and args.validator_descriptor is None:
            from build_worker_validator import build

            report["phase"] = "validator_build"
            validation = build(work / "validator-build")
            args.validator_artifact = validation["artifact"]
            descriptor = validation["descriptor"]
        else:
            require(
                args.validator_artifact is not None and args.validator_descriptor is not None,
                "validator_artifact_required",
            )
            descriptor = document(args.validator_descriptor)
        report["phase"] = "controller_initialization"
        runtime = Runtime.initialize(
            work / "deployment",
            AUTHORITY,
            DEPLOYMENT,
            args.runtime_jar,
            args.producer_jar,
            bundles["A"]["manifest"]["compatibility_sha256"],
            project="detectbridge-p15b-" + attempt[:16],
            validator_artifact=args.validator_artifact,
            validator_descriptor=descriptor,
            qualification_jar=args.probe_jar,
        )
        report["artifacts"] = dict(
            runtime_sha256=sha(args.runtime_jar.read_bytes()),
            producer_sha256=sha(args.producer_jar.read_bytes()),
            probe_sha256=sha(args.probe_jar.read_bytes()),
            validator=descriptor,
        )
        report["phase"] = "deployment"
        engine_result = subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],
            capture_output=True,
            timeout=30,
            check=True,
        )
        engine = json.loads(engine_result.stdout)
        report["docker_engine"] = {
            key: engine.get(key)
            for key in ("MemTotal", "Architecture", "ServerVersion", "OSType", "NCPU")
        }
        report["docker_engine"]["interpretation"] = (
            "Observed engine metadata; memory limits are ceilings, not measured reservations or qualified capacity."
        )
        runtime.up()
        report["images"] = {}
        for role, reference in (
            ("flink", runtime.config["image"]),
            ("kafka", runtime.config["kafka_image"]),
            ("validator", descriptor["image_id"]),
        ):
            observed = subprocess.run(
                ["docker", "image", "inspect", reference],
                capture_output=True,
                timeout=30,
                check=True,
            )
            image = json.loads(observed.stdout)[0]
            report["images"][role] = {
                key: image.get(key) for key in ("Id", "RepoDigests", "Architecture", "Os")
            }
        qualification = Qualification(folder, runtime, bundles, store, args.probe_jar)
        report["phase"] = "runtime_cases"
        qualification.run(args.scenario_group)
        report.update(
            scenario_outcome(args.scenario_group, qualification.coverage), phase="complete"
        )
    except Exception as error:
        report["exception_class"] = type(error).__name__
        category = str(error)
        if (
            category.startswith("lifecycle_")
            and len(category) <= 256
            and all(c.isalnum() or c in "_-" for c in category)
        ):
            report["category"] = category
    finally:
        if qualification is not None:
            report.update(
                coverage=qualification.coverage,
                logical_outputs=len(qualification.oracle.seen),
                physical_outputs=qualification.physical_outputs,
                admitted_locations=len(qualification.oracle.receipts),
                checkpoints=qualification.checkpoint_evidence,
                approved_fault_proofs=qualification.approved_fault_proofs,
                unexpected_job_failures=qualification.unexpected_job_failures,
                query_failures=qualification.query_failures,
            )
        if runtime is not None:
            report["worker_logging"] = {}
            for worker in WORKERS:
                job = runtime.state.get("jobs", {}).get(worker, {})
                logging = job.get("logging")
                proof: dict[str, Any] = dict(
                    status="not_observed",
                    job_id=job.get("job_id"),
                    incarnation=job.get("incarnation"),
                )
                if isinstance(logging, dict):
                    allowed = (
                        "resource_sha256",
                        "process_arguments_sha256",
                        "backend_record_sha256",
                    )
                    services = {}
                    for service in ("jobmanager", "taskmanager"):
                        value = logging.get(service)
                        if isinstance(value, dict) and all(
                            isinstance(value.get(key), str)
                            and re.fullmatch(r"[a-f0-9]{64}", value[key])
                            for key in allowed
                        ):
                            services[service] = {key: value[key] for key in allowed}
                    if set(services) == {"jobmanager", "taskmanager"}:
                        proof.update(
                            status="observed", services=services, proof_sha256=digest(services)
                        )
                report["worker_logging"][worker] = proof
            for worker in WORKERS:
                try:
                    runtime.evidence(worker)
                except Exception:
                    pass  # Secondary diagnostics never replace the original scenario result.
            try:
                runtime.stop()
                report["owned_runtime_stopped"] = True
            except Exception as error:
                report["cleanup_exception_class"] = type(error).__name__
                report["status"] = "failed"
        report["executed_scenarios"] = sorted(report["coverage"])
        report["unqualified_required_scenarios"] = sorted(set(REQUIRED) - set(report["coverage"]))
        report["full_gate"] = (
            args.scenario_group == "all"
            and report["status"] == "passed"
            and not report["unqualified_required_scenarios"]
        )
        matrix_ids = set(
            re.findall(
                r"^\| ([CSTP][0-9]{2}) \|", (ROOT / "docs/p15b-expectations.md").read_text(), re.M
            )
        )
        report["matrix_coverage"] = {
            item: dict(state="unrun", evidence_kind="not_executed") for item in sorted(matrix_ids)
        }
        for name, entry in report["coverage"].items():
            for item in entry["requirements"]:
                if item in report["matrix_coverage"]:
                    report["matrix_coverage"][item] = dict(
                        state="bounded_scenario_passed",
                        evidence_kind=entry["evidence_kind"],
                        scenario=name,
                    )
        for item in ("P03", "P04", "P10"):
            report["matrix_coverage"][item] = dict(
                state="future_owning_slice",
                evidence_kind="P15b2 archive/replay profile not implemented by B1",
            )
        try:
            validator_folder = work / "validator-build"
            if not validator_folder.exists() and args.validator_artifact is not None:
                validator_folder = args.validator_artifact.parent
            report["validator_build_evidence"] = retain_validator_build(
                folder,
                reports,
                validator_folder,
                args.validator_artifact,
                args.validator_descriptor,
            )
        except Exception as error:
            report["validator_evidence_exception_class"] = type(error).__name__
            report["status"] = "failed"
        build_log = folder / "build.log"
        if build_log.exists():
            log_data = build_log.read_bytes()
            report["build_log_sha256"] = sha(log_data)
            (reports / "build.log").write_bytes(log_data)
        report["full_gate"] = report["full_gate"] and report["status"] == "passed"
        data = encoded(report) + b"\n"
        (folder / "summary.json").write_bytes(data)
        (reports / "summary.json").write_bytes(data)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in ("passed", "partial_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
