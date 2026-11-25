import json
import pytest
from src.ingest.json_decoder import decode_span


def test_decode_valid(sample_span):
    raw = json.dumps(sample_span).encode()
    assert decode_span(raw) == sample_span


def test_decode_with_defaults():
    raw = json.dumps({
        "trace_id": "a" * 32, "span_id": "b" * 16,
        "name": "t", "service_name": "s",
    }).encode()
    d = decode_span(raw)
    assert d["kind"] == "INTERNAL"
    assert d["status"] == "UNSET"
    assert d["attributes"] == {}
    assert d["events"] == []
    assert d["links"] == []


@pytest.mark.parametrize("raw,match", [
    (b"{not json}", "invalid json"),
    (b'["array"]', "must be an object"),
    (b'{"trace_id":"' + b"a"*32 + b'","span_id":"' + b"b"*16 + b'"}', "missing field: name"),
])
def test_decode_errors(raw, match):
    with pytest.raises(ValueError, match=match):
        decode_span(raw)


@pytest.mark.parametrize("field,bad_value,match", [
    ("trace_id", "abc", "trace_id must be 32 hex chars"),
    ("trace_id", "Z"*32, "trace_id must be 32 hex chars"),
    ("span_id", "xyz", "span_id must be 16 hex chars"),
    ("span_id", "Z"*16, "span_id must be 16 hex chars"),
])
def test_decode_bad_ids(sample_span, field, bad_value, match):
    data = dict(sample_span, **{field: bad_value})
    with pytest.raises(ValueError, match=match):
        decode_span(json.dumps(data).encode())


def test_decode_normalizes_bad_status(sample_span):
    data = dict(sample_span, status="WEIRD")
    d = decode_span(json.dumps(data).encode())
    assert d["status"] == "UNSET"