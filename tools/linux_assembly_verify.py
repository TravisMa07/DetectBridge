"""Independent P12b byte, membership, outcome and transport accounting oracle."""

import base64
import copy
import hashlib
import re

from check_contracts import ContractValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker
from linux_assembly_cases import ROOT, digest, encoded, identity
from referencing import Registry, Resource
from stack import StackError


def require(condition):
    if not condition:
        raise StackError("assembly_independent_expectation_failed")


def transport_id(binding, location, category):
    return identity(
        [
            binding,
            location["cluster_id"],
            location["topic_id"],
            location["partition"],
            location["offset"],
            location["value_sha256"],
            category,
        ]
    )


def member(row):
    raw, context = row["raw"], row["context"]
    result = dict(
        record_id=raw["record_id"],
        evidence_sha256=raw["evidence"]["sha256"],
        encoding=raw["evidence"]["encoding"],
        media_type=raw["evidence"]["media_type"],
        retention="raw_inline",
        cursor=raw["cursor"],
        first_observed=raw["first_observed"],
        raw_sha256=digest(raw),
        context_sha256=digest(context),
    )
    if "reference" in raw["evidence"]:
        result["retention"] = "raw_reference"
        result["reference"] = raw["evidence"]["reference"]
    if len(encoded(result)) > 2048:
        result = {
            key: result[key]
            for key in ("record_id", "evidence_sha256", "raw_sha256", "context_sha256")
        }
        result["retention"] = "retained_raw"
    return result


def manifest(rows, closure, findings):
    context = rows[0]["context"]
    header = re.search(r"msg=audit\(([^:]+):([0-9]+)\)", rows[0]["raw"]["evidence"]["inline"])
    if header is None:
        raise StackError("assembly_independent_header_invalid")
    ids = sorted(row["raw"]["record_id"] for row in rows)
    event_id = identity([context["source"]["namespace"], context["source"]["instance"], ids])
    result = dict(
        version="1.0.0",
        key=dict(
            run_id=context["run_id"],
            source=context["source"],
            host_id=context["host_binding"]["host_id"],
            generation=context["source_generation"]["id"],
            audit_timestamp=header[1],
            audit_serial=header[2],
        ),
        closure=closure,
        assembler="linux-audit/1.0.0",
        policy="execution-evidence/1.0.0",
        findings=findings,
        eligible=not findings,
        source_sha256=context["source_contract"]["sha256"],
        mapping_sha256=context["mapping_profile"]["sha256"],
        scope_provenance=dict(
            host_binding=context["host_binding"], source_generation=context["source_generation"]
        ),
        members=[member(row) for row in rows],
        event_id=event_id,
    )
    result["manifest_id"] = "sha256:" + digest(result)
    return result


