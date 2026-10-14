import asyncio
import shutil

import pytest

from fieldops import app as web, mcp_server, store

SHOWN = ["id", "site", "equipment", "description", "priority", "status", "crew", "created"]


@pytest.fixture(autouse=True)
def temp_data(tmp_path, monkeypatch):
    orders = tmp_path / "work_orders.csv"
    crews = tmp_path / "crews.csv"
    shutil.copy(store.ORDERS_FILE, orders)
    shutil.copy(store.CREWS_FILE, crews)
    monkeypatch.setattr(store, "ORDERS_FILE", str(orders))
    monkeypatch.setattr(store, "CREWS_FILE", str(crews))
    return orders


def first_with_status(status):
    return next(o for o in store.load_orders() if o["status"] == status)


def test_three_tools_only():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert sorted(t.name for t in tools) == ["assign_order", "close_order", "list_orders"]


def test_list_orders_sorted_by_priority_then_created():
    result = mcp_server.list_orders("North Substation", "open")
    expected = sorted(
        (o for o in store.load_orders()
         if o["site"] == "North Substation" and o["status"] == "open"),
        key=lambda o: (o["priority"], o["created"]),
    )
    assert len(result) > 1
    assert [o["id"] for o in result] == [o["id"] for o in expected]
    assert all(list(o.keys()) == SHOWN for o in result)


def test_list_orders_has_no_personal_data():
    result = mcp_server.list_orders("North Substation", "open")
    text = str(result)
    for o in store.load_orders():
        assert o["customer_name"] not in text
        assert o["customer_phone"] not in text
    assert all("customer_name" not in o and "customer_phone" not in o for o in result)


def test_assign_order_good():
    o = first_with_status("open")
    result = mcp_server.assign_order(o["id"], "B")
    assert result["ok"] is True
    after = store.get_order(o["id"])
    assert after["crew"] == "B" and after["status"] == "assigned"


def test_assign_order_unknown_crew_refused(temp_data):
    o = first_with_status("open")
    before = temp_data.read_text()
    assert mcp_server.assign_order(o["id"], "Z")["ok"] is False
    assert temp_data.read_text() == before


def test_assign_order_missing_order_refused(temp_data):
    before = temp_data.read_text()
    assert mcp_server.assign_order(999999, "B")["ok"] is False
    assert temp_data.read_text() == before


def test_assign_order_closed_order_refused(temp_data):
    o = first_with_status("closed")
    before = temp_data.read_text()
    assert mcp_server.assign_order(o["id"], "B")["ok"] is False
    assert temp_data.read_text() == before


def test_close_order_good():
    o = first_with_status("open")
    assert mcp_server.close_order(o["id"])["ok"] is True
    assert store.get_order(o["id"])["status"] == "closed"


def test_close_order_missing_order_refused(temp_data):
    before = temp_data.read_text()
    assert mcp_server.close_order(999999)["ok"] is False
    assert temp_data.read_text() == before


def test_changes_show_on_web_screen():
    open_orders = [o for o in store.load_orders() if o["status"] == "open"]
    to_assign, to_close = open_orders[0], open_orders[1]
    mcp_server.assign_order(to_assign["id"], "B")
    mcp_server.close_order(to_close["id"])
    html = web.app.test_client().get("/").get_data(as_text=True)
    assert "<td>assigned</td><td>B</td>" in html
    assert "<td>%d</td>" % to_close["id"] not in html


def test_entry_point_exists():
    assert callable(mcp_server.main)
