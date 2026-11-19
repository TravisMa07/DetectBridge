"""Opt-in controlled-original P13 -> managed archive -> historical/current qualification.

All recordings, source expectations and helper diagnostics remain private and ignored.
Preflight is read-only except explicitly derived private qualification files. A
successful preflight is not runtime qualification; only the complete actual flow
can write status=qualified. No capture, replacement evidence or public upload occurs.
"""

import argparse
import ast
import base64
import copy
import gzip
import hashlib
import inspect
import json
import os
import subprocess
import sys
import traceback
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import archive_maintenance as maintenance
import current_replay
import historical as history
from archive import TOPICS
from check_archive import require as archive_require
from check_contracts import load_json
from current_replay_cases import ASSEMBLER, prepare_plan
from current_replay_verify import framed, image_identity, instant, results, snapshot
from integration import TOPICS as SOURCE_TOPICS
from integration import Integration, runtime_binding
from integration import build as integration_build
from integration_cases import prepare
from integration_oracle import FIELDS
from integration_verify import wait_outputs
from linux_assembly_audit_runtime import eligible_group
from linux_assembly_cases import digest, encoded, identity
from linux_assembly_verify import require
from search_writer_recorded import (
    AUDIT_CATALOG,
    WINDOWS_CATALOG,
    RecordedOracle,
    auth_fields,
    originals,
    remaining_admissions,
)
from stack import ROOT, StackError, project_lock, save

DEFAULTS = dict(
    windows=ROOT / ".cache/p11-windows-capture/attempt3/originals",
    audit=ROOT / ".cache/p12-audit-reviewed-v1",
    auth=ROOT / ".cache/p12-auth-reviewed-v1",
)
PACKET = ROOT / "contracts/archive-maintenance/v1/fixtures/expectations.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def controlled_late(row):
    late = copy.deepcopy(row)
    require(late["raw"]["cursor"]["kind"] == "dataset")
    raw = late["raw"]
    raw["cursor"]["position"] = 1000
    raw["record_id"] = identity(
        [
            raw["source"]["namespace"],
            raw["source"]["instance"],
            ["dataset", raw["cursor"]["artifact_sha256"], "1000"],
        ]
    )
    require(
        raw["evidence"] == row["raw"]["evidence"]
        and raw["first_observed"] == row["raw"]["first_observed"]
    )
    return late


def preflight(windows, audit, auth, folder):
    roots = {
        key: history.safe(value)
        for key, value in dict(windows=windows, audit=audit, auth=auth).items()
    }
    require(all(path.is_dir() for path in roots.values()))
    before = {key: snapshot(path) for key, path in roots.items()}
    catalogs, source = originals(
        roots["windows"], roots["audit"], roots["auth"], folder / "auth-inputs.ndjson"
    )
    packet = load_json(PACKET)
    for pin in packet["sources"]:
        require(sha((ROOT / pin["path"]).read_bytes()) == pin["sha256"])
    require(
        {key: len(value) for key, value in source.items()} == packet["recorded"]["source_records"]
    )
    require(sum(map(len, source.values())) == 46)
    for pin in packet["recorded"]["catalogs"]:
        require(digest(catalogs[pin["kind"]]) == pin["sha256"])
    require(len(catalogs["audit"]["groups"]) == 10)
    require(sum(bool(g["findings"]) for g in catalogs["audit"]["groups"]) == 9)
    # Correction 786ec14 precedes new runtime output: source catalogs count thirteen
    # original preservations; the explicit controlled late occurrence adds a fourteenth.
    categories = {
        "audit": Counter(item["disposition"] for item in catalogs["audit"]["records"]),
        "auth": Counter(item["disposition"] for item in catalogs["auth"]["expectations"]),
        "windows": Counter(
            item["expected"]["disposition"] for item in catalogs["windows"]["records"]
        ),
    }
    require(
        categories
        == {
            "audit": dict(group_member=27, extraction_failed=3),
            "auth": dict(normalized=2, unsupported_source=9),
            "windows": dict(eligible=4, unsupported_source=1),
        }
    )
    original_preservations = (
        categories["audit"]["extraction_failed"]
        + categories["auth"]["unsupported_source"]
        + categories["windows"]["unsupported_source"]
    )
    total_preservations = (
        original_preservations + packet["recorded"]["admissions"]["controlled_late_cursor"]
    )
    current_counts = packet["recorded"]["current"]
    require(original_preservations == 13 and total_preservations == 14)
    require(packet["recorded"]["historical"]["preservation"] == total_preservations)
    require(
        current_counts
        == dict(tagged=16, manifest=10, preservation=total_preservations, processing=9, detection=0)
    )
    require(sum(current_counts.values()) == 49)

    frozen_auth = {
        row["raw"]["record_id"]: auth_fields(row, expected)
        for row, expected in zip(source["auth"], catalogs["auth"]["expectations"], strict=True)
        if expected["disposition"] == "normalized"
    }
    require(
        len(frozen_auth) == 2
        and all(value["user"].casefold() != "bob" for value in frozen_auth.values())
    )
    require(catalogs["audit"]["execution"]["executable"] != "/usr/bin/whoami")
    run = str(uuid.uuid4())
    for batch in source.values():
        for row in batch:
            row["context"]["run_id"] = run
    selected = eligible_group(catalogs["audit"])
    execution = [source["audit"][i] for i in selected["member_positions"]]
    remainder = [
        row for i, row in enumerate(source["audit"]) if i not in selected["member_positions"]
    ]
    late = controlled_late(execution[-1])
    tail = remaining_admissions(source, remainder)
    admissions = [*execution, execution[0], late, *tail]
    require(len(admissions) == packet["recorded"]["admissions"]["total"] == 49)
    require(len({row["raw"]["record_id"] for batch in source.values() for row in batch}) == 46)
    require({key: snapshot(path) for key, path in roots.items()} == before)
    save(
        folder / "source-expectations.json",
        dict(
            catalogs=catalogs,
            roots={kind: str(path) for kind, path in roots.items()},
            frozen_auth=frozen_auth,
            source=source,
            eligible=selected,
            late=late,
            admissions=admissions,
            packet=packet["recorded"],
        ),
    )
    return dict(
        roots=roots,
        before=before,
        catalogs=catalogs,
        source=source,
        frozen_auth=frozen_auth,
        selected=selected,
        execution=execution,
        late=late,
        tail=tail,
        run=run,
        expected=packet["recorded"],
    )


