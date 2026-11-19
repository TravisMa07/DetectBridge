"""P15a closed candidate validation and bounded execution of the retained Java evaluator."""

import argparse
import hashlib
import json
import os
import selectors
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path

from check_contracts import StrictValidator, load_json
from detection_compile import compile_rules
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts/lifecycle/v1"
PIN = "51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d"
LOGGING_PIN = "7e1446499b359675d8aabe6af2de86b85e72ae8a2a932c0b40d0e5ba57097439"
MIB = 1024 * 1024
LIMITS = load_json(SCHEMAS / "manifest.schema.json")["properties"]["profile"]["properties"][
    "limits"
]["const"]


def fail(valid, category):
    if not valid:
        raise ValueError("lifecycle_" + category)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def decode(data):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            fail(key not in value, "duplicate_key")
            value[key] = item
        return value

    try:
        result = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=unique,
            parse_constant=lambda _: fail(False, "non_json_number"),
        )
        encoded(result)  # Reject unpaired surrogates before any publication.
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("lifecycle_invalid_json") from None


def safe(path):
    fail(".." not in Path(path).parts, "parent_path")
    path = Path(os.path.abspath(path))
    for component in [*reversed(path.parents), path]:
        fail(not component.is_symlink(), "symlink")
    return path


def read(path, maximum):
    path = safe(path)
    fail(path.is_file(), "regular_file_required")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    fail(len(data) <= maximum, "input_limit")
    return data


@lru_cache(maxsize=1)
def registry():
    resources = []
    for directory in (ROOT / "contracts/v1", ROOT / "contracts/integration/v1", SCHEMAS):
        for path in directory.glob("*.schema.json"):
            schema = load_json(path)
            Draft202012Validator.check_schema(schema)
            resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def require(kind, value):
    schema = load_json(SCHEMAS / (kind + ".schema.json"))
    fail(
        not list(
            StrictValidator(
                schema, registry=registry(), format_checker=FormatChecker()
            ).iter_errors(value)
        ),
        "schema_" + kind,
    )

    # Schema constants use JSON numeric equality; still reject bool/float counters.
    def integers(node):
        if isinstance(node, dict):
            return all(integers(v) for v in node.values())
        if isinstance(node, list):
            return all(integers(v) for v in node)
        return not isinstance(node, float)

    fail(integers(value), "integer_required")
    if kind == "manifest":
        fail(all(type(v) is int for v in value["profile"]["limits"].values()), "integer_required")


def profile(plan):
    properties = load_json(SCHEMAS / "manifest.schema.json")["properties"]["profile"]["properties"]
    result = {key: value["const"] for key, value in properties.items() if "const" in value}
    result.update(
        source_sha256=sha(encoded(plan["sources"])),
        mappings_sha256=sha(encoded(plan["mapping_profiles"])),
    )
    return result


def bundle(plan_bytes):
    fail(0 < len(plan_bytes) <= LIMITS["plan_bytes"], "plan_limit")
    plan = decode(plan_bytes)
    fail(isinstance(plan, dict) and plan.get("version") == "2.0.0", "mapped_plan_required")
    for key in ("sources", "mapping_profiles", "rules", "bundle_sha256"):
        fail(key in plan, "incomplete_plan")
    declaration = profile(plan)
    reference = dict(
        sha256=sha(plan_bytes), bundle_sha256=plan["bundle_sha256"], bytes=len(plan_bytes)
    )
    manifest = dict(
        version="1.0.0",
        plan=reference,
        profile=declaration,
        compatibility_sha256=sha(encoded(declaration)),
        members=[dict(name="plan.json", sha256=reference["sha256"], bytes=len(plan_bytes))],
    )
    manifest["bundle_sha256"] = sha(encoded(manifest))
    require("manifest", manifest)
    return manifest


def verify_bundle(directory):
    directory = safe(directory)
    fail(
        directory.is_dir()
        and {p.name for p in directory.iterdir()} == {"manifest.json", "plan.json"},
        "bundle_contents",
    )
    manifest_bytes = read(directory / "manifest.json", LIMITS["manifest_bytes"])
    manifest = decode(manifest_bytes)
    require("manifest", manifest)
    plan_bytes = read(directory / "plan.json", LIMITS["plan_bytes"])
    fail(len(manifest_bytes) + len(plan_bytes) <= LIMITS["closure_bytes"], "closure_limit")
    fail(manifest == bundle(plan_bytes), "bundle_integrity")
    return manifest, plan_bytes


def verify_artifact(path):
    path = safe(path)
    fail(path.is_file(), "evaluator_missing")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(MIB):
            digest.update(block)
    fail(digest.hexdigest() == PIN, "evaluator_integrity")
    logging_api()
    return path


def logging_api():
    cache = ROOT / ".cache/gradle/caches/modules-2/files-2.1/org.slf4j/slf4j-api/2.0.20"
    paths = list(cache.glob("*/slf4j-api-2.0.20.jar"))
    fail(len(paths) == 1, "logging_dependency_missing")
    path = safe(paths[0])
    fail(sha(read(path, MIB)) == LOGGING_PIN, "logging_dependency_integrity")
    return path


