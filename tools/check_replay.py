"""Local-only replay schema registry and example checks."""

import json
from pathlib import Path
from urllib.parse import urldefrag

from check_contracts import ContractValidator, StrictValidator, load_json
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "contracts/replay/v1"
BASE = "urn:detectbridge:replay:1.0.0:"
NAMES = {"capture", "timing-index", "envelope", "run-manifest", "checkpoint", "segment"}


class ReplayValidator:
    def __init__(self, directory=DIRECTORY):
        self.raw = ContractValidator()
        self.schemas = dict(self.raw.schemas)
        replay = {}
        for path in Path(directory).glob("*.schema.json"):
            schema = load_json(path)
            Draft202012Validator.check_schema(schema)
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                raise ValueError("unsupported_replay_draft")
            if schema["$id"] in replay:
                raise ValueError("duplicate_replay_schema")
            replay[schema["$id"]] = schema
        if set(replay) != {BASE + name for name in NAMES}:
            raise ValueError("unknown_replay_schema")
        self.schemas.update(replay)
        self.registry = Registry().with_resources(
            (name, Resource.from_contents(schema)) for name, schema in self.schemas.items()
        )
        for schema in replay.values():
            self.check_refs(schema, schema["$id"])

    def check_refs(self, node, current):
        if isinstance(node, dict):
            for key in ("$ref", "$dynamicRef"):
                if key in node:
                    name, _ = urldefrag(node[key])
                    if name and name not in self.schemas:
                        raise ValueError("nonlocal_replay_reference")
                    self.registry.resolver(current).lookup(node[key])
            for child in node.values():
                self.check_refs(child, current)
        elif isinstance(node, list):
            for child in node:
                self.check_refs(child, current)

    def require(self, name, value):
        if name not in NAMES:
            raise ValueError("unknown_replay_kind")
        validator = StrictValidator(
            self.schemas[BASE + name], registry=self.registry, format_checker=FormatChecker()
        )
        if next(validator.iter_errors(value), None) is not None:
            raise ValueError("invalid_" + name)
        if name == "envelope" and value["type"] == "record":
            if self.raw.validate("raw-record", value["record"]):
                raise ValueError("invalid_embedded_raw_record")


def main():
    try:
        validator = ReplayValidator()
        index = load_json(DIRECTORY / "examples/index.json")
        files = {
            path.name
            for path in (DIRECTORY / "examples").glob("*.json")
            if path.name != "index.json"
        }
        if len(index) != len(files) or {entry["path"] for entry in index} != files:
            raise ValueError("incomplete_replay_examples")
        for entry in index:
            validator.require(entry["kind"], load_json(DIRECTORY / "examples" / entry["path"]))
    except Exception:
        print(json.dumps({"category": "invalid_replay_contract_or_example"}))
        return 1
    print("PASS: local replay schemas and examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
