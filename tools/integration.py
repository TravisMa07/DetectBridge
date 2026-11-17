"""Exclusive P13b Kafka/Flink lifecycle and independent failure qualification."""

import argparse
import base64
import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from check_contracts import load_json
from detection import Detection
from integration_cases import (
    ROOT,
    digest,
)
from jsonschema import Draft202012Validator, FormatChecker
from stack import DEPLOY, StackError, project_lock, run, save
from transport import Transport, java_env

CACHE = ROOT / ".cache/integration-runtime"
BUILDS = ROOT / ".cache/integration-build"
INPUT = "detectbridge.integration.input.v1"
ROUTES = {
    "tagged": "detectbridge.tagged-events.v1",
    "detection": "detectbridge.detections.v1",
    "processing": "detectbridge.processing-diagnostics.v1",
    "manifest": "detectbridge.integration.manifests.v1",
    "preservation": "detectbridge.integration.preservation.v1",
    "quarantine": "detectbridge.integration.quarantine.v1",
    "receipt": "detectbridge.integration.receipts.v1",
}
TOPICS = [INPUT, *ROUTES.values()]


def build(plan_path=None):
    run(
        [
            ROOT / "gradlew",
            ":linux-adapters:test",
            ":integration-job:test",
            ":integration-job:shadowJar",
        ],
        env=java_env(),
        timeout=600,
    )
    from integration_cases import prepare

    prepare()
    plan = Path(plan_path) if plan_path is not None else ROOT / ".cache/integration/plan.json"
    jar = ROOT / "packages/integration-job/build/libs/integration-job.jar"
    dockerfile, logger = DEPLOY / "integration.Dockerfile", DEPLOY / "transport-log4j.properties"
    from stack import Stack

    if dockerfile.read_text().splitlines()[0] != "FROM " + Stack().image("flink"):
        raise StackError("integration_base_image_mismatch")
    fingerprint = hashlib.sha256(
        jar.read_bytes() + dockerfile.read_bytes() + logger.read_bytes() + plan.read_bytes()
    ).hexdigest()
    directory = BUILDS / fingerprint
    directory.mkdir(parents=True, exist_ok=True)
    for source, name in (
        (jar, "integration-job.jar"),
        (plan, "plan.json"),
        (dockerfile, "Dockerfile"),
        (logger, "log4j-console.properties"),
    ):
        shutil.copyfile(source, directory / name)
    image = "detectbridge-integration:" + fingerprint
    run(
        [
            "docker",
            "build",
            "--label",
            "io.detectbridge.bundle_sha256=" + fingerprint,
            "--tag",
            image,
            directory,
        ],
        timeout=600,
    )
    metadata = json.loads(run(["docker", "image", "inspect", image]).stdout)[0]
    sha = hashlib.sha256(jar.read_bytes()).hexdigest()
    bundle = dict(
        bundle_sha256=fingerprint,
        jar_sha256=sha,
        publisher_sha256=sha,
        image=image,
        image_id=metadata["Id"],
        platform="linux/" + metadata["Architecture"],
    )
    save(BUILDS / "bundle.json", bundle)
    return dict(status="built", bundle=bundle)


