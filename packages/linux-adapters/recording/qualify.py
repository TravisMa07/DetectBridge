"""Review local recording originals and independently verify offline adapter/evaluator output."""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from functools import cache
from itertools import zip_longest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from check_contracts import ContractValidator  # noqa: E402
from detection_mapping import require_schema  # noqa: E402

CATALOG = ROOT / "catalog/recordings/openssh9-password-lab-v1.json"


def require(condition):
    if not condition:
        raise ValueError("recording_qualification_mismatch")


def encoded(value, canonical=False):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=canonical, separators=(",", ":")
    ).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return "sha256:" + sha(encoded(value))


@cache
def module_validator(kind):
    paths = list((ROOT / "packages/linux-adapters/contracts").glob("*.schema.json"))
    paths.append(ROOT / "contracts/v1/common.schema.json")
    schemas = [json.loads(path.read_bytes()) for path in paths]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    schema = next(
        schema for schema in schemas if schema["$id"] == "urn:detectbridge:linux:1.0.0:" + kind
    )
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def artifacts(catalog, directory):
    require(catalog["version"] == "1.0.0" and catalog["kind"] == "local-controlled-recording")
    names = set()
    for artifact in catalog["artifacts"]:
        name = artifact["filename"]
        require(Path(name).name == name and name not in names)
        names.add(name)
        path = directory / name
        require(path.stat().st_size == artifact["size_bytes"] <= 32 * 1024 * 1024)
        require(sha(path.read_bytes()) == artifact["sha256"])
    require(
        {"auth.native", "auth.rfc5424", "container.json", "image.json", "actions.json"} <= names
    )
    acquisition = catalog["acquisition"]
    require(sha((ROOT / acquisition["capture_path"]).read_bytes()) == acquisition["capture_sha256"])
    container = json.loads((directory / "container.json").read_bytes())[0]
    image = json.loads((directory / "image.json").read_bytes())[0]
    require(container["Id"] == acquisition["source"]["instance"])
    require(container["Image"] == image["Id"] == acquisition["image_id"])
    require(container["HostConfig"]["NetworkMode"] == "none")
    require(not container["HostConfig"]["PortBindings"] and not container["Mounts"])
    require(
        [a["client_exit"] for a in json.loads((directory / "actions.json").read_bytes())]
        == [0, 255]
    )
    require(acquisition["daemon_version"].startswith("OpenSSH_9."))
    host = dict(acquisition["host_binding"])
    digest = host.pop("sha256")
    require(host["kind"] == "reviewed" and host["source"] == acquisition["source"])
    require(
        host["host_id"] == "container:" + container["Id"] and sha(encoded(host, True)) == digest
    )
    rows = (directory / "auth.rfc5424").read_bytes().splitlines(keepends=True)
    originals = (directory / "auth.native").read_bytes().splitlines(keepends=True)
    require(len(rows) == len(originals) == len(catalog["expectations"]))
    for index, (row, original, expectation) in enumerate(
        zip(rows, originals, catalog["expectations"])
    ):
        require(expectation["position"] == index and expectation["sha256"] == sha(row))
        require(expectation["size_bytes"] == len(row))
        native = re.fullmatch(
            rb"<[0-9]+>[A-Z][a-z]{2} [ 0-9][0-9] [0-9:]{8} sshd\[[0-9]+\]: (.*)\n", original
        )
        framed = re.fullmatch(rb"<[0-9]+>1 (\S+) \S+ sshd \S+ - - (.*)\n", row)
        require(native is not None and framed is not None)
        require(native[1] == framed[2])
    return rows


def prepare(catalog, rows, destination):
    acquisition = catalog["acquisition"]
    family = "openssh-authentication-p12a"
    directory = ROOT / "packages/linux-adapters/contracts"
    source = json.loads((directory / (family + ".source.json")).read_bytes())
    mapping = json.loads((directory / (family + ".mapping.json")).read_bytes())
    context = {
        k: acquisition[k] for k in ("source", "first_observed", "source_generation", "host_binding")
    }
    context.update(
        version="1.0.0",
        run_id="00000000-0000-4000-8000-000000000012",
        source_contract=dict(
            id=family, version="1.0.0", sha256=sha(encoded(source, True)), snapshot=source
        ),
        mapping_profile=dict(
            id=mapping["id"],
            version=mapping["version"],
            sha256=mapping["sha256"],
            declaration=mapping,
        ),
        parser=dict(id="openssh-password", version="1.0.0"),
    )
    with destination.open("wb") as out:
        for index, row in enumerate(rows):
            cursor = dict(
                kind="native", value=f"recording:{catalog['id']}:{sha(b''.join(rows))}:{index}"
            )
            raw = dict(
                contract_version="1.0.0",
                source=context["source"],
                first_observed=context["first_observed"],
                cursor=cursor,
                evidence=dict(
                    sha256=sha(row),
                    encoding="utf-8",
                    media_type="text/plain",
                    inline=row.decode("utf-8"),
                ),
            )
            raw["record_id"] = identity(
                [raw["source"]["namespace"], raw["source"]["instance"], ["native", cursor["value"]]]
            )
            out.write(encoded(dict(raw=raw, context=context)) + b"\n")


def disposition(expectation, published):
    normalized = expectation["disposition"] == "normalized"
    require(("event" in published) == normalized)
    require(("preservation" in published) != normalized)
    require(("evaluation" in published) == normalized)
    if not normalized:
        require(published["preservation"]["code"] == expectation["disposition"])
    return normalized


