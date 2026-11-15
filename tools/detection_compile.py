"""Bounded pySigma compiler; immutable JSON plans, no per-event Python."""

import argparse
import json
import os
import re
import signal
import tempfile
import uuid
from pathlib import Path
from typing import Any

import yaml
from check_contracts import ContractValidator, StrictValidator, load_json
from detection_mapping import (
    MAPPING,
    CompileError,
    encoded,
    require_schema,
    sha,
    validate_profiles,
    validate_provenance,
)
from sigma.conditions import (
    ConditionAND,
    ConditionFieldEqualsValueExpression,
    ConditionNOT,
    ConditionOR,
)
from sigma.rule import SigmaRule
from sigma.rule.detection import SigmaDetectionItem
from sigma.types import SigmaNumber, SigmaString, SpecialChars

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "contracts/detection/v1"
VERSION = "1.0.0"


class Loader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise CompileError("yaml_alias")
        depth = getattr(self, "bounded_depth", 0) + 1
        self.bounded_depth = depth
        if depth > 32:
            raise CompileError("depth_limit")
        try:
            return super().compose_node(parent, index)
        finally:
            self.bounded_depth -= 1

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise CompileError("duplicate_or_nonstring_key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse(text):
    if len(text.encode()) > 262144:
        raise CompileError("rule_size_limit")
    try:
        document = yaml.load(text, Loader=Loader)
    except CompileError:
        raise
    except Exception:
        raise CompileError("invalid_yaml") from None
    if not isinstance(document, dict):
        raise CompileError("rule_object_required")
    if set(document) - {
        "title",
        "id",
        "status",
        "description",
        "author",
        "date",
        "modified",
        "references",
        "tags",
        "falsepositives",
        "level",
        "license",
        "logsource",
        "detection",
    }:
        raise CompileError("unsupported_rule_attribute")
    try:
        uuid.UUID(document["id"])
    except (ValueError, TypeError, KeyError, AttributeError):
        raise CompileError("rule_id_required") from None
    source = document.get("logsource")
    if not isinstance(source, dict) or set(source) - {"product", "category", "service"}:
        raise CompileError("unsupported_logsource")
    if any(not isinstance(v, str) or not v for v in source.values()):
        raise CompileError("invalid_logsource")
    detection = document.get("detection")
    if not isinstance(detection, dict) or not isinstance(detection.get("condition"), str):
        raise CompileError("condition_required")
    condition = detection["condition"]
    if not re.fullmatch(r"[A-Za-z0-9_()\s-]+", condition) or re.search(r"\bof\b", condition):
        raise CompileError("unsupported_condition")
    for name, selection in detection.items():
        if name == "condition":
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name):
            raise CompileError("invalid_selection")
        if not isinstance(selection, dict) or not selection:
            raise CompileError("unsupported_selection")
        for field, value in selection.items():
            parts = field.split("|")
            if parts[0] not in MAPPING:
                raise CompileError("unmapped_field")
            if len(parts) > 2 or (
                len(parts) == 2 and parts[1] not in {"contains", "startswith", "endswith"}
            ):
                raise CompileError("unsupported_modifier")
            values = value if isinstance(value, list) else [value]
            if not values or len(values) > 4096:
                raise CompileError("invalid_value_list")
            for item in values:
                if type(item) not in (int, str):
                    raise CompileError("unsupported_value")
                if isinstance(item, int):
                    if parts[0] != "ProcessId" or len(parts) != 1 or not -(2**63) <= item < 2**63:
                        raise CompileError("integer_type_or_range")
                elif parts[0] == "ProcessId" or len(item) > 4096:
                    raise CompileError("string_type_or_limit")
    return document


def expression(node, budget, depth=1):
    budget[0] += 1
    if budget[0] > 4096 or depth > 32:
        raise CompileError("expression_limit")
    if type(node) in (ConditionAND, ConditionOR):
        return {
            "op": "and" if type(node) is ConditionAND else "or",
            "args": [expression(a, budget, depth + 1) for a in node.args],
        }
    if type(node) is ConditionNOT:
        return {"op": "not", "arg": expression(node.args[0], budget, depth + 1)}
    if type(node) is not ConditionFieldEqualsValueExpression or node.field not in MAPPING:
        raise CompileError("unsupported_expression")
    field = MAPPING[node.field]
    if type(node.value) is SigmaNumber:
        return {"op": "integer", "field": field, "value": node.value.number}
    if type(node.value) is not SigmaString:
        raise CompileError("unsupported_expression_value")
    tokens: list[dict[str, str]] = []
    for part in node.value.s:
        if isinstance(part, str):
            tokens.extend({"kind": "literal", "text": c} for c in part)
        elif part == SpecialChars.WILDCARD_MULTI:
            tokens.append({"kind": "star", "text": ""})
        elif part == SpecialChars.WILDCARD_SINGLE:
            tokens.append({"kind": "any", "text": ""})
        else:
            raise CompileError("unsupported_string_token")
    if len(tokens) > 4096:
        raise CompileError("pattern_limit")
    return {"op": "string", "field": field, "tokens": tokens}