class Integration(Detection):
    def __init__(self, project):
        if not re.fullmatch(r"detectbridge-p13-[a-z0-9-]+", project):
            raise StackError("dedicated_integration_project_required")
        self.mapped, self.cache, self.builds = False, CACHE, BUILDS
        self.input, self.output, self.quarantine, self.topics = (
            INPUT,
            ROUTES["tagged"],
            ROUTES["quarantine"],
            TOPICS,
        )
        Transport.__init__(self, project)
        self.folder = CACHE / project
        if self.folder.is_symlink():
            raise StackError("unsafe_integration_state")

    def config(self):
        value = load_json(self.folder / "configuration.json")
        Draft202012Validator(
            load_json(ROOT / "contracts/integration-runtime/v1/integration-runtime.schema.json"),
            format_checker=FormatChecker(),
        ).validate(value)
        if (
            value.get("runtime") != "integration/1.0.0"
            or value["project"] != self.project
            or set(value["broker"]["topics"]) != set(TOPICS)
        ):
            raise StackError("integration_configuration_mismatch")
        if (self.folder / "configuration.sha256").read_text().strip() != digest(value):
            raise StackError("configuration_checksum_mismatch")
        self.bundle(value["bundle"])
        if self.qualification_plan(value)["bundle_sha256"] != value["evaluation_bundle_sha256"]:
            raise StackError("integration_plan_changed")
        return value

    def process_args(self, command, *args, config=None):
        replacements = {
            "/opt/detectbridge/detection-job.jar:/opt/flink/lib/*": "/opt/detectbridge/integration-job.jar:/opt/flink/lib/*",
            "io.detectbridge.detection.DetectionPublisher": "io.detectbridge.integration.IntegrationPublisher",
        }
        return [
            replacements.get(str(value), value)
            for value in super().process_args(command, *args, config=config)
        ]

    def init(self, profile="default", objects=None):
        existing = (self.folder / "configuration.json").exists()
        result = super().init()
        if not existing:
            value = load_json(self.folder / "configuration.json")
            entries: list[dict[str, Any]] = []
            target = self.folder / "objects"
            target.mkdir(mode=0o755)
            target.chmod(0o755)
            if objects is not None:
                total = 0
                for original in Path(objects).resolve().iterdir():
                    if (
                        len(entries) >= 128
                        or original.is_symlink()
                        or not original.is_file()
                        or not re.fullmatch("[a-f0-9]{64}", original.name)
                    ):
                        raise StackError("integration_invalid_object_registration")
                    with original.open("rb") as file:
                        data = file.read(32 * 1024 * 1024 + 1)
                    total += len(data)
                    if (
                        not data
                        or len(data) > 32 * 1024 * 1024
                        or total > 64 * 1024 * 1024
                        or hashlib.sha256(data).hexdigest() != original.name
                    ):
                        raise StackError("integration_invalid_object_registration")
                    destination = target / original.name
                    destination.write_bytes(data)
                    destination.chmod(0o444)
                    entries.append(dict(sha256=original.name, size_bytes=len(data)))
            registration = dict(
                version="1.0.0", objects=sorted(entries, key=lambda entry: entry["sha256"])
            )
            manifest = self.folder / "object-registration.json"
            save(manifest, registration)
            manifest.chmod(0o444)
            overlay_path = self.stack.folder / "transport.compose.json"
            overlay = load_json(overlay_path)
            state = self.stack.load()
            for service in ("jobmanager", "taskmanager"):
                overlay["services"][service]["volumes"] = [
                    dict(
                        type="bind",
                        source=str(target.resolve()),
                        target="/opt/detectbridge/objects",
                        read_only=True,
                    ),
                    dict(
                        type="bind",
                        source=str(manifest.resolve()),
                        target="/opt/detectbridge/object-registration.json",
                        read_only=True,
                    ),
                ]
            save(overlay_path, overlay)
            state["transport_overlay_sha256"] = hashlib.sha256(
                overlay_path.read_bytes()
            ).hexdigest()
            save(self.stack.folder / "state.json", state)
            value["evidence_registry_sha256"] = digest(registration)
            self.stack.up("core")
            value.update(
                evaluation_bundle_sha256=self.qualification_plan(value)["bundle_sha256"],
                runtime="integration/1.0.0",
                limits_profile=profile,
                consumer_group="detectbridge-integration-v1-" + value["pipeline_id"],
            )
            save(self.folder / "configuration.json", value)
            (self.folder / "configuration.sha256").write_text(digest(value) + "\n")
        elif self.config()["limits_profile"] != profile:
            raise StackError("immutable_integration_profile")
        return result

    def qualification_plan(self, config=None):
        config = self.config() if config is None else config
        folder = BUILDS / config["bundle"]["bundle_sha256"]
        material = b"".join(
            (folder / name).read_bytes()
            for name in (
                "integration-job.jar",
                "Dockerfile",
                "log4j-console.properties",
                "plan.json",
            )
        )
        if hashlib.sha256(material).hexdigest() != config["bundle"]["bundle_sha256"]:
            raise StackError("integration_build_inputs_changed")
        return load_json(folder / "plan.json")

    def start(self, restore=None, from_beginning=False):
        config = self.config()
        self.verify_destination(config)
        if from_beginning:
            raise StackError("integration_replay_requires_explicit_new_run")
        if restore and from_beginning:
            raise StackError("conflicting_restore_options")
        if any(
            j["state"] not in ("FINISHED", "FAILED", "CANCELED", "SUSPENDED")
            for j in self.rest("/jobs/overview").get("jobs", [])
        ):
            raise StackError("job_already_active")
        if self.latest_job() and not restore and not from_beginning:
            raise StackError("explicit_restore_or_from_beginning_required")
        command = ["/opt/flink/bin/flink", "run", "-d"]
        if restore:
            match = re.fullmatch(
                r"file:/+(state/checkpoints/([0-9a-f]{32})/chk-[0-9]+)(?:/_metadata)?/?", restore
            )
            parsed = urlsplit(restore)
            if (
                not match
                or parsed.netloc
                or parsed.query
                or parsed.fragment
                or match[2] not in {j["job_id"] for j in self.jobs()["jobs"]}
            ):
                raise StackError("unsafe_checkpoint_uri")
            path = "/" + match[1] + "/_metadata"
            self.stack.exec("jobmanager", "test", "-s", path)
            command += ["-s", "file://" + path]
        command += [
            "-c",
            "io.detectbridge.integration.IntegrationJob",
            "/opt/detectbridge/integration-job.jar",
            "kafka:9092",
            config["consumer_group"],
            config["broker"]["cluster_id"],
            *[config["broker"]["topics"][t]["id"] for t in TOPICS],
            config["bundle"]["jar_sha256"],
            config["limits_profile"],
            config["evidence_registry_sha256"],
        ]
        response = self.stack.exec("jobmanager", *command)
        match = re.search(r"JobID ([0-9a-f]{32})", response)
        if not match:
            raise StackError("missing_submitted_job_id")
        job = dict(
            job_id=match[1],
            bundle_sha256=config["bundle"]["bundle_sha256"],
            restored_from=restore,
            from_beginning=from_beginning,
        )
        history = self.jobs()
        history["jobs"].append(job)
        save(self.folder / "jobs.json", history)
        self.wait_checkpoint(job["job_id"])
        return job

    def inject_rows(self, values):
        config = self.config()
        self.verify_destination(config)
        ipc = "".join(
            json.dumps(
                dict(
                    sequence=i,
                    key=None,
                    value=base64.b64encode(value).decode() if value is not None else None,
                )
            )
            + "\n"
            for i, value in enumerate(values)
        )
        result = self.helper_run(self.process_args("inject", INPUT), timeout=120, data=ipc)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        acks = [row for row in rows if row.get("type") == "ack"]
        if len(acks) != len(values) or rows[-1].get("count") != len(values):
            raise StackError("integration_missing_ack")
        return acks

    def outputs(self):
        info = self.broker()
        result = []
        for kind, topic in ROUTES.items():
            end = info["end_offsets"][topic]
            if not end:
                continue
            read = self.private_read(self.process_args("read", topic, "0", str(end)), timeout=90)
            for line in read.stdout.splitlines():
                wire = json.loads(line)
                if "value" in wire:
                    result.append((kind, wire, json.loads(base64.b64decode(wire["value"]))))
        return result

    def fault(self, kind, value):
        self.helper_run(
            self.process_args("sink-policy", ROUTES[kind], "1" if value == "2" else "4194304"),
            timeout=90,
        )


