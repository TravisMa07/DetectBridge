"""Actual archive/current JVM execution with independent source and policy expectations."""

import argparse
import base64
import copy
import datetime
import errno
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from unittest.mock import patch

import current_replay as current
import historical as history
from check_contracts import load_json
from current_replay_cases import packet, prepare_plan, request
from historical_fixtures import archive_fixture, original
from historical_verify import HistoricalOracle, expect_helper_failure, semantic_check
from integration_oracle import FIELDS, Oracle
from stack import StackError


def instant(milliseconds):
    # Only the explicitly bounded new virtual clock is formatted; originals are never parsed.
    seconds, millis = divmod(milliseconds, 1000)
    value = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(seconds=seconds)
    return value.strftime("%Y-%m-%dT%H:%M:%S") + (f".{millis:03d}" if millis else "") + "Z"


def framed(entries, binding):
    output = []
    for entry in entries:
        kind, value = entry["kind"], entry["value"]
        key = value[FIELDS[kind]]
        wire = dict(
            key=base64.b64encode(key.encode()).decode(),
            value=base64.b64encode(history.encoded(value)).decode(),
            headers={
                "detectbridge.runtime.binding": binding,
                "detectbridge.intent.kind": kind,
                "detectbridge.intent.sequence": "0",
            },
        )
        output.append((kind, wire, value))
    return output


def snapshot(folder):
    return {
        str(p.relative_to(folder)): history.sha(p.read_bytes())
        for p in folder.rglob("*")
        if p.is_file()
    }


class CurrentOracle(Oracle):
    def __init__(self, plan, units, historical_request, spec, run, case):
        super().__init__({}, "synthetic-current-check", plan)
        # Frozen UUID ...0001 (Image) sorts before ...0004 (Bob); only ordinal bit 0
        # is quality-skipped. The old nine-rule packet's 0x134 mask is inapplicable.
        assert [rule["id"] for rule in plan["rules"]] == [
            "72000000-0000-4000-8000-000000000001",
            "72000000-0000-4000-8000-000000000004",
        ]
        self.expected["audit_skipped_bits"] = "0000000000000000000000001"
        by_label = {u["label"]: u for u in units}
        unit_refs = {u["id"]: u["inputs"] for u in historical_request["units"]}
        original_rows = {}
        for label, unit in by_label.items():
            for ref, row in zip(unit_refs[label], unit["inputs"], strict=True):
                original_rows[(ref["topic"], ref["offset"])] = row
        rows = []
        for step in spec["schedule"]:
            if step["action"] == "input":
                ref = step["input"]
                row = copy.deepcopy(original_rows[(ref["topic"], ref["offset"])])
                row["context"]["run_id"] = run
                row["context"]["receipt"] = dict(received=instant(step["at_ms"]))
                rows.append(row)
        self.rows = rows
        if case == "resource":
            # C05 supplemental literal: first two records lack CWD; the explicit member cap
            # closes that serial and later records retain the new closed-group link.
            self.manifest = self.group(
                rows[:2], "resource_limit", ["cwd_missing", "resource_limit"]
            )
            for row in rows[2:6]:
                self.preservation(row, "late_evidence", self.manifest)
        else:
            frozen = next(c for c in packet()["cases"] if c["id"] == case)
            self.manifest = self.group(rows[: frozen["audit_members"]], frozen["closure"], [])
            if frozen["late"]:
                self.preservation(rows[5], "late_evidence", self.manifest)
        self.event(rows[6], "auth")
        for expected in self.events.values():
            skipped = expected["scenario"] == "audit_skipped"
            expected["counts"] = (
                dict(
                    matched=0,
                    unmatched=0,
                    inapplicable=1,
                    configuration_blocked=0,
                    quality_skipped=1,
                    evaluation_error=0,
                )
                if skipped
                else packet()["counts"][expected["scenario"]]
            )
            expected["match_ids"] = (
                []
                if expected["scenario"] == "auth" or skipped
                else ["72000000-0000-4000-8000-000000000001"]
            )


