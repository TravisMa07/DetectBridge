"""Independent P15a blackbox gates; literal outcomes precede implementation."""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle
from detection_compile import compile_rules
from lifecycle import Store
from lifecycle_validation import (
    PIN,
    bundle,
    encoded,
    java_compact,
    require,
    run_suite,
    verify_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts/lifecycle/v1/fixtures"
JAR = ROOT / "packages/integration-job/build/libs/integration-job.jar"
AUTHORITY = "71500000-0000-4000-8000-000000000010"
DEPLOYMENT = "71500000-0000-4000-8000-000000000011"
FREEZE = "2ff0e4f978363466f63714c550a0d296a4b32a00"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def document(path):
    return json.loads(path.read_bytes())


class LifecycleTests(unittest.TestCase):
    plan: ClassVar[dict[str, Any]]
    plan_bytes: ClassVar[bytes]
    manifest: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls):
        if not JAR.is_file() or digest(JAR.read_bytes()) != PIN:
            if os.environ.get("DETECTBRIDGE_LIFECYCLE_REQUIRED") == "1":
                raise AssertionError("required exact retained lifecycle evaluator unavailable")
            raise unittest.SkipTest(
                "exact retained lifecycle evaluator unavailable; no runtime qualification"
            )
        rule = FIXTURES / "rule.yml"
        revision = digest(rule.read_bytes())
        provenance = dict(
            version="1.0.0",
            rule_id="71500000-0000-4000-8000-000000000001",
            revision=revision,
            kind="synthetic",
            repository="https://github.com/TravisMa07/DetectBridge",
            repository_revision=FREEZE,
            path="contracts/lifecycle/v1/fixtures/rule.yml",
            original_sha256=revision,
            authors=["DetectBridge contributors"],
            license="Apache-2.0",
            notices=[],
            modifications=[],
        )
        profiles = ROOT / "packages/windows-adapters/profiles"
        cls.plan = compile_rules(
            [rule],
            [document(profiles / "security.source.json")],
            mappings=[document(profiles / "security.mapping.json")],
            provenance=[provenance],
        )
        cls.plan_bytes = encoded(cls.plan)
        cls.manifest = bundle(cls.plan_bytes)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=(ROOT / ".cache").resolve())
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.candidate = self.folder / "candidate"
        self.candidate.mkdir()
        (self.candidate / "manifest.json").write_bytes(encoded(self.manifest))
        (self.candidate / "plan.json").write_bytes(self.plan_bytes)
        self.suite = self.folder / "cases.json"
        self.suite.write_bytes((FIXTURES / "cases.json").read_bytes())
        self.store_root = self.folder / "store"
        Store.initialize(self.store_root, AUTHORITY, JAR, self.manifest["profile"])
        self.store = Store(self.store_root, AUTHORITY, JAR)

    def request(self, operation, arguments=None, request_id=None):
        return dict(
            version="1.0.0",
            authority_id=AUTHORITY,
            request_id=request_id or str(uuid.uuid4()),
            operation=operation,
            bundle_sha256=self.manifest["bundle_sha256"],
            arguments={} if arguments is None else arguments,
        )

    def imported(self):
        request = self.request(
            "import",
            dict(
                manifest_sha256=digest((self.candidate / "manifest.json").read_bytes()),
                plan_sha256=digest(self.plan_bytes),
            ),
        )
        result = self.store.execute(request, bundle_directory=self.candidate)
        return request, result

    def validated(self):
        self.imported()
        return self.store.execute(self.request("validate"))

    def run_tested(self):
        self.validated()
        return self.store.execute(
            self.request("test", dict(suite_sha256=digest(self.suite.read_bytes()))),
            suite_path=self.suite,
        )

    def staged(self):
        report = self.run_tested()
        self.assertTrue(
            report["report"]["passed"], "actual pinned evaluator must pass before stage"
        )
        return self.store.execute(self.request("stage"))

    def preparation(self, expected=0, previous=None, action="activate"):
        request = self.request("prepare")
        request["arguments"] = dict(
            expected_preparation_revision=expected,
            command=dict(
                version="1.0.0",
                authority_id=AUTHORITY,
                deployment_id=DEPLOYMENT,
                request_id=request["request_id"],
                revision=expected + 1,
                previous_sha256=previous,
                action=action,
                bundle_sha256=self.manifest["bundle_sha256"],
                compatibility_sha256=self.manifest["compatibility_sha256"],
                participants=[
                    dict(
                        worker_id="71500000-0000-4000-8000-000000000020",
                        incarnation="71500000-0000-4000-8000-000000000021",
                    )
                ],
            ),
        )
        return request

    def test_stage_rejects_imported_but_untested_candidate(self):
        self.imported()
        with self.assertRaises(ValueError):
            self.store.execute(self.request("stage"))
        self.assertFalse(self.store.status()["bundles"][self.manifest["bundle_sha256"]]["staged"])

    def test_test_requires_validation_and_prepare_requires_stage(self):
        self.imported()
        with self.assertRaises(ValueError):
            self.store.execute(
                self.request("test", dict(suite_sha256=digest(self.suite.read_bytes()))),
                suite_path=self.suite,
            )
        with self.assertRaises(ValueError):
            self.store.execute(self.preparation())
        self.assertEqual(0, self.store.status()["preparation_revision"])

    def test_exact_import_retry_and_request_conflict(self):
        request, original = self.imported()
        self.assertEqual(original, self.store.execute(request, bundle_directory=self.candidate))
        changed = self.request("validate", request_id=request["request_id"])
        with self.assertRaises(ValueError):
            self.store.execute(changed)
        self.assertEqual(1, self.store.status()["records"])

    def test_changed_plan_never_imports_under_frozen_identity(self):
        (self.candidate / "plan.json").write_bytes(self.plan_bytes + b" ")
        with self.assertRaises(ValueError):
            self.imported()
        self.assertEqual({}, self.store.status()["bundles"])

    def test_extra_candidate_file_and_symlink_plan_rejected(self):
        (self.candidate / "extra.txt").write_text("unexpected")
        with self.assertRaises(ValueError):
            verify_bundle(self.candidate)
        (self.candidate / "extra.txt").unlink()
        target = self.folder / "external-plan.json"
        target.write_bytes(self.plan_bytes)
        (self.candidate / "plan.json").unlink()
        (self.candidate / "plan.json").symlink_to(target)
        with self.assertRaises(ValueError):
            verify_bundle(self.candidate)

    def test_wrong_authority_root_mode_and_symlink_root_rejected(self):
        with self.assertRaises(ValueError):
            Store(self.store_root, str(uuid.uuid4()), JAR)
        os.chmod(self.store_root, 0o755)
        with self.assertRaises(ValueError):
            Store(self.store_root, AUTHORITY, JAR)
        os.chmod(self.store_root, 0o700)
        alias = self.folder / "alias"
        alias.symlink_to(self.store_root, target_is_directory=True)
        with self.assertRaises(ValueError):
            Store(alias, AUTHORITY, JAR)

    def test_strict_request_types_and_unknown_fields(self):
        self.imported()
        for changed in (
            {**self.request("validate"), "unknown": True},
            self.request("validate", dict(passed=True)),
        ):
            with self.subTest(request=changed), self.assertRaises(ValueError):
                self.store.execute(changed)
        prepared = self.preparation()
        prepared["arguments"]["expected_preparation_revision"] = False
        with self.assertRaises(ValueError):
            require("request", prepared)
        prepared = self.preparation()
        prepared["arguments"]["command"]["revision"] = 2**63
        with self.assertRaises(ValueError):
            require("request", prepared)

    def test_control_membership_unique_worker_ids_and_nonempty(self):
        self.imported()
        for participants in (
            [],
            [
                dict(worker_id=AUTHORITY, incarnation=str(uuid.uuid4())),
                dict(worker_id=AUTHORITY, incarnation=str(uuid.uuid4())),
            ],
            [dict(worker_id=str(uuid.uuid4()), incarnation=str(uuid.uuid4())) for _ in range(17)],
        ):
            request = self.preparation()
            request["arguments"]["command"]["participants"] = participants
            with self.subTest(count=len(participants)), self.assertRaises(ValueError):
                self.store.execute(request)

    def test_corrupt_head_and_journal_block_reopen(self):
        self.imported()
        head = self.store_root / "head.json"
        original = head.read_bytes()
        head.write_bytes(b"{}\n")
        with self.assertRaises(ValueError):
            Store(self.store_root, AUTHORITY, JAR).status()
        head.write_bytes(original)
        records = list((self.store_root / "journal").iterdir())
        regular = [path for path in records if path.is_file() and path.suffix != ".sha256"]
        self.assertTrue(regular)
        regular[0].write_bytes(b"{}\n")
        with self.assertRaises(ValueError):
            Store(self.store_root, AUTHORITY, JAR).status()

    def test_actual_process_exit_leaves_one_recoverable_validation_successor(self):
        self.imported()
        request = self.request("validate")
        request_path = self.folder / "child-request.json"
        request_path.write_bytes(encoded(request))
        program = """
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import lifecycle
store = lifecycle.Store(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
def terminate(phase):
    if phase == "after_record_publication":
        os._exit(86)
lifecycle.HOOK = terminate
store.execute(json.loads(Path(sys.argv[5]).read_bytes()))
raise SystemExit(99)
"""
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                program,
                str(ROOT / "tools"),
                str(self.store_root),
                AUTHORITY,
                str(JAR),
                str(request_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        self.assertEqual(86, child.returncode, "observe actual abrupt exit, not caught exception")
        self.assertEqual(1, document(self.store_root / "head.json")["value"]["sequence"])
        self.assertEqual(2, len(list((self.store_root / "journal").iterdir())))
        recovered = Store(self.store_root, AUTHORITY, JAR)
        self.assertEqual(2, recovered.status()["records"])
        first = recovered.execute(request)
        self.assertEqual("validated", first["state"])
        self.assertEqual(first, recovered.execute(request))
        self.assertEqual(2, recovered.status()["records"])

    def test_effective_store_capacity_boundary_preserves_prior_state(self):
        # Reduced effective limits exercise accounting; these are not 512-MiB capacity claims.
        self.imported()
        used = sum(path.stat().st_size for path in self.store_root.rglob("*") if path.is_file())
        limit = used + lifecycle.TEMP_BYTES + lifecycle.RECORD_BYTES * 2
        with patch("lifecycle.STORE_BYTES", limit - 1), self.assertRaises(ValueError):
            self.store.execute(self.request("validate"))
        self.assertEqual(1, self.store.status()["records"])
        with patch("lifecycle.STORE_BYTES", limit):
            result = self.store.execute(self.request("validate"))
        self.assertEqual("validated", result["state"])

    def test_effective_free_reserve_and_history_boundaries(self):
        self.imported()
        free = lifecycle.RESERVE_BYTES + lifecycle.TEMP_BYTES + lifecycle.RECORD_BYTES * 2
        with (
            patch("lifecycle.shutil.disk_usage", return_value=SimpleNamespace(free=free - 1)),
            self.assertRaises(ValueError),
        ):
            self.store.execute(self.request("validate"))
        self.assertEqual(1, self.store.status()["records"])
        with patch("lifecycle.RECORD_COUNT", 1), self.assertRaises(ValueError):
            self.store.execute(self.request("validate"))
        with (
            patch("lifecycle.RECORD_COUNT", 2),
            patch("lifecycle.shutil.disk_usage", return_value=SimpleNamespace(free=free)),
        ):
            self.assertEqual("validated", self.store.execute(self.request("validate"))["state"])
            with self.assertRaises(ValueError):
                self.store.execute(self.request("validate"))
        self.assertEqual(2, self.store.status()["records"])

    def test_input_and_evaluator_paths_must_be_disjoint_from_store(self):
        imported, _ = self.imported()
        imported["request_id"] = str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError, "overlapping_roots"):
            self.store.execute(imported, bundle_directory=self.folder)
        self.store.execute(self.request("validate"))
        internal_plan = self.store_root / "bundles" / self.manifest["bundle_sha256"] / "plan.json"
        with self.assertRaisesRegex(ValueError, "overlapping_roots"):
            Store(self.store_root, AUTHORITY, internal_plan)
        with self.assertRaisesRegex(ValueError, "overlapping_roots"):
            self.store.execute(
                self.request("test", dict(suite_sha256=digest(internal_plan.read_bytes()))),
                suite_path=internal_plan,
            )

    def test_self_rehashed_changed_ast_cannot_pass_compiler_validation(self):
        changed = copy.deepcopy(self.plan)
        changed["rules"][0]["expression"]["tokens"][0]["text"] = "B"
        del changed["bundle_sha256"]
        changed["bundle_sha256"] = digest(encoded(changed))
        plan_bytes = encoded(changed)
        manifest = bundle(plan_bytes)
        manifest_bytes = encoded(manifest)
        (self.candidate / "manifest.json").write_bytes(manifest_bytes)
        (self.candidate / "plan.json").write_bytes(plan_bytes)
        request = self.request(
            "import", dict(manifest_sha256=digest(manifest_bytes), plan_sha256=digest(plan_bytes))
        )
        request["bundle_sha256"] = manifest["bundle_sha256"]
        self.store.execute(request, bundle_directory=self.candidate)
        validate = self.request("validate")
        validate["bundle_sha256"] = manifest["bundle_sha256"]
        with self.assertRaisesRegex(ValueError, "plan_compilation_mismatch"):
            self.store.execute(validate)
        stage = self.request("stage")
        stage["bundle_sha256"] = manifest["bundle_sha256"]
        with self.assertRaises(ValueError):
            self.store.execute(stage)
        self.assertFalse(self.store.status()["bundles"][manifest["bundle_sha256"]]["validated"])

    def test_compiler_temporaries_for_validate_and_test_stay_in_reserved_store(self):
        self.imported()
        compile_plan = lifecycle.validation.validate_plan
        observed = []

        def observe(plan_bytes, temporary_root=None):
            self.assertIsNotNone(temporary_root)
            root = Path(temporary_root)
            self.assertIn(self.store_root / ".temporary", root.parents)
            self.assertTrue(root.is_dir())
            observed.append(root)
            return compile_plan(plan_bytes, temporary_root)

        with patch("lifecycle_validation.validate_plan", side_effect=observe):
            self.store.execute(self.request("validate"))
            result = self.store.execute(
                self.request("test", dict(suite_sha256=digest(self.suite.read_bytes()))),
                suite_path=self.suite,
            )
        self.assertTrue(result["report"]["passed"])
        self.assertEqual(2, len(observed))
        self.assertTrue(all(not path.exists() for path in observed))

    def test_recovery_forces_surviving_journal_before_publishing_advanced_head(self):
        request = self.request(
            "import",
            dict(
                manifest_sha256=digest((self.candidate / "manifest.json").read_bytes()),
                plan_sha256=digest(self.plan_bytes),
            ),
        )
        journal = self.store_root / "journal"
        successor = journal / "00000000000000000001.json"
        sync_directory = lifecycle.sync_directory

        def interrupt_parent_force(path):
            if Path(path) == journal and successor.exists():
                raise RuntimeError("independent_unsynced_journal_rename")
            sync_directory(path)

        # The real immutable rename survives; its directory force fails before head update.
        with (
            patch("lifecycle.sync_directory", side_effect=interrupt_parent_force),
            self.assertRaisesRegex(RuntimeError, "independent_unsynced_journal_rename"),
        ):
            self.store.execute(request, bundle_directory=self.candidate)
        self.assertTrue(successor.is_file())
        self.assertEqual(0, document(self.store_root / "head.json")["value"]["sequence"])
        forced: list[Path] = []
        publish_head = Store._head

        def observe_force(path):
            sync_directory(path)
            forced.append(Path(path))

        def observe_head(instance, sequence, record_hash):
            self.assertIn(
                journal,
                forced,
                "recovery must force surviving journal rename before advancing durable head",
            )
            return publish_head(instance, sequence, record_hash)

        with (
            patch("lifecycle.sync_directory", side_effect=observe_force),
            patch.object(Store, "_head", autospec=True, side_effect=observe_head),
        ):
            recovered = Store(self.store_root, AUTHORITY, JAR)
        self.assertEqual(1, recovered.status()["records"])
        recovered.execute(request, bundle_directory=self.candidate)
        self.assertEqual(1, recovered.status()["records"])

    def test_published_successor_recovers_once_after_crash(self):
        request = self.request(
            "import",
            dict(
                manifest_sha256=digest((self.candidate / "manifest.json").read_bytes()),
                plan_sha256=digest(self.plan_bytes),
            ),
        )

        def crash(phase):
            if phase == "after_record_publication":
                raise RuntimeError("independent_injected_crash")

        with patch("lifecycle.HOOK", side_effect=crash), self.assertRaises(RuntimeError):
            self.store.execute(request, bundle_directory=self.candidate)
        recovered = Store(self.store_root, AUTHORITY, JAR)
        self.assertEqual(1, recovered.status()["records"])
        original = recovered.execute(request, bundle_directory=self.candidate)
        self.assertEqual(original, recovered.execute(request, bundle_directory=self.candidate))
        self.assertEqual(1, recovered.status()["records"])

    def test_object_publication_is_not_imported_lifecycle_fact(self):
        request = self.request(
            "import",
            dict(
                manifest_sha256=digest((self.candidate / "manifest.json").read_bytes()),
                plan_sha256=digest(self.plan_bytes),
            ),
        )

        def crash(phase):
            if phase == "after_object_publication":
                raise RuntimeError("independent_injected_crash")

        with patch("lifecycle.HOOK", side_effect=crash), self.assertRaises(RuntimeError):
            self.store.execute(request, bundle_directory=self.candidate)
        recovered = Store(self.store_root, AUTHORITY, JAR)
        self.assertEqual({}, recovered.status()["bundles"])
        self.assertEqual(0, recovered.status()["records"])
        recovered.execute(request, bundle_directory=self.candidate)
        self.assertEqual(1, recovered.status()["records"])

    def test_runner_subprocess_boundaries_are_sanitized_component_cases(self):
        # These adversarial helper processes qualify runner mechanics, not Java semantics.
        popen = subprocess.Popen
        scenarios = (
            (
                "import sys;sys.stdout.write('not-json');sys.stderr.write('PRIVATE')",
                "invalid_output",
            ),
            ("import sys;sys.stdout.write('{}')", "invalid_output"),
            ("import sys;sys.exit(3)", "evaluator_failure"),
            ("import sys;sys.stdout.buffer.write(b'x'*(2*1024*1024+1))", "output_limit"),
            ("import time;time.sleep(2)", "timeout"),
        )
        for program, expected in scenarios:

            def helper(command, **kwargs):
                self.assertEqual(subprocess.DEVNULL, kwargs["stderr"])
                return popen([sys.executable, "-c", program], **kwargs)

            with (
                self.subTest(category=expected),
                patch("lifecycle_validation.subprocess.Popen", side_effect=helper),
                patch.dict("lifecycle_validation.LIMITS", test_timeout_seconds=0.3),
            ):
                observed, category = java_compact(
                    self.candidate / "plan.json", b"{}", JAR, self.folder
                )
            self.assertIsNone(observed)
            self.assertEqual(expected, category)

    def test_real_literal_suite_passes_and_changed_expectation_fails(self):
        report = run_suite(self.plan_bytes, self.suite, JAR, self.folder)
        self.assertTrue(report["passed"])
        self.assertEqual(digest(self.plan_bytes), report["plan_sha256"])
        self.assertEqual(digest(self.suite.read_bytes()), report["suite_sha256"])
        changed = document(self.suite)
        changed["cases"][0]["expected"]["matched"][0]["revision"] = "0" * 64
        self.suite.write_bytes(encoded(changed))
        self.assertFalse(run_suite(self.plan_bytes, self.suite, JAR, self.folder)["passed"])

    def test_real_validated_passing_candidate_can_stage(self):
        result = self.staged()
        self.assertEqual("staged", result["state"])
        candidate = self.store.status()["bundles"][self.manifest["bundle_sha256"]]
        self.assertTrue(candidate["validated"])
        self.assertTrue(candidate["tested"])
        self.assertTrue(candidate["staged"])

    def test_real_stage_prepare_retry_and_monotonic_rollback(self):
        self.staged()
        request = self.preparation()
        result = self.store.execute(request)
        self.assertEqual(1, result["preparation_revision"])
        self.assertEqual(result, self.store.execute(request))
        self.assertEqual(1, self.store.status()["preparation_revision"])
        next_request = self.preparation(1, result["command_sha256"], "rollback")
        rollback = self.store.execute(next_request)
        self.assertEqual(2, rollback["preparation_revision"])
        with self.assertRaises(ValueError):
            self.store.execute(self.preparation())
        with self.assertRaises(ValueError):
            self.store.execute(self.request("retire"))

    def test_real_distinct_candidate_proposals_a_to_b_to_a_retain_history(self):
        # Independent local modification: change literal User Alice to Bob, retaining
        # original Apache-2.0 YAML provenance and the exact original→modified hash chain.
        # Bob then matches and Alice does not by literal equality, not evaluator output.
        # This qualifies prepared proposals only; no worker activation is asserted.
        self.staged()
        retained_a = self.store_root / "bundles" / self.manifest["bundle_sha256"]
        original_a = {path.name: path.read_bytes() for path in retained_a.iterdir()}
        original_history = {
            path.name: path.read_bytes() for path in (self.store_root / "journal").iterdir()
        }
        yaml_a = (FIXTURES / "rule.yml").read_bytes()
        yaml_b = yaml_a.replace(b"User: Alice", b"User: Bob")
        self.assertNotEqual(yaml_a, yaml_b)
        revision_b = digest(yaml_b)
        rule_path = self.folder / "modified-rule.yml"
        rule_path.write_bytes(yaml_b)
        provenance_b = copy.deepcopy(self.plan["rules"][0]["provenance"])
        provenance_b["revision"] = revision_b
        provenance_b["modifications"].append(
            dict(
                input_sha256=digest(yaml_a),
                output_sha256=revision_b,
                description="Independent P15 proposal rollback test: User Alice changed to Bob",
            )
        )
        plan_b = compile_rules(
            [rule_path],
            self.plan["sources"],
            mappings=self.plan["mapping_profiles"],
            provenance=[provenance_b],
        )
        bytes_b = encoded(plan_b)
        manifest_b = bundle(bytes_b)
        self.assertNotEqual(self.manifest["bundle_sha256"], manifest_b["bundle_sha256"])
        self.assertNotEqual(self.plan["bundle_sha256"], plan_b["bundle_sha256"])
        self.assertEqual(self.manifest["compatibility_sha256"], manifest_b["compatibility_sha256"])
        candidate_b = self.folder / "candidate-b"
        candidate_b.mkdir()
        (candidate_b / "manifest.json").write_bytes(encoded(manifest_b))
        (candidate_b / "plan.json").write_bytes(bytes_b)
        suite_b = document(self.suite)
        for case in suite_b["cases"]:
            matches_b = case["event"]["user"]["name"] == "Bob"
            case["expected"] = dict(
                version="1.0.0",
                counts=dict(
                    matched=1 if matches_b else 0,
                    unmatched=0 if matches_b else 1,
                    inapplicable=0,
                    configuration_blocked=0,
                    quality_skipped=0,
                    evaluation_error=0,
                ),
                matched=[dict(id="71500000-0000-4000-8000-000000000001", revision=revision_b)]
                if matches_b
                else [],
                diagnostics=[],
            )
        suite_path_b = self.folder / "cases-b.json"
        suite_path_b.write_bytes(encoded(suite_b))

        def request_b(operation, arguments=None):
            request = self.request(operation, arguments)
            request["bundle_sha256"] = manifest_b["bundle_sha256"]
            return request

        self.store.execute(
            request_b(
                "import",
                dict(
                    manifest_sha256=digest((candidate_b / "manifest.json").read_bytes()),
                    plan_sha256=digest(bytes_b),
                ),
            ),
            bundle_directory=candidate_b,
        )
        self.store.execute(request_b("validate"))
        tested = self.store.execute(
            request_b("test", dict(suite_sha256=digest(suite_path_b.read_bytes()))),
            suite_path=suite_path_b,
        )
        self.assertTrue(tested["report"]["passed"])
        self.store.execute(request_b("stage"))
        first_a = self.store.execute(self.preparation())
        next_b = self.preparation(1, first_a["command_sha256"])
        next_b["bundle_sha256"] = manifest_b["bundle_sha256"]
        next_b["arguments"]["command"]["bundle_sha256"] = manifest_b["bundle_sha256"]
        second_b = self.store.execute(next_b)
        rollback_a = self.store.execute(self.preparation(2, second_b["command_sha256"], "rollback"))
        self.assertEqual(
            [1, 2, 3], [row["preparation_revision"] for row in (first_a, second_b, rollback_a)]
        )
        self.assertEqual(self.manifest["bundle_sha256"], rollback_a["command"]["bundle_sha256"])
        self.assertEqual(second_b["command_sha256"], rollback_a["command"]["previous_sha256"])
        self.assertEqual(
            original_a, {path.name: path.read_bytes() for path in retained_a.iterdir()}
        )
        for name, original in original_history.items():
            self.assertEqual(original, (self.store_root / "journal" / name).read_bytes())
        state = self.store.status()
        self.assertEqual(11, state["records"])
        self.assertTrue(state["bundles"][self.manifest["bundle_sha256"]]["prepared"])
        self.assertTrue(state["bundles"][manifest_b["bundle_sha256"]]["prepared"])

    def test_real_failed_retest_clears_readiness_preserves_preparation(self):
        self.staged()
        self.store.execute(self.preparation())
        changed = document(self.suite)
        changed["cases"][0]["event"]["user"]["name"] = "Bob"
        self.suite.write_bytes(encoded(changed))
        report = self.store.execute(
            self.request("test", dict(suite_sha256=digest(self.suite.read_bytes()))),
            suite_path=self.suite,
        )
        self.assertFalse(report["report"]["passed"])
        state = self.store.status()
        candidate = state["bundles"][self.manifest["bundle_sha256"]]
        self.assertFalse(candidate["tested"])
        self.assertFalse(candidate["staged"])
        self.assertEqual(1, state["preparation_revision"])
        with self.assertRaises(ValueError):
            self.store.execute(self.request("stage"))

    def test_real_competing_compare_and_swap_has_one_winner(self):
        self.staged()
        requests = [self.preparation(), self.preparation()]

        def apply(request):
            try:
                Store(self.store_root, AUTHORITY, JAR).execute(request)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(apply, requests))
        self.assertEqual([False, True], sorted(outcomes))
        self.assertEqual(1, self.store.status()["preparation_revision"])

    def test_retired_bundle_cannot_reimport_or_validate(self):
        request, _ = self.imported()
        self.store.execute(self.request("retire"))
        request["request_id"] = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            self.store.execute(request, bundle_directory=self.candidate)
        with self.assertRaises(ValueError):
            self.store.execute(self.request("validate"))

    def test_suite_requires_positive_negative_unique_ids_and_bounds(self):
        original = document(self.suite)
        boundary: dict[str, Any] = dict(version="1.0.0", cases=[])
        for index in range(64):
            case = copy.deepcopy(original["cases"][index % 2])
            case["id"] = "boundary-" + str(index)
            boundary["cases"].append(case)
        require("test-suite", boundary)  # Contract boundary, not 64-case runtime qualification.
        oversized_event = copy.deepcopy(original)
        oversized_event["cases"][0]["event"]["source_fields"]["budget_probe"] = "x" * (1024 * 1024)
        self.suite.write_bytes(encoded(oversized_event))
        with self.assertRaises(ValueError):
            run_suite(self.plan_bytes, self.suite, JAR, self.folder)
        self.suite.write_bytes(encoded(original) + b" " * (16 * 1024 * 1024))
        with self.assertRaises(ValueError):
            run_suite(self.plan_bytes, self.suite, JAR, self.folder)
        for changed in (
            dict(version="1.0.0", cases=original["cases"][:1]),
            dict(version="1.0.0", cases=original["cases"] * 33),
            dict(version="1.0.0", cases=[original["cases"][0]] * 2),
        ):
            self.suite.write_bytes(encoded(changed))
            with self.subTest(count=len(changed["cases"])), self.assertRaises(ValueError):
                run_suite(self.plan_bytes, self.suite, JAR, self.folder)
        forged = copy.deepcopy(original)
        forged["passed"] = True
        with self.assertRaises(ValueError):
            require("test-suite", forged)


if __name__ == "__main__":
    unittest.main()
