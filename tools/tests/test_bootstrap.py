"""Observed setup failures recover narrowly; build/test failures remain failures."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dev

HTTP_429 = (
    "Could not resolve all artifacts for configuration 'classpath'.\n"
    "> Could not GET 'https://repo.maven.apache.org/maven2/org/example/lib/1/lib-1.pom'.\n"
    "> Received status code 429 from server: Too Many Requests\n"
)


class BootstrapTests(unittest.TestCase):
    def invoke(self, folder, outcomes, failure=False, smoke_error=None):
        calls = []

        def run(args, **kwargs):
            if args[-1] == "help":
                calls.append(list(args))
                code, output, *errors = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
                stderr = errors[0] if errors else ""
                if code and kwargs.get("check", True):
                    raise subprocess.CalledProcessError(code, args, output=output)
                return subprocess.CompletedProcess(args, code, stdout=output, stderr=stderr)
            return subprocess.CompletedProcess(args, 0, stdout="uv " + dev.PINS["uv"], stderr="")

        with (
            patch.object(dev, "ROOT", Path(folder)),
            patch.object(dev, "run", side_effect=run),
            patch.object(dev, "install_archive"),
            patch.object(dev, "doctor"),
            patch.object(dev, "smoke", side_effect=smoke_error) as smoke,
            patch("time.sleep") as delay,
        ):
            if failure:
                with self.assertRaises(subprocess.CalledProcessError) as raised:
                    dev.bootstrap()
                if smoke_error is None:
                    self.assertEqual(raised.exception.returncode, outcomes[-1][0])
                else:
                    self.assertIs(raised.exception, smoke_error)
            else:
                dev.bootstrap()
            return calls, smoke.call_count, delay.call_args_list

    def test_observed_http_429_then_success_retains_each_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, smoke, delays = self.invoke(folder, [(1, HTTP_429), (0, "BUILD SUCCESSFUL")])
            self.assertEqual(len(calls), 2)
            self.assertEqual(smoke, 1)
            self.assertEqual(len(delays), 1)
            logs = sorted(Path(folder).glob(".cache/bootstrap/gradle-help-*/attempt-*.log"))
            self.assertEqual(len(logs), 2)
            self.assertIn(HTTP_429, logs[0].read_text())
            self.assertIn("BUILD SUCCESSFUL", logs[1].read_text())

    def test_dependency_error_on_stderr_is_retained_and_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, smoke, delays = self.invoke(folder, [(2, "setup output", HTTP_429), (0, "ok")])
            self.assertEqual((len(calls), smoke, len(delays)), (2, 1, 1))
            first = next(Path(folder).glob(".cache/bootstrap/gradle-help-*/attempt-1.log"))
            self.assertIn("setup output", first.read_text())
            self.assertIn(HTTP_429, first.read_text())

    def test_exhaustion_retains_failure_and_never_runs_smoke(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, smoke, delays = self.invoke(folder, [(7, HTTP_429)], failure=True)
            self.assertEqual(len(calls), 3)
            self.assertEqual(smoke, 0)
            self.assertEqual(len(delays), 2)
            self.assertTrue(5 <= delays[0].args[0] <= 11)
            self.assertTrue(15 <= delays[1].args[0] <= 21)
            logs = list(Path(folder).glob(".cache/bootstrap/gradle-help-*/attempt-*.log"))
            self.assertEqual(len(logs), 3)
            self.assertTrue(all(HTTP_429 in p.read_text() for p in logs))

    def test_gateway_errors_on_get_and_head_have_the_same_bounded_policy(self):
        for method in ("GET", "HEAD"):
            for status in ("502", "503", "504"):
                with (
                    self.subTest(method=method, status=status),
                    tempfile.TemporaryDirectory() as folder,
                ):
                    output = HTTP_429.replace("GET", method).replace("429", status)
                    calls, smoke, delays = self.invoke(folder, [(1, output), (0, "ok")])
                    self.assertEqual((len(calls), smoke, len(delays)), (2, 1, 1))

    def test_other_failures_are_not_retried(self):
        failures = [
            HTTP_429.replace("429", "404"),
            HTTP_429.replace("repo.maven.apache.org", "untrusted.example"),
            HTTP_429.replace("https://", "http://"),
            "429 errors in a test assertion",
            "Could not find org.example:missing:1.0.\n",
            "Script compilation errors: unresolved reference",
            HTTP_429 + "Dependency verification failed",
            HTTP_429 + "Script compilation errors",
            HTTP_429 + "Could not find org.example:missing:1.0",
        ]
        for output in failures:
            with self.subTest(output=output), tempfile.TemporaryDirectory() as folder:
                calls, smoke, delays = self.invoke(folder, [(1, output)], failure=True)
                self.assertEqual((len(calls), smoke, len(delays)), (1, 0, 0))

    def test_success_containing_429_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, smoke, delays = self.invoke(folder, [(0, HTTP_429)])
            self.assertEqual((len(calls), smoke, len(delays)), (1, 1, 0))

    def test_smoke_failure_after_bootstrap_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            calls, smoke, delays = self.invoke(
                folder,
                [(0, "ok")],
                failure=True,
                smoke_error=subprocess.CalledProcessError(1, ["runtime-verification"]),
            )
            self.assertEqual((len(calls), smoke, len(delays)), (1, 1, 0))

    def test_bootstrap_jobs_retain_failed_attempt_diagnostics(self):
        import json

        workflow = json.loads((dev.ROOT / ".github/workflows/hygiene.yml").read_text())
        count = 0
        for job in workflow["jobs"].values():
            steps = job.get("steps", [])
            if not any("tools/dev.py bootstrap" in step.get("run", "") for step in steps):
                continue
            count += 1
            upload = [
                s
                for s in steps
                if s.get("with", {}).get("path") == ".cache/bootstrap/gradle-*/attempt-*.log"
            ]
            self.assertEqual(len(upload), 1)
            setup = next(
                i for i, s in enumerate(steps) if "tools/dev.py bootstrap" in s.get("run", "")
            )
            self.assertEqual(steps.index(upload[0]), setup + 1)
            self.assertEqual(upload[0]["if"], "${{ failure() }}")
            self.assertEqual(upload[0]["with"]["include-hidden-files"], True)
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