def compile_rules(paths, sources, *, mappings=None, provenance=None):
    if not 1 <= len(paths) <= 100 or not 1 <= len(sources) <= 16:
        raise CompileError("bundle_count_limit")
    validator = ContractValidator()
    for source in sources:
        if validator.validate("source-contract", source):
            raise CompileError("invalid_source_contract")
    if len({s["id"] for s in sources}) != len(sources):
        raise CompileError("duplicate_source")
    mapped = mappings is not None or provenance is not None
    profiles = validate_profiles(mappings, sources) if mapped else None
    if mapped and (not isinstance(provenance, list) or len(provenance) != len(paths)):
        raise CompileError("candidate_provenance_set")
    candidates = {}
    for candidate in provenance or []:
        require_schema("candidate-provenance", candidate)
        identity = candidate["rule_id"]
        if identity in candidates:
            raise CompileError("duplicate_candidate")
        candidates[identity] = candidate
    rules, total, ids = [], 0, set()
    for path in paths:
        with Path(path).open("rb") as stream:
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise CompileError("rule_size_limit")
        try:
            text = raw.decode("utf-8", errors="strict")
            document = parse(text)
            rule = SigmaRule.from_dict(document)
            # pySigma 2.1.0 converts non-float-representable integers to float.
            # Restore validated source integers before condition expansion; never round them.
            for name, selection in document["detection"].items():
                if name == "condition":
                    continue
                for item in rule.detection.detections[name].detection_items:
                    if not isinstance(item, SigmaDetectionItem):
                        raise CompileError("unsupported_selection")
                    if item.field == "ProcessId":
                        original = selection["ProcessId"]
                        values = original if isinstance(original, list) else [original]
                        if len(values) != len(item.value):
                            raise CompileError("integer_structure_mismatch")
                        for typed, exact in zip(item.value, values, strict=True):
                            if type(typed) is not SigmaNumber:
                                raise CompileError("integer_structure_mismatch")
                            typed.number = exact
            budget = [0]
            tree = expression(rule.detection.parsed_condition[0].parsed, budget)
        except CompileError:
            raise
        except Exception:
            raise CompileError("pysigma_validation") from None
        identity = str(rule.id)
        if identity in ids:
            raise CompileError("duplicate_rule")
        ids.add(identity)
        total += budget[0]
        if total > 65536:
            raise CompileError("bundle_node_limit")
        rules.append(
            {
                "id": identity,
                "revision": sha(raw),
                "yaml": text,
                "logsource": document["logsource"],
                "expression": tree,
            }
        )
    if mapped:
        for compiled in rules:
            if compiled["id"] not in candidates:
                raise CompileError("candidate_provenance_set")
            candidate = candidates[compiled["id"]]
            validate_provenance(
                candidate, compiled["id"], compiled["revision"], parse(compiled["yaml"])
            )
            compiled["provenance"] = candidate
    plan: dict[str, Any] = {
        "version": VERSION,
        "compiler": "detectbridge/1.0.0",
        "pysigma": "2.1.0",
        "evaluator": "detectbridge-java/1.0.0",
        "mapping": MAPPING,
        "mapping_version": "fixture/1.0.0",
        "sources": sorted(sources, key=lambda s: s["id"]),
        "rules": sorted(rules, key=lambda r: r["id"]),
    }
    if mapped:
        plan.update(
            version="2.0.0",
            compiler="detectbridge/2.0.0",
            evaluator="detectbridge-java/2.0.0",
            mapping_version="source-mappings/1.0.0",
            mapping_profiles=profiles,
        )
    plan["bundle_sha256"] = sha(encoded(plan))
    if len(encoded(plan)) + 1 > 4 * 1024 * 1024:
        raise CompileError("bundle_size_limit")
    if mapped:
        require_schema("plan", plan)
    elif next(
        StrictValidator(
            load_json(DIRECTORY / "plan.schema.json"), registry=validator.registry
        ).iter_errors(plan),
        None,
    ):
        raise CompileError("invalid_plan")
    return plan


