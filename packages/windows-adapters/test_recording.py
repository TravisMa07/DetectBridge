"""Controlled-recording verifier regressions using explicitly synthetic XML only."""

import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import recording as subject
from recording_plan import prepare, validate_rules

ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(__file__).resolve().parent
RUN = "00000000-0000-4000-8000-000000000011"


class ControlledRecordingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        specs = json.loads((MODULE / "recording/expectations.json").read_bytes())
        records = []
        for family in ("security", "sysmon"):
            for action in specs["actions"]:
                data = (MODULE / f"fixtures/{family}.xml").read_bytes().rstrip(b"\n")
                data = data.replace(b"C:\\synthetic.exe", action["image"].encode())
                name = f"{family}-{action['id']}.xml"
                (self.directory / name).write_bytes(data)
                system, fields, _ = subject.xml_record(data)
                security = family == "security"
                records.append(
                    dict(
                        filename=name,
                        family=family,
                        action=action["id"],
                        event_record_id=len(records) + 1,
                        observed_utc="2026-11-12T12:02:00Z",
                        sha256=subject.sha(data),
                        size_bytes=len(data),
                        computer="SYNTHETIC-HOST",
                        expected=dict(
                            disposition="eligible",
                            image=action["image"],
                            pid=16 if security else 42,
                            parent_pid=32 if security else 12,
                            command_line=fields["CommandLine"],
                            user="LAB\\Alice",
                            source_time=system.find(subject.NS + "TimeCreated").attrib["SystemTime"]
                            if security
                            else fields["UtcTime"],
                            counts=specs["rule_counts"][action["id"]],
                        ),
                    )
                )
        data = (
            (MODULE / "fixtures/sysmon.xml")
            .read_bytes()
            .rstrip(b"\n")
            .replace(b"<EventID>1</EventID>", b"<EventID>4</EventID>")
        )
        (self.directory / "sysmon-control.xml").write_bytes(data)
        records.append(
            dict(
                filename="sysmon-control.xml",
                family="sysmon",
                action="service-state",
                event_record_id=5,
                observed_utc="2026-11-12T12:02:00Z",
                sha256=subject.sha(data),
                size_bytes=len(data),
                computer="SYNTHETIC-HOST",
                expected=dict(disposition="unsupported_source"),
            )
        )
        self.catalog = dict(
            version="1.0.0",
            review_status="candidate",
            host_id="synthetic-test-host",
            generation="synthetic-test-boot",
            capture_run=dict(id=1, attempt=1, url="https://example.invalid/synthetic"),
            records=records,
        )
        # These tests exercise prepared-input/output integrity, not capture provenance.
        # Only this boundary is mocked; real evidence uses artifacts() with no bypass.
        self.bypass = patch.object(subject, "artifacts", return_value=None)
        self.bypass.start()
        self.addCleanup(self.bypass.stop)
        self.rows = subject.inputs(self.catalog, self.directory, RUN)
        self.plan = prepare()
        plan = self.directory / "plan.json"
        plan.write_bytes(subject.encoded(self.plan))
        source = self.directory / "input.ndjson"
        source.write_bytes(b"".join(subject.encoded(r) + b"\n" for r in self.rows))
        output = self.directory / "output.ndjson"
        environment = dict(os.environ, JAVA_HOME=str(ROOT / ".cache/jdk"))
        subprocess.run(
            [
                str(MODULE / "build/install/windows-adapters/bin/windows-adapters"),
                str(source),
                str(output),
                str(self.directory),
                str(plan),
            ],
            env=environment,
            check=True,
            capture_output=True,
        )
        self.published = [json.loads(line) for line in output.read_bytes().splitlines()]

    def verify(self, published=None, rows=None, catalog=None, plan=None):
        return subject.verify(
            catalog or self.catalog,
            self.directory,
            self.rows if rows is None else rows,
            self.published if published is None else published,
            plan or self.plan,
            RUN,
        )

    def test_frozen_plan_keeps_its_committed_revision(self):
        revision = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "packages/windows-adapters/recording/rules"],
            cwd=ROOT,
            text=True,
        ).strip()
        frozen = prepare(revision)
        validate_rules(frozen)
        frozen["rules"][0]["expression"] = frozen["rules"][1]["expression"]
        with self.assertRaises(ValueError):
            validate_rules(frozen)

    def test_literal_counts_and_real_adapter_evaluator(self):
        self.assertEqual(
            self.verify(), dict(records=5, eligible=4, unsupported=1, matched=2, unmatched=6)
        )

    def test_same_count_field_quality_and_outcome_tampering_rejected(self):
        changes = [
            lambda r: r[0]["event"]["source_fields"]["windows_system"]["values"].update(
                Computer="forged"
            ),
            lambda r: r[0]["event"]["user"].update(id="wrong-sid"),
            lambda r: r[0]["event"]["host"].update(id="made-up-host"),
            lambda r: r[0]["event"]["process"].update(pid=99),
            lambda r: r[0]["event"]["detectbridge"]["quality"].update(eligibility="skipped"),
            lambda r: r[0]["evaluation"]["counts"].update(matched=0, unmatched=2),
            lambda r: r[0]["evaluation"].update(matched=[]),
            lambda r: r[0]["event"]["detectbridge"]["time"].update(
                first_observed="2026-11-12T12:03:00Z"
            ),
            lambda r: r[4]["preservation"].update(code="extraction_failed"),
        ]
        for change in changes:
            with self.subTest(change=change):
                mutated = copy.deepcopy(self.published)
                change(mutated)
                with self.assertRaises(ValueError):
                    self.verify(published=mutated)

    def test_input_binding_source_and_membership_tampering_rejected(self):
        for member, key in (
            ("host_binding", "host_id"),
            ("source_generation", "id"),
            ("mapping_profile", "sha256"),
        ):
            mutated = copy.deepcopy(self.rows)
            mutated[0]["context"][member][key] = "tampered"
            with self.assertRaises(ValueError):
                self.verify(rows=mutated)
        with self.assertRaises(ValueError):
            self.verify(published=self.published[:-1])
        with self.assertRaises(ValueError):
            self.verify(published=list(reversed(self.published)))

    def test_replay_retains_raw_event_identity_and_isolates_results(self):
        replay = subject.inputs(
            self.catalog, self.directory, "00000000-0000-4000-8000-000000000022"
        )
        self.assertEqual([r["raw"] for r in self.rows], [r["raw"] for r in replay])
        self.assertNotEqual(self.rows[0]["context"]["run_id"], replay[0]["context"]["run_id"])
        with self.assertRaises(ValueError):
            subject.verify(
                self.catalog,
                self.directory,
                replay,
                self.published,
                self.plan,
                replay[0]["context"]["run_id"],
            )

    def test_candidate_catalog_and_changed_original_cannot_pass_provenance(self):
        self.bypass.stop()
        with self.assertRaises(ValueError):
            subject.artifacts(self.catalog, self.directory)
        catalog = dict(
            version="1.0.0",
            review_status="reviewed",
            terms=dict(
                scope="local-qualification-only",
                payload_publication=False,
                sysmon_binary_redistribution=False,
            ),
            artifacts=[dict(filename="security-cmd.xml", size_bytes=1, sha256="0" * 64)],
        )
        with self.assertRaises(ValueError):
            subject.artifacts(catalog, self.directory)
        catalog["artifacts"][0]["filename"] = "../outside"
        with self.assertRaises(ValueError):
            subject.artifacts(catalog, self.directory)
        self.bypass.start()


if __name__ == "__main__":
    unittest.main()
