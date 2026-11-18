"""Qualification-only new policy and schedules from the pre-implementation packet."""

import copy
import json
from pathlib import Path

from detection_compile import compile_rules
from historical import ROOT, encoded, sha

FIXTURES = ROOT / "contracts/current-replay/v1/fixtures"
FREEZE = "b068b5358acb6313f8eb19a4055c33f3953ba2b1"
ASSEMBLER = dict(
    members=256,
    group_bytes=1048576,
    open_groups=1024,
    pending_bytes=33554432,
    age_ms=30000,
    runs=16,
    closed_keys=100000,
    closed_bytes=33554432,
)


def packet():
    value = json.loads((FIXTURES / "expectations.json").read_bytes())
    for source in value["sources"]:
        assert sha((ROOT / source["path"]).read_bytes()) == source["sha256"]
    assert sha(encoded(value["identity"]["preimage"])) == value["identity"]["sha256"]
    return value


def prepare_plan(path):
    """Compile original frozen rules; no evaluator output supplies expectations."""
    packet()
    paths = sorted(FIXTURES.glob("*.yml"))
    import yaml

    provenance = [
        dict(
            version="1.0.0",
            rule_id=yaml.safe_load(p.read_bytes())["id"],
            revision=sha(p.read_bytes()),
            kind="synthetic",
            repository="https://github.com/TravisMa07/DetectBridge",
            repository_revision=FREEZE,
            path=str(p.relative_to(ROOT)),
            original_sha256=sha(p.read_bytes()),
            authors=["DetectBridge contributors"],
            license="Apache-2.0",
            notices=[],
            modifications=[],
        )
        for p in paths
    ]
    sources, mappings = [], []
    for folder, families in [
        (ROOT / "packages/windows-adapters/profiles", ("security", "sysmon")),
        (
            ROOT / "packages/linux-adapters/contracts",
            ("linux-audit-execution-p12a", "openssh-authentication-p12a"),
        ),
    ]:
        for family in families:
            sources.append(json.loads((folder / (family + ".source.json")).read_bytes()))
            mappings.append(json.loads((folder / (family + ".mapping.json")).read_bytes()))
    plan = compile_rules(paths, sources, mappings=mappings, provenance=provenance)
    Path(path).write_bytes(encoded(plan) + b"\n")
    return plan


def request(selection_hash, historical_request, plan_hash, case="regroup"):
    """Three original units: timeout members, original late EOE and Alice auth."""
    unit = {u["id"]: u for u in historical_request["units"]}
    assert set(unit) == {"audit_timeout", "late", "auth"}
    refs = {
        **{"audit_" + str(i): r for i, r in enumerate(unit["audit_timeout"]["inputs"])},
        "audit_5": unit["late"]["inputs"][0],
        "auth": unit["auth"]["inputs"][0],
    }
    expected = next(c for c in packet()["cases"] if c["id"] == case)
    schedule = []
    for label, at in zip(expected["inputs"], expected["milliseconds"], strict=True):
        if label == "audit_5" and "tick_before_eoe" in expected:
            schedule.append(dict(at_ms=expected["tick_before_eoe"], action="tick", input=None))
        schedule.append(dict(at_ms=at, action="input", input=copy.deepcopy(refs[label])))
    schedule.append(dict(at_ms=expected["milliseconds"][-1] + 1, action="end", input=None))
    return dict(
        version="1.0.0",
        mode="current",
        selection_sha256=selection_hash,
        plan_sha256=plan_hash,
        engine_profile="p13-runtime-51a984de/1.0.0",
        source_policy="preserve-original-context/1.0.0",
        schedule_policy="explicit-offline-clock/1.0.0",
        enrichment=[],
        assembler_limits=copy.deepcopy(ASSEMBLER),
        schedule=schedule,
    )
