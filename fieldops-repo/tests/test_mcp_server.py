import os
import shutil
import pytest
from fieldops import store
from fieldops import mcp_server


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Isolate data files so tests never mutate real CSV files."""
    real_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    temp_orders = tmp_path / "work_orders.csv"
    temp_crews = tmp_path / "crews.csv"
    shutil.copy(os.path.join(real_data_dir, "work_orders.csv"), temp_orders)
    shutil.copy(os.path.join(real_data_dir, "crews.csv"), temp_crews)

    monkeypatch.setattr(store, "ORDERS_FILE", str(temp_orders))
    monkeypatch.setattr(store, "CREWS_FILE", str(temp_crews))


def test_list_orders_filtering_and_sorting():
    orders = mcp_server.list_orders(site="North Substation", status="open")
    assert len(orders) > 0
    for o in orders:
        assert o["site"] == "North Substation"
        assert o["status"] == "open"
        assert "415-555-****" in o.get("customer_phone", "")

    # Test sorting: lowest priority number first, then oldest created date
    for i in range(len(orders) - 1):
        p1 = int(orders[i]["priority"])
        p2 = int(orders[i + 1]["priority"])
        assert p1 <= p2
        if p1 == p2:
            assert orders[i]["created"] <= orders[i + 1]["created"]


def test_list_orders_no_filter():
    orders = mcp_server.list_orders()
    assert len(orders) > 0
    # Priority sorting check across all orders
    for i in range(len(orders) - 1):
        p1 = int(orders[i]["priority"])
        p2 = int(orders[i + 1]["priority"])
        assert p1 <= p2
        if p1 == p2:
            assert orders[i]["created"] <= orders[i + 1]["created"]


def test_assign_order_success():
    orders = mcp_server.list_orders(site="North Substation", status="open")
    assert len(orders) >= 2
    order1_id = orders[0]["id"]
    order2_id = orders[1]["id"]

    res1 = mcp_server.assign_order(id=order1_id, crew="B")
    assert res1.get("success") is True or res1 is True

    res2 = mcp_server.assign_order(id=order2_id, crew="B")
    assert res2.get("success") is True or res2 is True

    o1 = store.get_order(order1_id)
    assert o1["status"] == "assigned"
    assert o1["crew"] == "B"

    o2 = store.get_order(order2_id)
    assert o2["status"] == "assigned"
    assert o2["crew"] == "B"


def test_assign_order_invalid_crew():
    orders = mcp_server.list_orders(status="open")
    order_id = orders[0]["id"]
    res = mcp_server.assign_order(id=order_id, crew="NONEXISTENT")
    assert res.get("success") is False or res is False


def test_assign_order_nonexistent_order():
    res = mcp_server.assign_order(id=999999, crew="A")
    assert res.get("success") is False or res is False


def test_close_order_success():
    orders = mcp_server.list_orders()
    order_id = orders[0]["id"]
    res = mcp_server.close_order(id=order_id)
    assert res.get("success") is True or res is True

    o = store.get_order(order_id)
    assert o["status"] == "closed"


def test_close_order_nonexistent():
    res = mcp_server.close_order(id=999999)
    assert res.get("success") is False or res is False
