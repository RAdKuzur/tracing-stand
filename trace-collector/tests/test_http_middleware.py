import pytest
from src.ingest.http_middleware import check_content_type, validate_content_length


@pytest.mark.parametrize("header", [
    "application/json",
    "application/json; charset=utf-8",
    "application/json;charset=utf-8",
    "APPLICATION/JSON",
    "application/json; boundary=xxx",
])
def test_content_type_ok(header):
    ok, msg = check_content_type(header)
    assert ok and msg == ""


@pytest.mark.parametrize("header", [
    None, "", "text/plain", "application/x-protobuf", "application/xml",
])
def test_content_type_rejected(header):
    ok, msg = check_content_type(header)
    assert not ok and msg


@pytest.mark.parametrize("header,expected", [
    ("100", True),
    ("1048576", True),
    ("1048577", False),
    ("0", False),
    ("-1", False),
    ("abc", False),
    (None, False),
])
def test_content_length(header, expected):
    ok, _ = validate_content_length(header)
    assert ok == expected