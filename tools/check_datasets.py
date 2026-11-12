"""Offline catalog validation; no payload retrieval or event interpretation."""

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from check_contracts import load_json
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/datasets"
MAX_ARTIFACT = 32 * 1024 * 1024
MAX_BATCH = 64 * 1024 * 1024
HOSTS = {"raw.githubusercontent.com", "media.githubusercontent.com"}


def approved_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("unapproved_url")


def manifest_errors(data, schema):
    errors = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker(), registry=Registry())
    try:
        structural_errors = list(validator.iter_errors(data))
    except Exception:
        return ["invalid_catalog_schema_reference"]
    for error in structural_errors:
        errors.append("schema_" + str(error.validator))
    if errors:
        return errors
    upstream = data["upstream"]
    base = f"{upstream['repository']}/{upstream['revision']}/"
    if (
        data["payload"]["url"]
        != "https://media.githubusercontent.com/media/" + base + upstream["path"]
    ):
        errors.append("unpinned_payload_url")
    roles = Counter(p["role"] for p in data["provenance"])
    if roles != Counter({"license": 1, "scenario_metadata": 1, "lfs_pointer": 1}):
        errors.append("incomplete_provenance")
    if data["terms"]["applicable_notice_paths"]:
        errors.append("unsupported_notice_requires_review")
    for resource in data["provenance"]:
        if resource["url"] != "https://raw.githubusercontent.com/" + base + resource["path"]:
            errors.append("unpinned_provenance_url")
        if resource["role"] == "lfs_pointer" and resource["path"] != upstream["path"]:
            errors.append("pointer_path_mismatch")
        if resource["role"] == "license" and resource["path"] != "LICENSE":
            errors.append("license_path_mismatch")
    expected_ancestors = ["."] + [
        "/".join(upstream["path"].split("/")[:i])
        for i in range(1, len(upstream["path"].split("/")))
    ]
    if data["terms"]["ancestor_paths_checked"] != expected_ancestors:
        errors.append("incomplete_ancestor_review")
    for resource in [data["payload"], *data["provenance"]]:
        try:
            approved_url(resource["url"])
        except ValueError:
            errors.append("unapproved_url")
    return sorted(set(errors))


def load_catalog(directory=CATALOG):
    directory = Path(directory)
    schema = load_json(directory / "manifest.schema.json")
    Draft202012Validator.check_schema(schema)
    catalog = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "manifest.schema.json":
            continue
        data = load_json(path)
        errors = manifest_errors(data, schema)
        if errors:
            raise ValueError(f"{path.name}: " + ",".join(errors))
        if data["id"] in catalog:
            raise ValueError("duplicate_catalog_id")
        if path.stem != data["id"]:
            raise ValueError("catalog_filename_mismatch")
        catalog[data["id"]] = data
    if not catalog:
        raise ValueError("empty_catalog")
    return catalog


def main():
    try:
        catalog = load_catalog()
    except (ValueError, OSError, KeyError):
        print(json.dumps({"category": "invalid_dataset_catalog"}))
        return 1
    print(f"PASS: {len(catalog)} pinned dataset manifests (offline)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
