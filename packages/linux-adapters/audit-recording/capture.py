"""Capture native auditd output from a disposable emulated kernel, never the host kernel."""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = {
    "boot-id",
    "cmdline",
    "kernel-version",
    "setup",
    "rules",
    "status-before",
    "status-after",
    "action-exit",
    "action.stdout",
    "auditd.stderr",
    "audit.native",
}


def command(args, *, timeout=180):
    return subprocess.run(args, check=True, capture_output=True, timeout=timeout).stdout


def extract(serial):
    """Decode only framed base64 artifacts, retaining the unchanged serial separately."""
    text = serial.replace(b"\r\n", b"\n")
    matches = list(
        re.finditer(
            rb"^DB_ARTIFACT_BEGIN:([a-z.-]+):([a-f0-9]{64})\n(.*?)^DB_ARTIFACT_END:\1(?:\n|$)",
            text,
            re.S | re.M,
        )
    )
    result = {}
    for match in matches:
        name = match[1].decode()
        if name not in NAMES or name in result:
            raise ValueError("guest_artifact_name")
        data = base64.b64decode(b"".join(match[3].split()), validate=True)
        if hashlib.sha256(data).hexdigest().encode() != match[2]:
            raise ValueError("guest_artifact_hash")
        result[name] = data
    if set(result) != NAMES or text.count(b"DB_CAPTURE_EXIT:0\n") != 1:
        raise ValueError("guest_capture_incomplete")
    return result


def capture(image, destination):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("immutable_image_required")
    destination.mkdir(parents=True, exist_ok=False)
    name = "detectbridge-audit-capture-" + uuid.uuid4().hex[:12]
    container = (
        command(
            [
                "docker",
                "create",
                "--name",
                name,
                "--network",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=16m",
                image,
            ]
        )
        .decode()
        .strip()
    )
    try:
        started = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        serial = command(["docker", "start", "--attach", container])
        (destination / "guest.serial").write_bytes(serial)
        for target, data in extract(serial).items():
            (destination / target).write_bytes(data)
        for target in (
            "kernel",
            "kernel.config",
            "guest.cpio.gz",
            "packages.txt",
            "copyrights.tar.gz",
            "binaries.sha256",
        ):
            command(["docker", "cp", container + ":/capture/" + target, str(destination / target)])
        (destination / "container.json").write_bytes(command(["docker", "inspect", container]))
        (destination / "image.json").write_bytes(command(["docker", "image", "inspect", image]))
        for target in (
            "expectations.json",
            "probe.c",
            "guest-init",
            "Dockerfile",
            "build-initramfs.py",
            "capture.py",
        ):
            (destination / target).write_bytes((HERE / target).read_bytes())
        manifest = dict(
            version="1.0.0",
            status="unreviewed-capture",
            image_id=image,
            container_id=container,
            capture_started=started,
            first_observed=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            completed=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            artifacts=[
                dict(
                    filename=path.name,
                    size_bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in sorted(destination.iterdir())
                if path.is_file()
            ],
        )
        (destination / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return dict(status="captured_unreviewed", artifacts=len(manifest["artifacts"]))
    finally:
        command(["docker", "rm", "--force", container])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(capture(args.image, args.destination)))
    except Exception:
        print('{"status":"failed","category":"isolated_audit_capture_failed"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