def runtime_binding(config):
    # Same source defaults, independently serialized with the P13 destination and policy boundary.
    limits = dict(
        members=256,
        groupBytes=1048576,
        openGroups=1024,
        pendingBytes=33554432,
        ageMillis=30000,
        runs=16,
        closedKeys=100000,
        closedBytes=33554432,
    )
    if config["limits_profile"] == "limits":
        limits.update(
            members=2,
            groupBytes=512,
            openGroups=2,
            pendingBytes=32768,
            runs=2,
            closedKeys=4,
            closedBytes=65536,
        )
    elif config["limits_profile"] == "bytes":
        limits["pendingBytes"] = 12000
    return digest(
        dict(
            version="1.0.0",
            artifact=config["bundle"]["jar_sha256"],
            group=config["consumer_group"],
            cluster=config["broker"]["cluster_id"],
            topics={t: config["broker"]["topics"][t]["id"] for t in TOPICS},
            limits=limits,
            queue_bytes=33554432,
            queue_count=128,
            evidence_registry=config["evidence_registry_sha256"],
            profiles=dict(
                bundle=config["evaluation_bundle_sha256"],
                evaluator="detectbridge-java/2.0.0",
                selector="source-index/1.0.0",
                pipeline="p13-runtime/1.0.0",
            ),
        )
    )


