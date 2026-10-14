import asyncio

from fieldops import app as web, mcp_server, store


def _extra_orders():
    base = {"equipment": "feeder", "description": "extra", "crew": "",
            "customer_name": "Test Customer", "customer_phone": "000-000-0000"}
    orders = store.load_orders()
    orders.append(dict(base, id=9010, site="Bravo Site", priority=1, status="open", created="2026-02-01"))
    orders.append(dict(base, id=9011, site="Bravo Site", priority=2, status="open", created="2025-12-01"))
    store.save_orders(orders)


def test_server_offers_exactly_three_tools(temp_store):
    tools = asyncio.run(mcp_server.server.list_tools())
    assert sorted(t.name for t in tools) == ["assign_order", "close_order", "list_orders"]


def test_list_orders_filters_and_sorts_top_first(temp_store):
    _extra_orders()
    result = mcp_server.list_orders("Bravo Site", "open")
    assert [o["id"] for o in result] == [9010, 9011, 9001]
    assert mcp_server.list_orders("Bravo Site", "closed")[0]["id"] == 9002
    assert mcp_server.list_orders("Nowhere", "open") == []


def test_list_orders_hides_customer_data(temp_store):
    result = mcp_server.list_orders("Bravo Site", "open")
    assert result
    for o in result:
        assert "customer_name" not in o
        assert "customer_phone" not in o
        assert "Test Customer" not in str(o)
        assert "000-000-0000" not in str(o)


def test_assign_order_saves_change(temp_store):
    result = mcp_server.assign_order(9001, "B")
    assert result["ok"] is True
    o = store.get_order(9001)
    assert o["crew"] == "B" and o["status"] == "assigned"


def test_assign_order_refusals_change_nothing(temp_store):
    path = store.ORDERS_FILE
    before = open(path).read()
    assert mcp_server.assign_order(9001, "Z")["ok"] is False
    assert mcp_server.assign_order(1, "B")["ok"] is False
    assert mcp_server.assign_order(9002, "A")["ok"] is False
    assert open(path).read() == before


def test_close_order_saves_change_and_refuses_missing(temp_store):
    assert mcp_server.close_order(9001)["ok"] is True
    assert store.get_order(9001)["status"] == "closed"
    path = store.ORDERS_FILE
    before = open(path).read()
    assert mcp_server.close_order(1)["ok"] is False
    assert open(path).read() == before


def test_change_shows_on_web_screen(temp_store):
    mcp_server.assign_order(9001, "B")
    client = web.app.test_client()
    html = client.get("/").get_data(as_text=True)
    assert "<td>9001</td>" in html and "<td>assigned</td>" in html
    mcp_server.close_order(9001)
    html = client.get("/").get_data(as_text=True)
    assert "<td>9001</td>" not in html


def test_module_exposes_main_entry():
    assert callable(mcp_server.main)