class SupplementalOracle(HistoricalOracle):
    """Prior public field/quality oracles plus literal new-rule applicability."""

    def __init__(self, plan, units, spec, run):
        rewritten = copy.deepcopy(units)
        times = {
            history.encoded(step["input"]): step["at_ms"]
            for step in spec["schedule"]
            if step["action"] == "input"
        }
        # The fixture helper preserves ordered unit inputs and their original refs.
        position = 0
        admissions = [step for step in spec["schedule"] if step["action"] == "input"]
        assert len(times) == len(admissions)
        for unit in rewritten:
            for row in unit["inputs"]:
                row["context"]["run_id"] = run
                row["context"]["receipt"] = dict(received=instant(admissions[position]["at_ms"]))
                position += 1
        super().__init__({}, "synthetic-current-supplemental", plan, rewritten)
        for expected in self.events.values():
            expected["counts"] = (
                dict(
                    matched=0,
                    unmatched=0,
                    inapplicable=2,
                    configuration_blocked=0,
                    quality_skipped=0,
                    evaluation_error=0,
                )
                if expected["rows"][0]["kind"] == "windows_record"
                else packet()["counts"]["auth"]
            )
            expected["match_ids"] = []

    def check_source(self, event, expected):
        if expected["rows"][0]["kind"] == "windows_record":
            event = copy.deepcopy(event)
            receipt = event["detectbridge"]["time"].pop("received")
            assert receipt == expected["rows"][0]["context"]["receipt"]["received"]
            assert "processed" not in event["detectbridge"]["time"]
        super().check_source(event, expected)


def supplemental(folder, observed, base_spec, plan_path, plan):
    folder.mkdir(mode=0o700)
    labels = {
        "security",
        "sysmon",
        "windows_skipped",
        "windows_budget",
        "windows_extraction",
        "auth_range_0",
        "auth_range_1",
        "auth_empty",
        "auth_crlf",
        "auth_precision",
    }
    selected = [unit for unit in observed if unit["label"] in labels]
    assert {unit["label"] for unit in selected} == labels
    old_plan = history.ROOT / ".cache/integration/plan.json"
    old = HistoricalOracle(
        {}, "synthetic-current-supplemental-original", load_json(old_plan), selected
    )
    assert old.check(
        framed([entry for unit in selected for entry in unit["original_outputs"]], old.binding)
    )
    shutil.copytree(folder.parent / "evidence", folder / "evidence")
    archive, original_request = archive_fixture(folder, selected, old_plan)
    catalog = folder / "historical-catalog"
    selection = history.seal(archive, catalog, original_request, old_plan)["selection_sha256"]
    spec = copy.deepcopy(base_spec)
    spec["selection_sha256"] = selection
    refs = [ref for unit in load_json(original_request)["units"] for ref in unit["inputs"]]
    spec["schedule"] = [dict(at_ms=i, action="input", input=ref) for i, ref in enumerate(refs)]
    spec["schedule"].append(dict(at_ms=len(refs), action="end", input=None))
    request_path = folder / "current-request.json"
    request_path.write_bytes(history.encoded(spec) + b"\n")
    workspace = folder / "current-workspace"
    run = str(uuid.uuid4())
    protected = snapshot(archive), snapshot(catalog)
    current.replay(archive, catalog, workspace, request_path, plan_path, run)
    transitions = results(workspace, run)
    assert len(transitions) == len(spec["schedule"])
    for index, transition in enumerate(transitions):
        assert transition["index"] == index and transition["step"] == spec["schedule"][index]
        assert transition["run_id"] == run and transition["mode"] == "current"
        assert transition["origin_selection_sha256"] == selection
        assert transition["request_sha256"] == history.sha(history.encoded(spec))
    state = transitions[-1]["state"]
    assert state["assembler"]["runs"][run] == "ended"
    assert not state["assembler"]["groups"] and not state["inbox"] and not state["outbox"]
    entries = [entry for transition in transitions for entry in transition["outputs"]]
    oracle = SupplementalOracle(plan, selected, spec, run)
    assert oracle.check(framed(entries, oracle.binding))
    tags = [entry["value"] for entry in entries if entry["kind"] == "tagged"]
    range_rows = [unit["inputs"][0] for unit in selected if unit["label"].startswith("auth_range_")]
    assert range_rows[0]["raw"]["evidence"]["sha256"] == range_rows[1]["raw"]["evidence"]["sha256"]
    records = {row["raw"]["record_id"] for row in range_rows}
    assert len(records) == 2
    range_events = [
        tag["event"]["event"]["id"]
        for tag in tags
        if tag["event"]["detectbridge"]["evidence"][0]["record_id"] in records
    ]
    assert len(set(range_events)) == 2
    assert protected == (snapshot(archive), snapshot(catalog))
    return dict(
        cases=sorted(labels),
        inputs=len(refs),
        outputs=len(entries),
        same_bytes_distinct_occurrences=True,
    )


