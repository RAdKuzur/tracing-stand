"""Аутентификация (cookie-сессия) и RBAC для trace-ui."""
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional


SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-me").encode()
SESSION_TTL = 8 * 3600  # 8 часов


# Матрица прав: роль → набор действий
ROLE_MATRIX = {
    "SRE":     {"spans:read", "audit:read", "pii:read"},
    "DEV":     {"spans:read"},
    "ADMIN":   {"spans:read", "audit:read", "policies:write", "pii:read"},
    "AUDITOR": {"spans:read", "audit:read", "pii:read"},
}

ROLE_LABELS = {
    "SRE": "SRE",
    "DEV": "Разработчик",
    "ADMIN": "Администратор",
    "AUDITOR": "Аудитор безопасности",
}


def can(role: str, action: str) -> bool:
    return action in ROLE_MATRIX.get(role, set())


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def make_session(username: str, role: str) -> str:
    """Создаёт подписанный токен: base64(payload).base64(hmac)."""
    payload = json.dumps({
        "user": username, "role": role, "exp": int(time.time()) + SESSION_TTL,
    }).encode()
    sig = hmac.new(SECRET, payload, hashlib.sha256).digest()
    return f"{_b64e(payload)}.{_b64e(sig)}"


def verify_session(token: Optional[str]) -> Optional[dict]:
    """Возвращает {'user','role'} или None, если токен невалиден/просрочен."""
    if not token or "." not in token:
        return None
    try:
        p_b64, s_b64 = token.split(".", 1)
        payload = _b64d(p_b64)
        sig = _b64d(s_b64)
    except Exception:
        return None
    expected = hmac.new(SECRET, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(payload)
    except Exception:
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    return {"user": data["user"], "role": data["role"]}


def parse_cookie(header: Optional[str]) -> dict:
    if not header:
        return {}
    out = {}
    for part in header.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            out[k] = v
    return out