def test_add_and_search(tmp_store, sample_span):
    assert tmp_store.add(sample_span) is True
    spans, total, truncated = tmp_store.search(trace_id=sample_span["trace_id"])
    assert len(spans) == 1
    assert total == 1
    assert truncated is False
    assert spans[0]["service_name"] == "service-b"
    assert spans[0]["attributes"]["http.method"] == "GET"


def test_duplicate_rejected(tmp_store, sample_span):
    assert tmp_store.add(sample_span) is True
    assert tmp_store.add(sample_span) is False  # PRIMARY KEY (trace_id, span_id)
    spans, total, _ = tmp_store.search(trace_id=sample_span["trace_id"])
    assert total == 1


def test_search_by_service(tmp_store, sample_span):
    other = dict(sample_span, span_id="f"*16, trace_id="a"*32, service_name="service-a")
    tmp_store.add(sample_span)
    tmp_store.add(other)
    spans, total, _ = tmp_store.search(service="service-a")
    assert total == 1
    assert spans[0]["service_name"] == "service-a"


def test_search_by_status(tmp_store, sample_span):
    err = dict(sample_span, span_id="e"*16, trace_id="b"*32, status="ERROR")
    tmp_store.add(sample_span)
    tmp_store.add(err)
    spans, total, _ = tmp_store.search(status="ERROR")
    assert total == 1
    assert spans[0]["status"] == "ERROR"


def test_search_by_min_duration(tmp_store, sample_span):
    tmp_store.add(sample_span)
    _, total, _ = tmp_store.search(min_duration_ns=5_000_000)   # 5 мс
    assert total == 1
    _, total, _ = tmp_store.search(min_duration_ns=50_000_000)  # 50 мс
    assert total == 0


def test_search_limit_truncated(tmp_store, sample_span):
    for i in range(5):
        s = dict(sample_span, span_id=f"{i:016x}", trace_id=f"{i:032x}")
        tmp_store.add(s)
    spans, total, truncated = tmp_store.search(limit=3)
    assert len(spans) == 3
    assert total == 5
    assert truncated is True


def test_count(tmp_store, sample_span):
    assert tmp_store.count() == 0
    tmp_store.add(sample_span)
    assert tmp_store.count() == 1


def test_retention_removes_old(tmp_store):
    import time
    old = {
        "trace_id": "a"*32, "span_id": "b"*16,
        "parent_span_id": None, "service_name": "s", "name": "n",
        "kind": "SERVER",
        "start_time_unix_nano": int((time.time() - 8*86400) * 1e9),  # 8 дней назад
        "end_time_unix_nano": int((time.time() - 8*86400) * 1e9) + 1000,
        "status": "OK",
    }
    tmp_store.add(old)
    assert tmp_store.count() == 1
    removed = tmp_store.apply_retention(hot_days=7)
    assert removed == 1
    assert tmp_store.count() == 0