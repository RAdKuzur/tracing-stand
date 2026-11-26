import json
import logging
import os
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.ingest.json_decoder import decode_span
from src.ingest.header_parser import parse_traceparent
from src.ingest.http_middleware import check_content_type, validate_content_length
from src.storage.span_store import SpanStore
from src.query.trace_lookup import lookup
from src.policy import masking
from src.audit.audit_log import AuditLog


class JsonFormatter(logging.Formatter):
    def format(self, r):
        return json.dumps({
            "ts": self.formatTime(r),
            "level": r.levelname,
            "msg": r.getMessage(),
        })


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("collector")


DB_PATH = os.getenv("SPAN_DB_PATH", "/data/spans.db")
AUDIT_PATH = os.getenv("AUDIT_LOG_PATH", "/data/audit.jsonl")
STORE = SpanStore(DB_PATH)
AUDIT = AuditLog(AUDIT_PATH)
MASK_RULES = masking.load_rules()

REJECTED = {"total": 0, "by_reason": {}}


def _reject(reason: str) -> None:
    REJECTED["total"] += 1
    REJECTED["by_reason"][reason] = REJECTED["by_reason"].get(reason, 0) + 1


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_raw(self, code: int, body: bytes, ctype: str) -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _role(self) -> str:
        return self.headers.get("X-Role", "viewer")

    def do_POST(self):
        if self.path != "/v1/traces":
            return self._send(404, {"error": "not found"})

        ok, msg = check_content_type(self.headers.get("Content-Type"))
        if not ok:
            _reject("bad_content_type")
            return self._send(415, {"error": msg})

        ok, msg = validate_content_length(self.headers.get("Content-Length"))
        if not ok:
            _reject("bad_content_length")
            return self._send(400, {"error": msg})

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            span = decode_span(raw)
        except ValueError as e:
            _reject(str(e))
            return self._send(400, {"error": str(e)})

        tp = self.headers.get("traceparent")
        if tp and parse_traceparent(tp) is None:
            _reject("invalid_traceparent")
            return self._send(400, {"error": "invalid traceparent"})

        span = masking.apply(span, MASK_RULES)
        if not STORE.add(span):
            return self._send(200, {"status": "duplicate"})
        return self._send(200, {"status": "ok"})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/healthz":
            return self._send(200, {"status": "ok"})
        if parsed.path == "/readyz":
            return self._send(200, {"ready": True})
        if parsed.path == "/metrics":
            lines = [
                "# TYPE spans_total counter",
                f"spans_total {STORE.count()}",
                "# TYPE spans_rejected_total counter",
                f"spans_rejected_total {REJECTED['total']}",
            ]
            for reason, n in REJECTED["by_reason"].items():
                lines.append(f'spans_rejected_total{{reason="{reason}"}} {n}')
            body = ("\n".join(lines) + "\n").encode()
            return self._send_raw(200, body, "text/plain; version=0.0.4")

        if parsed.path == "/spans":
            qs = parse_qs(parsed.query)
            trace_id = qs.get("trace_id", [None])[0]
            service = qs.get("service", [None])[0]
            status = qs.get("status", [None])[0]
            try:
                limit = int(qs.get("limit", ["1000"])[0])
                min_dur_ms = qs.get("min_duration_ms", [None])[0]
                min_dur_ns = int(float(min_dur_ms) * 1e6) if min_dur_ms else None
            except ValueError:
                return self._send(400, {"error": "invalid numeric parameter"})

            role = self._role()
            AUDIT.append(
                user=self.headers.get("X-User", "anonymous"),
                role=role,
                op="SEARCH",
                params={
                    "trace_id": trace_id,
                    "service": service,
                    "status": status,
                    "limit": limit,
                    "min_duration_ms": min_dur_ms,
                },
            )

            if trace_id:
                try:
                    spans = lookup(STORE, trace_id)
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {
                    "spans": spans,
                    "total": len(spans),
                    "truncated": False,
                })

            spans, total, truncated = STORE.search(
                service=service,
                status=status,
                min_duration_ns=min_dur_ns,
                limit=limit,
            )
            return self._send(200, {
                "spans": spans,
                "total": total,
                "truncated": truncated,
            })

        if parsed.path == "/audit/logs":
            role = self._role()
            if role not in ("ADMIN", "AUDITOR"):
                return self._send(403, {"error": "forbidden"})
            return self._send(200, {"logs": AUDIT.read_all()})

        return self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def _retention_worker():
    while True:
        time.sleep(3600)
        try:
            n = STORE.apply_retention(hot_days=7)
            log.info(f"retention: removed {n} old spans")
        except Exception as e:
            log.error(f"retention failed: {e}")


if __name__ == "__main__":
    port = int(os.getenv("COLLECTOR_PORT", "4318"))
    threading.Thread(target=_retention_worker, daemon=True).start()
    log.info(f"Trace Collector listening on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()