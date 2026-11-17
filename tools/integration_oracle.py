"""Independent P13 counts, identities, source/manifest semantics and Kafka accounting."""

import base64
import copy
import hashlib
from typing import Any

from check_contracts import load_json
from check_integration import validate
from integration import INPUT
from integration_cases import ROOT, digest, encoded
from linux_assembly_verify import Oracle as SourceOracle
from linux_assembly_verify import require, transport_id

FIELDS = dict(
    tagged="processing_id",
    detection="detection_id",
    processing="diagnostic_id",
    manifest="manifest_id",
    preservation="preservation_id",
    quarantine="id",
    receipt="id",
)
POLICY = dict(
    id="coverage-and-rule-metadata",
    version="1.0.0",
    tags=["nonzero-coverage-in-outcome-order", "quality-eligibility"],
    rule_metadata="plan-without-yaml-and-expression",
    external_inputs=[],
)


def identity(preimage):
    return "sha256:" + digest(preimage)


def semantic_event(event):
    result = copy.deepcopy(event)
    result["event"].pop("ingested", None)
    for key in ("received", "processed"):
        result["detectbridge"]["time"].pop(key, None)
    context = (
        result["detectbridge"].get("extensions", {}).get("linux.context", {}).get("context", {})
    )
    context.pop("receipt", None)
    return result


def manifest_ref(manifest):
    if manifest is None:
        return None
    semantic = copy.deepcopy(manifest)
    semantic.pop("manifest_id")
    for member in semantic["members"]:
        member.pop("context_sha256")
    return dict(
        manifest_id=manifest["manifest_id"],
        sha256=digest(manifest),
        semantic_sha256=digest(semantic),
    )


