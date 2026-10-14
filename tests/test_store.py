import csv
import os
import sqlite3
import shutil
import pytest
from fieldops import store

SAMPLE_CSV = [
    {
        "id": "1001",
        "site": "North Substation",
        "equipment": "transformer",
        "description": "Oil leak at base of T2",
        "priority": "1",
        "status": "open",
        "crew": "",
        "customer_name": "Test Customer 1",
        "customer_phone": "415-555-0142",
        "created": "2026-09-02",
    },
    {
        "id": "1002",
        "site": "",
        "equipment": "feeder",
        "description": "Feeder tripping",
        "priority": "2",
        "status": "open",
        "crew": "A",
        "customer_name": "Test Customer 2",
        "customer_phone": "415-555-0177",
        "created": "2026-09-04",
    },
]


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    csv_path = tmp_path / "work_orders.csv"
    db_path = tmp_path / "fieldops.db"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=store.FIELDS)
        writer.writeheader()
        for row in SAMPLE_CSV:
            writer.writerow(row)

    monkeypatch.setenv("FIELDOPS_DB", str(db_path))
    return {"csv_path": str(csv_path), "db_path": str(db_path), "tmp_path": tmp_path}


def test_rollback_note_present():
    import scripts.migrate as migrate
    doc = migrate.__doc__ or ""
    with open("scripts/migrate.py") as f:
        content = f.read()
    assert "Rollback" in content or "rollback" in content
    assert "1." in content or "1)" in content


def test_migrate_copies_every_order(temp_env):
    import scripts.migrate as migrate
    result = migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])
    assert result == len(SAMPLE_CSV)
    assert os.path.exists(temp_env["db_path"])

    conn = sqlite3.connect(temp_env["db_path"])
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM work_orders")
    count = cur.fetchone()[0]
    conn.close()
    assert count == len(SAMPLE_CSV)


def test_load_orders_matches_csv(temp_env):
    import scripts.migrate as migrate
    migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])

    orders = store.load_orders()
    assert len(orders) == len(SAMPLE_CSV)
    first = orders[0]
    assert first["id"] == 1001
    assert isinstance(first["id"], int)
    assert first["priority"] == 1
    assert isinstance(first["priority"], int)
    assert first["site"] == "North Substation"
    assert first["equipment"] == "transformer"
    assert first["status"] == "open"
    assert first["crew"] == ""

    second = orders[1]
    assert second["id"] == 1002
    assert second["site"] == ""
    assert second["crew"] == "A"


def test_update_order_changes_one_row(temp_env):
    import scripts.migrate as migrate
    migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])

    updated = store.update_order(1001, crew="B", status="assigned")
    assert updated is not None
    assert updated["crew"] == "B"
    assert updated["status"] == "assigned"

    # verify in store and database
    order1 = store.get_order(1001)
    assert order1["crew"] == "B"
    assert order1["status"] == "assigned"

    order2 = store.get_order(1002)
    assert order2["crew"] == "A"
    assert order2["status"] == "open"


def test_get_order(temp_env):
    import scripts.migrate as migrate
    migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])

    o = store.get_order(1001)
    assert o is not None
    assert o["id"] == 1001

    assert store.get_order(9999) is None


def test_save_orders_replaces_all(temp_env):
    import scripts.migrate as migrate
    migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])

    new_orders = [
        {
            "id": 2001,
            "site": "South Substation",
            "equipment": "rack",
            "description": "New rack install",
            "priority": 3,
            "status": "open",
            "crew": "",
            "customer_name": "Test Customer 3",
            "customer_phone": "415-555-0199",
            "created": "2026-10-01",
        }
    ]
    store.save_orders(new_orders)

    orders = store.load_orders()
    assert len(orders) == 1
    assert orders[0]["id"] == 2001
    assert orders[0]["site"] == "South Substation"


def test_csv_untouched(temp_env):
    import scripts.migrate as migrate
    with open(temp_env["csv_path"], "r") as f:
        before = f.read()

    migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])

    with open(temp_env["csv_path"], "r") as f:
        after = f.read()

    assert before == after


def test_migrate_refuses_existing_db(temp_env):
    import scripts.migrate as migrate
    migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])

    with pytest.raises(Exception):
        migrate.migrate_csv_to_sqlite(temp_env["csv_path"], temp_env["db_path"])
