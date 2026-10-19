import os
import shutil

import pytest

from fieldops import store


@pytest.fixture(autouse=True)
def temp_data(tmp_path, monkeypatch):
    # never touch the real data files
    for name in ("work_orders.csv", "crews.csv"):
        shutil.copy(os.path.join(store.DATA_DIR, name), tmp_path / name)
    monkeypatch.setattr(store, "ORDERS_FILE", str(tmp_path / "work_orders.csv"))
    monkeypatch.setattr(store, "CREWS_FILE", str(tmp_path / "crews.csv"))


@pytest.fixture
def server():
    from fieldops import mcp_server
    return mcp_server


def first_with(status, site="North Substation"):
    return [o for o in store.load_orders() if o["status"] == status and o["site"] == site][0]


def test_list_orders_matches_site_and_status(server):
    result = server.list_orders("North Substation", "open")
    assert result
    assert all(o["site"] == "North Substation" and o["status"] == "open" for o in result)
    expected = [o for o in store.load_orders()
                if o["site"] == "North Substation" and o["status"] == "open"]
    assert len(result) == len(expected)


def test_list_orders_strips_pii(server):
    result = server.list_orders("North Substation", "open")
    for o in result:
        assert "customer_name" not in o
        assert "customer_phone" not in o


def test_list_orders_no_match_is_empty(server):
    assert server.list_orders("Nowhere Substation", "open") == []


def test_assign_order_valid(server):
    order = first_with("open")
    assert server.assign_order(order["id"], "B") is True
    updated = store.get_order(order["id"])
    assert updated["status"] == "assigned"
    assert updated["crew"] == "B"


def test_assign_order_unknown_crew(server):
    order = first_with("open")
    assert server.assign_order(order["id"], "Z") is False
    assert store.get_order(order["id"])["status"] == "open"


def test_assign_order_closed_order(server):
    order = first_with("closed")
    assert server.assign_order(order["id"], "B") is False
    assert store.get_order(order["id"])["status"] == "closed"


def test_close_order_assigned(server):
    order = first_with("assigned")
    assert server.close_order(order["id"]) is True
    assert store.get_order(order["id"])["status"] == "closed"


def test_close_order_open_is_refused(server):
    order = first_with("open")
    assert server.close_order(order["id"]) is False
    assert store.get_order(order["id"])["status"] == "open"


def test_close_order_already_closed(server):
    order = first_with("closed")
    assert server.close_order(order["id"]) is False
    assert store.get_order(order["id"])["status"] == "closed"


def test_close_order_missing_order(server):
    assert server.close_order(999999) is False
