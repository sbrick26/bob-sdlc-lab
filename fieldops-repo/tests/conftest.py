import csv

import pytest

from fieldops import store

CREWS = [
    {"id": "A", "name": "Alpha Crew", "home_site": "North", "skills": "transformer;switchgear"},
    {"id": "B", "name": "Bravo Crew", "home_site": "North", "skills": "feeder;rack"},
    {"id": "C", "name": "Charlie Crew", "home_site": "South", "skills": "transformer;feeder"},
]

ORDERS = [
    {"id": 1, "site": "North", "equipment": "transformer", "description": "open order",
     "priority": 1, "status": "open", "crew": "", "customer_name": "", "customer_phone": "",
     "created": "2026-01-01"},
    {"id": 2, "site": "South", "equipment": "feeder", "description": "closed order",
     "priority": 2, "status": "closed", "crew": "C", "customer_name": "", "customer_phone": "",
     "created": "2026-01-02"},
]


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the store at temp CSV files so tests never touch the real data/."""
    crews_file = tmp_path / "crews.csv"
    with open(crews_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "home_site", "skills"])
        w.writeheader()
        w.writerows(CREWS)

    orders_file = tmp_path / "work_orders.csv"
    monkeypatch.setattr(store, "ORDERS_FILE", str(orders_file))
    monkeypatch.setattr(store, "CREWS_FILE", str(crews_file))
    store.save_orders(ORDERS)
    return tmp_path
