"""Private immutable candidate lifecycle. Prepared proposals never activate workers."""

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

import lifecycle_validation as validation

MIB = 1024 * 1024
STORE_BYTES = 512 * MIB
RESERVE_BYTES = 128 * MIB
TEMP_BYTES = 24 * MIB
RECORD_BYTES = 65536
BUNDLE_COUNT = 64
RECORD_COUNT = 4096
MAX_REVISION = 9223372036854775807


def HOOK(name):
    """Fault-injection boundary; ordinary execution has no observer."""
    return None


class LifecycleError(ValueError):
    """Only fixed bounded categories leave the administrative boundary."""


def check(condition, category):
    if not condition:
        raise LifecycleError("lifecycle_" + category)


def encoded(value):
    return validation.encoded(value)


def digest(value):
    return validation.sha(encoded(value))


def path_safe(value):
    check(".." not in Path(value).parts, "parent_path")
    path = Path(os.path.abspath(value))
    for parent in [*reversed(path.parents), path]:
        if parent.exists() or parent.is_symlink():
            check(not stat.S_ISLNK(parent.lstat().st_mode), "symlink")
    return path


def regular(path):
    path = path_safe(path)
    info = path.lstat()
    check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "regular_file")
    return path


def disjoint(a, b):
    check(a != b and a not in b.parents and b not in a.parents, "overlapping_roots")


def read(path, limit):
    with regular(path).open("rb") as stream:
        data = stream.read(limit + 1)
    check(len(data) <= limit, "file_limit")
    return data


def document(data):
    def pairs(items):
        value = {}
        for key, item in items:
            check(key not in value, "duplicate_key")
            value[key] = item
        return value

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(LifecycleError("lifecycle_number")),
        )
        # Reject lone Unicode surrogates before canonical serialization or diagnostics.
        encoded(value).decode("utf-8").encode("utf-8", errors="strict")
        return value
    except LifecycleError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise LifecycleError("lifecycle_invalid_json") from None


def checked(path, limit=RECORD_BYTES):
    wrapper = document(read(path, limit))
    check(isinstance(wrapper, dict) and set(wrapper) == {"value", "sha256"}, "checked_file")
    check(wrapper["sha256"] == digest(wrapper["value"]), "checked_digest")
    return wrapper["value"]


def wrapped(value):
    return encoded({"value": value, "sha256": digest(value)})


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive(path, data):
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # A partial durable write is never presented as a complete publication.
        raise


