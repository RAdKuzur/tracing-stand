import time
import pytest
from auth import (
    can, make_session, verify_session, parse_cookie,
    ROLE_MATRIX, ROLE_LABELS,
)


def test_role_matrix_complete():
    assert set(ROLE_MATRIX.keys()) == {"SRE", "DEV", "ADMIN", "AUDITOR"}
    for role, actions in ROLE_MATRIX.items():
        assert "spans:read" in actions, f"{role} must read spans"


@pytest.mark.parametrize("role,action,expected", [
    ("SRE",     "spans:read",  True),
    ("SRE",     "audit:read",  True),
    ("SRE",     "pii:read",    True),
    ("SRE",     "policies:write", False),
    ("DEV",     "spans:read",  True),
    ("DEV",     "audit:read",  False),
    ("ADMIN",   "audit:read",  True),
    ("ADMIN",   "policies:write", True),
    ("AUDITOR", "audit:read",  True),
    ("AUDITOR", "policies:write", False),
])
def test_can(role, action, expected):
    assert can(role, action) is expected


def test_can_unknown_role():
    assert can("HACKER", "spans:read") is False


def test_make_and_verify():
    token = make_session("ivanov_sre", "SRE")
    assert "." in token
    data = verify_session(token)
    assert data == {"user": "ivanov_sre", "role": "SRE"}


def test_verify_tampered():
    token = make_session("ivanov_sre", "SRE")
    payload, sig = token.split(".")
    # подменяем payload (роль) — подпись не сойдётся
    bad = payload[::-1] + "." + sig
    assert verify_session(bad) is None


def test_verify_garbage():
    assert verify_session(None) is None
    assert verify_session("") is None
    assert verify_session("no-dot") is None
    assert verify_session("aa.bb") is None


def test_parse_cookie():
    assert parse_cookie(None) == {}
    assert parse_cookie("") == {}
    assert parse_cookie("a=1; b=2") == {"a": "1", "b": "2"}
    assert parse_cookie("session=abc; Path=/") == {"session": "abc", "Path": "/"}


def test_role_labels_cover_all():
    for role in ROLE_MATRIX:
        assert role in ROLE_LABELS