import csv

import pytest

from fieldops import store

CREW_FIELDS = ["id", "name", "home_site", "skills"]

# Made-up crews: no personal data, never the real data/crews.csv.
TEST_CREWS = [
    {"id": "A", "name": "Alpha", "home_site": "North", "skills": "transformer;switchgear"},
    {"id": "B", "name": "Bravo", "home_site": "North", "skills": "feeder;rack;transformer"},
    {"id": "C", "name": "Charlie", "home_site": "South", "skills": "transformer;feeder"},
]

TEST_ORDERS = [
    {"id": 1, "site": "North", "equipment": "feeder", "priority": 2, "status": "open", "crew": ""},
    {"id": 2, "site": "South", "equipment": "feeder", "priority": 3, "status": "closed", "crew": "C"},
    {"id": 3, "site": "South", "equipment": "transformer", "priority": 1, "status": "assigned", "crew": "C"},
]


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the store at small temp CSV files so the real data is never touched."""
    orders_file = tmp_path / "work_orders.csv"
    crews_file = tmp_path / "crews.csv"

    with open(crews_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CREW_FIELDS)
        w.writeheader()
        w.writerows(TEST_CREWS)

    with open(orders_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=store.FIELDS)
        w.writeheader()
        for o in TEST_ORDERS:
            w.writerow({k: o.get(k, "") for k in store.FIELDS})

    monkeypatch.setattr(store, "ORDERS_FILE", str(orders_file))
    monkeypatch.setattr(store, "CREWS_FILE", str(crews_file))