class Oracle:
    def __init__(self, config, binding, plan):
        self.config, self.binding, self.plan = config, binding, plan
        self.native = SourceOracle(config, binding)
        self.inputs, self.events, self.preserves = {}, {}, {}
        self.expected = load_json(
            ROOT / "contracts/integration-runtime/v1/fixtures/expectations.json"
        )

    def event(self, row, scenario):
        run = row["context"]["run_id"]
        event_id = identity(
            [
                row["raw"]["source"]["namespace"],
                row["raw"]["source"]["instance"],
                [row["raw"]["record_id"]],
            ]
        )
        self.events[(run, event_id)] = dict(
            rows=[copy.deepcopy(row)], scenario=scenario, manifest=None
        )
        if row["kind"] == "record":
            self.native.auth(row)
        return event_id

    def group(self, rows, closure="source_boundary", findings=None):
        execution = (
            None
            if findings
            else dict(
                executable="/usr/bin/whoami",
                args=["whoami", "", "whoami"],
                pid=42,
                cwd="/tmp",
                paths=[dict(item=0, name="/usr/bin/whoami"), dict(item=1, name="/lib/ld.so")],
            )
        )
        manifest = self.native.group(rows, closure, findings or [], execution=execution)
        self.events[(rows[0]["context"]["run_id"], manifest["event_id"])] = dict(
            rows=copy.deepcopy(rows),
            scenario="audit_skipped" if findings else "audit",
            manifest=manifest,
        )
        return manifest

    def preservation(self, row, code, original=None):
        self.native.diagnostic(row, code, original)

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

    def expected_tag(self, event, expected):
        rows, scenario, manifest = expected["rows"], expected["scenario"], expected["manifest"]
        ctx = rows[0]["context"]
        if rows[0]["kind"] == "windows_record":
            family = (
                "security"
                if ctx["source_contract"]["id"].startswith("windows-security")
                else "sysmon"
            )
            literal = load_json(
                ROOT / "packages/windows-adapters/profiles" / (family + ".expected.json")
            )
            literal["event"]["id"] = event["event"]["id"]
            literal["detectbridge"]["run_id"] = ctx["run_id"]
            literal["detectbridge"]["evidence"] = [
                dict(record_id=rows[0]["raw"]["record_id"], evidence=rows[0]["raw"]["evidence"])
            ]
            if scenario == "windows_skipped":
                literal["host"].pop("id")
                literal["detectbridge"]["quality"] = dict(
                    integrity="insufficient",
                    eligibility="skipped",
                    diagnostics=[dict(code="identity_missing", field="/host/id")],
                )
            if scenario == "windows_budget":
                literal["process"]["command_line"] = "x" * 65536
                literal["source_fields"]["CommandLine"] = "x" * 65536
            require(event == literal)
        context = copy.deepcopy(ctx)
        context.pop("receipt", None)
        processing = dict(
            parser=ctx["parser"]["id"] + "/" + ctx["parser"]["version"],
            mapping=ctx["mapping_profile"]["id"] + "/" + ctx["mapping_profile"]["version"],
            normalizer="windows-normalizer/1.0.0"
            if rows[0]["kind"] == "windows_record"
            else "linux-p12a/1.0.0",
        )
        require(event["detectbridge"]["processing"] == processing)
        attrs = dict(
            context_sha256=digest(context),
            pipeline="p13-runtime/1.0.0",
            bundle_sha256=self.plan["bundle_sha256"],
            source=ctx["source"],
            source_contract={k: ctx["source_contract"][k] for k in ("id", "version", "sha256")},
            mapping_profile={k: ctx["mapping_profile"][k] for k in ("id", "version", "sha256")},
            processing=processing,
            compiler="detectbridge/2.0.0",
            evaluator="detectbridge-java/2.0.0",
            mapping_version="source-mappings/1.0.0",
            selector="source-index/1.0.0",
            mapping_sha256=digest(self.plan["mapping_profiles"]),
            enrichment=dict(id=POLICY["id"], version="1.0.0", sha256=digest(POLICY)),
            external_inputs=[],
        )
        reference = manifest_ref(manifest)
        processing = identity(
            [
                "detectbridge.p13.processing/1",
                "p13-runtime/1.0.0",
                ctx["run_id"],
                event["event"]["id"],
                digest(semantic_event(event)),
                attrs,
                None if reference is None else dict(semantic_sha256=reference["semantic_sha256"]),
            ]
        )
        counts = self.expected[scenario]
        match_ids = []
        if counts["matched"]:
            match_ids = [
                "71100000-0000-4000-8000-000000000001"
                if scenario.startswith("windows")
                else "72000000-0000-4000-8000-000000000004"
                if scenario == "auth"
                else "72000000-0000-4000-8000-000000000001"
            ]
        matches, detections, diagnostics = [], [], []
        base = dict(
            version="1.1.0",
            processing_id=processing,
            event_id=event["event"]["id"],
            run_id=ctx["run_id"],
            attribution=attrs,
        )
        for rule in self.plan["rules"]:
            if rule["id"] in match_ids:
                detection = identity(
                    ["detectbridge.p13.detection/1", processing, rule["id"], rule["revision"]]
                )
                matches.append(
                    dict(id=rule["id"], revision=rule["revision"], detection_id=detection)
                )
                detections.append(
                    dict(
                        base,
                        detection_id=detection,
                        manifest=reference,
                        rule={k: v for k, v in rule.items() if k not in ("yaml", "expression")},
                    )
                )
        for category in ("configuration_blocked", "quality_skipped", "evaluation_error"):
            if not counts[category]:
                continue
            bits = (
                self.expected["audit_blocked_bits"]
                if category == "configuration_blocked"
                else self.expected["windows_error_bits"]
                if category == "evaluation_error"
                else self.expected["audit_skipped_bits"]
                if scenario == "audit_skipped"
                else "000000000000000000000000b"
            )
            rule_set = dict(
                version="bundle-bits/1.0.0",
                bundle_sha256=self.plan["bundle_sha256"],
                bits=bits,
                count=counts[category],
            )
            rule_set["sha256"] = digest(rule_set)
            diagnostics.append(
                dict(
                    base,
                    category=category,
                    rule_set=rule_set,
                    diagnostic_id=identity(
                        ["detectbridge.p13.diagnostic/1", processing, category, rule_set["sha256"]]
                    ),
                )
            )
        return (
            dict(
                version="1.1.0",
                processing_id=processing,
                event=event,
                attribution=attrs,
                manifest=reference,
                counts=counts,
                matches=matches,
                tags=["coverage:" + k for k, v in counts.items() if v]
                + ["quality:" + event["detectbridge"]["quality"]["eligibility"]],
            ),
            detections,
            diagnostics,
        )

    def check(self, outputs):
        seen: dict[tuple[str, str], bytes] = {}
        tags: dict[tuple[str, str], Any] = {}
        detections: dict[str, Any] = {}
        diagnostics: dict[str, Any] = {}
        native = []
        for kind, wire, document in outputs:
            require(
                wire["headers"]["detectbridge.runtime.binding"] == self.binding
                and wire["headers"]["detectbridge.intent.kind"] == kind
            )
            key = document[FIELDS[kind]]
            require(base64.b64decode(wire["key"]).decode() == key)
            logical = (kind, key)
            value = base64.b64decode(wire["value"])
            if logical in seen:
                require(value == seen[logical])
            seen[logical] = value
            if kind in ("tagged", "detection", "processing"):
                validate(
                    "urn:detectbridge:integration:1.1.0:"
                    + dict(tagged="tagged-event", detection="detection", processing="diagnostic")[
                        kind
                    ],
                    document,
                )
                if kind == "tagged":
                    logical_event = (
                        document["event"]["detectbridge"]["run_id"],
                        document["event"]["event"]["id"],
                    )
                    require(logical_event in self.events)
                    tags[logical_event] = document
                    if self.events[logical_event]["rows"][0]["kind"] == "record":
                        native.append(
                            self.native_wire(
                                "event", wire, document["event"], document["event"]["event"]["id"]
                            )
                        )
                elif kind == "detection":
                    detections[key] = document
                else:
                    diagnostics[key] = document
            elif kind == "manifest":
                native.append((kind, wire, document))
            elif kind == "preservation":
                validate("urn:detectbridge:integration-runtime:1.0.0:preservation", document)
                require(
                    key
                    == identity(
                        [
                            "detectbridge.p13.preservation/1",
                            document["adapter"],
                            document["source"],
                            document["diagnostic"],
                        ]
                    )
                )
                require(document["adapter"] == "linux")
                native.append(
                    self.native_wire(
                        "diagnostic", wire, document["diagnostic"], document["diagnostic"]["id"]
                    )
                )
            else:
                validate("urn:detectbridge:integration-runtime:1.0.0:" + kind, document)
                offset = document["input"]["offset"]
                require(offset in self.inputs)
                expected = self.inputs[offset]
                location = dict(
                    cluster_id=self.config["broker"]["cluster_id"],
                    topic_id=self.config["broker"]["topics"][INPUT]["id"],
                    topic=INPUT,
                    partition=0,
                    offset=offset,
                    value_sha256=expected["value_sha256"],
                )
                require(
                    document["input"] == location
                    and key
                    == transport_id(
                        self.binding, location, "receipt" if kind == "receipt" else "invalid_input"
                    )
                )
                require((kind == "receipt") == isinstance(expected["row"], dict))
                if kind == "receipt":
                    require(document["action"] == expected["row"]["kind"])
                    if "raw" in expected["row"]:
                        require(document["record_id"] == expected["row"]["raw"]["record_id"])
                else:
                    require(
                        document["value_size"] == expected["value_size"]
                        and document["value_is_null"] == expected["value_is_null"]
                    )
        self.native.check(native, complete=False)
        expected_detections: dict[str, Any] = {}
        expected_diagnostics: dict[str, Any] = {}
        for logical, tag in tags.items():
            expected_tag, det, diag = self.expected_tag(tag["event"], self.events[logical])
            require(tag == expected_tag)
            expected_detections.update((d["detection_id"], d) for d in det)
            expected_diagnostics.update((d["diagnostic_id"], d) for d in diag)
        require(set(detections) <= set(expected_detections) or len(tags) < len(self.events))
        for key, value in detections.items():
            if key in expected_detections:
                require(value == expected_detections[key])
        for key, value in diagnostics.items():
            if key in expected_diagnostics:
                require(value == expected_diagnostics[key])
        receipt_count = len({key for kind, key in seen if kind in ("receipt", "quarantine")})
        return (
            set(tags) == set(self.events)
            and detections == expected_detections
            and diagnostics == expected_diagnostics
            and receipt_count == len(self.inputs)
            and self.native.check(native, complete=True)
        )

    @staticmethod
    def native_wire(kind, wire, doc, key):
        translated = copy.deepcopy(wire)
        translated["headers"]["detectbridge.intent.kind"] = kind
        translated["key"] = base64.b64encode(key.encode()).decode()
        translated["value"] = base64.b64encode(encoded(doc)).decode()
        return kind, translated, doc