def validate_plan(plan_bytes, temporary_root=None):
    """Recompile original YAML/provenance instead of trusting a self-hashed AST."""
    manifest = bundle(plan_bytes)
    plan = decode(plan_bytes)
    fail(
        1 <= len(plan["rules"]) <= LIMITS["rules"]
        and 1 <= len(plan["sources"]) <= LIMITS["sources"],
        "plan_count_limit",
    )
    with tempfile.TemporaryDirectory(prefix=".compile-", dir=temporary_root) as temp:
        paths, provenance = [], []
        for number, rule in enumerate(plan["rules"]):
            fail(
                isinstance(rule, dict)
                and isinstance(rule.get("yaml"), str)
                and "provenance" in rule,
                "rule_provenance",
            )
            path = Path(temp) / (str(number) + ".yml")
            path.touch(mode=0o600)
            path.write_bytes(rule["yaml"].encode("utf-8"))
            paths.append(path)
            provenance.append(rule["provenance"])
        rebuilt = compile_rules(
            paths, plan["sources"], mappings=plan["mapping_profiles"], provenance=provenance
        )
    fail(rebuilt == plan, "plan_compilation_mismatch")
    fail(manifest["plan"]["bundle_sha256"] == rebuilt["bundle_sha256"], "plan_identity")
    return plan


def java_compact(plan, event, jar, folder):
    """Bound stdout while reading it; discard stderr and kill on size/deadline."""
    event_path = folder / "event.json"
    if not event_path.exists():
        event_path.touch(mode=0o600)
    event_path.write_bytes(event)
    command = [
        str(ROOT / ".cache/jdk/bin/java"),
        "-Xmx256m",
        "-cp",
        str(jar) + os.pathsep + str(logging_api()),
        "io.detectbridge.detection.Evaluate",
        str(plan),
        str(event_path),
        "--compact",
    ]
    deadline = time.monotonic() + LIMITS["test_timeout_seconds"]
    output = bytearray()
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env={"PATH": os.defpath},
    ) as process:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        process.kill()
                        return None, "timeout"
                    ready = selector.select(min(remaining, 0.1))
                    if ready:
                        block = os.read(process.stdout.fileno(), 65536)
                        if not block:
                            break
                        output.extend(block)
                        if len(output) > LIMITS["test_stdout_bytes"]:
                            process.kill()
                            return None, "output_limit"
                try:
                    returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    process.kill()
                    return None, "timeout"
            finally:
                if process.poll() is None:
                    process.kill()
        if returncode:
            return None, "evaluator_failure"
    try:
        value = decode(bytes(output))
        schema = load_json(ROOT / "contracts/integration/v1/compact-evaluation.schema.json")
        fail(
            not list(StrictValidator(schema, registry=registry()).iter_errors(value)),
            "compact_output",
        )
        return value, "ok"
    except (ValueError, TypeError):
        return None, "invalid_output"


def run_suite(plan_bytes, suite_path, jar_path, temporary_root):
    jar = verify_artifact(jar_path)
    temporary_root = safe(temporary_root)
    validate_plan(plan_bytes, temporary_root)
    suite_bytes = read(suite_path, LIMITS["test_input_bytes"])
    suite = decode(suite_bytes)
    require("test-suite", suite)
    identities = [case["id"] for case in suite["cases"]]
    fail(len(identities) == len(set(identities)), "duplicate_case")
    fail(
        any(
            c["expected"]["counts"]["matched"] > 0
            and c["event"]["detectbridge"]["quality"]["eligibility"] == "eligible"
            for c in suite["cases"]
        ),
        "positive_case_required",
    )
    fail(
        any(
            c["expected"]["counts"]["unmatched"] > 0
            and c["event"]["detectbridge"]["quality"]["eligibility"] == "eligible"
            for c in suite["cases"]
        ),
        "negative_case_required",
    )
    events = [encoded(case["event"]) for case in suite["cases"]]
    fail(all(len(event) <= LIMITS["test_case_bytes"] for event in events), "test_case_limit")
    result = dict(
        version="1.0.0",
        passed=True,
        suite_sha256=sha(suite_bytes),
        plan_sha256=sha(plan_bytes),
        evaluator_sha256=PIN,
        logging_api_sha256=LOGGING_PIN,
        cases=[],
    )
    temporary_root = safe(temporary_root)
    with tempfile.TemporaryDirectory(prefix=".test-", dir=temporary_root) as temp:
        folder = Path(temp)
        folder.chmod(0o700)
        plan_path = folder / "plan.json"
        plan_path.touch(mode=0o600)
        plan_path.write_bytes(plan_bytes)
        for case, event in zip(suite["cases"], events, strict=True):
            observed, category = java_compact(plan_path, event, jar, folder)
            expected = case["expected"]
            if category == "ok" and observed != expected:
                category = "outcome_mismatch"
            result["passed"] = result["passed"] and category == "ok"
            result["cases"].append(
                dict(
                    id=case["id"],
                    input_sha256=sha(event),
                    expected_sha256=sha(encoded(expected)),
                    observed_sha256=sha(encoded(observed)) if observed is not None else None,
                    category=category,
                )
            )
    result["report_sha256"] = sha(encoded(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        data = read(args.plan, LIMITS["plan_bytes"])
        validate_plan(data)
        manifest = bundle(data)
        destination = safe(args.destination)
        fail(not destination.exists() and destination.parent.is_dir(), "destination")
        destination.mkdir(mode=0o700)
        (destination / "plan.json").write_bytes(data)
        (destination / "manifest.json").write_bytes(encoded(manifest) + b"\n")
        print(json.dumps(dict(status="candidate_files", bundle_sha256=manifest["bundle_sha256"])))
        return 0
    except Exception:
        print('{"category":"lifecycle_candidate_failure"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
