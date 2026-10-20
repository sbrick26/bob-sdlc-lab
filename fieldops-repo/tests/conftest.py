"""
conftest.py — shared fixtures for fieldops tests.

Redirects store.ORDERS_FILE and store.CREWS_FILE to temp copies so
tests never touch the real data files.
"""
import csv
import os
import shutil
import tempfile

import pytest

from fieldops import store


@pytest.fixture()
def temp_store(tmp_path):
    """
    Function-scoped fixture.
    Copies the real CSVs into a temp directory and patches store module
    variables so every test starts with the real data but writes nowhere
    near fieldops-repo/data/.
    """
    real_orders = store.ORDERS_FILE
    real_crews = store.CREWS_FILE

    tmp_orders = str(tmp_path / "work_orders.csv")
    tmp_crews = str(tmp_path / "crews.csv")

    shutil.copy(real_orders, tmp_orders)
    shutil.copy(real_crews, tmp_crews)

    store.ORDERS_FILE = tmp_orders
    store.CREWS_FILE = tmp_crews

    yield tmp_path

    store.ORDERS_FILE = real_orders
    store.CREWS_FILE = real_crews