class Oracle:
    def __init__(self, config, binding):
        self.config, self.binding = config, binding
        self.inputs = {}
        self.groups = {}
        self.events = {}
        self.diagnostics = {}
        self.validator = ContractValidator()
        paths = [
            *(ROOT / "contracts/v1").glob("*.schema.json"),
            *(ROOT / "packages/linux-adapters/contracts").glob("*.schema.json"),
            *(ROOT / "contracts/linux-assembly/v1").glob("*.schema.json"),
        ]
        schemas = [load_json(path) for path in paths]
        self.registry = Registry().with_resources(
            (s["$id"], Resource.from_contents(s)) for s in schemas
        )
        self.schemas = {s["$id"]: s for s in schemas}
        self.physical = 0

    def group(self, rows, closure="source_boundary", findings=None):
        rows = copy.deepcopy(rows)
        expected = manifest(rows, closure, findings or [])
        run = rows[0]["context"]["run_id"]
        self.groups[(run, expected["manifest_id"])] = expected
        self.events[(run, expected["event_id"])] = dict(
            rows=rows, eligible=not expected["findings"], complete=not expected["findings"]
        )
        return expected

    def auth(self, row, outcome="success", *, expectation=None):
        raw, context = row["raw"], row["context"]
        event_id = identity(
            [raw["source"]["namespace"], raw["source"]["instance"], [raw["record_id"]]]
        )
        self.events[(context["run_id"], event_id)] = dict(
            rows=[copy.deepcopy(row)],
            eligible=True,
            auth_expectation=copy.deepcopy(expectation)
            if expectation is not None
            else dict(outcome=outcome, user="alice", source_ip="192.0.2.1", source_port=2222),
        )

    def diagnostic(self, row, code, original=None):
        raw, ctx = row["raw"], row["context"]
        result = dict(
            version="1.0.0",
            kind="preservation",
            code=code,
            run_id=ctx["run_id"],
            source=raw["source"],
            member=member(row),
            context=ctx,
            id=identity([ctx["run_id"], raw["record_id"], code]),
        )
        if original:
            result.update(
                original_manifest_id=original["manifest_id"], original_event_id=original["event_id"]
            )
        self.diagnostics[(ctx["run_id"], result["id"])] = result

    def register(self, rows, acks):
        require(len(rows) == len(acks))
        for row, ack in zip(rows, acks):
            value = row if isinstance(row, bytes) or row is None else encoded(row)
            sha = hashlib.sha256(value or b"").hexdigest()
            require(
                ack["partition"] == 0
                and ack["value_sha256"] == sha
                and ack["offset"] not in self.inputs
            )
            self.inputs[ack["offset"]] = dict(
                row=copy.deepcopy(row),
                value_sha256=sha,
                value_size=len(value or b""),
                value_is_null=value is None,
            )

    def schema(self, id, value):
        Draft202012Validator(
            self.schemas[id], registry=self.registry, format_checker=FormatChecker()
        ).validate(value)

    def check(self, outputs, *, complete=True):
        seen: dict[tuple[str, str, str], bytes] = {}
        physical = 0
        for kind, wire, document in outputs:
            physical += 1
            headers = wire["headers"]
            require(
                headers["detectbridge.runtime.binding"] == self.binding
                and headers["detectbridge.intent.kind"] == kind
            )
            require(
                re.fullmatch(r"0|[1-9][0-9]*", headers["detectbridge.intent.sequence"]) is not None
            )
            key = (
                document["event"]["id"]
                if kind == "event"
                else document["manifest_id"]
                if kind == "manifest"
                else document["id"]
            )
            run = (
                document["key"]["run_id"]
                if kind == "manifest"
                else document.get("detectbridge", {}).get("run_id", document.get("run_id", ""))
            )
            require(base64.b64decode(wire["key"]).decode() == key)
            logical = (kind, run, key)
            value = base64.b64decode(wire["value"])
            if logical in seen:
                require(seen[logical] == value)
            seen[logical] = value
            if kind == "manifest":
                self.schema("urn:detectbridge:linux:1.0.0:manifest", document)
                require((run, key) in self.groups and document == self.groups[(run, key)])
            elif kind == "diagnostic":
                self.schema("urn:detectbridge:linux:1.0.0:preservation", document)
                require((run, key) in self.diagnostics and document == self.diagnostics[(run, key)])
            elif kind == "event":
                require((run, key) in self.events)
                expected = self.events[(run, key)]
                rows = expected["rows"]
                ctx = rows[0]["context"]
                require(
                    not self.validator.validate(
                        "normalized-event",
                        document,
                        source_contract=ctx["source_contract"]["snapshot"],
                    )
                )
                db = document["detectbridge"]
                require(
                    db["quality"]["eligibility"]
                    == ("eligible" if expected["eligible"] else "skipped")
                )
                require(
                    db["source"] == ctx["source"]
                    and document["host"]["id"] == ctx["host_binding"]["host_id"]
                )
                require(
                    db["evidence"]
                    == [
                        dict(record_id=r["raw"]["record_id"], evidence=r["raw"]["evidence"])
                        for r in rows
                    ]
                )
                require(db["time"]["first_observed"] == ctx["first_observed"])
                require(
                    "command_line" not in document.get("process", {})
                    and "path" not in document.get("file", {})
                )
                if "auth_expectation" in expected:
                    auth = expected["auth_expectation"]
                    require(
                        document["event"]["outcome"] == auth["outcome"]
                        and document["user"]["name"] == auth["user"]
                    )
                    require(
                        document["source"] == dict(ip=auth["source_ip"], port=auth["source_port"])
                    )
                    if "timestamp" in auth:
                        from datetime import datetime

                        require(
                            datetime.fromisoformat(document["@timestamp"])
                            == datetime.fromisoformat(auth["timestamp"])
                        )
                        require(db["time"]["source_value"] == auth["timestamp"])
                        require(db["time"]["source_utc"] == document["@timestamp"])
                        require(
                            db["time"]["basis"] == "source" and db["time"]["quality"] == "valid"
                        )
                        require(
                            document["source_fields"]["rfc5424"]["timestamp"] == auth["timestamp"]
                        )
                    require(db["quality"]["integrity"] == "sufficient")
                    require(
                        db["source_contract"]
                        == {k: ctx["source_contract"][k] for k in ("id", "version")}
                    )
                    require(
                        db["processing"]
                        == dict(
                            parser="openssh-password/1.0.0",
                            mapping=ctx["mapping_profile"]["id"] + "/1.0.0",
                            normalizer="linux-p12a/1.0.0",
                        )
                    )
                elif expected["complete"]:
                    require(
                        document["process"]["executable"] == "/usr/bin/whoami"
                        and document["process"]["args"] == ["whoami", "", "whoami"]
                    )
                    require(
                        document["source_fields"]["paths"]
                        == [dict(item=0, name="/usr/bin/whoami"), dict(item=1, name="/lib/ld.so")]
                    )
            elif kind in ("receipt", "quarantine"):
                self.schema("urn:detectbridge:assembly:1.0.0:" + kind, document)
                location = document["input"]
                offset = location["offset"]
                require(offset in self.inputs)
                expected = self.inputs[offset]
                require(
                    location
                    == dict(
                        cluster_id=self.config["broker"]["cluster_id"],
                        topic_id=self.config["broker"]["topics"]["detectbridge.assembly.input.v1"][
                            "id"
                        ],
                        topic="detectbridge.assembly.input.v1",
                        partition=0,
                        offset=offset,
                        value_sha256=expected["value_sha256"],
                    )
                )
                category = "receipt" if kind == "receipt" else "invalid_input"
                require(key == transport_id(self.binding, location, category))
                if kind == "quarantine":
                    require(
                        not isinstance(expected["row"], dict)
                        and document["value_size"] == expected["value_size"]
                        and document["value_is_null"] == expected["value_is_null"]
                    )
                else:
                    require(
                        isinstance(expected["row"], dict)
                        and document["action"] == expected["row"]["kind"]
                    )
                    if document["action"] == "record":
                        require(document["record_id"] == expected["row"]["raw"]["record_id"])
            else:
                require(False)
        required = {
            *(("manifest", run, id) for run, id in self.groups),
            *(("diagnostic", run, id) for run, id in self.diagnostics),
            *(("event", run, id) for run, id in self.events),
        }
        for offset, expected in self.inputs.items():
            kind = "receipt" if isinstance(expected["row"], dict) else "quarantine"
            location = dict(
                cluster_id=self.config["broker"]["cluster_id"],
                topic_id=self.config["broker"]["topics"]["detectbridge.assembly.input.v1"]["id"],
                topic="detectbridge.assembly.input.v1",
                partition=0,
                offset=offset,
                value_sha256=expected["value_sha256"],
            )
            required.add(
                (
                    kind,
                    "",
                    transport_id(
                        self.binding, location, "receipt" if kind == "receipt" else "invalid_input"
                    ),
                )
            )
        require(set(seen) <= required)
        self.physical = physical
        return required <= set(seen) if complete else True
