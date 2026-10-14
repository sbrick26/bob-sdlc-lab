"""conftest.py – sys.path setup and shared fixtures for tests."""
import csv
import sys
import os
import pytest

# Add the repo root to sys.path so `fieldops` can be imported without install.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


CREWS_HEADER = ["id", "home_site", "skills"]
ORDERS_HEADER = ["id", "site", "equipment", "description", "priority",
                 "status", "crew", "customer_name", "customer_phone", "created"]


@pytest.fixture()
def csv_store(tmp_path, monkeypatch):
    """Write small hand-built CSV files to tmp_path and patch store paths."""
    from fieldops import store

    crews_file = tmp_path / "crews.csv"
    orders_file = tmp_path / "work_orders.csv"

    # Crew A: site=Alpha, skills=transformer;feeder
    # Crew B: site=Beta,  skills=feeder;switchgear
    # Crew C: site=Alpha, skills=switchgear;rack
    crews = [
        {"id": "A", "home_site": "Alpha", "skills": "transformer;feeder"},
        {"id": "B", "home_site": "Beta",  "skills": "feeder;switchgear"},
        {"id": "C", "home_site": "Alpha", "skills": "switchgear;rack"},
    ]
    with open(crews_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CREWS_HEADER)
        w.writeheader()
        w.writerows(crews)

    orders = [
        {"id": 1, "site": "Alpha", "equipment": "transformer", "description": "out",
         "priority": 1, "status": "open", "crew": "", "customer_name": "x",
         "customer_phone": "415-555-0000", "created": "2024-01-01"},
        {"id": 2, "site": "Beta",  "equipment": "feeder",      "description": "out",
         "priority": 2, "status": "open", "crew": "", "customer_name": "y",
         "customer_phone": "415-555-0001", "created": "2024-01-02"},
    ]
    with open(orders_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDERS_HEADER)
        w.writeheader()
        w.writerows(orders)

    monkeypatch.setattr(store, "ORDERS_FILE", str(orders_file))
    monkeypatch.setattr(store, "CREWS_FILE",  str(crews_file))
    return {"crews_file": str(crews_file), "orders_file": str(orders_file)}
