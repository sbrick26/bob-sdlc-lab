import datetime
import os
import shutil
import pytest
from fieldops import audit, store


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    src_orders = store.ORDERS_FILE
    src_crews = store.CREWS_FILE
    dst_orders = str(data_dir / "work_orders.csv")
    dst_crews = str(data_dir / "crews.csv")
    shutil.copy(src_orders, dst_orders)
    shutil.copy(src_crews, dst_crews)
    audit_file = str(data_dir / "audit.log")
    monkeypatch.setattr(store, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(store, "ORDERS_FILE", dst_orders)
    monkeypatch.setattr(store, "CREWS_FILE", dst_crews)
    monkeypatch.setattr(audit, "AUDIT_FILE", audit_file)
    return data_dir, audit_file


def test_record_function(isolated_data):
    _, audit_file = isolated_data
    audit.record("dispatcher1", 1, "test change")
    assert os.path.exists(audit_file)
    with open(audit_file, "r") as f:
        lines = f.readlines()
    assert len(lines) == 1
    parts = [p.strip() for p in lines[0].split("|")]
    assert len(parts) == 4
    # Check timestamp parses as ISO
    datetime.datetime.fromisoformat(parts[0])
    assert parts[1] == "dispatcher1"
    assert parts[2] == "1"
    assert parts[3] == "test change"


def test_assign_wrapper_records_audit_and_updates_order(isolated_data):
    _, audit_file = isolated_data
    order_id = 1001
    res = audit.assign(order_id, "B", who="dispatcher1")
    assert res is True
    order = store.get_order(order_id)
    assert order["status"] == "assigned"
    assert order["crew"] == "B"

    with open(audit_file, "r") as f:
        lines = f.readlines()
    assert len(lines) == 1
    parts = [p.strip() for p in lines[0].split("|")]
    assert parts[1] == "dispatcher1"
    assert parts[2] == str(order_id)
    assert "assigned" in parts[3]
    assert "B" in parts[3]


def test_close_wrapper_records_audit_and_updates_order(isolated_data):
    _, audit_file = isolated_data
    order_id = 1002
    res = audit.close(order_id, who="supervisor1")
    assert res is not None
    order = store.get_order(order_id)
    assert order["status"] == "closed"

    with open(audit_file, "r") as f:
        lines = f.readlines()
    assert len(lines) == 1
    parts = [p.strip() for p in lines[0].split("|")]
    assert parts[1] == "supervisor1"
    assert parts[2] == str(order_id)
    assert parts[3] == "closed"


def test_default_who_records_unknown(isolated_data):
    _, audit_file = isolated_data
    order_id = 1001
    audit.assign(order_id, "A")
    audit.close(order_id)

    with open(audit_file, "r") as f:
        lines = f.readlines()
    assert len(lines) == 2
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        assert parts[1] == "unknown"


def test_audit_log_is_append_only(isolated_data):
    _, audit_file = isolated_data
    audit.record("user1", 1, "first action")
    with open(audit_file, "r") as f:
        first_content = f.read()

    audit.record("user2", 2, "second action")
    with open(audit_file, "r") as f:
        second_content = f.read()

    assert second_content.startswith(first_content)
    lines = second_content.strip().split("\n")
    assert len(lines) == 2
