"""Qualify P15a with the exact retained Java artifact and independent synthetic cases."""

import json
import os
import platform
import subprocess
import unittest

from lifecycle_validation import LOGGING_PIN, PIN, ROOT, encoded, sha, verify_artifact
from transport import java_env


def main():
    folder = ROOT / ".cache/lifecycle-qualification"
    folder.mkdir(parents=True, exist_ok=True)
    report = dict(
        version="1.0.0",
        status="failed",
        platform=platform.platform(),
        source_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        tracked_dirty=bool(
            subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=ROOT)
        ),
        evaluator_sha256=PIN,
        logging_api_sha256=LOGGING_PIN,
        source_sha256={
            name: sha((ROOT / name).read_bytes())
            for name in (
                "tools/lifecycle.py",
                "tools/lifecycle_validation.py",
                "tools/lifecycle_verify.py",
                "tools/tests/test_lifecycle.py",
                "tools/tests/test_lifecycle_gate.py",
                "contracts/lifecycle/v1/fixtures/cases.json",
                "contracts/lifecycle/v1/fixtures/rule.yml",
            )
        },
        phase="build",
        limits="P15a synthetic candidate preparation only; no worker runtime or throughput",
    )
    try:
        with (folder / "build.log").open("wb") as log:
            subprocess.run(
                [
                    ROOT / "gradlew",
                    "--offline",
                    "--console=plain",
                    ":integration-job:test",
                    ":integration-job:shadowJar",
                ],
                cwd=ROOT,
                env=java_env(),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=600,
                check=True,
            )
        verify_artifact(ROOT / "packages/integration-job/build/libs/integration-job.jar")
        report["phase"] = "tests"
        os.environ["DETECTBRIDGE_LIFECYCLE_REQUIRED"] = "1"
        suite = unittest.defaultTestLoader.discover(
            str(ROOT / "tools/tests"), pattern="test_lifecycle*.py"
        )
        with (folder / "tests.log").open("w") as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        from test_lifecycle import LifecycleTests

        if hasattr(LifecycleTests, "plan_bytes"):
            report.update(
                plan_sha256=sha(LifecycleTests.plan_bytes),
                bundle_sha256=LifecycleTests.manifest["bundle_sha256"],
                compatibility_sha256=LifecycleTests.manifest["compatibility_sha256"],
            )
        report.update(
            tests=result.testsRun,
            failures=len(result.failures),
            errors=len(result.errors),
            skipped=len(result.skipped),
        )
        if result.wasSuccessful() and result.testsRun > 0 and not result.skipped:
            report.update(status="passed", phase="complete")
    except Exception as error:
        report["exception_class"] = type(error).__name__
    for name in ("build.log", "tests.log"):
        path = folder / name
        if path.exists():
            report[name + "_sha256"] = sha(path.read_bytes())
    (folder / "summary.json").write_bytes(encoded(report) + b"\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