def registry(folder, frozen):
    """Exact source evidence and original reviewed catalog bytes; no capture build blobs."""
    path = folder / "registry"
    path.mkdir(mode=0o700)

    def retain(body):
        require(0 < len(body) <= 32 * history.MIB)
        target = path / sha(body)
        if target.exists():
            require(target.read_bytes() == body)
        else:
            target.write_bytes(body)
        return target.name

    for batch in frozen["source"].values():
        for row in batch:
            evidence = row["raw"]["evidence"]
            # Accepted controlled originals currently use reviewed inline UTF-8 bytes.
            # A new reference layout needs explicit original-object resolution, not repair.
            require("inline" in evidence and "reference" not in evidence)
            body = evidence["inline"].encode("utf-8")
            require(sha(body) == evidence["sha256"])
            retain(body)
    from linux_assembly_recorded import recording_verifier

    catalog_paths = dict(
        windows=WINDOWS_CATALOG, audit=AUDIT_CATALOG, auth=recording_verifier().CATALOG
    )
    provenance = [retain(path.read_bytes()) for path in catalog_paths.values()]
    bindings: dict[str, dict[str, str]] = {}
    needed_objects = {
        row["raw"]["cursor"]["artifact_sha256"]
        for batch in frozen["source"].values()
        for row in batch
        if "artifact_sha256" in row["raw"]["cursor"]
    }
    metadata_names = {
        "capture-manifest.json",
        "capture.json",
        "copyrights.tar.gz",
        "licenses.tar.gz",
        "packages.txt",
    }
    for kind, root in frozen["roots"].items():
        bindings[kind] = {}
        for artifact in frozen["catalogs"][kind].get("artifacts", []):
            name = artifact.get("filename")
            if name not in metadata_names and artifact["sha256"] not in needed_objects:
                continue
            original = history.safe(root / name)
            require(original.is_file() and original.stat().st_size <= 32 * history.MIB)
            body = original.read_bytes()
            require(sha(body) == artifact["sha256"])
            bindings[kind][name] = retain(body)
    require(needed_objects <= {p.name for p in path.iterdir()})
    provenance.append(
        retain(
            history.encoded(
                dict(
                    version="1.0.0",
                    kind="derived-registration",
                    origin="accepted controlled originals; local-only terms remain authoritative",
                    reviewed_catalog_sha256={
                        kind: digest(value) for kind, value in frozen["catalogs"].items()
                    },
                    original_capture_objects=bindings,
                    source_counts=frozen["expected"]["source_records"],
                )
            )
            + b"\n"
        )
    )
    require(
        len(list(path.iterdir())) <= 128
        and sum(p.stat().st_size for p in path.iterdir()) <= 64 * history.MIB
    )
    return path, provenance


class CurrentRecordedOracle(RecordedOracle):
    def describe(self, key, scenario, **extra):
        super().describe(key, scenario, **extra)
        category = (
            "windows"
            if scenario.startswith("windows_")
            else "skipped_audit"
            if scenario == "audit_recorded_skipped"
            else "eligible_linux"
        )
        self.events[key].update(
            counts=load_json(PACKET)["recorded"]["current_counts"][category],
            match_ids=[],
            skipped_bits="0000000000000000000000001",
        )

    def check_source(self, event, expected):
        if "item" in expected:
            event = copy.deepcopy(event)
            time = event["detectbridge"]["time"]
            require(time.pop("received") == expected["rows"][0]["context"]["receipt"]["received"])
            require("processed" not in time)
        super().check_source(event, expected)


def oracle(
    frozen,
    plan,
    run,
    *,
    config=None,
    binding="private-offline-recorded",
    current=False,
    schedule=None,
    original_anchor=None,
):
    # P12 prepared() intentionally shares one context across its source rows.
    # Receipts belong to individual admissions: copying the whole collection would
    # preserve that alias and overwrite earlier steps with a later receipt clock.
    source = {kind: [copy.deepcopy(row) for row in rows] for kind, rows in frozen["source"].items()}
    late = copy.deepcopy(frozen["late"])
    times = schedule or {}
    for row in [*[r for batch in source.values() for r in batch], late]:
        row["context"]["run_id"] = run
        if current:
            row["context"]["receipt"] = dict(received=instant(times[row["raw"]["record_id"]]))
    cls = CurrentRecordedOracle if current else RecordedOracle
    check = cls(
        config or {},
        binding,
        plan,
        frozen["catalogs"],
        frozen["roots"]["windows"],
        frozen["frozen_auth"],
    )
    selected = frozen["selected"]
    grouped = check.audit_group(
        [source["audit"][i] for i in selected["member_positions"]], selected, "timeout"
    )
    check.preservation(late, "late_evidence", original_anchor or grouped)
    check.audit_remainder(source["audit"])
    check.windows_rows(source["windows"])
    check.auth_rows(source["auth"])
    return check, grouped


