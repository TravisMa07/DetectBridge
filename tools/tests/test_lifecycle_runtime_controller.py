"""Controller state/fault cases with explicit helper transport doubles, not runtime proof."""

import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle
import lifecycle_runtime as control
import lifecycle_validation as validation
from detection_compile import compile_rules

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = "71500000-0000-4000-8000-000000000010"
DEPLOYMENT = "71500000-0000-4000-8000-000000000011"
WORKER = "71500000-0000-4000-8000-000000000020"
INCARNATION = "71500000-0000-4000-8000-000000000021"
RUN = "71500000-0000-4000-8000-000000000101"


def helper_double(root, *args):
    if args[0] == "keygen":
        Path(args[1]).write_bytes(b"private synthetic test key")
        Path(args[2]).write_bytes(b"public synthetic test key")
        return "{}"
    if args[0] == "sign":
        payload = json.loads(Path(args[4]).read_bytes())
        value = dict(
            version="1.0.0",
            key_sha256=control.sha(Path(args[3]).read_bytes()),
            payload=payload,
            signature=base64.b64encode(bytes(64)).decode(),
        )
        Path(args[5]).write_bytes(control.encoded(value))
        return "{}"
    if args[0] == "verify":
        signed = json.loads(Path(args[3]).read_bytes())
        return json.dumps(
            dict(
                verified=True,
                payload=signed["payload"],
                payload_sha256=control.identity(signed["payload"]),
            )
        )
    raise AssertionError("unplanned helper operation")


