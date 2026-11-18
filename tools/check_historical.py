"""Closed historical schemas, independent fixture lineage and thin artifact boundary."""

import argparse
import zipfile

from check_contracts import load_json
from historical import PRODUCER, ROOT, SCHEMAS, encoded, sha
from jsonschema import Draft202012Validator


def check(artifacts=False):
    for name in ("request", "selection", "run", "result", "commit"):
        schema = load_json(SCHEMAS / (name + ".schema.json"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == "urn:detectbridge:historical-replay:1.0.0:" + name
        assert schema["additionalProperties"] is False

        def local(node):
            if isinstance(node, dict):
                assert "$ref" not in node and "$dynamicRef" not in node
                for value in node.values():
                    local(value)
            elif isinstance(node, list):
                for value in node:
                    local(value)

        local(schema)
    vector = load_json(SCHEMAS / "fixtures/identity.json")
    assert vector["id"] == "sha256:" + sha(encoded(vector["preimage"]))
    packet = load_json(SCHEMAS / "fixtures/expectations.json")
    for path, digest in packet["source_sha256"].items():
        assert sha((ROOT / path).read_bytes()) == digest
    for value in packet["inputs"].values():
        assert sha(encoded(value["value"])) == value["sha256"]
    assert packet["literal_counts"] == load_json(
        ROOT / "contracts/integration-runtime/v1/fixtures/expectations.json"
    )
    if artifacts:
        with zipfile.ZipFile(
            ROOT / "packages/historical-replay/build/libs/historical-replay.jar"
        ) as jar:
            names = jar.namelist()
            assert len(names) == len(set(names))
            assert "io/detectbridge/history/Bootstrap.class" in names
            assert all(n.startswith(("META-INF/", "io/")) for n in names)
            assert all(
                not n.endswith(".class") or n.startswith("io/detectbridge/history/") for n in names
            )
            assert not any("Probe" in n or "OriginalProducer" in n for n in names)
            assert jar.read("META-INF/DetectBridge-LICENSE") == (ROOT / "LICENSE").read_bytes()
        assert (
            sha((ROOT / "packages/integration-job/build/libs/integration-job.jar").read_bytes())
            == PRODUCER
        )
    print(
        "PASS: historical contracts, independent source/count/identity packet and selected artifact checks"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", action="store_true")
    check(parser.parse_args().artifacts)
