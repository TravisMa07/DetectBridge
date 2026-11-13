"""Reproducible, project-local development commands; no system tool replacement."""

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / "tools/toolchains.json").read_text())


def environment():
    env = os.environ.copy()
    node = ROOT / ".cache/node/bin"
    java = ROOT / ".cache/jdk"
    env["PATH"] = str(node) + os.pathsep + env.get("PATH", "")
    env["JAVA_HOME"] = str(java)
    env["GRADLE_USER_HOME"] = str(ROOT / ".cache/gradle")
    return env


def run(args, capture=False, cwd=ROOT, check=True):
    return subprocess.run(
        [str(a) for a in args],
        cwd=cwd,
        env=environment(),
        check=check,
        text=True,
        capture_output=capture,
    )


def npm(*args):
    cli = ROOT / ".cache/npm/node_modules/npm/bin/npm-cli.js"
    return ["node", cli, *args] if cli.exists() else ["npm", *args]


def checked_digest(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("Download or Wrapper checksum mismatch")


def install_archive(name):
    dest = ROOT / ".cache" / name
    if dest.exists():
        return
    key = f"{platform.system()}-{platform.machine()}"
    artifact = PINS["downloads"][name].get(key)
    if artifact is None:
        raise RuntimeError(f"Unsupported platform {key}; supported: macOS ARM64, Linux AMD64")
    request = urllib.request.Request(
        artifact["url"], headers={"User-Agent": "DetectBridge-development"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    checked_digest(data, artifact["sha256"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            archive.extractall(tmp, filter="data")
        children = list(Path(tmp).iterdir())
        if len(children) != 1 or not children[0].is_dir():
            raise RuntimeError(f"Unexpected {name} archive structure")
        source = children[0]
        if name == "jdk" and platform.system() == "Darwin":
            source = source / "Contents/Home"
        shutil.move(str(source), dest)


def expect_version(label, actual, expected):
    if actual != expected:
        raise RuntimeError(
            f"{label}: expected {expected}, found {actual}. Run python3 tools/dev.py bootstrap; install pinned uv explicitly if needed."
        )


def consistency():
    expect_version("Python pin", (ROOT / ".python-version").read_text().strip(), PINS["python"])
    expect_version("Node pin", (ROOT / ".node-version").read_text().strip(), PINS["node"])
    package = json.loads((ROOT / "package.json").read_text())
    expect_version("npm metadata", package["packageManager"], "npm@" + PINS["npm"])
    expect_version("Node metadata", package["engines"]["node"], PINS["node"])
    expect_version("npm engine", package["engines"]["npm"], PINS["npm"])
    expect_version("TypeScript pin", package["devDependencies"]["typescript"], PINS["typescript"])
    import tomllib

    py = tomllib.loads((ROOT / "pyproject.toml").read_text())
    expect_version("uv requirement", py["tool"]["uv"]["required-version"], "==" + PINS["uv"])
    for name in ("ruff", "mypy"):
        if f"{name}=={PINS[name]}" not in py["dependency-groups"]["dev"]:
            raise RuntimeError(f"{name} manifest drift")
    properties = (ROOT / "gradle/wrapper/gradle-wrapper.properties").read_text()
    if (
        f"gradle-{PINS['gradle']}-bin.zip" not in properties
        or PINS["gradle_sha256"] not in properties
    ):
        raise RuntimeError("Gradle distribution pin drift")
    checked_digest(
        (ROOT / "gradle/wrapper/gradle-wrapper.jar").read_bytes(), PINS["wrapper_sha256"]
    )
    # Check every literal runtime input; dynamic workflows must source the manifest.
    from check_repo import yaml_load

    for path in (ROOT / ".github/workflows").glob("*.yml"):
        data = yaml_load(path.read_text())
        for job in data["jobs"].values():
            for step in job.get("steps", []):
                for key, pin in [("python-version", "python"), ("node-version", "node")]:
                    if key in step.get("with", {}):
                        expect_version(f"{path.name} {key}", str(step["with"][key]), PINS[pin])


def doctor():
    print(f"Platform: {platform.system()} {platform.machine()}")
    commands = [
        ("uv", ["uv", "--version"], "uv"),
        ("node", ["node", "--version"], "node"),
        ("npm", npm("--version"), "npm"),
    ]
    for label, command, pin in commands:
        output = run(command, capture=True).stdout.strip().split()
        actual = output[1] if label == "uv" else output[0].lstrip("v")
        print(f"{label}: {actual}")
        expect_version(label, actual, PINS[pin])
    output = run(
        [
            "uv",
            "run",
            "--locked",
            "--no-sync",
            "python",
            "-c",
            "import platform; print(platform.python_version())",
        ],
        capture=True,
    ).stdout.strip()
    expect_version("Python", output, PINS["python"])
    java = ROOT / ".cache/jdk/bin/java"
    if not java.exists():
        raise RuntimeError("Missing project JDK: python3 tools/dev.py bootstrap")
    result = run([java, "-version"], capture=True)
    if PINS["java"] not in result.stderr or "Temurin" not in result.stderr:
        raise RuntimeError("JDK mismatch: expected Temurin " + PINS["java"])
    print("Java: Temurin " + PINS["java"])
    print("Python: " + PINS["python"])
    print("Gradle Wrapper: " + PINS["gradle"])
    for package in ("ruff", "mypy"):
        output = run(
            ["uv", "run", "--locked", "--no-sync", package, "--version"], capture=True
        ).stdout
        expect_version(package, output.split()[1], PINS[package])
        print(output.strip())
    output = run(
        ["node", ROOT / "node_modules/typescript/bin/tsc", "--version"], capture=True
    ).stdout
    expect_version("TypeScript", output.split()[1], PINS["typescript"])
    print(output.strip())
    consistency()


def bootstrap():
    expect_version("uv", run(["uv", "--version"], capture=True).stdout.split()[1], PINS["uv"])
    install_archive("node")
    install_archive("jdk")
    # Install npm in ignored project cache, never using a global install.
    if not (ROOT / ".cache/npm/node_modules/npm/bin/npm-cli.js").exists():
        run(
            [
                ROOT / ".cache/node/bin/npm",
                "install",
                "--prefix",
                ROOT / ".cache/npm",
                "--ignore-scripts",
                "npm@" + PINS["npm"],
            ]
        )
    run(["uv", "sync", "--locked"])
    run(npm("ci", "--ignore-scripts"))
    run(["uv", "run", "--locked", "python", "tools/install_hygiene.py"])
    doctor()
    run([ROOT / "gradlew", "--console=plain", "help"])
    # Populate built-in Java plugin caches; verification subsequently runs offline.
    smoke()


def check():
    consistency()
    run(["uv", "run", "--locked", "python", "tools/check_datasets.py"])
    run(["uv", "run", "--locked", "python", "tools/check_contracts.py"])
    run(["uv", "run", "--locked", "python", "tools/check_replay.py"])
    run(["uv", "run", "--locked", "python", "tools/check_stack.py"])
    run(["uv", "run", "--locked", "python", "tools/check_repo.py"])
    run(["uv", "run", "--locked", "ruff", "check", "tools"])
    run(["uv", "run", "--locked", "ruff", "format", "--check", "tools"])
    run(["uv", "run", "--locked", "mypy"])


def smoke():
    doctor()
    with tempfile.TemporaryDirectory(prefix="detectbridge-toolchain-") as tmp:
        folder = Path(tmp)
        (folder / "settings.gradle").write_text("rootProject.name = 'toolchain-smoke'\n")
        (folder / "build.gradle").write_text(
            "plugins { id 'java' }\njava { toolchain { languageVersion = JavaLanguageVersion.of(17) } }\ntasks.register('runSmoke', JavaExec) { classpath = sourceSets.main.runtimeClasspath; mainClass = 'Smoke' }\n"
        )
        source = folder / "src/main/java/Smoke.java"
        source.parent.mkdir(parents=True)
        source.write_text(
            'public class Smoke { public static void main(String[] args) { System.out.println("toolchain-ok"); } }\n'
        )
        command = [ROOT / "gradlew", "-p", folder, "--offline", "--console=plain", "runSmoke"]
        result = run(command, capture=True)
        if "toolchain-ok" not in result.stdout:
            raise RuntimeError("Java execution did not return expected output")
        source.write_text("public class Smoke { broken syntax }\n")
        if run(command, capture=True, check=False).returncode == 0:
            raise RuntimeError("Java accepted invalid source")
        (folder / "tsconfig.json").write_text(
            json.dumps({"extends": str(ROOT / "tsconfig.base.json"), "files": ["smoke.ts"]})
        )
        ts = folder / "smoke.ts"
        ts.write_text("const value: number = 42;\nexport { value };\n")
        command = [
            "node",
            ROOT / "node_modules/typescript/bin/tsc",
            "--project",
            folder,
            "--noEmit",
        ]
        run(command)
        ts.write_text('const value: number = "invalid";\n')
        if run(command, capture=True, check=False).returncode == 0:
            raise RuntimeError("TypeScript accepted invalid assignment")
    print("PASS: Java and TypeScript positive/negative smoke checks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "bootstrap", "check", "smoke", "verify"])
    args = parser.parse_args()
    try:
        if Path(sys.executable).parent.resolve() != (ROOT / ".venv/bin").resolve():
            if args.command == "doctor" and not (ROOT / ".venv/bin/python").exists():
                raise RuntimeError("Missing locked environment: python3 tools/dev.py bootstrap")
            extra = ["--no-sync"] if args.command == "doctor" else []
            return run(
                ["uv", "run", "--locked", *extra, "python", __file__, args.command], check=False
            ).returncode
        if args.command == "verify":
            check()
            smoke()
        else:
            globals()[args.command]()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