def verify(catalog, originals, input_path, output_path, plan_path):
    plan = json.loads(plan_path.read_bytes())
    require_schema("plan", plan)
    unhashed = dict(plan)
    unhashed.pop("bundle_sha256")
    require(sha(encoded(unhashed, True)) == plan["bundle_sha256"])
    validator = ContractValidator()
    count = 0
    with input_path.open() as inputs, output_path.open() as outputs:
        for index, values in enumerate(
            zip_longest(inputs, outputs, originals, catalog["expectations"])
        ):
            input_line, output_line, original, expectation = values
            require(all(value is not None for value in values))
            supplied, published = json.loads(input_line), json.loads(output_line)
            raw, context = supplied["raw"], supplied["context"]
            module_validator("context").validate(context)
            require(not validator.validate("raw-record", raw))
            require(
                published["raw"] == raw
                and published["context"] == context
                and published["version"] == "1.0.0"
            )
            require(
                raw["evidence"]["inline"].encode() == original
                and raw["evidence"]["sha256"] == sha(original)
            )
            require(context["host_binding"] == catalog["acquisition"]["host_binding"])
            require(context["source_generation"] == catalog["acquisition"]["source_generation"])
            require(raw["source"] == context["source"] == catalog["acquisition"]["source"])
            require(
                raw["first_observed"]
                == context["first_observed"]
                == catalog["acquisition"]["first_observed"]
            )
            if disposition(expectation, published):
                event, evaluation = published["event"], published["evaluation"]
                require(
                    not validator.validate(
                        "normalized-event",
                        event,
                        source_contract=context["source_contract"]["snapshot"],
                    )
                )
                require(event["event"]["outcome"] == expectation["outcome"])
                require(event["user"]["name"] == expectation["user"])
                require(
                    event["source"]
                    == dict(ip=expectation["source_ip"], port=expectation["source_port"])
                )
                require(
                    datetime.fromisoformat(event["@timestamp"]).astimezone(UTC)
                    == datetime.fromisoformat(expectation["timestamp"]).astimezone(UTC)
                )
                require(event["host"]["id"] == context["host_binding"]["host_id"])
                db = event["detectbridge"]
                require(
                    db["quality"]["eligibility"] == "eligible"
                    and db["quality"]["integrity"] == "sufficient"
                )
                require(db["run_id"] == context["run_id"] and db["source"] == raw["source"])
                require(
                    db["evidence"] == [dict(record_id=raw["record_id"], evidence=raw["evidence"])]
                )
                require(db["time"]["first_observed"] == raw["first_observed"])
                require(
                    db["processing"]
                    == dict(
                        parser="openssh-password/1.0.0",
                        mapping=context["mapping_profile"]["id"] + "/1.0.0",
                        normalizer="linux-p12a/1.0.0",
                    )
                )
                require("command_line" not in event.get("process", {}))
                require_schema("result", evaluation)
                require(evaluation["bundle_sha256"] == plan["bundle_sha256"])
                require(
                    evaluation["mapping_sha256"] == sha(encoded(plan["mapping_profiles"], True))
                )
                for key in ("compiler", "evaluator", "mapping_version"):
                    require(evaluation[key] == plan[key])
                require(evaluation["matched"] == [] and evaluation["diagnostics"] == [])
                require(
                    evaluation["run_id"] == context["run_id"]
                    and evaluation["event_id"] == event["event"]["id"]
                )
                require(
                    evaluation["result_id"]
                    == identity([event["event"]["id"], context["run_id"], plan["bundle_sha256"]])
                )
                require(
                    evaluation["input"]
                    == dict(
                        cluster_id="offline",
                        topic_id="offline",
                        topic="linux-auth-offline",
                        partition=0,
                        offset=index,
                        value_sha256=sha(encoded(event)),
                    )
                )
                require(
                    evaluation["counts"]
                    == {
                        key: int(key == expectation["evaluation_outcome"])
                        for key in (
                            "matched",
                            "unmatched",
                            "inapplicable",
                            "quality_skipped",
                            "configuration_blocked",
                            "evaluation_error",
                        )
                    }
                )
                require(
                    db["source_contract"]
                    == {key: context["source_contract"][key] for key in ("id", "version")}
                )
                count += 1
            else:
                preserved = published["preservation"]
                module_validator("preservation").validate(preserved)
                require(preserved["member"]["record_id"] == raw["record_id"])
                require(preserved["member"]["raw_sha256"] == sha(encoded(raw, True)))
                require(preserved["member"]["context_sha256"] == sha(encoded(context, True)))
                require(preserved["member"]["evidence_sha256"] == sha(original))
                require(
                    preserved["id"]
                    == identity([context["run_id"], raw["record_id"], expectation["disposition"]])
                )
                require(
                    preserved["context"] == context
                    and preserved["source"] == raw["source"]
                    and preserved["run_id"] == context["run_id"]
                )
    require(count == 2)
    return dict(
        records=len(originals), normalized_eligible=count, unsupported=len(originals) - count
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    try:
        catalog = json.loads(CATALOG.read_bytes())
        rows = artifacts(catalog, args.directory)
        if args.prepare:
            prepare(catalog, rows, args.prepare)
            print(json.dumps(dict(status="prepared", records=len(rows))))
        else:
            require(args.input is not None and args.output is not None and args.plan is not None)
            print(
                json.dumps(
                    verify(catalog, rows, args.input, args.output, args.plan), sort_keys=True
                )
            )
    except Exception:
        print('{"category":"recording_qualification_failed"}', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
