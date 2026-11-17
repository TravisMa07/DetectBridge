"""Original synthetic P13b admissions, pinned plan and independent literal expectations."""

import copy
import hashlib
import json
import subprocess

from detection_compile import compile_rules
from linux_assembly_cases import ROOT, RUN, digest, encoded, identity
from linux_assembly_cases import cases as linux_cases

CACHE = ROOT / ".cache/integration"


def windows(family="security", *, run=RUN, binding=True, budget=False, unsupported=False):
    directory = ROOT / "packages/windows-adapters"
    expected = json.loads((directory / "profiles" / (family + ".expected.json")).read_bytes())
    raw = copy.deepcopy(expected["detectbridge"]["evidence"][0])
    raw.update(
        contract_version="1.0.0",
        source=expected["detectbridge"]["source"],
        first_observed=expected["detectbridge"]["time"]["first_observed"],
        cursor=dict(kind="native", value="p13b-" + family),
    )
    if not binding:
        raw["cursor"]["value"] += "-skipped"
    if budget:
        raw["cursor"]["value"] += "-budget"
        raw["evidence"]["inline"] = raw["evidence"]["inline"].replace(
            "synthetic.exe &quot;α 😀&quot;", "x" * 65536
        )
    if unsupported:
        raw["cursor"]["value"] += "-unsupported"
        raw["evidence"]["inline"] = "<invalid/>"
    raw["evidence"]["sha256"] = hashlib.sha256(raw["evidence"]["inline"].encode()).hexdigest()
    raw["record_id"] = identity(
        [raw["source"]["namespace"], raw["source"]["instance"], ["native", raw["cursor"]["value"]]]
    )
    source = json.loads((directory / "profiles" / (family + ".source.json")).read_bytes())
    mapping = json.loads((directory / "profiles" / (family + ".mapping.json")).read_bytes())
    ctx = dict(
        version="1.0.0",
        run_id=run,
        source=raw["source"],
        first_observed=raw["first_observed"],
        source_contract=dict(
            id=source["id"], version="1.0.0", sha256=digest(source), snapshot=source
        ),
        mapping_profile=dict(
            id=mapping["id"], version="1.0.0", sha256=mapping["sha256"], declaration=mapping
        ),
        parser=dict(id="windows-xml", version="1.0.0"),
    )
    if binding:
        host = dict(
            host_id="synthetic-host-id",
            computer="SYNTHETIC-HOST",
            source=raw["source"],
            revision="synthetic-1",
            provenance=["original synthetic fixture"],
            kind="synthetic",
        )
        host["sha256"] = digest(host)
        ctx["host_binding"] = host
    return dict(version="1.0.0", kind="windows_record", raw=raw, context=ctx)


def prepare():
    CACHE.mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = sorted((ROOT / "packages/windows-adapters/fixtures/rules").glob("*.yml")) + sorted(
        (ROOT / "packages/linux-adapters/fixtures/rules").glob("*.yml")
    )
    import yaml

    provenance = []
    for path in paths:
        original = subprocess.check_output(
            ["git", "show", f"{revision}:{path.relative_to(ROOT)}"], cwd=ROOT
        )
        if original != path.read_bytes():
            raise ValueError("uncommitted_integration_rule")
        sha = hashlib.sha256(original).hexdigest()
        provenance.append(
            dict(
                version="1.0.0",
                rule_id=yaml.safe_load(original)["id"],
                revision=sha,
                kind="synthetic",
                repository="https://github.com/TravisMa07/DetectBridge",
                repository_revision=revision,
                path=str(path.relative_to(ROOT)),
                original_sha256=sha,
                authors=["DetectBridge contributors"],
                license="Apache-2.0",
                notices=[],
                modifications=[],
            )
        )
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
    (CACHE / "plan.json").write_bytes(encoded(plan) + b"\n")
    data = linux_cases()
    data.update(
        windows=windows(),
        sysmon=windows("sysmon"),
        windows_skipped=windows(binding=False),
        windows_budget=windows(budget=True),
        windows_preserved=windows(unsupported=True),
    )
    (CACHE / "cases.json").write_bytes(encoded(data) + b"\n")
    print(
        "PASS: pinned combined plan and original source inputs; expectations are independent literals"
    )


if __name__ == "__main__":
    prepare()
