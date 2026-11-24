def test_add_and_all(tmp_store, sample_span):
    assert tmp_store.all() == []
    tmp_store.add(sample_span)
    assert tmp_store.all() == [sample_span]


def test_persisted_to_file(tmp_store, sample_span):
    tmp_store.add(sample_span)
    with open(tmp_store._path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    assert '"service-b"' in lines[0]


def test_by_trace_id(tmp_store, sample_span):
    other = dict(sample_span, span_id="ffffffffffffffff", trace_id="a" * 32)
    tmp_store.add(sample_span)
    tmp_store.add(other)

    result = tmp_store.by_trace_id(sample_span["trace_id"])
    assert len(result) == 1
    assert result[0]["span_id"] == sample_span["span_id"]


def test_by_trace_id_not_found(tmp_store, sample_span):
    tmp_store.add(sample_span)
    assert tmp_store.by_trace_id("b" * 32) == []


def test_all_returns_copy(tmp_store, sample_span):
    tmp_store.add(sample_span)
    copy = tmp_store.all()
    copy.append({"x": 1})
    assert len(tmp_store.all()) == 1  # внутренний список не изменился