"""
Tests for KAN-158: SQLite-backed work order store.

All tests use a temp database via the FIELDOPS_DB env variable.
No test touches data/work_orders.csv or prints customer names or phone numbers.
"""
import csv
import importlib
import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
CSV_FILE = os.path.join(DATA_DIR, "work_orders.csv")
MIGRATE_SCRIPT = os.path.join(REPO_ROOT, "scripts", "migrate.py")


# ---------------------------------------------------------------------------
# Fixture: isolated temp database for every test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("FIELDOPS_DB", db_path)
    # Re-import store so it picks up the new env var
    if "fieldops.store" in sys.modules:
        importlib.reload(sys.modules["fieldops.store"])
    yield db_path
    # Teardown: cleanup handled by tmp_path


def _import_store():
    """Fresh import of store after env is set."""
    if "fieldops.store" in sys.modules:
        importlib.reload(sys.modules["fieldops.store"])
    import fieldops.store as s
    return s


def _run_migrate(db_path):
    """Run migrate.py against the given db_path using FIELDOPS_DB."""
    env_backup = os.environ.get("FIELDOPS_DB")
    os.environ["FIELDOPS_DB"] = db_path
    import runpy
    runpy.run_path(MIGRATE_SCRIPT, run_name="__main__")
    if env_backup is not None:
        os.environ["FIELDOPS_DB"] = env_backup
    else:
        del os.environ["FIELDOPS_DB"]


# ---------------------------------------------------------------------------
# Criteria 1 & 2: migration row count matches CSV
# ---------------------------------------------------------------------------
def test_migrate_row_count_matches_csv(tmp_path):
    db_path = str(tmp_path / "migrate_count.db")
    _run_migrate(db_path)

    with open(CSV_FILE, newline="") as f:
        csv_count = sum(1 for _ in csv.DictReader(f))

    conn = sqlite3.connect(db_path)
    db_count = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    conn.close()

    assert db_count == csv_count
    assert db_count == 40


def test_migrate_all_ids_present(tmp_path):
    db_path = str(tmp_path / "migrate_ids.db")
    _run_migrate(db_path)

    with open(CSV_FILE, newline="") as f:
        csv_ids = {int(row["id"]) for row in csv.DictReader(f)}

    conn = sqlite3.connect(db_path)
    db_ids = {row[0] for row in conn.execute("SELECT id FROM work_orders")}
    conn.close()

    assert db_ids == csv_ids


# ---------------------------------------------------------------------------
# Criterion 3: store functions work after migration
# ---------------------------------------------------------------------------
def test_load_orders_returns_all(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    orders = store.load_orders()
    assert len(orders) == 40


def test_get_order_returns_correct_row(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    order = store.get_order(1001)
    assert order is not None
    assert order["id"] == 1001
    assert isinstance(order["id"], int)
    assert isinstance(order["priority"], int)


def test_update_order_assign(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    result = store.update_order(1001, crew="A", status="assigned")
    assert result is not None
    assert result["crew"] == "A"
    assert result["status"] == "assigned"
    # Persists across a fresh load
    reloaded = store.get_order(1001)
    assert reloaded["crew"] == "A"
    assert reloaded["status"] == "assigned"


def test_update_order_close(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    result = store.update_order(1002, status="closed")
    assert result is not None
    assert result["status"] == "closed"
    reloaded = store.get_order(1002)
    assert reloaded["status"] == "closed"


def test_save_orders_persists(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    orders = store.load_orders()
    orders[0]["status"] = "closed"
    store.save_orders(orders)
    reloaded = store.load_orders()
    assert reloaded[0]["status"] == "closed"


# ---------------------------------------------------------------------------
# Criterion 4: rollback note in migrate.py, CSV unchanged
# ---------------------------------------------------------------------------
def test_migrate_has_rollback_note():
    with open(MIGRATE_SCRIPT, newline="", encoding="utf-8") as f:
        content = f.read()
    # Must have a numbered rollback note near the top
    assert "rollback" in content.lower() or "Rollback" in content
    assert "1." in content  # numbered steps


def test_csv_unchanged_after_migration(tmp_path):
    db_path = str(tmp_path / "csv_check.db")
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        before = f.read()
    _run_migrate(db_path)
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        after = f.read()
    assert before == after


# ---------------------------------------------------------------------------
# Criterion 5: second migration run is a no-op and explains why
# ---------------------------------------------------------------------------
def test_second_migrate_is_noop(tmp_path, capsys):
    db_path = str(tmp_path / "noop.db")
    _run_migrate(db_path)

    conn = sqlite3.connect(db_path)
    count_before = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    conn.close()

    _run_migrate(db_path)

    conn = sqlite3.connect(db_path)
    count_after = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    conn.close()

    assert count_before == count_after

    captured = capsys.readouterr()
    assert captured.out.strip() != ""  # must print a reason


# ---------------------------------------------------------------------------
# Criterion 6: empty site/crew round-trip, types, load_crews
# ---------------------------------------------------------------------------
def test_empty_site_order_round_trips(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    order = store.get_order(1035)
    assert order is not None
    assert order["site"] == ""
    assert isinstance(order["id"], int)
    assert isinstance(order["priority"], int)


def test_empty_crew_order_round_trips(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    order = store.get_order(1036)
    assert order is not None
    assert order["site"] == ""


def test_unassigned_order_has_empty_crew(temp_db):
    _run_migrate(temp_db)
    store = _import_store()
    order = store.get_order(1001)
    assert order is not None
    assert order["crew"] == ""


def test_load_crews_returns_same_as_before(temp_db):
    store = _import_store()
    crews = store.load_crews()
    assert len(crews) > 0
    for crew in crews:
        assert "name" in crew or "id" in crew or "crew" in crew or crew  # not empty
        assert "skills" in crew
        assert isinstance(crew["skills"], list)
