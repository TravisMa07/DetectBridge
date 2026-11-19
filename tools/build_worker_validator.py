"""Build the pinned first-party worker compiler packet and native platform image."""

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "deploy/lifecycle-validator/images.lock.json").read_bytes())["base_image"]
SOURCES = (
    "lifecycle_worker_validator.py",
    "lifecycle_validation.py",
    "detection_compile.py",
    "detection_mapping.py",
    "check_contracts.py",
    "contract_identity.py",
)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_requirements():
    exported = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--only-group",
            "dev",
            "--no-emit-project",
            "--no-annotate",
            "--prune",
            "ruff",
            "--prune",
            "mypy",
            "--prune",
            "types-jsonschema",
            "--format",
            "requirements-txt",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=30,
        text=True,
    ).stdout

    def body(text):
        return [line for line in text.splitlines() if line.strip() and not line.startswith("#")]

    if body(exported) != body((ROOT / "deploy/lifecycle-validator/requirements.txt").read_text()):
        raise ValueError("validator_requirements_lock_mismatch")


def packet(destination):
    """Exact content identity, independent of source timestamps, paths and Git dirtiness."""
    destination = Path(destination)
    check_requirements()
    paths = [ROOT / "tools" / name for name in SOURCES]
    paths += sorted((ROOT / "contracts").rglob("*.schema.json"))
    paths += [
        ROOT / "deploy/lifecycle-validator" / name
        for name in ("Dockerfile", "requirements.txt", "images.lock.json")
    ]
    paths += [ROOT / "uv.lock", ROOT / "LICENSE"]
    files = {str(path.relative_to(ROOT)): path.read_bytes() for path in paths}
    manifest = dict(
        version="1.0.0",
        base_image=BASE,
        files={
            name: dict(sha256=sha(data), bytes=len(data)) for name, data in sorted(files.items())
        },
    )
    files["validator-manifest.json"] = encoded(manifest)
    with tarfile.open(destination, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o444, 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    destination.chmod(0o600)
    if destination.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("validator_packet_limit")
    return sha(destination.read_bytes())


def build(folder):
    folder = Path(folder).absolute()
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    artifact = folder / "artifact.tar"
    digest = packet(artifact)
    with tarfile.open(artifact) as archive:
        dockerfile = archive.extractfile("deploy/lifecycle-validator/Dockerfile")
        assert dockerfile is not None
        (folder / "Dockerfile").write_bytes(dockerfile.read())
    (folder / ".dockerignore").write_text("*\n!Dockerfile\n!artifact.tar\n")
    architecture = subprocess.run(
        ["docker", "info", "--format", "{{.Architecture}}"],
        capture_output=True,
        check=True,
        timeout=30,
        text=True,
    ).stdout.strip()
    platform = {
        "arm64": "linux/arm64",
        "aarch64": "linux/arm64",
        "x86_64": "linux/amd64",
        "amd64": "linux/amd64",
    }.get(architecture)
    if platform is None:
        raise ValueError("validator_platform")
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DOCKER_DEFAULT_PLATFORM", "BUILDX_CONFIG"}
    }
    with (folder / "build.log").open("wb") as log:
        result = subprocess.run(
            [
                "docker",
                "build",
                "--platform",
                platform,
                "--iidfile",
                str(folder / "image-id"),
                "--build-arg",
                "VALIDATOR_ARTIFACT=" + digest,
                "--tag",
                "detectbridge-validator:" + digest[:20],
                str(folder),
            ],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
        )
    if result.returncode:
        raise ValueError("validator_image_build_failed")
    image_id = (folder / "image-id").read_text().strip()
    info = json.loads(
        subprocess.run(
            ["docker", "image", "inspect", image_id],
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
    )[0]
    labels = info["Config"].get("Labels", {})
    if not (
        info["Id"] == image_id
        and labels.get("io.detectbridge.p15b.validator.artifact") == digest
        and labels.get("io.detectbridge.p15b.validator.base") == BASE
    ):
        raise ValueError("validator_image_identity")
    descriptor = dict(version="1.0.0", artifact_sha256=digest, image_id=image_id, base_image=BASE)
    (folder / "descriptor.json").write_bytes(encoded(descriptor))
    name = "detectbridge-validator-check-" + uuid.uuid4().hex
    try:
        with (folder / "packet-check.log").open("wb") as log:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "--network",
                    "none",
                    "--read-only",
                    "--user",
                    "9999:9999",
                    "--memory",
                    "512m",
                    "--cpus",
                    "1",
                    "--pids-limit",
                    "64",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--label",
                    "io.detectbridge.p15b.validator.artifact=" + digest,
                    "--entrypoint",
                    "python",
                    image_id,
                    "-c",
                    "import sys;sys.path.insert(0,'/opt/validator/tools');"
                    "from lifecycle_worker_validator import ROOT,verify_install;"
                    "verify_install(ROOT,sys.argv[1])",
                    digest,
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=30,
            )
        if result.returncode:
            raise ValueError("validator_installed_packet_check_failed")
    finally:
        remaining = subprocess.run(
            ["docker", "inspect", name], capture_output=True, timeout=10, check=False
        )
        if remaining.returncode == 0:
            owned = json.loads(remaining.stdout)[0]
            if (
                owned["Config"].get("Labels", {}).get("io.detectbridge.p15b.validator.artifact")
                != digest
            ):
                raise ValueError("validator_packet_check_foreign_container")
            subprocess.run(
                ["docker", "rm", "--force", owned["Id"]],
                capture_output=True,
                check=True,
                timeout=20,
            )
    return dict(artifact=artifact, descriptor=descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    result = build(args.folder)
    print(encoded({**result, "artifact": str(result["artifact"])}).decode())


if __name__ == "__main__":
    main()
