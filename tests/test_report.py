import re
import shutil

import pytest

from fieldops import report, store


@pytest.fixture
def orders_copy(tmp_path, monkeypatch):
    dst = tmp_path / "work_orders.csv"
    shutil.copy(store.ORDERS_FILE, dst)
    monkeypatch.setattr(store, "ORDERS_FILE", str(dst))
    return dst


def test_mask_phone_keeps_first_two_segments():
    assert report.mask_phone("415-555-0142") == "415-555-****"


def test_report_masks_every_phone(orders_copy):
    out = report.daily_report()
    assert "****" in out
    assert not re.search(r"\d{3}-\d{3}-\d{4}", out)
    for o in store.load_orders():
        assert o["customer_phone"] not in out
