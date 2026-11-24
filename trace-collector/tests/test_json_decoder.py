import json
import pytest
from src.ingest.json_decoder import decode_span


def test_decode_valid_span(sample_span):
    raw = json.dumps(sample_span).encode()
    assert decode_span(raw) == sample_span


def test_decode_invalid_json():
    with pytest.raises(ValueError, match="invalid json"):
        decode_span(b"{not json}")


def test_decode_not_object():
    with pytest.raises(ValueError, match="must be an object"):
        decode_span(b'["array"]')


@pytest.mark.parametrize("missing", ["trace_id", "span_id", "name", "service_name"])
def test_decode_missing_field(sample_span, missing):
    data = dict(sample_span)
    del data[missing]
    with pytest.raises(ValueError, match=f"missing field: {missing}"):
        decode_span(json.dumps(data).encode())


def test_decode_bad_trace_id_length(sample_span):
    data = dict(sample_span, trace_id="abc")
    with pytest.raises(ValueError, match="trace_id must be 32 hex chars"):
        decode_span(json.dumps(data).encode())


def test_decode_bad_span_id_length(sample_span):
    data = dict(sample_span, span_id="xyz")
    with pytest.raises(ValueError, match="span_id must be 16 hex chars"):
        decode_span(json.dumps(data).encode())


def test_decode_non_hex_trace_id(sample_span):
    data = dict(sample_span, trace_id="Z" * 32)
    with pytest.raises(ValueError, match="trace_id must be 32 hex chars"):
        decode_span(json.dumps(data).encode())