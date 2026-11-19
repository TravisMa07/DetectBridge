"""Actual managed-backend corruption and completed-P05 retirement qualification.

Every corrupt archive is a fresh clone of the frozen synthetic packet. This module
never imports the verifier and never opens controlled-original evidence.
"""

import hashlib
import json
import shutil
import uuid

import historical as history
from archive_maintenance import ManagedArchive
from check_contracts import load_json
from stack import StackError

# Store.bounded explicitly rejects a missing regular file; its NIO operations can
# also raise NoSuchFileException. Both precise outcomes occurred against the same
# deliberately removed head in retained attempts 8/9. No cache cause is inferred.
MISSING_HEAD_FAILURES = frozenset(
    {
        ("managed_operation_failed", "java.nio.file.NoSuchFileException"),
        ("unsafe_or_oversized_file", "io.detectbridge.archive.Format$Failure"),
    }
)


# A missing retained segment is rejected either by the exact directory-content
# guard on the selected path or by the subsequent chain-completeness guard.
RETAINED_GAP_FAILURES = frozenset(
    {
        ("archive_contents", "io.detectbridge.archive.Format$Failure"),
        ("segment_chain_gap", "io.detectbridge.archive.Format$Failure"),
    }
)


def hashes(root):
    assert root.is_dir(), "required qualification source is missing"
    result = {}
    for path in sorted(root.rglob("*")):
        assert not path.is_symlink(), "unexpected qualification symlink"
        name = str(path.relative_to(root))
        if path.is_dir():
            result[name + "/"] = "directory"
        elif path.name != ".lock":
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def write_metadata(path, value):
    data = history.encoded(value) + b"\n"
    path.write_bytes(data)
    path.with_suffix(".sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")


def mutate(archive, fault, frozen):
    """Apply exactly one declared fault before taking the no-further-mutation snapshot."""
    first_object = frozen["legacy"]["objects"][0]["metadata"]["sha256"]
    object_dir = archive / "objects" / first_object
    segment = archive / "segments/topic-0/0/0"
    retirement = archive / "maintenance/retirements"
    if fault == "missing_global_object":
        shutil.rmtree(object_dir)
    elif fault == "wrong_global_object":
        metadata = load_json(object_dir / "object.json")
        metadata["sha256"] = "0" * 64
        write_metadata(object_dir / "object.json", metadata)
    elif fault == "truncated_segment":
        path = segment / "records.ndjson.gz"
        path.write_bytes(path.read_bytes()[:-1])
    elif fault == "corrupt_segment_gzip_footer":
        path = segment / "records.ndjson.gz"
        body = bytearray(path.read_bytes())
        body[-8] ^= 1
        path.write_bytes(body)
        metadata = load_json(segment / "segment.json")
        metadata["payload"]["compressed_sha256"] = hashlib.sha256(body).hexdigest()
        write_metadata(segment / "segment.json", metadata)
    elif fault == "missing_hold_head":
        (archive / "maintenance/holds/head.json").unlink()
    elif fault == "missing_retirement_head":
        (retirement / "head.json").unlink()
    elif fault == "corrupt_retirement_record":
        path = retirement / "00000000000000000001/retirement.json"
        body = bytearray(path.read_bytes())
        body[-2] ^= 1
        path.write_bytes(body)
    elif fault == "retirement_head_ahead":
        path = retirement / "head.json"
        head = load_json(path)
        head["sequence"], head["record_sha256"] = 1, "a" * 64
        del head["checksum_sha256"]
        head["checksum_sha256"] = history.sha(history.encoded(head))
        path.write_bytes(history.encoded(head) + b"\n")
    elif fault == "retained_segment_gap":
        shutil.rmtree(archive / "segments/topic-0/0/2")
    elif fault == "retirement_journal_gap":
        # Two genuine records exist. Removing their required predecessor must not
        # turn the surviving second record into a fresh, apparently empty history.
        shutil.rmtree(retirement / "00000000000000000001")
    else:
        raise AssertionError("unknown managed corruption case")


def declared_removal(before, after, name):
    assert name in before and name not in after, "required missing-head fault absent"
    assert {path: value for path, value in before.items() if path != name} == after, (
        "missing-head case changed another file or directory"
    )


