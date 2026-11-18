"""Actual pinned-JVM archive replay, independent source oracles and process faults."""

import base64
import copy
import json
import subprocess
import sys
import time
import uuid

import historical as history
from check_contracts import load_json
from historical_fixtures import PACKET, archive_fixture, original
from integration_oracle import FIELDS, Oracle


class HistoricalOracle(Oracle):
    def __init__(self, config, binding, plan, units, run=None):
        super().__init__(config, binding, plan)
        self.windows_expected = {}
        self.windows_seen = set()
        cases = {c["id"]: c for c in load_json(PACKET)["cases"]}
        cases.update(
            audit_dataset_end=dict(scenario="audit", closure="dataset_end", findings=[]),
            audit_resource=dict(
                scenario="audit_skipped",
                closure="resource_limit",
                findings=["cwd_missing", "resource_limit"],
            ),
        )
        for unit in units:
            case = cases.get(unit["label"], dict(scenario="auth"))
            assert unit["label"] in cases or unit["label"] in {
                "auth_range_0",
                "auth_range_1",
                "auth_empty",
                "auth_crlf",
                "auth_precision",
            }
            rows = copy.deepcopy(unit["inputs"])
            if run:
                for row in rows:
                    row["context"]["run_id"] = run
            if unit["kind"] == "audit":
                self.group(rows, case["closure"], case["findings"])
            elif unit["kind"] == "audit_preservation":
                self.preservation(rows[0], "late_evidence", unit["anchor"])
            elif unit["label"] in {"auth_empty", "auth_crlf"}:
                self.preservation(
                    rows[0],
                    "unsupported_source" if unit["label"] == "auth_empty" else "extraction_failed",
                )
            elif unit["label"] == "windows_extraction":
                row = rows[0]
                raw = row["raw"]
                diagnostic = dict(
                    version="1.0.0",
                    run_id=row["context"]["run_id"],
                    record_id=raw["record_id"],
                    evidence_sha256=raw["evidence"]["sha256"],
                    code="extraction_failed",
                    reason="xml_or_limit",
                    field="",
                )
                self.windows_expected[history.sha(history.encoded(diagnostic))] = dict(
                    diagnostic=diagnostic, source=raw["source"]
                )
            else:
                self.event(rows[0], case["scenario"])

    def check_windows_preservation(self, document):
        key = history.sha(history.encoded(document["diagnostic"]))
        assert self.windows_expected[key] == dict(
            diagnostic=document["diagnostic"], source=document["source"]
        )
        self.windows_seen.add(key)

    def check(self, outputs):
        return super().check(outputs) and self.windows_seen == set(self.windows_expected)


def semantic_check(folder, units, plan, run):
    """Adapter wrappers only: these synthetic wire headers make no Kafka-delivery claim."""
    oracle = HistoricalOracle({}, "synthetic-history-check", plan, units, run)
    output = []
    for p in sorted((folder / "runs" / run / "units").glob("*/result.json")):
        result = load_json(p)
        for entry in result["outputs"]:
            kind, value = entry["kind"], entry["value"]
            key = value[FIELDS[kind]]
            wire = dict(
                key=base64.b64encode(key.encode()).decode(),
                value=base64.b64encode(history.encoded(value)).decode(),
                headers={
                    "detectbridge.runtime.binding": oracle.binding,
                    "detectbridge.intent.kind": kind,
                    "detectbridge.intent.sequence": "0",
                },
            )
            output.append((kind, wire, value))
    assert oracle.check(output)
    return output


def snapshot(folder):
    return {
        str(p.relative_to(folder)): history.sha(p.read_bytes())
        for p in folder.rglob("*")
        if p.is_file()
    }


def fault_driver(archive, catalog, selection, run, phase):
    code = """import os,sys
sys.path.insert(0,'tools')
import historical as h
armed=False
def hook(phase):
 global armed
 if phase=='during_payload':armed=True
 if armed and phase==sys.argv[5]:os._exit(77)
h.HOOK=hook
h.replay(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4])
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(archive), str(catalog), selection, run, phase],
        cwd=history.ROOT,
    )
    assert result.returncode == 77, (phase, result.returncode)
    before = snapshot(catalog / "runs" / run / "units")
    history.replay(archive, catalog, selection, run, True)
    after = snapshot(catalog / "runs" / run / "units")
    assert all(after[k] == v for k, v in before.items())


def helper_recovery(catalog):
    code = """import sys
