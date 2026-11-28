"""Real compiler comparison and bounded local validator protocol/artifact failures."""

import base64
import copy
import json
import socket
import struct
import sys
import tarfile
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_worker_validator as builder
import lifecycle_worker_validator as service
from lifecycle_runtime_cases import prepare
from lifecycle_validation import bundle, encoded


class WorkerValidatorTests(unittest.TestCase):
    temporary: ClassVar[tempfile.TemporaryDirectory[str]]
    cases: ClassVar[dict[str, Any]]
    descriptor: ClassVar[dict[str, str]]

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.cases = prepare(Path(cls.temporary.name) / "cases")
        cls.descriptor = dict(
            version="1.0.0",
            artifact_sha256="e" * 64,
            image_id="sha256:" + "f" * 64,
            base_image=builder.BASE,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def request(self, data):
        return dict(
            version="1.0.0",
            nonce=str(uuid.uuid4()),
            plan_sha256=service.sha(data),
            plan_base64=base64.b64encode(data).decode(),
            validator_binding_sha256=service.sha(encoded(self.descriptor)),
        )

    def test_exact_frozen_a_and_b_recompile(self):
        for name in ("A", "B"):
            request = self.request(self.cases[name]["plan_bytes"])
            result = service.validate_request(request, self.descriptor)
            self.assertTrue(result["passed"])
            self.assertEqual(result["category"], "ok")
            self.assertEqual(result["nonce"], request["nonce"])
            self.assertEqual(result["plan_sha256"], request["plan_sha256"])

    def test_self_hashed_ast_disagreeing_with_original_yaml_rejected(self):
        forged = copy.deepcopy(self.cases["B"]["plan"])
        original = forged["rules"][0]["yaml"]
        forged["rules"][0]["expression"] = copy.deepcopy(
            self.cases["A"]["plan"]["rules"][0]["expression"]
        )
        del forged["bundle_sha256"]
        forged["bundle_sha256"] = service.sha(encoded(forged))
        data = encoded(forged)
        manifest = bundle(data)
        self.assertEqual(manifest["plan"]["sha256"], service.sha(data))
        self.assertEqual(forged["rules"][0]["yaml"], original)
        result = service.validate_request(self.request(data), self.descriptor)
        self.assertEqual((result["passed"], result["category"]), (False, "compiler_rejected"))

    def test_bad_hash_binding_encoding_and_unknown_fields_never_reach_compiler(self):
        request = self.request(self.cases["A"]["plan_bytes"])
        for key, value in (
            ("plan_sha256", "0" * 64),
            ("validator_binding_sha256", "0" * 64),
            ("plan_base64", request["plan_base64"] + "===="),
            ("untrusted_path", "/tmp/input"),
        ):
            invalid = {**request, key: value}
            with self.subTest(key=key), patch.object(service, "validate_plan") as compiler:
                with self.assertRaises(ValueError):
                    service.validate_request(invalid, self.descriptor)
                compiler.assert_not_called()

    def test_actual_local_framed_exchange_runs_compiler_and_binds_nonce(self):
        request = self.request(self.cases["A"]["plan_bytes"])
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        errors = []

        def worker():
            try:
                with right:
                    service.exchange(right, self.descriptor)
            except Exception as error:
                errors.append(type(error).__name__)

        thread = threading.Thread(target=worker)
        thread.start()
        with left:
            wire = encoded(request)
            left.sendall(struct.pack("!I", len(wire)) + wire)
            deadline = time.monotonic() + 10
            length = struct.unpack("!I", service.receive(left, 4, deadline))[0]
            result = json.loads(service.receive(left, length, deadline))
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual((result["passed"], result["nonce"]), (True, request["nonce"]))

    def test_oversized_frame_and_duplicate_json_close_before_compiler(self):
        for wire in (
            struct.pack("!I", 8 * service.MIB + 1),
            struct.pack("!I", 13) + b'{"x":1,"x":2}',
        ):
            left, right = socket.socketpair()
            try:
                left.sendall(wire)
                with (
                    self.subTest(wire=wire[:4]),
                    patch.object(service, "validate_plan") as compiler,
                ):
                    with self.assertRaises(ValueError):
                        service.exchange(right, self.descriptor)
                    compiler.assert_not_called()
            finally:
                left.close()
                right.close()

    def test_packet_is_reproducible_and_anchors_installed_source_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            first, second = root / "artifact.tar", root / "second.tar"
            self.assertEqual(builder.packet(first), builder.packet(second))
            with tarfile.open(first) as archive:
                archive.extractall(root, filter="data")
            descriptor = builder.packet(second)
            service.verify_install(root, descriptor)
            source = root / "tools/detection_compile.py"
            source.chmod(0o600)
            source.write_bytes(source.read_bytes() + b"\n# changed\n")
            with self.assertRaises(ValueError):
                service.verify_install(root, descriptor)
            manifest_path = root / "validator-manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"]["tools/detection_compile.py"].update(
                sha256=service.sha(source.read_bytes()), bytes=source.stat().st_size
            )
            manifest_path.chmod(0o600)
            manifest_path.write_bytes(encoded(manifest))
            with self.assertRaises(ValueError):
                service.verify_install(root, descriptor)


if __name__ == "__main__":
    unittest.main()
