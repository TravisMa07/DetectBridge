"""Review, prepare and independently qualify a local controlled Windows recording."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_contracts import ContractValidator  # noqa: E402
from detection_mapping import require_schema, validate_profiles  # noqa: E402

MODULE = Path(__file__).resolve().parent
NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"
LIMIT = 32 * 1024 * 1024
RULE = "71110000-0000-4000-8000-000000000001"
SIGNATURES = {
    "security": ("Microsoft-Windows-Security-Auditing", "4688", "2", "Security"),
    "sysmon": ("Microsoft-Windows-Sysmon", "1", "5", "Microsoft-Windows-Sysmon/Operational"),
}


def require(value):
    if not value:
        raise ValueError("controlled_recording_mismatch")


def encoded(value, canonical=False):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=canonical, separators=(",", ":")
    ).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def identity(value):
    return "sha256:" + sha(encoded(value))


def load(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= LIMIT)
    return json.loads(path.read_bytes())


def xml_record(data):
    require(len(data) <= 1024 * 1024 and b"<!DOCTYPE" not in data and b"<!ENTITY" not in data)
    node = ET.fromstring(data.decode("utf-8"))
    require(node.tag == NS + "Event")
    system = node.find(NS + "System")
    require(system is not None)
    fields = {}
    for item in node.find(NS + "EventData"):
        name = item.attrib["Name"]
        require(name not in fields)
        fields[name] = item.text or ""
    signature = (
        system.find(NS + "Provider").attrib["Name"],
        system.findtext(NS + "EventID"),
        system.findtext(NS + "Version"),
        system.findtext(NS + "Channel"),
    )
    return system, fields, signature


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".windows-recording-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def review(directory, run):
    """Produce a candidate catalog from originals, before any adapter/evaluator use."""
    require(run["event"] == "workflow_dispatch")
    job = load(directory.parent / "job.json")
    require(job["run_id"] == run["id"] and job["head_sha"] == run["head_sha"])
    require(job["name"] == "controlled-windows-recording" and job["conclusion"] == "success")
    require(all(step["conclusion"] == "success" for step in job["steps"]))
    artifact = load(directory.parent / "artifact.json")
    require(artifact["name"] == "p11-controlled-windows-encrypted")
    require(
        artifact["workflow_run"]["id"] == run["id"]
        and artifact["workflow_run"]["head_sha"] == run["head_sha"]
    )
    transport = directory.parent / "transport.zip"
    require(transport.stat().st_size == artifact["size_in_bytes"] <= LIMIT)
    require("sha256:" + sha(transport.read_bytes()) == artifact["digest"])
    with zipfile.ZipFile(transport) as archive:
        require(archive.namelist() == ["recording.p7m"])
        require(archive.getinfo("recording.p7m").file_size <= LIMIT)
        require(archive.read("recording.p7m") == (directory.parent / "recording.p7m").read_bytes())
    with zipfile.ZipFile(directory.parent / "originals.zip") as archive:
        require(set(archive.namelist()) == {p.name for p in directory.iterdir()})
        require(len(archive.namelist()) == len(set(archive.namelist())) <= 64)
        require(sum(i.file_size for i in archive.infolist()) <= LIMIT)
        for info in archive.infolist():
            require(Path(info.filename).name == info.filename)
            require(archive.read(info) == (directory / info.filename).read_bytes())
    host = load(directory / "host.json")
    origin = host["origin"]
    require(origin["repository"] == "TravisMa07/DetectBridge")
    require(str(run["id"]) == origin["run_id"] and str(run["run_attempt"]) == origin["run_attempt"])
    require(run["head_sha"] == origin["commit"] and origin["job"] == "controlled-windows-recording")
    require(origin["runner_os"] == "Windows" and origin["runner_arch"] == "X64")
    require(str(uuid.UUID(host["machine_guid"])).lower() == host["machine_guid"].lower())
    require(str(uuid.UUID(host["product_uuid"])).lower() == host["product_uuid"].lower())
    expected = load(MODULE / "recording/expectations.json")
    require(load(directory / "action-expectations.json") == expected)
    # Resolve committed script bytes from the actual capture head, not current HEAD.
    import subprocess

    checkout = []
    for name in ("capture.ps1", "expectations.json"):
        captured = directory / ("action-expectations.json" if name.endswith("json") else name)
        committed = subprocess.check_output(
            ["git", "show", f"{origin['commit']}:packages/windows-adapters/recording/{name}"],
            cwd=ROOT,
        )
        retained = captured.read_bytes()
        transform = "identity/1.0.0" if retained == committed else "git-lf-to-crlf/1.0.0"
        require(
            retained == committed
            if transform.startswith("identity")
            else retained == committed.replace(b"\n", b"\r\n")
        )
        checkout.append(
            dict(
                filename=captured.name,
                git_blob_sha256=sha(committed),
                retained_sha256=sha(retained),
                transform=transform,
            )
        )
    require(load(directory / "command-line-policy.json") == 1)
    require("Success" in (directory / "audit-policy-active.csv").read_text(encoding="utf-8-sig"))
    sysmon = load(directory / "sysmon.json")
    require(
        sysmon["zip_sha256"] == "00ecf1b46aec99299d3ae0bca79dc621458bd014b20b509d7c5c8e8c8611aa54"
    )
    require(sysmon["signature_status"] == "Valid" and "Microsoft Corporation" in sysmon["signer"])
    require(
        sha((directory / "sysmon-license.txt").read_bytes())
        == "8329bcbadc7f81539a4969ca13f0be5b8eb7652b912324a1926fc9bfb6ec005a"
    )
    actions = load(directory / "actions.json")
    require(len(actions) == 2 and len({a["pid"] for a in actions}) == 2)
    for action, spec in zip(actions, expected["actions"]):
        require(all(action[k] == spec[k] for k in ("id", "image", "arguments", "exit_code")))
        require(action["pid"] > 0 and action["parent_pid"] > 0)
    selected = load(directory / "selection.json")
    require(len(selected) == 5 and len({r["filename"] for r in selected}) == 5)
    complete = load(directory / "capture-complete.json")
    require(complete["selected_records"] == 5)
    rows = []
    seen = set()
    for item in selected:
        family, action_id = item["family"], item["action"]
        require(family in SIGNATURES and action_id in ("cmd", "hostname", "service-state"))
        expected_name = (
            f"{family}-control.xml" if action_id == "service-state" else f"{family}-{action_id}.xml"
        )
        require(item["filename"] == expected_name)
        data = (directory / item["filename"]).read_bytes()
        system, fields, signature = xml_record(data)
        computer = system.findtext(NS + "Computer")
        dns = host["dns"]
        names = {host["computer"]["Name"].lower(), dns["hostname"].lower()}
        if dns["domain"]:
            names.add((dns["hostname"] + "." + dns["domain"]).lower())
        require(computer.lower() in names)
        require(int(system.findtext(NS + "EventRecordID")) == item["event_record_id"])
        observed = item["observed_utc"]
        require(
            datetime.fromisoformat(observed) <= datetime.fromisoformat(complete["completed_utc"])
        )
        if action_id == "service-state":
            require(
                family == "sysmon" and signature[0] == SIGNATURES[family][0] and signature[1] == "4"
            )
            require(signature[3] == SIGNATURES[family][3])
            expected_row = dict(disposition="unsupported_source")
        else:
            require(signature == SIGNATURES[family])
            action = next(a for a in actions if a["id"] == action_id)
            security = family == "security"
            image = fields["NewProcessName" if security else "Image"]
            pid = int(fields["NewProcessId" if security else "ProcessId"], 16 if security else 10)
            parent = int(
                fields["ProcessId" if security else "ParentProcessId"], 16 if security else 10
            )
            require(
                image.lower() == action["image"].lower()
                and pid == action["pid"]
                and parent == action["parent_pid"]
            )
            require(bool(fields["CommandLine"]) and action["arguments"] in fields["CommandLine"])
            if security:
                require(fields["SubjectUserSid"] == host["identity"]["sid"])
                account = fields["SubjectDomainName"] + "\\" + fields["SubjectUserName"]
            else:
                account = fields["User"]
            require(account.lower() == host["identity"]["name"].lower())
            native_time = system.find(NS + "TimeCreated").attrib["SystemTime"]
            require(
                datetime.fromisoformat(action["started_utc"])
                <= datetime.fromisoformat(native_time)
                <= datetime.fromisoformat(observed)
            )
            expected_row = dict(
                disposition="eligible",
                image=image,
                pid=pid,
                parent_pid=parent,
                command_line=fields["CommandLine"],
                user=account,
                source_time=native_time if security else fields["UtcTime"],
                counts=expected["rule_counts"][action_id],
            )
        seen.add((family, action_id))
        rows.append(
            dict(
                **item,
                sha256=sha(data),
                size_bytes=len(data),
                computer=computer,
                expected=expected_row,
            )
        )
    require(
        seen
        == {(f, a) for f in SIGNATURES for a in ("cmd", "hostname")} | {("sysmon", "service-state")}
    )
    artifacts = []
    for path in sorted(directory.iterdir()):
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= LIMIT)
        artifacts.append(
            dict(filename=path.name, sha256=sha(path.read_bytes()), size_bytes=path.stat().st_size)
        )
    return dict(
        version="1.0.0",
        id="windows-process-lab-v1",
        kind="local-controlled-recording",
        review_status="candidate",
        capture_run=dict(
            id=run["id"], attempt=run["run_attempt"], commit=run["head_sha"], url=run["html_url"]
        ),
        host_id="windows-machineguid:" + host["machine_guid"].lower(),
        generation=host["boot_utc"],
        observation_policy=dict(
            version="per-record-capture-completion/1.0.0",
            description="Retained selected XML capture-completion timestamps; exact first Get-WinEvent enumeration time is unavailable.",
        ),
        artifacts=artifacts,
        records=rows,
        terms=dict(
            scope="local-qualification-only",
            payload_publication=False,
            sysmon_binary_redistribution=False,
        ),
    )


def artifacts(catalog, directory):
    require(catalog["version"] == "1.0.0" and catalog["review_status"] == "reviewed")
    require(
        catalog["terms"]
        == dict(
            scope="local-qualification-only",
            payload_publication=False,
            sysmon_binary_redistribution=False,
        )
    )
    seen = set()
    for item in catalog["artifacts"]:
        name = item["filename"]
        require(Path(name).name == name and name not in seen)
        seen.add(name)
        path = directory / name
        require(not path.is_symlink() and path.stat().st_size == item["size_bytes"] <= LIMIT)
        require(sha(path.read_bytes()) == item["sha256"])
    require(
        {"host.json", "actions.json", "selection.json", "capture.ps1", "action-expectations.json"}
        <= seen
    )
    # Recheck provenance/independent action relations; a catalog hash is not authenticity.
    run = load(directory.parent / "run.json")
    candidate = review(directory, run)
    candidate["review_status"] = "reviewed"
    candidate["review"] = catalog["review"]
    require(candidate == catalog)
    require(catalog["review"]["provenance"] and catalog["review"]["independent_expectations"])


def inputs(catalog, directory, run_id):
    require(str(uuid.UUID(run_id)).lower() == run_id.lower())
    artifacts(catalog, directory)
    rows = []
    catalog_hash = sha(encoded(catalog, True))
    for position, item in enumerate(catalog["records"]):
        family = item["family"]
        data = (directory / item["filename"]).read_bytes()
        # Inline preserves exact API bytes, avoiding any LF reserialization.
        require(b"\n" not in data and b"\r" not in data)
        source = dict(
            namespace="detectbridge-windows-lab",
            instance=f"github:{catalog['capture_run']['id']}:{catalog['capture_run']['attempt']}:{family}",
        )
        raw = dict(
            contract_version="1.0.0",
            source=source,
            cursor=dict(kind="native", value=f"{family}:{item['event_record_id']}"),
            first_observed=item["observed_utc"],
            evidence=dict(
                sha256=sha(data),
                encoding="utf-8",
                media_type="application/xml",
                inline=data.decode("utf-8"),
            ),
        )
        raw["record_id"] = identity(
            [source["namespace"], source["instance"], ["native", raw["cursor"]["value"]]]
        )
        snapshot = load(MODULE / f"profiles/{family}.source.json")
        mapping = load(MODULE / f"profiles/{family}.mapping.json")
        binding = dict(
            host_id=catalog["host_id"],
            computer=item["computer"],
            source=source,
            revision="windows-process-lab/1.0.0",
            kind="reviewed",
            provenance=[
                "catalog-sha256:" + catalog_hash,
                catalog["capture_run"]["url"] + ":host.json",
            ],
        )
        binding["sha256"] = sha(encoded(binding, True))
        context = dict(
            version="1.0.0",
            run_id=run_id,
            source=source,
            first_observed=raw["first_observed"],
            source_contract=dict(
                id=snapshot["id"],
                version=snapshot["version"],
                sha256=sha(encoded(snapshot, True)),
                snapshot=snapshot,
            ),
            mapping_profile=dict(
                id=mapping["id"],
                version=mapping["version"],
                sha256=mapping["sha256"],
                declaration=mapping,
            ),
            parser=dict(id="windows-xml", version="1.0.0"),
            host_binding=binding,
            source_generation=dict(
                id=catalog["generation"],
                provenance=["catalog-sha256:" + catalog_hash],
                command_line_capture="enabled",
            ),
        )
        rows.append(dict(raw=raw, context=context))
    return rows


def verify(catalog, directory, supplied, published, plan, run_id):
    expected_inputs = inputs(catalog, directory, run_id)
    require(supplied == expected_inputs and len(published) == len(supplied) == 5)
    require_schema("plan", plan)
    require(plan["version"] == "2.0.0")
    unhashed = dict(plan)
    unhashed.pop("bundle_sha256")
    require(sha(encoded(unhashed, True)) == plan["bundle_sha256"])
    validate_profiles(plan["mapping_profiles"], plan["sources"])
    require(len(plan["rules"]) == 3)
    # Bind actual committed YAML, not a plan declaring convenient expected results.
    from recording_plan import validate_rules

    validate_rules(plan)
    validator = ContractValidator()
    counts = dict(records=5, eligible=0, unsupported=0, matched=0, unmatched=0)
    for index, (original, output, item) in enumerate(zip(supplied, published, catalog["records"])):
        require(
            output["raw"] == original["raw"]
            and output["context"] == original["context"]
            and output["version"] == "1.0.0"
        )
        raw, context = original["raw"], original["context"]
        require(not validator.validate("raw-record", raw))
        if item["expected"]["disposition"] == "unsupported_source":
            require(set(output) == {"version", "raw", "context", "preservation"})
            require(
                output["preservation"]
                == dict(
                    version="1.0.0",
                    record_id=raw["record_id"],
                    run_id=run_id,
                    evidence_sha256=raw["evidence"]["sha256"],
                    code="unsupported_source",
                    reason="source_signature",
                    field="",
                )
            )
            counts["unsupported"] += 1
            continue
        require(set(output) == {"version", "raw", "context", "event", "evaluation"})
        event, evaluation = output["event"], output["evaluation"]
        require(
            not validator.validate(
                "normalized-event", event, source_contract=context["source_contract"]["snapshot"]
            )
        )
        ex = item["expected"]
        require(
            event["process"]["executable"] == ex["image"]
            and event["process"]["pid"] == ex["pid"]
            and event["process"]["parent"]["pid"] == ex["parent_pid"]
            and event["process"]["command_line"] == ex["command_line"]
        )
        require(event["user"]["domain"] + "\\" + event["user"]["name"] == ex["user"])
        require(event["host"] == dict(id=catalog["host_id"], name=item["computer"]))
        system, fields, _ = xml_record((directory / item["filename"]).read_bytes())
        system_values = {child.tag.removeprefix(NS): child.text or "" for child in system}
        system_attributes = {child.tag.removeprefix(NS): child.attrib for child in system}
        require(
            event["source_fields"]
            == dict(fields, windows_system=dict(values=system_values, attributes=system_attributes))
        )
        security = item["family"] == "security"
        if security:
            require(event["user"].get("id") == fields["SubjectUserSid"])
        else:
            for key, source_name in (
                ("entity_id", "ProcessGuid"),
                ("working_directory", "CurrentDirectory"),
            ):
                require(event["process"].get(key) == (fields.get(source_name) or None))
            for key, source_name in (
                ("entity_id", "ParentProcessGuid"),
                ("executable", "ParentImage"),
                ("command_line", "ParentCommandLine"),
            ):
                require(event["process"]["parent"].get(key) == (fields.get(source_name) or None))
        db = event["detectbridge"]
        require(
            db["quality"] == dict(integrity="sufficient", eligibility="eligible", diagnostics=[])
        )
        timestamp = (
            ex["source_time"]
            if item["family"] == "security"
            else ex["source_time"].replace(" ", "T") + "Z"
        )
        require(
            event["@timestamp"] == timestamp and event["event"]["created"] == raw["first_observed"]
        )
        require(
            db["time"]
            == dict(
                basis="source",
                quality="valid",
                first_observed=raw["first_observed"],
                source_value=ex["source_time"],
                source_utc=timestamp,
            )
        )
        require(db["run_id"] == run_id and db["source"] == raw["source"])
        require(db["evidence"] == [dict(record_id=raw["record_id"], evidence=raw["evidence"])])
        require(
            db["source_contract"] == {k: context["source_contract"][k] for k in ("id", "version")}
        )
        require(
            db["processing"]
            == dict(
                parser="windows-xml/1.0.0",
                normalizer="windows-normalizer/1.0.0",
                mapping=context["mapping_profile"]["id"] + "/1.0.0",
            )
        )
        event_id = identity(
            [raw["source"]["namespace"], raw["source"]["instance"], [raw["record_id"]]]
        )
        require(
            event["event"]
            == dict(
                id=event_id,
                kind="event",
                category=["process"],
                type=["start"],
                code="4688" if security else "1",
                created=raw["first_observed"],
                provider=SIGNATURES[item["family"]][0],
            )
        )
        require(
            db["assembly"]
            == dict(
                mode="standalone",
                closure="not_required",
                quality="source_indicated",
                assembler_version="1.0.0",
            )
        )
        require_schema("result", evaluation)
        require(evaluation["counts"] == ex["counts"] and evaluation["diagnostics"] == [])
        matches = (
            [dict(id=RULE, revision=next(r["revision"] for r in plan["rules"] if r["id"] == RULE))]
            if item["action"] == "cmd"
            else []
        )
        require(evaluation["matched"] == matches)
        require(evaluation["event_id"] == event_id and evaluation["run_id"] == run_id)
        require(evaluation["result_id"] == identity([event_id, run_id, plan["bundle_sha256"]]))
        require(
            evaluation["bundle_sha256"] == plan["bundle_sha256"]
            and evaluation["mapping_sha256"] == sha(encoded(plan["mapping_profiles"], True))
        )
        for name in ("compiler", "evaluator", "mapping_version"):
            require(evaluation[name] == plan[name])
        require(
            evaluation["input"]
            == dict(
                cluster_id="offline",
                topic_id="offline",
                topic="windows-offline",
                partition=0,
                offset=index,
                value_sha256=sha(encoded(event)),
            )
        )
        counts["eligible"] += 1
        for name in ("matched", "unmatched"):
            counts[name] += ex["counts"][name]
    require(counts == dict(records=5, eligible=4, unsupported=1, matched=2, unmatched=6))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--run", type=Path, help="Retained GitHub workflow run metadata")
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    try:
        if args.candidate:
            atomic(args.candidate, encoded(review(args.directory, load(args.run)), True) + b"\n")
            print('{"status":"candidate_only_not_reviewed"}')
        elif args.prepare:
            rows = inputs(load(args.catalog), args.directory, args.run_id)
            atomic(args.prepare, b"".join(encoded(row, True) + b"\n" for row in rows))
            print('{"status":"prepared","records":5}')
        else:
            result = verify(
                load(args.catalog),
                args.directory,
                [json.loads(line) for line in args.input.read_bytes().splitlines()],
                [json.loads(line) for line in args.output.read_bytes().splitlines()],
                load(args.plan),
                args.run_id,
            )
            print(json.dumps(result, sort_keys=True))
    except Exception:
        print('{"category":"controlled_windows_qualification_failed"}', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
