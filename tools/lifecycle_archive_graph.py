"""Verify the signed lifecycle dependency graph of a checked physical archive export."""

import argparse
import base64
import binascii
import fcntl
import os
import re
import struct
import subprocess
import tempfile
import uuid
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import lifecycle as local
import lifecycle_validation as candidate
from build_worker_validator import BASE
from check_contracts import StrictValidator
from check_lifecycle_runtime import schemas
from contract_identity import record_id
from jsonschema import FormatChecker
from lifecycle_runtime import (
    DOMAINS,
    IMAGE,
    LIMITS,
    MIB,
    ROOT,
    Runtime,
    checked,
    identity,
    worker_binding,
)
from lifecycle_validation import decode, encoded, sha

RUNTIME = "055a7fcbbb144d3f9a62fac5a7537d58f8b48ab0fae4684343d085911156841d"
VALIDATOR = "f2a11f42978b2f609bbf0dba8246f4ba4adfb00633fff4226c2996cea424ef4d"
PROOF = ROOT / "tools/LifecycleArchiveSignatures.java"
COMMON = (
    "version",
    "deployment_id",
    "authority_id",
    "authority_key_sha256",
    "runtime_sha256",
    "producer_sha256",
    "image",
    "compatibility_sha256",
    "limits",
    "validator",
)
INNER = {
    "tagged": ("integration:1.1.0:tagged-event", "processing_id"),
    "detection": ("integration:1.1.0:detection", "detection_id"),
    "processing": ("integration:1.1.0:diagnostic", "diagnostic_id"),
    "manifest": ("linux:1.0.0:manifest", "manifest_id"),
    "preservation": ("integration-runtime:1.0.0:preservation", "preservation_id"),
    "receipt": ("integration-runtime:1.0.0:receipt", "id"),
    "quarantine": ("integration-runtime:1.0.0:quarantine", "id"),
}


def require(condition, category):
    if not condition:
        raise ValueError("lifecycle_archive_" + category)


def manifest_for(runtime, archive_id, objects):
    return deployment_manifest(runtime.root, archive_id, objects)


def deployment_manifest(root, archive_id, objects):
    """Verify the committed public journal prefix without invoking controller recovery."""
    root = local.path_safe(root)
    require(
        root.stat().st_uid == os.getuid() and root.stat().st_mode & 0o777 == 0o700,
        "deployment_permissions",
    )
    with local.regular(root / ".lock").open("rb") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        config = checked(root / "config.json")
        head = checked(root / "head.json")
        sequence = head["sequence"]
        require(type(sequence) is int and 0 < sequence <= 524288, "journal_count")
        journal = local.path_safe(root / "journal")
        require(len(list(journal.iterdir())) == sequence, "journal_count")
        previous = None
        broker: dict[str, Any] = {}
        workers: dict[str, dict] = {}
        for index in range(1, sequence + 1):
            entry = checked(journal / f"{index:020d}.json")
            require(
                set(entry) == {"sequence", "previous_sha256", "kind", "value"}
                and entry["sequence"] == index
                and entry["previous_sha256"] == previous,
                "journal_chain",
            )
            kind, value = entry["kind"], entry["value"]
            if kind == "broker":
                require(not broker, "broker_reinitialization")
                broker = dict(value)
            elif kind == "broker_topics":
                require(broker and not broker["topics"], "broker_topics")
                broker["topics"] = value["topics"]
            elif kind == "worker":
                topic = dict(name=value["input_topic"], id=value["input_topic_id"], partition=0)
                require(workers.setdefault(value["worker_id"], topic) == topic, "worker_topic")
            else:
                require(
                    kind
                    in {
                        "start",
                        "stop",
                        "launch",
                        "adopt",
                        "published",
                        "ack",
                        "ack_rejected",
                        "ack_cursor",
                        "injection",
                        "admit",
                        "qualification_batch_intent",
                        "qualification_batch_result",
                    },
                    "unknown_journal_graph",
                )
            previous = identity(entry)
        require(previous == head["sha256"] and broker and workers, "journal_head")
        return dict(
            version="lifecycle-archive/1",
            archive_id=str(archive_id),
            common={key: config[key] for key in COMMON}
            | dict(cluster_id=broker["cluster_id"], topics=broker["topics"]),
            authority_public_key=config["authority_public_key"],
            workers=[
                dict(worker_id=worker, input_topic=workers[worker]) for worker in sorted(workers)
            ],
            objects=objects,
        )


