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


def needs_writer(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "tools/toolchains.json",
        "tools/dev.py",
        "tools/stack.py",
        "tools/transport.py",
        "tools/replay.py",
        "tools/datasets.py",
        "tools/check_datasets.py",
        "tools/check_contracts.py",
        "tools/check_replay.py",
        "tools/check_transport.py",
        "tools/check_gate.py",
        "tools/classify_changes.py",
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
                "contracts/writer/",
                "catalog/datasets/",
                "tools/writer",
                "tools/check_writer",
                "tools/tests/test_writer",
                "deploy/local/",
                ".github/workflows/",
            )
        )
        for p in paths
        if not (p.endswith(".md") or p == "LICENSE")
    )


def needs_detection(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "tools/dev.py",
        "tools/toolchains.json",
        "tools/check_gate.py",
        "tools/classify_changes.py",
        "tools/stack.py",
        "tools/transport.py",
        "tools/check_contracts.py",
        "tools/dependency_inventory.py",
    }
    return any(
        p in shared
        or p.startswith(
            (
                "packages/detection-",
                "packages/transport-contracts/",
                "contracts/v1/",
                "contracts/detection/",
                "contracts/integration/",
                "gradle/",
                "deploy/local/",
                ".github/workflows/",
                "tools/detection",
                "tools/check_detection",
                "tools/check_mapping",
                "tools/tests/test_detection",
                "tools/tests/test_mapping",
            )
        )
        for p in paths
        if not (p.endswith(".md") or p == "LICENSE")
    )


def needs_windows(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "tools/dev.py",
        "tools/toolchains.json",
        "tools/check_gate.py",
        "tools/classify_changes.py",
        "tools/dependency_inventory.py",
        "tools/check_contracts.py",
        "tools/datasets.py",
        "docs/windows-dependencies.json",
        "docs/transport-dependencies.json",
    }
    return any(
        (
            p in shared
            or p.startswith(
                (
                    "packages/windows-adapters/",
                    "packages/detection-evaluator/",
                    "packages/transport-contracts/",
                    "contracts/v1/",
                    "contracts/detection/",
                    "contracts/integration/",
                    "catalog/datasets/",
                    "gradle/",
                    ".github/workflows/",
                    "tools/detection_compile",
                    "tools/detection_mapping",
                    "tools/check_windows",
                    "tools/tests/test_windows",
                )
            )
        )
        for p in paths
        if not (p.endswith(".md") or p == "LICENSE")
    )


def needs_linux(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "tools/dev.py",
        "tools/toolchains.json",
        "tools/check_gate.py",
        "tools/classify_changes.py",
        "tools/dependency_inventory.py",
        "tools/check_contracts.py",
        "tools/datasets.py",
        "docs/linux-dependencies.json",
        "docs/transport-dependencies.json",
    }
    return any(
        (
            p in shared
            or p.startswith(
                (
                    "packages/linux-adapters/",
                    "packages/detection-evaluator/",
                    "packages/transport-contracts/",
                    "contracts/v1/",
                    "contracts/detection/",
                    "contracts/integration/",
                    "catalog/datasets/",
                    "catalog/recordings/",
                    "gradle/",
                    ".github/workflows/",
                    "tools/detection_compile",
                    "tools/detection_mapping",
                    "tools/check_linux",
                    "tools/tests/test_linux",
                )
            )
        )
        for p in paths
        if not (p.endswith(".md") or p == "LICENSE")
    )


def needs_assembly(paths):
    shared = {
        "pyproject.toml",
        "uv.lock",
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "tools/dev.py",
        "tools/toolchains.json",
        "tools/check_gate.py",
        "tools/classify_changes.py",
        "tools/dependency_inventory.py",
        "tools/check_contracts.py",
        "tools/datasets.py",
        "docs/assembly-dependencies.json",
        "docs/transport-dependencies.json",
    }
    return any(
        (
            p in shared
            or p.startswith(
                (
                    "packages/linux-adapters/",
                    "packages/linux-assembly-job/",
                    "contracts/linux-assembly/",
                    "deploy/local/",
                    "tools/linux_assembly",
                    "packages/detection-evaluator/",
                    "packages/transport-contracts/",
                    "contracts/v1/",
                    "contracts/detection/",
                    "contracts/integration/",
                    "catalog/datasets/",
                    "catalog/recordings/",
                    "gradle/",
                    ".github/workflows/",
                    "tools/detection_compile",
                    "tools/detection_mapping",
                    "tools/check_assembly",
                    "tools/tests/test_linux_assembly",
                    "tools/tests/test_assembly_gate",
                )
            )
        )
        for p in paths
        if not (p.endswith(".md") or p == "LICENSE")
    )


