#!/usr/bin/env python3
"""Экспресс-проверка стенда: поднять compose, загрузить фикстуру, сверить."""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(ROOT, "fixtures", "seed_data.json")
COLLECTOR = os.getenv("COLLECTOR_URL", "http://localhost:4318")
SERVICE_A = os.getenv("SERVICE_A_URL", "http://localhost:8081")
UI = os.getenv("UI_URL", "http://localhost:8080")

EXPECTED_TRACES = 5
EXPECTED_SPANS = 10
EXPECTED_ERROR_TRACES = 2  # 2222 (service-a) и 5555 (payment-service)


def log(msg: str) -> None:
    print(f"[verify] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"[verify] FAIL: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def http_get(url: str, headers=None, timeout=5):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        return None, str(e).encode()


def http_post_json(url: str, body: dict, headers=None, timeout=5):
    data = json.dumps(body).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def wait_healthy(url: str, name: str, tries: int = 30, delay: float = 1.0) -> None:
    log(f"waiting for {name} at {url} ...")
    for i in range(tries):
        code, _ = http_get(url, timeout=2)
        if code == 200:
            log(f"{name} is up (attempt {i+1})")
            return
        time.sleep(delay)
    fail(f"{name} not healthy after {tries} attempts")


def compose_up() -> None:
    log("docker compose up -d --build")
    r = subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        fail("docker compose up failed")


def load_fixture() -> int:
    log(f"loading fixture {FIXTURE}")
    with open(FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    spans = data["spans"]
    ok, dup, err = 0, 0, 0
    for s in spans:
        code, body = http_post_json(f"{COLLECTOR}/v1/traces", s)
        if code == 200:
            resp = json.loads(body)
            if resp.get("status") == "ok":
                ok += 1
            elif resp.get("status") == "duplicate":
                dup += 1
        else:
            err += 1
            print(f"  span {s['span_id']}: {code} {body[:200]}", file=sys.stderr)
    log(f"fixture: {ok} added, {dup} duplicate, {err} errors (total {len(spans)})")
    if err > 0:
        fail(f"{err} spans failed to load")
    return ok + dup


def check_traces() -> None:
    log("checking /spans (all)")
    code, body = http_get(f"{COLLECTOR}/spans?limit=10000")
    if code != 200:
        fail(f"GET /spans returned {code}")
    data = json.loads(body)
    spans = data["spans"]
    trace_ids = {s["trace_id"] for s in spans}

    # фикстура + реальные спаны от Go-сервисов; проверяем, что все 5 трейсов фикстуры на месте
    fixture_ids = {
        "11111111111111111111111111111111",
        "22222222222222222222222222222222",
        "33333333333333333333333333333333",
        "44444444444444444444444444444444",
        "55555555555555555555555555555555",
    }
    missing = fixture_ids - trace_ids
    if missing:
        fail(f"missing fixture traces: {sorted(missing)}")
    log(f"all {len(fixture_ids)} fixture traces present (total traces in DB: {len(trace_ids)})")


def check_errors() -> None:
    log("checking /spans?status=ERROR")
    code, body = http_get(f"{COLLECTOR}/spans?status=ERROR&limit=10000")
    if code != 200:
        fail(f"GET /spans?status=ERROR returned {code}")
    data = json.loads(body)
    error_trace_ids = {s["trace_id"] for s in data["spans"]}
    expected = {
        "22222222222222222222222222222222",
        "55555555555555555555555555555555",
    }
    missing = expected - error_trace_ids
    if missing:
        fail(f"missing ERROR traces: {sorted(missing)}")
    log(f"ERROR filter works: {len(error_trace_ids)} traces with errors")


def check_service_filter() -> None:
    log("checking /spans?service=payment-service")
    code, body = http_get(f"{COLLECTOR}/spans?service=payment-service&limit=10000")
    if code != 200:
        fail(f"GET /spans?service=payment-service returned {code}")
    data = json.loads(body)
    if not data["spans"]:
        fail("no spans for payment-service")
    services = {s["service_name"] for s in data["spans"]}
    if services != {"payment-service"}:
        fail(f"expected only payment-service, got {services}")
    log(f"service filter works: {len(data['spans'])} spans")


def check_masking() -> None:
    log("checking PII masking")
    code, body = http_get(f"{COLLECTOR}/spans?trace_id=22222222222222222222222222222222")
    if code != 200:
        fail(f"GET trace 2222 returned {code}")
    spans = json.loads(body)["spans"]
    for s in spans:
        attrs = s.get("attributes") or {}
        if "user.email" in attrs and attrs["user.email"] != "***":
            fail(f"user.email not masked in {s['span_id']}: {attrs['user.email']}")

    code, body = http_get(f"{COLLECTOR}/spans?trace_id=55555555555555555555555555555555")
    spans = json.loads(body)["spans"]
    for s in spans:
        attrs = s.get("attributes") or {}
        if "http.request.header.authorization" in attrs:
            fail(f"authorization header not dropped in {s['span_id']}")
        if "user.password" in attrs:
            fail(f"user.password not dropped in {s['span_id']}")
    log("PII masking works (drop + mask)")


def check_metrics() -> None:
    log("checking /metrics")
    code, body = http_get(f"{COLLECTOR}/metrics")
    if code != 200:
        fail(f"GET /metrics returned {code}")
    text = body.decode()
    if "spans_total" not in text:
        fail("metrics: spans_total missing")
    log("metrics endpoint ok")


def check_audit_rbac() -> None:
    log("checking /audit/logs RBAC")
    # без роли — 403
    code, _ = http_get(f"{COLLECTOR}/audit/logs")
    if code != 403:
        fail(f"/audit/logs without X-Role returned {code}, expected 403")
    # с AUDITOR — 200
    code, body = http_get(f"{COLLECTOR}/audit/logs", headers={"X-Role": "AUDITOR"})
    if code != 200:
        fail(f"/audit/logs as AUDITOR returned {code}")
    logs = json.loads(body)["logs"]
    if not logs:
        fail("/audit/logs returned empty (expected SEARCH entries from previous checks)")
    if "hash" not in logs[0]:
        fail("/audit/logs entry missing hash")
    log(f"RBAC + audit works: {len(logs)} entries, hash-chain present")


def check_service_a() -> None:
    log(f"calling {SERVICE_A}/ (Go service-a → service-b)")
    code, body = http_get(f"{SERVICE_A}/", timeout=10)
    if code != 200:
        fail(f"service-a returned {code}")
    trace = json.loads(body)
    if "trace_id" not in trace:
        fail("service-a response missing trace_id")
    time.sleep(0.5)  # дождаться асинхронной отправки спанов
    tid = trace["trace_id"]
    code, body = http_get(f"{COLLECTOR}/spans?trace_id={tid}")
    if code != 200:
        fail(f"GET /spans?trace_id={tid} returned {code}")
    spans = json.loads(body)["spans"]
    if len(spans) != 2:
        fail(f"expected 2 spans in trace {tid}, got {len(spans)}")
    services = {s["service_name"] for s in spans}
    if services != {"service-a", "service-b"}:
        fail(f"expected service-a + service-b, got {services}")
    log(f"service-a → service-b works: trace {tid[:8]}… has 2 spans")


def check_ui_available() -> None:
    log(f"checking UI at {UI}/login.html")
    code, _ = http_get(f"{UI}/login.html", timeout=5)
    if code != 200:
        fail(f"UI /login.html returned {code}")
    log("UI login page available")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["local", "ci"], default="local",
                        help="local: поднять compose; ci: считать, что уже поднято")
    parser.add_argument("--skip-e2e", action="store_true",
                        help="пропустить проверку service-a → service-b")
    args = parser.parse_args()

    print("=" * 60)
    print("  Express verification of tracing-stand")
    print("=" * 60)

    if args.mode == "local":
        compose_up()

    wait_healthy(f"{COLLECTOR}/healthz", "trace-collector")
    wait_healthy(f"{COLLECTOR}/readyz", "trace-collector readyz")
    if not args.skip_e2e:
        wait_healthy(f"{SERVICE_A}/healthz", "service-a", tries=15)
    if os.getenv("CHECK_UI", "1") == "1":
        wait_healthy(f"{UI}/login.html", "trace-ui", tries=15)

    load_fixture()
    check_traces()
    check_errors()
    check_service_filter()
    check_masking()
    check_metrics()
    check_audit_rbac()
    if not args.skip_e2e:
        check_service_a()
    if os.getenv("CHECK_UI", "1") == "1":
        check_ui_available()

    print("=" * 60)
    print("  ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()