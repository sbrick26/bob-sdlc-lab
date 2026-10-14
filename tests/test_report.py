from fieldops import report, store

PHONE = "415-555-0199"


def _prepare(temp_store):
    store.update_order(9001, site="North Substation", customer_phone=PHONE)
    store.update_order(9003, site="North Substation", customer_phone="212-555-0111")


def test_report_masks_phone_numbers(temp_store):
    _prepare(temp_store)
    text = report.daily_report()
    assert "415-555-****" in text
    assert "212-555-****" in text


def test_report_has_no_full_phone_number(temp_store):
    _prepare(temp_store)
    text = report.daily_report()
    assert PHONE not in text
    assert "0199" not in text
    assert "212-555-0111" not in text
