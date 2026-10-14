"""Tests for KAN-160: audit trail in fieldops/audit.py."""
import shutil
import os
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    """Copy data/ to a temp directory so tests never modify real files."""
    src = os.path.join(os.path.dirname(__file__), "..", "data")
    dst = str(tmp_path / "data")
    shutil.copytree(src, dst)
    import fieldops.store as store_mod
    monkeypatch.setattr(store_mod, "DATA_DIR", dst)
    monkeypatch.setattr(store_mod, "ORDERS_FILE", os.path.join(dst, "work_orders.csv"))
    monkeypatch.setattr(store_mod, "CREWS_FILE", os.path.join(dst, "crews.csv"))
    return dst


@pytest.fixture
def audit_log_path(isolated_data_dir):
    """Return the path to the audit log in the isolated data directory."""
    return os.path.join(isolated_data_dir, "audit.log")


# ---------------------------------------------------------------------------
# Module-level API check
# ---------------------------------------------------------------------------

def test_audit_module_has_record():
    import fieldops.audit as audit
    assert callable(audit.record)


def test_audit_module_has_assign():
    import fieldops.audit as audit
    assert callable(audit.assign)


def test_audit_module_has_close():
    import fieldops.audit as audit
    assert callable(audit.close)


# ---------------------------------------------------------------------------
# record() — basic behaviour
# ---------------------------------------------------------------------------

def test_record_appends_one_line(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.record("dispatcher1", 1001, "test-change")
    with open(audit_log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_record_line_contains_expected_fields(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.record("dispatcher1", 1001, "test-change")
    with open(audit_log_path) as f:
        line = f.readline()
    assert "who=dispatcher1" in line
    assert "order=1001" in line
    assert "change=test-change" in line


def test_record_line_has_timestamp(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.record("dispatcher1", 1001, "test-change")
    with open(audit_log_path) as f:
        line = f.readline()
    # ISO-8601 UTC timestamps contain a 'T' and 'Z' or '+00:00'
    assert "T" in line and ("Z" in line or "+00" in line), (
        f"Expected ISO-8601 UTC timestamp in: {line!r}"
    )


# ---------------------------------------------------------------------------
# append-only: two calls produce two lines; first unchanged
# ---------------------------------------------------------------------------

def test_two_records_produce_two_lines(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.record("user1", 1001, "first")
    audit.record("user2", 1002, "second")
    with open(audit_log_path) as f:
        lines = f.readlines()
    assert len(lines) == 2


def test_first_line_unchanged_after_second_record(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.record("user1", 1001, "first")
    with open(audit_log_path) as f:
        first_line = f.readline()
    audit.record("user2", 1002, "second")
    with open(audit_log_path) as f:
        lines = f.readlines()
    assert lines[0] == first_line, "First log line was altered by a second write"


# ---------------------------------------------------------------------------
# audit.assign() wrapper
# ---------------------------------------------------------------------------

def test_assign_appends_one_line(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.assign("dispatcher1", 1001, "A")
    with open(audit_log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_assign_log_line_contains_crew(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.assign("dispatcher1", 1001, "A")
    with open(audit_log_path) as f:
        line = f.readline()
    assert "assigned" in line
    assert "A" in line


def test_assign_updates_order_status(monkeypatch, isolated_data_dir):
    import fieldops.audit as audit
    import fieldops.store as store
    log = os.path.join(isolated_data_dir, "audit.log")
    monkeypatch.setattr(audit, "LOG_PATH", log)
    audit.assign("dispatcher1", 1001, "A")
    order = store.get_order(1001)
    assert order["status"] == "assigned"
    assert order["crew"] == "A"


# ---------------------------------------------------------------------------
# audit.close() wrapper
# ---------------------------------------------------------------------------

def test_close_appends_one_line(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.close("dispatcher1", 1001)
    with open(audit_log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_close_log_line_contains_closed(monkeypatch, isolated_data_dir, audit_log_path):
    import fieldops.audit as audit
    monkeypatch.setattr(audit, "LOG_PATH", audit_log_path)
    audit.close("dispatcher1", 1001)
    with open(audit_log_path) as f:
        line = f.readline()
    assert "closed" in line


def test_close_updates_order_status(monkeypatch, isolated_data_dir):
    import fieldops.audit as audit
    import fieldops.store as store
    log = os.path.join(isolated_data_dir, "audit.log")
    monkeypatch.setattr(audit, "LOG_PATH", log)
    audit.close("dispatcher1", 1001)
    order = store.get_order(1001)
    assert order["status"] == "closed"
