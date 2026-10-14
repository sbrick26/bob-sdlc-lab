import csv
import hashlib
import importlib.util
import os
import sqlite3

import pytest

from fieldops import store

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MIGRATE_PATH = os.path.join(ROOT, "scripts", "migrate.py")


def load_migrate():
    spec = importlib.util.spec_from_file_location("migrate", MIGRATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_rows(n=40, blank_sites=(7, 23)):
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": 2000 + i,
            "site": "" if i in blank_sites else "Test Site %d" % (i % 4),
            "equipment": "feeder",
            "description": "made-up order %d" % i,
            "priority": (i % 3) + 1,
            "status": "open",
            "crew": "",
            "customer_name": "Test Customer",
            "customer_phone": "000-000-0000",
            "created": "2026-01-01",
        })
    return rows


@pytest.fixture
def migration(tmp_path):
    csv_path = tmp_path / "orders.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=store.FIELDS)
        w.writeheader()
        w.writerows(make_rows())
    return load_migrate(), str(csv_path), str(tmp_path / "test.db")


def db_count(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    finally:
        conn.close()


def test_migrate_copies_every_order(migration, monkeypatch):
    migrate, csv_path, db_path = migration
    copied = migrate.migrate(csv_path, db_path)
    assert os.path.exists(db_path)
    assert copied == 40
    monkeypatch.setattr(store, "DB_FILE", db_path)
    ids = sorted(o["id"] for o in store.load_orders())
    assert ids == [2000 + i for i in range(1, 41)]


def test_migrate_count_matches_csv(migration):
    migrate, csv_path, db_path = migration
    migrate.migrate(csv_path, db_path)
    with open(csv_path, newline="") as f:
        csv_rows = list(csv.DictReader(f))
    assert db_count(db_path) == len(csv_rows) == 40
    conn = sqlite3.connect(db_path)
    try:
        blanks = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE site = ''").fetchone()[0]
    finally:
        conn.close()
    assert blanks == 2


def test_migrate_is_repeatable(migration, monkeypatch):
    migrate, csv_path, db_path = migration
    migrate.migrate(csv_path, db_path)
    monkeypatch.setattr(store, "DB_FILE", db_path)
    store.update_order(2001, status="closed")
    migrate.migrate(csv_path, db_path)
    assert db_count(db_path) == 40
    assert store.get_order(2001)["status"] == "closed"


def test_migrate_leaves_csv_unchanged(migration):
    migrate, csv_path, db_path = migration
    with open(csv_path, "rb") as f:
        before = hashlib.sha256(f.read()).hexdigest()
    migrate.migrate(csv_path, db_path)
    with open(csv_path, "rb") as f:
        after = hashlib.sha256(f.read()).hexdigest()
    assert before == after


def test_migrate_has_rollback_note():
    with open(MIGRATE_PATH) as f:
        head = "".join(f.readlines()[:40])
    assert "rollback" in head.lower()
    for step in ("1.", "2.", "3."):
        assert step in head


def test_load_orders_shape(temp_store):
    orders = store.load_orders()
    assert len(orders) == 3
    for o in orders:
        assert isinstance(o["id"], int)
        assert isinstance(o["priority"], int)
        assert set(o) == set(store.FIELDS)


def test_get_order(temp_store):
    assert store.get_order("9001")["description"] == "test open"
    assert store.get_order(9999) is None


def test_update_order_saves(temp_store):
    updated = store.update_order(9001, status="assigned", crew="B")
    assert updated["status"] == "assigned"
    again = store.get_order(9001)
    assert again["status"] == "assigned" and again["crew"] == "B"
    assert store.update_order(9999, status="closed") is None


def test_save_orders_roundtrip(temp_store):
    orders = store.load_orders()
    orders[0]["priority"] = 1
    orders[0]["site"] = ""
    store.save_orders(orders)
    assert store.load_orders() == orders


def test_load_crews_unchanged(temp_store):
    crews = store.load_crews()
    assert [c["id"] for c in crews] == ["A", "B", "C", "D"]
    assert crews[1]["skills"] == ["feeder", "rack"]