sys.path.insert(0,'tools')
import historical as h
with h.catalog(sys.argv[1]) as root:
 stage=h.partial(root)
 h.container(h.Stack().image('flink'),[(stage,'/out',False)],['sleep','300'])
"""
    child = subprocess.Popen([sys.executable, "-c", code, str(catalog)], cwd=history.ROOT)
    name = history.helper_name(catalog)
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip() == "true":
                break
            assert child.poll() is None
            time.sleep(0.1)
        else:
            raise AssertionError("helper did not start")
        child.kill()
        child.wait(timeout=10)
        with history.catalog(catalog):
            pass
        assert subprocess.run(["docker", "inspect", name], capture_output=True).returncode != 0
        assert not (catalog / "helper.active").exists()
        with history.catalog(catalog) as root:
            stage = history.partial(root)
            try:
                history.container(
                    history.Stack().image("flink"),
                    [(stage, "/out", False)],
                    ["sleep", "300"],
                    timeout=1,
                )
            except subprocess.TimeoutExpired:
                pass
            else:
                raise AssertionError("helper timeout absent")
        assert subprocess.run(["docker", "inspect", name], capture_output=True).returncode != 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        with history.catalog(catalog):
            pass


def seal_faults(folder, archive, request, plan, expected):
    phases = [
        "during_file",
        "after_artifact_publication",
        "during_metadata",
        "before_metadata_sync",
        "before_publication",
        "after_publication",
        "after_directory_sync",
    ]
    code = """import os,sys
