"""Opt-in offline inventory and input preparation; reads only already-reviewed cache objects."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from datasets import process  # noqa: E402

NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def inventory(cache, output, first_observed, run_id):
    uuid.UUID(run_id)
    profiles = Path(__file__).resolve().parent / "profiles"
    report = []
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(dir=output.parent, prefix=".windows-input-")
    try:
        with os.fdopen(descriptor, "wb") as target:
            for catalog, family in [
                ("windows-security-4688", "security"),
                ("windows-sysmon-mixed", "sysmon"),
            ]:
                manifest = json.loads((ROOT / f"catalog/datasets/{catalog}.json").read_text())
                verified = process(manifest, cache=cache, fetch=False)
                artifact = manifest["payload"]["sha256"]
                payload = (cache / "objects/sha256" / artifact).read_bytes()
                source = json.loads((profiles / f"{family}.source.json").read_text())
                mapping = json.loads((profiles / f"{family}.mapping.json").read_text())
                origin = {
                    "namespace": "splunk-attack-data",
                    "instance": catalog + "/lf-byte-records-v1",
                }
                counts = dict(
                    records=0, supported=0, unsupported=0, malformed=0, supported_command_line=0
                )
                offset = 0
                # split only LF bytes; preserve CR and a final unterminated record.
                records = payload.split(b"\n")
                if records[-1] == b"":
                    records.pop()
                for position, part in enumerate(records):
                    record = part + (b"\n" if offset + len(part) < len(payload) else b"")
                    cursor = dict(kind="dataset", artifact_sha256=artifact, position=position)
                    identity = json.dumps(
                        [
                            origin["namespace"],
                            origin["instance"],
                            ["dataset", artifact, str(position)],
                        ],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode()
                    raw = dict(
                        contract_version="1.0.0",
                        record_id="sha256:" + digest(identity),
                        source=origin,
                        cursor=cursor,
                        first_observed=first_observed,
                        evidence=dict(
                            sha256=digest(record),
                            media_type="application/xml",
                            encoding="utf-8",
                            reference=dict(
                                uri="urn:sha256:" + artifact,
                                object_sha256=artifact,
                                byte_range=dict(offset=offset, length=len(record)),
                            ),
                        ),
                    )
                    context = dict(
                        version="1.0.0",
                        run_id=run_id,
                        source=origin,
                        first_observed=first_observed,
                        source_contract=dict(
                            id=source["id"],
                            version="1.0.0",
                            sha256=digest(canonical(source)),
                            snapshot=source,
                        ),
                        mapping_profile=dict(
                            id=mapping["id"],
                            version="1.0.0",
                            sha256=mapping["sha256"],
                            declaration=mapping,
                        ),
                        parser=dict(id="windows-xml", version="1.0.0"),
                    )
                    target.write(canonical(dict(raw=raw, context=context)) + b"\n")
                    offset += len(record)
                    counts["records"] += 1
                    try:
                        # Independent inventory parser only; actual admission uses hardened Java.
                        if b"<!DOCTYPE" in record or b"<!ENTITY" in record:
                            raise ValueError("declaration")
                        event = ET.fromstring(record.decode("utf-8"))
                        system = event.find(NS + "System")
                        signature = (
                            system.find(NS + "Provider").attrib.get("Name"),
                            system.findtext(NS + "EventID"),
                            system.findtext(NS + "Version"),
                            system.findtext(NS + "Channel"),
                        )
                        expected = (
                            ("Microsoft-Windows-Security-Auditing", "4688", "2", "Security")
                            if family == "security"
                            else (
                                "Microsoft-Windows-Sysmon",
                                "1",
                                "5",
                                "Microsoft-Windows-Sysmon/Operational",
                            )
                        )
                        supported = event.tag == NS + "Event" and signature == expected
                        counts["supported" if supported else "unsupported"] += 1
                        if supported:
                            data = event.find(NS + "EventData")
                            if any(d.attrib.get("Name") == "CommandLine" and d.text for d in data):
                                counts["supported_command_line"] += 1
                    except (ET.ParseError, ValueError, AttributeError, TypeError):
                        counts["malformed"] += 1
                if (
                    offset != len(payload)
                    or counts["records"] != verified["framing"]["record_count"]
                ):
                    raise ValueError("inventory_partition")
                report.append(
                    dict(
                        catalog_id=catalog,
                        artifact_sha256=artifact,
                        **counts,
                        host_binding="not_substantiated",
                    )
                )
            target.flush()
            os.fsync(target.fileno())
        os.replace(filename, output)
    finally:
        Path(filename).unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--first-observed",
        required=True,
        help="Actual immutable acquisition observation; never metadata capture date",
    )
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                inventory(args.cache, args.output, args.first_observed, args.run_id), sort_keys=True
            )
        )
    except Exception:
        print('{"category":"windows_recorded_inventory_failure"}', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
