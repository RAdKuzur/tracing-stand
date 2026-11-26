import json

REQUIRED = ("trace_id", "span_id", "name", "service_name")

DEFAULTS = {
    "parent_span_id": None,
    "kind": "INTERNAL",
    "status": "UNSET",
    "attributes": {},
    "events": [],
    "links": [],
    "start_time_unix_nano": 0,
    "end_time_unix_nano": 0,
}


def decode_span(raw: bytes) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid json: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("span must be an object")

    for key in REQUIRED:
        if key not in data:
            raise ValueError(f"missing field: {key}")

    tid, sid = data["trace_id"], data["span_id"]
    if len(tid) != 32 or not all(c in "0123456789abcdef" for c in tid):
        raise ValueError("trace_id must be 32 hex chars")
    if len(sid) != 16 or not all(c in "0123456789abcdef" for c in sid):
        raise ValueError("span_id must be 16 hex chars")

    for key, default in DEFAULTS.items():
        data.setdefault(key, default)

    if data["status"] not in ("OK", "ERROR", "UNSET"):
        data["status"] = "UNSET"

    return data