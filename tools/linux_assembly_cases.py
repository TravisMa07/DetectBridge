"""Original P12b inputs and independently reasoned membership/outcome expectations."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = "00000000-0000-4000-8000-000000000012"
FIRST = "2026-01-01T00:00:01Z"
PARTS = [
    'SYSCALL arch=c000003e syscall=59 success=yes exit=0 pid=42 items=2 exe="/usr/bin/whoami"',
    'EXECVE argc=3 a0="whoami" a1="" a2="whoami"',
    'CWD cwd="/tmp"',
    'PATH item=0 name="/usr/bin/whoami"',
    'PATH item=1 name="/lib/ld.so"',
    "EOE",
]


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def identity(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )


def context(auth=False, *, host="host-a", generation="boot-a", run=RUN):
    family = "openssh-authentication-p12a" if auth else "linux-audit-execution-p12a"
    directory = ROOT / "packages/linux-adapters/contracts"
    source = json.loads((directory / (family + ".source.json")).read_bytes())
    mapping = json.loads((directory / (family + ".mapping.json")).read_bytes())
    scope = dict(namespace="original-p12b-synthetic", instance="a")
    binding = dict(
        host_id=host,
        source=scope,
        revision="synthetic-1",
        kind="synthetic",
        provenance=["synthetic:p12b-binding"],
    )
    binding["sha256"] = digest(binding)
    return dict(
        version="1.0.0",
        run_id=run,
        source=scope,
        first_observed=FIRST,
        host_binding=binding,
        source_generation=dict(id=generation, provenance=["synthetic:p12b-generation"]),
        source_contract=dict(id=family, version="1.0.0", sha256=digest(source), snapshot=source),
        mapping_profile=dict(
            id=mapping["id"], version="1.0.0", sha256=mapping["sha256"], declaration=mapping
        ),
        parser=dict(id="openssh-password" if auth else "linux-audit", version="1.0.0"),
    )


def record(body, position, ctx=None):
    ctx = copy.deepcopy(ctx or context())
    data = body.encode()
    cursor = dict(kind="native", value="p12b-original-position-" + str(position))
    source = ctx["source"]
    raw = dict(
        contract_version="1.0.0",
        source=source,
        first_observed=FIRST,
        cursor=cursor,
        evidence=dict(
            sha256=hashlib.sha256(data).hexdigest(),
            encoding="utf-8",
            media_type="text/plain",
            inline=body,
        ),
    )
    raw["record_id"] = identity(
        [source["namespace"], source["instance"], ["native", cursor["value"]]]
    )
    return dict(version="1.0.0", kind="record", raw=raw, context=ctx)


def audit(part, serial="7"):
    name, _, fields = part.partition(" ")
    return (
        f"type={name} msg=audit(1767225600.001:{serial}):" + (" " + fields if fields else "") + "\n"
    )


def cases():
    complete = [record(audit(part), i) for i, part in enumerate(PARTS)]
    ids = sorted(row["raw"]["record_id"] for row in complete)
    source = complete[0]["raw"]["source"]
    auth = record(
        "<38>1 2026-01-01T00:00:00Z lab sshd 7 - - Accepted password for alice from 192.0.2.1 port 2222 ssh2\n",
        100,
        context(True),
    )
    return dict(
        version="1.0.0",
        complete=complete,
        auth=auth,
        expected=dict(
            member_ids=ids,
            event_id=identity([source["namespace"], source["instance"], ids]),
            closure="source_boundary",
            eligibility="eligible",
            executable="/usr/bin/whoami",
            args=["whoami", "", "whoami"],
            path_items=[0, 1],
            auth_outcome="success",
        ),
    )


def prepare():
    path = ROOT / ".cache/linux-assembly/cases.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(cases()) + b"\n")
    print("PASS: prepared original inputs and independent P12b expectations")


if __name__ == "__main__":
    prepare()