def declared_subtree_removal(before, after, name):
    prefix = name.rstrip("/") + "/"
    assert before.get(prefix) == "directory", "required segment subtree absent before fault"
    removed = {path for path in before if path.startswith(prefix)}
    assert removed and all(path not in after for path in removed), (
        "segment subtree fault incomplete"
    )
    assert {path: value for path, value in before.items() if path not in removed} == after, (
        "segment-gap case changed another file or directory"
    )


def retirement_seed_steps(frozen, count):
    # Independent literal timestamps are 100 in the first two segments and 200
    # in the third. These are valid setup transactions, not negative-case waivers.
    steps = ((4, 100), (6, 200))[:count]
    for next_offset, cutoff in steps:
        timestamps = [
            row["timestamp"]
            for segment in frozen["legacy"]["segments"]
            if segment["metadata"]["next"] <= next_offset
            for row in segment["rows"]
        ]
        assert timestamps and max(timestamps) == cutoff
        assert all(type(value) is int and 0 <= value <= cutoff for value in timestamps)
    return steps


def qualify_faults(RuntimeFactory, base_folder, bundle, frozen, cases, stage):
    expectations = (
        ("missing_global_object", "missing_object", 0),
        ("wrong_global_object", "object_binding", 0),
        ("truncated_segment", "compressed_integrity", 0),
        ("corrupt_segment_gzip_footer", "gzip_footer", 0),
        ("missing_hold_head", "managed_operation_failed", 0),
        ("missing_retirement_head", "managed_operation_failed", 0),
        ("corrupt_retirement_record", "managed_metadata_integrity", 1),
        ("retirement_head_ahead", "managed_retirement_head_missing", 0),
        ("retained_segment_gap", "segment_chain_gap", 0),
        ("retirement_journal_gap", "managed_retirement_head_missing", 2),
    )
    for fault, category, retirement_count in expectations:
        stage("actual_backend_negative_" + fault)
        runtime = RuntimeFactory(base_folder / fault, bundle)
        packet, source = runtime.folder / "frozen.json", runtime.folder / "legacy"
        packet.write_bytes(history.encoded(frozen) + b"\n")
        runtime.invoke("fixture", packet, source, role="probe")
        original = hashes(source)
        runtime.clone(source)
        for next_offset, cutoff in retirement_seed_steps(frozen, retirement_count):
            plan, catalog, operation = runtime.plan(next_offset, cutoff)
            runtime.invoke("retire", runtime.archive, plan, catalog, operation, operation=operation)
        # Establish actual backend validity immediately before the sole declared fault.
        runtime.invoke("inspect", runtime.archive)
        before = hashes(runtime.archive)
        mutate(runtime.archive, fault, frozen)
        faulted = hashes(runtime.archive)
        missing_head = {
            "missing_hold_head": "maintenance/holds/head.json",
            "missing_retirement_head": "maintenance/retirements/head.json",
        }.get(fault)
        failure_details = {}
        if missing_head is not None:
            declared_removal(before, faulted, missing_head)
            # Exact paired outcomes only, following successful backend preflight
            # and proof that no other path changed. Attempts 8/9 remain failed.
            failure_details["expected_pairs"] = MISSING_HEAD_FAILURES
        elif fault == "retained_segment_gap":
            declared_subtree_removal(before, faulted, "segments/topic-0/0/2")
            failure_details["expected_pairs"] = RETAINED_GAP_FAILURES
        runtime.invoke("inspect", runtime.archive, expected=category, **failure_details)
        assert hashes(runtime.archive) == faulted, "inspection changed a rejected archive"
        runtime.invoke(
            "recover", runtime.archive, str(uuid.uuid4()), expected=category, **failure_details
        )
        assert hashes(runtime.archive) == faulted, "recovery changed a rejected archive"
        assert hashes(source) == original, "frozen legacy source was changed"
        cases.append("actual_backend_rejects_" + fault + "_without_mutation")


def public_failure(session, invoke, category):
    failures = set(session.operation.folder.glob("failure-*.json"))
    try:
        invoke()
    except StackError:
        retained = set(session.operation.folder.glob("failure-*.json")) - failures
        assert len(retained) == 1, "required failure diagnostics missing"
        record = load_json(retained.pop())
        assert record["exit_code"] == 1
        assert json.loads(record["stdout"].splitlines()[-1])["category"] == category
    else:
        raise AssertionError("required managed failure did not occur")


