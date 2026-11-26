import json
import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import requests

from auth import (
    can,
    make_session,
    verify_session,
    parse_cookie,
    ROLE_LABELS,
)

COLLECTOR = os.getenv("COLLECTOR_URL", "http://trace-collector:4318")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
USERS_PATH = os.getenv("USERS_PATH", "/app/config/users.json")
PUBLIC_PATHS = {"/login.html", "/login.css", "/login.js"}


def load_users() -> dict:
    with open(USERS_PATH, encoding="utf-8") as f:
        return json.load(f)


USERS = load_users()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)
    def _session(self):
        cookies = parse_cookie(self.headers.get("Cookie"))
        return verify_session(cookies.get("session"))

    def _send_json(self, code: int, payload: dict, extra_headers: dict | None = None):
        body = json.dumps(payload).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _redirect(self, location: str, code: int = 302):
        try:
            self.send_response(code)
            self.send_header("Location", location)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_body(self) -> bytes:
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/login":
            body = self._read_body()
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                return self._send_json(400, {"error": "invalid json"})

            username = data.get("username", "")
            user = USERS.get(username)
            if not user:
                return self._send_json(401, {"error": "unknown user"})

            token = make_session(username, user["role"])
            cookie = f"session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(json.dumps({
                "user": username,
                "display_name": user["display_name"],
                "role": user["role"],
                "role_label": ROLE_LABELS.get(user["role"], user["role"]),
            }).encode())
            return

        if parsed.path == "/api/logout":
            self.send_response(200)
            self.send_header("Set-Cookie", "session=; Path=/; Max-Age=0")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        return self._send_json(404, {"error": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in PUBLIC_PATHS:
            return super().do_GET()

        if parsed.path == "/api/users":
            return self._send_json(200, {
                "users": [
                    {
                        "username": u,
                        "display_name": v["display_name"],
                        "role": v["role"],
                        "role_label": ROLE_LABELS.get(v["role"], v["role"]),
                    }
                    for u, v in USERS.items()
                ]
            })

        session = self._session()
        if not session:
            if parsed.path.startswith("/api/"):
                return self._send_json(401, {"error": "unauthorized"})
            return self._redirect("/login.html")

        if parsed.path == "/api/me":
            return self._send_json(200, {
                "user": session["user"],
                "role": session["role"],
                "role_label": ROLE_LABELS.get(session["role"], session["role"]),
            })

        if parsed.path.startswith("/api/"):
            action, target = self._map_api(parsed.path)
            if action is None:
                return self._send_json(404, {"error": "unknown api"})
            if not can(session["role"], action):
                return self._send_json(
                    403, {"error": f"role {session['role']} cannot {action}"}
                )

            url = COLLECTOR + target
            if parsed.query:
                url += "?" + parsed.query
            headers = {"X-User": session["user"], "X-Role": session["role"]}
            try:
                r = requests.get(url, timeout=15, headers=headers)
                self.send_response(r.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Auth-User", session["user"])
                self.send_header("X-Auth-Role", session["role"])
                self.end_headers()
                self.wfile.write(r.content)
            except requests.RequestException as e:
                self._send_json(502, {"error": str(e)})
            return

        return super().do_GET()

    @staticmethod
    def _map_api(path: str) -> tuple:
        if path == "/api/spans":
            return "spans:read", "/spans"
        if path == "/api/audit/logs":
            return "audit:read", "/audit/logs"
        if path == "/api/healthz":
            return "spans:read", "/healthz"
        if path == "/api/readyz":
            return "spans:read", "/readyz"
        return None, ""

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("UI_PORT", "8080"))
    print(f"UI listening on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()