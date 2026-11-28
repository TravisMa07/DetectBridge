"""Bounded value-free inclusive timings, enabled only by the first-party qualifier."""

import contextlib
import contextvars
import functools
import json
import re
import time
from typing import Any

STAGES = frozenset(
    {
        "immutable_verification",
        "load_replay_and_references",
        "candidate_capture",
        "kafka_drain",
        "signature_batch",
        "record_validation",
        "ack_file_fsync",
        "journal_append",
        "journal_ack",
        "journal_ack_cursor",
        "journal_ack_rejected",
        "kafka_commit",
        "observe",
        "inspect",
        "evidence_join",
        "predicate",
        "network_other",
        "job_health",
        "publication",
        "artifact_transfer",
        "artifact_readiness",
        "artifact_authorization",
        "artifact_preparation",
        "qualification_admission",
        "completed_open_group",
    }
)
COUNTS = frozenset({"requested", "fetched", "processed", "accepted", "rejected", "duplicates"})
HASHES = frozenset({"command_sha256", "snapshot_sha256", "wire_sha256"})
IDENTITIES = frozenset({"worker_id", "incarnation", "job_id"})
ACTIVE: contextvars.ContextVar[Any] = contextvars.ContextVar("lifecycle_diagnostics", default=None)


def snapshot(owner):
    state = getattr(getattr(owner, "runtime", owner), "state", {})
    result = {}
    for name in ("ack_cursor", "sequence", "ack_rejections", "ack_bytes"):
        value = state.get(name)
        if type(value) is int and 0 <= value < 2**63:
            result[name] = value
    acks = state.get("acks")
    if isinstance(acks, dict):
        result["ack_count"] = len(acks)
    return result


class Timings:
    MAX_SAMPLES = 8192
    MAX_SAMPLE_BYTES = 2048
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self):
        self.origin = time.monotonic_ns()
        self.deadline_ns: int | None = None
        self.samples: list[dict[str, Any]] = []
        self.stack: list[dict[str, Any]] = []
        self.totals: dict[str, dict[str, int]] = {}
        self.calls = 0
        self.dropped = 0
        self.bytes = 0
        self.last_by_stage: dict[str, dict[str, Any]] = {}
        self.last_predicate: dict[str, Any] | None = None
        self.last_late_truth: dict[str, Any] | None = None
        self.late_truth_count = 0

    @contextlib.contextmanager
    def activate(self):
        token = ACTIVE.set(self)
        try:
            yield self
        finally:
            ACTIVE.reset(token)

    def report(self):
        return dict(
            version="1.0.0",
            clock="monotonic_ns_offsets",
            attribution="inclusive_nested_spans_do_not_sum",
            limits=dict(
                samples=self.MAX_SAMPLES, sample_bytes=self.MAX_SAMPLE_BYTES, bytes=self.MAX_BYTES
            ),
            dropped_samples=self.dropped,
            totals=self.totals,
            samples=self.samples,
            last_by_stage=self.last_by_stage,
            last_predicate=self.last_predicate,
            last_late_truth=self.last_late_truth,
            late_truth_count=self.late_truth_count,
        )

    @contextlib.contextmanager
    def span(self, stage, owner=None):
        if stage not in STAGES:
            raise ValueError("unknown_diagnostic_stage")
        start = time.monotonic_ns()
        self.calls += 1
        row = dict(
            id=self.calls,
            parent=self.stack[-1]["id"] if self.stack else None,
            stage=stage,
            start_ns=start - self.origin,
            start_state=snapshot(owner),
            counters={},
            context={},
        )
        deadline = self.deadline_ns
        if deadline is not None:
            row["remaining_start_ns"] = deadline - start
        self.stack.append(row)
        success = False
        try:
            yield
            success = True
        finally:
            end = time.monotonic_ns()
            self.stack.pop()
            row.update(end_ns=end - self.origin, success=success, end_state=snapshot(owner))
            if deadline is not None:
                row["remaining_end_ns"] = deadline - end
            total = self.totals.setdefault(stage, dict(calls=0, failures=0, inclusive_ns=0))
            total["calls"] += 1
            total["failures"] += int(not success)
            total["inclusive_ns"] += end - start
            self.last_by_stage[stage] = row
            if stage == "predicate":
                self.last_predicate = row
                if row["context"].get("truthy") and row.get("remaining_end_ns", 0) < 0:
                    self.last_late_truth = row
                    self.late_truth_count += 1
            size = len(json.dumps(row, separators=(",", ":")))
            if (
                len(self.samples) < self.MAX_SAMPLES
                and size <= self.MAX_SAMPLE_BYTES
                and self.bytes + size <= self.MAX_BYTES
            ):
                self.samples.append(row)
                self.bytes += size
            else:
                self.dropped += 1


def note(**values):
    collector = ACTIVE.get()
    if collector is None or not collector.stack:
        return
    row = collector.stack[-1]
    for key, value in values.items():
        if key in COUNTS and type(value) is int and 0 <= value < 2**63:
            row["counters"][key] = value
        elif key == "checkpoint_id" and type(value) is int and 0 <= value < 2**63:
            row["context"][key] = value
        elif key == "truthy" and type(value) is bool:
            row["context"][key] = value
        elif key in HASHES and isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value):
            row["context"][key] = value
        elif (
            key in IDENTITIES
            and isinstance(value, str)
            and re.fullmatch(r"[a-f0-9-]{32,36}", value)
        ):
            row["context"][key] = value


@contextlib.contextmanager
def span(stage, owner=None):
    collector = ACTIVE.get()
    if collector is None:
        yield
    else:
        with collector.span(stage, owner):
            yield


def measured(stage):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            selected = stage
            if stage == "network_other" and len(args) > 1:
                selected = {"drain": "kafka_drain", "commit": "kafka_commit"}.get(args[1], stage)
            if stage == "journal_append" and len(args) > 1:
                selected = {
                    "ack": "journal_ack",
                    "ack_cursor": "journal_ack_cursor",
                    "ack_rejected": "journal_ack_rejected",
                }.get(args[1], stage)
            with span(selected, args[0] if args else None):
                return function(*args, **kwargs)

        return wrapped

    return decorate
