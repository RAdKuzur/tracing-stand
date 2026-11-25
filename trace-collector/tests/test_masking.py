from src.policy import masking


def test_apply_drop_and_mask(sample_span):
    rules = {
        "drop_keys": ["http.request.header.authorization"],
        "mask_keys": ["user.email"],
        "mask_value": "***",
    }
    span = dict(sample_span)
    span["attributes"] = {
        "http.request.header.authorization": "Bearer xxx",
        "user.email": "ivan@example.com",
        "http.method": "GET",
    }
    out = masking.apply(span, rules)
    assert "http.request.header.authorization" not in out["attributes"]
    assert out["attributes"]["user.email"] == "***"
    assert out["attributes"]["http.method"] == "GET"
    assert "user.email" in span["attributes"]  # исходный не изменён


def test_apply_no_rules(sample_span):
    out = masking.apply(sample_span, {"drop_keys": [], "mask_keys": []})
    assert out["attributes"] == sample_span["attributes"]


def test_load_rules_missing_file(tmp_path):
    rules = masking.load_rules(str(tmp_path / "nonexistent.json"))
    assert rules == masking.DEFAULT_RULES


def test_load_rules_from_file(tmp_path):
    import json
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"drop_keys": ["a"], "mask_keys": ["b"], "mask_value": "X"}))
    rules = masking.load_rules(str(p))
    assert rules["drop_keys"] == ["a"]
    assert rules["mask_value"] == "X"