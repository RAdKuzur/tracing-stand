import json
import os
import socket
import threading
import time
import urllib.request
import urllib.error
import pytest


@pytest.fixture(scope="module")
def collector_server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("collector")
    os.environ["SPAN_DB_PATH"] = str(tmp / "spans.db")
    os.environ["AUDIT_LOG_PATH"] = str(tmp / "audit.jsonl")
    os.environ["MASKING_RULES_PATH"] = str(tmp / "rules.json")

    (tmp / "rules.json").write_text(json.dumps({
        "drop_keys": ["secret"],
        "mask_keys": ["user.email"],
        "mask_value": "***",
    }))

    # ВАЖНО: импорт после установки os.environ, без reload
    import app as collector_app
    from http.server import ThreadingHTTPServer

    # свободный порт
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    server = ThreadingHTTPServer(("127.0.0.1", port), collector_app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    yield f"http://127.0.0.1:{port}"
    server.shutdown()