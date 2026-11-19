"""Independent runtime-oracle mutation tests; no Docker or new evaluator execution."""

import base64
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifecycle_runtime_cases import (
    DEPLOYMENT,
    ROOT,
    Oracle,
    check_packet,
    digest,
    document,
    encoded,
    identity,
    output_id,
    phase_cases,
    prepare,
    semantic_output,
    sha,
)
from linux_assembly_verify import transport_id


class LifecycleRuntimeOracleTests(unittest.TestCase):
    temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    bundles: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve())
        cls.bundles = prepare(Path(cls.temporary.name) / "bundles")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.case = phase_cases(1)[0]
        self.publication = dict(revision=1, command_sha256="1" * 64)
        self.registration = dict(
            worker_id=self.case["worker_id"], incarnation="71500000-0000-4000-8000-000000000031"
        )
        self.binding = "f" * 64
        row = self.case["admissions"][0]
        self.receipt = dict(
            cluster_id="synthetic-cluster",
            topic_id="synthetic-input",
            topic="synthetic.input",
            partition=0,
            offset=0,
            value_sha256=sha(encoded(row)),
        )
        self.oracle = Oracle(self.bundles)
        self.oracle.add(
            self.case, "A", self.publication, self.registration, [self.receipt], self.binding
        )

    def envelope(self, kind, body):
        from integration_oracle import FIELDS

        manifest = self.bundles["A"]["manifest"]
        value = dict(
            version="1.0.0",
            deployment_id=DEPLOYMENT,
            worker_id=self.registration["worker_id"],
            origin_incarnation=self.registration["incarnation"],
            revision=1,
            command_sha256="1" * 64,
            bundle_sha256=manifest["bundle_sha256"],
            plan_sha256=sha(self.bundles["A"]["plan_bytes"]),
            compatibility_sha256=manifest["compatibility_sha256"],
            sequence=0,
            kind=kind,
            inner_key=body[FIELDS[kind]],
            document=copy.deepcopy(body),
            document_sha256=digest(body),
        )
        value["output_id"] = output_id(value)
        value["semantic_sha256"] = semantic_output(value)
        return value

    @staticmethod
    def wire(envelope):
        return dict(
            output=envelope,
            wire=dict(
                key_base64=base64.b64encode(envelope["output_id"].encode()).decode(),
                value_sha256=sha(encoded(envelope)),
            ),
            wire_sha256=sha(encoded(envelope)),
        )

    def bodies(self):
        event = document(ROOT / "packages/windows-adapters/profiles/security.expected.json")
        row = self.case["admissions"][0]
        event["event"]["id"] = self.case["expected"]["event_id"]
        event["detectbridge"]["run_id"] = self.case["run_id"]
        event["detectbridge"]["evidence"] = [
            dict(record_id=row["raw"]["record_id"], evidence=row["raw"]["evidence"])
        ]
        expected = self.oracle.events[(self.case["run_id"], self.case["expected"]["event_id"])]
        tag, detections, diagnostics = expected["legacy"].expected_tag(event, expected["expected"])
        self.assertFalse(diagnostics)
        receipt = dict(
            version="1.0.0",
            id=transport_id(self.binding, self.receipt, "receipt"),
            input=self.receipt,
            kind="input_receipt",
            action="windows_record",
            record_id=row["raw"]["record_id"],
        )
        return [("tagged", tag), *[("detection", d) for d in detections], ("receipt", receipt)]

    def test_packet_static_independent_contracts(self):
        self.assertEqual(14, check_packet()["source_admissions"])
        self.assertEqual(9, check_packet()["binding_vectors"])

    def test_complete_literal_windows_decision_and_exact_retry(self):
        records = [self.wire(self.envelope(kind, body)) for kind, body in self.bodies()]
        self.assertTrue(self.oracle.check(records, complete=True))
        self.assertTrue(self.oracle.check(records, complete=True))
        self.assertEqual(3, len(self.oracle.seen))

    def test_self_consistent_wrong_command_is_rejected(self):
        value = self.envelope(*self.bodies()[0])
        value["command_sha256"] = "2" * 64
        value["output_id"] = output_id(value)
        value["semantic_sha256"] = semantic_output(value)
        with self.assertRaisesRegex(ValueError, "actual_command"):
            self.oracle.check([self.wire(value)])

    def test_wrong_plan_origin_and_full_bundle_are_rejected(self):
        for field, changed in (
            ("plan_sha256", "0" * 64),
            ("bundle_sha256", self.bundles["B"]["manifest"]["bundle_sha256"]),
            ("origin_incarnation", "71500000-0000-4000-8000-000000000099"),
        ):
            value = self.envelope(*self.bodies()[0])
            value[field] = changed
            value["semantic_sha256"] = semantic_output(value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.oracle.check([self.wire(value)])

    def test_wrong_literal_counts_cannot_hide_with_recomputed_checksums(self):
        kind, tag = self.bodies()[0]
        tag["counts"]["matched"] = 0
        with self.assertRaisesRegex(ValueError, "literal_decision"):
            self.oracle.check([self.wire(self.envelope(kind, tag))])

    def test_wrong_source_fields_and_membership_are_rejected(self):
        kind, tag = self.bodies()[0]
        tag["event"]["user"]["name"] = "Bob"
        with self.assertRaises(Exception):
            self.oracle.check([self.wire(self.envelope(kind, tag))])
        kind, tag = self.bodies()[0]
        tag["event"]["event"]["id"] = identity(["foreign-event"])
        with self.assertRaisesRegex(ValueError, "unexpected_event"):
            self.oracle.check([self.wire(self.envelope(kind, tag))])

    def test_wrong_kafka_key_and_physical_receipt_are_rejected(self):
        value = self.envelope(*self.bodies()[0])
        row = self.wire(value)
        row["wire"]["key_base64"] = base64.b64encode(b"wrong").decode()
        with self.assertRaisesRegex(ValueError, "kafka_key"):
            self.oracle.check([row])
        _, receipt = self.bodies()[-1]
        receipt["input"] = {**receipt["input"], "offset": 5}
        with self.assertRaisesRegex(ValueError, "unexpected_receipt"):
            self.oracle.check([self.wire(self.envelope("receipt", receipt))])

    def test_same_identity_changed_exact_intent_is_conflict(self):
        value = self.envelope(*self.bodies()[0])
        self.oracle.check([self.wire(value)])
        changed = copy.deepcopy(value)
        changed["sequence"] = 5
        with self.assertRaisesRegex(ValueError, "immutable_duplicate"):
            self.oracle.check([self.wire(changed)])

    def test_incarnation_and_clocks_do_not_rekey_original_intent(self):
        value = self.envelope(*self.bodies()[0])
        original = output_id(value)
        value["origin_incarnation"] = "71500000-0000-4000-8000-000000000099"
        value["document"]["event"]["event"]["ingested"] = "2026-01-01T00:00:00Z"
        self.assertEqual(original, output_id(value))
        value["revision"] = 3
        self.assertNotEqual(original, output_id(value))

    def test_approved_fault_export_preserves_exact_document_hash(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            private = root / "private"
            (private / "authority").mkdir(parents=True)
            (private / "workers").mkdir()
            (private / "authority/private.der").write_bytes(b"synthetic-private-DER-not-real-key")
            public = root / "reports"
            public.mkdir()
            qualifier = Qualification(
                public, SimpleNamespace(root=private), self.bundles, None, root / "probe.jar"
            )
            detail = {
                "root-exception": "org.apache.kafka.common.errors.RecordTooLargeException: original synthetic fault"
            }
            proof = qualifier.export_approved_fault("required-sink-failure", detail, digest(detail))
            self.assertEqual(encoded(detail), (public / proof["filename"]).read_bytes())
            self.assertEqual(proof["sha256"], sha((public / proof["filename"]).read_bytes()))

    def test_approved_fault_export_rejects_private_key_and_unknown_scope(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            private = root / "private"
            (private / "authority").mkdir(parents=True)
            (private / "workers").mkdir()
            secret = b"synthetic-private-DER-not-real-key"
            (private / "authority/private.der").write_bytes(secret)
            public = root / "reports"
            public.mkdir()
            qualifier = Qualification(
                public, SimpleNamespace(root=private), self.bundles, None, root / "probe.jar"
            )
            detail = {"message": base64.b64encode(secret).decode()}
            with self.assertRaisesRegex(ValueError, "private_key_in_fault_proof"):
                qualifier.export_approved_fault("required-sink-failure", detail, digest(detail))
            with self.assertRaisesRegex(ValueError, "unapproved_fault_export"):
                qualifier.export_approved_fault("unknown-arbitrary-log", {}, digest({}))
            self.assertFalse((public / "approved-fault-proofs").exists())

    def test_convergence_failed_job_is_failfast_and_retains_private_proofs(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            public = root / "reports"
            public.mkdir()
            worker = self.registration["worker_id"]
            job = "a" * 32
            original = dict(jid=job, state="FAILED")
            exceptions = {
                "root-exception": "java.lang.IllegalArgumentException: lifecycle_private_mode"
            }
            runtime = SimpleNamespace(
                root=root / "deployment",
                state=dict(jobs={worker: dict(job_id=job)}),
                rest=Mock(
                    side_effect=lambda _worker, path: (
                        exceptions if path.endswith("/exceptions") else original
                    )
                ),
                observe=Mock(
                    side_effect=AssertionError("failed job must not wait for more acknowledgments")
                ),
            )
            qualifier = Qualification(public, runtime, self.bundles, None, root / "probe.jar")
            with (
                patch(
                    "lifecycle_runtime_verify.time.sleep",
                    side_effect=AssertionError("must fail before polling sleep"),
                ),
                self.assertRaisesRegex(
                    ValueError, "lifecycle_qualification_unexpected_job_failure"
                ),
            ):
                qualifier.converge([worker])
            runtime.observe.assert_not_called()
            self.assertEqual(2, runtime.rest.call_count)
            proof = qualifier.unexpected_job_failures[0]
            self.assertEqual(digest(original), proof["job_response_sha256"])
            self.assertEqual(digest(exceptions), proof["exceptions_sha256"])
            self.assertEqual(["java.lang.IllegalArgumentException"], proof["exception_classes"])
            self.assertEqual(2, len(list((root / "qualification-private-evidence").glob("*.json"))))
            self.assertFalse((public / "approved-fault-proofs").exists())

    def test_ack_named_checkpoint_query_failure_is_retained_without_fallback(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            public = root / "reports"
            public.mkdir()
            worker = self.registration["worker_id"]
            job = "a" * 32
            command = "2" * 64
            failure: Any = RuntimeError("lifecycle_runtime_helper_failed")
            failure.stdout = b""
            failure.stderr = b"curl: (22) The requested URL returned error: 404\n"
            failure.returncode = 22
            ack = dict(
                worker_id=worker,
                incarnation=self.registration["incarnation"],
                command_sha256=command,
                phase="durable",
                checkpoint_id=12,
            )
            runtime = SimpleNamespace(
                root=root / "deployment",
                state=dict(
                    jobs={worker: dict(job_id=job)}, acks={"signed-proof": dict(payload=ack)}
                ),
                rest=Mock(
                    side_effect=lambda _worker, path: (
                        {"history": [{"id": 12, "status": "COMPLETED"}]}
                        if path.endswith("/checkpoints")
                        else dict(state="RUNNING")
                    )
                ),
                observe=Mock(
                    return_value=dict(
                        participants=[dict(worker_id=worker, durable=True, rejected=False)]
                    )
                ),
                worker_inventory=Mock(side_effect=failure),
            )
            qualifier = Qualification(public, runtime, self.bundles, None, root / "probe.jar")
            qualifier.current = dict(revision=2, command_sha256=command)
            qualifier.registrations = [self.registration]
            with self.assertRaises(RuntimeError) as caught:
                qualifier.converge([worker])
            self.assertIs(failure, caught.exception)
            runtime.observe.assert_called_once_with(limit=8)
            runtime.worker_inventory.assert_called_once_with(worker, 12)
            proof = qualifier.query_failures[0]
            self.assertEqual(404, proof["http_status"])
            self.assertEqual(12, proof["checkpoint_id"])
            self.assertEqual(
                sha(("/jobs/" + job + "/checkpoints/details/12").encode()), proof["path_sha256"]
            )
            self.assertEqual(sha(failure.stderr), proof["stderr_sha256"])
            self.assertTrue(proof["stderr_retained_privately"])
            self.assertFalse((public / "approved-fault-proofs").exists())

    def test_evicted_ack_is_unproven_until_fresh_exact_checkpoint_and_cached(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            public = root / "reports"
            public.mkdir()
            worker = self.registration["worker_id"]
            job, command = "a" * 32, "2" * 64
            failure: Any = RuntimeError("lifecycle_runtime_helper_failed")
            failure.stdout, failure.stderr, failure.returncode = (
                b"",
                b"curl: (22) The requested URL returned error: 404\n",
                22,
            )
            ack = dict(
                worker_id=worker,
                incarnation=self.registration["incarnation"],
                command_sha256=command,
                phase="durable",
                checkpoint_id=12,
            )
            history = {
                "history": [{"id": 14, "status": "COMPLETED"}, {"id": 13, "status": "COMPLETED"}]
            }
            state: dict[str, Any] = dict(
                jobs={worker: dict(job_id=job)}, acks={"old": dict(payload=ack)}
            )
            observed = []

            def observe(limit):
                observed.append(limit)
                if len(observed) > 1:
                    state["acks"]["new"] = dict(payload={**ack, "checkpoint_id": 15})
                return dict(participants=[dict(worker_id=worker, durable=True, rejected=False)])

            confirmed = dict(
                checkpoint=dict(id=15, status="COMPLETED"),
                inventory=dict(
                    selection=dict(revision=2, command_sha256=command), snapshot_sha256="f" * 64
                ),
            )
            runtime = SimpleNamespace(
                root=root / "deployment",
                state=state,
                rest=Mock(
                    side_effect=lambda _worker, path: (
                        history if path.endswith("/checkpoints") else dict(state="RUNNING")
                    )
                ),
                observe=Mock(side_effect=observe),
                worker_inventory=Mock(side_effect=[failure, confirmed]),
            )
            qualifier = Qualification(public, runtime, self.bundles, None, root / "probe.jar")
            qualifier.current = dict(revision=2, command_sha256=command)
            qualifier.registrations = [self.registration]
            with patch("lifecycle_runtime_verify.time.sleep"):
                qualifier.converge([worker])
            self.assertEqual([8, 8], observed)
            self.assertEqual(
                [(worker, 12), (worker, 15)],
                [call.args for call in runtime.worker_inventory.call_args_list],
            )
            self.assertEqual(
                "evicted_unproven_wait_for_fresh_signed_ack",
                qualifier.query_failures[0]["retry_disposition"],
            )
            self.assertEqual(digest(history), qualifier.query_failures[0]["history_sha256"])
            self.assertEqual(15, qualifier.checkpoint_evidence[0]["checkpoint_id"])
            qualifier.converge([worker])
            self.assertEqual(2, runtime.worker_inventory.call_count)
            self.assertEqual(1, len(qualifier.checkpoint_evidence))
            qualifier.current = dict(revision=3, command_sha256="3" * 64)
            with self.assertRaisesRegex(ValueError, "durable_proof_missing"):
                qualifier.converge([worker])
            qualifier.current = dict(revision=2, command_sha256=command)
            qualifier.registrations = [
                {**self.registration, "incarnation": "71500000-0000-4000-8000-000000000099"}
            ]
            with self.assertRaisesRegex(ValueError, "durable_proof_missing"):
                qualifier.converge([worker])

    def test_eight_ack_poll_keeps_exact_checkpoint_proof_within_original_deadline(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            worker, job, command = self.registration["worker_id"], "a" * 32, "2" * 64
            ack = dict(
                worker_id=worker,
                incarnation=self.registration["incarnation"],
                command_sha256=command,
                phase="durable",
                checkpoint_id=15,
            )
            proof = dict(
                checkpoint=dict(id=15, status="COMPLETED"),
                inventory=dict(
                    selection=dict(revision=2, command_sha256=command),
                    snapshot_sha256="f" * 64,
                ),
            )
            clock = [0.0]
            status = dict(participants=[dict(worker_id=worker, durable=True, rejected=False)])

            def proportional_observe(limit):
                # Deterministic cost model, not a measured throughput/runtime assertion.
                clock[0] += 4 * limit
                return status

            runtime = SimpleNamespace(
                root=root / "deployment",
                state=dict(
                    jobs={worker: dict(job_id=job)}, acks={"authenticated": dict(payload=ack)}
                ),
                rest=Mock(return_value=dict(state="RUNNING")),
                observe=Mock(side_effect=proportional_observe),
                worker_inventory=Mock(return_value=proof),
            )
            qualifier = Qualification(root, runtime, self.bundles, None, root / "probe.jar")
            qualifier.current = dict(revision=2, command_sha256=command)
            qualifier.registrations = [self.registration]
            with patch("lifecycle_runtime_verify.time.monotonic", side_effect=lambda: clock[0]):
                self.assertIs(status, qualifier.converge([worker], timeout=120))
            runtime.observe.assert_called_once_with(limit=8)
            runtime.worker_inventory.assert_called_once_with(worker, 15)
            self.assertEqual(32, clock[0])
            self.assertEqual(15, qualifier.checkpoint_evidence[0]["checkpoint_id"])
            self.assertEqual(digest(proof), qualifier.checkpoint_evidence[0]["confirmation_sha256"])
            self.assertTrue(qualifier.confirmed_ack_checkpoints)
            # The same modeled per-record cost for a32-record poll crosses the original
            # deadline; even a truthy complete predicate may not turn that into success.
            clock[0] = 0
            with (
                patch("lifecycle_runtime_verify.time.monotonic", side_effect=lambda: clock[0]),
                self.assertRaisesRegex(ValueError, "timeout_counterfactual_large_poll"),
            ):
                qualifier.wait(
                    lambda: proportional_observe(32), "counterfactual_large_poll", timeout=120
                )
            self.assertEqual(128, clock[0])

    def test_failed_checkpoint_is_not_an_eviction_or_completion_fallback(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            public = root / "reports"
            public.mkdir()
            worker, job, command = self.registration["worker_id"], "a" * 32, "2" * 64
            failure = ValueError("lifecycle_runtime_checkpoint_not_completed")
            ack = dict(
                worker_id=worker,
                incarnation=self.registration["incarnation"],
                command_sha256=command,
                phase="durable",
                checkpoint_id=12,
            )
            runtime = SimpleNamespace(
                root=root / "deployment",
                state=dict(jobs={worker: dict(job_id=job)}, acks={"proof": dict(payload=ack)}),
                rest=Mock(return_value=dict(state="RUNNING")),
                observe=Mock(
                    return_value=dict(
                        participants=[dict(worker_id=worker, durable=True, rejected=False)]
                    )
                ),
                worker_inventory=Mock(side_effect=failure),
            )
            qualifier = Qualification(public, runtime, self.bundles, None, root / "probe.jar")
            qualifier.current = dict(revision=2, command_sha256=command)
            qualifier.registrations = [self.registration]
            with self.assertRaisesRegex(ValueError, "checkpoint_not_completed"):
                qualifier.converge([worker])
            self.assertEqual(1, runtime.rest.call_count)
            self.assertFalse(qualifier.confirmed_ack_checkpoints)
            self.assertNotIn("retry_disposition", qualifier.query_failures[0])

    def test_missing_same_job_history_after_checkpoint_404_cannot_retry(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            public = root / "reports"
            public.mkdir()
            worker, job, command = self.registration["worker_id"], "a" * 32, "2" * 64
            missing: Any = RuntimeError("lifecycle_runtime_helper_failed")
            missing.stdout, missing.stderr, missing.returncode = (
                b"",
                b"curl: (22) The requested URL returned error: 404\n",
                22,
            )
            ack = dict(
                worker_id=worker,
                incarnation=self.registration["incarnation"],
                command_sha256=command,
                phase="durable",
                checkpoint_id=12,
            )

            def rest(_worker, path):
                if path.endswith("/checkpoints"):
                    raise missing
                return dict(state="RUNNING")

            runtime = SimpleNamespace(
                root=root / "deployment",
                state=dict(jobs={worker: dict(job_id=job)}, acks={"proof": dict(payload=ack)}),
                rest=Mock(side_effect=rest),
                observe=Mock(
                    return_value=dict(
                        participants=[dict(worker_id=worker, durable=True, rejected=False)]
                    )
                ),
                worker_inventory=Mock(side_effect=missing),
            )
            qualifier = Qualification(public, runtime, self.bundles, None, root / "probe.jar")
            qualifier.current = dict(revision=2, command_sha256=command)
            qualifier.registrations = [self.registration]
            with (
                patch(
                    "lifecycle_runtime_verify.time.sleep",
                    side_effect=AssertionError("missing job history cannot be retried"),
                ),
                self.assertRaises(RuntimeError) as caught,
            ):
                qualifier.converge([worker])
            self.assertIs(missing, caught.exception)
            runtime.worker_inventory.assert_called_once_with(worker, 12)
            self.assertEqual(2, len(qualifier.query_failures))
            self.assertEqual("checkpoint-history", qualifier.query_failures[-1]["endpoint_family"])
            self.assertFalse(qualifier.confirmed_ack_checkpoints)

    def test_wait_rejects_late_truthy_result_without_extending_deadline(self):
        from lifecycle_runtime_verify import Qualification

        qualifier = object.__new__(Qualification)
        with (
            patch("lifecycle_runtime_verify.time.monotonic", side_effect=[0.0, 0.1, 1.001]),
            patch("lifecycle_runtime_verify.time.sleep") as sleep,
            self.assertRaisesRegex(ValueError, "lifecycle_qualification_timeout_late_result"),
        ):
            qualifier.wait(lambda: True, "late_result", timeout=1)
        sleep.assert_not_called()
        with patch("lifecycle_runtime_verify.time.monotonic", side_effect=[0.0, 0.1, 1.0]):
            self.assertTrue(qualifier.wait(lambda: True, "at_deadline", timeout=1))

    def test_timeout_snapshot_requires_actual_hash_inventory_and_candidate(self):
        from lifecycle_runtime_verify import Qualification

        selection = dict(revision=2, command_sha256="2" * 64)
        marker = dict(checkpoint_id=7, selection=selection, snapshot_sha256="a" * 64)
        inventory = dict(
            checkpoint_id=7,
            selection=selection,
            snapshot_sha256="a" * 64,
            durable_ack_candidates=[
                dict(
                    checkpoint_id=7,
                    ack=dict(
                        payload=dict(checkpoint_id=7, phase="durable", command_sha256="2" * 64)
                    ),
                )
            ],
        )
        observed = Qualification.uncompleted_snapshot_observation(marker, inventory)
        self.assertEqual("a" * 64, observed["snapshot_sha256"])
        self.assertIn("never completed-checkpoint", observed["evidence_scope"])
        before_snapshot = {key: value for key, value in marker.items() if key != "snapshot_sha256"}
        with self.assertRaisesRegex(ValueError, "unconfirmed_snapshot_marker"):
            Qualification.uncompleted_snapshot_observation(before_snapshot, inventory)
        changed = {**inventory, "snapshot_sha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "unconfirmed_snapshot_inventory"):
            Qualification.uncompleted_snapshot_observation(marker, changed)
        with self.assertRaisesRegex(ValueError, "unconfirmed_snapshot_candidate"):
            Qualification.uncompleted_snapshot_observation(
                marker, {**inventory, "durable_ack_candidates": []}
            )

    def test_frozen_ack_barrier_fences_before_read_and_checks_complete_prefix(self):
        from lifecycle_runtime_verify import Qualification

        order = []
        positions = iter((5, 11))
        broker = dict(
            cluster_id="synthetic-cluster",
            topics=dict(ack=dict(name="synthetic.ack", id="synthetic-ack", partition=0)),
        )

        def status(_role):
            order.append("freeze_end")
            return dict(
                cluster_id="synthetic-cluster",
                topic="synthetic.ack",
                topic_id="synthetic-ack",
                partition=0,
                partitions=1,
                end=10,
            )

        def observe(limit):
            self.assertEqual(8, limit)
            order.append("checked_observe")
            return dict(ack_cursor=next(positions))

        runtime = SimpleNamespace(
            state=dict(broker=broker),
            stop=Mock(side_effect=lambda _worker: order.append("fence")),
            topic_status=Mock(side_effect=status),
            observe=Mock(side_effect=observe),
        )
        qualifier = Qualification(ROOT / ".cache", runtime, self.bundles, None, ROOT / "probe.jar")
        with patch("lifecycle_runtime_verify.time.sleep"):
            barrier = qualifier.fenced_ack_barrier(self.registration["worker_id"])
        self.assertEqual(["fence", "freeze_end", "checked_observe", "checked_observe"], order)
        self.assertEqual(10, barrier["end"])
        self.assertEqual(11, barrier["checked_cursor"])
        runtime.stop.assert_called_once_with(self.registration["worker_id"])
        runtime.topic_status.return_value = None
        runtime.topic_status.side_effect = lambda _role: dict(
            cluster_id="foreign-cluster", topic="synthetic.ack", topic_id="synthetic-ack", end=10
        )
        with self.assertRaisesRegex(ValueError, "ack_barrier_identity"):
            qualifier.ack_barrier()

    def test_open_group_requires_exact_five_members_run_and_initial_selection(self):
        from lifecycle_runtime_verify import Qualification

        case = Qualification.extra("audit-whoami", 205)
        publication = dict(revision=7, command_sha256="7" * 64)
        context = case["admissions"][0]["context"]
        key = dict(
            run_id=case["run_id"],
            source=context["source"],
            host_id=context["host_binding"]["host_id"],
            generation=context["source_generation"]["id"],
            audit_timestamp="1767225600.001",
            audit_serial="7",
        )
        members = [
            dict(
                record_id=row["raw"]["record_id"],
                evidence_sha256=row["raw"]["evidence"]["sha256"],
                raw_sha256=digest(row["raw"]),
                context_sha256=digest(row["context"]),
            )
            for row in case["admissions"][:-1]
        ]
        group = dict(key=key, members=members, opened=1000, deadline=31000)
        inventory: dict[str, Any] = dict(selection=publication, machine=dict(groups=[group]))
        self.assertEqual(group, Qualification.exact_open_group(inventory, case, publication))
        partial = dict(
            selection=publication, machine=dict(groups=[{**group, "members": members[:1]}])
        )
        self.assertIsNone(Qualification.exact_open_group(partial, case, publication))
        foreign = copy.deepcopy(inventory)
        foreign["machine"]["groups"][0]["key"]["run_id"] = "715b0000-0000-4000-8000-000000000299"
        self.assertIsNone(Qualification.exact_open_group(foreign, case, publication))
        corrupt = copy.deepcopy(inventory)
        corrupt["machine"]["groups"][0]["members"][0]["context_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "group_member_integrity"):
            Qualification.exact_open_group(corrupt, case, publication)
        self.assertIsNone(
            Qualification.exact_open_group(
                {**inventory, "selection": dict(revision=8, command_sha256="8" * 64)},
                case,
                publication,
            )
        )
        qualifier: Any = Qualification.__new__(Qualification)
        qualifier.runtime = SimpleNamespace(
            checkpoints=Mock(
                return_value=dict(latest=dict(completed=dict(id=9, status="COMPLETED")))
            ),
            worker_inventory=Mock(return_value=dict(inventory=inventory)),
        )
        qualifier.fail_on_failed_job = Mock()
        qualifier.private_evidence = Mock(return_value="a" * 64)
        qualifier.checkpoint_evidence = []
        # An older, genuinely completed snapshot is pending, not evidence of the new selection.
        newer = dict(revision=8, command_sha256="8" * 64)
        self.assertIsNone(qualifier.completed_open_group("worker", case, newer))
        qualifier.private_evidence.assert_not_called()
        inventory["selection"] = newer
        inventory["snapshot_sha256"] = "b" * 64
        proof = qualifier.completed_open_group("worker", case, newer)
        self.assertEqual(group, proof["group"])
        qualifier.runtime.worker_inventory.return_value = dict(inventory=corrupt)
        corrupt["selection"] = newer
        with self.assertRaisesRegex(ValueError, "group_member_integrity"):
            qualifier.completed_open_group("worker", case, newer)

    def test_group_closure_oracle_rejects_eoe_under_old_policy_and_wrong_closure(self):
        from lifecycle_runtime_verify import Qualification

        case = Qualification.extra("audit-whoami", 205)
        registration = {**self.registration, "worker_id": case["worker_id"]}
        before = dict(revision=7, command_sha256="7" * 64)
        after = dict(revision=8, command_sha256="8" * 64)
        receipts = [
            {**self.receipt, "offset": index, "value_sha256": sha(encoded(row))}
            for index, row in enumerate(case["admissions"])
        ]
        oracle = Oracle(self.bundles)
        oracle.add(
            case,
            "A",
            after,
            registration,
            receipts,
            self.binding,
            [("B", before, registration)] * 5 + [("A", after, registration)],
        )

        def wrapped(kind, body, publication=after):
            value = self.envelope(kind, body)
            value.update(worker_id=case["worker_id"], **publication)
            value["output_id"] = output_id(value)
            value["semantic_sha256"] = semantic_output(value)
            return self.wire(value)

        receipt = dict(
            version="1.0.0",
            id=transport_id(self.binding, receipts[-1], "receipt"),
            input=receipts[-1],
            kind="input_receipt",
            action="record",
            record_id=case["admissions"][-1]["raw"]["record_id"],
        )
        # Even a completely self-consistent old-policy EOE envelope cannot pass.
        with self.assertRaisesRegex(ValueError, "actual_command"):
            oracle.check([wrapped("receipt", receipt, before)])
        self.assertFalse(oracle.check([wrapped("receipt", receipt)]))
        manifest = copy.deepcopy(next(iter(oracle.expected_bodies.values())))
        self.assertEqual("source_boundary", manifest["closure"])
        self.assertEqual(6, len(manifest["members"]))
        self.assertTrue(manifest["eligible"])
        manifest["closure"] = "timeout"
        with self.assertRaisesRegex(ValueError, "manifest_membership"):
            oracle.check([wrapped("manifest", manifest)])

    def test_partial_marker_must_belong_to_current_atomic_case_not_old_outbox(self):
        from lifecycle_runtime_verify import Qualification

        case = Qualification.extra("security-alice", 206)
        receipt = {**self.receipt, "offset": 206}
        documents: dict[str, Any] = dict(
            receipt=dict(input=receipt, record_id=case["admissions"][0]["raw"]["record_id"]),
            tagged=dict(
                event=dict(
                    detectbridge=dict(run_id=case["run_id"]),
                    event=dict(id=case["expected"]["event_id"]),
                )
            ),
            detection=dict(run_id=case["run_id"], event_id=case["expected"]["event_id"]),
        )
        for kind, body in documents.items():
            envelope = dict(kind=kind, document=body)
            Qualification.require_atomic_case_output(envelope, case, [receipt])
            prior = copy.deepcopy(envelope)
            if kind == "receipt":
                prior["document"]["input"]["offset"] -= 1
            elif kind == "tagged":
                prior["document"]["event"]["detectbridge"]["run_id"] = "prior-run"
            else:
                prior["document"]["run_id"] = "prior-run"
            with self.assertRaisesRegex(ValueError, "partial_marker_atomic_case"):
                Qualification.require_atomic_case_output(prior, case, [receipt])

    def test_focused_dispatch_uses_fresh_setup_without_full_core(self):
        # Dispatch-only unit expectations; these mocks establish no runtime coverage.
        from lifecycle_runtime_verify import SCENARIO_GROUPS, Qualification

        for group, method in (
            ("partial-recovery", "partial_recovery"),
            ("checkpoint-timeout", "checkpoint_timeout"),
            ("invalid-messages", "invalid_messages"),
            ("hostile-ast", "hostile_ast"),
        ):
            qualifier: Any = Qualification.__new__(Qualification)
            qualifier.coverage = {}
            qualifier.setup_workers = Mock()
            qualifier.core = Mock(side_effect=AssertionError("full core must not run"))
            for name in (
                "mixed_workers",
                "production_faults",
                "pressure",
                "open_group",
                "partial_recovery",
                "checkpoint_timeout",
                "invalid_messages",
                "hostile_ast",
                "retained",
            ):
                setattr(qualifier, name, Mock())
            selected = getattr(qualifier, method)
            # Successful return without recorded proof must never qualify even a focused group.
            with self.assertRaisesRegex(ValueError, "required_scenarios_unqualified"):
                qualifier.run(group)
            qualifier.setup_workers.assert_called_once_with()
            selected.assert_called_once_with()
            self.assertLess(len(SCENARIO_GROUPS[group]), len(SCENARIO_GROUPS["all"]))

    def test_focused_mixed_requires_prior_actual_a_case_before_existing_schedule(self):
        from lifecycle_runtime_verify import Qualification

        qualifier: Any = Qualification.__new__(Qualification)
        qualifier.coverage = {}
        order: list[Any] = []
        qualifier.setup_workers = Mock(side_effect=lambda: order.append("setup_A"))
        qualifier.add_case = Mock(side_effect=lambda case, bundle: order.append((case, bundle)))
        qualifier.collect = Mock(side_effect=lambda: order.append("collect_prior_A"))
        for name in (
            "production_faults",
            "pressure",
            "open_group",
            "partial_recovery",
            "checkpoint_timeout",
            "invalid_messages",
            "hostile_ast",
            "retained",
        ):
            setattr(qualifier, name, Mock())
        qualifier.mixed_workers = Mock(side_effect=lambda: order.append("mixed_schedule"))
        with self.assertRaisesRegex(ValueError, "required_scenarios_unqualified"):
            qualifier.run("mixed-workers")
        self.assertEqual("setup_A", order[0])
        prior, bundle = order[1]
        self.assertEqual("A", bundle)
        self.assertEqual("security-alice", prior["id"])
        self.assertEqual("71500000-0000-4000-8000-000000000021", prior["worker_id"])
        self.assertTrue(prior["run_id"].endswith("000000000210"))
        self.assertEqual(["collect_prior_A", "mixed_schedule"], order[2:])

    def test_default_dispatch_retains_every_real_group_and_full_required_check(self):
        from lifecycle_runtime_verify import Qualification

        qualifier: Any = Qualification.__new__(Qualification)
        qualifier.coverage = {}
        order = []
        expected = [
            "core",
            "production_faults",
            "pressure",
            "open_group",
            "partial_recovery",
            "checkpoint_timeout",
            "invalid_messages",
            "retained",
            "hostile_ast",
        ]
        for name in expected:
            setattr(qualifier, name, Mock(side_effect=lambda *_, name=name: order.append(name)))
        # No runtime evidence was produced by dispatch stubs, so even default must fail closed.
        with self.assertRaisesRegex(ValueError, "required_scenarios_unqualified"):
            qualifier.run()
        self.assertEqual(expected, order)

    def test_focused_report_cannot_become_full_gate_even_with_all_names(self):
        from lifecycle_runtime_verify import REQUIRED, SCENARIO_GROUPS, scenario_outcome

        self.assertEqual(tuple(REQUIRED), SCENARIO_GROUPS["all"])
        # Pure report-classification inputs, not claims of actual execution.
        all_names = dict.fromkeys(REQUIRED)
        self.assertEqual("passed", scenario_outcome("all", all_names)["status"])
        self.assertTrue(scenario_outcome("all", all_names)["full_gate"])
        focused = scenario_outcome("partial-recovery", {"partial_ack_recovery": {}})
        self.assertEqual("partial_passed", focused["status"])
        self.assertFalse(focused["full_gate"])
        self.assertEqual(13, len(focused["unqualified_required_scenarios"]))
        self.assertFalse(scenario_outcome("partial-recovery", all_names)["full_gate"])
        with self.assertRaisesRegex(ValueError, "selected_scenarios_unqualified"):
            scenario_outcome("all", {"partial_ack_recovery": {}})

    def test_required_activation_job_rejects_focused_group_before_setup(self):
        import io

        from lifecycle_runtime_verify import main

        with (
            patch.dict("os.environ", {"DETECTBRIDGE_ACTIVATION_REQUIRED": "1"}),
            patch("sys.stderr", new_callable=io.StringIO) as error,
            self.assertRaises(SystemExit) as raised,
        ):
            main(["--scenario-group", "partial-recovery"])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("must execute --scenario-group all", error.getvalue())

    def test_collect_failed_job_retains_originals_before_reading_outputs(self):
        from lifecycle_runtime_verify import Qualification

        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            root = Path(folder)
            public = root / "reports"
            public.mkdir()
            worker = self.registration["worker_id"]
            job = "a" * 32
            detail = dict(jid=job, state="FAILED")
            exceptions = {
                "root-exception": "java.lang.IllegalArgumentException: lifecycle_private_mode"
            }
            runtime = SimpleNamespace(
                root=root / "deployment",
                state=dict(jobs={worker: dict(job_id=job)}),
                rest=Mock(
                    side_effect=lambda _worker, path: (
                        exceptions if path.endswith("/exceptions") else detail
                    )
                ),
                outputs=Mock(
                    side_effect=AssertionError("failed job must be diagnosed before source polling")
                ),
            )
            qualifier = Qualification(public, runtime, self.bundles, None, root / "probe.jar")
            with (
                patch(
                    "lifecycle_runtime_verify.time.sleep",
                    side_effect=AssertionError("must not exhaust source-accounting deadline"),
                ),
                self.assertRaisesRegex(
                    ValueError, "lifecycle_qualification_unexpected_job_failure"
                ),
            ):
                qualifier.collect()
            runtime.outputs.assert_not_called()
            proof = qualifier.unexpected_job_failures[0]
            self.assertEqual(digest(detail), proof["job_response_sha256"])
            self.assertEqual(digest(exceptions), proof["exceptions_sha256"])
            self.assertEqual(2, len(list((root / "qualification-private-evidence").glob("*.json"))))

    def test_mixed_selection_requires_exact_command_and_current_incarnation(self):
        from lifecycle_runtime_verify import Qualification

        worker = self.registration["worker_id"]
        selected = dict(revision=2, command_sha256="2" * 64, origin_incarnation="old")
        proof = dict(checkpoint=dict(id=7, status="COMPLETED"), inventory=dict(selection=selected))
        runtime = SimpleNamespace(
            checkpoints=Mock(return_value=dict(latest=dict(completed=proof["checkpoint"]))),
            worker_inventory=Mock(return_value=proof),
        )
        qualifier: Any = Qualification(
            ROOT / ".cache", runtime, self.bundles, None, ROOT / "probe.jar"
        )
        qualifier.registrations = [self.registration]
        qualifier.fail_on_failed_job = Mock()
        desired = dict(revision=2, command_sha256="2" * 64)
        self.assertIsNone(qualifier.completed_selection(worker, desired))
        selected["origin_incarnation"] = self.registration["incarnation"]
        selected["command_sha256"] = "1" * 64
        self.assertIsNone(qualifier.completed_selection(worker, desired))
        selected["command_sha256"] = desired["command_sha256"]
        self.assertIs(proof, qualifier.completed_selection(worker, desired))
        runtime.checkpoints.return_value = dict(latest=dict(completed=dict(id=7, status="FAILED")))
        runtime.worker_inventory.reset_mock()
        self.assertIsNone(qualifier.completed_selection(worker, desired))
        runtime.worker_inventory.assert_not_called()

    def test_mixed_pause_checks_actual_owned_state_and_shared_budget(self):
        from lifecycle_runtime_verify import Qualification

        worker = self.registration["worker_id"]
        managers: list[dict[str, Any]] = [
            dict(
                Id=role,
                Config=dict(Labels={"com.docker.compose.service": role}),
                State=dict(Running=True, Paused=role == "taskmanager"),
            )
            for role in ("jobmanager", "taskmanager")
        ]
        runtime = SimpleNamespace(
            state=dict(workers={worker: self.registration}),
            _containers=Mock(return_value=managers),
        )
        qualifier: Any = Qualification(
            ROOT / ".cache", runtime, self.bundles, None, ROOT / "probe.jar"
        )
        qualifier.registrations = [self.registration]
        qualifier.private_evidence = Mock(return_value="a" * 64)
        self.assertTrue(qualifier.paused_worker_proof(worker)["paused"])
        managers[1]["State"]["Paused"] = False
        with self.assertRaisesRegex(ValueError, "mixed_worker_not_paused"):
            qualifier.paused_worker_proof(worker)
        with patch("lifecycle_runtime_verify.time.monotonic", return_value=39.5):
            self.assertEqual(0.5, qualifier.mixed_pause_remaining(0))
        with patch("lifecycle_runtime_verify.time.monotonic", return_value=40):
            with self.assertRaisesRegex(ValueError, "mixed_pause_budget"):
                qualifier.mixed_pause_remaining(0)

    def test_mixed_failure_resumes_worker_without_recording_pass(self):
        from lifecycle_runtime_verify import WORKERS, Qualification

        registration = dict(worker_id=WORKERS[1], incarnation="current")
        selected = dict(revision=1, command_sha256="1" * 64, origin_incarnation="current")
        runtime = SimpleNamespace(fault=Mock())
        qualifier: Any = Qualification(
            ROOT / ".cache", runtime, self.bundles, None, ROOT / "probe.jar"
        )
        qualifier.current = dict(revision=1, command_sha256="1" * 64)
        qualifier.registrations = [registration]
        qualifier.completed = Mock(return_value=dict(inventory=dict(selection=selected)))
        qualifier.paused_worker_proof = Mock(return_value={})
        qualifier.publish = Mock()
        qualifier.wait = Mock(side_effect=ValueError("missing_completed_proof"))
        qualifier.record = Mock()
        with self.assertRaisesRegex(ValueError, "missing_completed_proof"):
            qualifier.mixed_workers()
        self.assertEqual(
            [("worker_pause", WORKERS[1]), ("worker_resume", WORKERS[1])],
            [call.args for call in runtime.fault.call_args_list],
        )
        qualifier.record.assert_not_called()
        self.assertTrue(qualifier.mixed_pause_observations[0]["resumed"])

    def test_failure_classifier_exposes_only_pinned_category_and_hashes(self):
        from lifecycle_runtime_verify import classify_unexpected_failure

        message = (
            "java.util.concurrent.TimeoutException: "
            "Heartbeat of TaskManager with id 172.18.0.3:34567-abcdef timed out."
        )
        document = {"root-exception": message}
        result = classify_unexpected_failure(document)
        self.assertEqual("flink_taskmanager_heartbeat_timeout", result["category"])
        self.assertEqual(digest(document), result["document_sha256"])
        self.assertEqual([sha(message.encode())], result["matched_message_sha256"])
        self.assertNotIn("172.18.0.3", encoded(result).decode())
        for changed in (
            message.replace("TimeoutException", "IllegalArgumentException"),
            message.replace("34567", "65536"),
            message.replace("abcdef", "ABCDEF"),
            message.replace("abcdef", "abcdef(private-secret)"),
            "unknown failure private-secret",
        ):
            with self.subTest(changed=changed):
                classified = classify_unexpected_failure({"root-exception": changed})
                self.assertEqual("unclassified", classified["category"])
                self.assertNotIn("private-secret", encoded(classified).decode())
        multiple = dict(
            exception=message,
            history=[dict(stacktrace=message.replace("34567", "12345"))],
        )
        self.assertEqual(
            "ambiguous_taskmanager_heartbeat_messages",
            classify_unexpected_failure(multiple)["category"],
        )

    def test_source_case_uses_one_qualification_batch_with_unchanged_input(self):
        from lifecycle_runtime_verify import Qualification

        qualifier: Any = Qualification.__new__(Qualification)
        qualifier.current = self.publication
        qualifier.registration = Mock(return_value=self.registration)
        qualifier.runtime = SimpleNamespace(
            admit_qualification_batch=Mock(return_value=[self.receipt])
        )
        qualifier.oracle = Oracle(self.bundles)
        original = copy.deepcopy(self.case)
        with patch(
            "lifecycle_runtime_verify.expected_bindings", return_value=("a" * 64, self.binding)
        ):
            result = qualifier.add_case(self.case, "A")
        self.assertEqual([self.receipt], result)
        qualifier.runtime.admit_qualification_batch.assert_called_once_with(
            self.case["worker_id"], original["admissions"]
        )
        self.assertEqual(original, self.case)
        self.assertEqual(1, len(qualifier.oracle.receipts))

    def test_batch_reporting_distinguishes_requested_and_verified_admission_prefix(self):
        from lifecycle_runtime_verify import Qualification

        operation = "715b0000-0000-4000-8000-000000000210"
        qualifier: Any = Qualification.__new__(Qualification)
        qualifier.runtime = SimpleNamespace(
            state=dict(
                qualification_batches={
                    operation: dict(
                        status="failed",
                        count=6,
                        admitted=["a" * 64, "b" * 64],
                        worker_id=self.registration["worker_id"],
                        incarnation=self.registration["incarnation"],
                        request_sha256="c" * 64,
                        command_sha256="d" * 64,
                        unknown_private_value="must-not-echo",
                    )
                }
            )
        )
        summary = qualifier.batch_state_summary()
        self.assertEqual(1, summary["count"])
        self.assertEqual("failed", summary["batches"][0]["status"])
        self.assertEqual(6, summary["batches"][0]["requested_record_count"])
        self.assertEqual(2, summary["batches"][0]["admitted_index_count"])
        self.assertNotIn("must-not-echo", encoded(summary).decode())

    def test_unexpected_partial_timeout_output_is_retained_without_changing_oracle(self):
        from lifecycle_runtime_verify import Qualification

        case = Qualification.extra("audit-whoami", 205)
        event = document(
            ROOT
            / "packages/linux-adapters/contracts/linux-audit-execution-p12a.contract-example.event.json"
        )
        event["event"]["id"] = identity(
            [
                case["admissions"][0]["raw"]["source"]["namespace"],
                case["admissions"][0]["raw"]["source"]["instance"],
                sorted(row["raw"]["record_id"] for row in case["admissions"][:2]),
            ]
        )
        metadata = event["detectbridge"]
        metadata["run_id"] = case["run_id"]
        metadata["assembly"]["closure"] = "timeout"
        metadata["evidence"] = case["admissions"][:2]
        metadata["extensions"] = {"linux.context": dict(findings=["cwd_missing"])}
        _, body = self.bodies()[0]
        body["event"] = event
        record = self.wire(self.envelope("tagged", body))
        original_expected = copy.deepcopy(self.oracle.events)
        with tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve()) as folder:
            qualifier: Any = Qualification.__new__(Qualification)
            qualifier.runtime = SimpleNamespace(root=Path(folder) / "deployment")
            qualifier.oracle = self.oracle
            qualifier.oracle_failure_observations = []
            with self.assertRaisesRegex(ValueError, "unexpected_event"):
                qualifier.check_output_records([record])
            observation = qualifier.oracle_failure_observations[0]
            summary = observation["actual_output_summary"][0]
            self.assertEqual("timeout", summary["closure"])
            self.assertEqual(2, summary["member_count"])
            self.assertEqual(["cwd_missing"], summary["findings"])
            self.assertEqual(event["event"]["id"], summary["event_id"])
            self.assertEqual(case["run_id"], summary["run_id"])
            retained = list(
                (Path(folder) / "qualification-private-evidence").glob("output-*/*.json")
            )
            self.assertEqual(1, len(retained))
            self.assertEqual(encoded(record), retained[0].read_bytes())
            self.assertEqual(0o600, retained[0].stat().st_mode & 0o777)
        self.assertEqual(original_expected.keys(), self.oracle.events.keys())

    def test_output_failure_summary_never_echoes_unknown_values_or_field_names(self):
        from lifecycle_runtime_verify import Qualification

        secret = "never-export-this-private-value"
        record = dict(
            wire_sha256=secret,
            output=dict(
                kind=secret,
                document_sha256=secret,
                output_id=secret,
                document=dict(
                    run_id=secret,
                    event_id=secret,
                    closure=secret,
                    findings=["cwd_missing", secret],
                    members=[{}, {}],
                    **{secret: secret},
                ),
            ),
        )
        summary = Qualification.output_failure_summary([record])[0]
        self.assertNotIn(secret, encoded(summary).decode())
        self.assertEqual(2, summary["member_count"])
        self.assertEqual(["cwd_missing"], summary["findings"])
        self.assertEqual([digest(secret)], summary["unknown_finding_sha256"])
        self.assertEqual(digest(secret), summary["run_id_value_sha256"])
        malformed = dict(output=dict(kind=secret, document=dict(event=secret, key=secret)))
        self.assertNotIn(
            secret, encoded(Qualification.output_failure_summary([malformed])).decode()
        )

    def test_missing_expected_source_outputs_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "incomplete_outputs"):
            self.oracle.check([], complete=True)


if __name__ == "__main__":
    unittest.main()
