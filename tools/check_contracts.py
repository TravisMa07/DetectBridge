"""Validate local contracts and examples with redacted, stable diagnostics."""

import argparse
import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urldefrag, urlsplit

from contract_identity import event_id, record_id
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts/v1"
BASE = "urn:detectbridge:contracts:1.0.0:"
KINDS = ("raw-record", "normalized-event", "source-contract")


@dataclass(frozen=True)
class Diagnostic:
    document: str
    pointer: str
    category: str


def pointer(parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non_json_number")),
    )


class ContractValidator:
    def __init__(self, directory=CONTRACTS):
        self.directory = Path(directory)
        self.schemas: dict[str, dict] = {}
        for path in sorted(self.directory.glob("*.schema.json")):
            schema = load_json(path)
            Draft202012Validator.check_schema(schema)
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                raise ValueError("unsupported_draft")
            name = schema["$id"]
            if name in self.schemas:
                raise ValueError("duplicate_schema_id")
            self.schemas[name] = schema
        if set(self.schemas) != {BASE + k for k in (*KINDS, "common")}:
            raise ValueError("unsupported_schema_registry")
        for schema in self.schemas.values():
            self._check_refs(schema, schema["$id"])
        self.registry = Registry().with_resources(
            (name, Resource.from_contents(schema)) for name, schema in self.schemas.items()
        )

    def _check_refs(self, node, current):
        if isinstance(node, dict):
            for key in ("$ref", "$dynamicRef"):
                if key in node:
                    uri, _ = urldefrag(node[key])
                    if uri and uri not in self.schemas:
                        raise ValueError("unknown_schema_reference")
                    # Resolve fragments eagerly, even when an example never visits them.
                    registry = Registry().with_resources(
                        (name, Resource.from_contents(s)) for name, s in self.schemas.items()
                    )
                    registry.resolver(current).lookup(node[key])
            for child in node.values():
                self._check_refs(child, current)
        elif isinstance(node, list):
            for child in node:
                self._check_refs(child, current)

    def validate(self, kind, data, document="<input>", source_contract=None):
        errors = []
        if kind not in KINDS:
            return [Diagnostic(document, "", "unknown_contract_kind")]
        validator = Draft202012Validator(
            self.schemas[BASE + kind], registry=self.registry, format_checker=FormatChecker()
        )
        for error in validator.iter_errors(data):
            errors.append(
                Diagnostic(document, pointer(error.absolute_path), "schema_" + str(error.validator))
            )
        if errors:
            return sorted(set(errors), key=lambda d: (d.pointer, d.category))

        def report(path, code):
            errors.append(Diagnostic(document, path, code))

        def evidence(value, path):
            if "inline" in value:
                try:
                    raw = (
                        value["inline"].encode("utf-8")
                        if value["encoding"] == "utf-8"
                        else base64.b64decode(value["inline"], validate=True)
                    )
                except (ValueError, UnicodeError):
                    report(path + "/inline", "invalid_encoding")
                    return
                if hashlib.sha256(raw).hexdigest() != value["sha256"]:
                    report(path + "/sha256", "inline_digest_mismatch")
            else:
                try:
                    uri = value["reference"]["uri"]
                    parsed = urlsplit(uri)
                    if (
                        parsed.username is not None
                        or parsed.password is not None
                        or parsed.query
                        or parsed.fragment
                        or "@" in parsed.netloc
                    ):
                        report(path + "/reference/uri", "unsafe_evidence_reference")
                    if (
                        parsed.scheme == "urn"
                        and uri != "urn:sha256:" + value["reference"]["object_sha256"]
                    ):
                        report(path + "/reference/uri", "invalid_content_address")
                    if parsed.scheme in ("s3", "https") and not parsed.hostname:
                        report(path + "/reference/uri", "invalid_object_reference")
                    if parsed.scheme not in ("urn", "s3", "https", "file"):
                        report(path + "/reference/uri", "unsupported_evidence_scheme")
                except ValueError:
                    report(path + "/reference/uri", "unsafe_evidence_reference")

        if kind == "raw-record":
            evidence(data["evidence"], "/evidence")
            if record_id(data["source"], data["cursor"]) != data["record_id"]:
                report("/record_id", "record_identity_mismatch")
        elif kind == "normalized-event":
            db = data["detectbridge"]
            records = [r["record_id"] for r in db["evidence"]]
            if len(set(records)) != len(records):
                report("/detectbridge/evidence", "duplicate_record_membership")
            elif event_id(db["source"], records) != data["event"]["id"]:
                report("/event/id", "event_identity_mismatch")
            for index, item in enumerate(db["evidence"]):
                evidence(item["evidence"], f"/detectbridge/evidence/{index}/evidence")
            time = db["time"]
            if time["basis"] == "source":
                if (
                    time["quality"] != "valid"
                    or time.get("source_utc") != data["@timestamp"]
                    or "source_value" not in time
                ):
                    report("/detectbridge/time", "inconsistent_source_time")
            elif (
                time["quality"] == "valid"
                or "source_utc" in time
                or data["@timestamp"] != time["first_observed"]
            ):
                report("/detectbridge/time", "inconsistent_time_fallback")
            if (
                time["quality"] in ("unparseable", "timezone_ambiguous")
                and "source_value" not in time
            ):
                report("/detectbridge/time/source_value", "missing_original_time")
            if "created" in data["event"] and data["event"]["created"] != time["first_observed"]:
                report("/event/created", "first_observed_mismatch")
            quality = db["quality"]
            if quality["integrity"] == "insufficient" and quality["eligibility"] != "skipped":
                report("/detectbridge/quality", "insufficient_integrity_must_skip")
            if quality["eligibility"] == "eligible" and quality["integrity"] != "sufficient":
                report("/detectbridge/quality", "eligibility_without_integrity")
            if quality["eligibility"] == "skipped" and not quality["diagnostics"]:
                report("/detectbridge/quality", "skip_reason_required")
            if (
                db["assembly"]["quality"] in ("known_missing", "conflicting")
                and quality["integrity"] != "insufficient"
            ):
                report("/detectbridge/quality", "assembly_integrity_mismatch")
            if db["assembly"]["mode"] == "standalone" and (
                len(records) != 1 or db["assembly"]["closure"] != "not_required"
            ):
                report("/detectbridge/assembly", "standalone_membership_mismatch")
            if source_contract is None:
                report("/detectbridge/source_contract", "source_contract_required")
            else:
                sc = source_contract
                if self.validate("source-contract", sc, document):
                    report("/detectbridge/source_contract", "invalid_source_contract")
                    return errors
                if db["source_contract"] != {"id": sc["id"], "version": sc["version"]}:
                    report("/detectbridge/source_contract", "source_contract_mismatch")
                for name, expected in sc["classification"].items():
                    if data["event"][name] != expected:
                        report("/event/" + name, "source_classification_mismatch")
                for name in sc["required_fields"] + (["host.id"] if sc["requires_host_id"] else []):
                    node = data
                    for part in name.split("."):
                        node = node.get(part) if isinstance(node, dict) else None
                    if node is None and quality["eligibility"] != "skipped":
                        report("/" + name.replace(".", "/"), "required_source_field_missing")
                blocking = set(sc["quality_policy"]["blocking_codes"])
                if (
                    any(d["code"] in blocking for d in quality["diagnostics"])
                    and quality["eligibility"] != "skipped"
                ):
                    report("/detectbridge/quality", "blocking_diagnostic_must_skip")
        elif kind == "source-contract":
            event_properties = self.schemas[BASE + "normalized-event"]["properties"]
            paths = data["required_fields"] + [
                mapping["target_path"] for mapping in data["mappings"]
            ]
            for name in paths:
                properties = event_properties
                valid = name.split(".")[0] not in ("detectbridge", "source_fields")
                for part in name.split("."):
                    field = properties.get(part)
                    if field is None:
                        valid = False
                        break
                    properties = field.get("properties", {})
                if not valid:
                    report("/mappings", "unknown_ecs_target")
            policy = data["quality_policy"]
            if set(policy["blocking_codes"]) & set(policy["warning_codes"]):
                report("/quality_policy", "ambiguous_quality_policy")
        return sorted(set(errors), key=lambda d: (d.pointer, d.category))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--document", type=Path)
    parser.add_argument("--source-contract", type=Path)
    args = parser.parse_args()
    errors = []
    try:
        validator = ContractValidator()
        if args.document:
            if not args.kind:
                parser.error("--document requires --kind")
            sc = load_json(args.source_contract) if args.source_contract else None
            if sc is not None:
                errors += validator.validate("source-contract", sc, str(args.source_contract))
            if not errors:
                errors += validator.validate(
                    args.kind, load_json(args.document), str(args.document), sc
                )
        else:
            index = load_json(CONTRACTS / "examples/index.json")
            profiles = {}
            for entry in index:
                if entry["kind"] == "source-contract":
                    data = load_json(CONTRACTS / "examples" / entry["path"])
                    errors += validator.validate(entry["kind"], data, entry["path"])
                    profiles[(data["id"], data["version"])] = data
            for entry in index:
                if entry["kind"] == "source-contract":
                    continue
                data = load_json(CONTRACTS / "examples" / entry["path"])
                sc = None
                if entry["kind"] == "normalized-event":
                    link = data["detectbridge"]["source_contract"]
                    sc = profiles.get((link["id"], link["version"]))
                errors += validator.validate(entry["kind"], data, entry["path"], sc)
            for sc in profiles.values():
                for fixture in sc["fixtures"]:
                    path = CONTRACTS / "examples" / fixture["path"]
                    data = load_json(path)
                    errors += validator.validate("normalized-event", data, fixture["path"], sc)
                    q = data["detectbridge"]["quality"]
                    if (
                        q["integrity"] != fixture["expected_integrity"]
                        or q["eligibility"] != fixture["expected_eligibility"]
                    ):
                        errors.append(
                            Diagnostic(
                                fixture["path"],
                                "/detectbridge/quality",
                                "fixture_expectation_mismatch",
                            )
                        )
    except Exception:
        # Errors can contain event values; never print the exception text.
        errors.append(
            Diagnostic(str(args.document or CONTRACTS), "", "invalid_document_or_registry")
        )
    for error in errors:
        print(json.dumps(asdict(error), sort_keys=True))
    if not errors:
        print("PASS: local contract schemas, source contracts and examples")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