sys.path.insert(0,'tools')
import historical as h
h.HOOK=lambda phase:os._exit(78) if phase==sys.argv[5] else None
h.seal(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4])
"""
    for phase in phases:
        path = folder / ("seal-fault-" + phase)
        with history.catalog(path):
            pass
        result = subprocess.run(
            [sys.executable, "-c", code, str(archive), str(path), str(request), str(plan), phase],
            cwd=history.ROOT,
        )
        assert result.returncode == 78, (phase, result.returncode)
        assert history.seal(archive, path, request, plan)["selection_sha256"] == expected
        assert len(list((path / "pins").iterdir())) == 1
    return phases


def expect_helper_failure(action, catalog, reason):
    before = set((catalog / "failures").glob("*.json"))
    try:
        action()
    except ValueError:
        failures = set((catalog / "failures").glob("*.json")) - before
        assert any(reason in load_json(p)["stderr"] for p in failures), reason
    else:
        raise AssertionError("missing expected failure " + reason)


def component(folder, plan):
    units = original(folder, plan)
    archive, request = archive_fixture(folder, units, plan)
    catalog = folder / "catalog"
    selected = history.seal(archive, catalog, request, plan)["selection_sha256"]
    results = []
    for _ in range(2):
        run = str(uuid.uuid4())
        history.replay(archive, catalog, selected, run)
        results.append(semantic_check(catalog, units, load_json(plan), run))
        before = snapshot(catalog / "runs" / run)
        history.replay(archive, catalog, selected, run, True)
        assert snapshot(catalog / "runs" / run) == before

    def ids(rows, kind):
        return {doc[FIELDS[kind]] for k, _, doc in rows if k == kind}

    assert ids(results[0], "tagged").isdisjoint(ids(results[1], "tagged"))
    assert ids(results[0], "detection").isdisjoint(ids(results[1], "detection"))
    assert {d["event"]["event"]["id"] for k, _, d in results[0] if k == "tagged"} == {
        d["event"]["event"]["id"] for k, _, d in results[1] if k == "tagged"
    }
    # A one-unit selection isolates publication faults from unrelated source work.
    small = load_json(request)
    small["units"] = small["units"][:1]
    small_path = folder / "small-request.json"
    small_path.write_bytes(history.encoded(small))
    small_hash = history.seal(archive, catalog, small_path, plan)["selection_sha256"]
    phases = [
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
    ]
    for phase in phases:
        fault_driver(archive, catalog, small_hash, str(uuid.uuid4()), phase)
    # Changed original output membership/counts must not seal, even with a correct wire reference.
    bad = copy.deepcopy(small)
    bad["units"][0]["outputs"] = bad["units"][0]["outputs"][:1]
    bad_path = folder / "missing-output.json"
    bad_path.write_bytes(history.encoded(bad))
    failures_before = set((catalog / "failures").glob("*.json"))
    try:
        history.seal(archive, catalog, bad_path, plan)
    except ValueError:
        failures = set((catalog / "failures").glob("*.json")) - failures_before
        assert any(
            "historical_original_outputs_mismatch" in load_json(p)["stderr"] for p in failures
        )
    else:
        raise AssertionError("missing output sealed")
    sealed_faults = seal_faults(folder, archive, small_path, plan, small_hash)
    helper_recovery(catalog)
    invalid = folder / "invalid-wrapper"
    invalid.mkdir()
    altered = copy.deepcopy(units[:1])
    altered[0]["inputs"][0]["unexpected"] = "unsupported original wrapper"
    altered_root, altered_request = archive_fixture(invalid, altered, plan)
    try:
        history.seal(altered_root, folder / "invalid-catalog", altered_request, plan)
    except ValueError:
        assert any(
            "historical_runtime_schema" in load_json(p)["stderr"]
            for p in (folder / "invalid-catalog/failures").glob("*.json")
        )
    else:
        raise AssertionError("invalid original input wrapper sealed")
    run = next((catalog / "runs").iterdir()).name
    commit = next((catalog / "runs" / run / "units").glob("*/commit.json"))
    sidecar = commit.with_suffix(".sha256")
    saved = (commit.read_bytes(), sidecar.read_bytes())
    changed = load_json(commit)
    changed["index"] = float(changed["index"])
    commit.write_bytes(history.encoded(changed) + b"\n")
    sidecar.write_text(history.sha(commit.read_bytes()) + "\n")
    try:
        try:
            history.replay(
                archive,
                catalog,
                load_json(catalog / "runs" / run / "run.json")["selection_sha256"],
                run,
                True,
            )
        except ValueError as failure:
            assert str(failure) == "historical_metadata_integer"
        else:
            raise AssertionError("fractional committed index accepted")
    finally:
        commit.write_bytes(saved[0])
        sidecar.write_bytes(saved[1])
    # Exact output redelivery is retained as two physical origins and one logical result.
    duplicate_folder = folder / "duplicate-output"
    duplicate_folder.mkdir()
    duplicate = copy.deepcopy(units[:1])
    duplicate[0]["original_outputs"].append(copy.deepcopy(duplicate[0]["original_outputs"][0]))
    duplicate_archive, duplicate_request = archive_fixture(duplicate_folder, duplicate, plan)
    duplicate_catalog = duplicate_folder / "catalog"
    duplicate_hash = history.seal(duplicate_archive, duplicate_catalog, duplicate_request, plan)[
        "selection_sha256"
    ]
    duplicate_run = str(uuid.uuid4())
    history.replay(duplicate_archive, duplicate_catalog, duplicate_hash, duplicate_run)
    semantic_check(duplicate_catalog, duplicate, load_json(plan), duplicate_run)
    conflict_folder = folder / "conflicting-output"
    conflict_folder.mkdir()
    conflict = copy.deepcopy(duplicate)
    counts = conflict[0]["original_outputs"][-1]["value"]["counts"]
    counts["matched"] -= 1
    counts["unmatched"] += 1
    conflict_archive, conflict_request = archive_fixture(conflict_folder, conflict, plan)
    expect_helper_failure(
        lambda: history.seal(conflict_archive, conflict_folder / "catalog", conflict_request, plan),
        conflict_folder / "catalog",
        "conflicting_output",
    )
    # Missing referenced bytes fail during verified archive export, never as an evaluator fault.
    blob = next((folder / "evidence").iterdir()).name
    missing = archive / "objects" / blob
    held = folder / "held-object"
    missing.rename(held)
    try:
        expect_helper_failure(
            lambda: history.replay(archive, catalog, selected, str(uuid.uuid4())),
            catalog,
            "historical_missing_object",
        )
    finally:
        held.rename(missing)
    return dict(
        units=len(units),
        isolated_runs=2,
        helper_parent_kill_and_timeout=True,
        reference_ranges=2,
        seal_publication_faults=sealed_faults,
        exact_retry_and_conflicting_delivery=True,
        missing_referenced_object=True,
        process_faults=phases,
        selection_sha256=selected,
    )


def closure_edges(folder, plan):
    folder.mkdir(mode=0o700)
    units = original(folder, plan, edges=True)
    archive, request = archive_fixture(folder, units, plan)
    catalog = folder / "catalog"
    selected = history.seal(archive, catalog, request, plan)["selection_sha256"]
    run = str(uuid.uuid4())
    history.replay(archive, catalog, selected, run)
    semantic_check(catalog, units, load_json(plan), run)
    return dict(closures=["dataset_end", "resource_limit"], selection_sha256=selected)


def kafka(folder, plan):
    """Actual P13 source -> Flink -> Kafka -> durable P14a archive -> historical JVMs."""
    from archive import TOPICS, Archive
    from archive import build as archive_build
    from integration import Integration, runtime_binding
    from integration import build as integration_build
    from integration_verify import wait_outputs
    from stack import project_lock, save

    integration_build(plan)
    archive_build()
    project = "detectbridge-p13-history-" + uuid.uuid4().hex[:10]
    test = Integration(project)
    archive = Archive(project)
    units = load_json(folder / "original.json")
    with project_lock(project):
        try:
            test.init(objects=folder / "evidence")
            test.start()
            config = test.config()
            oracle = HistoricalOracle(
                config, runtime_binding(config), test.qualification_plan(), units
            )
            archive.command("init", "kafka:9092", probe=True)
            registry = folder / "registry"
            registry.mkdir()
            for p in (folder / "evidence").iterdir():
                (registry / p.name).write_bytes(p.read_bytes())
            provenance = history.encoded(
                dict(kind="synthetic", license="Apache-2.0", origin="P14b frozen source packet")
            )
            (registry / history.sha(provenance)).write_bytes(provenance)
            archive.init(registry, {t: 0 for t in TOPICS}, [history.sha(provenance)])
            input_refs = {}

            def send(unit):
                acks = test.inject_rows([history.encoded(r) for r in unit["inputs"]])
                oracle.register(unit["inputs"], acks)
                input_refs[unit["label"]] = [
                    dict(topic=history.INPUT, offset=a["offset"], value_sha256=a["value_sha256"])
                    for a in acks
                ]

            timed = next(u for u in units if u["label"] == "audit_timeout")
            send(timed)
            # Until other expected inputs exist, use a temporary timeout-only independent oracle.
            timeout_oracle = HistoricalOracle(
                config, runtime_binding(config), test.qualification_plan(), units
            )
            timeout_oracle.events = {
                k: v for k, v in timeout_oracle.events.items() if v["rows"] == timed["inputs"]
            }
            timeout_oracle.native.groups = {
                k: v
                for k, v in timeout_oracle.native.groups.items()
                if [m["record_id"] for m in v["members"]]
                == [r["raw"]["record_id"] for r in timed["inputs"]]
            }
            timeout_oracle.native.events = {
                k: v
                for k, v in timeout_oracle.native.events.items()
                if v["rows"] == timed["inputs"]
            }
            timeout_oracle.native.diagnostics = {}
            timeout_oracle.windows_expected = {}
            timeout_oracle.inputs = copy.deepcopy(oracle.inputs)
            wait_outputs(test, timeout_oracle)
            for unit in units:
                if unit is not timed:
                    send(unit)
            outputs = wait_outputs(test, oracle)
            test.stop()
            archive.command("drain", "/work/archive")
            selected = []
            manifest_refs = {}
            for kind, wire, doc in outputs:
                if kind == "manifest":
                    manifest_refs[doc["manifest_id"]] = dict(
                        topic=history.ROUTES[kind],
                        offset=wire["offset"],
                        value_sha256=history.sha(base64.b64decode(wire["value"])),
                    )
            for unit in units:
                expected = {
                    (o["kind"], o["value"][FIELDS[o["kind"]]]) for o in unit["original_outputs"]
                }
                refs = []
                for kind, wire, doc in outputs:
                    if (kind, doc[FIELDS[kind]]) in expected:
                        refs.append(
                            dict(
                                topic=history.ROUTES[kind],
                                offset=wire["offset"],
                                value_sha256=history.sha(base64.b64decode(wire["value"])),
                            )
                        )
                assert refs
                selected.append(
                    dict(
                        id=unit["label"],
                        kind=unit["kind"],
                        inputs=input_refs[unit["label"]],
                        outputs=refs,
                        anchor=manifest_refs[unit["anchor"]["manifest_id"]]
                        if unit["anchor"]
                        else None,
                        control=None,
                    )
                )
            request = dict(
                version="1.0.0",
                mode="historical",
                original_run_id=timed["inputs"][0]["context"]["run_id"],
                producer_sha256=history.PRODUCER,
                plan_sha256=history.sha(plan.read_bytes()),
                units=selected,
            )
            request_path = folder / "kafka-request.json"
            save(request_path, request)
            catalog = folder / "kafka-catalog"
            root = archive.folder / "archive"
            selection = history.seal(root, catalog, request_path, plan)["selection_sha256"]
            for _ in range(2):
                run = str(uuid.uuid4())
                history.replay(root, catalog, selection, run)
                semantic_check(catalog, units, load_json(plan), run)
            return dict(
                project=project,
                inputs=len(oracle.inputs),
                physical_outputs=len(outputs),
                selection_sha256=selection,
                isolated_runs=2,
                jar_sha256=history.PRODUCER,
            )
        except Exception:
            try:
                save(
                    folder / "failure-original-exceptions.json",
                    test.rest("/jobs/" + test.latest_job()["job_id"] + "/exceptions"),
                )
            except Exception as observation:
                save(
                    folder / "failure-observation-unavailable.json",
                    dict(failure_class=type(observation).__name__),
                )
            raise
        finally:
            if (test.stack.folder / "state.json").exists():
                test.stack.down()
                test.stack.compose("down", "--volumes", "--remove-orphans", profile="core")


def qualify():
    folder = history.ROOT / ".cache" / ("historical-qualification-" + uuid.uuid4().hex[:12])
    folder.mkdir(mode=0o700)
    plan = history.ROOT / ".cache/integration/plan.json"
    source_diff = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--", "."])
    (folder / "source.diff").write_bytes(source_diff)
    runtime = json.loads(
        subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                history.Stack().image("flink").split("@")[0].rsplit(":", 1)[0]
                + "@"
                + history.Stack().image("flink").split("@")[1],
            ]
        )
    )[0]
    report = dict(
        status="running",
        working_tree_diff_sha256=history.sha(source_diff),
        runtime=dict(
            image_id=runtime["Id"], os=runtime["Os"], architecture=runtime["Architecture"]
        ),
        source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        bundle=load_json(history.BUILDS / "bundle.json"),
        platform=sys.platform,
        qualification_probe_sha256=history.sha(
            (
                history.ROOT / "packages/historical-replay/build/libs/historical-probe.jar"
            ).read_bytes()
        ),
        tools_sha256={
            name: history.sha((history.ROOT / "tools" / name).read_bytes())
            for name in ["historical.py", "historical_fixtures.py", "historical_verify.py"]
        },
        folder=str(folder),
    )
    path = folder / "report.json"
    try:
        report["phase"] = "component"
        path.write_bytes(history.encoded(report) + b"\n")
        report["component"] = component(folder, plan)
        path.write_bytes(history.encoded(report) + b"\n")
        report["closure_edges"] = closure_edges(folder / "closure-edges", plan)
        report["phase"] = "source-to-archive"
        path.write_bytes(history.encoded(report) + b"\n")
        report["kafka"] = kafka(folder, plan)
        report["status"] = "qualified"
    except Exception as failure:
        report.update(status="failed", failure_class=type(failure).__name__)
        raise
    finally:
        path.write_bytes(history.encoded(report) + b"\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    qualify()
