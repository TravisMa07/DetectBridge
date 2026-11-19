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

    def test_control_send_hook_follows_artifacts_and_precedes_broker_control(self):
        proposal = self.proposal()
        observations = []

        def before_control(phase):
            if phase == "before_control_publication":
                roles = [item["role"] for item in self.sent]
                self.assertTrue(roles)
                self.assertEqual({"artifact"}, set(roles))
                observations.append(roles)
                raise OSError("qualification boundary before control")

        with patch("lifecycle_runtime.HOOK", side_effect=before_control):
            with self.assertRaisesRegex(OSError, "qualification boundary before control"):
                self.publish(proposal)
        self.assertEqual(1, len(observations))
        self.assertFalse(any(item["role"] == "control" for item in self.sent))
        self.assertEqual("adopted_pending", self.runtime.status()["publication"])
        original = control.checked(self.root / "publications/1.json")
        published = self.publish(proposal)
        self.assertEqual(1, published["revision"])
        self.assertIsNotNone(published["receipt"])
        self.assertEqual(original, control.checked(self.root / "publications/1.json"))
        self.assertEqual(1, sum(item["role"] == "control" for item in self.sent))

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
                lifecycle.write_exclusive(folder / name, wire)
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

    def ack_signature_batch_result(self, request_path, request_sha256):
        """Explicit signature transport double, never actual cryptographic/runtime evidence."""
        raw = Path(request_path).read_bytes()
        self.assertEqual(request_sha256, control.sha(raw))
        self.assertEqual(0o600, Path(request_path).stat().st_mode & 0o777)
        request = json.loads(raw)
        self.assertEqual({"version", "records"}, set(request))
        self.assertEqual("1.0.0", request["version"])
        results = []
        for index, row in enumerate(request["records"]):
            self.assertEqual(
                {"index", "public_key", "wire_base64", "wire_sha256", "key_sha256"}, set(row)
            )
            self.assertEqual(index, row["index"])
            wire = base64.b64decode(row["wire_base64"], validate=True)
            key = base64.b64decode(row["public_key"], validate=True)
            self.assertEqual(control.sha(wire), row["wire_sha256"])
            self.assertEqual(control.sha(key), row["key_sha256"])
            results.append(
                dict(
                    index=index,
                    wire_sha256=row["wire_sha256"],
                    key_sha256=row["key_sha256"],
                    verified=True,
                    payload_sha256=control.identity(json.loads(wire)["payload"]),
                )
            )
        return control.encoded(
            dict(version="1.0.0", request_sha256=request_sha256, results=results)
        ).decode()

    def ack_signature_batch_network(self, wires, commits):
        def network(*args, **_kwargs):
            if args[0] == "drain":
                folder = self.root / args[-1].removeprefix("/io/")
                first = int(args[6])
                records = []
                for offset, wire in enumerate(wires, first):
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
                    next_offset=first + len(wires),
                    cluster_id="synthetic-cluster",
                    topic_id="ack_id",
                )
            if args[0] == "commit":
                self.assertEqual(int(args[-1]), self.runtime.state["ack_cursor"])
                commits.append(int(args[-1]))
                return dict(cluster_id="synthetic-cluster", topic_id="ack_id")
            raise AssertionError("unexpected network operation")

        return network

    def test_qualification_ack_batch_one_helper_preserves_normal_ack_prefix_and_commit(self):
        self.enable_batch_artifact()
        publication = self.runtime.state["publications"][-1]
        wires = [self.ack_wire(publication, phase) for phase in ("applied", "durable")]
        commits: list[int] = []
        with (
            patch.object(
                self.runtime,
                "_network",
                side_effect=self.ack_signature_batch_network(wires, commits),
            ),
            patch.object(
                self.runtime,
                "_local_ack_batch",
                side_effect=self.ack_signature_batch_result,
                create=True,
            ) as batch,
            patch.object(
                self.runtime, "_local", side_effect=AssertionError("per-ACK helper must not run")
            ),
        ):
            result = self.runtime.observe(limit=2, qualification_batch=True)
        self.assertTrue(result["converged"])
        self.assertEqual(1, batch.call_count)
        self.assertEqual([2], commits)
        self.assertEqual(2, self.runtime.state["ack_cursor"])
        self.assertEqual(2, len(self.runtime.state["acks"]))
        self.assertIsNone(self.runtime._qualification_ack_proofs)

    def test_qualification_ack_invalid_signature_is_ordinary_rejection_not_helper_failure(self):
        self.enable_batch_artifact()
        publication = self.runtime.state["publications"][-1]
        wires = [self.ack_wire(publication, phase) for phase in ("applied", "durable")]
        commits: list[int] = []

        def result(path, request_sha):
            value = json.loads(self.ack_signature_batch_result(path, request_sha))
            value["results"][0].pop("payload_sha256")
            value["results"][0].update(verified=False, category="signature_invalid")
            return control.encoded(value).decode()

        with (
            patch.object(
                self.runtime,
                "_network",
                side_effect=self.ack_signature_batch_network(wires, commits),
            ),
            patch.object(self.runtime, "_local_ack_batch", side_effect=result),
        ):
            observed = self.runtime.observe(limit=2, qualification_batch=True)
        self.assertTrue(observed["converged"])
        self.assertEqual(1, self.runtime.state["ack_rejections"])
        self.assertEqual(1, len(self.runtime.state["acks"]))
        self.assertEqual(2, self.runtime.state["ack_cursor"])
        self.assertEqual([2], commits)
        self.assertIsNone(self.runtime._qualification_ack_proofs)

    def test_qualification_ack_result_integrity_fails_before_any_new_journal_prefix(self):
        self.enable_batch_artifact()
        publication = self.runtime.state["publications"][-1]
        wires = [self.ack_wire(publication, phase) for phase in ("applied", "durable")]
        before = (self.root / "head.json").read_bytes()
        mutations = (
            "missing",
            "extra",
            "index",
            "wire",
            "key",
            "request",
            "unknown_top",
            "unknown_row",
            "verified_type",
            "payload",
            "false_with_payload",
            "false_category",
            "true_category",
            "noncanonical",
            "oversize",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                commits: list[int] = []

                def result(path, request_sha):
                    value = json.loads(self.ack_signature_batch_result(path, request_sha))
                    row = value["results"][
                        -1
                    ]  # The earlier positive result must not be journaled first.
                    if mutation == "missing":
                        value["results"].pop()
                    elif mutation == "extra":
                        value["results"].append(copy.deepcopy(row))
                    elif mutation == "index":
                        row["index"] = 0
                    elif mutation == "wire":
                        row["wire_sha256"] = "0" * 64
                    elif mutation == "key":
                        row["key_sha256"] = "0" * 64
                    elif mutation == "request":
                        value["request_sha256"] = "0" * 64
                    elif mutation == "unknown_top":
                        value["unexpected"] = True
                    elif mutation == "unknown_row":
                        row["unexpected"] = True
                    elif mutation == "verified_type":
                        row["verified"] = "true"
                    elif mutation == "payload":
                        row["payload_sha256"] = "0" * 64
                    elif mutation == "false_with_payload":
                        row.update(verified=False, category="signature_invalid")
                    elif mutation == "false_category":
                        row.pop("payload_sha256")
                        row.update(verified=False, category="unknown")
                    elif mutation == "true_category":
                        row["category"] = "signature_invalid"
                    elif mutation == "noncanonical":
                        return json.dumps(value, indent=2)
                    elif mutation == "oversize":
                        return "x" * 65537
                    return control.encoded(value).decode()

                with (
                    patch.object(
                        self.runtime,
                        "_network",
                        side_effect=self.ack_signature_batch_network(wires, commits),
                    ),
                    patch.object(self.runtime, "_local_ack_batch", side_effect=result),
                    self.assertRaises(control.IntegrityError),
                ):
                    self.runtime.observe(limit=2, qualification_batch=True)
                self.assertEqual(before, (self.root / "head.json").read_bytes())
                self.assertEqual(0, self.runtime.state["ack_cursor"])
                self.assertFalse(self.runtime.state["acks"])
                self.assertEqual([], commits)
                self.assertIsNone(self.runtime._qualification_ack_proofs)

    def test_qualification_ack_proofs_are_exact_ephemeral_pairs_not_cross_call_cache(self):
        self.enable_batch_artifact()
        wire = self.ack_wire(self.runtime.state["publications"][-1])
        payload = json.loads(wire)["payload"]
        public = base64.b64decode(self.registration["public_key"])
        with self.runtime._temporary() as temporary:
            path = temporary / "00000000000000000000.value"
            key = temporary / "test-public.der"
            lifecycle.write_exclusive(path, wire)
            lifecycle.write_exclusive(key, public)
            records = [dict(value_file=path.name, value_sha256=control.sha(wire))]
            pair = (control.sha(wire), control.sha(public))
            with patch.object(
                self.runtime, "_local_ack_batch", side_effect=self.ack_signature_batch_result
            ) as batch:
                for _ in range(2):
                    with self.runtime._qualification_ack_verification(records, temporary, True):
                        self.assertEqual({pair}, set(self.runtime._qualification_ack_proofs))
                        self.runtime._verify_signature("ack", key, path, payload)
                    self.assertIsNone(self.runtime._qualification_ack_proofs)
                self.assertEqual(2, batch.call_count)
                changed_wire = temporary / "changed-wire.json"
                changed_key = temporary / "changed-key.der"
                lifecycle.write_exclusive(changed_wire, wire + b" ")
                lifecycle.write_exclusive(changed_key, b"other synthetic public key")
                with self.runtime._qualification_ack_verification(records, temporary, True):
                    for public_path, message, claimed_payload in (
                        (changed_key, path, payload),
                        (key, changed_wire, payload),
                        (key, path, {**payload, "revision": 99}),
                    ):
                        with self.assertRaises(control.IntegrityError):
                            self.runtime._verify_signature(
                                "ack", public_path, message, claimed_payload
                            )
                with self.runtime._qualification_ack_verification(records, temporary, True):
                    self.runtime._qualification_ack_proofs.clear()
                    with self.assertRaises(control.IntegrityError):
                        self.runtime._verify_signature("ack", key, path, payload)
                self.assertIsNone(self.runtime._qualification_ack_proofs)
            with patch.object(self.runtime, "_local", wraps=self.runtime._local) as legacy:
                self.runtime._verify_signature("ack", key, path, payload)
            self.assertEqual(1, legacy.call_count)

    def test_qualification_ack_malformed_unknown_key_keep_ordinary_rejection_boundaries(self):
        self.enable_batch_artifact()
        publication = self.runtime.state["publications"][-1]
        wires = [
            b"{",
            self.ack_wire(publication, incarnation=str(uuid.uuid4())),
            self.ack_wire(publication),
        ]
        commits: list[int] = []
        with (
            patch.object(
                self.runtime,
                "_network",
                side_effect=self.ack_signature_batch_network(wires, commits),
            ),
            patch.object(
                self.runtime, "_local_ack_batch", side_effect=self.ack_signature_batch_result
            ) as batch,
        ):
            observed = self.runtime.observe(limit=3, qualification_batch=True)
        self.assertTrue(observed["converged"])
        self.assertEqual(1, batch.call_count)
        self.assertEqual(2, self.runtime.state["ack_rejections"])
        self.assertEqual(1, len(self.runtime.state["acks"]))
        self.assertEqual([3], commits)

    def test_qualification_ack_helper_failure_does_not_become_remote_rejection(self):
        self.enable_batch_artifact()
        wires = [self.ack_wire(self.runtime.state["publications"][-1])]
        before = (self.root / "head.json").read_bytes()
        commits: list[int] = []
        with (
            patch.object(
                self.runtime,
                "_network",
                side_effect=self.ack_signature_batch_network(wires, commits),
            ),
            patch.object(
                self.runtime,
                "_local_ack_batch",
                side_effect=RuntimeError("synthetic_infrastructure_failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "synthetic_infrastructure_failure"),
        ):
            self.runtime.observe(limit=1, qualification_batch=True)
        self.assertEqual(before, (self.root / "head.json").read_bytes())
        self.assertEqual(0, self.runtime.state["ack_rejections"])
        self.assertEqual(0, self.runtime.state["ack_cursor"])
        self.assertEqual([], commits)
        self.assertIsNone(self.runtime._qualification_ack_proofs)

    def test_qualification_ack_inspection_is_readonly_and_default_keeps_legacy_verifier(self):
        self.enable_batch_artifact()
        wires = [self.ack_wire(self.runtime.state["publications"][-1])]
        before = (self.root / "head.json").read_bytes()
        commits: list[int] = []
        with (
            patch.object(
                self.runtime,
                "_network",
                side_effect=self.ack_signature_batch_network(wires, commits),
            ),
            patch.object(
                self.runtime, "_local_ack_batch", side_effect=self.ack_signature_batch_result
            ) as batch,
        ):
            inspected = self.runtime.inspect_acks(limit=1, qualification_batch=True)
            self.assertTrue(inspected["records"][0]["signature_verified"])
            self.assertEqual(1, batch.call_count)
        self.assertEqual(before, (self.root / "head.json").read_bytes())
        self.assertEqual([], commits)
        with (
            patch.object(
                self.runtime,
                "_network",
                side_effect=self.ack_signature_batch_network(wires, commits),
            ),
            patch.object(
                self.runtime,
                "_local_ack_batch",
                side_effect=AssertionError("default must not use qualification verifier"),
            ),
            patch.object(self.runtime, "_local", wraps=self.runtime._local) as legacy,
        ):
            result = self.runtime.inspect_acks(limit=1)
            self.assertTrue(result["records"][0]["signature_verified"])
            self.assertEqual(1, legacy.call_count)
        self.assertEqual(before, (self.root / "head.json").read_bytes())

    def test_ack_readers_never_repair_symlink_target_or_unsafe_member_mode(self):
        self.enable_batch_artifact()
        wire = self.ack_wire(self.runtime.state["publications"][-1])
        for method in ("observe", "inspect_acks"):
            for qualified in (False, True):
                for unsafe in ("symlink", "mode"):
                    with self.subTest(method=method, qualified=qualified, unsafe=unsafe):
                        outside = self.folder / ("outside-" + uuid.uuid4().hex)
                        outside.write_bytes(wire)
                        outside.chmod(0o644)
                        members: list[Path] = []
                        cleanup_modes: list[int] = []
                        original_cleanup = control.shutil.rmtree

                        def cleanup(path, *args, **kwargs):
                            for member in members:
                                if member.parent == Path(path) and member.exists():
                                    cleanup_modes.append(member.stat().st_mode & 0o777)
                                    self.assertEqual(wire, member.read_bytes())
                            return original_cleanup(path, *args, **kwargs)

                        def network(*args, **_kwargs):
                            if args[0] != "drain":
                                raise AssertionError("unsafe ACK must never commit")
                            folder = self.root / args[-1].removeprefix("/io/")
                            name = "00000000000000000000.value"
                            member = folder / name
                            if unsafe == "symlink":
                                member.symlink_to(outside)
                            else:
                                member.write_bytes(wire)
                                member.chmod(0o644)
                            members.append(member)
                            return dict(
                                records=[
                                    dict(
                                        topic="test.ack",
                                        partition=0,
                                        offset=0,
                                        value_file=name,
                                        value_sha256=control.sha(wire),
                                        key_base64="",
                                    )
                                ],
                                next_offset=1,
                                cluster_id="synthetic-cluster",
                                topic_id="ack_id",
                            )

                        before = (self.root / "head.json").read_bytes()
                        with (
                            patch.object(control.shutil, "rmtree", side_effect=cleanup),
                            patch.object(self.runtime, "_network", side_effect=network),
                            patch.object(
                                self.runtime,
                                "_local_ack_batch",
                                side_effect=AssertionError(
                                    "unsafe ACK must fail before signature batch"
                                ),
                            ),
                            self.assertRaises((ValueError, RuntimeError)),
                        ):
                            getattr(self.runtime, method)(limit=1, qualification_batch=qualified)
                        self.assertEqual(0o644, outside.stat().st_mode & 0o777)
                        self.assertEqual(wire, outside.read_bytes())
                        self.assertEqual(before, (self.root / "head.json").read_bytes())
                        self.assertEqual(0, self.runtime.state["ack_cursor"])
                        self.assertEqual([0o644], cleanup_modes)

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

    def enable_batch_artifact(self):
        # Explicit executable/transport double, not a built qualification artifact.
        artifact = b"first-party qualification helper test double"
        lifecycle.write_exclusive(self.root / "artifacts/qualification.jar", artifact)
        self.runtime.config = {**self.runtime.config, "qualification_sha256": control.sha(artifact)}
        control.save(self.root / "config.json", self.runtime.config)
        self.publish()

    def batch_rows(self, count=3):
        return [dict(kind="raw", context=dict(run_id=RUN), ordinal=index) for index in range(count)]

    def batch_helper_double(self, batch, folder, *, prefix=None, uncertain=False, corrupt=None):
        request = json.loads((folder / "request.json").read_bytes())
        count = len(request["records"]) if prefix is None else prefix
        hashes = []
        for index, row in enumerate(request["records"][: count + int(uncertain)]):
            attempt = dict(
                version="1.0.0",
                operation_id=batch["operation_id"],
                request_sha256=batch["request_sha256"],
                index=index,
                cluster_id=batch["cluster_id"],
                topic=batch["topic"],
                topic_id=batch["topic_id"],
                partition=0,
                key_sha256=control.sha(row["run_id"].encode()),
                value_sha256=row["value_sha256"],
                value_bytes=row["value_bytes"],
            )
            name = f"{index:020d}.json"
            lifecycle.write_exclusive(folder / "attempts" / name, control.encoded(attempt))
            ack = {
                key: attempt[key]
                for key in (
                    "version",
                    "operation_id",
                    "request_sha256",
                    "index",
                    "topic",
                    "partition",
                    "key_sha256",
                    "value_sha256",
                )
            }
            ack.update(offset=100 + index * 2, broker_timestamp=-1)
            ack_bytes = control.encoded(ack)
            lifecycle.write_exclusive(folder / "acknowledgments" / name, ack_bytes)
            if index == count:
                break
            receipt = {
                **attempt,
                "offset": ack["offset"],
                "broker_timestamp": -1,
                "acknowledgment_sha256": control.sha(ack_bytes),
            }
            if corrupt == index:
                receipt["offset"] = -1
            data = control.encoded(receipt)
            lifecycle.write_exclusive(folder / "receipts" / name, data)
            hashes.append(control.sha(data))
        return dict(
            version="1.0.0",
            operation_id=batch["operation_id"],
            request_sha256=batch["request_sha256"],
            completed=count,
            receipt_sha256=hashes,
        )

    def test_qualification_batch_success_force_order_and_idempotent_reopen(self):
        self.enable_batch_artifact()
        original_append = self.runtime._append
        observed = []

        def append(kind, value, **kwargs):
            if kind == "qualification_batch_intent":
                folder = self.root / "qualification-batches" / value["operation_id"]
                request = json.loads((folder / "request.json").read_bytes())
                self.assertEqual(3, len(request["records"]))
                for record in request["records"]:
                    path = folder / "values" / record["value_file"]
                    self.assertEqual(record["value_sha256"], control.sha(path.read_bytes()))
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                observed.append("intent")
            elif kind == "admit":
                marker = value["qualification_batch"]
                path = (
                    self.root
                    / "qualification-batches"
                    / marker["operation_id"]
                    / "receipts"
                    / f"{marker['index']:020d}.json"
                )
                self.assertEqual(marker["receipt_sha256"], control.sha(path.read_bytes()))
                observed.append("admit")
            return original_append(kind, value, **kwargs)

        def helper(batch, folder):
            self.assertEqual(["intent"], observed)
            return self.batch_helper_double(batch, folder)

        with (
            patch.object(self.runtime, "_append", side_effect=append),
            patch.object(self.runtime, "_qualification_batch_helper", side_effect=helper),
            patch.object(self.runtime, "_fence_qualification_batch") as fence,
        ):
            receipts = self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        self.assertEqual([100, 102, 104], [row["offset"] for row in receipts])
        self.assertEqual(["intent", "admit", "admit", "admit"], observed)
        fence.assert_called_once()
        batch = next(iter(self.runtime.state["qualification_batches"].values()))
        self.assertEqual("complete", batch["status"])
        with patch.object(
            self.runtime, "_qualification_batch_helper", side_effect=AssertionError("no resend")
        ):
            reopened = control.Runtime(self.root)
        self.assertEqual(3, reopened.state["admissions"])
        self.assertEqual(
            3, len(next(iter(reopened.state["qualification_batches"].values()))["admitted"])
        )

    def test_qualification_batch_nonzero_recovers_only_certified_prefix_blocks_both_admission_apis(
        self,
    ):
        self.enable_batch_artifact()

        def helper(batch, folder):
            self.batch_helper_double(batch, folder, prefix=1, uncertain=True)
            raise control.RuntimeError("transport_double_lost_reply")

        with (
            patch.object(self.runtime, "_qualification_batch_helper", side_effect=helper),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_incomplete"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        batch = next(iter(self.runtime.state["qualification_batches"].values()))
        self.assertEqual(
            (1, 1, "failed"),
            (self.runtime.state["admissions"], batch["uncertain_index"], batch["status"]),
        )
        for admission in (self.runtime.admit, self.runtime.admit_qualification_batch):
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_worker_blocked"):
                admission(WORKER, self.batch_rows(1))
        self.assertEqual(1, control.Runtime(self.root).state["admissions"])

    def test_qualification_batch_missing_stdout_does_not_manufacture_success(self):
        self.enable_batch_artifact()

        def helper(batch, folder):
            self.batch_helper_double(batch, folder)
            return None

        with (
            patch.object(self.runtime, "_qualification_batch_helper", side_effect=helper),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_incomplete"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        self.assertEqual(3, self.runtime.state["admissions"])
        self.assertEqual(
            "failed", next(iter(self.runtime.state["qualification_batches"].values()))["status"]
        )

    def test_qualification_batch_later_corruption_preserves_earlier_journaled_receipt(self):
        self.enable_batch_artifact()
        with (
            patch.object(
                self.runtime,
                "_qualification_batch_helper",
                side_effect=lambda b, f: self.batch_helper_double(b, f, corrupt=1),
            ),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_receipt"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        self.assertEqual(1, self.runtime.state["admissions"])
        journal = [lifecycle.checked(path) for path in sorted((self.root / "journal").iterdir())]
        self.assertEqual(
            [0],
            [
                row["value"]["qualification_batch"]["index"]
                for row in journal
                if row["kind"] == "admit"
            ],
        )
        operation = next(iter(self.runtime.state["qualification_batches"]))
        path = self.root / "qualification-batches" / operation / "receipts" / f"{1:020d}.json"
        self.assertEqual(-1, json.loads(path.read_bytes())["offset"])

    def test_qualification_batch_crash_after_admit_record_recovers_prefix_once_without_helper_relaunch(
        self,
    ):
        self.enable_batch_artifact()

        def crash(name):
            if name == "after_record_publication":
                entries = sorted((self.root / "journal").iterdir())
                if lifecycle.checked(entries[-1])["kind"] == "admit":
                    raise SystemExit("simulated process crash")

        with (
            patch.object(
                self.runtime, "_qualification_batch_helper", side_effect=self.batch_helper_double
            ),
            patch.object(self.runtime, "_fence_qualification_batch"),
            patch.object(control, "HOOK", side_effect=crash),
        ):
            with self.assertRaises(SystemExit):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        with (
            patch.object(control.Runtime, "_fence_qualification_batch") as fence,
            patch.object(
                control.Runtime,
                "_qualification_batch_helper",
                side_effect=AssertionError("no resend"),
            ),
        ):
            reopened = control.Runtime(self.root)
        fence.assert_called_once()
        self.assertEqual(3, reopened.state["admissions"])
        self.assertEqual(
            "recovered", next(iter(reopened.state["qualification_batches"].values()))["status"]
        )
        self.assertEqual(3, control.Runtime(self.root).state["admissions"])
        with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_worker_blocked"):
            reopened.admit(WORKER, self.batch_rows(1))

    def test_qualification_batch_rejects_unregistered_and_invalid_inputs_before_helper(self):
        with patch.object(self.runtime, "_qualification_batch_helper") as helper:
            with self.assertRaisesRegex(control.RuntimeError, "probe_not_registered"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows(1))
            helper.assert_not_called()
        self.enable_batch_artifact()
        invalid = [
            [],
            self.batch_rows(129),
            [dict(context=dict(run_id=str(uuid.uuid4())))],
            [b"not JSON"],
            [dict(context=dict(run_id=RUN), padding="x" * (2 * control.MIB))],
        ]
        with patch.object(self.runtime, "_qualification_batch_helper") as helper:
            for rows in invalid:
                with self.subTest(rows_count=len(rows)), self.assertRaises(ValueError):
                    self.runtime.admit_qualification_batch(WORKER, rows)
            helper.assert_not_called()
        self.assertEqual({}, self.runtime.state["qualification_batches"])

    def test_qualification_batch_pins_new_artifact_and_fixed_helper_command_limits(self):
        self.enable_batch_artifact()
        captured = []

        def command(arguments, timeout=120):
            captured.append((arguments, timeout))
            return "{}"

        batch = dict(
            operation_id=INCARNATION,
            cluster_id="cluster",
            topic="topic",
            topic_id="topicid",
            request_sha256="1" * 64,
        )
        folder = self.root / "qualification-batches" / INCARNATION
        with patch.object(self.runtime, "_command", side_effect=command):
            self.runtime._qualification_batch_helper(batch, folder)
        arguments, timeout = captured[0]
        self.assertEqual(120, timeout)
        self.assertEqual("512m", arguments[arguments.index("--memory") + 1])
        self.assertEqual("0.5", arguments[arguments.index("--cpus") + 1])
        self.assertEqual("128", arguments[arguments.index("--pids-limit") + 1])
        self.assertEqual(
            "/io/artifacts/runtime.jar:/io/artifacts/producer.jar:/io/artifacts/qualification.jar:/opt/flink/lib/*",
            arguments[arguments.index("-cp") + 1],
        )
        self.assertEqual(
            8,
            len(
                arguments[
                    arguments.index("io.detectbridge.integration.LifecycleBatchProducer") + 1 :
                ]
            ),
        )
        (self.root / "artifacts/qualification.jar").write_bytes(b"changed")
        with self.assertRaises(control.IntegrityError):
            self.runtime._qualification_batch_helper(batch, folder)

    def test_helper_fence_rejects_daemon_errors_and_removes_exact_validated_container_id(self):
        name = self.runtime.config["project"] + "-helper-" + "1" * 12
        result = subprocess.CompletedProcess([], 1, b"", b"Cannot connect to the Docker daemon")
        with patch.object(control.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(control.RuntimeError, "helper_fence_unconfirmed"):
                self.runtime._cleanup_helper(name, "1" * 32)
        labels = {
            "io.detectbridge.p15b.owner": DEPLOYMENT,
            "io.detectbridge.p15b.operation": "1" * 32,
        }
        result = subprocess.CompletedProcess(
            [], 0, control.encoded([dict(Id="a" * 64, Config=dict(Labels=labels))]), b""
        )
        with (
            patch.object(control.subprocess, "run", return_value=result),
            patch.object(self.runtime, "_command", return_value="") as command,
        ):
            self.runtime._cleanup_helper(name, "1" * 32)
        self.assertEqual(["docker", "rm", "-f", "a" * 64], command.call_args.args[0])

    def test_qualification_batch_accepts_128_and_exact_byte_cap_rejects_boundary_plus_one(self):
        self.enable_batch_artifact()
        with (
            patch.object(
                self.runtime, "_qualification_batch_helper", side_effect=self.batch_helper_double
            ),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            self.assertEqual(
                128, len(self.runtime.admit_qualification_batch(WORKER, self.batch_rows(128)))
            )
            prefix = ('{"context":{"run_id":"' + RUN + '"},"padding":"').encode()
            suffix = b'"}'
            wire = prefix + b"x" * (2 * control.MIB - len(prefix) - len(suffix)) + suffix
            self.assertEqual(2 * control.MIB, len(wire))
            self.assertEqual(4, len(self.runtime.admit_qualification_batch(WORKER, [wire] * 4)))
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_bytes"):
                self.runtime.admit_qualification_batch(WORKER, [wire] * 5)
            with self.assertRaisesRegex(control.RuntimeError, "raw_limit"):
                self.runtime.admit_qualification_batch(WORKER, [wire + b" "])
        self.assertEqual(132, self.runtime.state["admissions"])

    def test_qualification_batch_requires_reserve_before_copy_and_counts_orphan_operations(self):
        self.enable_batch_artifact()
        original = self.runtime._reserve

        def reserve(amount, recovery=False):
            if amount == 16 * control.MIB:
                self.assertFalse((self.root / "qualification-batches").exists())
                raise control.RuntimeError("no_capacity")
            return original(amount, recovery)

        with (
            patch.object(self.runtime, "_reserve", side_effect=reserve),
            patch.object(self.runtime, "_qualification_batch_helper") as helper,
        ):
            with self.assertRaisesRegex(control.RuntimeError, "no_capacity"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows(1))
            helper.assert_not_called()
        root = self.root / "qualification-batches"
        root.mkdir(mode=0o700)
        for _ in range(64):
            (root / str(uuid.uuid4())).mkdir(mode=0o700)
        with patch.object(self.runtime, "_qualification_batch_helper") as helper:
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_count"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows(1))
            helper.assert_not_called()
        self.assertEqual(64, len(list(root.iterdir())))

    def test_qualification_batch_surviving_receipts_force_before_journal_then_recover_after_sync_failure(
        self,
    ):
        self.enable_batch_artifact()
        original = lifecycle.sync_directory
        seen = []

        def sync(path):
            if path.name == "receipts" and list(path.iterdir()):
                seen.append(path)
                raise OSError("receipt directory sync unavailable")
            original(path)

        with (
            patch.object(
                self.runtime, "_qualification_batch_helper", side_effect=self.batch_helper_double
            ),
            patch.object(self.runtime, "_fence_qualification_batch"),
            patch.object(lifecycle, "sync_directory", side_effect=sync),
        ):
            with self.assertRaises(OSError):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        self.assertTrue(seen)
        self.assertEqual(0, self.runtime.state["admissions"])
        with patch.object(
            control.Runtime, "_qualification_batch_helper", side_effect=AssertionError("no resend")
        ):
            reopened = control.Runtime(self.root)
        self.assertEqual(3, reopened.state["admissions"])
        self.assertEqual(
            "failed", next(iter(reopened.state["qualification_batches"].values()))["status"]
        )
        with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_worker_blocked"):
            reopened.admit(WORKER, self.batch_rows(1))

    def test_qualification_batch_journal_anchors_exact_ack_timestamp_bytes(self):
        self.enable_batch_artifact()
        with (
            patch.object(
                self.runtime, "_qualification_batch_helper", side_effect=self.batch_helper_double
            ),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            self.runtime.admit_qualification_batch(WORKER, self.batch_rows(1))
        operation = next(iter(self.runtime.state["qualification_batches"]))
        folder = self.root / "qualification-batches" / operation
        ack_path = folder / "acknowledgments" / f"{0:020d}.json"
        receipt_path = folder / "receipts" / f"{0:020d}.json"
        ack = json.loads(ack_path.read_bytes())
        receipt = json.loads(receipt_path.read_bytes())
        ack["broker_timestamp"] = 1000
        ack_path.write_bytes(control.encoded(ack))
        receipt.update(
            broker_timestamp=1000, acknowledgment_sha256=control.sha(ack_path.read_bytes())
        )
        receipt_path.write_bytes(control.encoded(receipt))
        with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_admit_conflict"):
            control.Runtime(self.root)

    def test_qualification_batch_raw_ack_and_missing_receipt_never_admit_or_resend(self):
        self.enable_batch_artifact()

        def helper(batch, folder):
            self.batch_helper_double(batch, folder, prefix=0, uncertain=True)
            raise control.RuntimeError("post_send_namespace_unavailable")

        with (
            patch.object(self.runtime, "_qualification_batch_helper", side_effect=helper),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            with self.assertRaisesRegex(control.RuntimeError, "qualification_batch_incomplete"):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows())
        self.assertEqual(0, self.runtime.state["admissions"])
        batch = next(iter(self.runtime.state["qualification_batches"].values()))
        self.assertEqual(0, batch["uncertain_index"])
        with patch.object(
            control.Runtime, "_qualification_batch_helper", side_effect=AssertionError("no resend")
        ):
            self.assertEqual(0, control.Runtime(self.root).state["admissions"])

    def test_helper_fence_accepts_actual_docker29_lowercase_missing_message(self):
        token = "1" * 32
        name = self.runtime.config["project"] + "-helper-" + token[:12]
        result = subprocess.CompletedProcess(
            [], 1, b"", ("error: no such object: " + name + "\n").encode()
        )
        with (
            patch.object(control.subprocess, "run", return_value=result),
            patch.object(self.runtime, "_command") as remove,
        ):
            self.runtime._cleanup_helper(name, token)
        remove.assert_not_called()

    def check_bad_later_metadata_prefix(self, symlink):
        self.enable_batch_artifact()
        outside = self.folder / "outside-never-walk"
        outside.mkdir(mode=0o700)
        sentinel = outside / "foreign-file"
        sentinel.write_bytes(b"unchanged external bytes")
        before = sentinel.stat()

        def helper(batch, folder):
            result = self.batch_helper_double(batch, folder, prefix=1, uncertain=True)
            path = folder / "receipts" / f"{1:020d}.json"
            if symlink:
                path.symlink_to(outside, target_is_directory=True)
            else:
                path.mkdir(mode=0o700)
                # A nested foreign file must not be traversed before the earlier prefix is durable.
                (path / "untrusted-child").write_bytes(b"invalid metadata namespace")
            return result

        with (
            patch.object(self.runtime, "_qualification_batch_helper", side_effect=helper),
            patch.object(self.runtime, "_fence_qualification_batch"),
        ):
            with self.assertRaises(ValueError):
                self.runtime.admit_qualification_batch(WORKER, self.batch_rows(2))
        self.assertEqual(1, self.runtime.state["admissions"])
        admissions = [
            lifecycle.checked(path)
            for path in (self.root / "journal").iterdir()
            if lifecycle.checked(path)["kind"] == "admit"
        ]
        self.assertEqual([0], [row["value"]["qualification_batch"]["index"] for row in admissions])
        self.assertEqual(b"unchanged external bytes", sentinel.read_bytes())
        self.assertEqual(
            (before.st_mode, before.st_ino), (sentinel.stat().st_mode, sentinel.stat().st_ino)
        )

    def test_qualification_batch_later_metadata_directory_preserves_certified_prefix(self):
        self.check_bad_later_metadata_prefix(False)

    def test_qualification_batch_later_metadata_symlink_to_directory_preserves_certified_prefix(
        self,
    ):
        self.check_bad_later_metadata_prefix(True)

    def test_qualification_orphan_metadata_rejected_but_preintent_inputs_retained(self):
        root = self.root / "qualification-batches"
        root.mkdir(mode=0o700)
        folder = root / str(uuid.uuid4())
        folder.mkdir(mode=0o700)
        for role in ("values", "attempts", "acknowledgments", "receipts"):
            (folder / role).mkdir(mode=0o700)
        partial = folder / (".partial-" + str(uuid.uuid4()))
        lifecycle.write_exclusive(partial, b"unfinished pre-intent request")
        source = folder / "values" / f"{0:020d}.value"
        lifecycle.write_exclusive(source, b"pre-intent source bytes")
        self.assertEqual({}, control.Runtime(self.root).state["qualification_batches"])
        self.assertEqual(b"unfinished pre-intent request", partial.read_bytes())
        target = self.folder / "external-marker"
        target.write_bytes(b"external unchanged")
        for role, kind in (
            ("attempts", "wrong-mode"),
            ("acknowledgments", "symlink"),
            ("receipts", "directory"),
        ):
            with self.subTest(role=role, kind=kind):
                marker = folder / role / f"{0:020d}.json"
                if kind == "symlink":
                    marker.symlink_to(target)
                elif kind == "directory":
                    marker.mkdir(mode=0o700)
                else:
                    marker.write_bytes(b"orphan effect metadata")
                    marker.chmod(0o644)
                with self.assertRaisesRegex(
                    control.RuntimeError, "qualification_batch_orphan_metadata"
                ):
                    control.Runtime(self.root)
                if kind == "directory":
                    marker.rmdir()
                else:
                    marker.unlink()
        self.assertEqual(b"pre-intent source bytes", source.read_bytes())
        self.assertEqual(b"external unchanged", target.read_bytes())

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
