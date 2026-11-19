"""Independent P05 import byte, completion, provenance and restoration expectations."""

import copy
import fcntl
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import datasets
import p05_archive as archive
import replay
from check_contracts import load_json
from check_datasets import load_catalog

BODY = bytes.fromhex("410d0a0ac3a90a5a")
MANAGED = "00000000-0000-4000-8000-000000000051"


def hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


class P05ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.cache = self.root / "data"
        self.runs = self.root / "runs"
        self.catalog = {"linux-audit-whoami": copy.deepcopy(load_catalog()["linux-audit-whoami"])}
        manifest = self.catalog["linux-audit-whoami"]
        self.put(manifest["payload"], BODY)
        manifest["framing"]["record_count"] = 4
        for resource in manifest["provenance"]:
            if resource["role"] == "lfs_pointer":
                payload = manifest["payload"]
                body = (
                    "version https://git-lfs.github.com/spec/v1\noid sha256:"
                    + payload["sha256"]
                    + "\nsize 8\n"
                ).encode()
            else:
                body = resource["role"].encode()
            self.put(resource, body)
        with patch.object(replay, "SEGMENT_RECORDS", 2):
            self.run_id = replay.start(
                list(self.catalog),
                catalog=self.catalog,
                runs=self.runs,
                captures=self.root / "captures",
                data_cache=self.cache,
                rate=None,
            )["run_id"]
        self.folder = self.runs / self.run_id
        self.generated = self.root / "generated"

    def tearDown(self):
        self.temporary.cleanup()

    def put(self, resource, body):
        resource.update(sha256=hashlib.sha256(body).hexdigest(), size_bytes=len(body))
        path = replay.object_path(self.cache, resource)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def source(self, **changes):
        args = dict(
            run_dir=self.folder,
            data_cache=self.cache,
            managed_id=MANAGED,
            generated_dir=self.generated,
            reviewed_catalog=self.catalog,
        )
        args.update(changes)
        return archive.source(**args)

    def test_exact_closure_framing_identity_and_original_lock(self):
        before = hashes(self.folder), hashes(self.cache)
        with self.source() as prepared:
            meta = prepared.metadata
            self.assertEqual(
                (meta["record_count"], meta["envelope_count"], meta["segment_count"]), (4, 6, 3)
            )
            self.assertEqual(set(prepared.sources), {f["path"] for f in meta["files"]})
            self.assertEqual(
                meta["files"],
                sorted(
                    meta["files"], key=lambda f: (f["role"], f["path"], f["sha256"], f["length"])
                ),
            )
            self.assertEqual(
                meta["manifest_sha256"],
                hashlib.sha256((self.folder / "manifest.json").read_bytes()).hexdigest(),
            )
            config = load_json(self.folder / "manifest.json")
            self.assertEqual(meta["p05_manifest_sha256"], replay.digest(config))
            framing = load_json(prepared.sources["index/framing.json"])
            self.assertEqual(
                [(r["offset"], r["length"]) for r in framing["datasets"][0]["framing"]["records"]],
                [(0, 3), (3, 1), (4, 3), (7, 1)],
            )
            projection = load_json(prepared.sources["index/captures.json"])
            self.assertEqual(projection["captures"][0]["capture"], config["datasets"][0]["capture"])
            canonical = json.dumps(
                [
                    "detectbridge.archive.p05-import/1",
                    MANAGED,
                    self.run_id,
                    meta["manifest_sha256"],
                    meta["files"],
                ],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            self.assertEqual(meta["id"], hashlib.sha256(canonical).hexdigest())
            with (self.folder / ".run.lock").open("rb") as lock:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(before, (hashes(self.folder), hashes(self.cache)))
        with replay.locked(self.folder / ".run.lock"):
            pass
        with self.source() as again:
            self.assertEqual(meta, again.metadata)

    def test_advisory_absent_or_behind_is_not_authority(self):
        for advisory in (
            None,
            dict(
                contract_version="1.0.0",
                manifest_sha256=replay.digest(load_json(self.folder / "manifest.json")),
                segments=0,
                next_sequence=0,
                bytes=0,
                status="running",
            ),
        ):
            checkpoint = self.folder / "checkpoint.json"
            if advisory is None:
                checkpoint.unlink(missing_ok=True)
            else:
                checkpoint.write_bytes(replay.encoded(advisory))
            before = hashes(self.folder)
            shutil.rmtree(self.generated, ignore_errors=True)
            with self.source() as prepared:
                self.assertEqual(prepared.metadata["envelope_count"], 6)
            self.assertEqual(before, hashes(self.folder))

    def test_restore_hashes_and_original_completed_semantics(self):
        with self.source() as prepared:
            restored = self.root / "restored" / self.run_id
            data = self.root / "restored-data"
            index = self.root / "restored-index"
            restored.mkdir(parents=True)
            for logical, source in prepared.sources.items():
                prefix, relative = logical.split("/", 1)
                destination = {"run": restored, "cache": data, "index": index}[prefix] / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            before = hashes(restored), hashes(data), hashes(index)
            archive.validate_restored(
                restored, data, prepared.metadata, index, reviewed_catalog=self.catalog
            )
            self.assertEqual(before, (hashes(restored), hashes(data), hashes(index)))
            self.assertFalse((restored / ".run.lock").exists())
            self.assertEqual(
                replay.execute(self.run_id, restored.parent, data, inspect=True)["status"],
                "completed",
            )
            damaged = next(index.iterdir())
            damaged.write_bytes(damaged.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                archive.validate_restored(
                    restored, data, prepared.metadata, index, reviewed_catalog=self.catalog
                )

    def test_missing_corrupt_gapped_or_incomplete_sources(self):
        for mutate in ("payload", "segment", "gap", "incomplete", "checkpoint", "terms"):
            with self.subTest(mutate=mutate):
                snapshots = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                try:
                    if mutate == "payload":
                        replay.object_path(
                            self.cache, self.catalog["linux-audit-whoami"]["payload"]
                        ).unlink()
                    elif mutate == "segment":
                        (self.folder / "segments/00000000/records.ndjson").write_bytes(b"corrupt\n")
                    elif mutate in {"gap", "incomplete"}:
                        shutil.rmtree(
                            self.folder
                            / ("segments/00000001" if mutate == "gap" else "segments/00000002")
                        )
                        (self.folder / "checkpoint.json").unlink()
                    elif mutate == "checkpoint":
                        checkpoint = load_json(self.folder / "checkpoint.json")
                        checkpoint["next_sequence"] += 1
                        (self.folder / "checkpoint.json").write_bytes(replay.encoded(checkpoint))
                    else:
                        self.catalog["linux-audit-whoami"]["terms"]["review_notes"] += "changed"
                        # Original P05 correctly validates its frozen local run; import adds
                        # the separate requirement to recheck today's reviewed usage terms.
                        self.assertEqual(
                            replay.execute(self.run_id, self.runs, self.cache, inspect=True)[
                                "status"
                            ],
                            "completed",
                        )
                    with self.assertRaises((ValueError, datasets.IntegrityError)):
                        with self.source():
                            self.fail("invalid source was accepted")
                finally:
                    self.catalog["linux-audit-whoami"]["terms"]["review_notes"] = load_json(
                        self.folder / "manifest.json"
                    )["datasets"][0]["manifest"]["terms"]["review_notes"]
                    for path, body in snapshots.items():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(body)

    def test_source_locks_overlap_and_symlinks(self):
        with replay.locked(self.folder / ".run.lock"):
            with self.assertRaises(ValueError):
                with self.source():
                    self.fail("source lock was bypassed")
        for generated in (self.folder, self.folder / "index", self.cache, self.root):
            with self.assertRaises(ValueError):
                with self.source(generated_dir=generated):
                    self.fail("overlapping root accepted")
        linked = self.root / "link"
        linked.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(ValueError):
            with self.source(run_dir=linked):
                self.fail("symlink source accepted")
        payload = replay.object_path(self.cache, self.catalog["linux-audit-whoami"]["payload"])
        saved = payload.read_bytes()
        payload.unlink()
        target = self.root / "external-object"
        target.write_bytes(saved)
        payload.symlink_to(target)
        with self.assertRaises(ValueError):
            with self.source():
                self.fail("symlink object accepted")

    def test_raw_manifest_hash_differs_from_semantic_digest(self):
        config = load_json(self.folder / "manifest.json")
        (self.folder / "manifest.json").write_text(json.dumps(config, indent=3))
        with self.source() as prepared:
            self.assertNotEqual(
                prepared.metadata["manifest_sha256"], prepared.metadata["p05_manifest_sha256"]
            )
            self.assertEqual(prepared.metadata["p05_manifest_sha256"], replay.digest(config))

    def test_p05_rejects_twelve_digit_timestamp(self):
        config = load_json(self.folder / "manifest.json")
        config["datasets"][0]["capture"]["first_observed"] = "2026-01-01T00:00:00.123456789012Z"
        (self.folder / "manifest.json").write_bytes(replay.encoded(config))
        (self.folder / "manifest.sha256").write_text(replay.digest(config) + "\n")
        with self.assertRaises(ValueError):
            with self.source():
                self.fail("unsupported P05 precision accepted")

    def test_selected_catalog_digest_and_another_original_run(self):
        with self.source() as first:
            metadata = copy.deepcopy(first.metadata)
        expanded = copy.deepcopy(self.catalog)
        expanded["unrelated"] = {"unselected": True}
        with self.source(reviewed_catalog=expanded) as same:
            self.assertEqual(same.metadata, metadata)
        run = replay.start(
            list(self.catalog),
            catalog=self.catalog,
            runs=self.runs,
            captures=self.root / "captures",
            data_cache=self.cache,
            rate=12.5,
            pacer_factory=lambda _: unittest.mock.Mock(),
        )
        with self.source(
            run_dir=self.runs / run["run_id"], generated_dir=self.root / "another-index"
        ) as another:
            self.assertNotEqual(metadata["id"], another.metadata["id"])
            self.assertEqual(load_json(self.runs / run["run_id"] / "manifest.json")["rate"], 12.5)

    def test_corrupt_restoration_and_descriptor_binding(self):
        with self.source() as prepared:
            restored = self.root / "restored" / self.run_id
            data = self.root / "restored-data"
            index = self.root / "restored-index"
            restored.mkdir(parents=True)
            for logical, source in prepared.sources.items():
                prefix, relative = logical.split("/", 1)
                target = {"run": restored, "cache": data, "index": index}[prefix] / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            target = next((data / "objects/sha256").iterdir())
            saved = target.read_bytes()
            target.unlink()
            with self.assertRaises((ValueError, datasets.IntegrityError)):
                archive.validate_restored(
                    restored, data, prepared.metadata, index, reviewed_catalog=self.catalog
                )
            target.write_bytes(saved)
            for mutate in ("role", "digest", "fraction", "path"):
                metadata = copy.deepcopy(prepared.metadata)
                if mutate == "role":
                    metadata["files"][0]["role"] = "manifest"
                elif mutate == "digest":
                    metadata["id"] = "0" * 64
                elif mutate == "fraction":
                    metadata["record_count"] = 4.0
                else:
                    metadata["files"][0]["path"] = "run/../outside"
                with self.assertRaises(ValueError):
                    archive.validate_restored(
                        restored, data, metadata, index, reviewed_catalog=self.catalog
                    )

    def test_invalid_utf8_and_timing_index_precision_fail_before_generation(self):
        original = load_json(self.folder / "manifest.json")
        manifest = self.catalog["linux-audit-whoami"]
        self.put(manifest["payload"], b"\xff" + BODY[1:])
        pointer = next(
            resource for resource in manifest["provenance"] if resource["role"] == "lfs_pointer"
        )
        self.put(
            pointer,
            (
                "version https://git-lfs.github.com/spec/v1\noid sha256:"
                + manifest["payload"]["sha256"]
                + "\nsize 8\n"
            ).encode(),
        )
        changed = copy.deepcopy(original)
        changed["datasets"][0]["manifest"] = copy.deepcopy(manifest)
        changed["datasets"][0]["manifest_sha256"] = replay.digest(manifest)
        (self.folder / "manifest.json").write_bytes(replay.encoded(changed))
        (self.folder / "manifest.sha256").write_text(replay.digest(changed) + "\n")
        with self.assertRaisesRegex(datasets.IntegrityError, "invalid_utf8"):
            with self.source():
                self.fail("invalid original UTF-8 accepted")
        self.assertFalse(self.generated.exists())
        manifest = copy.deepcopy(original["datasets"][0]["manifest"])
        self.catalog["linux-audit-whoami"] = manifest
        (self.folder / "manifest.json").write_bytes(replay.encoded(original))
        (self.folder / "manifest.sha256").write_text(replay.digest(original) + "\n")
        config = original
        index = dict(
            contract_version="1.0.0",
            datasets=[
                dict(
                    dataset_id="linux-audit-whoami",
                    artifact_sha256=manifest["payload"]["sha256"],
                    framing="lf-byte-records-v1",
                    timestamps=[dict(position=0, timestamp="2026-01-01T00:00:00.123456789012Z")],
                )
            ],
        )
        body = replay.encoded(index)
        (self.folder / "timing-index.json").write_bytes(body)
        config["timing_index_sha256"] = hashlib.sha256(body).hexdigest()
        (self.folder / "manifest.json").write_bytes(replay.encoded(config))
        (self.folder / "manifest.sha256").write_text(replay.digest(config) + "\n")
        with self.assertRaisesRegex(ValueError, "invalid_timing-index"):
            with self.source():
                self.fail("unsupported P05 timing precision accepted")
        self.assertFalse(self.generated.exists())

    def test_finite_component_bounds_and_no_unknown_generated_adoption(self):
        before = hashes(self.folder), hashes(self.cache)
        for module, name, value in (
            (archive, "MAX_FILE", 1),
            (archive, "MAX_FILES", 2),
            (archive, "MAX_DERIVED", 1),
            (replay, "MAX_RECORDS", 1),
            (replay, "MAX_BATCH", 1),
            (replay, "MAX_OUTPUT", 1),
        ):
            with self.subTest(bound=name), patch.object(module, name, value):
                with self.assertRaises(ValueError):
                    with self.source():
                        self.fail("finite bound bypassed")
                self.assertFalse(self.generated.exists())
                self.assertEqual(before, (hashes(self.folder), hashes(self.cache)))
        self.generated.mkdir()
        marker = self.generated / "foreign"
        marker.write_bytes(b"keep exact")
        with self.assertRaisesRegex(ValueError, "p05_index_contents"):
            with self.source():
                self.fail("foreign generation directory adopted")
        self.assertEqual(marker.read_bytes(), b"keep exact")

    def test_frozen_import_identity_and_missing_original_lock(self):
        packet = load_json(
            archive.ROOT / "contracts/archive-maintenance/v1/fixtures/expectations.json"
        )
        vector = next(
            v
            for v in packet["identities"]
            if v["preimage"][0] == "detectbridge.archive.p05-import/1"
        )
        self.assertEqual(archive.digest(vector["preimage"]), vector["sha256"])
        (self.folder / ".run.lock").unlink()
        before = hashes(self.folder), hashes(self.cache)
        with self.assertRaisesRegex(ValueError, "p05_source_file"):
            with self.source():
                self.fail("missing source lock was created")
        self.assertEqual(before, (hashes(self.folder), hashes(self.cache)))
        self.assertFalse((self.folder / ".run.lock").exists())

    def test_original_timing_precision_and_float_pacing_are_preserved(self):
        manifest = self.catalog["linux-audit-whoami"]
        timestamps = [
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00.123456Z",
            "2026-01-01T00:00:00.123456789Z",
        ]
        timing = dict(
            contract_version="1.0.0",
            datasets=[
                dict(
                    dataset_id="linux-audit-whoami",
                    artifact_sha256=manifest["payload"]["sha256"],
                    framing="lf-byte-records-v1",
                    timestamps=[
                        dict(position=i, timestamp=value) for i, value in enumerate(timestamps)
                    ],
                )
            ],
        )
        index = self.root / "timing.json"
        index.write_bytes(replay.encoded(timing))
        run = replay.start(
            list(self.catalog),
            catalog=self.catalog,
            runs=self.runs,
            captures=self.root / "captures",
            data_cache=self.cache,
            timing_path=index,
            rate=12.5,
            pacer_factory=lambda _: unittest.mock.Mock(),
        )
        folder = self.runs / run["run_id"]
        with self.source(run_dir=folder, generated_dir=self.root / "timing-generated") as prepared:
            self.assertEqual(
                prepared.sources["run/timing-index.json"].read_bytes(), index.read_bytes()
            )
            config, lookup = replay.load_run(folder, replay.ReplayValidator())
            self.assertEqual(config["rate"], 12.5)
            self.assertEqual([lookup[("linux-audit-whoami", i)] for i in range(3)], timestamps)
            self.assertEqual(
                config["timing_index_sha256"], hashlib.sha256(index.read_bytes()).hexdigest()
            )

    def test_catalog_numeric_and_boolean_equivalence_is_not_exact_match(self):
        for value in (4.0, True):
            config = load_json(self.folder / "manifest.json")
            config["datasets"][0]["manifest"]["framing"]["record_count"] = value
            config["datasets"][0]["manifest_sha256"] = replay.digest(
                config["datasets"][0]["manifest"]
            )
            (self.folder / "manifest.json").write_bytes(replay.encoded(config))
            (self.folder / "manifest.sha256").write_text(replay.digest(config) + "\n")
            with self.assertRaisesRegex(ValueError, "p05_catalog_changed"):
                with self.source():
                    self.fail("catalog scalar-type mismatch accepted")


if __name__ == "__main__":
    unittest.main()
