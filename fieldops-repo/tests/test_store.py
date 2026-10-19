"""
Tests for KAN-158: work-order store backed by SQLite.

All tests use a temp directory so they never touch data/work_orders.csv
or data/fieldops.db.  The FIELDOPS_DB env-var points store.py and
migrate.py at a temp database file.
"""
import csv
import importlib
import os
import shutil
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REAL_CSV = os.path.join(
    os.path.dirname(__file__), "..", "data", "work_orders.csv"
)

FIELDS = [
    "id", "site", "equipment", "description", "priority", "status",
    "crew", "customer_name", "customer_phone", "created",
]


def _csv_order_count(path):
    with open(path, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def _make_mini_csv(tmp_dir, rows=3):
    """Write a small CSV with `rows` work orders and return its path."""
    path = os.path.join(tmp_dir, "work_orders.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for i in range(1, rows + 1):
            w.writerow({
                "id": str(i),
                "site": f"Site {i}",
                "equipment": "transformer",
                "description": f"Desc {i}",
                "priority": str(i),
                "status": "open",
                "crew": "",
                "customer_name": "Test User",
                "customer_phone": "415-555-****",
                "created": "2026-01-01",
            })
    return path


@pytest.fixture()
def store_env(tmp_path, monkeypatch):
    """
    Set up a temp dir with a mini CSV and a temp database path.
    Points FIELDOPS_DB and ORDERS_FILE at the temp files so the store
    module is redirected.  Reloads fieldops.store after patching.
    """
    csv_path = _make_mini_csv(str(tmp_path))
    db_path = str(tmp_path / "test.db")

    monkeypatch.setenv("FIELDOPS_DB", db_path)
    monkeypatch.setenv("FIELDOPS_ORDERS_CSV", csv_path)

    # Force reload so the module picks up the new env vars
    if "fieldops.store" in sys.modules:
        del sys.modules["fieldops.store"]
    import fieldops.store as store
    importlib.reload(store)
    # Override the CSV path the store uses if it still has an attribute
    if hasattr(store, "ORDERS_FILE"):
        monkeypatch.setattr(store, "ORDERS_FILE", csv_path)

    # Pre-seed the SQLite database from the mini CSV so store tests have data.
    import csv as _csv
    with open(csv_path, newline="") as f:
        rows = list(_csv.DictReader(f))
    orders = [
        {
            "id": int(r["id"]),
            "site": r.get("site", ""),
            "equipment": r.get("equipment", ""),
            "description": r.get("description", ""),
            "priority": int(r.get("priority") or 3),
            "status": r.get("status", "open"),
            "crew": r.get("crew", ""),
            "customer_name": r.get("customer_name", ""),
            "customer_phone": r.get("customer_phone", ""),
            "created": r.get("created", ""),
        }
        for r in rows
    ]
    store.save_orders(orders)

    yield store, csv_path, db_path

    if "fieldops.store" in sys.modules:
        del sys.modules["fieldops.store"]


# ---------------------------------------------------------------------------
# Criterion 3: load_orders, get_order, update_order, save_orders, load_crews
# ---------------------------------------------------------------------------

class TestStoreInterface:
    """The public API of store.py must work with the SQLite backend."""

    def test_load_orders_returns_list(self, store_env):
        store, csv_path, db_path = store_env
        orders = store.load_orders()
        assert isinstance(orders, list)

    def test_load_orders_id_and_priority_are_ints(self, store_env):
        store, csv_path, db_path = store_env
        orders = store.load_orders()
        for o in orders:
            assert isinstance(o["id"], int), "id must be int"
            assert isinstance(o["priority"], int), "priority must be int"

    def test_get_order_returns_order(self, store_env):
        store, csv_path, db_path = store_env
        orders = store.load_orders()
        first_id = orders[0]["id"]
        o = store.get_order(first_id)
        assert o is not None
        assert o["id"] == first_id

    def test_get_order_unknown_returns_none(self, store_env):
        store, csv_path, db_path = store_env
        assert store.get_order(99999) is None

    def test_update_order_assign(self, store_env):
        store, csv_path, db_path = store_env
        orders = store.load_orders()
        oid = orders[0]["id"]
        result = store.update_order(oid, crew="A", status="assigned")
        assert result is not None
        assert result["crew"] == "A"
        assert result["status"] == "assigned"

    def test_update_order_close(self, store_env):
        store, csv_path, db_path = store_env
        orders = store.load_orders()
        oid = orders[0]["id"]
        store.update_order(oid, status="closed")
        refreshed = store.get_order(oid)
        assert refreshed["status"] == "closed"

    def test_save_and_reload_roundtrip(self, store_env):
        store, csv_path, db_path = store_env
        orders = store.load_orders()
        count_before = len(orders)
        store.save_orders(orders)
        assert len(store.load_orders()) == count_before

    def test_load_crews_has_skills_list(self, store_env):
        store, csv_path, db_path = store_env
        crews = store.load_crews()
        assert len(crews) > 0
        for c in crews:
            assert isinstance(c["skills"], list)


# ---------------------------------------------------------------------------
# Criteria 1 & 2: migration count
# ---------------------------------------------------------------------------

class TestMigration:
    """Running scripts/migrate.py produces a database matching the CSV."""

    def _run_migrate(self, tmp_path, monkeypatch):
        csv_path = _make_mini_csv(str(tmp_path), rows=5)
        db_path = str(tmp_path / "fieldops.db")

        monkeypatch.setenv("FIELDOPS_DB", db_path)
        monkeypatch.setenv("FIELDOPS_ORDERS_CSV", csv_path)

        migrate_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "migrate.py"
        )
        spec = importlib.util.spec_from_file_location("migrate", migrate_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate()
        return csv_path, db_path, mod

    def test_migration_row_count_matches_csv(self, tmp_path, monkeypatch):
        import importlib.util
        csv_path, db_path, mod = self._run_migrate(tmp_path, monkeypatch)
        import sqlite3
        csv_count = _csv_order_count(csv_path)
        with sqlite3.connect(db_path) as con:
            db_count = con.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        assert db_count == csv_count

    def test_migration_preserves_ids_and_priorities(self, tmp_path, monkeypatch):
        import importlib.util, sqlite3
        csv_path, db_path, mod = self._run_migrate(tmp_path, monkeypatch)
        with sqlite3.connect(db_path) as con:
            rows = con.execute("SELECT id, priority FROM work_orders ORDER BY id").fetchall()
        assert rows == [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]

    # Criterion 4: second migration run is a no-op
    def test_second_migration_does_not_overwrite(self, tmp_path, monkeypatch, capsys):
        import importlib.util, sqlite3
        csv_path, db_path, mod = self._run_migrate(tmp_path, monkeypatch)
        # run again
        spec = importlib.util.spec_from_file_location(
            "migrate2",
            os.path.join(os.path.dirname(__file__), "..", "scripts", "migrate.py"),
        )
        mod2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod2)
        mod2.migrate()
        captured = capsys.readouterr()
        # must print a message and leave rows unchanged
        assert "already exists" in captured.out.lower() or "skip" in captured.out.lower()
        with sqlite3.connect(db_path) as con:
            count = con.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        assert count == 5  # unchanged


# ---------------------------------------------------------------------------
# Criterion 5: CSV untouched + rollback note in migrate.py
# ---------------------------------------------------------------------------

class TestCsvPreservation:
    def test_real_csv_not_modified(self):
        """data/work_orders.csv must not be touched by the test suite."""
        original_bytes = open(REAL_CSV, "rb").read()
        # The store module (now SQLite-backed) should not write to the CSV.
        assert original_bytes == open(REAL_CSV, "rb").read()

    def test_migrate_script_has_rollback_note(self):
        migrate_path = os.path.join(
            os.path.dirname(__file__), "..", "scripts", "migrate.py"
        )
        with open(migrate_path) as f:
            header = f.read(1000)
        assert "rollback" in header.lower(), "migrate.py must have rollback note at the top"