def needs_integration(paths):
    return (
        needs_assembly(paths)
        or needs_windows(paths)
        or any(
            p.startswith(
                (
                    "packages/integration-job/",
                    "deploy/local/integration",
                    "contracts/integration-runtime/",
                    "contracts/integration/",
                    "tools/integration",
                    "tools/check_integration",
                    "tools/tests/test_integration",
                )
            )
            for p in paths
            if not p.endswith(".md")
        )
    )


def needs_search(paths):
    return (
        needs_integration(paths)
        or needs_writer(paths)
        or any(
            p.startswith(
                (
                    "packages/integration-writer/",
                    "contracts/search-writer/",
                    "tools/search_writer",
                    "tools/check_search_writer",
                    "tools/tests/test_search_writer",
                )
            )
            for p in paths
            if not p.endswith(".md")
        )
    )


def needs_archive(paths):
    shared = {
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradlew",
        "gradlew.bat",
        "gradle.properties",
        "tools/dev.py",
        "tools/stack.py",
        "tools/integration.py",
        "tools/search_writer.py",
        "tools/toolchains.json",
        "pyproject.toml",
        "uv.lock",
        "tools/classify_changes.py",
        "tools/check_gate.py",
        "tools/dependency_inventory.py",
        "docs/transport-dependencies.json",
    }
    return any(
        p in shared
        or p.startswith(
            (
                "packages/archive-writer/",
                "packages/integration-job/",
                "packages/integration-writer/",
                "packages/transport-contracts/",
                "contracts/archive/",
                "contracts/v1/",
                "contracts/integration-runtime/",
                "contracts/integration/",
                "tools/archive",
                "tools/check_archive",
                "tools/tests/test_archive",
                "gradle/",
                "deploy/local/",
                ".github/workflows/",
            )
        )
        for p in paths
        if not p.endswith(".md")
    )


def needs_historical(paths):
    shared = {
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradlew",
        "gradlew.bat",
        "gradle.properties",
        "tools/dev.py",
        "tools/stack.py",
        "tools/integration.py",
        "tools/archive.py",
        "tools/toolchains.json",
        "pyproject.toml",
        "uv.lock",
        "tools/classify_changes.py",
        "tools/check_gate.py",
        "tools/dependency_inventory.py",
        "docs/transport-dependencies.json",
    }
    prefixes = (
        "packages/historical-replay/",
        "packages/archive-writer/",
        "packages/integration-job/",
        "packages/linux-adapters/",
        "packages/windows-adapters/",
        "packages/detection-evaluator/",
        "packages/transport-contracts/",
        "contracts/",
        "tools/historical",
        "tools/check_historical",
        "tools/tests/test_historical",
        "tools/integration_oracle",
        "tools/integration_cases",
        "tools/linux_assembly",
        "gradle/",
        "deploy/local/",
        ".github/workflows/",
    )
    return any(p in shared or p.startswith(prefixes) for p in paths if not p.endswith(".md"))


