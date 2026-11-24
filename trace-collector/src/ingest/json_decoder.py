"""Декодирование JSON-спанов."""
import json

REQUIRED = ("trace_id", "span_id", "name", "service_name")

def decode_span(raw: bytes) -> dict:
    """Парсит байты в dict, проверяет обязательные поля. Бросает ValueError."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid json: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("span must be an object")

    for key in REQUIRED:
        if key not in data:
            raise ValueError(f"missing field: {key}")

    if len(data["trace_id"]) != 32 or not all(c in "0123456789abcdef" for c in data["trace_id"]):
        raise ValueError("trace_id must be 32 hex chars")
    if len(data["span_id"]) != 16 or not all(c in "0123456789abcdef" for c in data["span_id"]):
        raise ValueError("span_id must be 16 hex chars")

    return data