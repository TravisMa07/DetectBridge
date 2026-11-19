"""Fault injections preserve independent originals and target the intended verifier layer."""

import copy
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import archive_maintenance_faults as faults
import historical as history
from check_contracts import load_json

ROOT = Path(__file__).resolve().parents[2]


class FaultInjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.frozen = load_json(
            ROOT / "contracts/archive-maintenance/v1/fixtures/expectations.json"
        )
        self.segment = self.root / "segments/topic-0/0/0"
        self.segment.mkdir(parents=True)
        source = self.frozen["legacy"]["segments"][0]
        self.payload = self.segment / "records.ndjson.gz"
        self.payload.write_bytes(bytes.fromhex(source["gzip_hex"]))
        faults.write_metadata(self.segment / "segment.json", copy.deepcopy(source["metadata"]))

    def test_compensated_footer_fault_reaches_gzip_integrity_beyond_outer_checksum(self):
        original = copy.deepcopy(self.frozen)
        faults.mutate(self.root, "corrupt_segment_gzip_footer", self.frozen)
        metadata = load_json(self.segment / "segment.json")
        body = self.payload.read_bytes()
        self.assertEqual(metadata["payload"]["compressed_bytes"], len(body))
        self.assertEqual(metadata["payload"]["compressed_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(history.verified(self.segment / "segment.json"), metadata)
        with self.assertRaises(gzip.BadGzipFile):
            gzip.decompress(body)
        self.assertEqual(self.frozen, original)

    def test_truncation_preserves_expected_metadata_and_exposes_length_failure(self):
        before = (self.segment / "segment.json").read_bytes()
        original = self.payload.read_bytes()
        faults.mutate(self.root, "truncated_segment", self.frozen)
        self.assertEqual(self.payload.read_bytes(), original[:-1])
        self.assertEqual((self.segment / "segment.json").read_bytes(), before)

    def test_archive_snapshot_detects_empty_directory_append_and_file_changes(self):
        before = faults.hashes(self.root)
        added = self.root / "unexpected-empty-directory"
        added.mkdir()
        self.assertNotEqual(before, faults.hashes(self.root))
        added.rmdir()
        self.assertEqual(before, faults.hashes(self.root))
        self.payload.write_bytes(b"changed")
        self.assertNotEqual(before, faults.hashes(self.root))

    def test_missing_head_proof_rejects_an_unrelated_removed_or_changed_file(self):
        before = {"maintenance/holds/head.json": "original", "other.json": "unchanged"}
        faults.declared_removal(before, {"other.json": "unchanged"}, "maintenance/holds/head.json")
        for after in ({}, {"other.json": "changed"}, dict(before)):
            with self.subTest(after=after), self.assertRaises(AssertionError):
                faults.declared_removal(before, after, "maintenance/holds/head.json")

    def assert_runtime_pairs(self, pairs, outcomes):
        from archive_maintenance_verify import Runtime
        from stack import StackError

        runtime = Runtime.__new__(Runtime)
        runtime.folder = self.root
        runtime.control = self.root
        runtime.managed = "00000000-0000-4000-8000-000000000051"
        runtime.bundle = {"managed": "a" * 64, "image": "bound-test-image"}
        runtime.network = None
        for number, (category, failure_class, exit_code, accepted) in enumerate(outcomes):
            folder = self.root / str(number)
            folder.mkdir()

            def container(*args, **kwargs):
                detail = dict(status="blocked", category=category, failure_class=failure_class)
                record = dict(exit_code=exit_code, stdout=json.dumps(detail) + "\n", stderr="")
                (folder / "failure-unit.json").write_text(json.dumps(record))
                raise StackError("maintenance_helper_failed")

            owner = SimpleNamespace(folder=folder, container=container)
            with self.subTest(category=category, failure_class=failure_class, exit_code=exit_code):
                if accepted:
                    self.assertEqual(
                        runtime.invoke(
                            "inspect",
                            "/bound-archive",
                            owned_operation=owner,
                            catalog_lock=False,
                            expected="required_backend_failure",
                            expected_pairs=pairs,
                        )["status"],
                        "expected_failure",
                    )
                else:
                    with self.assertRaises(AssertionError):
                        runtime.invoke(
                            "inspect",
                            "/bound-archive",
                            owned_operation=owner,
                            catalog_lock=False,
                            expected="required_backend_failure",
                            expected_pairs=pairs,
                        )

    def test_runtime_requires_one_exact_missing_head_pair_and_exit_one(self):
        self.assert_runtime_pairs(
            faults.MISSING_HEAD_FAILURES,
            [
                ("managed_operation_failed", "java.nio.file.NoSuchFileException", 1, True),
                ("unsafe_or_oversized_file", "io.detectbridge.archive.Format$Failure", 1, True),
                ("managed_operation_failed", "java.lang.NullPointerException", 1, False),
                ("managed_operation_failed", "io.detectbridge.archive.Format$Failure", 1, False),
                ("unsafe_or_oversized_file", "java.nio.file.NoSuchFileException", 1, False),
                ("unrelated_failure", "java.nio.file.NoSuchFileException", 1, False),
                ("managed_operation_failed", "java.nio.file.NoSuchFileException", 86, False),
            ],
        )

    def test_runtime_retained_gap_accepts_only_its_two_exact_guards(self):
        self.assert_runtime_pairs(
            faults.RETAINED_GAP_FAILURES,
            [
                ("archive_contents", "io.detectbridge.archive.Format$Failure", 1, True),
                ("segment_chain_gap", "io.detectbridge.archive.Format$Failure", 1, True),
                ("archive_contents", "java.nio.file.NoSuchFileException", 1, False),
                ("segment_chain_gap", "java.lang.NullPointerException", 1, False),
                ("managed_operation_failed", "io.detectbridge.archive.Format$Failure", 1, False),
                ("unsafe_or_oversized_file", "io.detectbridge.archive.Format$Failure", 1, False),
                ("archive_contents", "io.detectbridge.archive.Format$Failure", 86, False),
            ],
        )

    def test_exact_subtree_proof_requires_every_file_removed_and_all_neighbors_unchanged(self):
        before = {
            "segments/2/": "directory",
            "segments/2/payload": "bytes",
            "segments/4/": "directory",
            "segments/4/payload": "neighbor",
        }
        after = {"segments/4/": "directory", "segments/4/payload": "neighbor"}
        faults.declared_subtree_removal(before, after, "segments/2")
        for changed in (
            dict(before),
            {"segments/4/": "directory"},
            dict(after, extra="new"),
            {"segments/4/": "directory", "segments/4/payload": "changed"},
        ):
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                faults.declared_subtree_removal(before, changed, "segments/2")

    def test_genuine_retirement_setup_uses_each_frozen_inclusive_timestamp_boundary(self):
        self.assertEqual(faults.retirement_seed_steps(self.frozen, 2), ((4, 100), (6, 200)))
        self.assertEqual(faults.retirement_seed_steps(self.frozen, 1), ((4, 100),))
        self.assertEqual(faults.retirement_seed_steps(self.frozen, 0), ())
        changed = copy.deepcopy(self.frozen)
        changed["legacy"]["segments"][2]["rows"][0]["timestamp"] = 201
        with self.assertRaises(AssertionError):
            faults.retirement_seed_steps(changed, 2)

    def test_ahead_head_keeps_its_checksum_valid_to_target_missing_committed_history(self):
        path = self.root / "maintenance/retirements/head.json"
        path.parent.mkdir(parents=True)
        value = dict(
            version="1.0.0",
            managed_id="00000000-0000-4000-8000-000000000051",
            kind="retirements",
            sequence=0,
            record_sha256=None,
        )
        value["checksum_sha256"] = history.sha(history.encoded(value))
        path.write_bytes(history.encoded(value) + b"\n")
        faults.mutate(self.root, "retirement_head_ahead", self.frozen)
        changed = json.loads(path.read_bytes())
        checksum = changed.pop("checksum_sha256")
        self.assertEqual(checksum, history.sha(history.encoded(changed)))
        self.assertEqual(changed["sequence"], 1)
        self.assertEqual(changed["record_sha256"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