def independent_archive(archive, expected):
    """Independently decode actual managed compressed segments and physical wire bytes."""
    configuration = history.verified(archive / "archive.json")
    seen = {}
    for topic in configuration["topics"]:
        parent = archive / "segments" / topic["id"] / "0"
        previous, cursor = None, topic["start"]
        for directory in (
            sorted(parent.iterdir(), key=lambda p: int(p.name)) if parent.exists() else []
        ):
            metadata = history.verified(directory / "segment.json")
            archive_require("segment", metadata)
            require(metadata["first"] == cursor and metadata["previous"] == previous)
            compressed = (directory / "records.ndjson.gz").read_bytes()
            raw = gzip.decompress(compressed)
            payload = metadata["payload"]
            require(
                sha(compressed) == payload["compressed_sha256"]
                and len(compressed) == payload["compressed_bytes"]
            )
            require(
                sha(raw) == payload["uncompressed_sha256"]
                and len(raw) == payload["uncompressed_bytes"]
            )
            rows = [json.loads(line) for line in raw.splitlines()]
            require(len(rows) == payload["rows"])
            for row in rows:
                archive_require("wire", row)
                location = row["topic"], row["offset"]
                require(location not in seen and location in expected)
                wire = expected[location]
                require(all(row[key] == wire[key] for key in ("key", "value")))
                require(
                    row["headers"]
                    == [
                        dict(name=name, value=base64.b64encode(value.encode()).decode())
                        for name, value in wire["headers"].items()
                    ]
                )
                require(row["timestamp"] >= 0)
                require(
                    row["id"]
                    == "sha256:"
                    + sha(
                        history.encoded(
                            [
                                "detectbridge.archive.wire/1",
                                configuration["cluster"],
                                topic["id"],
                                "0",
                                str(row["offset"]),
                            ]
                        )
                    )
                )
                seen[location] = row
            cursor, previous = metadata["next"], sha(history.encoded(metadata))
        require(cursor == sum(key[0] == topic["name"] for key in expected))
    require(set(seen) == set(expected))
    return seen


def historical_request(frozen, check, outputs, input_refs, plan):
    logical: dict[tuple[str, str], tuple[dict, dict]] = {}
    for kind, wire, document in outputs:
        if kind not in history.ROUTES:
            continue
        key = kind, document[FIELDS[kind]]
        if key in logical:
            require(logical[key][1] == document)
        else:
            logical[key] = wire, document
    selected, assigned = [], set()
    manifests = {
        document["event_id"]: (wire, document)
        for (kind, _), (wire, document) in logical.items()
        if kind == "manifest"
    }
    original_anchor = None

    def unit(label, kind, rows, event=None, anchor=None):
        refs = []
        record_ids = {row["raw"]["record_id"] for row in rows}
        for key, (wire, document) in logical.items():
            output_kind = key[0]
            belongs = (
                document.get("event", {}).get("event", {}).get("id") == event
                if output_kind == "tagged"
                else document.get("event_id") == event
                if output_kind in {"manifest", "detection", "processing"}
                else document["diagnostic"].get(
                    "record_id", document["diagnostic"].get("member", {}).get("record_id")
                )
                in record_ids
                if output_kind == "preservation"
                else False
            )
            if belongs:
                require(key not in assigned)
                assigned.add(key)
                refs.append(
                    dict(
                        topic=history.ROUTES[output_kind],
                        offset=wire["offset"],
                        value_sha256=sha(base64.b64decode(wire["value"])),
                    )
                )
        require(bool(refs))
        selected.append(
            dict(
                id=label,
                kind=kind,
                inputs=[input_refs[row["raw"]["record_id"]] for row in rows],
                outputs=refs,
                control=None,
                anchor=anchor,
            )
        )

    for number, group in enumerate(frozen["catalogs"]["audit"]["groups"]):
        rows = [frozen["source"]["audit"][i] for i in group["member_positions"]]
        expected = next(
            value["manifest"]
            for value in check.events.values()
            if value.get("group", {}).get("audit_serial") == group["audit_serial"]
        )
        event = expected["event_id"]
        wire, manifest = manifests[event]
        unit("audit_" + str(number), "audit", rows, event)
        if not group["findings"]:
            original_anchor = manifest
            anchor = dict(
                topic=history.ROUTES["manifest"],
                offset=wire["offset"],
                value_sha256=sha(base64.b64decode(wire["value"])),
            )
    require(original_anchor is not None)
    unit("controlled_late", "audit_preservation", [frozen["late"]], anchor=anchor)
    for number, (row, expected) in enumerate(
        zip(frozen["source"]["audit"], frozen["catalogs"]["audit"]["records"], strict=True)
    ):
        if expected["disposition"] != "group_member":
            unit("audit_preservation_" + str(number), "audit_preservation", [row])
    for family, kind in (("windows", "windows"), ("auth", "authentication")):
        for number, row in enumerate(frozen["source"][family]):
            record_id = row["raw"]["record_id"]
            event = next(
                (
                    key[1]
                    for key, value in check.events.items()
                    if len(value["rows"]) == 1 and value["rows"][0]["raw"]["record_id"] == record_id
                ),
                None,
            )
            unit(family + "_" + str(number), kind, [row], event)
    require(assigned == set(logical))
    request = dict(
        version="1.0.0",
        mode="historical",
        original_run_id=frozen["run"],
        producer_sha256=history.PRODUCER,
        plan_sha256=sha(plan.read_bytes()),
        units=selected,
    )
    history.references(request)
    return request, original_anchor


