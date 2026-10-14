import pytest

from fieldops import audit, store


@pytest.fixture
def audit_file(temp_store, monkeypatch):
    path = temp_store / "audit.log"
    monkeypatch.setattr(audit, "AUDIT_FILE", str(path))
    return path


def _lines(path):
    return path.read_text().splitlines()


def test_audit_assign_writes_one_line(audit_file):
    assert audit.assign("alex", 9001, "B") is True
    lines = _lines(audit_file)
    assert len(lines) == 1
    assert "alex" in lines[0]
    assert "9001" in lines[0]
    assert "B" in lines[0]
    assert lines[0][:4].isdigit()  # starts with a timestamp
    assert store.get_order(9001)["crew"] == "B"


def test_audit_close_writes_one_line(audit_file):
    audit.close("alex", 9001)
    lines = _lines(audit_file)
    assert len(lines) == 1
    assert "alex" in lines[0]
    assert "9001" in lines[0]
    assert "closed" in lines[0]
    assert store.get_order(9001)["status"] == "closed"


def test_audit_log_only_grows(audit_file):
    audit.assign("alex", 9001, "B")
    first = _lines(audit_file)[0]
    audit.close("alex", 9001)
    lines = _lines(audit_file)
    assert len(lines) == 2
    assert lines[0] == first


def test_audit_assign_refused_writes_nothing(audit_file):
    assert audit.assign("alex", 9001, "Z") is False  # unknown crew
    assert audit.assign("alex", 1, "B") is False  # missing order
    assert audit.assign("alex", 9002, "B") is False  # closed order
    assert not audit_file.exists() or _lines(audit_file) == []


def test_audit_log_has_no_personal_data(audit_file):
    audit.assign("alex", 9001, "B")
    audit.close("alex", 9001)
    text = audit_file.read_text()
    assert "Test Customer" not in text
    assert "000-000-0000" not in text
