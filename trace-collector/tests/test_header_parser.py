import pytest
from src.ingest.header_parser import parse_traceparent


def test_valid_traceparent():
    result = parse_traceparent("00-814c0dc5573cd646cdfb9f1a97a47f2c-5ae5b85246fa251d-01")
    assert result == {
        "trace_id": "814c0dc5573cd646cdfb9f1a97a47f2c",
        "span_id": "5ae5b85246fa251d",
        "flags": "01",
    }


@pytest.mark.parametrize("bad", [
    "",
    None,
    "00-814c0dc5573cd646cdfb9f1a97a47f2c-5ae5b85246fa251d",       # нет flags
    "00-814c0dc5573cd646cdfb9f1a97a47f2c-5ae5b85246fa251d-01-extra",  # лишнее
    "00-814c0dc5573cd646cdfb9f1a97a47f2-5ae5b85246fa251d-01",      # trace_id короче
    "00-814c0dc5573cd646cdfb9f1a97a47f2c-5ae5b85246fa251-01",      # span_id короче
    "00-ZZZZ0dc5573cd646cdfb9f1a97a47f2c-5ae5b85246fa251d-01",     # не hex
])
def test_invalid_traceparent(bad):
    assert parse_traceparent(bad) is None