def needs_current(paths):
    shared = {
        "settings.gradle.kts",
        "settings-gradle.lockfile",
        "build.gradle.kts",
        "gradlew",
        "gradlew.bat",
        "gradle.properties",
        "tools/dev.py",
        "tools/stack.py",
        "tools/integration.py",
        "tools/archive.py",
        "tools/check_contracts.py",
        "tools/check_integration.py",
        "tools/transport.py",
        "tools/toolchains.json",
        "pyproject.toml",
        "uv.lock",
        "tools/classify_changes.py",
        "tools/check_gate.py",
        "tools/dependency_inventory.py",
        "docs/transport-dependencies.json",
    }
    prefixes = (
        "packages/current-replay/",
        "packages/historical-replay/",
        "packages/archive-writer/",
        "packages/integration-job/",
        "packages/linux-adapters/",
        "packages/windows-adapters/",
        "packages/detection-evaluator/",
        "packages/transport-contracts/",
        "contracts/",
        "tools/detection",
        "tools/check_detection",
        "tools/check_mapping",
        "tools/current_replay",
        "tools/check_current_replay",
        "tools/tests/test_current",
        "tools/historical",
        "tools/check_historical",
        "tools/tests/test_historical",
        "tools/integration_oracle",
        "tools/integration_cases",
        "tools/linux_assembly",
        "gradle/",
        "deploy/local/",
        ".github/workflows/",
    )
    return any(p in shared or p.startswith(prefixes) for p in paths if not p.endswith(".md"))


def needs_maintenance(paths):
    direct = {
        "tools/archive_profiles.py",
        "tools/replay.py",
        "tools/replay_time.py",
        "tools/check_replay.py",
        "tools/datasets.py",
        "tools/check_datasets.py",
        "tools/contract_identity.py",
    }
    prefixes = (
        "packages/archive-maintenance/",
        "catalog/datasets/",
        "tools/archive_maintenance",
        "tools/check_archive_maintenance",
        "tools/managed_replay",
        "tools/p05_archive",
        "tools/tests/test_maintenance",
        "tools/tests/test_archive_maintenance",
        "tools/tests/test_managed_replay",
        "tools/tests/test_p05_archive",
    )
    return needs_current(paths) or any(
        p in direct or p.startswith(prefixes) for p in paths if not p.endswith(".md")
    )


def needs_lifecycle(paths):
    return needs_integration(paths) or any(
        p.startswith(("contracts/lifecycle/", "tools/lifecycle", "tools/tests/test_lifecycle"))
        for p in paths
        if not p.endswith(".md")
    )


def needs_activation(paths):
    return needs_lifecycle(paths) or any(
        p.startswith(
            (
                "packages/lifecycle-job/",
                "contracts/lifecycle-runtime/",
                "tools/lifecycle_runtime",
                "tools/lifecycle_diagnostics",
                "tools/lifecycle_ack_backlog",
                "tools/tests/test_lifecycle_ack_backlog",
                "tools/tests/test_lifecycle_diagnostics",
                "tools/check_lifecycle_runtime",
                "tools/tests/test_lifecycle_runtime",
                "tools/tests/test_activation",
                "tools/build_worker_validator",
                "tools/lifecycle_worker_validator",
                "tools/tests/test_worker_validator",
                "deploy/lifecycle-validator/",
            )
        )
        for p in paths
        if not p.endswith(".md")
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
        output.write(f"detection={str(needs_detection([p for p in paths if p])).lower()}\n")
        output.write(f"stack={str(needs_stack([p for p in paths if p])).lower()}\n")
        output.write(f"transport={str(needs_transport([p for p in paths if p])).lower()}\n")
        output.write(f"writer={str(needs_writer([p for p in paths if p])).lower()}\n")
        output.write(f"integration={str(needs_integration([p for p in paths if p])).lower()}\n")
        output.write(f"historical={str(needs_historical([p for p in paths if p])).lower()}\n")
        output.write(f"activation={str(needs_activation([p for p in paths if p])).lower()}\n")
        output.write(f"lifecycle={str(needs_lifecycle([p for p in paths if p])).lower()}\n")
        output.write(f"maintenance={str(needs_maintenance([p for p in paths if p])).lower()}\n")
        output.write(f"current={str(needs_current([p for p in paths if p])).lower()}\n")
        output.write(f"archive={str(needs_archive([p for p in paths if p])).lower()}\n")
        output.write(f"search={str(needs_search([p for p in paths if p])).lower()}\n")
        output.write(f"assembly={str(needs_assembly([p for p in paths if p])).lower()}\n")
        output.write(f"linux={str(needs_linux([p for p in paths if p])).lower()}\n")
        output.write(f"windows={str(needs_windows([p for p in paths if p])).lower()}\n")