def replay_entries(root, run):
    return [
        entry
        for path in sorted((root / "runs" / run / "units").glob("*/result.json"))
        for entry in load_json(path)["outputs"]
    ]


def counts(entries):
    return {kind: sum(entry["kind"] == kind for entry in entries) for kind in history.ROUTES}


def interrupted(client, selection, run, operation, folder):
    code = """import os,sys
sys.path.insert(0,'tools')
import archive_maintenance as m
import historical as h
armed=False
def hook(phase):
 global armed
 if phase=='during_payload':armed=True
 if armed and phase=='after_publication':os._exit(77)
h.HOOK=hook
client=m.ManagedArchive(*sys.argv[1:4])
with client.session(sys.argv[4]) as session:session.historical(sys.argv[5],sys.argv[6])
"""
    with (folder / "interruption-private.log").open("wb") as log:
        outcome = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                str(client.archive),
                str(client.catalog),
                str(client.control),
                operation,
                selection,
                run,
            ],
            cwd=ROOT,
            stdout=log,
            stderr=log,
        )
    require(outcome.returncode == 77)
    prefix = snapshot(client.catalog / "runs" / run / "units")
    require(bool(prefix))
    with client.session(operation) as session:
        session.historical(selection, run, True)
    after = snapshot(client.catalog / "runs" / run / "units")
    require(all(after.get(key) == value for key, value in prefix.items()))
    return len(prefix) // 3


def retained_subject(folder, source_roots=None):
    folder = history.safe(folder)
    saved = load_json(folder / "source-expectations.json")
    frozen = dict(
        source=saved["source"],
        late=saved["late"],
        catalogs=saved["catalogs"],
        selected=saved["eligible"],
        frozen_auth=saved["frozen_auth"],
        roots={
            kind: history.safe(path)
            for kind, path in saved.get("roots", source_roots or DEFAULTS).items()
        },
    )
    spec = load_json(folder / "current-request.json")
    identities = {}
    for segment in (folder / "archive/segments").glob("*/0/*/records.ndjson.gz"):
        for line in gzip.decompress(segment.read_bytes()).splitlines():
            wire = json.loads(line)
            if wire["topic"] == history.INPUT:
                row = json.loads(base64.b64decode(wire["value"]))
                if "raw" in row:
                    identities[(wire["topic"], wire["offset"])] = row["raw"]["record_id"]
    times = {
        identities[(step["input"]["topic"], step["input"]["offset"])]: step["at_ms"]
        for step in spec["schedule"]
        if step["action"] == "input"
    }
    runs = list((folder / "current-workspace/runs").iterdir())
    require(len(runs) == 1)
    return frozen, load_json(folder / "current-plan.json"), runs[0].name, spec, times


def alias_regression(frozen, plan, run, times):
    # Reproduce the accepted P12 helper's deliberate source alias without changing originals.
    shared = copy.deepcopy(frozen)
    context = shared["source"]["audit"][0]["context"]
    for row in shared["source"]["audit"]:
        row["context"] = context
    old_collection = copy.deepcopy(shared["source"])
    for row in old_collection["audit"]:
        row["context"]["receipt"] = dict(received=instant(times[row["raw"]["record_id"]]))
    require(
        any(
            row["context"]["receipt"]["received"] != instant(times[row["raw"]["record_id"]])
            for row in old_collection["audit"]
        )
    )
    expected, _ = oracle(shared, plan, run, current=True, schedule=times)
    for value in expected.events.values():
        for row in value["rows"]:
            require(
                row["context"]["receipt"] == dict(received=instant(times[row["raw"]["record_id"]]))
            )
    return dict(
        source_alias_reproduced=True,
        old_collection_copy_overwrites_earlier_clock=True,
        per_admission_copy_preserves_all_explicit_clocks=True,
        fixed_oracle_function_sha256=sha(inspect.getsource(oracle).encode()),
    )


def original_object(archive, digest):
    directory = archive / "objects" / digest
    metadata = history.verified(directory / "object.json")
    compressed = (directory / "bytes.ndjson.gz").read_bytes()
    raw = gzip.decompress(compressed)
    require(sha(compressed) == metadata["payload"]["compressed_sha256"])
    require(sha(raw) == metadata["payload"]["uncompressed_sha256"])
    output = bytearray()
    for line in raw.splitlines():
        chunk = json.loads(line)
        require(chunk["offset"] == len(output))
        output.extend(base64.b64decode(chunk["bytes"], validate=True))
    require(len(output) == metadata["length"] and sha(output) == digest)
    return bytes(output)


