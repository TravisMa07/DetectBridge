"""Version-1 evidence identity; processing and replay identity are excluded."""

import hashlib
import json


def identity_hash(parts: list) -> str:
    def valid(value):
        return isinstance(value, str) or (isinstance(value, list) and all(valid(v) for v in value))

    if not valid(parts):
        raise ValueError("invalid_identity_input")
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_id(source: dict, cursor: dict) -> str:
    kind = cursor["kind"]
    if kind == "dataset":
        position = cursor["position"]
        if type(position) is not int or position < 0:
            raise ValueError("invalid_record_position")
        token = [kind, cursor["artifact_sha256"], str(position)]
    elif kind == "native":
        token = [kind, cursor["value"]]
    elif kind == "capture":
        token = [kind, cursor["id"]]
    else:
        raise ValueError("unsupported_cursor")
    return identity_hash([source["namespace"], source["instance"], token])


def event_id(source: dict, records: list[str]) -> str:
    if not records or len(records) != len(set(records)):
        raise ValueError("invalid_membership")
    return identity_hash([source["namespace"], source["instance"], sorted(records)])
