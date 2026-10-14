"""Tests for KAN-160: phone masking in the daily report."""
import shutil
import tempfile
import os
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    """Copy data/ to a temp directory so tests never modify work_orders.csv."""
    src = os.path.join(os.path.dirname(__file__), "..", "data")
    dst = str(tmp_path / "data")
    shutil.copytree(src, dst)
    import fieldops.store as store_mod
    monkeypatch.setattr(store_mod, "DATA_DIR", dst)
    monkeypatch.setattr(store_mod, "ORDERS_FILE", os.path.join(dst, "work_orders.csv"))
    monkeypatch.setattr(store_mod, "CREWS_FILE", os.path.join(dst, "crews.csv"))


# ---------------------------------------------------------------------------
# Unit test: mask_phone helper
# ---------------------------------------------------------------------------

def test_mask_phone_replaces_last_segment():
    from fieldops.report import mask_phone
    assert mask_phone("415-555-0142") == "415-555-****"


def test_mask_phone_different_area_code():
    from fieldops.report import mask_phone
    assert mask_phone("510-555-0119") == "510-555-****"


def test_mask_phone_last_segment_has_no_raw_digits():
    from fieldops.report import mask_phone
    result = mask_phone("650-555-0108")
    last_segment = result.split("-")[-1]
    assert not any(ch.isdigit() for ch in last_segment), (
        f"Expected no digits in last segment, got: {last_segment!r}"
    )


# ---------------------------------------------------------------------------
# Integration test: daily_report output
# ---------------------------------------------------------------------------

def test_daily_report_no_full_phone_number():
    """No phone number in the report should have a digit-bearing last segment."""
    from fieldops.report import daily_report
    report = daily_report()
    # Each line that was originally a phone like XXX-XXX-NNNN must be masked.
    # We check that no substring matching NXX-NXX-<4digits> appears anywhere.
    import re
    matches = re.findall(r'\d{3}-\d{3}-\d{4}', report)
    assert matches == [], (
        f"Report contains unmasked phone numbers: {matches}"
    )


def test_daily_report_masked_phones_present():
    """The report should still show phone placeholders (e.g. 415-555-****)."""
    from fieldops.report import daily_report
    report = daily_report()
    assert "****" in report, "Expected masked phone placeholders in report"
