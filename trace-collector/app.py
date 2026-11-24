"""HTTP-сервер OTLP-коллектора на :4318."""
import json
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.ingest.json_decoder import decode_span
from src.ingest.header_parser import parse_traceparent
from src.storage.span_store import SpanStore
from src.query.trace_lookup import lookup

STORE = SpanStore(os.getenv("SPAN_STORAGE_PATH", "/data/spans.jsonl"))


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
            # клиент закрыл соединение раньше, чем мы успели ответить
            pass

    def do_POST(self):
        if self.path != "/v1/traces":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            span = decode_span(raw)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        tp = self.headers.get("traceparent")
        if tp and parse_traceparent(tp) is None:
            return self._send(400, {"error": "invalid traceparent"})
        STORE.add(span)
        return self._send(200, {"status": "ok"})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/spans":
            qs = parse_qs(parsed.query)
            if "trace_id" in qs:
                try:
                    return self._send(200, {"spans": lookup(STORE, qs["trace_id"][0])})
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
            try:
                limit = int(qs.get("limit", ["1000"])[0])
            except ValueError:
                return self._send(400, {"error": "limit must be integer"})
            return self._send(200, {"spans": STORE.all()[:limit]})
        return self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("COLLECTOR_PORT", "4318"))
    print(f"Trace Collector listening on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()