def verify_original_range(body, span):
    start, length = span["offset"], span["length"]
    if (
        type(start) is not int
        or type(length) is not int
        or start < 0
        or length <= 0
        or start + length > len(body)
        or sha(body[start : start + length]) != span["sha256"]
    ):
        raise ValueError("recorded_original_range_integrity")


def detached_negative_checks(folder, source_roots=None):
    """Separate checker evidence over copies of real output; never rewrites an old failed run."""
    folder = history.safe(folder)
    frozen, plan, run, spec, times = retained_subject(folder, source_roots)
    protected = {
        name: snapshot(folder / name) for name in ("archive", "catalog", "current-workspace")
    }
    originals_before = {kind: snapshot(path) for kind, path in frozen["roots"].items()}
    entries = replay_entries(folder / "current-workspace", run)
    expected, _ = oracle(frozen, plan, run, current=True, schedule=times)
    require(expected.check(framed(entries, expected.binding)))
    require(counts(entries) == load_json(PACKET)["recorded"]["current"] and len(entries) == 49)
    regression = alias_regression(frozen, plan, run, times)
    cases = []
    for case in ("field", "host", "context", "membership", "counts", "match", "attribution"):
        altered = copy.deepcopy(entries)
        tag = next(
            entry["value"]
            for entry in altered
            if entry["kind"] == "tagged"
            and entry["value"]["event"]["detectbridge"]["quality"]["eligibility"] == "eligible"
            and "audit_records" in entry["value"]["event"]["source_fields"]
        )
        if case == "field":
            tag["event"]["process"]["pid"] += 1
        elif case == "host":
            tag["event"]["host"]["id"] += "-detached"
        elif case == "context":
            tag["event"]["detectbridge"]["extensions"]["linux.context"]["context"]["host_binding"][
                "host_id"
            ] += "-detached"
        elif case == "membership":
            manifest = next(
                entry["value"]
                for entry in altered
                if entry["kind"] == "manifest"
                and entry["value"]["event_id"] == tag["event"]["event"]["id"]
            )
            manifest["members"][0], manifest["members"][1] = (
                manifest["members"][1],
                manifest["members"][0],
            )
        elif case == "counts":
            tag["counts"]["matched"] += 1
            tag["counts"]["unmatched"] -= 1
        elif case == "match":
            tag["matches"] = [
                dict(
                    id=plan["rules"][0]["id"],
                    revision=plan["rules"][0]["revision"],
                    detection_id="sha256:" + "0" * 64,
                )
            ]
        else:
            tag["attribution"]["context_sha256"] = "0" * 64
        require(len(altered) == len(entries))
        fresh, _ = oracle(frozen, plan, run, current=True, schedule=times)
        try:
            accepted = fresh.check(framed(altered, fresh.binding))
        except StackError as error:
            require(str(error) == "assembly_independent_expectation_failed")
            category = str(error)
        else:
            require(not accepted)
            category = "independent_oracle_false"
        cases.append(dict(case=case, rejected=True, category=category))
    # Original audit range expectations come from the reviewed whole source artifact,
    # independently of archive frames, JVM output or newly reconstructed projections.
    digest = frozen["source"]["audit"][0]["raw"]["cursor"]["artifact_sha256"]
    artifact = next(
        item for item in frozen["catalogs"]["audit"]["artifacts"] if item["sha256"] == digest
    )
    approved = (frozen["roots"]["audit"] / artifact["filename"]).read_bytes()
    require(sha(approved) == digest)
    archived = original_object(folder / "archive", digest)
    offset, spans = 0, []
    for position, line in enumerate(approved.splitlines(keepends=True)):
        span = dict(
            offset=offset,
            length=len(line),
            sha256=frozen["catalogs"]["audit"]["records"][position]["sha256"],
        )
        verify_original_range(archived, span)
        spans.append(span)
        offset += len(line)
    require(offset == len(approved) and len(spans) == 30)
    altered_span = copy.deepcopy(spans[0])
    altered_span["offset"] += 1
    try:
        verify_original_range(archived, altered_span)
    except ValueError as error:
        require(str(error) == "recorded_original_range_integrity")
    else:
        raise RuntimeError("recorded_range_mutation_accepted")
    cases.append(
        dict(case="original-range", rejected=True, category="recorded_original_range_integrity")
    )
    changed_bytes = bytes([archived[0] ^ 1]) + archived[1:]
    try:
        verify_original_range(changed_bytes, spans[0])
    except ValueError as error:
        require(str(error) == "recorded_original_range_integrity")
    else:
        raise RuntimeError("recorded_byte_mutation_accepted")
    cases.append(
        dict(case="original-bytes", rejected=True, category="recorded_original_range_integrity")
    )
    require(protected == {name: snapshot(folder / name) for name in protected})
    require(originals_before == {kind: snapshot(path) for kind, path in frozen["roots"].items()})
    positive = load_json(folder / "report.json")
    output = dict(
        status="negative-checkers-qualified",
        full_pipeline_requalification=False,
        positive_run_status=positive["status"],
        positive_verifier_sha256=positive["qualification_source_sha256"],
        checker_sha256=sha(Path(__file__).read_bytes()),
        expectation_sha256=sha(PACKET.read_bytes()),
        subject_current_run=run,
        actual_outputs=49,
        alias_regression=regression,
        cases=cases,
        original_ranges_verified=30,
        originals_archive_catalog_workspace_unchanged=True,
        checker_sources={
            name: sha((ROOT / "tools" / name).read_bytes())
            for name in (
                "archive_recorded.py",
                "search_writer_recorded.py",
                "integration_oracle.py",
                "linux_assembly_verify.py",
                "linux_assembly_audit_recording.py",
            )
        },
    )
    failed_source = folder / "failed-verifier-source.py"
    if failed_source.exists():
        text = failed_source.read_text()
        node = next(
            node
            for node in ast.parse(text).body
            if isinstance(node, ast.FunctionDef) and node.name == "oracle"
        )
        segment = ast.get_source_segment(text, node)
        assert isinstance(segment, str)
        output["failed_oracle_function_sha256"] = sha(segment.encode())
    save(folder / "detached-checker-report.json", output)
    return output


