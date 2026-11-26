import hashlib
import json
import os
import threading
import time


class AuditLog:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not os.path.exists(self._path):
            return "0" * 64
        with open(self._path, encoding="utf-8") as f:
            last = ""
            for line in f:
                last = line.strip()
        if not last:
            return "0" * 64
        return json.loads(last).get("hash", "0" * 64)

    def append(self, user: str, role: str, op: str, params: dict) -> dict:
        entry = {
            "ts": time.time(),
            "user": user,
            "role": role,
            "op": op,
            "params": params,
        }
        payload = json.dumps(entry, sort_keys=True)
        h = hashlib.sha256((self._last_hash + payload).encode()).hexdigest()
        entry["hash"] = h
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            self._last_hash = h
        return entry

    def read_all(self) -> list[dict]:
        if not os.path.exists(self._path):
            return []
        with open(self._path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]