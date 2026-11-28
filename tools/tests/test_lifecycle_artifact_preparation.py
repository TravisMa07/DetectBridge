"""Independent preparation guards with explicit transport doubles, not worker proof."""

import base64
import copy
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lifecycle_runtime as control
import test_lifecycle_runtime_controller as fixtures

OTHER_WORKER = "71500000-0000-4000-8000-000000000022"
OTHER_INCARNATION = "71500000-0000-4000-8000-000000000023"
OTHER_RUN = "71500000-0000-4000-8000-000000000102"


class ArtifactPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Compose the fixture; do not subclass/import its TestCase into discovery.
        fixtures.ControllerTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.ControllerTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime, self.store = self.fixture.runtime, self.fixture.store
        artifact = b"qualification artifact transport double"
        control.local.write_exclusive(self.runtime.root / "artifacts/qualification.jar", artifact)
        self.runtime.config["qualification_sha256"] = control.sha(artifact)
        control.save(self.runtime.root / "config.json", self.runtime.config)
        other = dict(
            self.fixture.registration,
            worker_id=OTHER_WORKER,
            incarnation=OTHER_INCARNATION,
            public_key=base64.b64encode(b"second synthetic worker key").decode(),
            input_topic="test.other-input",
            input_topic_id="other-input-id",
            assigned_runs=[OTHER_RUN],
        )
        self.registrations = [self.fixture.registration, other]
        self.jobs = {
            row["worker_id"]: dict(
                worker_id=row["worker_id"],
                incarnation=row["incarnation"],
                job_id=("a" if index == 0 else "b") * 32,
                state="running",
            )
            for index, row in enumerate(self.registrations)
        }
        with self.runtime._locked():
            self.runtime._load()
            self.runtime._append("worker", dict(other, flink_project="detectbridge-p15b-other"))
            for job in self.jobs.values():
                self.runtime._append("launch", job)
        initial = self.proposal(1, "activate")
        self.current = self.runtime.publish(self.store, initial, self.registrations, 0, None)
        self.proposal_a = self.proposal(2, "rollback")
        self.start_sent = len(self.fixture.sent)
        self.cp = 20
        self.group: dict[str, Any] | None = None
        self.checkpoint_status = "COMPLETED"
        self.cursor_overrides: dict[str, int] = {}
        self.cursor_topics: dict[str, Any] = {}
        self.rejections: dict[str, Any] = {
            row["worker_id"]: dict(count=0, sha256=None) for row in self.registrations
        }
        self.expected_group = dict(
            worker_id=fixtures.WORKER,
            key=dict(
                run_id=fixtures.RUN,
                source="linux.audit",
                host_id=fixtures.WORKER,
                generation=fixtures.INCARNATION,
                audit_timestamp="1700000000.001",
                audit_serial="42",
            ),
            members=[
                dict(
                    record_id="sha256:" + f"{index:064x}",
                    evidence_sha256="1" * 64,
                    raw_sha256="2" * 64,
                    context_sha256="3" * 64,
                )
                for index in range(5)
            ],
        )
        self.scope_count = 0
        self.addCleanup(patch.stopall)
        patch.object(self.runtime, "checkpoints", side_effect=self.checkpoints).start()
        patch.object(self.runtime, "rest", side_effect=self.rest).start()
        patch.object(self.runtime, "_worker_file", side_effect=self.worker_file).start()

    def proposal(self, revision, action):
        proposal = self.fixture.proposal(revision=revision, action=action)
        proposal["participants"] = [
            {key: row[key] for key in ("worker_id", "incarnation")} for row in self.registrations
        ]
        self.store.requests[proposal["request_id"]] = (
            "prepared transport double",
            dict(command=proposal),
        )
        return proposal

    def checkpoints(self, _worker):
        return dict(latest=dict(completed=dict(id=self.cp, status="COMPLETED")))

    def rest(self, _worker, path, *_args, **_kwargs):
        if "/checkpoints/details/" in path:
            return dict(id=int(path.rsplit("/", 1)[1]), status=self.checkpoint_status)
        return dict(state="RUNNING")

    def artifact_next(self):
        return 1 + max(
            row["receipt"]["offset"] for row in self.fixture.sent if row["role"] == "artifact"
        )

    def worker_file(self, worker, path, **_kwargs):
        checkpoint = int(Path(path).stem)
        descriptor = self.runtime.state["broker"]["topics"]["artifact"]
        return dict(
            checkpoint_id=checkpoint,
            snapshot_sha256=control.identity(dict(worker=worker, checkpoint=checkpoint)),
            selection=dict(
                revision=self.current["revision"],
                command_sha256=self.current["command_sha256"],
                origin_incarnation=self.jobs[worker]["incarnation"],
            ),
            artifact_cursor=dict(
                cluster_id="synthetic-cluster",
                topic=copy.deepcopy(self.cursor_topics.get(worker, descriptor)),
                next_offset=self.cursor_overrides.get(worker, self.artifact_next()),
            ),
            rejection_head=copy.deepcopy(self.rejections[worker]),
            machine=dict(
                groups=[copy.deepcopy(self.group)]
                if self.group is not None and worker == fixtures.WORKER
                else []
            ),
        )

    def scope(self):
        self.scope_count += 1
        return self.runtime.qualification_artifact_preparation(
            self.store,
            self.proposal_a,
            self.registrations,
            self.current["revision"],
            self.current["command_sha256"],
            expected_open_group=self.expected_group,
            evidence_root=self.fixture.folder / ("preparation-" + str(self.scope_count)),
        )

    def ready(self, token):
        self.cp += 1
        return self.runtime.qualification_artifact_readiness(token)

    def observe_open_group(self):
        self.group = dict(
            key=copy.deepcopy(self.expected_group["key"]),
            members=copy.deepcopy(self.expected_group["members"]),
            opened=1000,
            deadline=31000,
        )
        self.cp += 1
        return self.runtime.worker_inventory(fixtures.WORKER, self.cp)

    def authorize(self, token):
        self.observe_open_group()
        return self.runtime.qualification_authorize_artifacts(token, fixtures.WORKER, self.cp)

    def publish_a(self):
        return self.runtime.publish(
            self.store,
            self.proposal_a,
            self.registrations,
            self.current["revision"],
            self.current["command_sha256"],
        )

    def new_roles(self):
        return [row["role"] for row in self.fixture.sent[self.start_sent :]]

    def test_artifact_only_preparation_preserves_guarded_admission_then_exact_control(self):
        with self.scope() as token:
            self.assertNotIsInstance(token, (dict, str, bytes, int))
            self.assertEqual(["artifact", "artifact"], self.new_roles())
            self.assertEqual(1, self.runtime.status()["revision"])
            # Scope yields without either nonreentrant lock and with B fully published.
            admitted = self.runtime.admit(
                fixtures.WORKER, [dict(kind="run_end", run_id=fixtures.RUN)]
            )
            self.assertEqual(1, len(admitted))
            self.assertTrue(self.ready(token))
            self.authorize(token)
            published = self.publish_a()
            self.assertEqual(2, published["revision"])
            self.assertEqual(["artifact", "artifact", "input", "control"], self.new_roles())
        with self.assertRaises(ValueError):
            self.runtime.qualification_artifact_readiness(token)

    def test_transport_ack_alone_cannot_publish_before_worker_readiness(self):
        with self.scope():
            with self.assertRaises(ValueError):
                self.publish_a()
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_readiness_requires_every_worker_cursor_covering_frozen_artifact_prefix(self):
        with self.scope() as token:
            self.cursor_overrides[OTHER_WORKER] = self.artifact_next() - 1
            self.assertFalse(self.ready(token))
            with self.assertRaises(ValueError):
                self.publish_a()
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_new_rejection_fails_readiness_instead_of_treating_cursor_as_installation(self):
        with self.scope() as token:
            self.rejections[OTHER_WORKER] = dict(count=1, sha256="f" * 64)
            with self.assertRaises(ValueError):
                self.ready(token)
        self.assertEqual(1, self.runtime.status()["revision"])

    def test_readiness_is_not_the_later_five_member_proof(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            with self.assertRaises(ValueError):
                self.runtime.qualification_authorize_artifacts(token, fixtures.WORKER, self.cp)
        self.assertNotIn("control", self.new_roles())

    def test_advisory_or_caller_supplied_proof_cannot_authorize_reuse(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.group = dict(
                key=copy.deepcopy(self.expected_group["key"]),
                members=copy.deepcopy(self.expected_group["members"]),
                opened=1000,
                deadline=31000,
            )
            self.cp += 1
            self.runtime.advisory_inventory(fixtures.WORKER, self.cp)
            with self.assertRaises(ValueError):
                self.runtime.qualification_authorize_artifacts(token, fixtures.WORKER, self.cp)
        with self.assertRaises(ValueError):
            self.runtime.qualification_artifact_readiness(dict(receipts=self.fixture.sent))
        self.assertNotIn("control", self.new_roles())

    def test_exact_member_hashes_and_original_deadline_are_mandatory(self):
        for change in ("member", "deadline", "run"):
            self.group = None
            with self.subTest(change=change), self.scope() as token:
                self.assertTrue(self.ready(token))
                self.observe_open_group()
                assert self.group is not None
                if change == "member":
                    self.group["members"][0]["raw_sha256"] = "f" * 64
                elif change == "deadline":
                    self.group["deadline"] += 1
                else:
                    self.group["key"]["run_id"] = OTHER_RUN
                self.cp += 1
                with self.assertRaises(ValueError):
                    self.runtime.worker_inventory(fixtures.WORKER, self.cp)
                    self.runtime.qualification_authorize_artifacts(token, fixtures.WORKER, self.cp)
            self.assertEqual(1, self.runtime.status()["revision"])
            self.assertNotIn("control", self.new_roles())

    def test_none_forged_or_deserialized_token_cannot_use_an_active_scope(self):
        for operation in ("readiness", "authorize"):
            for kind in ("none", "forged", "deserialized"):
                self.group = None
                with self.subTest(operation=operation, token=kind), self.scope() as token:
                    supplied = (
                        None
                        if kind == "none"
                        else object()
                        if kind == "forged"
                        else dict(receipts=[])
                    )
                    if operation == "authorize":
                        self.assertTrue(self.ready(token))
                        self.observe_open_group()
                    with self.assertRaises(ValueError):
                        if operation == "readiness":
                            self.runtime.qualification_artifact_readiness(supplied)
                        else:
                            self.runtime.qualification_authorize_artifacts(
                                supplied, fixtures.WORKER, self.cp
                            )
                self.assertEqual(1, self.runtime.status()["revision"])
                self.assertNotIn("control", self.new_roles())

    def test_uncompleted_checkpoint_cannot_authorize_even_with_exact_inventory(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.group = dict(
                key=copy.deepcopy(self.expected_group["key"]),
                members=copy.deepcopy(self.expected_group["members"]),
                opened=1000,
                deadline=31000,
            )
            self.cp += 1
            self.checkpoint_status = "IN_PROGRESS"
            with self.assertRaises(ValueError):
                self.runtime.worker_inventory(fixtures.WORKER, self.cp)
            with self.assertRaises(ValueError):
                self.runtime.qualification_authorize_artifacts(token, fixtures.WORKER, self.cp)
        self.assertNotIn("control", self.new_roles())

    def test_wrong_topic_cursor_cannot_establish_retained_artifact_readiness(self):
        with self.scope() as token:
            descriptor = self.runtime.state["broker"]["topics"]["artifact"]
            self.cursor_topics[OTHER_WORKER] = dict(descriptor, id="different-artifact-topic")
            with self.assertRaises(ValueError):
                self.ready(token)
        self.assertNotIn("control", self.new_roles())

    def test_successful_use_consumes_capability_and_cannot_authorize_again(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            self.publish_a()
            before = len(self.fixture.sent)
            with self.assertRaises(ValueError):
                self.runtime.qualification_authorize_artifacts(token, fixtures.WORKER, self.cp)
            self.assertEqual(before, len(self.fixture.sent))
        self.assertEqual(2, self.runtime.status()["revision"])

    def test_changed_valid_proposal_cannot_reuse_prepared_receipts(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            other = self.proposal(3, "rollback")
            with self.assertRaises(ValueError):
                self.runtime.publish(
                    self.store, other, self.registrations, 1, self.current["command_sha256"]
                )
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_changed_cas_cannot_reuse_preparation(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            with self.assertRaises(ValueError):
                self.runtime.publish(
                    self.store,
                    self.proposal_a,
                    self.registrations,
                    self.current["revision"] + 1,
                    self.current["command_sha256"],
                )
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_changed_registration_cannot_reuse_preparation(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            changed = copy.deepcopy(self.registrations)
            changed[0]["assigned_runs"] = []
            with self.assertRaises(ValueError):
                self.runtime.publish(
                    self.store, self.proposal_a, changed, 1, self.current["command_sha256"]
                )
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_changed_authority_or_artifact_topic_context_cannot_reuse_preparation(self):
        for changed in ("authority", "artifact-topic"):
            self.group = None
            with self.subTest(changed=changed):
                original_config = copy.deepcopy(self.runtime.config)
                try:
                    with self.scope() as token:
                        self.assertTrue(self.ready(token))
                        self.authorize(token)
                        if changed == "authority":
                            self.runtime.config["authority_id"] = OTHER_RUN
                            control.save(self.runtime.root / "config.json", self.runtime.config)
                            with self.assertRaises(ValueError):
                                self.publish_a()
                        else:
                            load = self.runtime._load

                            def changed_topic():
                                load()
                                self.runtime.state["broker"]["topics"]["artifact"]["id"] = (
                                    "replacement-topic-id"
                                )

                            # Explicit changed-namespace state double after ordinary replay.
                            with patch.object(self.runtime, "_load", side_effect=changed_topic):
                                with self.assertRaises(ValueError):
                                    self.publish_a()
                finally:
                    self.runtime.config = original_config
                    control.save(self.runtime.root / "config.json", original_config)
                self.assertEqual(1, self.runtime.status()["revision"])
                self.assertNotIn("control", self.new_roles())

    def test_changed_job_invalidates_preparation_before_publication(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            changed = dict(self.jobs[OTHER_WORKER], job_id="c" * 32)
            with self.runtime._locked():
                self.runtime._load()
                self.runtime._append("launch", changed)
            with self.assertRaises(ValueError):
                self.publish_a()
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_changed_deployed_artifact_bytes_cannot_be_reused(self):
        target = self.runtime.root / "bundles" / self.proposal_a["bundle_sha256"] / "plan.json"
        original = target.read_bytes()
        try:
            with self.scope() as token:
                self.assertTrue(self.ready(token))
                self.authorize(token)
                target.write_bytes(original + b" ")
                with self.assertRaises(ValueError):
                    self.publish_a()
        finally:
            target.write_bytes(original)
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())

    def test_partial_preparation_preserves_original_error_and_no_reuse_capability(self):
        original = OSError("owned preparation send uncertainty")
        send = self.runtime._send_bytes
        seen = [0]

        def uncertain(*args, **kwargs):
            result = send(*args, **kwargs)
            seen[0] += 1
            if seen[0] == 2:
                raise original
            return result

        with patch.object(self.runtime, "_send_bytes", side_effect=uncertain):
            with self.assertRaises(OSError) as caught:
                with self.scope():
                    self.fail("uncertain preparation must not yield a capability")
        self.assertIs(original, caught.exception)
        self.assertEqual(1, self.runtime.status()["revision"])
        self.assertNotIn("control", self.new_roles())
        failed = self.fixture.folder / ("preparation-" + str(self.scope_count))
        self.assertTrue((failed / "0.wire").is_file())
        self.assertTrue((failed / "0.attempt.json").is_file())
        self.assertTrue((failed / "0.receipt.json").is_file())
        self.assertTrue((failed / "1.wire").is_file())
        self.assertTrue((failed / "1.attempt.json").is_file())
        self.assertFalse((failed / "1.receipt.json").exists())
        before = len(self.fixture.sent)
        self.publish_a()
        self.assertEqual(
            ["artifact", "artifact", "control"], [row["role"] for row in self.fixture.sent[before:]]
        )

    def test_control_uncertainty_keeps_pending_admission_guard_and_default_retry(self):
        def fail(phase):
            if phase == "before_control_publication":
                raise OSError("after adoption before effective control")

        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            with patch("lifecycle_runtime.HOOK", side_effect=fail), self.assertRaises(OSError):
                self.publish_a()
            self.assertEqual("adopted_pending", self.runtime.status()["publication"])
            with self.assertRaises(ValueError):
                self.runtime.admit(fixtures.WORKER, [dict(kind="run_end", run_id=fixtures.RUN)])
        before = len(self.fixture.sent)
        self.publish_a()
        self.assertEqual(
            ["artifact", "artifact", "control"], [row["role"] for row in self.fixture.sent[before:]]
        )

    def test_normal_completed_restore_path_accounting_keeps_job_identity_valid(self):
        with self.scope() as token:
            with self.runtime._locked():
                self.runtime._load()
                job = self.runtime.state["jobs"][fixtures.WORKER]
                self.runtime._append(
                    "start",
                    dict(
                        job,
                        completed_restore_paths=[
                            "file:///state/checkpoints/" + job["job_id"] + "/chk-21"
                        ],
                    ),
                )
            self.assertTrue(self.ready(token))
            self.authorize(token)
            self.assertIsNotNone(self.publish_a()["receipt"])
        self.assertEqual(["artifact", "artifact", "control"], self.new_roles())

    def test_unavailable_truncated_prefix_error_invalidates_without_control(self):
        # Explicit transport error double, not a real Kafka truncation claim.
        with self.scope() as token:
            with patch.object(
                self.runtime, "_worker_file", side_effect=ValueError("lifecycle_preservation_gap")
            ):
                with self.assertRaisesRegex(ValueError, "lifecycle_preservation_gap"):
                    self.ready(token)
            with self.assertRaises(ValueError):
                self.publish_a()
        self.assertNotIn("control", self.new_roles())

    def test_successful_context_mutator_invalidates_preparation(self):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            self.runtime.worker(fixtures.WORKER)
            with self.assertRaises(ValueError):
                self.publish_a()
        self.assertNotIn("control", self.new_roles())

    def test_resulting_intent_binding_rejects_self_consistent_replaced_intent(self):
        finish = self.runtime._finish_publication
        path = self.runtime.root / "publications" / "2.json"
        originals = {}

        def replace_intent(entry):
            originals["wire"] = path.read_bytes()
            originals["entry"] = entry
            originals["sha"] = entry["intent_sha256"]
            intent = control.checked(path)
            intent["unbound_extra"] = True
            control.save(path, intent)
            entry["intent_sha256"] = control.identity(intent)
            return finish(entry)

        try:
            with self.scope() as token:
                self.assertTrue(self.ready(token))
                self.authorize(token)
                with patch.object(self.runtime, "_finish_publication", side_effect=replace_intent):
                    with self.assertRaises(ValueError):
                        self.publish_a()
            self.assertNotIn("control", self.new_roles())
        finally:
            if originals:
                path.write_bytes(originals["wire"])
                originals["entry"]["intent_sha256"] = originals["sha"]

    def assert_early_argument_failure_invalidates(self, operation):
        with self.scope() as token:
            self.assertTrue(self.ready(token))
            self.authorize(token)
            with self.assertRaises(ValueError):
                operation()
            with self.assertRaises(ValueError):
                self.publish_a()
        self.assertNotIn("control", self.new_roles())

    def test_early_argument_publish_failure_invalidates_authorized_reuse(self):
        self.assert_early_argument_failure_invalidates(
            lambda: self.runtime.publish(
                object(), self.proposal_a, self.registrations, 1, self.current["command_sha256"]
            )
        )

    def test_early_argument_checkpoint_failure_invalidates_authorized_reuse(self):
        self.assert_early_argument_failure_invalidates(
            lambda: self.runtime.worker_inventory(fixtures.WORKER, -1)
        )

    def test_early_argument_admission_failure_invalidates_authorized_reuse(self):
        self.assert_early_argument_failure_invalidates(
            lambda: self.runtime.admit_qualification_batch(fixtures.WORKER, [])
        )

    def test_scope_exception_invalidates_token_without_replacing_original_error(self):
        original = RuntimeError("original scope failure")
        token = None
        with self.assertRaises(RuntimeError) as caught:
            with self.scope() as token:
                self.assertTrue(self.ready(token))
                raise original
        self.assertIs(original, caught.exception)
        with self.assertRaises(ValueError):
            self.runtime.qualification_artifact_readiness(token)
        self.assertEqual(1, self.runtime.status()["revision"])


if __name__ == "__main__":
    unittest.main()
