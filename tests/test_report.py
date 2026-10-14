import shutil

import pytest

from fieldops import report, store


@pytest.fixture
def temp_orders(tmp_path, monkeypatch):
    dst = tmp_path / "work_orders.csv"
    shutil.copy(store.ORDERS_FILE, dst)
    monkeypatch.setattr(store, "ORDERS_FILE", str(dst))
    return str(dst)


def test_report_shows_only_masked_phone_numbers(temp_orders):
    phones = [o["customer_phone"] for o in store.load_orders() if o["customer_phone"]]
    assert phones
    text = report.daily_report()
    assert "415-555-****" in text
    for phone in phones:
        assert phone not in text