def provision_archive_topic(pipeline, folder):
    """Admin creates only the missing ninth topic, before any original admission."""
    before = pipeline.broker()
    require(set(before["end_offsets"]) == set(SOURCE_TOPICS))
    require(all(offset == 0 for offset in before["end_offsets"].values()))
    bundle = history.document(maintenance.BUILDS / "bundle.json")
    managed, probe = [maintenance.BUILDS / bundle[key] for key in ("managed", "probe")]
    require(maintenance.verify_managed(managed) == bundle["managed"])
    require(sha(probe.read_bytes()) == bundle["probe"])
    text = pipeline.stack.helper(
        "flink",
        "java -Xmx320m -cp /managed.jar:/probe.jar io.detectbridge.archive.ManagedProbe kafka init kafka:9092",
        mounts=[
            f"type=bind,source={maintenance.safe(path)},target={target},readonly"
            for path, target in ((managed, "/managed.jar"), (probe, "/probe.jar"))
        ],
        user=f"{os.getuid()}:{os.getgid()}",
        network=pipeline.project + "_internal",
        timeout=90,
    )
    response = json.loads(text)
    require(response["status"] == "ok" and response["result"]["created"] == 1)
    after = pipeline.broker()
    require(after["end_offsets"] == before["end_offsets"])
    pipeline.verify_destination(pipeline.config())
    save(
        folder / "topic-provision.json",
        dict(before=before, after=after, probe=response, probe_sha256=bundle["probe"]),
    )
    return dict(
        created=1,
        existing_topics=len(SOURCE_TOPICS),
        existing_offsets_unchanged=True,
        probe_sha256=bundle["probe"],
    )


