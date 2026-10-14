import csv
import shutil
import pytest
from fieldops import store, assign


@pytest.fixture(autouse=True)
def setup_test_data(tmp_path, monkeypatch):
    test_orders_file = tmp_path / "work_orders.csv"
    test_crews_file = tmp_path / "crews.csv"

    # Seed crews
    with open(test_crews_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "home_site", "skills"])
        w.writeheader()
        w.writerow({"id": "A", "home_site": "North Substation", "skills": "transformer;feeder"})
        w.writerow({"id": "B", "home_site": "North Substation", "skills": "transformer;rack"})

    # Seed orders
    with open(test_orders_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=store.FIELDS)
        w.writeheader()
        w.writerow({
            "id": "1",
            "site": "North Substation",
            "equipment": "transformer",
            "description": "Humming loudly",
            "priority": "1",
            "status": "open",
            "crew": "",
            "customer_name": "Jane Doe",
            "customer_phone": "415-555-1234",
            "created": "2026-01-01"
        })
        w.writerow({
            "id": "2",
            "site": "North Substation",
            "equipment": "feeder",
            "description": "Line loose",
            "priority": "2",
            "status": "assigned",
            "crew": "A",
            "customer_name": "John Smith",
            "customer_phone": "415-555-5678",
            "created": "2026-01-02"
        })
        w.writerow({
            "id": "3",
            "site": "South Substation",
            "equipment": "rack",
            "description": "Corrosion",
            "priority": "1",
            "status": "open",
            "crew": "",
            "customer_name": "Bob Jones",
            "customer_phone": "415-555-9999",
            "created": "2026-01-03"
        })

    monkeypatch.setattr(store, "ORDERS_FILE", str(test_orders_file))
    monkeypatch.setattr(store, "CREWS_FILE", str(test_crews_file))


def test_list_orders_filters():
    from fieldops import mcp_server
    orders = mcp_server.list_orders(site="North Substation", status="open")
    assert len(orders) == 1
    assert orders[0]["id"] == 1
    assert orders[0]["site"] == "North Substation"
    assert orders[0]["status"] == "open"


def test_list_orders_no_pii():
    from fieldops import mcp_server
    orders = mcp_server.list_orders(site="North Substation", status="open")
    for o in orders:
        assert "customer_name" not in o
        assert "customer_phone" not in o


def test_assign_order_success():
    from fieldops import mcp_server
    result = mcp_server.assign_order(id=1, crew="B")
    assert result is True or result == "Order 1 assigned to crew B" or result
    order = store.get_order(1)
    assert order["crew"] == "B"
    assert order["status"] == "assigned"


def test_assign_order_bad_crew():
    from fieldops import mcp_server
    result = mcp_server.assign_order(id=1, crew="Z")
    assert result is False or result == "Unknown crew Z" or (isinstance(result, dict) and not result.get("success"))
    order = store.get_order(1)
    assert order["crew"] != "Z"
    assert order["status"] == "open"


def test_close_order():
    from fieldops import mcp_server
    result = mcp_server.close_order(id=1)
    assert result is True or result == "Order 1 closed" or result
    order = store.get_order(1)
    assert order["status"] == "closed"
