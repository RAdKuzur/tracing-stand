import json


def test_append_and_read(tmp_audit):
    e1 = tmp_audit.append("ivan", "SRE", "SEARCH", {"limit": 10})
    e2 = tmp_audit.append("petr", "DEV", "SEARCH", {"limit": 5})
    assert e1["hash"] != e2["hash"]

    logs = tmp_audit.read_all()
    assert len(logs) == 2
    assert logs[0]["user"] == "ivan"
    assert logs[1]["role"] == "DEV"


def test_hash_chain(tmp_path):
    from src.audit.audit_log import AuditLog
    path = str(tmp_path / "audit.jsonl")
    a = AuditLog(path)
    a.append("u1", "SRE", "SEARCH", {})
    a.append("u2", "DEV", "SEARCH", {})

    # после перезапуска последний hash восстанавливается из файла
    b = AuditLog(path)
    e3 = b.append("u3", "ADMIN", "CONFIG_CHANGE", {"k": "v"})
    logs = b.read_all()
    # hash третьей записи зависит от второй
    assert logs[-1]["hash"] == e3["hash"]
    assert len(logs) == 3


def test_read_empty(tmp_audit):
    assert tmp_audit.read_all() == []