"""Install checksum-verified native tools into ignored .cache/hygiene/bin."""

import argparse
import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", choices=("actionlint", "gitleaks"), action="append")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "tools/hygiene/downloads.json").read_text())
    target = f"{platform.system()}-{platform.machine()}"
    dest = ROOT / ".cache/hygiene/bin"
    dest.mkdir(parents=True, exist_ok=True)
    for tool in args.tool or manifest:
        if target not in manifest[tool]:
            raise SystemExit(f"Unsupported hygiene platform: {target}")
        asset = manifest[tool][target]
        request = urllib.request.Request(
            asset["url"], headers={"User-Agent": "DetectBridge-hygiene"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            archive = response.read()
        if hashlib.sha256(archive).hexdigest() != asset["sha256"]:
            raise SystemExit(f"{tool}: checksum mismatch")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name in (tool, "./" + tool) and m.isfile()]
            if len(members) != 1:
                raise SystemExit(f"{tool}: expected exactly one executable")
            stream = tar.extractfile(members[0])
            if stream is None:
                raise RuntimeError("Missing executable archive member")
            data = stream.read()
        path = dest / tool
        path.write_bytes(data)
        path.chmod(0o755)
        print(f"Installed checksum-verified {tool} for {target}")


if __name__ == "__main__":
    main()
