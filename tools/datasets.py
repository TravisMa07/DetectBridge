"""Selective, bounded dataset acquisition. No parsing, normalization or replay."""

import argparse
import codecs
import hashlib
import http.client
import json
import os
import socket
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from check_datasets import CATALOG, MAX_ARTIFACT, MAX_BATCH, ROOT, approved_url, load_catalog

TOOL_VERSION = "1.0.0"
CACHE = ROOT / ".cache/datasets"


class AcquisitionError(Exception):
    """Safe category only; never include URLs or event content."""


class IntegrityError(AcquisitionError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path):
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    records = []
    offset = 0
    with path.open("rb") as stream:
        for position, line in enumerate(stream):
            decoder.decode(line)
            records.append({"position": position, "offset": offset, "length": len(line)})
            offset += len(line)
    decoder.decode(b"", final=True)
    return {
        "id": "lf-byte-records-v1",
        "record_count": len(records),
        "size_bytes": offset,
        "records": records,
    }


def verify_file(path, resource):
    if not path.is_file() or path.is_symlink():
        raise IntegrityError("missing_or_unsafe_object")
    if path.stat().st_size != resource["size_bytes"]:
        raise IntegrityError("size_mismatch")
    if sha256_file(path) != resource["sha256"]:
        raise IntegrityError("sha256_mismatch")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, validate, deadline):
        self.validate = validate
        self.deadline = deadline
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 3 or time.monotonic() >= self.deadline:
            raise AcquisitionError("redirect_limit_or_deadline")
        self.validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise AcquisitionError("artifact_deadline")
    return min(30, value)


def stream_download(resource, destination, deadline, validate=approved_url):
    validate(resource["url"])
    opener = urllib.request.build_opener(SafeRedirect(validate, deadline))
    request = urllib.request.Request(
        resource["url"],
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "DetectBridge-datasets/" + TOOL_VERSION,
        },
    )
    digest, total, prefix = hashlib.sha256(), 0, b""
    try:
        with (
            opener.open(request, timeout=remaining(deadline)) as response,
            destination.open("wb") as output,
        ):
            validate(response.geturl())
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise IntegrityError("unsupported_content_encoding")
            declared = response.headers.get("Content-Length")
            if declared is not None and (
                not declared.isdigit() or int(declared) != resource["size_bytes"]
            ):
                raise IntegrityError("declared_size_mismatch")
            while True:
                remaining(deadline)
                # Recompute the socket timeout for every read, not only connection setup.
                raw = getattr(getattr(response, "fp", None), "raw", None)
                sock = getattr(raw, "_sock", None)
                if sock is not None:
                    sock.settimeout(remaining(deadline))
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > resource["size_bytes"] or total > MAX_ARTIFACT:
                    raise IntegrityError("oversized_response")
                prefix = (prefix + chunk)[:512]
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except http.client.IncompleteRead as exc:
        raise IntegrityError("truncated_response") from exc
    if resource.get("role") != "lfs_pointer" and prefix.startswith(
        b"version https://git-lfs.github.com/spec/"
    ):
        raise IntegrityError("lfs_pointer_instead_of_payload")
    if (
        prefix.startswith((b"PK\x03\x04", b"PK\x05\x06", b"\x1f\x8b", b"BZh", b"\xfd7zXZ"))
        or prefix[257:262] == b"ustar"
    ):
        raise IntegrityError("archives_not_supported")
    if total != resource["size_bytes"] or digest.hexdigest() != resource["sha256"]:
        raise IntegrityError("payload_integrity_failure")


def object_path(cache, resource):
    return cache / "objects/sha256" / resource["sha256"]


def acquire(resource, cache, deadline, validate=approved_url):
    final = object_path(cache, resource)
    repaired = False
    if final.exists():
        try:
            verify_file(final, resource)
            return final, "cache_hit"
        except IntegrityError:
            repaired = True
    final.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        descriptor, name = tempfile.mkstemp(prefix=".partial-", dir=final.parent)
        os.close(descriptor)
        temporary = Path(name)
        try:
            stream_download(resource, temporary, deadline, validate)
            if resource.get("record_count") is not None:
                try:
                    framing = inventory(temporary)
                except UnicodeError as exc:
                    raise IntegrityError("invalid_utf8") from exc
                if framing["record_count"] != resource["record_count"]:
                    raise IntegrityError("framing_count_mismatch")
            os.replace(temporary, final)
            return final, "repaired_corrupt_cache" if repaired else "downloaded"
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise AcquisitionError("http_failure") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, socket.timeout) as exc:
            if attempt == 2:
                raise AcquisitionError("transport_failure") from exc
        finally:
            temporary.unlink(missing_ok=True)
        delay = min(2**attempt, remaining(deadline))
        time.sleep(delay)
    raise AcquisitionError("attempts_exhausted")