def binary(value):
    require(isinstance(value, str), "base64")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("lifecycle_archive_base64") from None
    require(base64.b64encode(raw).decode() == value, "base64")
    return raw


@lru_cache(maxsize=1)
def validators():
    documents, registry = schemas()
    return {
        name: StrictValidator(doc, registry=registry, format_checker=FormatChecker())
        for name, doc in documents.items()
    }


def schema(name, value):
    validator = validators()["urn:detectbridge:" + name]
    require(validator.is_valid(value), "schema")
    if name == "integration-runtime:1.0.0:input" and value["kind"] == "windows_record":
        windows_context(value)


def windows_context(row):
    """The P13 input schema delegates the Windows context shape to its pinned adapter."""
    c = row["context"]
    raw = row["raw"]
    required = {
        "version",
        "run_id",
        "source",
        "first_observed",
        "source_contract",
        "mapping_profile",
        "parser",
    }
    require(
        required <= c.keys() <= required | {"receipt", "host_binding", "source_generation"}
        and c["source"] == raw["source"]
        and c["first_observed"] == raw["first_observed"]
        and c["version"] == "1.0.0"
        and c["parser"] == {"id": "windows-xml", "version": "1.0.0"},
        "windows_context",
    )
    source, mapping = c["source_contract"], c["mapping_profile"]
    require(
        set(source) == {"id", "version", "sha256", "snapshot"}
        and set(mapping) == {"id", "version", "sha256", "declaration"},
        "windows_profile",
    )
    family = {"windows-security-4688-xml": "security", "windows-sysmon-process-xml": "sysmon"}.get(
        source["id"]
    )
    require(family is not None, "windows_profile")
    profiles = ROOT / "packages/windows-adapters/profiles"
    expected = decode((profiles / f"{family}.source.json").read_bytes())
    declared = decode((profiles / f"{family}.mapping.json").read_bytes())
    require(
        source["snapshot"] == expected
        and source["sha256"] == identity(expected)
        and source["version"] == expected["version"]
        and mapping
        == {**{k: declared[k] for k in ("id", "version", "sha256")}, "declaration": declared},
        "windows_profile",
    )
    if "host_binding" in c:
        host = c["host_binding"]
        require(
            set(host)
            == {"host_id", "computer", "source", "revision", "sha256", "provenance", "kind"}
            and host["source"] == raw["source"]
            and identity({k: v for k, v in host.items() if k != "sha256"}) == host["sha256"],
            "windows_host_binding",
        )
    if "source_generation" in c:
        keys = c["source_generation"].keys()
        require(
            {"id", "provenance"} <= keys <= {"id", "provenance", "command_line_capture"},
            "windows_generation",
        )
    if "receipt" in c:
        require(c["receipt"].keys() <= {"received", "processed"}, "windows_receipt")


def check_compiler(plan, descriptor):
    """Run the original installed compiler in its independently built, networkless image."""
    trusted_tag = "detectbridge-validator:" + VALIDATOR[:20]
    image = (
        subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", trusted_tag],
            capture_output=True,
            check=True,
            timeout=20,
        )
        .stdout.decode()
        .strip()
    )
    require(image == descriptor["image_id"], "validator_image")
    Runtime._verify_validator_image(descriptor)
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0,'/opt/validator/tools'); "
        "from lifecycle_worker_validator import verify_install, validate_plan; "
        "verify_install(Path('/opt/validator'),sys.argv[1]); "
        "\ntry:\n validate_plan(sys.stdin.buffer.read(4194305))"
        "\nexcept ValueError as error:\n"
        " sys.exit(42 if str(error) == 'lifecycle_plan_compilation_mismatch' else 43)"
    )
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=512m",
            "--pids-limit=64",
            "--cpus=1",
            "--tmpfs=/tmp:size=32m,noexec,nosuid,nodev",
            "--entrypoint=python",
            image,
            "-I",
            "-c",
            script,
            VALIDATOR,
        ],
        input=plan,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    require(result.returncode not in (42, 43), "compiler_rejected")
    require(result.returncode == 0, "validator_unavailable")


