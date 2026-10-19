import csv
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fieldops import store


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    orders_file = tmp_path / "work_orders.csv"
    crews_file = tmp_path / "crews.csv"

    crews_data = [
        {"id": "A", "name": "Alpha Crew", "home_site": "North Substation", "skills": "transformer;switchgear"},
        {"id": "B", "name": "Bravo Crew", "home_site": "North Substation", "skills": "feeder;rack;transformer"},
        {"id": "C", "name": "Charlie Crew", "home_site": "South Substation", "skills": "transformer;feeder"},
        {"id": "D", "name": "Delta Crew", "home_site": "East Yard", "skills": "switchgear;rack"},
    ]

    orders_data = [
        {
            "id": 1,
            "site": "North Substation",
            "equipment": "transformer",
            "description": "Inspect transformer unit",
            "priority": 1,
            "status": "open",
            "crew": "",
            "customer_name": "Test Customer",
            "customer_phone": "415-555-****",
            "created": "2026-10-01 08:00:00",
        },
        {
            "id": 2,
            "site": "South Substation",
            "equipment": "feeder",
            "description": "Check feeder line",
            "priority": 2,
            "status": "assigned",
            "crew": "C",
            "customer_name": "Test Customer",
            "customer_phone": "415-555-****",
            "created": "2026-10-01 09:00:00",
        },
        {
            "id": 3,
            "site": "East Yard",
            "equipment": "switchgear",
            "description": "Maintain switchgear",
            "priority": 3,
            "status": "closed",
            "crew": "D",
            "customer_name": "Test Customer",
            "customer_phone": "415-555-****",
            "created": "2026-10-01 10:00:00",
        },
    ]

    with open(crews_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "home_site", "skills"])
        writer.writeheader()
        for row in crews_data:
            writer.writerow(row)

    with open(orders_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=store.FIELDS)
        writer.writeheader()
        for row in orders_data:
            writer.writerow(row)

    monkeypatch.setattr(store, "ORDERS_FILE", str(orders_file))
    monkeypatch.setattr(store, "CREWS_FILE", str(crews_file))

    return {"orders_file": str(orders_file), "crews_file": str(crews_file)}
