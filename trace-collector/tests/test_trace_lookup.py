import pytest
from src.query.trace_lookup import lookup


def test_lookup_valid(tmp_store, sample_span):
    tmp_store.add(sample_span)
    result = lookup(tmp_store, sample_span["trace_id"])
    assert result == [sample_span]


def test_lookup_short_trace_id_raises(tmp_store):
    with pytest.raises(ValueError, match="32 hex chars"):
        lookup(tmp_store, "abc")


def test_lookup_empty_result(tmp_store):
    assert lookup(tmp_store, "c" * 32) == []