"""Component-test UDS peer using the unchanged real compiler, not a passing oracle."""
import base64
import hashlib
import json
import os
import socket
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(root / "tools"))
from lifecycle_validation import validate_plan

os.umask(0o077)
address = Path(sys.argv[1])
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(str(address))
os.chmod(address, 0o600)
server.listen(1)
address.with_name(address.name + ".ready").write_bytes(b"ready")


def exact(connection, size):
    result = bytearray()
    while len(result) < size:
        part = connection.recv(size - len(result))
        if not part:
            raise ValueError("framing")
        result.extend(part)
    return bytes(result)


while True:
    connection, _ = server.accept()
    with connection:
        connection.settimeout(10)
        size = struct.unpack("!I", exact(connection, 4))[0]
        if not 0 < size <= 8 * 1024 * 1024:
            continue
        request = json.loads(exact(connection, size))
        plan = base64.b64decode(request["plan_base64"], validate=True)
        response = {key: request[key] for key in ("version", "nonce", "plan_sha256", "validator_binding_sha256")}
        try:
            if hashlib.sha256(plan).hexdigest() != request["plan_sha256"]:
                raise ValueError("hash")
            validate_plan(plan)
            response.update(passed=True, category="ok")
        except ValueError:
            response.update(passed=False, category="compiler_rejected")
        data = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
        connection.sendall(struct.pack("!I", len(data)) + data)
