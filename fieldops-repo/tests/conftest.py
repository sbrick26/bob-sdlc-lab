import pytest
import csv
from fieldops import store

@pytest.fixture(autouse=True)
def isolate_storage(tmp_path, monkeypatch):
    """
    Automatically isolates CSV storage for each test.
    Creates temporary copies of work_orders.csv and crews.csv
    and monkeypatches the module attributes in fieldops.store.
    """
    temp_orders_file = tmp_path / "work_orders.csv"
    temp_crews_file = tmp_path / "crews.csv"
    
    with open(temp_orders_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(store.FIELDS)
        
    with open(temp_crews_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "home_site", "skills"])
        
    monkeypatch.setattr(store, "ORDERS_FILE", str(temp_orders_file))
    monkeypatch.setattr(store, "CREWS_FILE", str(temp_crews_file))
