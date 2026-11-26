import json
import os
from typing import Dict, Any

DEFAULT_RULES = {"drop_keys": [], "mask_keys": [], "mask_value": "***"}


def load_rules(path: str | None = None) -> Dict[str, Any]:
    path = path or os.getenv("MASKING_RULES_PATH", "/app/config/masking_rules.json")
    if not os.path.exists(path):
        return DEFAULT_RULES
    with open(path, encoding="utf-8") as f:
        return {**DEFAULT_RULES, **json.load(f)}


def apply(span: dict, rules: Dict[str, Any]) -> dict:
    attrs = dict(span.get("attributes") or {})
    for key in list(attrs.keys()):
        if key in rules.get("drop_keys", []):
            del attrs[key]
        elif key in rules.get("mask_keys", []):
            attrs[key] = rules.get("mask_value", "***")
    out = dict(span)
    out["attributes"] = attrs
    return out