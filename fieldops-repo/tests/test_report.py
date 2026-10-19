import re
import shutil
import pytest
from fieldops import report, store


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    src_orders = store.ORDERS_FILE
    src_crews = store.CREWS_FILE
    dst_orders = str(data_dir / "work_orders.csv")
    dst_crews = str(data_dir / "crews.csv")
    shutil.copy(src_orders, dst_orders)
    shutil.copy(src_crews, dst_crews)
    monkeypatch.setattr(store, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(store, "ORDERS_FILE", dst_orders)
    monkeypatch.setattr(store, "CREWS_FILE", dst_crews)
    return data_dir


def test_mask_phone_helper():
    assert report.mask_phone("415-555-1234") == "415-555-****"
    assert report.mask_phone("510-555-9876") == "510-555-****"


def test_daily_report_masks_phone_numbers(isolated_data):
    output = report.daily_report()
    # No full 10-digit phone number in NXX-NXX-XXXX format should appear
    full_phones = re.findall(r"\b\d{3}-\d{3}-\d{4}\b", output)
    assert full_phones == [], f"Found unmasked phone numbers in report: {len(full_phones)}"
    # Masked phone numbers in NXX-NXX-**** format must be present
    masked_phones = re.findall(r"\b\d{3}-\d{3}-\*{4}", output)
    assert len(masked_phones) > 0, "Expected masked phone numbers in daily report"