class ControllerTests(unittest.TestCase):
    plan_bytes: ClassVar[bytes]
    manifest: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls):
        rule = ROOT / "contracts/lifecycle/v1/fixtures/rule.yml"
        revision = control.sha(rule.read_bytes())
        provenance = dict(
            version="1.0.0",
            rule_id="71500000-0000-4000-8000-000000000001",
            revision=revision,
            kind="synthetic",
            repository="https://github.com/TravisMa07/DetectBridge",
            repository_revision="2ff0e4f978363466f63714c550a0d296a4b32a00",
            path="contracts/lifecycle/v1/fixtures/rule.yml",
            original_sha256=revision,
            authors=["DetectBridge contributors"],
            license="Apache-2.0",
            notices=[],
            modifications=[],
        )
        profiles = ROOT / "packages/windows-adapters/profiles"
        plan = compile_rules(
            [rule],
            [json.loads((profiles / "security.source.json").read_bytes())],
            mappings=[json.loads((profiles / "security.mapping.json").read_bytes())],
            provenance=[provenance],
        )
        cls.plan_bytes = control.encoded(plan)
        cls.manifest = validation.bundle(cls.plan_bytes)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve())
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        runtime_jar = self.folder / "runtime.jar"
        with zipfile.ZipFile(runtime_jar, "w") as archive:
            archive.writestr(
                "lifecycle-log4j.properties",
                (
                    ROOT / "packages/lifecycle-job/src/main/resources/lifecycle-log4j.properties"
                ).read_bytes(),
            )
        producer = self.folder / "producer.jar"
        producer.write_bytes(b"synthetic original artifact double")
        self.addCleanup(patch.stopall)
        patch.object(control.Runtime, "_local_java", side_effect=helper_double).start()
        patch.object(validation, "verify_artifact", return_value=producer).start()
        patch.object(validation, "PIN", control.sha(producer.read_bytes())).start()
        validator = self.folder / "compiler.tar"
        validator.write_bytes(b"synthetic compiler packet double")
        descriptor = dict(
            version="1.0.0",
            artifact_sha256=control.sha(validator.read_bytes()),
            image_id="sha256:" + "1" * 64,
            base_image="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c",
        )
        patch.object(control.Runtime, "_verify_validator_image", return_value=None).start()
        self.runtime = control.Runtime.initialize(
            self.folder / "deployment",
            AUTHORITY,
            DEPLOYMENT,
            runtime_jar,
            producer,
            self.manifest["compatibility_sha256"],
            validator_artifact=validator,
            validator_descriptor=descriptor,
        )
        self.root = self.runtime.root
        patch.object(self.runtime, "_logging_proof", return_value={"synthetic": True}).start()
        broker = dict(
            cluster_id="synthetic-cluster",
            topics={
                role: dict(name="test." + role, id=role + "_id", partition=0)
                for role in ("control", "artifact", "ack", "output")
            },
        )
        worker = dict(
            worker_id=WORKER,
            incarnation=INCARNATION,
            public_key=base64.b64encode(b"synthetic worker public").decode(),
            input_topic="test.input",
            input_topic_id="input_id",
            assigned_runs=[RUN],
            flink_project=self.runtime.config["project"] + "-worker",
        )
        with self.runtime._locked():
            self.runtime._load()
            self.runtime._append("broker", broker)
            self.runtime._append("worker", worker)
        self.registration = {key: value for key, value in worker.items() if key != "flink_project"}
        # Explicit staged-store double: these tests do not qualify the P15a runner.
        self.store = lifecycle.Store.__new__(lifecycle.Store)
        self.store.root = self.folder / "candidate-store"
        self.store.root.mkdir(mode=0o700)
        (self.store.root / ".lock").write_bytes(b"")
        (self.store.root / ".lock").chmod(0o600)
        self.store.authority = AUTHORITY
        target = self.manifest["bundle_sha256"]
        self.store.bundles = {target: dict(staged=True, tested=True, retired=False)}
        self.store.available = {target: self.manifest}
        self.store.requests = {}
        patch.object(self.store, "_load", return_value=None).start()
        folder = self.store.root / "bundles" / target
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_bytes(control.encoded(self.manifest))
        (folder / "plan.json").write_bytes(self.plan_bytes)
        self.sent: list[dict[str, Any]] = []

        def send(role, key, wire, temporary, topic=None):
            descriptor = topic or self.runtime.state["broker"]["topics"][role]
            receipt = dict(
                cluster_id="synthetic-cluster",
                topic=descriptor["name"],
                topic_id=descriptor["id"],
                partition=0,
                offset=len(self.sent),
                value_sha256=control.sha(wire),
            )
            self.sent.append(dict(role=role, key=key, wire=wire, receipt=receipt))
            return receipt

        patch.object(self.runtime, "_send_bytes", side_effect=send).start()

    def proposal(self, revision=1, action="activate"):
        value = dict(
            version="1.0.0",
            authority_id=AUTHORITY,
            deployment_id=DEPLOYMENT,
            request_id=str(uuid.uuid4()),
            revision=revision,
            previous_sha256=None if revision == 1 else "a" * 64,
            action=action,
            bundle_sha256=self.manifest["bundle_sha256"],
            compatibility_sha256=self.manifest["compatibility_sha256"],
            participants=[dict(worker_id=WORKER, incarnation=INCARNATION)],
        )
        self.store.requests[value["request_id"]] = (
            "unused-model-request-hash",
            dict(command=value),
        )
        return value

    def publish(self, proposal=None, registrations=None, expected=0, previous=None):
        return self.runtime.publish(
            self.store,
            proposal or self.proposal(),
            registrations or [self.registration],
            expected,
            previous,
        )

    def test_prepared_proposal_is_not_convergence_and_artifacts_precede_control(self):
        result = self.publish()
        self.assertEqual(1, result["revision"])
        self.assertEqual(["artifact", "artifact", "control"], [item["role"] for item in self.sent])
        status = self.runtime.status()
        self.assertEqual("broker_published", status["publication"])
        self.assertFalse(status["converged"])
        self.assertEqual({RUN: WORKER}, status["run_owners"])

    def test_skipped_preparation_is_not_implicit_publication(self):
        proposal = self.proposal(revision=7)
        result = self.publish(proposal)
        intent = control.checked(self.root / "publications/1.json")
        self.assertEqual(1, result["revision"])
        self.assertEqual(7, intent["control"]["payload"]["proposal"]["revision"])

    def test_exact_adoption_retry_keeps_original_identity_and_changed_content_conflicts(self):
        proposal = self.proposal()
        original = self.publish(proposal)
        count = len(self.sent)
        self.assertEqual(original, self.publish(proposal))
        self.assertEqual(count, len(self.sent))
        changed = [{**self.registration, "assigned_runs": []}]
        with self.assertRaisesRegex(ValueError, "adoption_conflict"):
            self.publish(proposal, changed)

    def test_uncertain_broker_ack_does_not_allocate_another_revision(self):
        proposal = self.proposal()

        def failure(phase):
            if phase == "after_control_broker_ack":
                raise OSError("injected real boundary")

        with patch("lifecycle_runtime.HOOK", side_effect=failure), self.assertRaises(OSError):
            self.publish(proposal)
        before = control.checked(self.root / "publications/1.json")
        self.assertEqual("adopted_pending", self.runtime.status()["publication"])
        with self.assertRaisesRegex(ValueError, "publication_pending"):
            self.publish(self.proposal(2), expected=1, previous=before["command_sha256"])
        result = self.publish(proposal)
        self.assertIsNotNone(result["receipt"])
        controls = [item["wire"] for item in self.sent if item["role"] == "control"]
        self.assertEqual(2, len(controls))
        self.assertEqual(controls[0], controls[1])
        self.assertEqual(1, self.runtime.status()["revision"])

    def test_unstaged_candidate_or_unprepared_command_cannot_be_published(self):
        proposal = self.proposal()
        self.store.bundles[self.manifest["bundle_sha256"]]["staged"] = False
        with self.assertRaisesRegex(ValueError, "candidate_not_staged"):
            self.publish(proposal)
        self.store.bundles[self.manifest["bundle_sha256"]]["staged"] = True
        self.store.requests.clear()
        with self.assertRaisesRegex(ValueError, "unprepared_proposal"):
            self.publish(proposal)
        self.assertEqual([], self.sent)

    def test_stale_compare_and_swap_and_rollback_without_history_reject(self):
        with self.assertRaisesRegex(ValueError, "publication_cas"):
            self.publish(expected=True)
        with self.assertRaisesRegex(ValueError, "rollback_history"):
            self.publish(self.proposal(action="rollback"))
        self.assertEqual(0, self.runtime.status()["revision"])

    def test_run_ownership_survives_membership_omission_and_conflicting_worker(self):
        result = self.publish()
        empty = [{**self.registration, "assigned_runs": []}]
        self.publish(self.proposal(2, "membership"), empty, 1, result["command_sha256"])
        self.assertEqual(WORKER, self.runtime.status()["run_owners"][RUN])
        other = {
            **self.registration,
            "worker_id": str(uuid.uuid4()),
            "incarnation": str(uuid.uuid4()),
            "public_key": base64.b64encode(b"other synthetic key").decode(),
            "input_topic_id": "other_id",
        }
        with self.runtime._locked():
            self.runtime._load()
            self.runtime._append(
                "worker", {**other, "flink_project": self.runtime.config["project"] + "-other"}
            )
        with self.assertRaisesRegex(ValueError, "run_owner"):
            self.runtime._registrations([other])

    def test_journal_surviving_successor_recovers_and_corruption_fails_closed(self):
        def failure(phase):
            if phase == "after_record_publication":
                raise OSError("journal-before-head")

        with patch("lifecycle_runtime.HOOK", side_effect=failure), self.assertRaises(OSError):
            with self.runtime._locked():
                self.runtime._load()
                self.runtime._append("ack_cursor", dict(next_offset=1))
        reopened = control.Runtime(self.root)
        self.assertEqual(1, reopened.state["ack_cursor"])
        head = self.root / "head.json"
        head.write_bytes(b"{}")
        with self.assertRaises(ValueError):
            control.Runtime(self.root)

    def test_root_authorization_and_artifact_identity_are_checked_on_reopen(self):
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "private_root"):
            control.Runtime(self.root)
        self.root.chmod(0o700)
        (self.root / "artifacts/runtime.jar").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "artifact_integrity"):
            control.Runtime(self.root)

    def test_broker_cluster_changes_common_binding_but_incarnation_does_not_change_worker_binding(
        self,
    ):
        common = self.runtime._common()
        changed = {**common, "cluster_id": "another-cluster"}
        self.assertNotEqual(control.runtime_binding(common), control.runtime_binding(changed))
        worker = self.runtime.state["workers"][WORKER]
        self.runtime.config["producer_sha256"] = (
            "51a984dedc04af7b368fea63a9cec88d2127c6ddf5aa019352f491a3481bad6d"
        )
        config = self.runtime._worker_config(worker)
        self.assertEqual(
            control.worker_binding(config),
            control.worker_binding({**config, "incarnation": str(uuid.uuid4())}),
        )
        self.assertNotEqual(
            control.worker_binding(config),
            control.worker_binding({**config, "worker_id": str(uuid.uuid4())}),
        )

    def test_partial_bundle_member_publication_resumes_exact_bytes(self):
        proposal = self.proposal()

        def failure(phase):
            if phase == "after_bundle_member_manifest":
                raise OSError("interrupted bundle publication")

        with patch("lifecycle_runtime.HOOK", side_effect=failure), self.assertRaises(OSError):
            self.publish(proposal)
        folder = self.root / "bundles" / self.manifest["bundle_sha256"]
        self.assertTrue((folder / "manifest.json").exists())
        self.assertFalse((folder / "plan.json").exists())
        self.assertEqual(0, self.runtime.status()["revision"])
        self.assertEqual(1, self.publish(proposal)["revision"])
        self.assertEqual(self.plan_bytes, (folder / "plan.json").read_bytes())

    def test_uncertain_publication_retry_does_not_recheck_new_adoption_readiness(self):
        proposal = self.proposal()

        def failure(phase):
            if phase == "after_adoption":
                raise OSError("intent durable before send")

        with patch("lifecycle_runtime.HOOK", side_effect=failure), self.assertRaises(OSError):
            self.publish(proposal)
        self.store.bundles[self.manifest["bundle_sha256"]]["staged"] = False
        self.assertIsNotNone(self.publish(proposal)["receipt"])
        self.assertEqual(1, self.runtime.status()["revision"])

    def test_launch_intent_survives_lost_submission_ack_and_blocks_incarnation_reuse(self):
        responses = ["", OSError("Flink accepted submission; helper acknowledgment lost")]
        with (
            patch.object(self.runtime, "_verify_stopped"),
            patch.object(
                self.runtime, "_initialize_worker_volumes", return_value=self.folder / "worker.json"
            ),
            patch.object(self.runtime, "_compose", side_effect=responses),
            self.assertRaises(OSError),
        ):
            self.runtime.start(WORKER)
        self.runtime.status()
        self.assertEqual("launch_pending", self.runtime.state["jobs"][WORKER]["state"])
        with (
            patch.object(self.runtime, "_verify_stopped"),
            self.assertRaisesRegex(ValueError, "incarnation_already_attempted"),
        ):
            self.runtime.start(WORKER)

    def test_stopping_never_started_worker_does_not_invent_launch_attempt(self):
        with patch.object(self.runtime, "_containers", return_value=[]):
            self.runtime.stop(WORKER)
        self.assertFalse(self.runtime.state["jobs"][WORKER]["ever_attempted"])
        with (
            patch.object(self.runtime, "_verify_stopped"),
            patch.object(
                self.runtime, "_initialize_worker_volumes", return_value=self.folder / "worker.json"
            ),
            patch.object(self.runtime, "_compose", side_effect=["", "JobID " + "1" * 32]),
        ):
            job = self.runtime.start(WORKER)
        self.assertEqual("1" * 32, job["job_id"])
        self.assertTrue(job["ever_attempted"])

    def test_effective_byte_reserve_boundary_and_unknown_store_entries_fail_closed(self):
        used = self.runtime._usage()
        amount = 65536
        maximum = used + control.LIMITS["controller_recovery_headroom_bytes"] + amount
        with patch.dict(control.LIMITS, store_bytes=maximum):
            self.runtime._reserve(amount)
            with self.assertRaisesRegex(ValueError, "store_limit"):
                self.runtime._reserve(amount + 1)
        unknown = self.root / "foreign.json"
        unknown.write_bytes(b"{}")
        unknown.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "unknown_store_entry"):
            self.runtime.status()

    def test_advisory_inventory_observes_failed_snapshot_without_completed_claim(self):
        with self.runtime._locked():
            self.runtime._load()
            self.runtime._append(
                "start",
                dict(
                    worker_id=WORKER,
                    incarnation=INCARNATION,
                    job_id="a" * 32,
                    state="submitted",
                    ever_attempted=True,
                    completed_restore_paths=[],
                ),
            )
        inventory = dict(checkpoint_id=7, snapshot_sha256="b" * 64)
        with (
            patch.object(self.runtime, "_worker_file", return_value=inventory) as read,
            patch.object(self.runtime, "rest", return_value=dict(status="FAILED")) as status,
        ):
            with self.assertRaisesRegex(control.RuntimeError, "checkpoint_not_completed"):
                self.runtime.worker_inventory(WORKER, 7)
            read.assert_not_called()
            observed = self.runtime.advisory_inventory(WORKER, 7)
            self.assertEqual(dict(inventory=inventory), observed)
            self.assertNotIn("checkpoint", observed)
            status.assert_called_once()
            read.assert_called_once_with(
                WORKER, f"/store/inventory/{INCARNATION}/{7:020d}.json", maximum=2 * control.MIB
            )

    def test_advisory_inventory_rejects_invalid_or_mismatched_checkpoint_identity(self):
        with patch.object(self.runtime, "_worker_file") as read:
            with self.assertRaisesRegex(control.RuntimeError, "checkpoint_id"):
                self.runtime.advisory_inventory(WORKER, True)
            read.assert_not_called()
        with self.runtime._locked():
            self.runtime._load()
            self.runtime._append(
                "start",
                dict(
                    worker_id=WORKER,
                    incarnation=INCARNATION,
                    job_id="a" * 32,
                    state="submitted",
                    ever_attempted=True,
                    completed_restore_paths=[],
                ),
            )
        with patch.object(self.runtime, "_worker_file", return_value=dict(checkpoint_id=8)):
            with self.assertRaisesRegex(control.RuntimeError, "inventory_missing"):
                self.runtime.advisory_inventory(WORKER, 7)

    def ack_wire(self, publication, phase="durable", incarnation=INCARNATION):
        payload = dict(
            version="1.0.0",
            deployment_id=DEPLOYMENT,
            authority_id=AUTHORITY,
            worker_id=WORKER,
            incarnation=incarnation,
            revision=publication["revision"],
            command_sha256=publication["command_sha256"],
            bundle_sha256=publication["bundle_sha256"],
            compatibility_sha256=self.manifest["compatibility_sha256"],
            phase=phase,
            checkpoint_id=7 if phase == "durable" else None,
            category="ok",
        )
        payload["ack_id"] = "sha256:" + control.identity(
            [
                control.DOMAINS["ack"],
                *[
                    payload[key]
                    for key in (
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
                ],
            ]
        )
        return control.encoded(
            dict(
                version="1.0.0",
                key_sha256=control.sha(base64.b64decode(self.registration["public_key"])),
                payload=payload,
                signature=base64.b64encode(bytes(64)).decode(),
            )
        )

    def deliver_ack(self, wire, fail_commit=False, cluster="synthetic-cluster", topic_id="ack_id"):
        commits = []

        def network(*args, **kwargs):
            if args[0] == "drain":
                folder = self.root / args[-1].removeprefix("/io/")
                offset = int(args[6])
                name = f"{offset:020d}.value"
                (folder / name).write_bytes(wire)
                return dict(
                    records=[
                        dict(
                            topic="test.ack",
                            partition=0,
                            offset=offset,
                            value_sha256=control.sha(wire),
                            value_file=name,
                            key_base64="",
                        )
                    ],
                    next_offset=offset + 1,
                    cluster_id=cluster,
                    topic_id=topic_id,
                )
            if args[0] == "commit":
                commits.append(int(args[-1]))
                if fail_commit:
                    raise OSError("injected group commit failure")
                return dict(status="committed", cluster_id="synthetic-cluster", topic_id="ack_id")
            raise AssertionError(args)

        with patch.object(self.runtime, "_network", side_effect=network):
            return self.runtime.observe(), commits

    def test_changed_artifacts_on_same_instance_block_before_helper_execution(self):
        for name in ("runtime.jar", "producer.jar", "compiler.tar"):
            path = self.root / "artifacts" / name
            original = path.read_bytes()
            head = (self.root / "head.json").read_bytes()
            path.write_bytes(b"changed executable packet")
            try:
                with self.subTest(name=name), patch.object(self.runtime, "_local_java") as helper:
                    with self.assertRaises(control.IntegrityError):
                        self.runtime._local("verify")
                    helper.assert_not_called()
                with self.assertRaises(control.IntegrityError):
                    self.runtime.status()
                self.assertEqual((self.root / "head.json").read_bytes(), head)
            finally:
                path.write_bytes(original)

    def test_foreign_broker_is_rejected_before_up_or_stop_mutations(self):
        lifecycle.write_exclusive(self.root / "broker.compose.json", b"{}")
        foreign = [
            dict(
                Config=dict(
                    Labels={
                        "io.detectbridge.p15b.owner": str(uuid.uuid4()),
                        "com.docker.compose.service": "kafka",
                    }
                )
            )
        ]
        for operation in (self.runtime.up, self.runtime.stop):
            with (
                self.subTest(operation=operation.__name__),
                patch.object(self.runtime, "_command", side_effect=["a" * 64, json.dumps(foreign)]),
                patch.object(self.runtime, "_compose") as mutation,
            ):
                with self.assertRaisesRegex(control.RuntimeError, "foreign_broker"):
                    operation()
                mutation.assert_not_called()

    def test_up_restarts_owned_registered_broker_and_verifies_existing_namespaces(self):
        before = (self.root / "head.json").read_bytes()
        lifecycle.write_exclusive(
            self.root / "broker.compose.json",
            control.encoded(self.runtime._broker_definition("synthetic-cluster")),
        )
        topics = {
            value["name"]: dict(id=value["id"])
            for value in self.runtime.state["broker"]["topics"].values()
        }
        topics["test.input"] = dict(id="input_id")
        actual: dict[str, Any] = dict(cluster_id="synthetic-cluster", topics=topics)
        with (
            patch.object(self.runtime, "_verify_broker_owner", return_value=[]),
            patch.object(self.runtime, "_compose", return_value="") as start,
            patch.object(self.runtime, "_network", return_value=actual) as inspect,
        ):
            self.runtime.up()
            self.assertEqual(start.call_args.args[2:], ("up", "-d", "--wait", "kafka"))
            self.assertEqual(inspect.call_args.args[0], "inspect")
        self.assertEqual((self.root / "head.json").read_bytes(), before)
        actual["topics"]["test.input"]["id"] = "recreated-input-topic"
        with (
            patch.object(self.runtime, "_verify_broker_owner", return_value=[]),
            patch.object(self.runtime, "_compose", return_value=""),
            patch.object(self.runtime, "_network", return_value=actual),
        ):
            with self.assertRaisesRegex(control.RuntimeError, "topic_identity"):
                self.runtime.up()

    def test_ack_batch_from_changed_cluster_or_topic_cannot_advance_cursor(self):
        publication = self.publish()
        wire = self.ack_wire(publication, "durable")
        for cluster, topic in (
            ("replacement-cluster", "ack_id"),
            ("synthetic-cluster", "replacement-topic"),
        ):
            with self.subTest(cluster=cluster, topic=topic):
                with self.assertRaisesRegex(control.RuntimeError, "batch_topic_identity"):
                    self.deliver_ack(wire, cluster=cluster, topic_id=topic)
                status = self.runtime.status()
                self.assertEqual(status["ack_cursor"], 0)
                self.assertFalse(status["converged"])

    def test_reserved_headroom_can_fund_ack_recovery_after_ordinary_writes_stop(self):
        publication = self.publish()
        used = (
            control.LIMITS["store_bytes"]
            - control.LIMITS["controller_recovery_headroom_bytes"]
            - control.MIB
        )
        with patch.object(self.runtime, "_usage", return_value=used):
            with self.assertRaisesRegex(control.RuntimeError, "store_limit"):
                self.runtime._reserve(2 * control.MIB)
            status, commits = self.deliver_ack(self.ack_wire(publication, "durable"))
        self.assertTrue(status["converged"])
        self.assertEqual(commits, [1])

    def test_logger_is_bound_to_jar_and_mounted_as_selected_read_only_config(self):
        path = self.runtime._logging_file()
        self.assertEqual(path.stat().st_mode & 0o777, 0o444)
        self.assertEqual(path.read_bytes(), self.runtime._logging_bytes())
        compose = self.runtime._worker_compose(self.runtime.state["workers"][WORKER])
        self.assertEqual(compose["services"]["jobmanager"]["networks"], ["internal"])
        self.assertEqual(compose["services"]["taskmanager"]["networks"], ["internal", "broker"])
        self.assertEqual(compose["services"]["validator"]["network_mode"], "none")
        for role in ("jobmanager", "taskmanager"):
            self.assertEqual(
                compose["services"][role]["entrypoint"],
                ["bash", "-ceu", 'umask 077; exec /docker-entrypoint.sh "$@"', "--"],
            )
            mount = next(
                item for item in compose["services"][role]["volumes"] if isinstance(item, dict)
            )
            self.assertEqual(mount["source"], str(path))
            self.assertEqual(mount["target"], "/opt/flink/conf/log4j-console.properties")
            self.assertTrue(mount["read_only"])
        path.chmod(0o600)
        path.write_bytes(b"untrusted logging replacement")
        path.chmod(0o444)
        with patch.object(self.runtime, "_local_java") as helper:
            with self.assertRaisesRegex(control.IntegrityError, "logging_integrity"):
                self.runtime._local("verify")
            helper.assert_not_called()

    def probe_release_command(self, marker):
        with (
            patch.object(self.runtime, "_containers"),
            patch.object(self.runtime, "_compose", return_value="") as compose,
        ):
            self.runtime.release_probe(WORKER, INCARNATION)
        arguments = list(compose.call_args.args)
        command = arguments[arguments.index("taskmanager") + 1 :]
        self.assertEqual(command[-1], "/store/probes/" + INCARNATION + "/release")
        command[-1] = str(marker)
        environment = dict(os.environ)
        if sys.platform == "darwin":
            # Execute the actual Bash payload; translate GNU stat's format to
            # the native BSD stat equivalent, reading real filesystem metadata.
            binaries = self.folder / "native-stat-adapter"
            binaries.mkdir(exist_ok=True)
            adapter = binaries / "stat"
            adapter.write_text(
                "#!/bin/bash\n"
                '[[ "$1" == -c && "$2" == \'%a:%u:%h:%s\' && "$3" == -- ]] || exit 2\n'
                "exec /usr/bin/stat -f '%Lp:%u:%l:%z' \"$4\"\n"
            )
            adapter.chmod(0o700)
            environment["PATH"] = str(binaries) + os.pathsep + environment["PATH"]
        return subprocess.run(
            ["bash", "-ceu", 'umask 022; exec "$@"', "release-test", *command],
            env=environment,
            capture_output=True,
            check=False,
        )

    def test_probe_release_creates_private_empty_marker_under_exec_umask022(self):
        marker = self.folder / "release"
        result = self.probe_release_command(marker)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        self.assertEqual(marker.stat().st_uid, os.getuid())
        self.assertEqual(marker.stat().st_nlink, 1)
        self.assertEqual(marker.read_bytes(), b"")
        inode = marker.stat().st_ino
        self.assertEqual(self.probe_release_command(marker).returncode, 0)
        self.assertEqual(marker.stat().st_ino, inode)

    def test_probe_release_rejects_existing_unsafe_marker_without_repair(self):
        for kind in ("public", "nonempty", "hardlink", "symlink", "directory"):
            with self.subTest(kind=kind):
                folder = self.folder / kind
                folder.mkdir(mode=0o700)
                marker = folder / "release"
                target = folder / "target"
                if kind == "directory":
                    marker.mkdir(mode=0o700)
                elif kind == "symlink":
                    target.write_bytes(b"untouched")
                    target.chmod(0o600)
                    marker.symlink_to(target)
                else:
                    marker.write_bytes(b"unexpected" if kind == "nonempty" else b"")
                    marker.chmod(0o644 if kind == "public" else 0o600)
                    if kind == "hardlink":
                        os.link(marker, target)
                before = marker.lstat()
                result = self.probe_release_command(marker)
                self.assertNotEqual(result.returncode, 0)
                after = marker.lstat()
                self.assertEqual(
                    (after.st_ino, after.st_mode, after.st_nlink),
                    (before.st_ino, before.st_mode, before.st_nlink),
                )
                if kind == "symlink":
                    self.assertEqual(target.read_bytes(), b"untouched")
                elif marker.is_file():
                    self.assertEqual(
                        marker.read_bytes(), b"unexpected" if kind == "nonempty" else b""
                    )

    def test_probe_requires_fresh_initialization_pin_and_cannot_change_later(self):
        probe = self.folder / "qualification-input.jar"
        probe.write_bytes(b"first party qualification artifact double")
        with self.assertRaisesRegex(control.RuntimeError, "probe_not_registered"):
            self.runtime.start_probe(WORKER, None, probe, "hold-release", str(uuid.uuid4()))
        registered = control.Runtime.initialize(
            self.folder / "registered-probe-runtime",
            AUTHORITY,
            DEPLOYMENT,
            self.root / "artifacts/runtime.jar",
            self.root / "artifacts/producer.jar",
            self.manifest["compatibility_sha256"],
            validator_artifact=self.root / "artifacts/compiler.tar",
            validator_descriptor=self.runtime.config["validator"],
            qualification_jar=probe,
        )
        with patch.object(registered, "start", return_value={"synthetic": True}) as start:
            registered.start_probe(WORKER, None, probe, "hold-release", str(uuid.uuid4()))
            self.assertEqual(
                start.call_args.kwargs["_probe"]["sha256"], control.sha(probe.read_bytes())
            )
        (registered.root / "artifacts/qualification.jar").write_bytes(b"changed probe executable")
        with self.assertRaisesRegex(control.IntegrityError, "probe_artifact_integrity"):
            registered.status()

    def test_ack_batch_commits_once_after_both_checked_prefix_records_are_durable(self):
        publication = self.publish()
        wires = [self.ack_wire(publication, phase) for phase in ("applied", "durable")]
        commits = []

        def network(*args, **kwargs):
            if args[0] == "drain":
                folder = self.root / args[-1].removeprefix("/io/")
                records = []
                for offset, wire in enumerate(wires):
                    name = f"{offset:020d}.value"
                    lifecycle.write_exclusive(folder / name, wire)
                    records.append(
                        dict(
                            topic="test.ack",
                            partition=0,
                            offset=offset,
                            value_sha256=control.sha(wire),
                            value_file=name,
                            key_base64="",
                        )
                    )
                return dict(
                    records=records,
                    next_offset=2,
                    cluster_id="synthetic-cluster",
                    topic_id="ack_id",
                )
            if args[0] == "commit":
                self.assertEqual(self.runtime.state["ack_cursor"], 2)
                self.assertEqual(len(self.runtime.state["acks"]), 2)
                head = lifecycle.checked(self.root / "head.json")
                last = lifecycle.checked(self.root / "journal" / f"{head['sequence']:020d}.json")
                self.assertEqual(last["kind"], "ack_cursor")
                self.assertEqual(last["value"]["next_offset"], 2)
                commits.append(int(args[-1]))
                return dict(cluster_id="synthetic-cluster", topic_id="ack_id")
            raise AssertionError(args)

        with patch.object(self.runtime, "_network", side_effect=network):
            result = self.runtime.observe(limit=2)
        self.assertTrue(result["converged"])
        self.assertEqual(commits, [2])

    def test_ack_requires_authentic_registered_proof_and_durable_phase(self):
        publication = self.publish()
        applied, _ = self.deliver_ack(self.ack_wire(publication, "applied"))
        self.assertFalse(applied["converged"])
        durable, commits = self.deliver_ack(self.ack_wire(publication))
        self.assertTrue(durable["converged"])
        self.assertEqual([2], commits)
        self.assertEqual(2, self.runtime.status()["ack_cursor"])

    def test_foreign_incarnation_ack_is_durably_rejected_then_valid_ack_can_converge(self):
        publication = self.publish()
        invalid, _ = self.deliver_ack(self.ack_wire(publication, incarnation=str(uuid.uuid4())))
        self.assertFalse(invalid["converged"])
        self.assertEqual(1, self.runtime.state["ack_rejections"])
        valid, _ = self.deliver_ack(self.ack_wire(publication))
        self.assertTrue(valid["converged"])

    def test_ack_persistence_precedes_group_commit_and_duplicate_has_one_payload(self):
        publication = self.publish()
        wire = self.ack_wire(publication)
        with self.assertRaises(OSError):
            self.deliver_ack(wire, fail_commit=True)
        self.assertEqual(1, self.runtime.status()["ack_cursor"])
        self.assertEqual(1, len(self.runtime.state["acks"]))
        self.deliver_ack(wire)
        self.assertEqual(1, len(self.runtime.state["acks"]))
        self.assertEqual(2, self.runtime.status()["ack_cursor"])

    def test_private_clusters_retain_original_resource_bounds_and_no_host_ports(self):
        worker = self.runtime.state["workers"][WORKER]
        compose = self.runtime._worker_compose(worker)
        self.assertEqual("1g", compose["services"]["jobmanager"]["mem_limit"])
        self.assertEqual("2g", compose["services"]["taskmanager"]["mem_limit"])
        for name, service in compose["services"].items():
            self.assertNotIn("ports", service)
            if name == "validator":
                self.assertEqual("none", service["network_mode"])
                self.assertTrue(service["read_only"])
                self.assertEqual(["validation:/validation"], service["volumes"])
                continue
            self.assertIn("restart-strategy.type: none", service["environment"]["FLINK_PROPERTIES"])
        changed = copy.deepcopy(worker)
        changed["flink_project"] += "-other"
        self.assertNotEqual(compose["volumes"], self.runtime._worker_compose(changed)["volumes"])


if __name__ == "__main__":
    unittest.main()
