import json
import os
import threading

class SpanStore:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._spans: list[dict] = []
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def add(self, span: dict) -> None:
        with self._lock:
            self._spans.append(span)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(span) + "\n")

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._spans)

    def by_trace_id(self, trace_id: str) -> list[dict]:
        with self._lock:
            return [s for s in self._spans if s["trace_id"] == trace_id]