def qualify_import_retirement(runtime, import_metadata, cases, stage):
    """Called only after the verifier created/restored a genuine completed P05 run."""
    identifier = import_metadata["id"]
    assert (
        import_metadata["record_count"],
        import_metadata["envelope_count"],
        import_metadata["segment_count"],
    ) == (4, 6, 1)
    directory = runtime.archive / "imports" / identifier
    assert history.verified(directory / "import.json") == import_metadata
    client = ManagedArchive(runtime.archive, runtime.catalog, runtime.control)
    original = hashes(runtime.folder / "legacy")
    p05_originals = {name: hashes(runtime.folder / name) for name in ("p05-runs", "p05-cache")}
    protected = {
        path: digest
        for path, digest in hashes(runtime.archive).items()
        if not path.startswith(
            ("maintenance/holds/", "maintenance/retirements/", "imports/" + identifier + "/")
        )
    }
    stage("actual_completed_p05_import_hold_blocks_public_retirement")
    current = max(
        (path for path in (runtime.archive / "maintenance/holds").iterdir() if path.name.isdigit()),
        key=lambda path: int(path.name),
    )
    holds = history.verified(current / "holds.json")
    next_hold = dict(
        holds,
        revision=holds["revision"] + 1,
        previous_sha256=history.sha(history.encoded(holds)),
        reason="synthetic completed P05 import retention hold",
        holds=[
            *holds["holds"],
            dict(
                id=str(uuid.uuid4()),
                scope="import",
                topic=None,
                first=None,
                next=None,
                subject=identifier,
            ),
        ],
    )
    with client.session(str(uuid.uuid4())) as session:
        path = session.file("import-hold.json", next_hold)
        session.command("holds", path, session.operation.id)
    operation = str(uuid.uuid4())
    request = dict(
        operation_id=operation,
        cutoff_ms=0,
        imports=[identifier],
        reason="explicit whole completed P05 import retirement; no Kafka age assertion",
    )
    before = hashes(runtime.archive)
    with client.session(operation) as session:
        public_failure(session, lambda: session.plan_import(request), "managed_hold_blocker")
    assert hashes(runtime.archive) == before
    released = dict(
        next_hold,
        revision=next_hold["revision"] + 1,
        previous_sha256=history.sha(history.encoded(next_hold)),
        holds=holds["holds"],
    )
    with client.session(str(uuid.uuid4())) as session:
        path = session.file("release-import-hold.json", released)
        session.command("holds", path, session.operation.id)
    cases.append("actual_completed_p05_import_hold_blocks_public_plan")
    stage("actual_completed_p05_import_retirement_publication_crash_and_same_operation_retry")
    operation = str(uuid.uuid4())
    request["operation_id"] = operation
    with client.session(operation) as session:
        plan = session.plan_import(request)
        assert plan["kind"] == "import" and plan["candidates"] == [] and plan["targets"] == []
        assert plan["imports"] == [
            dict(id=identifier, metadata_sha256=history.sha(history.encoded(import_metadata)))
        ]
        plan_path = session.file("retire-import-frozen-plan.json", plan)
        catalog_path = session.file("retire-import-frozen-catalog.json", session.catalog_snapshot())
        runtime.invoke(
            "retire",
            runtime.archive,
            plan_path,
            catalog_path,
            operation,
            operation=operation,
            crash="after_retirement_publication",
            expected="crash",
            catalog_lock=False,
            owned_operation=session.operation,
        )
        assert history.verified(directory / "import.json") == import_metadata
        output = runtime.folder / "retired-import-export"
        runtime.invoke(
            "export-import",
            runtime.archive,
            identifier,
            output / "run",
            output / "cache",
            output / "index",
            operation=operation,
            expected="archive_retired",
            catalog_lock=False,
            owned_operation=session.operation,
        )
        record = session.retire(plan)
        assert not directory.exists()
        assert session.retire(plan) == record
        assert not directory.exists()
    assert hashes(runtime.folder / "legacy") == original
    assert {name: hashes(runtime.folder / name) for name in p05_originals} == p05_originals
    assert {
        path: digest
        for path, digest in hashes(runtime.archive).items()
        if not path.startswith(
            ("maintenance/holds/", "maintenance/retirements/", "imports/" + identifier + "/")
        )
    } == protected
    cases.append(
        "actual_completed_p05_import_durable_retirement_crash_public_retry_and_retired_retrieval"
    )