def results(workspace, run):
    return [
        history.document(p, 24 * history.MIB)
        for p in sorted((workspace / "runs" / run / "units").glob("*/result.json"))
    ]


def check_current(workspace, run, plan, units, historical_request, spec, case):
    oracle = CurrentOracle(plan, units, historical_request, spec, run, case)
    if case == "regroup":
        original_group = next(unit for unit in units if unit["label"] == "audit_timeout")
        original_manifest = next(
            entry["value"]
            for entry in original_group["original_outputs"]
            if entry["kind"] == "manifest"
        )
        assert oracle.manifest["event_id"] != original_manifest["event_id"]
    transitions = results(workspace, run)
    assert len(transitions) == len(spec["schedule"])
    entries = []
    for index, transition in enumerate(transitions):
        assert transition["index"] == index and transition["step"] == spec["schedule"][index]
        assert transition["mode"] == "current" and transition["run_id"] == run
        assert transition["origin_selection_sha256"] == spec["selection_sha256"]
        assert transition["request_sha256"] == history.sha(history.encoded(spec))
        assert transition["transition_id"] == history.sha(
            history.encoded(
                ["detectbridge.current.transition/1", run, transition["request_sha256"], index]
            )
        )
        entries.extend(transition["outputs"])
    assert oracle.check(framed(entries, oracle.binding))
    tags = [e["value"] for e in entries if e["kind"] == "tagged"]
    for tag in tags:
        event = tag["event"]
        expected = oracle.events[(run, event["event"]["id"])]
        assert (
            event["detectbridge"]["time"]["first_observed"]
            == expected["rows"][0]["raw"]["first_observed"]
        )
        context = event["detectbridge"]["extensions"]["linux.context"]["context"]
        assert context["receipt"] == expected["rows"][0]["context"]["receipt"]
        assert "processed" not in context["receipt"]
    final = transitions[-1]["state"]
    assert final["assembler"]["runs"][run] == "ended" and not final["assembler"]["groups"]
    assert not final["inbox"] and not final["outbox"]
    return entries


def prepare(folder):
    old_plan = history.ROOT / ".cache/integration/plan.json"
    observed = original(folder, old_plan)
    units = [u for u in observed if u["label"] in {"audit_timeout", "late", "auth"}]
    old = HistoricalOracle({}, "synthetic-current-original-check", load_json(old_plan), units)
    assert old.check(framed([e for u in units for e in u["original_outputs"]], old.binding))
    archive, original_request = archive_fixture(folder, units, old_plan)
    catalog = folder / "historical-catalog"
    selection = history.seal(archive, catalog, original_request, old_plan)["selection_sha256"]
    new_plan = folder / "new-plan.json"
    plan = prepare_plan(new_plan)
    assert history.sha(new_plan.read_bytes()) != history.sha(old_plan.read_bytes())
    return archive, catalog, selection, original_request, new_plan, plan, units


def rejected(action, category):
    try:
        action()
    except ValueError as error:
        assert str(error) == category, (type(error).__name__, category)
    else:
        raise AssertionError("expected " + category)


def interrupted(archive, catalog, folder, spec_path, plan_path, phase):
    workspace = folder / ("kill-" + phase)
    run = str(uuid.uuid4())
    code = """import os,sys
sys.path.insert(0,'tools')
import current_replay as c
import historical as h
armed=False
def hook(phase):
 global armed
 if phase=='during_payload':armed=True
 if armed and phase==sys.argv[7]:os._exit(77)
h.HOOK=hook
c.replay(*sys.argv[1:7])
"""
    outcome = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(archive),
            str(catalog),
            str(workspace),
            str(spec_path),
            str(plan_path),
            run,
            phase,
        ],
        cwd=history.ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert outcome.returncode == 77, (phase, outcome.returncode)
    prefix = snapshot(workspace / "runs" / run / "units")
    current.replay(archive, catalog, workspace, spec_path, plan_path, run, True)
    after = snapshot(workspace / "runs" / run / "units")
    assert all(after.get(k) == v for k, v in prefix.items())
    return workspace, run, len(prefix) // 3


