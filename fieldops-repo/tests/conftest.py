"""conftest.py — shared pytest fixtures for fieldops-repo/tests/.

redirect_store:
    Redirects store.ORDERS_FILE and store.CREWS_FILE to temporary copies
    inside tmp_path for the duration of each test that requests the fixture.
    This ensures tests that call assign_order (or any store write) never
    touch the real data files in fieldops-repo/data/.
"""
import shutil
import pytest
from fieldops import store


@pytest.fixture(autouse=False)
def redirect_store(tmp_path):
    """Point store module-level paths at temp copies of the real CSVs."""
    import os

    data_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data"
    )

    tmp_orders = tmp_path / "work_orders.csv"
    tmp_crews = tmp_path / "crews.csv"
    shutil.copy(os.path.join(data_dir, "work_orders.csv"), tmp_orders)
    shutil.copy(os.path.join(data_dir, "crews.csv"), tmp_crews)

    original_orders = store.ORDERS_FILE
    original_crews = store.CREWS_FILE

    store.ORDERS_FILE = str(tmp_orders)
    store.CREWS_FILE = str(tmp_crews)

    yield

    store.ORDERS_FILE = original_orders
    store.CREWS_FILE = original_crews