def retain_source_failure(pipeline, folder):
    # Original Python traceback and actual P13 exception report stay private, before cleanup.
    (folder / "failure-private-traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    try:
        job = pipeline.latest_job()
        save(
            folder / "failure-source-job-exceptions.json",
            pipeline.rest("/jobs/" + job["job_id"] + "/exceptions"),
        )
    except Exception as observation:
        save(
            folder / "failure-source-observation-unavailable.json",
            dict(failure_class=type(observation).__name__),
        )


def qualify(windows, audit, auth, *, preflight_only=False, build_artifacts=True):
    project = "detectbridge-p13-archive-recorded-" + uuid.uuid4().hex[:10]
    folder = ROOT / ".cache/archive-recorded-reports" / project
    folder.mkdir(parents=True, mode=0o700)
    report = dict(status="running", project=project, phase="original-preflight", recorded=True)
    report_path = folder / "report.json"
    pipeline = None
    prepared_build = False

    def stage(name):
        report["phase"] = name
        save(report_path, report)
        print(json.dumps(dict(project=project, phase=name)), flush=True)

    try:
        frozen = preflight(windows, audit, auth, folder)
        report.update(
            source_counts=frozen["expected"]["source_records"],
            catalog_sha256={key: digest(value) for key, value in frozen["catalogs"].items()},
            qualification_source_sha256=sha(Path(__file__).read_bytes()),
            expectation_sha256=sha(PACKET.read_bytes()),
            source_revision=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            working_diff_sha256=sha(subprocess.check_output(["git", "diff", "HEAD"], cwd=ROOT)),
        )
        if preflight_only:
            report.update(status="preflight-verified", runtime_qualified=False)
            return report
        registry_path, provenance = registry(folder, frozen)
        stage("artifact-build")
        plan = ROOT / ".cache/integration/recorded-plan.json"
        prepared_build = True
        if build_artifacts:
            history.build()
            current_replay.build()
            maintenance.build()
            prepare(recorded=True)
            integration_build(plan)
            prepared_build = True
        require(plan.is_file())
        current_plan = folder / "current-plan.json"
        new_plan = prepare_plan(current_plan)
        require(
            [rule["id"] for rule in new_plan["rules"]]
            == ["72000000-0000-4000-8000-000000000001", "72000000-0000-4000-8000-000000000004"]
        )
        pipeline = Integration(project)
        with project_lock(project):
            try:
                stage("original-source-kafka")
                pipeline.init()
                configuration = pipeline.config()
                require(pipeline.qualification_plan() == load_json(plan))
                report["topic_setup"] = provision_archive_topic(pipeline, folder)
                pipeline.start()
                check = RecordedOracle(
                    configuration,
                    runtime_binding(configuration),
                    pipeline.qualification_plan(),
                    frozen["catalogs"],
                    frozen["roots"]["windows"],
                    frozen["frozen_auth"],
                )
                manifest = check.audit_group(frozen["execution"], frozen["selected"], "timeout")
                input_refs: dict[str, dict[str, Any]] = {}

                def send(rows):
                    acknowledgements = pipeline.inject_rows([encoded(row) for row in rows])
                    check.register(rows, acknowledgements)
                    for row, acknowledgement in zip(rows, acknowledgements, strict=True):
                        if "raw" in row:
                            ref = dict(
                                topic=history.INPUT,
                                offset=acknowledgement["offset"],
                                value_sha256=acknowledgement["value_sha256"],
                            )
                            input_refs.setdefault(row["raw"]["record_id"], ref)
                    return acknowledgements

                send(frozen["execution"])
                wait_outputs(pipeline, check)
                stage("original-timeout-and-controlled-late")
                check.preservation(frozen["late"], "late_evidence", manifest)
                redelivery = send([frozen["execution"][0], frozen["late"]])
                require(
                    redelivery[0]["value_sha256"]
                    == input_refs[frozen["execution"][0]["raw"]["record_id"]]["value_sha256"]
                )
                wait_outputs(pipeline, check)
                check.audit_remainder(frozen["source"]["audit"])
                check.windows_rows(frozen["source"]["windows"])
                check.auth_rows(frozen["source"]["auth"])
                send(frozen["tail"])
                output = wait_outputs(pipeline, check)
                require(len(check.inputs) == 49 and len(input_refs) == 47)
                pipeline.stop()
                output = pipeline.outputs()
                require(check.check(output))
                expected_wires = {}
                ends = pipeline.broker()["end_offsets"]
                require(set(ends) == set(SOURCE_TOPICS))
                for topic in SOURCE_TOPICS:
                    if not ends[topic]:
                        continue
                    response = pipeline.private_read(
                        pipeline.process_args("read", topic, "0", str(ends[topic])), timeout=90
                    )
                    for line in response.stdout.splitlines():
                        wire = json.loads(line)
                        if "value" in wire:
                            expected_wires[(topic, wire["offset"])] = wire
                require(sum(topic == history.INPUT for topic, _ in expected_wires) == 49)
                stage("managed-kafka-durability")
                client = maintenance.initialize(
                    project,
                    folder / "archive",
                    folder / "catalog",
                    folder / "control",
                    registry_path,
                    {topic: 0 for topic in TOPICS},
                    provenance,
                    str(uuid.uuid4()),
                    str(uuid.uuid4()),
                )
                operation = str(uuid.uuid4())
                with client.session(operation, project=project) as session:
                    progress = session.command("drain", operation)
                archived = independent_archive(client.archive, expected_wires)
                require(len(archived) == len(expected_wires))
                protected = snapshot(client.archive)
                save(
                    folder / "protected-snapshots.json",
                    dict(archive=protected, originals=frozen["before"]),
                )
                stage("managed-historical-seal")
                request, original_anchor = historical_request(
                    frozen, check, output, input_refs, plan
                )
                request_path = folder / "historical-request.json"
                save(request_path, request)
                with client.session(str(uuid.uuid4())) as session:
                    selection = session.seal(request_path, plan)["selection_sha256"]
                stage("historical-isolation-and-interrupted-resume")
                historical_runs, historical_outputs = [], []
                retained = None
                for number in range(2):
                    run = str(uuid.uuid4())
                    operation = str(uuid.uuid4())
                    if number == 0:
                        retained = interrupted(client, selection, run, operation, folder)
                    else:
                        with client.session(operation) as session:
                            session.historical(selection, run)
                    expected, _ = oracle(
                        frozen, load_json(plan), run, original_anchor=original_anchor
                    )
                    entries = replay_entries(client.catalog, run)
                    require(expected.check(framed(entries, expected.binding)))
                    observed = counts(entries)
                    require(
                        all(
                            observed[kind] == value
                            for kind, value in frozen["expected"]["historical"].items()
                        )
                    )
                    before = snapshot(client.catalog / "runs" / run)
                    with client.session(str(uuid.uuid4())) as session:
                        session.historical(selection, run, True)
                    require(before == snapshot(client.catalog / "runs" / run))
                    historical_runs.append(run)
                    historical_outputs.append(entries)
                for kind in ("tagged", "detection"):
                    first = {
                        entry["value"][FIELDS[kind]]
                        for entry in historical_outputs[0]
                        if entry["kind"] == kind
                    }
                    second = {
                        entry["value"][FIELDS[kind]]
                        for entry in historical_outputs[1]
                        if entry["kind"] == kind
                    }
                    require(bool(first) and first.isdisjoint(second))
                stage("current-explicit-policy")
                selected_ids = {row["raw"]["record_id"] for row in frozen["execution"]}
                rows = [
                    *frozen["execution"],
                    frozen["late"],
                    *[row for row in frozen["tail"] if "raw" in row],
                ]
                schedule = [
                    dict(at_ms=0, action="input", input=input_refs[row["raw"]["record_id"]])
                    for row in frozen["execution"]
                ]
                schedule.append(dict(at_ms=30000, action="tick", input=None))
                schedule.append(
                    dict(
                        at_ms=30001,
                        action="input",
                        input=input_refs[frozen["late"]["raw"]["record_id"]],
                    )
                )
                schedule.extend(
                    dict(at_ms=30002, action="input", input=input_refs[row["raw"]["record_id"]])
                    for row in rows
                    if row["raw"]["record_id"] not in selected_ids and row is not frozen["late"]
                )
                schedule.append(dict(at_ms=30003, action="end", input=None))
                times = {
                    row["raw"]["record_id"]: 0
                    if row["raw"]["record_id"] in selected_ids
                    else 30001
                    if row is frozen["late"]
                    else 30002
                    for row in rows
                }
                spec = dict(
                    version="1.0.0",
                    mode="current",
                    selection_sha256=selection,
                    plan_sha256=sha(current_plan.read_bytes()),
                    engine_profile="p13-runtime-51a984de/1.0.0",
                    source_policy="preserve-original-context/1.0.0",
                    schedule_policy="explicit-offline-clock/1.0.0",
                    enrichment=[],
                    assembler_limits=ASSEMBLER,
                    schedule=schedule,
                )
                spec_path = folder / "current-request.json"
                save(spec_path, spec)
                run = str(uuid.uuid4())
                workspace = folder / "current-workspace"
                historical_before = snapshot(client.catalog)
                with client.session(str(uuid.uuid4())) as session:
                    session.current(workspace, spec_path, current_plan, run)
                expected, _ = oracle(frozen, new_plan, run, current=True, schedule=times)
                entries = replay_entries(workspace, run)
                require(expected.check(framed(entries, expected.binding)))
                require(counts(entries) == frozen["expected"]["current"] and len(entries) == 49)
                transitions = results(workspace, run)
                require(len(transitions) == len(schedule))
                final = transitions[-1]["state"]
                require(
                    final["assembler"]["runs"][run] == "ended"
                    and not final["assembler"]["groups"]
                    and not final["inbox"]
                    and not final["outbox"]
                )
                require(
                    snapshot(client.catalog) == historical_before
                    and snapshot(client.archive) == protected
                )
                require(
                    {key: snapshot(path) for key, path in frozen["roots"].items()}
                    == frozen["before"]
                )
                stage("detached-negative-checkers")
                negative = detached_negative_checks(folder)
                report.update(
                    detached_negative_report_sha256=sha(
                        (folder / "detached-checker-report.json").read_bytes()
                    ),
                    rejected_mutations=[case["case"] for case in negative["cases"]],
                    status="qualified",
                    runtime_qualified=True,
                    phase="complete",
                    admissions=49,
                    original_occurrences=46,
                    controlled_late=1,
                    exact_redeliveries=1,
                    source_run=frozen["run"],
                    historical_runs=historical_runs,
                    historical_kind_counts=[counts(rows) for rows in historical_outputs],
                    interrupted_committed_units=retained,
                    current_run=run,
                    current_kind_counts=counts(entries),
                    selection_sha256=selection,
                    physical_archive_wires=len(archived),
                    progress=progress,
                    integration_bundle=configuration["bundle"],
                    managed_sha256=maintenance.digest(client.reader),
                    managed_bundle=history.document(maintenance.BUILDS / "bundle.json"),
                    original_plan_sha256=sha(plan.read_bytes()),
                    current_plan_sha256=sha(current_plan.read_bytes()),
                    image=image_identity(load_json(PACKET)["legacy_artifacts"]["image"]),
                    limits=[
                        "private local controlled originals only",
                        "native private AMD64 unavailable",
                        "no new malformed/error-budget/throughput/disk-loss claim",
                    ],
                )
                return report
            except Exception:
                retain_source_failure(pipeline, folder)
                raise
            finally:
                if pipeline is not None and (pipeline.stack.folder / "state.json").exists():
                    try:
                        pipeline.stack.down()
                        pipeline.stack.compose(
                            "down", "--volumes", "--remove-orphans", profile="core"
                        )
                        report["owned_runtime_cleanup"] = "complete"
                    except Exception:
                        report["phase"] = "owned-runtime-cleanup"
                        raise
    except Exception as error:
        report.update(
            status="unavailable" if report["phase"] == "original-preflight" else "failed",
            runtime_qualified=False,
            failure_class=type(error).__name__,
        )
        raise
    finally:
        try:
            if prepared_build:
                try:
                    prepare()
                    integration_build()
                    report["default_build_restored"] = True
                except Exception as error:
                    report.update(
                        status="failed",
                        runtime_qualified=False,
                        phase="default-build-restore"
                        if report["status"] == "qualified"
                        else report["phase"],
                        default_build_restored=False,
                        restore_failure_class=type(error).__name__,
                    )
                    raise
        finally:
            save(report_path, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorded", action="store_true", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--prepared-artifacts", action="store_true")
    parser.add_argument("--check-retained", type=Path)
    for kind, path in DEFAULTS.items():
        parser.add_argument("--" + kind, type=Path, default=path)
    args = parser.parse_args()
    try:
        if args.check_retained is not None:
            print(
                json.dumps(
                    detached_negative_checks(
                        args.check_retained,
                        source_roots={kind: getattr(args, kind) for kind in DEFAULTS},
                    ),
                    sort_keys=True,
                )
            )
            return
        report = qualify(
            args.windows,
            args.audit,
            args.auth,
            preflight_only=args.preflight_only,
            build_artifacts=not args.prepared_artifacts,
        )
        print(json.dumps(report, sort_keys=True))
    except Exception as error:
        print(
            json.dumps(
                dict(status="blocked", runtime_qualified=False, failure_class=type(error).__name__)
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