def check_pointer(path, manifest):
    expected = (
        "version https://git-lfs.github.com/spec/v1\n"
        + "oid sha256:"
        + manifest["payload"]["sha256"]
        + "\n"
        + "size "
        + str(manifest["payload"]["size_bytes"])
        + "\n"
    )
    if path.read_text() != expected:
        raise IntegrityError("pointer_metadata_mismatch")


def process(manifest, cache=CACHE, fetch=False, validate=approved_url, deadline_seconds=120):
    deadline = time.monotonic() + deadline_seconds
    resources = [
        *manifest["provenance"],
        {**manifest["payload"], "record_count": manifest["framing"]["record_count"]},
    ]
    outcomes = []
    for resource in resources:
        if fetch:
            path, outcome = acquire(resource, cache, deadline, validate)
        else:
            path = object_path(cache, resource)
            verify_file(path, resource)
            outcome = "verified"
        outcomes.append(
            {
                "sha256": resource["sha256"],
                "role": resource.get("role", "payload"),
                "outcome": outcome,
            }
        )
        if resource.get("role") == "lfs_pointer":
            check_pointer(path, manifest)
    path = object_path(cache, manifest["payload"])
    try:
        framing = inventory(path)
    except UnicodeError as exc:
        raise IntegrityError("invalid_utf8") from exc
    if framing["record_count"] != manifest["framing"]["record_count"]:
        raise IntegrityError("framing_count_mismatch")
    report = {
        "tool_version": TOOL_VERSION,
        "manifest_id": manifest["id"],
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        "artifact_sha256": manifest["payload"]["sha256"],
        "verified_at": datetime.now(UTC).isoformat(),
        "record_labels": manifest["capture"]["record_labels"],
        "conversion_history": [],
        "provenance": outcomes,
        "framing": framing,
    }
    if fetch:
        folder = cache / "reports"
        folder.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=manifest["id"] + "-", suffix=".partial", dir=folder
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump(report, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, temporary.with_suffix(".json"))
        finally:
            temporary.unlink(missing_ok=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "fetch", "verify"])
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    try:
        catalog = load_catalog(CATALOG)
        if args.command == "list":
            if args.ids or args.all:
                raise AcquisitionError("list_takes_no_selection")
            for ident, manifest in catalog.items():
                print(
                    json.dumps(
                        {
                            "id": ident,
                            "size_bytes": manifest["payload"]["size_bytes"],
                            "record_count": manifest["framing"]["record_count"],
                            "record_labels": "unknown",
                        }
                    )
                )
            return 0
        if args.all and args.ids or not args.all and not args.ids:
            raise AcquisitionError("explicit_selection_required")
        ids = list(catalog) if args.all else list(dict.fromkeys(args.ids))
        if any(ident not in catalog for ident in ids):
            raise AcquisitionError("unknown_catalog_id")
        if (
            sum(
                catalog[i]["payload"]["size_bytes"]
                + sum(p["size_bytes"] for p in catalog[i]["provenance"])
                for i in ids
            )
            > MAX_BATCH
        ):
            raise AcquisitionError("batch_size_limit")
    except (ValueError, OSError, AcquisitionError):
        print(json.dumps({"category": "invalid_catalog_or_selection"}))
        return 1
    failed = False
    for ident in ids:
        try:
            report = process(catalog[ident], fetch=args.command == "fetch")
            print(
                json.dumps(
                    {
                        "id": ident,
                        "status": "verified",
                        "sha256": report["artifact_sha256"],
                        "record_count": report["framing"]["record_count"],
                        "resources": report["provenance"],
                    }
                )
            )
        except (AcquisitionError, OSError, ValueError) as exc:
            failed = True
            category = (
                str(exc)
                if isinstance(exc, AcquisitionError)
                else "local_io_or_configuration_failure"
            )
            print(json.dumps({"id": ident, "status": "failed", "category": category}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