def checkpoint_inventory(test, checkpoint):
    match = re.fullmatch(
        r"file:/+state/checkpoints/([0-9a-f]{32})/chk-[0-9]+/?(?:_metadata)?",
        checkpoint["external_path"],
    )
    if not match:
        raise StackError("unsafe_checkpoint_uri")
    job = match[1]
    completed = test.rest("/jobs/" + job + "/checkpoints").get("history", [])
    if not any(c["id"] == checkpoint["id"] and c["status"] == "COMPLETED" for c in completed):
        raise StackError("unconfirmed_integration_checkpoint")
    data = test.stack.exec(
        "jobmanager", "cat", f"/state/integration-evidence/{job}/checkpoint-{checkpoint['id']}.json"
    )
    inventory = json.loads(data)
    if inventory["checkpoint_id"] != checkpoint["id"] or inventory["binding"] != runtime_binding(
        test.config()
    ):
        raise StackError("integration_inventory_mismatch")
    return inventory


def reject_incompatible(test):
    config = test.config()
    checkpoint = test.retained_checkpoint(test.latest_job()["job_id"])
    command = [
        "/opt/flink/bin/flink",
        "run",
        "-d",
        "-s",
        checkpoint["external_path"],
        "-c",
        "io.detectbridge.integration.IntegrationJob",
        "/opt/detectbridge/integration-job.jar",
        "kafka:9092",
        config["consumer_group"] + "-incompatible",
        config["broker"]["cluster_id"],
        *[config["broker"]["topics"][t]["id"] for t in TOPICS],
        config["bundle"]["jar_sha256"],
        config["limits_profile"],
        config["evidence_registry_sha256"],
    ]
    before = {j["jid"] for j in test.rest("/jobs/overview").get("jobs", [])}
    try:
        response = test.stack.exec("jobmanager", *command)
    except StackError as error:
        if str(error) != "command_failed_job_submission_exit_1":
            raise
        response = ""
    match = re.search(r"JobID ([a-f0-9]{32})", response)
    created = {j["jid"] for j in test.rest("/jobs/overview").get("jobs", [])} - before
    if len(created) != 1 or (match and match[1] not in created):
        raise StackError("integration_ambiguous_incompatible_job")
    job = created.pop()
    save(test.folder / "incompatible-probe.json", dict(job_id=job, checkpoint=checkpoint))
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        state = test.rest("/jobs/" + job)["state"]
        if state == "FAILED":
            original = test.rest("/jobs/" + job + "/exceptions")
            save(test.folder / "incompatible-probe-exceptions.json", original)
            save(test.folder / "incompatible-probe.json", dict(job_id=job, checkpoint=checkpoint))
            detail = json.dumps(original)
            if "incompatible_integration_restore" not in detail:
                raise StackError("integration_unrelated_restore_failure")
            return checkpoint
        if state in ("FINISHED", "CANCELED", "SUSPENDED"):
            raise StackError("integration_restore_not_rejected")
        time.sleep(1)
    raise StackError("integration_restore_not_rejected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="detectbridge-p13-dev")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    init = sub.add_parser("init")
    init.add_argument("--objects", type=Path)
    init.add_argument("--profile", choices=("default", "limits", "bytes"), default="default")
    start = sub.add_parser("start")
    start.add_argument("--restore")
    for name in ("stop", "status", "metrics", "verify"):
        sub.add_parser(name)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build()
        elif args.command == "verify":
            from integration_verify import verify

            result = verify()
        else:
            runtime = Integration(args.project)
            with project_lock(runtime.project):
                if args.command == "init":
                    result = runtime.init(args.profile, args.objects)
                elif args.command == "start":
                    result = runtime.start(args.restore)
                else:
                    result = getattr(runtime, args.command)()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps(dict(status="failed", category=type(error).__name__)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
