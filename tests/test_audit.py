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


def _open_order():
    return next(o for o in store.load_orders() if o["status"] == "open")


def _lines(log):
    return log.read_text().splitlines()


def test_assign_logs_who_time_order_and_crew(env):
    o = _open_order()
    crew = store.load_crews()[0]["id"]
    assert audit.assign("dana", o["id"], crew) is True
    line = _lines(env)[-1]
    assert "dana" in line
    assert str(o["id"]) in line
    assert crew in line
    assert line.split()[0].count("-") == 2 and "T" in line.split()[0]  # ISO timestamp first
    assert store.get_order(o["id"])["crew"] == crew


def test_close_logs_closed_and_updates_status(env):
    o = _open_order()
    audit.close("dana", o["id"])
    line = _lines(env)[-1]
    assert str(o["id"]) in line
    assert "closed" in line
    assert store.get_order(o["id"])["status"] == "closed"


def test_no_pii_in_log(env):
    o = _open_order()
    crew = store.load_crews()[0]["id"]
    audit.assign("dana", o["id"], crew)
    audit.close("dana", o["id"])
    text = env.read_text()
    assert o["customer_name"] not in text
    assert o["customer_phone"] not in text
    assert o["customer_phone"][-4:] not in text


def test_log_is_append_only(env):
    orders = [o for o in store.load_orders() if o["status"] == "open"][:2]
    crew = store.load_crews()[0]["id"]
    audit.assign("dana", orders[0]["id"], crew)
    first = _lines(env)[0]
    audit.assign("dana", orders[1]["id"], crew)
    lines = _lines(env)
    assert len(lines) == 2
    assert lines[0] == first
