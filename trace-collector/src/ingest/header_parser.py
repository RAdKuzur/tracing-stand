"""Разбор и валидация заголовка W3C traceparent."""
import re

TRACEPARENT_RE = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)

def parse_traceparent(header: str) -> dict | None:
    """Возвращает {'trace_id', 'span_id', 'flags'} или None при ошибке."""
    if not header:
        return None
    m = TRACEPARENT_RE.match(header.strip())
    if not m:
        return None
    _version, trace_id, span_id, flags = m.groups()
    return {"trace_id": trace_id, "span_id": span_id, "flags": flags}