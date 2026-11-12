"""Acquisition fault cases use temporary synthetic bytes and a loopback server."""

import concurrent.futures
import copy
import hashlib
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_datasets import CATALOG, approved_url, load_catalog, manifest_errors
from datasets import AcquisitionError, IntegrityError, acquire, inventory, process, verify_file


class TestServer(ThreadingHTTPServer):
    responses: dict[str, Any]
    requests: list[str]


class Handler(BaseHTTPRequestHandler):
    server: TestServer

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append(self.path)
        response = self.server.responses[self.path]
        if isinstance(response, list):
            response = response.pop(0) if len(response) > 1 else response[0]
        code, headers, body = response
        if self.path == "/slow":
            time.sleep(0.15)
        self.send_response(code)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name) / "cache"
        self.server = TestServer(("127.0.0.1", 0), Handler)
        self.server.responses = {}
        self.server.requests = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def local_only(self, url):
        if not url.startswith(self.base + "/") or urlsplit(url).hostname != "127.0.0.1":
            raise AcquisitionError("test_unapproved_redirect")

    def resource(self, body=b"one\n\nthree\r\nlast", path="/payload"):
        self.server.responses[path] = (200, {"Content-Length": str(len(body))}, body)
        return {
            "url": self.base + path,
            "sha256": hashlib.sha256(body).hexdigest(),
            "size_bytes": len(body),
        }

    def get(self, resource):
        return acquire(resource, self.cache, time.monotonic() + 5, self.local_only)

    def test_selective_repeatable_cache_and_corruption(self):
        first = self.resource()
        second = self.resource(b"not requested\n", "/other")
        path, outcome = self.get(first)
        self.assertEqual(outcome, "downloaded")
        self.assertEqual(self.server.requests, ["/payload"])
        self.assertEqual(self.get(first)[1], "cache_hit")
        self.assertEqual(self.server.requests, ["/payload"])
        path.write_bytes(b"corrupt")
        with self.assertRaises(IntegrityError):
            verify_file(path, first)
        self.assertEqual(self.get(first)[1], "repaired_corrupt_cache")
        verify_file(path, first)
        self.assertFalse((self.cache / "objects/sha256" / second["sha256"]).exists())

    def test_framing_preserves_every_byte(self):
        body = b"one\r\n\nlast"
        resource = self.resource(body)
        path, _ = self.get(resource)
        framing = inventory(path)
        self.assertEqual(
            framing["records"],
            [
                {"position": 0, "offset": 0, "length": 5},
                {"position": 1, "offset": 5, "length": 1},
                {"position": 2, "offset": 6, "length": 4},
            ],
        )
        self.assertEqual(path.read_bytes(), body)

    def test_bad_size_digest_pointer_and_archives_leave_no_object(self):
        for body in (
            b"version https://git-lfs.github.com/spec/v1\noid sha256:x\n",
            b"PK\x03\x04archive",
            b"\x1f\x8barchive",
            b"x" * 257 + b"ustar",
        ):
            resource = self.resource(body)
            with self.assertRaises(IntegrityError):
                self.get(resource)
            self.assertFalse((self.cache / "objects/sha256" / resource["sha256"]).exists())
        resource = self.resource()
        resource["sha256"] = "0" * 64
        with self.assertRaises(IntegrityError):
            self.get(resource)
        resource = self.resource()
        resource["size_bytes"] += 1
        with self.assertRaises(IntegrityError):
            self.get(resource)
        self.assertFalse(list(self.cache.rglob(".partial-*")))

    def test_no_content_length_oversize_and_truncation(self):
        resource = self.resource(b"abc")
        self.server.responses["/payload"] = (200, {}, b"abcd")
        with self.assertRaises(IntegrityError):
            self.get(resource)
        self.server.responses["/payload"] = (200, {}, b"ab")
        with self.assertRaises(IntegrityError):
            self.get(resource)

    def test_invalid_encoding_and_record_count_not_published(self):
        for body, count in [(b"\xff\n", 1), (b"one\n", 2)]:
            resource = self.resource(body)
            resource["record_count"] = count
            with self.assertRaises(IntegrityError):
                self.get(resource)
            self.assertFalse((self.cache / "objects/sha256" / resource["sha256"]).exists())

    def test_retry_limits_and_integrity_no_retry(self):
        resource = self.resource()
        success = self.server.responses["/payload"]
        self.server.responses["/payload"] = [(503, {}, b""), success]
        with patch("datasets.time.sleep"):
            self.get(resource)
        self.assertEqual(len(self.server.requests), 2)
        resource = self.resource(b"new data")
        self.server.requests.clear()
        self.server.responses["/payload"] = (503, {}, b"")
        with patch("datasets.time.sleep"):
            with self.assertRaises(AcquisitionError):
                self.get(resource)
        self.assertEqual(len(self.server.requests), 3)
        self.server.requests.clear()
        self.server.responses["/payload"] = (200, {}, b"tampered")
        with self.assertRaises(IntegrityError):
            self.get(resource)
        self.assertEqual(len(self.server.requests), 1)

    def test_redirect_policy_and_loop_limit(self):
        resource = self.resource()
        self.server.responses["/payload"] = (
            302,
            {"Location": "http://example.invalid/private"},
            b"",
        )
        with self.assertRaises(AcquisitionError):
            self.get(resource)
        self.server.responses["/payload"] = (302, {"Location": self.base + "/payload"}, b"")
        with self.assertRaises(AcquisitionError):
            self.get(resource)
        for url in (
            "http://raw.githubusercontent.com/path",
            "https://evil.invalid/path",
            "https://user:password@raw.githubusercontent.com/path",
            "https://raw.githubusercontent.com/path?token=x",
        ):
            with self.assertRaises(ValueError):
                approved_url(url)

    def test_deadline_transport_and_interruption(self):
        resource = self.resource()
        with self.assertRaises(AcquisitionError):
            acquire(resource, self.cache, time.monotonic() - 1, self.local_only)
        with (
            patch("datasets.stream_download", side_effect=urllib.error.URLError(socket.timeout())),
            patch("datasets.time.sleep"),
        ):
            with self.assertRaises(AcquisitionError):
                self.get(resource)
        self.assertFalse(list(self.cache.rglob(".partial-*")))
        self.assertFalse((self.cache / "objects/sha256" / resource["sha256"]).exists())

    def test_slow_server_obeys_deadline(self):
        resource = self.resource(b"delayed", "/slow")
        with self.assertRaises(AcquisitionError):
            acquire(resource, self.cache, time.monotonic() + 0.02, self.local_only)
        self.assertFalse((self.cache / "objects/sha256" / resource["sha256"]).exists())
        self.assertFalse(list(self.cache.rglob(".partial-*")))

    def test_catalog_schema_cannot_retrieve_remote_refs(self):
        schema = json.loads((CATALOG / "manifest.schema.json").read_text())
        schema["$ref"] = "https://example.invalid/not-allowed"
        manifest = next(iter(load_catalog().values()))
        with patch(
            "socket.create_connection", side_effect=AssertionError("network forbidden")
        ) as network:
            self.assertTrue(manifest_errors(manifest, schema))
            network.assert_not_called()

    def test_concurrent_publication(self):
        resource = self.resource()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.get(resource), range(4)))
        for path, _ in results:
            verify_file(path, resource)
        self.assertFalse(list(self.cache.rglob(".partial-*")))

    def test_complete_report_and_pointer_provenance(self):
        manifest = copy.deepcopy(next(iter(load_catalog().values())))
        resource = self.resource(b"first\nlast")
        manifest["payload"] = {**resource, "compression": "none"}
        manifest["framing"]["record_count"] = 2
        pointer = f"version https://git-lfs.github.com/spec/v1\noid sha256:{resource['sha256']}\nsize {resource['size_bytes']}\n".encode()
        manifest["provenance"] = [
            dict(self.resource(b"license", "/license"), role="license"),
            dict(self.resource(b"metadata", "/metadata"), role="scenario_metadata"),
            dict(self.resource(pointer, "/pointer"), role="lfs_pointer"),
        ]
        report = process(manifest, self.cache, True, self.local_only)
        self.assertEqual(report["record_labels"], "unknown")
        self.assertEqual(report["conversion_history"], [])
        self.assertEqual(report["framing"]["record_count"], 2)
        count = len(self.server.requests)
        again = process(manifest, self.cache, True, self.local_only)
        self.assertEqual(len(self.server.requests), count)
        self.assertEqual(again["artifact_sha256"], report["artifact_sha256"])
        self.assertTrue(all(p["outcome"] == "cache_hit" for p in again["provenance"]))
        self.assertEqual(len(list((self.cache / "reports").glob("*.json"))), 2)

    def test_catalog_rejects_unknown_labels_terms_paths_and_ids(self):
        schema = json.loads((CATALOG / "manifest.schema.json").read_text())
        manifest = next(iter(load_catalog().values()))
        for key, value in [("manifest_version", "2.0.0")]:
            broken = copy.deepcopy(manifest)
            broken[key] = value
            self.assertTrue(manifest_errors(broken, schema))
        for mutate in (
            lambda m: m["terms"].update(review_status="unresolved"),
            lambda m: m["capture"].update(record_labels="malicious"),
            lambda m: m["upstream"].update(path="../escape"),
            lambda m: m["provenance"].pop(),
        ):
            broken = copy.deepcopy(manifest)
            mutate(broken)
            self.assertTrue(manifest_errors(broken, schema))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.schema.json").write_text(json.dumps(schema))
            (root / (manifest["id"] + ".json")).write_text(json.dumps(manifest))
            (root / "duplicate.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_catalog(root)
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                ".cache/datasets/objects/sha256/example",
                ".cache/datasets/reports/example.json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 2)
