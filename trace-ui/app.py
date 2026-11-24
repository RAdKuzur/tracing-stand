"""UI-сервер: статика + прокси к trace-collector."""
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import requests

COLLECTOR = os.getenv("COLLECTOR_URL", "http://trace-collector:4318")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

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

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            target = COLLECTOR + parsed.path[4:]  # /api/spans -> /spans
            if parsed.query:
                target += "?" + parsed.query
            try:
                r = requests.get(target, timeout=5)
                self.send_response(r.status_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(r.content)
            except requests.RequestException as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(f'{{"error":"{e}"}}'.encode())
            return
        # всё остальное — статика
        return super().do_GET()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("UI_PORT", "8080"))
    print(f"UI listening on :{port}", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()