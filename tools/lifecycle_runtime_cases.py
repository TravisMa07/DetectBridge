"""Frozen independent P15b source cases, literal decisions and static packet checks."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts/lifecycle-runtime/v1/fixtures"
WORKERS = (
    "71500000-0000-4000-8000-000000000020",
    "71500000-0000-4000-8000-000000000021",
)
AUTHORITY = "71500000-0000-4000-8000-000000000010"
DEPLOYMENT = "71500000-0000-4000-8000-000000000011"


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(encoded(value))


def identity(value):
    return "sha256:" + digest(value)


def require(condition, category):
    if not condition:
        raise ValueError("lifecycle_oracle_" + category)


def document(path):
    return json.loads(Path(path).read_bytes())


def packet(name):
    return document(FIXTURES / (name + ".json"))


def phase_cases(number):
    """Apply only the independently frozen worker/run context substitution."""
    phase = packet("expectations")["rollback"]["phases"][number - 1]
    cases = {row["id"]: row for row in packet("source-cases")["cases"]}
    result = []
    for reference in phase["cases"]:
        case = copy.deepcopy(cases[reference["case_id"]])
        for row in case["admissions"]:
            row["context"]["run_id"] = reference["run_id"]
            require(digest(row["context"]) == reference["context_sha256"], "phase_context")
        case.update(run_id=reference["run_id"], phase=number, bundle=phase["selected_bundle"])
        result.append(case)
    return result


def check_packet():
    """Check original contracts/hashes/lineage/vectors without compiling or executing."""
    import yaml
    from check_contracts import StrictValidator
    from check_integration import registry
    from detection_mapping import validate_provenance
    from jsonschema import FormatChecker
    from referencing import Resource

    schemas, resources = registry()
    for path in (ROOT / "contracts/integration/v1").glob("*.schema.json"):
        value = document(path)
        schemas[value["$id"]] = value
        resources = resources.with_resource(value["$id"], Resource.from_contents(value))
    source_validator = StrictValidator(
        schemas["urn:detectbridge:integration-runtime:1.0.0:input"],
        registry=resources,
        format_checker=FormatChecker(),
    )
    compact_validator = StrictValidator(
        schemas["urn:detectbridge:integration:1.0.0:compact-evaluation"],
        registry=resources,
        format_checker=FormatChecker(),
    )
    references = packet("source-references")
    for family in references["sources"]:
        for role in ("source", "mapping"):
            ref = family[role]
            data = (ROOT / ref["path"]).read_bytes()
            require(
                len(data) == ref["bytes"]
                and sha(data) == ref["file_sha256"]
                and digest(json.loads(data)) == ref["canonical_sha256"],
                "source_reference",
            )
    provenance = packet("provenance")
    for path, entry in provenance["rules"].items():
        data = (FIXTURES / path).read_bytes()
        require(sha(data) == entry["revision"], "rule_revision")
        validate_provenance(entry, entry["rule_id"], entry["revision"], yaml.safe_load(data))
        original = (ROOT / entry["path"]).read_bytes()
        require(sha(original) == entry["original_sha256"], "original_rule")
    sources = packet("source-cases")["cases"]
    require(len(sources) == 4, "case_count")
    admissions = 0
    for case in sources:
        require(
            sha((ROOT / case["basis"]["path"]).read_bytes()) == case["basis"]["file_sha256"],
            "source_basis",
        )
        ids = []
        for row in case["admissions"]:
            source_validator.validate(row)
            raw = row["raw"]
            admissions += 1
            require(
                sha(raw["evidence"]["inline"].encode("utf-8")) == raw["evidence"]["sha256"],
                "evidence_hash",
            )
            scope = raw["source"]
            require(
                raw["record_id"]
                == identity(
                    [scope["namespace"], scope["instance"], ["native", raw["cursor"]["value"]]]
                ),
                "raw_identity",
            )
            ids.append(raw["record_id"])
        scope = case["admissions"][0]["raw"]["source"]
        require(sorted(ids) == case["expected"]["member_ids"], "member_ids")
        require(
            identity([scope["namespace"], scope["instance"], sorted(ids)])
            == case["expected"]["event_id"],
            "event_identity",
        )
    require(admissions == 14, "admission_count")
    expected = packet("expectations")
    for row in expected["cases"]:
        for outcome in row["bundles"].values():
            compact_validator.validate(outcome)
    runs: dict[str, str] = {}
    for number in (1, 2, 3):
        for case in phase_cases(number):
            require(
                case["run_id"] not in runs or runs[case["run_id"]] == case["worker_id"], "run_owner"
            )
            runs[case["run_id"]] = case["worker_id"]
    require(len(runs) == 6 and set(runs.values()) == set(WORKERS), "routing")
    for vector in packet("identity-vectors")["vectors"]:
        require(
            encoded(vector["preimage"]).decode() == vector["canonical_utf8"]
            and identity(vector["preimage"]) == vector["output_id"],
            "identity_vector",
        )
    bindings = packet("binding-vectors")
    limits = document(ROOT / "contracts/lifecycle-runtime/v1/common.schema.json")["$defs"][
        "limits"
    ]["const"]
    byname = {}
    for vector in bindings["vectors"]:
        require(
            encoded(vector["preimage"]).decode() == vector["canonical_utf8"]
            and digest(vector["preimage"]) == vector["sha256"],
            "binding_vector",
        )
        if vector["binding_kind"] == "runtime":
            require(vector["preimage"]["limits"] == limits, "binding_limits")
        byname[vector["name"]] = vector
    for pair in bindings["required_comparisons"]:
        require(
            (byname[pair["left"]]["sha256"] == byname[pair["right"]]["sha256"]) == pair["equal"],
            "binding_isolation",
        )
    totals = expected["core_schedule_totals"]
    require(
        totals["per_phase"]["source_output_envelopes"] == 14 + 4 + 2 + 2
        and totals["all_three_phases"]["source_output_envelopes"] == 66,
        "core_arithmetic",
    )
    return dict(
        status="passed",
        scope="static contracts and independent oracles only",
        source_admissions=14,
        compact_outcomes=8,
        phase_runs=6,
        identity_vectors=5,
        binding_vectors=9,
    )


def prepare(folder):
    """Compile frozen originals with the existing compiler; never infer expectations."""
    from detection_compile import compile_rules
    from lifecycle_validation import bundle

    check_packet()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    refs = packet("source-references")["sources"]
    sources = [document(ROOT / ref["source"]["path"]) for ref in refs]
    mappings = [document(ROOT / ref["mapping"]["path"]) for ref in refs]
    provenance = packet("provenance")["rules"]
    result = {}
    for name in ("A", "B"):
        paths = ["rules/" + name.lower() + "-" + kind + ".yml" for kind in ("windows", "linux")]
        plan = compile_rules(
            [FIXTURES / path for path in paths],
            sources,
            mappings=mappings,
            provenance=[provenance[path] for path in paths],
        )
        data = encoded(plan)
        manifest = bundle(data)
        destination = folder / name
        destination.mkdir()
        (destination / "plan.json").write_bytes(data)
        (destination / "manifest.json").write_bytes(encoded(manifest))
        # Candidate testing is normalized-only. Exact runtime source expectations stay frozen.
        windows = document(ROOT / "packages/windows-adapters/profiles/security.expected.json")
        linux = document(
            ROOT
            / "packages/linux-adapters/contracts/linux-audit-execution-p12a.contract-example.event.json"
        )
        cases = []
        literal = {row["case_id"]: row["bundles"][name] for row in packet("expectations")["cases"]}
        for cid, value in (
            ("security-alice", "Alice"),
            ("security-bob", "Bob"),
            ("audit-whoami", "/usr/bin/whoami"),
            ("audit-false", "/bin/false"),
        ):
            event = copy.deepcopy(windows if cid.startswith("security") else linux)
            if cid.startswith("security"):
                event["user"]["name"] = value
            else:
                event["process"]["executable"] = value
            cases.append(dict(id=cid, event=event, expected=copy.deepcopy(literal[cid])))
        suite = folder / (name + "-suite.json")
        suite.write_bytes(encoded(dict(version="1.0.0", cases=cases)))
        result[name] = dict(
            directory=destination, plan=plan, plan_bytes=data, manifest=manifest, suite=suite
        )
    require(
        result["A"]["manifest"]["compatibility_sha256"]
        == result["B"]["manifest"]["compatibility_sha256"],
        "bundle_compatibility",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(check_packet(), sort_keys=True))


def semantic_body(kind, body):
    result = copy.deepcopy(body)
    if kind == "tagged":
        event = result["event"]
        event["event"].pop("ingested", None)
        for field in ("received", "processed"):
            event["detectbridge"]["time"].pop(field, None)
        context = (
            event["detectbridge"].get("extensions", {}).get("linux.context", {}).get("context", {})
        )
        context.pop("receipt", None)
    if kind in ("tagged", "detection") and result.get("manifest") is not None:
        result["manifest"] = dict(semantic_sha256=result["manifest"]["semantic_sha256"])
    return result


def output_id(envelope):
    return identity(
        [
            "detectbridge.p15b.output/1",
            *[
                envelope[k]
                for k in (
                    "deployment_id",
                    "worker_id",
                    "revision",
                    "command_sha256",
                    "kind",
                    "inner_key",
                )
            ],
        ]
    )


def semantic_output(envelope):
    value = {
        key: envelope[key]
        for key in (
            "deployment_id",
            "worker_id",
            "origin_incarnation",
            "revision",
            "command_sha256",
            "bundle_sha256",
            "plan_sha256",
            "compatibility_sha256",
            "kind",
            "inner_key",
        )
    }
    value["document"] = semantic_body(envelope["kind"], envelope["document"])
    return digest(value)


class Oracle:
    """Input/command-bound verifier; never asks the new evaluator for expected results."""

    def __init__(self, bundles, deployment_id=DEPLOYMENT):
        self.bundles = bundles
        self.deployment_id = deployment_id
        self.events = {}
        self.receipts = {}
        self.seen = {}
        self.observed = {}
        self.legacy = {}
        self.expected_bodies = {}
        self.expected_kinds = dict(tagged=0, detection=0, manifest=0, receipt=0)

    def add(
        self,
        case,
        bundle_name,
        publication,
        registration,
        receipts,
        worker_binding,
        receipt_states=None,
    ):
        from integration_oracle import Oracle as LegacyOracle

        rows = case["admissions"]
        run = rows[0]["context"]["run_id"]
        event_id = case["expected"]["event_id"]
        require(len(rows) == len(receipts), "admission_receipts")
        for index, (row, receipt) in enumerate(zip(rows, receipts, strict=True)):
            require(receipt["value_sha256"] == sha(encoded(row)), "admission_wire")
            key = (case["worker_id"], receipt["topic_id"], receipt["offset"])
            require(key not in self.receipts, "admission_duplicate")
            receipt_bundle, receipt_publication, receipt_registration = (
                receipt_states[index]
                if receipt_states is not None
                else (bundle_name, publication, registration)
            )
            self.receipts[key] = dict(
                row=copy.deepcopy(row),
                receipt=receipt,
                worker_binding=worker_binding,
                publication=receipt_publication,
                registration=receipt_registration,
                bundle_name=receipt_bundle,
            )
        literal = next(
            row["bundles"][bundle_name]
            for row in packet("expectations")["cases"]
            if row["case_id"] == case["id"]
        )
        plan = self.bundles[bundle_name]["plan"]
        old = LegacyOracle({}, "0" * 64, plan)
        if rows[0]["kind"] == "windows_record":
            old.event(rows[0], "windows")
            expected = old.events[(run, event_id)]
            if case["expected"]["user_name"] == "Bob":
                expected["literal_overrides"] = {
                    "/user/name": "Bob",
                    "/source_fields/SubjectUserName": "Bob",
                }
        else:
            exe = case["expected"]["executable"]
            native_manifest = old.native.group(
                rows,
                execution=dict(
                    executable=exe,
                    args=case["expected"]["args"],
                    pid=42,
                    cwd="/tmp",
                    paths=[dict(item=0, name=exe), dict(item=1, name="/lib/ld.so")],
                ),
            )
            old.events[(run, event_id)] = dict(
                rows=copy.deepcopy(rows), scenario="audit", manifest=native_manifest
            )
            expected = old.events[(run, event_id)]
            self.expected_bodies[
                (case["worker_id"], "manifest", native_manifest["manifest_id"])
            ] = native_manifest
        expected["counts"] = literal["counts"]
        expected["match_ids"] = [m["id"] for m in literal["matched"]]
        self.events[(run, event_id)] = dict(
            case=case,
            bundle_name=bundle_name,
            publication=publication,
            registration=registration,
            legacy=old,
            expected=expected,
        )
        self.expected_kinds["tagged"] += 1
        self.expected_kinds["receipt"] += len(rows)
        self.expected_kinds["manifest"] += int(rows[0]["kind"] == "record")
        self.expected_kinds["detection"] += literal["counts"]["matched"]

    def _attribution(self, envelope, expected):
        bundle = self.bundles[expected["bundle_name"]]
        publication, registration = expected["publication"], expected["registration"]
        require(
            envelope["deployment_id"] == self.deployment_id
            and envelope["worker_id"] == registration["worker_id"]
            and envelope["origin_incarnation"] == registration["incarnation"],
            "worker_attribution",
        )
        require(
            envelope["revision"] == publication["revision"]
            and envelope["command_sha256"] == publication["command_sha256"],
            "actual_command",
        )
        require(
            envelope["bundle_sha256"] == bundle["manifest"]["bundle_sha256"]
            and envelope["plan_sha256"] == sha(bundle["plan_bytes"])
            and envelope["compatibility_sha256"] == bundle["manifest"]["compatibility_sha256"],
            "actual_bundle",
        )

    def check(self, records, complete=False):
        import base64

        from integration_oracle import FIELDS
        from linux_assembly_verify import transport_id

        for record in records:
            envelope = record["output"]
            body, kind = envelope["document"], envelope["kind"]
            require(envelope["output_id"] == output_id(envelope), "output_identity")
            require(
                envelope["document_sha256"] == digest(body)
                and envelope["semantic_sha256"] == semantic_output(envelope),
                "output_integrity",
            )
            require(envelope["inner_key"] == body[FIELDS[kind]], "inner_key")
            if "wire" in record:
                wire = record["wire"]
                key = wire.get("key_base64", wire.get("key"))
                require(
                    key is not None and base64.b64decode(key).decode() == envelope["output_id"],
                    "kafka_key",
                )
                require(
                    record.get("wire_sha256", wire["value_sha256"]) == sha(encoded(envelope)),
                    "wire_hash",
                )
            oid = envelope["output_id"]
            if oid in self.seen:
                require(self.seen[oid] == envelope, "immutable_duplicate")
            if kind == "tagged":
                event = body["event"]
                logical = (event["detectbridge"]["run_id"], event["event"]["id"])
                require(logical in self.events, "unexpected_event")
                expected = self.events[logical]
                self._attribution(envelope, expected)
                old = expected["legacy"]
                tagged, detections, diagnostics = old.expected_tag(event, expected["expected"])
                require(body == tagged and not diagnostics, "literal_decision")
                for doc in detections:
                    self.expected_bodies[
                        (envelope["worker_id"], "detection", doc["detection_id"])
                    ] = doc
                if expected["case"]["admissions"][0]["kind"] == "record":
                    native = old.native_wire(
                        "event",
                        dict(
                            headers={
                                "detectbridge.runtime.binding": "0" * 64,
                                "detectbridge.intent.sequence": "0",
                            }
                        ),
                        event,
                        event["event"]["id"],
                    )
                    require(old.native.check([native], complete=False), "native_source")
            elif kind == "receipt":
                physical = body["input"]
                key = (envelope["worker_id"], physical["topic_id"], physical["offset"])
                require(key in self.receipts, "unexpected_receipt")
                expected = self.receipts[key]
                self._attribution(envelope, expected)
                ack = expected["receipt"]
                location = {
                    k: ack[k]
                    for k in (
                        "cluster_id",
                        "topic_id",
                        "topic",
                        "partition",
                        "offset",
                        "value_sha256",
                    )
                }
                require(
                    physical == location
                    and body["id"] == transport_id(expected["worker_binding"], location, "receipt"),
                    "receipt_location",
                )
                require(
                    body["action"] == expected["row"]["kind"]
                    and body["record_id"] == expected["row"]["raw"]["record_id"],
                    "receipt_source",
                )
            elif kind == "manifest":
                key = (envelope["worker_id"], kind, envelope["inner_key"])
                require(
                    key in self.expected_bodies and body == self.expected_bodies[key],
                    "manifest_membership",
                )
                expected = self.events[(body["key"]["run_id"], body["event_id"])]
                self._attribution(envelope, expected)
            elif kind == "detection":
                expected = self.events.get((body["run_id"], body["event_id"]))
                require(expected is not None, "unexpected_detection")
                self._attribution(envelope, expected)
            else:
                require(False, "unexpected_core_kind")
            self.seen[oid] = copy.deepcopy(envelope)
            self.observed[(envelope["worker_id"], kind, envelope["inner_key"])] = body
        for key, expected in self.expected_bodies.items():
            if key in self.observed:
                require(self.observed[key] == expected, "derived_document")
        counts = {
            kind: sum(row["kind"] == kind for row in self.seen.values())
            for kind in self.expected_kinds
        }
        finished = counts == self.expected_kinds and all(
            key in self.observed for key in self.expected_bodies
        )
        if complete:
            require(finished, "incomplete_outputs")
        return finished