def analyze_candidates(paths, sources, mappings, provenance):
    """Report all submitted candidates without publishing a partial executable bundle."""
    if not 1 <= len(paths) <= 100 or not isinstance(provenance, list):
        raise CompileError("candidate_count_limit")
    if len(provenance) != len(paths):
        raise CompileError("candidate_provenance_set")
    validator = ContractValidator()
    if (
        not 1 <= len(sources) <= 16
        or any(validator.validate("source-contract", source) for source in sources)
        or len({source["id"] for source in sources}) != len(sources)
    ):
        raise CompileError("invalid_source_contract")
    profiles = validate_profiles(mappings, sources)
    candidates = {}
    ids = set()
    for candidate in provenance:
        require_schema("candidate-provenance", candidate)
        if candidate["revision"] in candidates or candidate["rule_id"] in ids:
            raise CompileError("duplicate_candidate")
        candidates[candidate["revision"]] = candidate
        ids.add(candidate["rule_id"])
    rows, used = [], set()
    for path in paths:
        with Path(path).open("rb") as stream:
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise CompileError("rule_size_limit")
        revision = sha(raw)
        if revision not in candidates or revision in used:
            raise CompileError("candidate_provenance_set")
        used.add(revision)
        candidate = candidates[revision]
        validate_provenance(candidate, candidate["rule_id"], revision, {})
        row = {"provenance": candidate, "revision": revision}
        try:
            plan = compile_rules([path], sources, mappings=profiles, provenance=[candidate])
            rule = plan["rules"][0]

            def fields(node):
                if node["op"] in ("and", "or"):
                    return set().union(*(fields(arg) for arg in node["args"]))
                if node["op"] == "not":
                    return fields(node["arg"])
                return {node["field"]}

            required = fields(rule["expression"])
            dispositions = []
            for source, profile in zip(plan["sources"], profiles, strict=True):
                applicable = all(source["sigma"].get(k) == v for k, v in rule["logsource"].items())
                blocked = any(
                    f["capability"] == "unsupported" and f["target"] in required
                    for f in profile["fields"]
                )
                dispositions.append(
                    {
                        "source_id": source["id"],
                        "source_version": source["version"],
                        "status": "inapplicable"
                        if not applicable
                        else "configuration_blocked"
                        if blocked
                        else "supported",
                    }
                )
            row.update(status="compiled", sources=dispositions)
        except CompileError as error:
            if str(error) == "compiler_timeout":
                raise
            row.update(status="rejected", diagnostic={"category": str(error), "pointer": ""})
        rows.append(row)
    report = {"version": "1.0.0", "kind": "candidate-analysis", "candidates": rows}
    require_schema("candidate-analysis", report)
    if len(encoded(report)) > 4 * 1024 * 1024:
        raise CompileError("candidate_report_limit")
    return report


def load_source(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise CompileError("source_size_limit")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise CompileError("duplicate_source_key")
            value[key] = item
        return value

    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(CompileError("non_json_number")),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rules", nargs="+")
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--analyze", action="store_true", help="Report every candidate; never publish a bundle"
    )
    parser.add_argument("--mapping", action="append", help="P10 mapping-profile JSON (one/source)")
    parser.add_argument("--provenance", help="P10 JSON array of candidate provenance manifests")
    args = parser.parse_args()

    def timeout(signum, frame):
        raise CompileError("compiler_timeout")

    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(30)
    temporary = None
    try:
        if len(args.source) > 16 or len(args.rules) > 100:
            raise CompileError("bundle_count_limit")
        if args.mapping is not None and len(args.mapping) > 16:
            raise CompileError("mapping_count_limit")
        operation = analyze_candidates if args.analyze else compile_rules
        plan = operation(
            args.rules,
            [load_source(p) for p in args.source],
            mappings=[load_source(p) for p in args.mapping] if args.mapping is not None else None,
            provenance=load_source(args.provenance) if args.provenance is not None else None,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as out:
            temporary = Path(out.name)
            out.write(encoded(plan) + b"\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, args.output)
    except Exception as error:
        print(
            json.dumps(
                {
                    "category": str(error)
                    if isinstance(error, CompileError)
                    else "compiler_input_or_io",
                    "pointer": "",
                }
            )
        )
        raise SystemExit(1) from None
    finally:
        signal.alarm(0)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
