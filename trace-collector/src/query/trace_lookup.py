from src.storage.span_store import SpanStore


def lookup(store: SpanStore, trace_id: str) -> list[dict]:
    if len(trace_id) != 32:
        raise ValueError("trace_id must be 32 hex chars")
    spans, _, _ = store.search(trace_id=trace_id, limit=100000)
    return spans