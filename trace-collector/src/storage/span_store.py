"""SQLite-хранилище спанов с индексами, дедупликацией и retention."""
import json
import os
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS span (
    trace_id       TEXT NOT NULL,
    span_id        TEXT NOT NULL,
    parent_span_id TEXT,
    service_name   TEXT NOT NULL,
    name           TEXT NOT NULL,
    kind           TEXT NOT NULL,
    start_time_ns  INTEGER NOT NULL,
    end_time_ns    INTEGER NOT NULL,
    status         TEXT NOT NULL,
    attributes     TEXT,
    events         TEXT,
    links          TEXT,
    received_at    INTEGER NOT NULL,
    PRIMARY KEY (trace_id, span_id)
);
CREATE INDEX IF NOT EXISTS idx_span_trace   ON span(trace_id);
CREATE INDEX IF NOT EXISTS idx_span_service ON span(service_name, start_time_ns);
CREATE INDEX IF NOT EXISTS idx_span_status  ON span(status, start_time_ns);
"""


class SpanStore:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()

    def add(self, span: dict) -> bool:
        """Возвращает True, если спан добавлен; False — если дубликат."""
        with self._lock:
            try:
                self._db.execute(
                    "INSERT INTO span VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        span["trace_id"], span["span_id"], span.get("parent_span_id"),
                        span["service_name"], span["name"], span["kind"],
                        span["start_time_unix_nano"], span["end_time_unix_nano"],
                        span["status"],
                        json.dumps(span.get("attributes", {})),
                        json.dumps(span.get("events", [])),
                        json.dumps(span.get("links", [])),
                        int(time.time()),
                    ),
                )
                self._db.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def search(self, trace_id=None, service=None, status=None,
               min_duration_ns=None, limit=1000):
        """Возвращает (spans, total, truncated)."""
        where, args = ["1=1"], []
        if trace_id:
            where.append("trace_id = ?"); args.append(trace_id)
        if service:
            where.append("service_name = ?"); args.append(service)
        if status:
            where.append("status = ?"); args.append(status)
        if min_duration_ns is not None:
            where.append("(end_time_ns - start_time_ns) >= ?"); args.append(min_duration_ns)

        w = " AND ".join(where)
        with self._lock:
            total = self._db.execute(f"SELECT COUNT(*) FROM span WHERE {w}", args).fetchone()[0]
            rows = self._db.execute(
                f"SELECT * FROM span WHERE {w} ORDER BY start_time_ns ASC LIMIT ?",
                args + [limit],
            ).fetchall()
        return [self._row(r) for r in rows], total, total > limit

    def all(self, limit=1000):
        return self.search(limit=limit)

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM span").fetchone()[0]

    def apply_retention(self, hot_days: int = 7) -> int:
        cutoff = int((time.time() - hot_days * 86400) * 1e9)
        with self._lock:
            cur = self._db.execute("DELETE FROM span WHERE start_time_ns < ?", (cutoff,))
            self._db.commit()
            return cur.rowcount

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        return {
            "trace_id": r["trace_id"],
            "span_id": r["span_id"],
            "parent_span_id": r["parent_span_id"],
            "service_name": r["service_name"],
            "name": r["name"],
            "kind": r["kind"],
            "start_time_unix_nano": r["start_time_ns"],
            "end_time_unix_nano": r["end_time_ns"],
            "status": r["status"],
            "attributes": json.loads(r["attributes"] or "{}"),
            "events": json.loads(r["events"] or "[]"),
            "links": json.loads(r["links"] or "[]"),
        }