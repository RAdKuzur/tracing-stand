import os
import sys
import pytest

# чтобы `from src...` работал при запуске pytest из trace-collector/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage.span_store import SpanStore


@pytest.fixture
def tmp_store(tmp_path):
    """SpanStore с временным файлом, изолированный от /data."""
    return SpanStore(str(tmp_path / "spans.jsonl"))


@pytest.fixture
def sample_span():
    return {
        "trace_id": "814c0dc5573cd646cdfb9f1a97a47f2c",
        "span_id": "5ae5b85246fa251d",
        "parent_span_id": "39f2e4dcfea7f9fe",
        "name": "service-b-work",
        "service_name": "service-b",
        "start_time_unix_nano": 1795544129995150600,
        "end_time_unix_nano": 1795544130005482800,
    }