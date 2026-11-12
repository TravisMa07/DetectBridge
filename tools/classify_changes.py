"""Classify paths; unknown non-documentation changes require toolchain verification."""

import os
import subprocess


def needs_toolchains(paths):
    return any(not (p.endswith(".md") or p == "LICENSE") for p in paths)


if __name__ == "__main__":
    base = os.environ.get("CHANGE_BASE", "")
    head = os.environ.get("CHANGE_HEAD", "HEAD")
    if not base or set(base) == {"0"}:
        paths = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    else:
        paths = (
            subprocess.check_output(["git", "diff", "--name-only", "-z", base, head])
            .decode()
            .split("\0")
        )
    value = str(needs_toolchains([p for p in paths if p])).lower()
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"toolchains={value}\n")
