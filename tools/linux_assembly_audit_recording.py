"""Independently qualify the reviewed local audit recording and atomic offline replay."""

import argparse
import base64
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from check_contracts import ContractValidator
from detection_mapping import require_schema
from linux_assembly_cases import ROOT, digest, encoded, identity
from linux_assembly_verify import manifest, member, require

CATALOG = ROOT / "catalog/recordings/linux-audit-execve-lab-v1.json"
HERE = ROOT / "packages/linux-adapters/audit-recording"
RUN = "00000000-0000-4000-8000-000000000014"


def sha(data):
    import hashlib

    return hashlib.sha256(data).hexdigest()


def capture_module():
    spec = importlib.util.spec_from_file_location("audit_capture", HERE / "capture.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status(data):
    result = {}
    for key in ("enabled", "pid", "lost", "backlog", "backlog_limit", "rate_limit"):
        values = re.findall(r"^" + key + r" ([0-9]+)$", data.decode(), re.M)
        require(len(values) == 1)
        result[key] = int(values[0])
    require(result["enabled"] == 1 and result["pid"] > 0)
    require(result["lost"] == result["backlog"] == result["rate_limit"] == 0)
    require(result["backlog_limit"] == 8192)
    return result


def observation(catalog, captured):
    require(catalog["processing_metadata"]["version"] == "1.1.0")
    correction = catalog["processing_metadata"]["correction"]
    require(correction["original_value"] == captured["first_observed"])
    require(
        catalog["acquisition"]["first_observed"]
        == correction["corrected_value"]
        == captured["completed"]
    )
    require(
        datetime.fromisoformat(captured["completed"])
        >= datetime.fromisoformat(captured["first_observed"])
    )


def artifacts(catalog, directory):
    require(catalog["version"] == "1.0.0" and catalog["kind"] == "local-controlled-recording")
    names = set()
    for artifact in catalog["artifacts"]:
        name = artifact["filename"]
        require(Path(name).name == name and name not in names)
        names.add(name)
        path = directory / name
        require(path.is_file() and not path.is_symlink())
        require(path.stat().st_size == artifact["size_bytes"] <= 64 * 1024 * 1024)
        require(sha(path.read_bytes()) == artifact["sha256"])
    require(
        {
            "guest.serial",
            "audit.native",
            "container.json",
            "image.json",
            "kernel",
            "kernel.config",
            "guest.cpio.gz",
            "packages.txt",
            "copyrights.tar.gz",
            "binaries.sha256",
            "capture-manifest.json",
        }
        <= names
    )
    for name in (
        "Dockerfile",
        "guest-init",
        "build-initramfs.py",
        "probe.c",
        "expectations.json",
    ):
        require((directory / name).read_bytes() == (HERE / name).read_bytes())
    a = catalog["acquisition"]
    # Historical capture source is pinned by the reviewed catalog and original
    # artifact; newer capture tooling must not rewrite that provenance.
    require(sha((directory / "capture.py").read_bytes()) == a["capture_sha256"])
    captured = json.loads((directory / "capture-manifest.json").read_bytes())
    observation(catalog, captured)
    expected = catalog["independent_expectations"]
    require(sha((ROOT / expected["path"]).read_bytes()) == expected["sha256"])
    extracted = capture_module().extract((directory / "guest.serial").read_bytes())
    for name, data in extracted.items():
        require(data == (directory / name).read_bytes())
    before, after = [status(extracted[name]) for name in ("status-before", "status-after")]
    require(before["pid"] == after["pid"])
    require(
        extracted["action-exit"] == b"0\n"
        and extracted["action.stdout"] == b"detectbridge controlled audit action\n"
    )
    require(
        extracted["rules"] == b"-w /usr/local/bin/bridge-audit-probe -p x -k detectbridge-p12c\n"
    )
    require(extracted["cmdline"] == b"console=ttyAMA0 audit=1 panic=1 rdinit=/init\n")
    require(extracted["kernel-version"].decode().strip() == a["kernel"])
    config = (directory / "kernel.config").read_text()
    require("CONFIG_AUDIT=y\n" in config and "CONFIG_AUDITSYSCALL=y\n" in config)
    require(a["source_generation"]["id"] == "linux-boot:" + extracted["boot-id"].decode().strip())
    image = json.loads((directory / "image.json").read_bytes())[0]
    container = json.loads((directory / "container.json").read_bytes())[0]
    require(image["Id"] == container["Image"] == a["image_id"] and image["Architecture"] == "arm64")
    require(
        container["Id"] == a["source"]["instance"] and container["Path"] == "qemu-system-aarch64"
    )
    require(
        container["Args"] == image["Config"]["Cmd"][1:] and not image["Config"].get("Entrypoint")
    )
    require(container["State"]["ExitCode"] == 0 and not container["State"]["OOMKilled"])
    host = container["HostConfig"]
    require(host["NetworkMode"] == "none" and not host["Privileged"] and host["ReadonlyRootfs"])
    require(
        host["CapDrop"] == ["ALL"]
        and not host["CapAdd"]
        and not host["Devices"]
        and not host["Binds"]
    )
    require("no-new-privileges" in host["SecurityOpt"] and not host["PortBindings"])
    require(all(m["Type"] == "tmpfs" and m["Destination"] == "/tmp" for m in container["Mounts"]))
    binding = dict(a["host_binding"])
    binding_sha = binding.pop("sha256")
    require(binding["kind"] == "reviewed" and binding["source"] == a["source"])
    require(
        binding["host_id"] == "qemu-guest:" + container["Id"] and digest(binding) == binding_sha
    )
    rows = extracted["audit.native"].splitlines(keepends=True)
    require(len(rows) == len(catalog["records"]))
    for i, (row, expected_row) in enumerate(zip(rows, catalog["records"])):
        require(expected_row["position"] == i and expected_row["sha256"] == sha(row))
        require(expected_row["size_bytes"] == len(row) and row.endswith(b"\n"))
    return rows


def prepared(catalog, originals, run=RUN):
    a = catalog["acquisition"]
    family = "linux-audit-execution-p12a"
    directory = ROOT / "packages/linux-adapters/contracts"
    source = json.loads((directory / (family + ".source.json")).read_bytes())
    mapping = json.loads((directory / (family + ".mapping.json")).read_bytes())
    ctx = {key: a[key] for key in ("source", "first_observed", "host_binding", "source_generation")}
    ctx.update(
        version="1.0.0",
        run_id=run,
        source_contract=dict(id=family, version="1.0.0", sha256=digest(source), snapshot=source),
        mapping_profile=dict(
            id=mapping["id"],
            version=mapping["version"],
            sha256=mapping["sha256"],
            declaration=mapping,
        ),
        parser=dict(id="linux-audit", version="1.0.0"),
    )
    object_sha = sha(b"".join(originals))
    rows = []
    for i, original in enumerate(originals):
        raw = dict(
            contract_version="1.0.0",
            source=ctx["source"],
            first_observed=ctx["first_observed"],
            cursor=dict(kind="dataset", artifact_sha256=object_sha, position=i),
            evidence=dict(
                sha256=sha(original),
                encoding="utf-8",
                media_type="text/plain",
                inline=original.decode(),
            ),
        )
        raw["record_id"] = identity(
            [ctx["source"]["namespace"], ctx["source"]["instance"], ["dataset", object_sha, str(i)]]
        )
        rows.append(dict(raw=raw, context=ctx))
    return rows


def expected_documents(catalog, rows):
    manifests, events, diagnostics = {}, {}, {}
    covered = []
    for group in catalog["groups"]:
        positions = group["member_positions"]
        covered.extend(positions)
        originals = [dict(version="1.0.0", kind="record", **rows[i]) for i in positions]
        document = manifest(originals, group["closure"], group["findings"])
        require(document["key"]["audit_timestamp"] == group["audit_timestamp"])
        require(document["key"]["audit_serial"] == group["audit_serial"])
        manifests[document["manifest_id"]] = document
        events[document["event_id"]] = (group, originals)
    for i, row in enumerate(rows):
        code = catalog["records"][i]["disposition"]
        if code == "group_member":
            continue
        require(code == "extraction_failed")
        covered.append(i)
        ctx, raw = row["context"], row["raw"]
        doc = dict(
            version="1.0.0",
            kind="preservation",
            code=code,
            run_id=ctx["run_id"],
            source=raw["source"],
            member=member(row),
            context=ctx,
            id=identity([ctx["run_id"], raw["record_id"], code]),
        )
        diagnostics[doc["id"]] = doc
    require(sorted(covered) == list(range(len(rows))))
    return manifests, events, diagnostics


def source_time(timestamp):
    seconds, fraction = timestamp.split(".")
    fraction = fraction.rstrip("0")
    fraction = fraction.ljust(((len(fraction) + 2) // 3) * 3, "0")
    return (
        datetime.fromtimestamp(int(seconds), UTC).strftime("%Y-%m-%dT%H:%M:%S")
        + ("." + fraction if fraction else "")
        + "Z"
    )


def verify_event(catalog, group, rows, event):
    ctx = rows[0]["context"]
    require(
        not ContractValidator().validate(
            "normalized-event", event, source_contract=ctx["source_contract"]["snapshot"]
        )
    )
    db = event["detectbridge"]
    eligible = not group["findings"]
    require(db["run_id"] == ctx["run_id"] and db["source"] == ctx["source"])
    require(event["host"]["id"] == ctx["host_binding"]["host_id"])
    require(
        db["evidence"]
        == [dict(record_id=r["raw"]["record_id"], evidence=r["raw"]["evidence"]) for r in rows]
    )
    require(db["source_contract"] == {k: ctx["source_contract"][k] for k in ("id", "version")})
    require(
        db["processing"]
        == dict(
            parser="linux-audit/1.0.0",
            mapping=ctx["mapping_profile"]["id"] + "/1.0.0",
            normalizer="linux-p12a/1.0.0",
        )
    )
    require(
        db["time"]
        == dict(
            basis="source",
            quality="valid",
            first_observed=ctx["first_observed"],
            source_value=group["audit_timestamp"],
            source_utc=source_time(group["audit_timestamp"]),
        )
    )
    require(event["@timestamp"] == db["time"]["source_utc"])
    quality_diagnostics = [] if eligible else [dict(code="assembly_insufficient", field="")]
    if any(finding.startswith("unsupported_") for finding in group["findings"]):
        quality_diagnostics.append(dict(code="unsupported_source", field=""))
    require(
        db["quality"]
        == dict(
            eligibility="eligible" if eligible else "skipped",
            integrity="sufficient" if eligible else "insufficient",
            diagnostics=quality_diagnostics,
        )
    )
    require(
        db["assembly"]
        == dict(
            mode="assembled",
            closure=group["closure"],
            quality="source_indicated" if eligible else "known_missing",
            assembler_version="1.0.0",
        )
    )
    require(
        event["event"]["provider"] == "auditd"
        and event["event"]["dataset"] == ctx["source_contract"]["id"]
    )
    require(
        db["extensions"]["linux.context"]
        == dict(
            version="1.0.0",
            context=ctx,
            findings=group["findings"],
            source_sha256=ctx["source_contract"]["sha256"],
            mapping_sha256=ctx["mapping_profile"]["sha256"],
        )
    )
    fields = event["source_fields"]
    require(len(fields["audit_records"]) == len(rows))
    for record, row in zip(fields["audit_records"], rows):
        # Reconstruct original token spellings and order; never parse with the Java adapter.
        header = (
            "type="
            + record["type"]
            + " msg=audit("
            + record["timestamp"]
            + ":"
            + record["serial"]
            + "):"
        )
        body = " ".join(t["name"] + "=" + t["raw"] for t in record["tokens"])
        require(
            record["node"] is None
            and (header + (" " + body if body else "") + "\n") == row["raw"]["evidence"]["inline"]
        )
    require("command_line" not in event.get("process", {}) and "path" not in event.get("file", {}))
    if eligible:
        execution = catalog["execution"]
        require(
            event["process"]
            == dict(
                executable=execution["executable"],
                args=execution["args"],
                pid=execution["pid"],
                working_directory=execution["cwd"],
            )
        )
        require(fields["paths"] == execution["paths"] and fields["arguments"] == execution["args"])
        require(fields["exe"] == execution["executable"] and fields["cwd"] == execution["cwd"])
        require(event["@timestamp"] == execution["timestamp"])
        require(
            base64.b64decode(fields["proctitle_bytes_base64"])
            == b"\0".join(arg.encode() for arg in execution["args"])
        )


def verify_evaluation(result, event, plan, outcome, offset):
    require_schema("result", result)
    db, rule = event["detectbridge"], plan["rules"][0]
    require(result["event_id"] == event["event"]["id"] and result["run_id"] == db["run_id"])
    require(result["bundle_sha256"] == plan["bundle_sha256"])
    require(
        result["result_id"] == identity([event["event"]["id"], db["run_id"], plan["bundle_sha256"]])
    )
    require(result["mapping_sha256"] == digest(plan["mapping_profiles"]))
    for key in ("compiler", "evaluator", "mapping_version"):
        require(result[key] == plan[key])
    require(
        result["input"]
        == dict(
            cluster_id="offline",
            topic_id="offline",
            topic="linux-audit-offline",
            partition=0,
            offset=offset,
            value_sha256=sha(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()),
        )
    )
    require(
        result["counts"]
        == {
            key: int(key == outcome)
            for key in (
                "matched",
                "unmatched",
                "inapplicable",
                "quality_skipped",
                "configuration_blocked",
                "evaluation_error",
            )
        }
    )
    require(
        result["matched"]
        == ([dict(id=rule["id"], revision=rule["revision"])] if outcome == "matched" else [])
    )
    require(
        result["diagnostics"]
        == (
            [dict(rule_id=rule["id"], category=outcome, pointer="")]
            if outcome in ("quality_skipped", "configuration_blocked")
            else []
        )
    )


def verify(catalog, rows, input_path, output_path, plan_path, rule_name):
    require(rule_name in catalog["independent_expectations"]["outcomes"])
    require([json.loads(line) for line in input_path.read_bytes().splitlines()] == rows)
    plan = json.loads(plan_path.read_bytes())
    require_schema("plan", plan)
    unhashed = dict(plan)
    require(unhashed.pop("bundle_sha256") == digest(unhashed))
    require(len(plan["rules"]) == 1)
    original = (ROOT / "packages/linux-adapters/fixtures/rules" / (rule_name + ".yml")).read_bytes()
    require(
        plan["rules"][0]["yaml"] == original.decode()
        and plan["rules"][0]["revision"] == sha(original)
    )
    rule = plan["rules"][0]
    field, literal = {
        "audit-probe-match": ("process.executable", "/usr/local/bin/bridge-audit-probe"),
        "image-nonmatch": ("process.executable", "/bin/false"),
        "command-blocked": ("process.command_line", "whoami"),
    }[rule_name]
    require(
        rule["expression"]
        == dict(
            field=field,
            op="string",
            tokens=[dict(kind="literal", text=character) for character in literal],
        )
    )
    require(
        rule["id"]
        == next(line[4:] for line in original.decode().splitlines() if line.startswith("id: "))
    )
    contracts = ROOT / "packages/linux-adapters/contracts"
    require(
        plan["mapping_profiles"]
        == [json.loads(path.read_bytes()) for path in sorted(contracts.glob("*.mapping.json"))]
    )
    require(
        plan["sources"]
        == [json.loads(path.read_bytes()) for path in sorted(contracts.glob("*.source.json"))]
    )
    expected_manifests, expected_events, expected_diagnostics = expected_documents(catalog, rows)
    seen: dict[str, set[str]] = {"manifest": set(), "event": set(), "preservation": set()}
    retained, evaluations = [], 0
    with output_path.open() as output:
        for line in output:
            row = json.loads(line)
            require(row["version"] == "1.0.0")
            kind = row["kind"]
            if kind == "input":
                require(set(row) == {"version", "kind", "raw", "context"})
                retained.append({key: row[key] for key in ("raw", "context")})
                continue
            require(
                kind in seen
                and set(row)
                == (
                    {"version", "kind", "document", "evaluation"}
                    if kind == "event"
                    else {"version", "kind", "document"}
                )
            )
            doc = row["document"]
            key = (
                doc["event"]["id"]
                if kind == "event"
                else doc["manifest_id"]
                if kind == "manifest"
                else doc["id"]
            )
            require(key not in seen[kind])
            seen[kind].add(key)
            if kind == "manifest":
                require(key in expected_manifests and doc == expected_manifests[key])
            elif kind == "preservation":
                require(key in expected_diagnostics and doc == expected_diagnostics[key])
            else:
                require(key in expected_events)
                group, members = expected_events[key]
                verify_event(catalog, group, members, doc)
                expected_outcome = catalog["independent_expectations"]["outcomes"][rule_name]
                outcome = (
                    expected_outcome
                    if not group["findings"] or expected_outcome == "configuration_blocked"
                    else "quality_skipped"
                )
                verify_evaluation(row["evaluation"], doc, plan, outcome, evaluations)
                evaluations += 1
    require(
        retained == rows
        and seen["manifest"] == set(expected_manifests)
        and seen["event"] == set(expected_events)
        and seen["preservation"] == set(expected_diagnostics)
    )
    return dict(
        status="qualified",
        records=len(rows),
        groups=len(expected_manifests),
        eligible=sum(not g["findings"] for g in catalog["groups"]),
        preserved_diagnostics=len(expected_diagnostics),
        rule=rule_name,
        bundle_sha256=plan["bundle_sha256"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument(
        "--rule", choices=("audit-probe-match", "image-nonmatch", "command-blocked")
    )
    args = parser.parse_args()
    try:
        catalog = json.loads(CATALOG.read_bytes())
        originals = artifacts(catalog, args.directory)
        rows = prepared(catalog, originals)
        expected_documents(catalog, rows)
        if args.prepare:
            require(
                args.prepare.resolve()
                not in {
                    (args.directory / artifact["filename"]).resolve()
                    for artifact in catalog["artifacts"]
                }
            )
            args.prepare.write_bytes(b"".join(encoded(row) + b"\n" for row in rows))
            print(json.dumps(dict(status="prepared", records=len(rows))))
        else:
            require(all(arg is not None for arg in (args.input, args.output, args.plan, args.rule)))
            print(json.dumps(verify(catalog, rows, args.input, args.output, args.plan, args.rule)))
    except Exception:
        print(
            '{"status":"failed","category":"audit_recording_qualification_failed"}', file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
