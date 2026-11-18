"""Actual deployed Log4j privacy/throw-location regression, without new dependencies."""

import json
import shutil
import tempfile
from pathlib import Path

from stack import DEPLOY, ROOT, StackError, run, save


def check_logging(image):
    # Compile original test code using only the pinned JDK API. Reflection loads
    # the actual pinned image's logging backend, rather than a test substitute.
    parent = ROOT / ".cache/integration-logging"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as name:
        folder = Path(name)
        folder.chmod(0o755)
        run(
            [
                ROOT / ".cache/jdk/bin/javac",
                "-encoding",
                "UTF-8",
                "-d",
                folder,
                ROOT / "packages/integration-job/fixtures/LoggingProbe.java",
            ]
        )
        shutil.copyfile(DEPLOY / "integration-log4j.properties", folder / "logger.properties")
        for file in folder.iterdir():
            file.chmod(0o644)
        result = run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--hostname",
                "localhost",
                "--entrypoint",
                "java",
                "--memory",
                "256m",
                "--cpus",
                "0.5",
                "--pids-limit",
                "64",
                "--user",
                "9999:9999",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--volume",
                str(folder.resolve()) + ":/probe:ro",
                image,
                "-XX:ActiveProcessorCount=1",
                "-Xmx128m",
                "-Dlog4j.configurationFile=file:/probe/logger.properties",
                "-cp",
                "/opt/flink/lib/*:/probe",
                "LoggingProbe",
            ],
            timeout=90,
        )
        save(
            parent / (folder.name + "-probe.json"),
            dict(image=image, stdout=result.stdout, stderr=result.stderr),
        )
        if (
            "private-body-sentinel" in result.stdout + result.stderr
            or "secret" in result.stdout + result.stderr
        ):
            raise StackError("integration_logging_payload_leak")
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        if len(rows) != 6 or any(
            set(row)
            != {
                "level",
                "logger",
                "category",
                "throw_class",
                "throw_method",
                "throw_line",
                "root_oom",
            }
            for row in rows
        ):
            raise StackError("integration_logging_shape_mismatch")
        if any(
            row["level"] != "ERROR"
            or row["logger"] != "detectbridge.logging.probe"
            or row["category"] != "runtime_log"
            for row in rows
        ):
            raise StackError("integration_logging_metadata_mismatch")
        if any(
            row[field] != ""
            for row in (rows[0], rows[-1])
            for field in ("throw_class", "throw_method", "throw_line", "root_oom")
        ):
            raise StackError("integration_logging_missing_exception_mismatch")
        if any(
            row["throw_class"] != "LoggingProbe"
            or row["throw_method"] not in ("failure", "oomFailure")
            or not row["throw_line"].isdigit()
            for row in rows[1:-1]
        ):
            raise StackError("integration_logging_throw_location_mismatch")
        if [row["root_oom"] for row in rows] != ["", "", "", "true", "true", ""]:
            raise StackError("integration_logging_oom_marker_mismatch")
    print(
        "PASS: actual integration runtime logger retains throw locations without messages or exception bodies"
    )
