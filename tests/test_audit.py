import shutil

import pytest

from fieldops import audit, store


@pytest.fixture
def env(tmp_path, monkeypatch):
    orders = tmp_path / "work_orders.csv"
    shutil.copy(store.ORDERS_FILE, orders)
    monkeypatch.setattr(store, "ORDERS_FILE", str(orders))
    log = tmp_path / "audit.log"
    monkeypatch.setattr(audit, "LOG_FILE", str(log))
    return log


def _lines(log):
    return log.read_text().splitlines()


def _open_order_and_crew():
    order = [o for o in store.load_orders() if o["status"] != "closed"][0]
    crew = store.load_crews()[0]["id"]
    return order["id"], crew


def test_assign_writes_one_line(env):
    order_id, crew = _open_order_and_crew()
    assert audit.assign("alex", order_id, crew) is True
    lines = _lines(env)
    assert len(lines) == 1
    assert "alex" in lines[0]
    assert str(order_id) in lines[0]
    assert crew in lines[0]
    assert lines[0].split()[0][:2] == "20"  # ISO timestamp first


def test_close_writes_one_line(env):
    order_id, _ = _open_order_and_crew()
    audit.close("alex", order_id)
    lines = _lines(env)
    assert len(lines) == 1
    assert "alex" in lines[0]
    assert str(order_id) in lines[0]
    assert "closed" in lines[0]
    assert store.get_order(order_id)["status"] == "closed"


def test_log_only_grows(env):
    order_id, crew = _open_order_and_crew()
    audit.assign("alex", order_id, crew)
    first = _lines(env)[0]
    audit.close("sam", order_id)
    lines = _lines(env)
    assert len(lines) == 2
    assert lines[0] == first


def test_no_personal_data_in_log(env):
    order_id, crew = _open_order_and_crew()
    order = store.get_order(order_id)
    audit.assign("alex", order_id, crew)
    audit.close("alex", order_id)
    text = env.read_text()
    assert order["customer_phone"] not in text
    assert order["customer_name"] not in text
    assert "415-555" not in text
