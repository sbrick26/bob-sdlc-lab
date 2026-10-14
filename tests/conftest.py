import csv

import pytest

from fieldops import store

CREWS = [
    {"id": "A", "name": "Test Crew A", "home_site": "Alpha Site", "skills": "transformer"},
    {"id": "B", "name": "Test Crew B", "home_site": "Bravo Site", "skills": "feeder;rack"},
    {"id": "C", "name": "Test Crew C", "home_site": "Charlie Site", "skills": "rack;feeder"},
    {"id": "D", "name": "Test Crew D", "home_site": "Delta Site", "skills": "switchgear"},
]

ORDERS = [
    {"id": 9001, "site": "Bravo Site", "equipment": "feeder", "description": "test open",
     "priority": 2, "status": "open", "crew": "", "customer_name": "Test Customer",
     "customer_phone": "000-000-0000", "created": "2026-01-01"},
    {"id": 9002, "site": "Bravo Site", "equipment": "rack", "description": "test closed",
     "priority": 3, "status": "closed", "crew": "B", "customer_name": "Test Customer",
     "customer_phone": "000-000-0000", "created": "2026-01-02"},
    {"id": 9003, "site": "Charlie Site", "equipment": "rack", "description": "test assigned",
     "priority": 3, "status": "assigned", "crew": "B", "customer_name": "Test Customer",
     "customer_phone": "000-000-0000", "created": "2026-01-03"},
]


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    orders_file = tmp_path / "work_orders.csv"
    crews_file = tmp_path / "crews.csv"
    with open(crews_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "home_site", "skills"])
        w.writeheader()
        w.writerows(CREWS)
    with open(orders_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=store.FIELDS)
        w.writeheader()
        w.writerows(ORDERS)
    monkeypatch.setattr(store, "ORDERS_FILE", str(orders_file))
    monkeypatch.setattr(store, "CREWS_FILE", str(crews_file))
    return tmp_path


@pytest.fixture
def crews(temp_store):
    result = store.load_crews()
    for c in result:
        c["load"] = 0
    return result
