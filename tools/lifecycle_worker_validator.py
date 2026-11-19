"""Fixed local worker-initiated recompilation service; no per-event Python."""

import base64
import hashlib
import json
import os
import resource
import signal
import socket
import stat
import struct
import sys
import tarfile
import time
import uuid
from pathlib import Path

from check_contracts import StrictValidator, load_json
from jsonschema import FormatChecker
from lifecycle_validation import decode, encoded, validate_plan

ROOT = Path(__file__).resolve().parents[1]
MIB = 1048576
DEFINITIONS = load_json(ROOT / "contracts/lifecycle-runtime/v1/common.schema.json")["$defs"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition):
    if not condition:
        raise ValueError("validator_invalid_request")


def schema(name, value):
    require(
        not list(
            StrictValidator(DEFINITIONS[name], format_checker=FormatChecker()).iter_errors(value)
        )
    )


def verify_install(root, artifact_sha256):
    root = Path(root)
    archive = root / "artifact.tar"
    require(not archive.is_symlink() and archive.stat().st_size <= 8 * MIB)
    require(sha(archive.read_bytes()) == artifact_sha256)
    with tarfile.open(archive) as packet:
        members = packet.getmembers()
        require(0 < len(members) <= 257 and all(item.isfile() for item in members))
        require(len({item.name for item in members}) == len(members))
        source = packet.extractfile("validator-manifest.json")
        require(source is not None)
        assert source is not None
        manifest_bytes = source.read(65537)
        require(len(manifest_bytes) <= 65536)
    require((root / "validator-manifest.json").read_bytes() == manifest_bytes)
    manifest = decode(manifest_bytes)
    require(set(manifest) == {"version", "base_image", "files"} and manifest["version"] == "1.0.0")
    require(0 < len(manifest["files"]) <= 256)
    for name, expected in manifest["files"].items():
        require(isinstance(name, str) and not name.startswith("/") and ".." not in Path(name).parts)
        path = root / name
        require(all(not parent.is_symlink() for parent in path.parents if parent != root.parent))
        require(not path.is_symlink() and path.is_file() and set(expected) == {"sha256", "bytes"})
        data = path.read_bytes()
        require(len(data) == expected["bytes"] and sha(data) == expected["sha256"])
    return manifest


def validate_request(request, descriptor):
    schema("validator", descriptor)
    schema("validator_request", request)
    require(str(uuid.UUID(request["nonce"])) == request["nonce"])
    binding = sha(encoded(descriptor))
    require(request["validator_binding_sha256"] == binding)
    plan = base64.b64decode(request["plan_base64"], validate=True)
    require(
        0 < len(plan) <= 4 * MIB
        and base64.b64encode(plan).decode() == request["plan_base64"]
        and sha(plan) == request["plan_sha256"]
    )
    response = {
        key: request[key] for key in ("version", "nonce", "plan_sha256", "validator_binding_sha256")
    }
    try:
        validate_plan(plan)
    except TimeoutError:
        response.update(passed=False, category="validation_timeout")
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        response.update(passed=False, category="compiler_rejected")
    except Exception:
        response.update(passed=False, category="validation_failed")
    else:
        response.update(passed=True, category="ok")
    schema("validator_response", response)
    return response


def receive(connection, count, deadline):
    result = bytearray()
    while len(result) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("validator_deadline")
        connection.settimeout(remaining)
        block = connection.recv(count - len(result))
        require(block)
        result.extend(block)
    return bytes(result)


def exchange(connection, descriptor):
    deadline = time.monotonic() + 10
    size = struct.unpack("!I", receive(connection, 4, deadline))[0]
    require(0 < size <= 8 * MIB)
    request = decode(receive(connection, size, deadline))
    response = encoded(validate_request(request, descriptor))
    require(len(response) <= 65536)
    connection.settimeout(max(0.001, deadline - time.monotonic()))
    connection.sendall(struct.pack("!I", len(response)) + response)


def timeout(_number, _frame):
    raise TimeoutError("validator_deadline")


def serve():
    require(sys.version_info[:3] == (3, 12, 12))
    descriptor = dict(
        version="1.0.0",
        artifact_sha256=os.environ["DETECTBRIDGE_VALIDATOR_ARTIFACT"],
        image_id=os.environ["DETECTBRIDGE_VALIDATOR_IMAGE_ID"],
        base_image=os.environ["DETECTBRIDGE_VALIDATOR_BASE_IMAGE"],
    )
    schema("validator", descriptor)
    manifest = verify_install(ROOT, descriptor["artifact_sha256"])
    require(manifest["base_image"] == descriptor["base_image"])
    require(os.environ["DETECTBRIDGE_VALIDATOR_SOCKET"] == "/validation/compiler.sock")
    path = Path("/validation/compiler.sock")
    info = path.parent.lstat()
    require(
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o700
    )
    if path.exists() or path.is_symlink():
        old = path.lstat()
        require(
            stat.S_ISSOCK(old.st_mode)
            and old.st_uid == os.getuid()
            and stat.S_IMODE(old.st_mode) == 0o600
        )
        path.unlink()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_AS, (384 * MIB, 384 * MIB))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.signal(signal.SIGALRM, timeout)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(path))
        path.chmod(0o600)
        server.listen(1)
        while True:
            connection, _ = server.accept()
            with connection:
                signal.setitimer(signal.ITIMER_REAL, 10)
                try:
                    exchange(connection, descriptor)
                except Exception:
                    # Invalid requests and timeouts close the connection; no input or exception is logged.
                    pass
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)


def main():
    try:
        serve()
    except Exception:
        print(json.dumps(dict(category="validator_startup_failed")), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