def signed(domain, wrapper, key, proofs):
    schema("lifecycle-runtime:1.0.0:" + domain, wrapper)
    public = binary(key)
    require(len(public) == 44 and sha(public) == wrapper["key_sha256"], "public_key")
    body = wrapper["payload"]
    proofs.append(
        (public, DOMAINS[domain].encode() + b"\0" + encoded(body), binary(wrapper["signature"]))
    )
    return body


def verify_signatures(proofs):
    require(0 < len(proofs) <= 4096, "signature_count")
    packet = bytearray(struct.pack(">I", len(proofs)))
    for proof in proofs:
        for field in proof:
            packet.extend(struct.pack(">I", len(field)))
            packet.extend(field)
    result = subprocess.run(
        [ROOT / ".cache/jdk/bin/java", "-Xmx96m", PROOF],
        input=packet,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    require(result.returncode == 0, "invalid_signature")


def controls(rows, catalog, common, key, proofs):
    commands: dict[str, dict] = {}
    registrations = {}
    previous = None
    requests = set()
    incarnations: dict[str, tuple[str, str]] = {}
    run_owners: dict[str, str] = {}
    targets = set()
    last_target = None
    for _, _, wrapper in rows:
        body = signed("control", wrapper, key, proofs)
        proposal = body["proposal"]
        command = identity(body)
        if command in commands:
            continue
        require(
            body["revision"] == len(commands) + 1
            and body["previous_control_sha256"] == previous
            and body["runtime_binding_sha256"] == identity(common)
            and body["proposal_sha256"] == identity(proposal)
            and proposal["request_id"] not in requests
            and all(body[k] == common[k] == proposal[k] for k in ("deployment_id", "authority_id"))
            and proposal["compatibility_sha256"] == common["compatibility_sha256"],
            "command_chain",
        )
        pairs = []
        keys = set()
        for reg in body["registrations"]:
            worker = reg["worker_id"]
            incarnation = reg["incarnation"]
            topic = catalog.get(worker)
            require(
                topic == dict(name=reg["input_topic"], id=reg["input_topic_id"], partition=0)
                and incarnations.setdefault(incarnation, (worker, reg["public_key"]))
                == (worker, reg["public_key"])
                and reg["public_key"] not in keys
                and reg["assigned_runs"] == sorted(set(reg["assigned_runs"]))
                and all(
                    run_owners.setdefault(run, worker) == worker for run in reg["assigned_runs"]
                ),
                "registration",
            )
            keys.add(reg["public_key"])
            pairs.append(dict(worker_id=worker, incarnation=incarnation))
            registrations[command, worker, incarnation] = reg
        require(
            pairs == proposal["participants"]
            and [x["worker_id"] for x in pairs] == sorted({x["worker_id"] for x in pairs})
            and len(incarnations) <= 256
            and all(list(run_owners.values()).count(w) <= 16 for w in catalog),
            "membership",
        )
        target = proposal["bundle_sha256"]
        require(proposal["action"] != "rollback" or target in targets, "rollback")
        require(proposal["action"] != "membership" or target == last_target, "membership_target")
        requests.add(proposal["request_id"])
        targets.add(target)
        commands[command] = body
        previous, last_target = command, target
    require(commands, "commands_missing")
    return commands, registrations


def bundles(rows, common, key, proofs):
    members: dict[tuple[str, str], tuple[int, int, str]] = {}
    grouped: dict[tuple[str, str], dict[int, bytes]] = defaultdict(dict)
    for _, _, wrapper in rows:
        body = signed("artifact", wrapper, key, proofs)
        bundle = body["bundle_sha256"]
        require(
            body["runtime_binding_sha256"] == identity(common)
            and all(body[k] == common[k] for k in ("deployment_id", "authority_id")),
            "artifact_scope",
        )
        name = body["member"]
        size, index = body["member_bytes"], body["chunk_index"]
        maximum = 256 * 1024
        count = (size + maximum - 1) // maximum
        piece = binary(body["data_base64"])
        header = (size, count, body["member_sha256"])
        require(
            count == body["chunk_count"]
            and index < count
            and len(piece) == min(maximum, size - index * maximum)
            and sha(piece) == body["chunk_sha256"]
            and members.setdefault((bundle, name), header) == header
            and grouped[bundle, name].setdefault(index, piece) == piece,
            "chunk_conflict",
        )
    result = {}
    for bundle in {b for b, _ in members}:
        files = {}
        for name in ("manifest.json", "plan.json"):
            require((bundle, name) in members, "missing_member")
            size, count, digest = members[bundle, name]
            pieces = grouped[bundle, name]
            require(set(pieces) == set(range(count)), "missing_chunk")
            data = b"".join(pieces[i] for i in range(count))
            require(len(data) == size and sha(data) == digest, "member_digest")
            files[name] = data
        manifest = decode(files["manifest.json"])
        require(
            manifest == candidate.bundle(files["plan.json"])
            and manifest["bundle_sha256"] == bundle
            and manifest["compatibility_sha256"] == common["compatibility_sha256"],
            "bundle_binding",
        )
        result[bundle] = dict(manifest=manifest, plan=files["plan.json"])
    return result


def acknowledgments(rows, commands, registrations, common, proofs):
    seen: dict[str, dict] = {}
    applied = set()
    for _, key, wrapper in rows:
        schema("lifecycle-runtime:1.0.0:ack", wrapper)
        p = wrapper["payload"]
        command = commands.get(p["command_sha256"])
        reg = registrations.get((p["command_sha256"], p["worker_id"], p["incarnation"]))
        require(command and reg, "ack_registration")
        signed("ack", wrapper, reg["public_key"], proofs)
        fields = (
            "deployment_id",
            "authority_id",
            "worker_id",
            "incarnation",
            "revision",
            "command_sha256",
            "bundle_sha256",
            "compatibility_sha256",
            "phase",
            "checkpoint_id",
            "category",
        )
        ack_id = "sha256:" + identity([DOMAINS["ack"], *(p[k] for k in fields)])
        require(
            all(
                p[k] == common[k] for k in ("deployment_id", "authority_id", "compatibility_sha256")
            )
            and p["revision"] == command["revision"]
            and p["bundle_sha256"] == command["proposal"]["bundle_sha256"]
            and key == ack_id.encode()
            and p["ack_id"] == ack_id
            and seen.setdefault(ack_id, wrapper) == wrapper,
            "ack_identity",
        )
        if p["phase"] in {"applied", "durable"}:
            applied.add((p["command_sha256"], p["worker_id"], p["incarnation"]))
    return applied


def check_members(raw, objects, registered):
    require(raw["record_id"] == record_id(raw["source"], raw["cursor"]), "raw_identity")
    e = raw["evidence"]
    if "inline" in e:
        data = e["inline"].encode() if e["encoding"] == "utf-8" else binary(e["inline"])
    else:
        ref = e["reference"]
        digest = ref["object_sha256"]
        require(digest in registered, "unregistered_original")
        data = candidate.read(objects / digest, 32 * MIB)
        require(sha(data) == digest, "original_digest")
        if "byte_range" in ref:
            start, size = (ref["byte_range"][k] for k in ("offset", "length"))
            require(0 <= start < len(data) and 0 < size <= len(data) - start, "original_range")
            data = data[start : start + size]
    require(sha(data) == e["sha256"], "evidence_digest")


def semantic_hash(envelope):
    # Mirrors the B1 wire projection. Only the documented receipt clocks are observational.
    from copy import deepcopy

    body = deepcopy(envelope["document"])
    kind = envelope["kind"]
    if kind == "tagged":
        event = body["event"]
        event["event"].pop("ingested", None)
        times = event["detectbridge"].get("time", {})
        times.pop("received", None)
        times.pop("processed", None)
        ext = event["detectbridge"].get("extensions", {})
        require(set(ext) <= {"linux.context"}, "unknown_extension")
        if "linux.context" in ext:
            schema("linux:1.0.0:context-extension", ext["linux.context"])
            ext["linux.context"]["context"].pop("receipt", None)
    if kind in ("tagged", "detection") and body.get("manifest") is not None:
        body["manifest"] = dict(semantic_sha256=body["manifest"]["semantic_sha256"])
    fields = (
        "deployment_id",
        "worker_id",
        "origin_incarnation",
        "revision",
        "command_sha256",
        "bundle_sha256",
        "plan_sha256",
        "compatibility_sha256",
        "kind",
        "inner_key",
    )
    return identity({k: envelope[k] for k in fields} | dict(document=body))


def physical_output(envelope, inputs, locations, common, topic, registry):
    doc = envelope["document"]
    ref = doc["input"]
    coord = (ref["topic"], ref["offset"])
    require(ref == locations.get(coord) and ref["topic_id"] == topic["id"], "physical_origin")
    binding = worker_binding(
        dict(
            runtime_binding_sha256=identity(common),
            worker_id=envelope["worker_id"],
            topics=dict(input=topic),
            evidence_registry_sha256=registry,
        )
    )
    preimage = [
        binding,
        *(ref[k] for k in ("cluster_id", "topic_id", "partition", "offset", "value_sha256")),
    ]
    if envelope["kind"] == "receipt":
        row = inputs.get(coord)
        require(
            row is not None
            and doc["action"] == row["kind"]
            and doc.get("record_id") == row.get("raw", {}).get("record_id"),
            "receipt_source",
        )
        require(doc["id"] == "sha256:" + identity([*preimage, "receipt"]), "receipt_id")
        return row.get("context", row).get("run_id")
    require(doc["id"] == "sha256:" + identity([*preimage, "invalid_input"]), "quarantine_id")
    return None


def outputs(rows, commands, regs, closures, common, catalog, inputs, locations, registry):
    verified = {}
    seen: dict[str, str] = {}
    for coord, key, env in rows:
        schema("lifecycle-runtime:1.0.0:output", env)
        kind, doc = env["kind"], env["document"]
        require(len(encoded(doc)) <= 2 * MIB, "document_size")
        schema_id, inner_key = INNER[kind]
        schema(schema_id, doc)
        cmd = commands.get(env["command_sha256"])
        reg = regs.get((env["command_sha256"], env["worker_id"], env["origin_incarnation"]))
        require(cmd and reg and env["bundle_sha256"] in closures, "output_closure")
        closure = closures[env["bundle_sha256"]]["manifest"]
        fields = ("deployment_id", "worker_id", "revision", "command_sha256", "kind", "inner_key")
        oid = "sha256:" + identity(["detectbridge.p15b.output/1", *(env[k] for k in fields)])
        require(
            key == oid.encode()
            and env["output_id"] == oid
            and env["inner_key"] == doc[inner_key]
            and env["deployment_id"] == common["deployment_id"]
            and env["revision"] == cmd["revision"]
            and env["bundle_sha256"] == cmd["proposal"]["bundle_sha256"]
            and env["compatibility_sha256"] == closure["compatibility_sha256"]
            and env["plan_sha256"] == closure["plan"]["sha256"]
            and env["document_sha256"] == identity(doc)
            and env["semantic_sha256"] == semantic_hash(env)
            and seen.setdefault(oid, env["semantic_sha256"]) == env["semantic_sha256"],
            "output_attribution",
        )
        run = doc.get("run_id")
        if kind in ("tagged", "detection", "processing"):
            require(
                doc["attribution"]["bundle_sha256"] == closure["plan"]["bundle_sha256"],
                "decision_plan",
            )
        if kind == "tagged":
            run = doc["event"]["detectbridge"]["run_id"]
        elif kind == "manifest":
            run = doc["key"]["run_id"]
            require(
                doc["manifest_id"]
                == "sha256:" + identity({k: v for k, v in doc.items() if k != "manifest_id"}),
                "manifest_id",
            )
        elif kind == "preservation":
            require(doc["adapter"] == "linux", "unknown_preservation_graph")
            schema("linux:1.0.0:preservation", doc["diagnostic"])
        elif kind in ("receipt", "quarantine"):
            run = physical_output(
                env, inputs, locations, common, catalog[env["worker_id"]], registry
            )
        require(run is None or run in reg["assigned_runs"], "output_run")
        verified[coord] = env
    return verified


def verify(manifest, rows, objects):
    """Consume only a successfully verified export and its immutable object copies."""
    common = manifest["common"]
    require(manifest["version"] == "lifecycle-archive/1" and len(rows) <= 4096, "profile")
    require(
        set(common) == {*COMMON, "topics", "cluster_id"}
        and common["authority_key_sha256"] == sha(binary(manifest["authority_public_key"]))
        and common["image"] == IMAGE
        and common["runtime_sha256"] == RUNTIME
        and common["producer_sha256"] == candidate.PIN
        and common["limits"] == LIMITS
        and common["validator"]["base_image"] == BASE
        and common["validator"]["artifact_sha256"] == VALIDATOR,
        "processing_profile",
    )
    objects = candidate.safe(objects)
    inventory = defaultdict(list)
    for obj in manifest["objects"]:
        digest = obj["sha256"]
        require(re.fullmatch("[0-9a-f]{64}", digest), "object_digest")
        require(sha(candidate.read(objects / digest, 64 * MIB)) == digest, "object_digest")
        inventory[obj["kind"]].append(digest)
    require(
        inventory["runtime"] == [RUNTIME]
        and inventory["producer"] == [candidate.PIN]
        and inventory["validator"] == [VALIDATOR]
        and len(inventory["registry"]) == 1,
        "executable_inventory",
    )
    registry = inventory["registry"][0]
    registry_doc = decode(candidate.read(objects / registry, MIB))
    schema("integration-runtime:1.0.0:registration", registry_doc)
    require(
        identity(registry_doc) == registry
        and sorted(o["sha256"] for o in registry_doc["objects"]) == sorted(inventory["original"]),
        "object_registry",
    )
    catalog = {r["worker_id"]: r["input_topic"] for r in manifest["workers"]}
    roles = {v["name"]: k for k, v in common["topics"].items()}
    roles.update({v["name"]: "input" for v in catalog.values()})
    ids = {v["name"]: v["id"] for v in [*catalog.values(), *common["topics"].values()]}
    by_role = defaultdict(list)
    inputs, locations = {}, {}
    size = 0
    previous: dict[str, int] = {}
    for row in rows:
        name = row["topic"]
        offset = row["offset"]
        coord = (name, offset)
        require(
            row["topic_id"] == ids.get(name)
            and row["partition"] == 0
            and type(offset) is int
            and offset > previous.get(name, -1),
            "wire_location",
        )
        previous[name] = offset
        raw = binary(row["value"]) if row["value"] is not None else b""
        key = binary(row["key"]) if row["key"] is not None else None
        size += len(raw) + len(key or b"") + sum(len(encoded(h)) for h in row["headers"])
        require(size <= 64 * MIB, "graph_size")
        role = roles[name]
        limit = {
            "input": 2 * MIB,
            "output": 2 * MIB + 65536,
            "ack": 65536,
            "control": 65536,
            "artifact": 512 * 1024,
        }[role]
        require(len(raw) <= limit, "semantic_wire_limit")
        doc = decode(raw)
        if role == "input":
            schema("integration-runtime:1.0.0:input", doc)
            if "raw" in doc:
                check_members(doc["raw"], objects, inventory["original"])
            inputs[coord] = doc
            locations[coord] = dict(
                cluster_id=common["cluster_id"],
                topic_id=ids[name],
                topic=name,
                partition=0,
                offset=offset,
                value_sha256=sha(raw),
            )
        else:
            by_role[role].append((coord, key, doc))
    proofs: list[tuple[bytes, bytes, bytes]] = []
    authority = manifest["authority_public_key"]
    commands, regs = controls(by_role["control"], catalog, common, authority, proofs)
    closures = bundles(by_role["artifact"], common, authority, proofs)
    applied = acknowledgments(by_role["ack"], commands, regs, common, proofs)
    verify_signatures(proofs)
    for closure in closures.values():
        check_compiler(closure["plan"], common["validator"])
    require(
        all(c["proposal"]["bundle_sha256"] in closures for c in commands.values()), "missing_bundle"
    )
    checked = outputs(
        by_role["output"], commands, regs, closures, common, catalog, inputs, locations, registry
    )
    for env in checked.values():
        require(
            (env["command_sha256"], env["worker_id"], env["origin_incarnation"]) in applied,
            "missing_application_ack",
        )
    return dict(commands=commands, bundles=closures, outputs=checked, inputs=inputs)


def prepare(deployment, destination, registry, originals, provenance):
    """Materialize only registered originals, explicit provenance and public artifacts."""
    destination, deployment, registry, originals = map(
        local.path_safe, (destination, deployment, registry, originals)
    )
    local.disjoint(deployment, destination)
    local.disjoint(deployment, originals)
    local.disjoint(deployment, registry)
    local.disjoint(originals, destination)
    require(not destination.exists() and destination.parent.is_dir(), "fresh_destination")
    registration = local.read(registry, MIB)
    doc = decode(registration)
    schema("integration-runtime:1.0.0:registration", doc)
    require(encoded(doc) == registration and originals.is_dir(), "registration")
    require(sum(m["size_bytes"] for m in doc["objects"]) <= 64 * MIB, "registry_limit")
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".archive-prepare-") as private:
        stage = Path(private) / "catalog"
        stage.mkdir(mode=0o700)
        directory = stage / "objects"
        directory.mkdir(mode=0o700)
        objects: list[dict[str, Any]] = []
        total = 0

        def retain(kind, data):
            nonlocal total
            digest = sha(data)
            total += len(data)
            require(
                len(objects) < 128 and total < 2 * 1024 * MIB and not (directory / digest).exists(),
                "object_inventory",
            )
            local.write_exclusive(directory / digest, data)
            objects.append(dict(kind=kind, sha256=digest))

        retain("registry", registration)
        for entry in doc["objects"]:
            digest = entry["sha256"]
            data = local.read(originals / digest, 32 * MIB)
            require(len(data) == entry["size_bytes"] and sha(data) == digest, "original_digest")
            retain("original", data)
        for source in provenance:
            source = local.regular(source)
            local.disjoint(source, deployment)
            retain("provenance", local.read(source, 32 * MIB))
        for kind, name, expected in (
            ("runtime", "runtime.jar", RUNTIME),
            ("producer", "producer.jar", candidate.PIN),
            ("validator", "compiler.tar", VALIDATOR),
        ):
            data = local.read(deployment / "artifacts" / name, 64 * MIB)
            require(sha(data) == expected, "processing_profile")
            retain(kind, data)
        manifest = deployment_manifest(deployment, uuid.uuid4(), objects)
        local.write_exclusive(stage / "manifest.json", encoded(manifest))
        local.sync_directory(directory)
        local.sync_directory(stage)
        stage.rename(destination)
        local.sync_directory(destination.parent)
    return manifest["archive_id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    command = sub.add_parser("prepare")
    command.add_argument("deployment", type=Path)
    command.add_argument("destination", type=Path)
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--originals", type=Path, required=True)
    command.add_argument("--provenance", type=Path, action="append", required=True)
    args = parser.parse_args()
    print(
        prepare(args.deployment, args.destination, args.registry, args.originals, args.provenance)
    )


if __name__ == "__main__":
    main()
