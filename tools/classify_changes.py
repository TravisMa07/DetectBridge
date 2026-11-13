"""Classify paths; unknown non-documentation changes require toolchain verification."""

import os
import subprocess


def needs_toolchains(paths):
    return any(not (p.endswith(".md") or p == "LICENSE") for p in paths)


def needs_stack(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "tools/toolchains.json",
        "tools/dev.py",
        "tools/check_gate.py",
        "tools/classify_changes.py",
        "tools/tests/test_hygiene.py",
        "tools/tests/test_development.py",
    }
    return any(
        p in shared
        or p.startswith(
            (
                "deploy/",
                ".github/workflows/",
                "tools/stack",
                "tools/check_stack",
                "tools/tests/test_stack",
            )
        )
        for p in paths
        if not p.endswith(".md")
    )


def needs_transport(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "gradlew",
        "gradlew.bat",
        "build.gradle.kts",
        "gradle.properties",
        "tools/dev.py",
        "tools/toolchains.json",
        "tools/check_gate.py",
        "tools/classify_changes.py",
        "tools/stack.py",
        "tools/replay.py",
        "tools/datasets.py",
        "tools/check_datasets.py",
        "tools/check_contracts.py",
        "tools/check_replay.py",
        "tools/dependency_inventory.py",
    }
    return any(
        p in shared
        or p.startswith(
            (
                "packages/transport-",
                "gradle/",
                "contracts/v1/",
                "contracts/replay/",
                "contracts/transport/",
                "catalog/datasets/",
                "tools/transport",
                "tools/check_transport",
                "tools/tests/test_transport",
                "deploy/local/",
                ".github/workflows/",
            )
        )
        for p in paths
        if not (p.endswith(".md") or p == "LICENSE")
    )


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
        output.write(f"stack={str(needs_stack([p for p in paths if p])).lower()}\n")
        output.write(f"transport={str(needs_transport([p for p in paths if p])).lower()}\n")