def negative_commits(action, destination):
    unit = destination / "units" / "000001"
    saved = {p: p.read_bytes() for p in unit.iterdir()}
    cases = []
    try:
        result = load_json(unit / "result.json")
        result["state"]["binding"] = "conflicting-state"
        payload = history.encoded(result) + b"\n"
        (unit / "result.json").write_bytes(payload)
        commit = load_json(unit / "commit.json")
        commit.update(result_sha256=history.sha(payload), result_bytes=len(payload))
        metadata = history.encoded(commit) + b"\n"
        (unit / "commit.json").write_bytes(metadata)
        (unit / "commit.sha256").write_text(history.sha(metadata) + "\n")
        before = snapshot(destination)
        rejected(action, "current_committed_result_conflict")
        assert before == snapshot(destination)
        cases.append("compensated-result-corruption")
    finally:
        for path, value in saved.items():
            path.write_bytes(value)
    try:
        commit = load_json(unit / "commit.json")
        commit["index"] = 1.0
        metadata = history.encoded(commit) + b"\n"
        (unit / "commit.json").write_bytes(metadata)
        (unit / "commit.sha256").write_text(history.sha(metadata) + "\n")
        before = snapshot(destination)
        rejected(action, "historical_metadata_integer")
        assert before == snapshot(destination)
        cases.append("fractional-commit-counter")
    finally:
        for path, value in saved.items():
            path.write_bytes(value)
    missing = unit / "result.json"
    held = destination.parent.parent.parent / "held-result"
    missing.rename(held)
    try:
        before = snapshot(destination)
        rejected(action, "historical_unexpected_contents")
        assert before == snapshot(destination)
        cases.append("missing-middle-result")
    finally:
        held.rename(missing)
    held = destination.parent.parent.parent / "held-unit"
    unit.rename(held)
    try:
        before = snapshot(destination)
        rejected(action, "current_transition_prefix")
        assert before == snapshot(destination)
        cases.append("missing-middle-unit")
    finally:
        held.rename(unit)
    return cases


def oracle_mutations(entries, plan, units, hrequest, spec, run):
    checks = []
    for case in ("counts", "attribution", "membership", "source-host"):
        changed = copy.deepcopy(entries)
        tag = next(e["value"] for e in changed if e["kind"] == "tagged")
        if case == "counts":
            # Keep the rule total unchanged: this must fail semantic expectations.
            tag["counts"]["matched"] = 0
            tag["counts"]["unmatched"] = 1
        elif case == "attribution":
            tag["attribution"]["bundle_sha256"] = "0" * 64
        elif case == "membership":
            manifest = next(e["value"] for e in changed if e["kind"] == "manifest")
            manifest["members"] = list(reversed(manifest["members"]))
        else:
            tag["event"]["host"]["id"] = "wrong-host"
        oracle = CurrentOracle(plan, units, hrequest, spec, run, "regroup")
        try:
            passed = oracle.check(framed(changed, oracle.binding))
        except StackError as error:
            assert str(error) == "assembly_independent_expectation_failed"
            passed = False
        except AssertionError:
            passed = False
        assert not passed, case
        checks.append(case)
    return checks


