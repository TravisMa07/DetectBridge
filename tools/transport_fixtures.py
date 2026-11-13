"""Temporary synthetic acquisition objects for transport qualification only.

Catalog shapes are copied to exercise the real P04/P05 verification path. The
substituted objects are invented bytes, not attested upstream acquisitions.
"""

import copy
import hashlib

from check_datasets import load_catalog
from datasets import object_path


def catalog(cache):
    originals = load_catalog()
    ids = ["linux-audit-whoami", "windows-security-4688"]
    result = {name: copy.deepcopy(originals[name]) for name in ids}

    def store(resource, data):
        resource["sha256"] = hashlib.sha256(data).hexdigest()
        resource["size_bytes"] = len(data)
        path = object_path(cache, resource)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    for name, manifest in result.items():
        body = (
            b"".join(f"synthetic-{index}\r\n".encode() for index in range(120)) + b"\nunterminated"
            if name.startswith("linux")
            else b"<synthetic/>\n"
        )
        store(manifest["payload"], body)
        manifest["framing"]["record_count"] = len(body.splitlines())
        for resource in manifest["provenance"]:
            if resource["role"] == "lfs_pointer":
                payload = manifest["payload"]
                value = f"version https://git-lfs.github.com/spec/v1\noid sha256:{payload['sha256']}\nsize {payload['size_bytes']}\n".encode()
            else:
                value = (
                    "Original synthetic qualification provenance: " + resource["role"]
                ).encode()
            store(resource, value)
    return result
