import base64
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle_archive_graph as graph


class LifecycleArchiveGraphTest(unittest.TestCase):
    windows: dict

    @classmethod
    def setUpClass(cls):
        packet = graph.ROOT / "contracts/lifecycle-runtime/v1/fixtures/source-cases.json"
        cls.windows = json.loads(packet.read_bytes())["cases"][0]["admissions"][0]

    def test_windows_schema_preserves_original_contract_and_rejects_unknown_context_edge(self):
        name = "integration-runtime:1.0.0:input"
        graph.schema(name, self.windows)
        for path in ((), ("host_binding",), ("mapping_profile",)):
            with self.subTest(path=path):
                invalid = copy.deepcopy(self.windows)
                context = invalid["context"]
                for key in path:
                    context = context[key]
                context["unregistered_dependency"] = "0" * 64
                with self.assertRaises(ValueError):
                    graph.schema(name, invalid)

    def test_wrong_evidence_hash_preserves_registered_original(self):
        raw = copy.deepcopy(self.windows["raw"])
        data = raw["evidence"].pop("inline").encode()
        digest = graph.sha(data)
        raw["evidence"].update(reference=dict(uri="urn:sha256:" + digest, object_sha256=digest))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name).resolve()
            (path / digest).write_bytes(data)
            graph.check_members(raw, path, [digest])
            for registered, expected in (([], digest), ([digest], "0" * 64)):
                raw["evidence"]["sha256"] = expected
                with self.assertRaises(ValueError):
                    graph.check_members(raw, path, registered)
                self.assertEqual(data, (path / digest).read_bytes())

    def test_incomplete_or_conflicting_signed_member_cannot_form_executable_closure(self):
        common = dict(
            deployment_id="71500000-0000-4000-8000-000000000020",
            authority_id="71500000-0000-4000-8000-000000000021",
        )
        data = b"synthetic member"
        pub = b"x" * 44
        key = base64.b64encode(pub).decode()

        def row(content):
            body = dict(
                **common,
                version="1.0.0",
                runtime_binding_sha256=graph.identity(common),
                bundle_sha256="0" * 64,
                member="plan.json",
                member_sha256=graph.sha(content),
                member_bytes=len(content),
                chunk_count=1,
                chunk_index=0,
                data_base64=base64.b64encode(content).decode(),
                chunk_sha256=graph.sha(content),
            )
            wrapper = dict(
                version="1.0.0",
                key_sha256=graph.sha(pub),
                payload=body,
                signature=base64.b64encode(bytes(64)).decode(),
            )
            return ((None, 0), None, wrapper)

        # This checks member assembly. Cryptographic verification is a separate mandatory stage.
        with self.assertRaisesRegex(ValueError, "missing_member"):
            graph.bundles([row(data)], common, key, [])
        with self.assertRaisesRegex(ValueError, "chunk_conflict"):
            graph.bundles([row(data), row(data + b"x")], common, key, [])
