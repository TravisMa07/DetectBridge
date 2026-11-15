"""Independently verify recorded P11 output accounting; no telemetry values in reports."""

import argparse
import base64
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_contracts import ContractValidator  # noqa: E402
from detection_mapping import require_schema, validate_profiles  # noqa: E402


def require(condition):
    if not condition:
        raise ValueError("qualification_mismatch")


def qualify(input_path, output_path, plan_path, expected_counts=None, objects=None):
    plan = json.loads(plan_path.read_bytes())
    require_schema("plan", plan)
    validate_profiles(plan["mapping_profiles"], plan["sources"])
    validator = ContractValidator()

    def canonical(v):
        return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    def identity(v):
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest()
        )

    mapping_hash = hashlib.sha256(canonical(plan["mapping_profiles"])).hexdigest()
    counts = Counter()
    retained = {}

    def evidence(raw):
        e = raw["evidence"]
        if "inline" in e:
            data = (
                e["inline"].encode("utf-8")
                if e["encoding"] == "utf-8"
                else base64.b64decode(e["inline"], validate=True)
            )
        else:
            r = e["reference"]
            digest = r["object_sha256"]
            if digest not in retained:
                require(objects is not None and len(retained) < 2)
                require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest))
                payload = (objects / digest).read_bytes()
                require(
                    len(payload) <= 32 * 1024 * 1024
                    and hashlib.sha256(payload).hexdigest() == digest
                )
                retained[digest] = payload
            payload = retained[digest]
            offset, length = r["byte_range"]["offset"], r["byte_range"]["length"]
            require(0 <= offset < len(payload) and 0 < length <= len(payload) - offset)
            require(offset == 0 or payload[offset - 1] == 10)
            require(raw["cursor"]["artifact_sha256"] == digest)
            require(raw["cursor"]["position"] == payload.count(b"\n", 0, offset))
            data = payload[offset : offset + length]
        require(hashlib.sha256(data).hexdigest() == e["sha256"])
        return data

    with input_path.open("rb") as inputs, output_path.open("rb") as outputs:
        for index, pair in enumerate(zip_longest(inputs, outputs)):
            original, published = pair
            require(original is not None and published is not None)
            expected = json.loads(original)
            actual = json.loads(published)
            require(actual["version"] == "1.0.0")
            require(actual["raw"] == expected["raw"] and actual["context"] == expected["context"])
            raw, context = expected["raw"], expected["context"]
            require("host_binding" not in context)
            require(("event" in actual) != ("preservation" in actual))
            require(not validator.validate("raw-record", raw))
            original_xml = ET.fromstring(evidence(raw))
            ns = "{http://schemas.microsoft.com/win/2004/08/events/event}"
            system = original_xml.find(ns + "System")
            require(system is not None)
            family = context["source_contract"]["id"]
            signatures = {
                "windows-security-4688-xml": (
                    "Microsoft-Windows-Security-Auditing",
                    "Security",
                    "4688",
                    "2",
                ),
                "windows-sysmon-process-xml": (
                    "Microsoft-Windows-Sysmon",
                    "Microsoft-Windows-Sysmon/Operational",
                    "1",
                    "5",
                ),
            }
            require(family in signatures)
            signature = (
                system.find(ns + "Provider").attrib.get("Name"),
                system.findtext(ns + "Channel"),
                system.findtext(ns + "EventID"),
                system.findtext(ns + "Version"),
            )
            supported = signature == signatures[family]
            counts["records"] += 1
            if "preservation" in actual:
                require(not supported)
                require(set(actual) == {"version", "raw", "context", "preservation"})
                diagnostic = actual["preservation"]
                require(
                    diagnostic
                    == dict(
                        version="1.0.0",
                        record_id=raw["record_id"],
                        run_id=context["run_id"],
                        evidence_sha256=raw["evidence"]["sha256"],
                        code="unsupported_source",
                        reason="source_signature",
                        field="",
                    )
                )
                require("evaluation" not in actual)
                counts["unsupported"] += 1
            else:
                require(supported)
                require(set(actual) == {"version", "raw", "context", "event", "evaluation"})
                fields = {
                    d.attrib["Name"]: d.text or "" for d in original_xml.find(ns + "EventData")
                }
                event = actual["event"]
                require(
                    not validator.validate(
                        "normalized-event",
                        event,
                        source_contract=context["source_contract"]["snapshot"],
                    )
                )
                security = context["source_contract"]["id"] == "windows-security-4688-xml"
                require(event["event"]["code"] == ("4688" if security else "1"))
                require(
                    event["process"]["executable"]
                    == fields["NewProcessName" if security else "Image"]
                )
                require(
                    event["process"]["pid"]
                    == int(
                        fields["NewProcessId" if security else "ProcessId"], 16 if security else 10
                    )
                )
                require(event["process"]["command_line"] == fields["CommandLine"])
                require(
                    event["user"]["name"]
                    == (fields["SubjectUserName"] if security else fields["User"].split("\\")[-1])
                )
                for name, value in fields.items():
                    require(event["source_fields"][name] == value)

                db = event["detectbridge"]
                source_time = (
                    original_xml.find(ns + "System").find(ns + "TimeCreated").attrib["SystemTime"]
                    if security
                    else fields["UtcTime"]
                )
                source_utc = source_time if security else source_time.replace(" ", "T") + "Z"
                require(db["time"]["source_value"] == source_time)
                require(db["time"]["basis"] == "source" and db["time"]["quality"] == "valid")
                require(
                    event["@timestamp"] == source_utc and db["time"]["source_utc"] == source_utc
                )
                require(
                    event["host"]["name"]
                    == original_xml.find(ns + "System").findtext(ns + "Computer")
                )

                preimage = json.dumps(
                    [raw["source"]["namespace"], raw["source"]["instance"], [raw["record_id"]]],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
                require(event["event"]["id"] == "sha256:" + hashlib.sha256(preimage).hexdigest())
                require(db["source"] == raw["source"] and db["run_id"] == context["run_id"])
                require(
                    db["source_contract"]
                    == {k: context["source_contract"][k] for k in ("id", "version")}
                )
                require(
                    db["evidence"] == [dict(record_id=raw["record_id"], evidence=raw["evidence"])]
                )
                require(db["time"]["first_observed"] == raw["first_observed"])
                require(
                    db["quality"]["integrity"] == "insufficient"
                    and db["quality"]["eligibility"] == "skipped"
                )
                require(
                    dict(code="identity_missing", field="/host/id") in db["quality"]["diagnostics"]
                )
                require("id" not in event.get("host", {}))
                require(
                    db["processing"]
                    == dict(
                        parser="windows-xml/1.0.0",
                        normalizer="windows-normalizer/1.0.0",
                        mapping=context["mapping_profile"]["id"] + "/1.0.0",
                    )
                )
                evaluation = actual["evaluation"]
                require_schema("result", evaluation)
                require(
                    evaluation["input"]
                    == dict(
                        cluster_id="offline",
                        topic_id="offline",
                        topic="windows-offline",
                        partition=0,
                        offset=index,
                        value_sha256=hashlib.sha256(
                            json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
                        ).hexdigest(),
                    )
                )
                require(
                    evaluation["version"] == "2.0.0"
                    and evaluation["event_id"] == event["event"]["id"]
                    and evaluation["run_id"] == context["run_id"]
                )
                # Literal P11 rules: three applicable Windows rules, one Linux rule.
                require(
                    evaluation["counts"]
                    == dict(
                        matched=0,
                        unmatched=0,
                        inapplicable=1,
                        configuration_blocked=0,
                        quality_skipped=3,
                        evaluation_error=0,
                    )
                )
                require(evaluation["matched"] == [])
                require(evaluation["bundle_sha256"] == plan["bundle_sha256"])
                require(evaluation["mapping_sha256"] == mapping_hash)
                for key in ("compiler", "evaluator", "mapping_version"):
                    require(evaluation[key] == plan[key])
                require(
                    evaluation["result_id"]
                    == identity([event["event"]["id"], context["run_id"], plan["bundle_sha256"]])
                )
                require(
                    evaluation["diagnostics"]
                    == [
                        dict(
                            rule_id="71100000-0000-4000-8000-00000000000" + str(n),
                            category="quality_skipped",
                            pointer="",
                        )
                        for n in (1, 2, 4)
                    ]
                )
                require(evaluation["input"]["offset"] == index)
                counts["supported_skipped"] += 1
    require(
        counts
        == Counter(expected_counts or dict(records=7018, unsupported=6657, supported_skipped=361))
    )
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("objects", type=Path)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                qualify(args.input, args.output, args.plan, objects=args.objects), sort_keys=True
            )
        )
    except Exception:
        print('{"category":"windows_recorded_qualification_failure"}', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
