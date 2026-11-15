"""Closed P10 mapping/provenance contracts; declarations never execute source code."""

import hashlib
import json
from pathlib import Path

from check_contracts import ContractValidator, StrictValidator, load_json
from jsonschema import FormatChecker
from referencing import Resource

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "contracts/detection/v2"
MAPPING = {
    "Image": "process.executable",
    "CommandLine": "process.command_line",
    "ProcessId": "process.pid",
    "User": "user.name",
}
TRANSFORMS = {
    "identity-string/1.0.0": "string",
    "windows-account/1.0.0": "string",
    "decimal-integer/1.0.0": "integer",
    "hex-integer/1.0.0": "integer",
}


class CompileError(ValueError):
    """Only fixed categories may leave compilation."""


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def content_hash(value):
    return sha(encoded({k: v for k, v in value.items() if k != "sha256"}))


def require_schema(kind, value):
    schemas = [load_json(p) for p in DIRECTORY.glob("*.schema.json")]
    registry = ContractValidator().registry.with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas
    )
    schema = load_json(DIRECTORY / (kind + ".schema.json"))
    if next(
        StrictValidator(schema, registry=registry, format_checker=FormatChecker()).iter_errors(
            value
        ),
        None,
    ):
        raise CompileError("invalid_" + kind.replace("-", "_"))


def validate_profiles(profiles, sources):
    if not isinstance(profiles, list) or len(profiles) != len(sources):
        raise CompileError("mapping_source_set")
    snapshots = {(s["id"], s["version"]): s for s in sources}
    seen, ids = set(), set()
    for profile in profiles:
        require_schema("mapping-profile", profile)
        ref = profile["source"]
        key = (ref["id"], ref["version"])
        if key in seen or profile["id"] in ids or key not in snapshots:
            raise CompileError("mapping_source_set")
        seen.add(key)
        ids.add(profile["id"])
        source = snapshots[key]
        if ref["sha256"] != sha(encoded(source)) or profile["sha256"] != content_hash(profile):
            raise CompileError("mapping_hash_mismatch")
        aliases = set()
        for field in profile["fields"]:
            alias = field["alias"]
            if alias in aliases:
                raise CompileError("duplicate_mapping_alias")
            aliases.add(alias)
            target = MAPPING[alias]
            expected = "integer" if alias == "ProcessId" else "string"
            if (
                field["target"] != target
                or field["type"] != expected
                or TRANSFORMS[field["transform"]] != expected
                or (field["transform"] == "windows-account/1.0.0" and alias != "User")
            ):
                raise CompileError("mapping_type_or_target")
            declarations = [
                m
                for m in source["mappings"]
                if m["target_path"] == target and m["source_path"] == field.get("source_path")
            ]
            if field["capability"] == "unsupported":
                if "source_path" in field:
                    raise CompileError("unsupported_mapping_path")
            elif len(declarations) != 1 or declarations[0]["capability"] != field["capability"]:
                raise CompileError("mapping_capability_conflict")
        if aliases != set(MAPPING):
            raise CompileError("incomplete_mapping_aliases")
    return sorted(profiles, key=lambda p: (p["source"]["id"], p["source"]["version"]))


def validate_provenance(provenance, identity, revision, document):
    require_schema("candidate-provenance", provenance)
    if provenance["rule_id"] != identity or provenance["revision"] != revision:
        raise CompileError("candidate_identity_mismatch")
    current = provenance["original_sha256"]
    for change in provenance["modifications"]:
        if change["input_sha256"] != current or change["input_sha256"] == change["output_sha256"]:
            raise CompileError("candidate_lineage_mismatch")
        current = change["output_sha256"]
    if current != revision:
        raise CompileError("candidate_lineage_mismatch")
    if document.get("license") not in (None, provenance["license"]):
        raise CompileError("candidate_license_mismatch")
    if document.get("author") not in (None, *provenance["authors"]):
        raise CompileError("candidate_author_mismatch")
    if provenance["kind"] == "synthetic" and provenance["license"] != "Apache-2.0":
        raise CompileError("synthetic_license_mismatch")