class Store:
    @staticmethod
    def initialize(root, authority_id, evaluator_jar, profile):
        root = path_safe(root)
        jar = regular(evaluator_jar)
        disjoint(root, jar)
        check(str(uuid.UUID(authority_id)) == authority_id, "authority")
        validation.verify_artifact(jar)
        # The manifest schema supplies the exact closed installed-profile definition.
        schema = document(
            read(
                Path(__file__).resolve().parents[1] / "contracts/lifecycle/v1/manifest.schema.json",
                MIB,
            )
        )
        from jsonschema import Draft202012Validator

        check(
            not list(Draft202012Validator(schema["properties"]["profile"]).iter_errors(profile)),
            "profile",
        )
        check(not root.exists() and not root.is_symlink(), "existing_root")
        check(root.parent.is_dir(), "root_parent")
        free = shutil.disk_usage(root.parent).free
        check(free >= RESERVE_BYTES + RECORD_BYTES * 2, "disk_reserve")
        root.mkdir(mode=0o700)
        for name in ("objects", "bundles", "journal", ".temporary"):
            (root / name).mkdir(mode=0o700)
        write_exclusive(root / ".lock", b"")
        configuration = dict(
            version="1.0.0",
            store_id=str(uuid.uuid4()),
            authority_id=authority_id,
            profile=profile,
            evaluator_sha256=validation.sha(read(jar, 64 * MIB)),
        )
        write_exclusive(root / "config.json", wrapped(configuration))
        write_exclusive(
            root / "head.json",
            wrapped(
                dict(
                    version="1.0.0",
                    store_id=configuration["store_id"],
                    sequence=0,
                    record_sha256=None,
                )
            ),
        )
        for name in ("objects", "bundles", "journal", ".temporary"):
            sync_directory(root / name)
        sync_directory(root)
        sync_directory(root.parent)
        return Store(root, authority_id, jar)

    def __init__(self, root, authority_id, evaluator_jar):
        self.root = path_safe(root)
        self.authority = authority_id
        self.jar = regular(evaluator_jar)
        disjoint(self.root, self.jar)
        self._private_root()
        with self._locked():
            self._load()

    def _private_root(self):
        info = self.root.lstat()
        check(
            stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700,
            "private_root",
        )

    @contextlib.contextmanager
    def _locked(self):
        self._private_root()
        lock = regular(self.root / ".lock")
        descriptor = os.open(lock, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            raise LifecycleError("lifecycle_locked") from None
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _inventory(self):
        total = 0
        for folder, directories, files in os.walk(self.root, followlinks=False):
            for name in directories:
                item = Path(folder) / name
                info = item.lstat()
                check(
                    stat.S_ISDIR(info.st_mode)
                    and not item.is_symlink()
                    and info.st_uid == os.getuid()
                    and stat.S_IMODE(info.st_mode) == 0o700,
                    "private_directory",
                )
            for name in files:
                item = regular(Path(folder) / name)
                info = item.lstat()
                check(
                    info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                    "private_file",
                )
                total += info.st_size
                check(total <= STORE_BYTES, "store_limit")
        return total

    def _reserve(self, amount):
        check(self._inventory() + amount <= STORE_BYTES, "store_limit")
        check(shutil.disk_usage(self.root).free >= RESERVE_BYTES + amount, "disk_reserve")

    def _head(self, sequence, record_hash):
        value = dict(
            version="1.0.0",
            store_id=self.config["store_id"],
            sequence=sequence,
            record_sha256=record_hash,
        )
        temporary = self.root / ".temporary" / "head.json"
        check(not temporary.exists(), "temporary_conflict")
        write_exclusive(temporary, wrapped(value))
        os.replace(temporary, self.root / "head.json")
        HOOK("after_head_publication")
        sync_directory(self.root)
        HOOK("after_head_sync")

    def _load(self):
        try:
            self._load_checked()
        except (KeyError, TypeError, AttributeError, IndexError):
            raise LifecycleError("lifecycle_store_structure") from None

    def _load_checked(self):
        self._private_root()
        check(
            set(p.name for p in self.root.iterdir())
            == {"objects", "bundles", "journal", ".temporary", ".lock", "config.json", "head.json"},
            "store_contents",
        )
        self._inventory()
        validation.verify_artifact(self.jar)
        self.config = checked(self.root / "config.json")
        check(
            isinstance(self.config, dict)
            and set(self.config)
            == {"version", "store_id", "authority_id", "profile", "evaluator_sha256"},
            "configuration",
        )
        check(
            self.config["version"] == "1.0.0" and self.config["authority_id"] == self.authority,
            "authority",
        )
        check(str(uuid.UUID(self.config["store_id"])) == self.config["store_id"], "store_identity")
        check(
            self.config["evaluator_sha256"]
            == self.config["profile"]["evaluator_artifact_sha256"]
            == validation.sha(read(self.jar, 64 * MIB)),
            "artifact",
        )
        self.bundles = {}
        self.requests = {}
        self.preparation_revision = 0
        self.prepared_hash = None
        self.deployment_id = None
        self.sequence = 0
        self.record_hash = None
        # Under the exclusive lock only this fixed owned namespace may be cleaned.
        for item in (self.root / ".temporary").iterdir():
            check(
                item.name == "head.json"
                or re.fullmatch(r"test-[a-f0-9]{32}", item.name)
                or re.fullmatch(r"publish-[a-f0-9]{32}", item.name),
                "temporary_contents",
            )
            if item.is_dir():
                shutil.rmtree(item)
            else:
                regular(item).unlink()
        sync_directory(self.root / ".temporary")
        available: dict[str, Any] = {}
        for item in (self.root / "bundles").iterdir():
            check(
                re.fullmatch(r"[a-f0-9]{64}", item.name) is not None and item.is_dir(),
                "bundle_contents",
            )
            check(len(available) < BUNDLE_COUNT, "bundle_limit")
            manifest, plan_bytes = validation.verify_bundle(item)
            check(
                item.name == manifest["bundle_sha256"]
                and manifest["profile"] == self.config["profile"],
                "profile",
            )
            available[item.name] = manifest
            check(
                read(self.root / "objects" / manifest["plan"]["sha256"], 4 * MIB) == plan_bytes,
                "object_integrity",
            )
        expected_objects = {value["plan"]["sha256"] for value in available.values()}
        # Orphan exact immutable objects can survive a pre-journal import failure.
        object_files = list((self.root / "objects").iterdir())
        check(len(object_files) <= BUNDLE_COUNT, "object_limit")
        for item in object_files:
            check(re.fullmatch(r"[a-f0-9]{64}", item.name) is not None, "object_name")
            check(validation.sha(read(item, 4 * MIB)) == item.name, "object_integrity")
        check(
            expected_objects <= {p.name for p in (self.root / "objects").iterdir()},
            "object_missing",
        )
        self.available = available
        head = checked(self.root / "head.json")
        check(
            isinstance(head, dict)
            and set(head) == {"version", "store_id", "sequence", "record_sha256"}
            and head["version"] == "1.0.0"
            and head["store_id"] == self.config["store_id"]
            and type(head["sequence"]) is int
            and 0 <= head["sequence"] <= RECORD_COUNT,
            "head",
        )
        files = sorted((self.root / "journal").iterdir())
        check(
            len(files) <= RECORD_COUNT and len(files) in {head["sequence"], head["sequence"] + 1},
            "journal_count",
        )
        if head["sequence"] == 0:
            check(head["record_sha256"] is None, "head_binding")
        for index, item in enumerate(files, 1):
            check(item.name == f"{index:020d}.json", "journal_gap")
            record = checked(item)
            self._replay(record, index)
            self.sequence = index
            self.record_hash = digest(record)
            if index == head["sequence"]:
                check(head["record_sha256"] == self.record_hash, "head_binding")
        # A surviving rename is not a durable directory entry until its parent is forced.
        # Force it before publishing a recovery head that depends on that entry.
        sync_directory(self.root / "journal")
        if len(files) == head["sequence"] + 1:
            self._head(self.sequence, self.record_hash)
        # Force the directory even if a prior rename survived without parent sync.
        sync_directory(self.root / "journal")
        sync_directory(self.root)

    def _replay(self, record, index):
        check(
            isinstance(record, dict)
            and set(record)
            == {
                "version",
                "store_id",
                "sequence",
                "previous_sha256",
                "request_id",
                "request_sha256",
                "request",
                "operation",
                "bundle_sha256",
                "result",
            },
            "record",
        )
        request = record["request"]
        validation.require("request", request)
        check(
            record["version"] == "1.0.0"
            and record["store_id"] == self.config["store_id"]
            and type(record["sequence"]) is int
            and record["sequence"] == index
            and record["previous_sha256"] == self.record_hash
            and record["request_id"] == request["request_id"]
            and record["request_sha256"] == digest(request)
            and record["operation"] == request["operation"]
            and record["bundle_sha256"] == request["bundle_sha256"]
            and request["authority_id"] == self.authority
            and request["request_id"] not in self.requests,
            "record_binding",
        )
        expected = self._transition(request, record["result"].get("report"), replay=True)
        check(record["result"] == expected, "record_result")
        self._apply(request, expected)
        self.requests[request["request_id"]] = (digest(request), expected)

    def _transition(self, request, report=None, replay=False):
        operation = request["operation"]
        target = request["bundle_sha256"]
        args = request["arguments"]
        result = dict(version="1.0.0", operation=operation, bundle_sha256=target)
        if operation == "import":
            check(target in self.available, "candidate_missing")
            manifest = self.available[target]
            stored = self.root / "bundles" / target
            check(
                validation.sha(read(stored / "manifest.json", 65536)) == args["manifest_sha256"]
                and manifest["plan"]["sha256"] == args["plan_sha256"],
                "import_binding",
            )
            check(not self.bundles.get(target, {}).get("retired", False), "retired")
            result["state"] = "imported"
            return result
        check(target in self.bundles, "not_imported")
        state = self.bundles[target]
        check(not state["retired"], "retired")
        if operation == "validate":
            result["state"] = "validated"
        elif operation == "test":
            check(state["validated"], "validation_required")
            check(
                isinstance(report, dict)
                and type(report.get("passed")) is bool
                and report.get("version") == "1.0.0"
                and report.get("suite_sha256") == args["suite_sha256"]
                and report.get("plan_sha256") == self.available[target]["plan"]["sha256"]
                and report.get("evaluator_sha256") == self.config["evaluator_sha256"],
                "test_report",
            )
            result.update(state="tested" if report["passed"] else "test_failed", report=report)
        elif operation == "stage":
            check(state["validated"] and state["tested"], "test_required")
            result["state"] = "staged"
        elif operation == "prepare":
            check(state["staged"] and state["tested"], "stage_required")
            command = args["command"]
            check(
                args["expected_preparation_revision"] == self.preparation_revision
                and self.preparation_revision < MAX_REVISION
                and command["revision"] == self.preparation_revision + 1,
                "preparation_revision",
            )
            check(command["previous_sha256"] == self.prepared_hash, "preparation_previous")
            check(
                command["authority_id"] == self.authority
                and command["request_id"] == request["request_id"]
                and command["bundle_sha256"] == target
                and command["compatibility_sha256"]
                == self.available[target]["compatibility_sha256"],
                "command_binding",
            )
            check(
                self.deployment_id is None or command["deployment_id"] == self.deployment_id,
                "deployment",
            )
            workers = [p["worker_id"] for p in command["participants"]]
            check(workers == sorted(set(workers)) and len(encoded(command)) <= 65536, "membership")
            result.update(
                state="prepared",
                command=command,
                command_sha256=digest(command),
                preparation_revision=command["revision"],
            )
        elif operation == "retire":
            check(not state["prepared"], "prepared_reference")
            result["state"] = "retired"
        else:
            raise LifecycleError("lifecycle_operation")
        return result

    def _apply(self, request, result):
        target = request["bundle_sha256"]
        operation = request["operation"]
        if operation == "import":
            self.bundles.setdefault(
                target,
                dict(
                    imported=True,
                    validated=False,
                    tested=False,
                    staged=False,
                    retired=False,
                    prepared=False,
                ),
            )
        else:
            state = self.bundles[target]
            if operation == "validate":
                state["validated"] = True
            elif operation == "test":
                state["tested"] = result["report"]["passed"]
                if not state["tested"]:
                    state["staged"] = False
            elif operation == "stage":
                state["staged"] = True
            elif operation == "retire":
                state["retired"] = True
                state["staged"] = False
            elif operation == "prepare":
                state["prepared"] = True
                self.preparation_revision = result["preparation_revision"]
                self.prepared_hash = result["command_sha256"]
                self.deployment_id = result["command"]["deployment_id"]

    def _publish_import(self, request, candidate):
        candidate = path_safe(candidate)
        disjoint(self.root, candidate)
        check(candidate.is_dir(), "candidate_directory")
        manifest, plan_bytes = validation.verify_bundle(candidate)
        target = request["bundle_sha256"]
        manifest_bytes = read(candidate / "manifest.json", 65536)
        check(
            manifest["bundle_sha256"] == target and manifest["profile"] == self.config["profile"],
            "profile",
        )
        check(
            validation.sha(manifest_bytes) == request["arguments"]["manifest_sha256"]
            and validation.sha(plan_bytes) == request["arguments"]["plan_sha256"],
            "import_binding",
        )
        if target not in self.available:
            check(len(self.available) < BUNDLE_COUNT, "bundle_limit")
            self._reserve(len(manifest_bytes) + 2 * len(plan_bytes) + RECORD_BYTES * 2)
            object_path = self.root / "objects" / manifest["plan"]["sha256"]
            if object_path.exists():
                check(read(object_path, 4 * MIB) == plan_bytes, "object_conflict")
            else:
                check(
                    len(list((self.root / "objects").iterdir())) < BUNDLE_COUNT,
                    "object_limit",
                )
                self._publish_file(object_path, plan_bytes)
            temporary = self.root / ".temporary" / ("publish-" + uuid.uuid4().hex)
            temporary.mkdir(mode=0o700)
            write_exclusive(temporary / "manifest.json", manifest_bytes)
            write_exclusive(temporary / "plan.json", plan_bytes)
            sync_directory(temporary)
            os.rename(temporary, self.root / "bundles" / target)
            sync_directory(self.root / "bundles")
            HOOK("after_object_publication")
            self.available[target] = manifest

    def _publish_file(self, target, data):
        temporary = self.root / ".temporary" / ("publish-" + uuid.uuid4().hex)
        write_exclusive(temporary, data)
        os.rename(temporary, target)
        sync_directory(target.parent)

    def execute(self, request, bundle_directory=None, suite_path=None):
        # Detach caller-owned values, enforce byte bounds and reject unserializable input.
        request = document(encoded(request))
        check(len(encoded(request)) <= RECORD_BYTES, "request_limit")
        validation.require("request", request)
        with self._locked():
            self._load()
            check(request["authority_id"] == self.authority, "authority")
            previous = self.requests.get(request["request_id"])
            if previous is not None:
                check(previous[0] == digest(request), "request_conflict")
                return document(encoded(previous[1]))
            check(self.sequence < RECORD_COUNT, "history_limit")
            self._reserve(RECORD_BYTES * 2)
            operation = request["operation"]
            report = None
            if operation == "import":
                check(bundle_directory is not None, "candidate_required")
                self._publish_import(request, bundle_directory)
            elif operation == "validate":
                self._transition(request)
                self._reserve(TEMP_BYTES + RECORD_BYTES * 2)
                temporary = self.root / ".temporary" / ("test-" + uuid.uuid4().hex)
                temporary.mkdir(mode=0o700)
                try:
                    validation.validate_plan(
                        read(
                            self.root / "bundles" / request["bundle_sha256"] / "plan.json", 4 * MIB
                        ),
                        temporary,
                    )
                finally:
                    shutil.rmtree(temporary)
                    sync_directory(self.root / ".temporary")
            elif operation == "test":
                target = request["bundle_sha256"]
                check(
                    target in self.bundles
                    and not self.bundles[target]["retired"]
                    and self.bundles[target]["validated"],
                    "validation_required",
                )
                check(suite_path is not None, "suite_required")
                suite_path = regular(suite_path)
                disjoint(self.root, suite_path)
                check(
                    validation.sha(read(suite_path, 17 * MIB))
                    == request["arguments"]["suite_sha256"],
                    "suite_binding",
                )
                self._reserve(TEMP_BYTES + RECORD_BYTES * 2)
                temporary = self.root / ".temporary" / ("test-" + uuid.uuid4().hex)
                temporary.mkdir(mode=0o700)
                try:
                    report = validation.run_suite(
                        read(self.root / "bundles" / target / "plan.json", 4 * MIB),
                        suite_path,
                        self.jar,
                        temporary,
                    )
                finally:
                    shutil.rmtree(temporary)
                    sync_directory(self.root / ".temporary")
            result = self._transition(request, report)
            record = dict(
                version="1.0.0",
                store_id=self.config["store_id"],
                sequence=self.sequence + 1,
                previous_sha256=self.record_hash,
                request_id=request["request_id"],
                request_sha256=digest(request),
                request=request,
                operation=operation,
                bundle_sha256=request["bundle_sha256"],
                result=result,
            )
            payload = wrapped(record)
            check(len(payload) <= RECORD_BYTES, "record_limit")
            self._reserve(len(payload) + RECORD_BYTES)
            self._publish_file(self.root / "journal" / f"{self.sequence + 1:020d}.json", payload)
            HOOK("after_record_publication")
            self._head(self.sequence + 1, digest(record))
            return document(encoded(result))

    def status(self):
        with self._locked():
            self._load()
            return document(
                encoded(
                    dict(
                        version="1.0.0",
                        store_id=self.config["store_id"],
                        authority_id=self.authority,
                        profile=self.config["profile"],
                        bundles=self.bundles,
                        preparation_revision=self.preparation_revision,
                        prepared_command_sha256=self.prepared_hash,
                        records=self.sequence,
                    )
                )
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "execute", "status"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--evaluator-jar", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--request")
    parser.add_argument("--candidate")
    parser.add_argument("--suite")
    args = parser.parse_args()
    try:
        if args.command == "init":
            check(args.profile is not None, "profile_required")
            store = Store.initialize(
                args.root, args.authority, args.evaluator_jar, document(read(args.profile, 65536))
            )
            result = store.status()
        else:
            store = Store(args.root, args.authority, args.evaluator_jar)
            if args.command == "status":
                result = store.status()
            else:
                check(args.request is not None, "request_required")
                result = store.execute(
                    document(read(args.request, RECORD_BYTES)), args.candidate, args.suite
                )
        print(encoded(result).decode())
        if result.get("state") == "test_failed":
            return 1
    except Exception as failure:
        category = str(failure)
        if not re.fullmatch(r"lifecycle_[a-z_]{1,64}", category):
            category = "lifecycle_operation_failed"
        print(json.dumps(dict(category=category)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
