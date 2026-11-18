"""Single verified dependency preparation precedes CI runtime fan-out."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dev
from dev import ROOT


class CacheTests(unittest.TestCase):
    def test_every_bootstrap_consumer_restores_the_seed_cache(self):
        workflow = json.loads((ROOT / ".github/workflows/hygiene.yml").read_text())
        seed = workflow["jobs"]["toolchain-verification"]
        cache = [s for s in seed["steps"] if s.get("uses", "").startswith("actions/cache@")]
        self.assertEqual(len(cache), 1)
        key = cache[0]["with"]["key"]
        self.assertEqual(
            cache[0]["with"]["path"].splitlines(),
            [
                ".cache/gradle/caches/modules-2/files-2.1",
                ".cache/gradle/caches/modules-2/metadata-*",
            ],
        )
        self.assertNotIn("restore-keys", cache[0]["with"])
        self.assertIn("verification-metadata", key)
        self.assertIn("gradle.lockfile", key)
        self.assertIn("runner.arch", key)
        self.assertTrue(any("tools/dev.py dependencies" in s.get("run", "") for s in seed["steps"]))
        count = 0
        for name, job in workflow["jobs"].items():
            if name == "toolchain-verification":
                continue
            steps = job.get("steps", [])
            setup = [i for i, s in enumerate(steps) if "tools/dev.py bootstrap" in s.get("run", "")]
            if not setup:
                continue
            count += 1
            self.assertIn("toolchain-verification", job["needs"])
            restore = [
                (i, s)
                for i, s in enumerate(steps)
                if s.get("uses", "").startswith("actions/cache/restore@")
            ]
            self.assertEqual(len(restore), 1)
            index, action = restore[0]
            self.assertLess(index, setup[0])
            self.assertEqual(action["with"]["key"], key)
            self.assertEqual(action["with"]["fail-on-cache-miss"], True)
            self.assertNotIn("restore-keys", action["with"])
            self.assertFalse(
                any(
                    s.get("uses", "").startswith(("actions/cache@", "actions/cache/save@"))
                    for s in steps
                )
            )
        self.assertEqual(count, 13)

    def test_every_consumer_requires_an_exact_cache_hit_before_bootstrap(self):
        workflow = json.loads((ROOT / ".github/workflows/hygiene.yml").read_text())
        guarded = 0
        for name, job in workflow["jobs"].items():
            steps = job.get("steps", [])
            restores = [
                (i, s)
                for i, s in enumerate(steps)
                if s.get("uses", "").startswith("actions/cache/restore@")
            ]
            if not restores:
                continue
            restore_index, restore = restores[0]
            guards = [
                (i, s)
                for i, s in enumerate(steps)
                if s.get("id") == "require-prepared-gradle-cache"
            ]
            with self.subTest(job=name):
                self.assertEqual(len(guards), 1)
                guard_index, guard = guards[0]
                bootstrap = next(
                    i for i, s in enumerate(steps) if "tools/dev.py bootstrap" in s.get("run", "")
                )
                self.assertEqual(restore["id"], "prepared-gradle-cache")
                self.assertLess(restore_index, guard_index)
                self.assertLess(guard_index, bootstrap)
                self.assertEqual(guard["shell"], "bash")
                self.assertEqual(
                    guard["env"]["CACHE_HIT"],
                    "${{ steps.prepared-gradle-cache.outputs.cache-hit }}",
                )
            guarded += 1
        self.assertEqual(guarded, 13)

    def test_exact_hit_guard_shell_rejects_absent_false_and_empty_outputs(self):
        workflow = json.loads((ROOT / ".github/workflows/hygiene.yml").read_text())
        guards = [
            s
            for job in workflow["jobs"].values()
            for s in job.get("steps", [])
            if s.get("id") == "require-prepared-gradle-cache"
        ]
        self.assertEqual(len(guards), 13)
        for guard in guards:
            for value, passed in (
                (None, False),
                ("", False),
                ("false", False),
                ("true", True),
                ("TRUE", False),
            ):
                env = os.environ.copy()
                env.pop("CACHE_HIT", None)
                if value is not None:
                    env["CACHE_HIT"] = value
                with self.subTest(value=value):
                    result = subprocess.run(
                        [
                            "bash",
                            "--noprofile",
                            "--norc",
                            "-e",
                            "-o",
                            "pipefail",
                            "-c",
                            guard["run"],
                        ],
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode == 0, passed)

    def test_runtime_tasks_cannot_use_the_dependency_retry_helper(self):
        for task in ("test", "integration", "ciDependencies --continue", ""):
            with self.subTest(task=task), patch.object(dev, "run") as invoke:
                with self.assertRaises(RuntimeError):
                    dev.bootstrap_gradle(task)
                invoke.assert_not_called()

    def test_prefetch_uses_the_same_bounded_http_setup_policy(self):
        failure = "Could not resolve all files.\n> Could not GET 'https://repo.maven.apache.org/maven2/example/1/example-1.jar'.\n> Received status code 429 from server: Too Many Requests\n"
        with tempfile.TemporaryDirectory() as folder, patch.object(dev, "ROOT", Path(folder)):
            outcomes = [
                subprocess.CompletedProcess([], 1, "", failure),
                subprocess.CompletedProcess([], 0, "prefetch complete", ""),
            ]
            with (
                patch.object(dev, "run", side_effect=outcomes) as invoke,
                patch.object(dev.time, "sleep") as sleep,
            ):
                dev.dependencies()
                self.assertEqual(invoke.call_count, 2)
                self.assertEqual(sleep.call_count, 1)
                self.assertTrue(
                    all(c.args[0][-1] == "ciDependencies" for c in invoke.call_args_list)
                )
                self.assertEqual(
                    len(
                        list(
                            Path(folder).glob(
                                ".cache/bootstrap/gradle-ciDependencies-*/attempt-*.log"
                            )
                        )
                    ),
                    2,
                )


if __name__ == "__main__":
    unittest.main()
