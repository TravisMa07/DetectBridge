"""Offline deployment policy validation; no Docker daemon or network required."""

import json
import re
from pathlib import Path

from check_contracts import load_json
from check_repo import yaml_load

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy/local"
EXPECTED = {
    "kafka": ("kafka", "1g", 1),
    "jobmanager": ("flink", "1g", 0.5),
    "taskmanager": ("flink", "2g", 1.5),
    "opensearch": ("opensearch", "2g", 1.5),
}


def validate(compose, lock):
    errors = []
    if lock.get("version") != 1 or set(lock.get("images", {})) != {"kafka", "flink", "opensearch"}:
        return ["invalid_image_lock"]
    for item in lock["images"].values():
        if (
            not re.fullmatch(r"[0-9a-f]{64}", item.get("index", ""))
            or set(item.get("platforms", {})) != {"linux/arm64", "linux/amd64"}
            or not all(re.fullmatch(r"[0-9a-f]{64}", v) for v in item["platforms"].values())
            or item.get("license") != "Apache-2.0"
            or not item.get("source", "").startswith("https://github.com/")
        ):
            errors.append("invalid_image_provenance")
    if set(compose.get("services", {})) != set(EXPECTED):
        return [*errors, "invalid_service_set"]
    if compose.get("networks") != {"internal": {"internal": True}} or set(
        compose.get("volumes", {})
    ) != {"kafka-data", "flink-state", "opensearch-data", "opensearch-config"}:
        errors.append("invalid_network_or_volumes")
    for name, (image, memory, cpus) in EXPECTED.items():
        service = compose["services"][name]
        item = lock["images"][image]
        if service.get("image") != item["tag"] + "@sha256:" + item["index"]:
            errors.append("unpinned_or_inconsistent_image")
        if (
            service.get("mem_limit") != memory
            or service.get("cpus") != cpus
            or service.get("pids_limit") != 256
        ):
            errors.append("invalid_resource_limit")
        if (
            service.get("user") != ("9999:9999" if image == "flink" else "1000:1000")
            or service.get("security_opt") != ["no-new-privileges:true"]
            or service.get("cap_drop") != ["ALL"]
            or any(
                service.get(k)
                for k in (
                    "privileged",
                    "cap_add",
                    "network_mode",
                    "pid",
                    "devices",
                    "build",
                    "container_name",
                )
            )
        ):
            errors.append("unsafe_container_policy")
        if service.get("networks") != ["internal"] or service.get("profiles") != (
            ["full"] if name == "opensearch" else ["core", "full"]
        ):
            errors.append("invalid_profile_or_network")
        wanted = ["127.0.0.1:${OPENSEARCH_PORT:-9200}:9200"] if name == "opensearch" else []
        if service.get("ports", []) != wanted:
            errors.append("unsafe_host_binding")
        if service.get("logging") != {
            "driver": "json-file",
            "options": {"max-size": "10m", "max-file": "3"},
        }:
            errors.append("unbounded_container_logs")
        health = service.get("healthcheck", {})
        if not health.get("test") or health.get("timeout") != "5s" or health.get("retries") != 30:
            errors.append("missing_bounded_healthcheck")
        for mount in service.get("volumes", []):
            if "/var/run/docker.sock" in mount or not (
                mount.split(":")[0] in compose["volumes"]
                or mount.startswith("${STACK_DIR:?Run stack.py init}/opensearch.yml:")
            ):
                errors.append("unsafe_mount")
    kafka = compose["services"]["kafka"]["environment"]
    for key, value in {
        "KAFKA_AUTO_CREATE_TOPICS_ENABLE": "false",
        "KAFKA_LOG_RETENTION_MS": "-1",
        "KAFKA_LOG_RETENTION_BYTES": "-1",
        "KAFKA_HEAP_OPTS": "-Xms512m -Xmx512m",
    }.items():
        if kafka.get(key) != value:
            errors.append("unsafe_kafka_defaults")
    if compose["services"]["opensearch"]["environment"] != {
        "DISABLE_INSTALL_DEMO_CONFIG": "true",
        "OPENSEARCH_JAVA_OPTS": "-Xms1g -Xmx1g",
    }:
        errors.append("unsafe_opensearch_environment")
    return errors


def main():
    try:
        errors = validate(
            yaml_load((DEPLOY / "compose.yml").read_text()), load_json(DEPLOY / "images.lock.json")
        )
    except Exception:
        errors = ["invalid_deployment_configuration"]
    if errors:
        print(json.dumps({"status": "failed", "categories": sorted(set(errors))}))
        return 1
    print("PASS: offline local infrastructure policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
