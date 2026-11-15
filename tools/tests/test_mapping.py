"""P10 source mappings and candidate provenance; expectations are not generated."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_contracts import load_json
from check_mapping import FIXTURES
from detection_compile import ROOT, CompileError, compile_rules
from detection_mapping import content_hash, encoded, sha

SOURCE_PATH = ROOT / "contracts/v1/examples/windows-security-4688.source.json"
SOURCE = load_json(SOURCE_PATH)
RULE_PATH = ROOT / "contracts/detection/v1/fixtures/rules/process.yml"
PROFILE = load_json(FIXTURES / "windows-security-4688.mapping.json")
PROVENANCE = load_json(FIXTURES / "candidates.json")


class MappingTests(unittest.TestCase):
    def compile(self, profile=None, provenance=None):
        return compile_rules(
            [RULE_PATH],
            [SOURCE],
            mappings=[PROFILE] if profile is None else profile,
            provenance=PROVENANCE if provenance is None else provenance,
        )

    def test_versions_provenance_and_determinism(self):
        old = compile_rules([RULE_PATH], [SOURCE])
        new = self.compile()
        self.assertEqual(old["version"], "1.0.0")
        self.assertEqual(new["version"], "2.0.0")
        self.assertEqual(new["rules"][0]["provenance"], PROVENANCE[0])
        self.assertEqual(new["rules"][0]["yaml"].encode(), RULE_PATH.read_bytes())
        self.assertEqual(encoded(new), encoded(self.compile()))
        self.assertNotEqual(old["bundle_sha256"], new["bundle_sha256"])

    def test_nested_mapping_tamper_with_recomputed_hash(self):
        for mutation in (
            "type",
            "target",
            "transform",
            "capability",
            "source_hash",
            "source_version",
            "source_id",
            "duplicate_alias",
            "incomplete",
            "path",
            "unsupported_path",
            "extra",
        ):
            profile = copy.deepcopy(PROFILE)
            field = profile["fields"][0]
            if mutation == "type":
                field["type"] = "integer"
            elif mutation == "target":
                field["target"] = "process"
            elif mutation == "transform":
                field["transform"] = "arbitrary-code/1.0.0"
            elif mutation == "capability":
                field["capability"] = "conditional"
            elif mutation == "source_hash":
                profile["source"]["sha256"] = "0" * 64
            elif mutation == "source_version":
                profile["source"]["version"] = "2.0.0"
            elif mutation == "source_id":
                profile["source"]["id"] = "other-source"
            elif mutation == "duplicate_alias":
                profile["fields"][1] = copy.deepcopy(field)
            elif mutation == "incomplete":
                profile["fields"].pop()
            elif mutation == "path":
                field["source_path"] = "/other"
            elif mutation == "unsupported_path":
                field["capability"] = "unsupported"
            elif mutation == "extra":
                field["execute"] = "private-value-sentinel"
            profile["sha256"] = content_hash(profile)
            with self.subTest(mutation=mutation), self.assertRaises(CompileError):
                self.compile([profile])

    def test_missing_duplicate_profiles_and_manifest_sets(self):
        for profiles, provenance in (
            ([], PROVENANCE),
            ([PROFILE, PROFILE], PROVENANCE),
            ([PROFILE], []),
            ([PROFILE], PROVENANCE * 2),
        ):
            with self.subTest(profiles=profiles), self.assertRaises(CompileError):
                self.compile(profiles, provenance)
        with self.assertRaises(CompileError):
            compile_rules([RULE_PATH], [SOURCE], mappings=[PROFILE])
        with self.assertRaises(CompileError):
            compile_rules([RULE_PATH], [SOURCE], provenance=PROVENANCE)

    def test_provenance_binding_and_lineage(self):
        for mutation in (
            "revision",
            "rule_id",
            "original_sha256",
            "license",
            "path",
            "repository_revision",
        ):
            p = copy.deepcopy(PROVENANCE)
            p[0][mutation] = {
                "revision": "0" * 64,
                "rule_id": "00000000-0000-4000-8000-000000000000",
                "original_sha256": "0" * 64,
                "license": "unknown",
                "path": "../private-file",
                "repository_revision": "main",
            }[mutation]
            with self.subTest(mutation=mutation), self.assertRaises(CompileError):
                self.compile(provenance=p)
        p = copy.deepcopy(PROVENANCE)
        p[0]["original_sha256"] = "0" * 64
        p[0]["modifications"] = [
            {
                "input_sha256": "0" * 64,
                "output_sha256": p[0]["revision"],
                "description": "Reviewed edit",
            }
        ]
        self.assertEqual(self.compile(provenance=p)["rules"][0]["provenance"], p[0])
        p[0]["modifications"][0]["input_sha256"] = "1" * 64
        with self.assertRaises(CompileError):
            self.compile(provenance=p)

    def test_failed_v2_cli_preserves_previous_bytes_and_redacts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            profile = copy.deepcopy(PROFILE)
            profile["fields"][0]["source_path"] = "/private-value-sentinel"
            profile["sha256"] = content_hash(profile)
            mapping = folder / "mapping.json"
            mapping.write_bytes(encoded(profile))
            output = folder / "plan.json"
            output.write_bytes(b"previous-valid-output")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/detection_compile.py"),
                    str(RULE_PATH),
                    "--source",
                    str(SOURCE_PATH),
                    "--mapping",
                    str(mapping),
                    "--provenance",
                    str(FIXTURES / "candidates.json"),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                timeout=35,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"previous-valid-output")
            self.assertNotIn(b"private-value-sentinel", result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["category"], "mapping_capability_conflict")

    def test_manifest_revision_is_exact_yaml_bytes(self):
        self.assertEqual(PROVENANCE[0]["revision"], sha(RULE_PATH.read_bytes()))
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "rule.yml"
            changed.write_bytes(RULE_PATH.read_bytes() + b"\n")
            with self.assertRaisesRegex(CompileError, "candidate_identity_mismatch"):
                compile_rules([changed], [SOURCE], mappings=[PROFILE], provenance=PROVENANCE)

    def test_candidate_analysis_accounts_for_rejected_rules(self):
        from detection_compile import analyze_candidates

        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "unsupported.yml"
            bad.write_text(
                RULE_PATH.read_text()
                .replace(
                    "70000000-0000-4000-8000-000000000001",
                    "70000000-0000-4000-8000-000000000002",
                )
                .replace("Image|endswith", "Image|re")
            )
            rejected = copy.deepcopy(PROVENANCE[0])
            rejected["rule_id"] = "70000000-0000-4000-8000-000000000002"
            rejected["revision"] = sha(bad.read_bytes())
            rejected["modifications"] = [
                {
                    "input_sha256": rejected["original_sha256"],
                    "output_sha256": rejected["revision"],
                    "description": "Original synthetic rejection case; changed UUID and modifier",
                }
            ]
            report = analyze_candidates(
                [RULE_PATH, bad], [SOURCE], [PROFILE], [PROVENANCE[0], rejected]
            )
            self.assertEqual([r["status"] for r in report["candidates"]], ["compiled", "rejected"])
            self.assertEqual(report["candidates"][0]["sources"][0]["status"], "supported")
            self.assertEqual(
                report["candidates"][1]["diagnostic"]["category"], "unsupported_modifier"
            )
            self.assertEqual(report["candidates"][1]["provenance"], rejected)
            with self.assertRaisesRegex(CompileError, "unsupported_modifier"):
                compile_rules(
                    [RULE_PATH, bad],
                    [SOURCE],
                    mappings=[PROFILE],
                    provenance=[PROVENANCE[0], rejected],
                )

    def test_analysis_rejects_invalid_or_duplicate_manifests(self):
        from detection_compile import analyze_candidates

        for paths, candidates in (([RULE_PATH], []), ([RULE_PATH, RULE_PATH], PROVENANCE * 2)):
            with self.assertRaises(CompileError):
                analyze_candidates(paths, [SOURCE], [PROFILE], candidates)

    def test_analysis_timeout_aborts_publication_instead_of_becoming_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            output.write_bytes(b"previous-valid-report")
            script = (
                "import sys, signal; sys.path.insert(0, 'tools'); "
                "import detection_compile as d; "
                "d.compile_rules=lambda *a, **k: signal.raise_signal(signal.SIGALRM); "
                "d.main()"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                    str(RULE_PATH),
                    "--source",
                    str(SOURCE_PATH),
                    "--mapping",
                    str(FIXTURES / "windows-security-4688.mapping.json"),
                    "--provenance",
                    str(FIXTURES / "candidates.json"),
                    "--analyze",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["category"], "compiler_timeout")
            self.assertEqual(output.read_bytes(), b"previous-valid-report")


if __name__ == "__main__":
    unittest.main()
