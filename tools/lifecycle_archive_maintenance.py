"""Managed retirement entry point for archives with the permanent lifecycle hold."""

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def retire(archive: Path, reader: Path, reader_sha256: str, *, java: str = "java") -> int:
    """Run only the independently selected archive reader on its registered format."""
    if not re.fullmatch(r"[a-f0-9]{64}", reader_sha256):
        raise ValueError("archive_reader_identity")
    with os.fdopen(os.open(reader, os.O_RDONLY | os.O_NOFOLLOW), "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 64 * 1024 * 1024:
            raise ValueError("archive_reader_file")
        # Copy exactly the verified bytes into private storage; caller's path may be replaced.
        with tempfile.TemporaryDirectory(prefix="detectbridge-lifecycle-reader-") as temporary:
            pinned = Path(temporary) / "reader.jar"
            sha = hashlib.sha256()
            with pinned.open("xb") as target:
                remaining = info.st_size
                while remaining:
                    chunk = source.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise ValueError("archive_reader_file")
                    remaining -= len(chunk)
                    sha.update(chunk)
                    target.write(chunk)
                if source.read(1) or sha.hexdigest() != reader_sha256:
                    raise ValueError("archive_reader_identity")
            result = subprocess.run(
                [java, "-jar", str(pinned), "retire", str(archive)], check=False
            )
            if result.returncode == 0:
                raise ValueError("lifecycle_hold_unenforced")
            return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--reader-sha256", required=True)
    parser.add_argument("--java", default="java")
    args = parser.parse_args()
    try:
        return retire(args.archive, args.reader, args.reader_sha256, java=args.java)
    except (OSError, ValueError) as exc:
        print(
            str(exc) if isinstance(exc, ValueError) else "lifecycle_maintenance_io", file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