def helper_recovery(workspace):
    code = """import sys
sys.path.insert(0,'tools')
import current_replay as c
import historical as h
with c.workspace(sys.argv[1]) as root:
 stage=h.partial(root)
 h.container(h.Stack().image('flink'),[(stage,'/out',False)],['sleep','300'])
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(workspace)],
        cwd=history.ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    name = history.helper_name(workspace)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            outcome = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if outcome.returncode == 0 and outcome.stdout.strip() == "true":
                break
            assert child.poll() is None
            time.sleep(0.1)
        else:
            raise AssertionError("owned helper did not start")
        child.kill()
        child.wait(timeout=10)
        with current.workspace(workspace):
            pass
        assert (
            subprocess.run(["docker", "inspect", name], capture_output=True, timeout=10).returncode
            != 0
        )
        assert not (workspace / "helper.active").exists()
        original_command = history.command

        def bounded(args, timeout=90, diagnostics=None):
            return original_command(
                args, 1 if list(args[:3]) == ["docker", "start", "-a"] else timeout, diagnostics
            )

        with current.workspace(workspace) as root:
            stage = history.partial(root)
            with patch.object(history, "command", bounded):
                try:
                    history.container(
                        history.Stack().image("flink"), [(stage, "/out", False)], ["sleep", "30"]
                    )
                except subprocess.TimeoutExpired as error:
                    assert error.cmd[:3] == ["docker", "start", "-a"]
                else:
                    raise AssertionError("executor wait did not time out")
        assert (
            subprocess.run(["docker", "inspect", name], capture_output=True, timeout=10).returncode
            != 0
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        with current.workspace(workspace):
            pass


def preflight_cases(folder, archive, catalog, spec, plan_path):
    workspace = folder / "preflight-workspace"
    cases = {}
    for case in (
        "missing",
        "duplicate",
        "foreign",
        "backwards",
        "fractional",
        "missing-end",
        "mode",
        "profile",
        "enrichment",
    ):
        value = copy.deepcopy(spec)
        category = "current_schema_request"
        if case == "missing":
            value["schedule"].pop(0)
            category = "current_missing_selected_input"
        elif case == "duplicate":
            value["schedule"].insert(0, copy.deepcopy(value["schedule"][0]))
            category = "current_duplicate_input"
        elif case == "foreign":
            value["schedule"][0]["input"]["offset"] += 999
            category = "current_foreign_input"
        elif case == "backwards":
            value["schedule"][0]["at_ms"] = 3
            category = "current_schedule_order"
        elif case == "fractional":
            value["schedule"][0]["at_ms"] = 0.0
        elif case == "missing-end":
            value["schedule"].pop()
            category = "current_missing_end"
        elif case == "mode":
            value["mode"] = "historical"
        elif case == "profile":
            value["engine_profile"] = "unsupported-profile"
        else:
            value["enrichment"] = [{}]
        path = folder / ("preflight-" + case + ".json")
        path.write_bytes(history.encoded(value) + b"\n")
        rejected(
            lambda: current.replay(archive, catalog, workspace, path, plan_path, str(uuid.uuid4())),
            category,
        )
        assert not workspace.exists()
        cases[case] = category
    oversized = folder / "oversized-request.json"
    oversized.write_bytes(b" " * (history.MIB + 1))
    rejected(
        lambda: current.replay(
            archive, catalog, workspace, oversized, plan_path, str(uuid.uuid4())
        ),
        "historical_file_limit",
    )
    assert not workspace.exists()
    cases["request-over-one-mib"] = "historical_file_limit"
    return cases


def protected_root_cases(folder, archive, catalog, spec_path, plan_path):
    protected = snapshot(archive), snapshot(catalog)
    independent = folder / "unused-overlap-workspace"
    cases = {
        "archive-equal-workspace": (archive, catalog, archive),
        "catalog-equal-workspace": (archive, catalog, catalog),
        "archive-ancestor-workspace": (archive, catalog, archive / "current"),
        "catalog-ancestor-workspace": (archive, catalog, catalog / "current"),
        "workspace-ancestor-sources": (archive, catalog, folder),
        "archive-equal-catalog": (archive, archive, independent),
        "archive-inside-catalog": (catalog / "nested", catalog, independent),
        "catalog-inside-archive": (archive, archive / "nested", independent),
    }
    for roots in cases.values():
        rejected(
            lambda: current.replay(*roots, spec_path, plan_path, str(uuid.uuid4())),
            "current_root_overlap",
        )
        assert protected == (snapshot(archive), snapshot(catalog))
        assert not independent.exists()
    return sorted(cases)


def full_cases(
    folder,
    archive,
    catalog,
    selection,
    hrequest,
    plan_path,
    plan,
    units,
    spec_path,
    spec,
    workspace,
    run,
    entries,
    report,
):
    original_request = load_json(hrequest)
    report["phase"] = "historical-compatibility"
    historical_run = str(uuid.uuid4())
    history.replay(archive, catalog, selection, historical_run)
    semantic_check(
        catalog, units, load_json(history.ROOT / ".cache/integration/plan.json"), historical_run
    )
    protected = {"archive": snapshot(archive), "historical": snapshot(catalog)}
    report["historical_compatibility"] = True
    report["phase"] = "supplemental-sources"
    report["supplemental_sources"] = supplemental(
        folder / "supplemental", load_json(folder / "original.json"), spec, plan_path, plan
    )
    report["phase"] = "completed-resume-and-two-run-isolation"
    run_path = workspace / "runs" / run

    def action():
        return current.replay(archive, catalog, workspace, spec_path, plan_path, run, True)

    before = snapshot(run_path)
    final = results(workspace, run)[-1]["state"]
    fingerprint = final["received_hash"], final["sha256"]
    for _ in range(3):
        action()
        assert before == snapshot(run_path)
        restored = results(workspace, run)[-1]["state"]
        assert fingerprint == (restored["received_hash"], restored["sha256"])
    report["completed_resume_unchanged"] = True
    report["completed_resume_fresh_jvms"] = 3
    exact_request = folder / "exact-one-mib-request.json"
    body = history.encoded(spec)
    exact_request.write_bytes(body + b" " * (history.MIB - len(body)))
    assert exact_request.stat().st_size == history.MIB
    current.replay(archive, catalog, workspace, exact_request, plan_path, run, True)
    assert before == snapshot(run_path)
    report["request_exact_one_mib"] = True
    second = str(uuid.uuid4())
    current.replay(archive, catalog, workspace, spec_path, plan_path, second)
    other = check_current(workspace, second, plan, units, original_request, spec, "regroup")
    for kind in ("tagged", "detection", "processing"):
        left = {e["value"][FIELDS[kind]] for e in entries if e["kind"] == kind}
        right = {e["value"][FIELDS[kind]] for e in other if e["kind"] == kind}
        assert left.isdisjoint(right)
        if kind != "processing":
            assert left and right
    assert {e["value"]["event"]["event"]["id"] for e in entries if e["kind"] == "tagged"} == {
        e["value"]["event"]["event"]["id"] for e in other if e["kind"] == "tagged"
    }
    report["two_run_isolation"] = True
    report["schedule_results"] = {}
    for case in ("timeout", "deadline", "short-age", "resource"):
        report["phase"] = "schedule-" + case
        chosen = request(
            selection,
            original_request,
            history.sha(plan_path.read_bytes()),
            "regroup" if case in ("short-age", "resource") else case,
        )
        if case == "short-age":
            chosen["assembler_limits"]["age_ms"] = 1
        if case == "resource":
            chosen["assembler_limits"]["members"] = 2
        path = folder / (case + "-request.json")
        path.write_bytes(history.encoded(chosen) + b"\n")
        identity = str(uuid.uuid4())
        current.replay(archive, catalog, workspace, path, plan_path, identity)
        observed = check_current(
            workspace,
            identity,
            plan,
            units,
            original_request,
            chosen,
            "timeout" if case == "short-age" else case,
        )
        report["schedule_results"][case] = dict(
            transitions=len(chosen["schedule"]),
            outputs={kind: sum(entry["kind"] == kind for entry in observed) for kind in FIELDS},
        )
    report["schedule_cases"] = ["regroup", "timeout", "deadline", "short-age", "resource"]
    report["phase"] = "oracle-mutations"
    report["oracle_mutations"] = oracle_mutations(entries, plan, units, original_request, spec, run)
    report["phase"] = "preflight-rejections"
    report["preflight"] = preflight_cases(folder, archive, catalog, spec, plan_path)
    report["protected_roots"] = protected_root_cases(folder, archive, catalog, spec_path, plan_path)
    phases = (
        "during_payload",
        "before_payload_sync",
        "during_metadata",
        "before_metadata_sync",
        "before_publication",
        "after_publication",
        "after_directory_sync",
        "before_advisory",
        "during_advisory",
        "before_advisory_sync",
        "after_advisory_rename",
    )
    report["process_interruptions"] = []
    for phase in phases:
        report["phase"] = "kill-" + phase
        killed, identity, committed = interrupted(
            archive, catalog, folder, spec_path, plan_path, phase
        )
        check_current(killed, identity, plan, units, original_request, spec, "regroup")
        report["process_interruptions"].append(dict(phase=phase, retained_transitions=committed))
    report["phase"] = "negative-bindings-and-commits"
    changed = copy.deepcopy(spec)
    changed["assembler_limits"]["age_ms"] -= 1
    changed_path = folder / "changed-request.json"
    changed_path.write_bytes(history.encoded(changed) + b"\n")
    rejected(
        lambda: current.replay(archive, catalog, workspace, changed_path, plan_path, run, True),
        "current_resume_binding",
    )
    rejected(
        lambda: current.replay(archive, catalog, workspace, spec_path, plan_path, historical_run),
        "current_run_reuse",
    )
    rejected(
        lambda: current.replay(
            archive, catalog, workspace, spec_path, plan_path, original_request["original_run_id"]
        ),
        "current_run_reuse",
    )
    assert before == snapshot(run_path)
    report["negative_commits"] = negative_commits(action, run_path)
    report["phase"] = "helper-recovery"
    helper_recovery(folder / "orphan-workspace")
    report["owned_helper_cleanup"] = ["killed-controller", "executor-wait-timeout"]
    report["phase"] = "missing-dependencies-and-budgets"
    relocated = folder / "relocated-workspace"
    shutil.copytree(workspace, relocated)
    rejected(
        lambda: current.replay(archive, catalog, relocated, spec_path, plan_path, run, True),
        "current_workspace_binding",
    )
    shutil.rmtree(relocated)
    pinned = history.verified(catalog / "pins" / selection / "selection.json")["executor_sha256"]
    artifact = catalog / "artifacts" / pinned
    held = folder / "held-artifact"
    artifact.rename(held)
    try:
        rejected(action, "historical_file_limit")
        assert before == snapshot(run_path)
    finally:
        held.rename(artifact)
    report["missing_pinned_artifact"] = True
    original_object = next((archive / "objects").iterdir())
    held_object = folder / "held-original-object"
    original_object.rename(held_object)
    try:
        expect_helper_failure(action, workspace, "historical_missing_object")
        assert before == snapshot(run_path)
    finally:
        held_object.rename(original_object)
    report["missing_original_object"] = True
    plan_bytes = plan_path.read_bytes()
    try:
        plan_path.write_bytes(plan_bytes + b" ")
        rejected(action, "current_plan_integrity")
        assert before == snapshot(run_path)
    finally:
        plan_path.write_bytes(plan_bytes)
    report["changed_plan_rejected"] = True
    # The reserve boundary is injected exactly at workspace accounting; originals stay real.
    original_size = history.tree_bytes

    def capped(path):
        return current.LIMITS["storage_bytes"] + 1 if path == workspace else original_size(path)

    with patch.object(history, "tree_bytes", capped):
        rejected(action, "historical_storage_budget")
    report["storage_cap_rejected"] = True
    report["permission_denial"] = "unavailable-root-user" if os.geteuid() == 0 else "passed"
    if os.geteuid() != 0:
        permissions = workspace.stat().st_mode & 0o777
        workspace.chmod(0o500)
        try:
            try:
                action()
            except PermissionError as error:
                assert error.filename is not None
                assert history.safe(error.filename).parent == workspace
            else:
                raise AssertionError("workspace permission failure absent")
            assert before == snapshot(run_path)
        finally:
            workspace.chmod(permissions)
    report["injected_io"] = []
    for phase, number in (("during_payload", errno.ENOSPC), ("before_payload_sync", errno.EIO)):
        report["phase"] = "injected-io-" + phase
        failing = folder / ("io-" + phase)
        identity = str(uuid.uuid4())

        def hook(observed, target=phase, error=number):
            if observed == target:
                raise OSError(error, "injected-current-write-failure")

        try:
            with patch.object(history, "HOOK", hook):
                current.replay(archive, catalog, failing, spec_path, plan_path, identity)
        except OSError as error:
            assert error.errno == number
        else:
            raise AssertionError("expected injected I/O failure")
        assert not list((failing / "runs").glob("*/units/*"))
        current.replay(
            archive,
            catalog,
            failing,
            spec_path,
            plan_path,
            identity,
            (failing / "runs" / identity).exists(),
        )
        check_current(failing, identity, plan, units, original_request, spec, "regroup")
        report["injected_io"].append(dict(phase=phase, errno=number))
    assert before == snapshot(run_path)
    assert protected == {"archive": snapshot(archive), "historical": snapshot(catalog)}
    report["historical_and_archive_unchanged"] = True
    report["limits"] = [
        "synthetic source fixtures only",
        "no Kafka delivery or throughput claim",
        "process interruption and injected I/O; no physical disk/power-loss claim",
    ]


def image_identity(image):
    # Match the canonical immutable reference prepared by historical.build().
    repository, digest = image.split("@")
    prepared = repository.rsplit(":", 1)[0] + "@" + digest
    identity = (
        subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                prepared,
                "--format",
                "{{.Id}} {{.Os}} {{.Architecture}}",
            ],
            text=True,
        )
        .strip()
        .split()
    )
    assert len(identity) == 3 and identity[0].startswith("sha256:") and len(identity[0]) == 71
    return dict(id=identity[0], os=identity[1], architecture=identity[2])


def qualify(focused=False):
    folder = history.ROOT / ".cache" / ("current-replay-qualification-" + uuid.uuid4().hex[:12])
    folder.mkdir(mode=0o700)
    report = dict(
        status="running",
        phase="prepare-originals-and-selection",
        folder=str(folder),
        bundle=history.document(current.BUILDS / "bundle.json"),
        platform=platform.platform(),
        source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        source_sha256={
            str(path.relative_to(history.ROOT)): history.sha(path.read_bytes())
            for path in sorted(
                [
                    *(history.ROOT / "packages/current-replay/src").rglob("*.java"),
                    *(history.ROOT / "contracts/current-replay/v1").rglob("*.json"),
                    *(history.ROOT / "contracts/current-replay/v1/fixtures").glob("*.yml"),
                    *(
                        history.ROOT / name
                        for name in (
                            "packages/current-replay/build.gradle.kts",
                            "packages/current-replay/gradle.lockfile",
                            "uv.lock",
                            "pyproject.toml",
                            "tools/check_contracts.py",
                            "tools/current_replay.py",
                            "tools/current_replay_verify.py",
                            "tools/current_replay_cases.py",
                            "tools/historical.py",
                            "tools/historical_verify.py",
                            "tools/historical_fixtures.py",
                            "tools/integration_oracle.py",
                            "tools/linux_assembly_verify.py",
                            "tools/linux_assembly_cases.py",
                            "tools/check_integration.py",
                        )
                    ),
                ]
            )
        },
        working_diff_sha256=history.sha(subprocess.check_output(["git", "diff", "HEAD"])),
    )
    path = folder / "report.json"
    path.write_bytes(history.encoded(report) + b"\n")
    try:
        report["docker_image"] = image_identity(report["bundle"]["image"])
        report["qualification_source_sha256"] = history.sha(
            history.encoded(report["source_sha256"])
        )
        archive, catalog, selection, hrequest, new_plan, plan, units = prepare(folder)
        spec = request(selection, load_json(hrequest), history.sha(new_plan.read_bytes()))
        spec_path = folder / "current-request.json"
        spec_path.write_bytes(history.encoded(spec) + b"\n")
        workspace = folder / "current-workspace"
        run = str(uuid.uuid4())
        protected = {"archive": snapshot(archive), "historical": snapshot(catalog)}
        report["phase"] = "focused-regroup"
        current.replay(archive, catalog, workspace, spec_path, new_plan, run)
        entries = check_current(workspace, run, plan, units, load_json(hrequest), spec, "regroup")
        assert protected == {"archive": snapshot(archive), "historical": snapshot(catalog)}
        if not focused:
            full_cases(
                folder,
                archive,
                catalog,
                selection,
                hrequest,
                new_plan,
                plan,
                units,
                spec_path,
                spec,
                workspace,
                run,
                entries,
                report,
            )
        report.update(
            status="qualified",
            phase="complete",
            focused=focused,
            selection_sha256=selection,
            run_id=run,
            inputs=7,
            transitions=len(spec["schedule"]),
            outputs=len(entries),
            plan_sha256=history.sha(new_plan.read_bytes()),
            bundle_sha256=plan["bundle_sha256"],
        )
    except Exception as error:
        report.update(status="failed", failure_class=type(error).__name__)
        raise
    finally:
        path.write_bytes(history.encoded(report) + b"\n")
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--focused", action="store_true")
    qualify(parser.parse_args().focused)
