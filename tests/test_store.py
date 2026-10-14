import csv
import hashlib
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_SRC = os.path.join(ROOT, "data", "work_orders.csv")
CREWS_SRC = os.path.join(ROOT, "data", "crews.csv")
MIGRATE = os.path.join(ROOT, "scripts", "migrate.py")

sys.path.insert(0, ROOT)
from fieldops import store  # noqa: E402


def _load_migrate():
    spec = importlib.util.spec_from_file_location("migrate", MIGRATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _csv_rows():
    with open(CSV_SRC, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    shutil.copy(CSV_SRC, d / "work_orders.csv")
    shutil.copy(CREWS_SRC, d / "crews.csv")
    monkeypatch.setattr(store, "ORDERS_FILE", str(d / "work_orders.csv"))
    monkeypatch.setattr(store, "CREWS_FILE", str(d / "crews.csv"))
    monkeypatch.setattr(store, "DB_FILE", str(d / "fieldops.db"))
    return d


@pytest.fixture
def migrated(data_dir):
    _load_migrate().migrate(str(data_dir / "work_orders.csv"), str(data_dir / "fieldops.db"))
    return data_dir


def test_migrate_creates_db_with_all_rows(data_dir):
    db = data_dir / "fieldops.db"
    _load_migrate().migrate(str(data_dir / "work_orders.csv"), str(db))
    assert db.exists()
    con = sqlite3.connect(str(db))
    count = con.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    blank_site = con.execute(
        "SELECT COUNT(*) FROM work_orders WHERE site = '' OR site IS NULL").fetchone()[0]
    con.close()
    rows = _csv_rows()
    assert count == len(rows)
    assert blank_site == len([r for r in rows if not r["site"]])
    assert blank_site > 0


def test_migrate_is_idempotent(data_dir):
    m = _load_migrate()
    csv_path, db = str(data_dir / "work_orders.csv"), str(data_dir / "fieldops.db")
    m.migrate(csv_path, db)
    store.update_order(1001, status="closed")
    m.migrate(csv_path, db)
    m.migrate(csv_path, db)
    assert len(store.load_orders()) == len(_csv_rows())
    assert store.get_order(1001)["status"] == "closed"


def test_migrate_leaves_csv_untouched(data_dir):
    before = _sha(str(data_dir / "work_orders.csv"))
    _load_migrate().migrate(str(data_dir / "work_orders.csv"), str(data_dir / "fieldops.db"))
    store.update_order(1001, status="closed")
    assert _sha(str(data_dir / "work_orders.csv")) == before


def test_migrate_script_runs_from_cli(data_dir):
    subprocess.run([sys.executable, MIGRATE, str(data_dir / "work_orders.csv"),
                    str(data_dir / "fieldops.db")], check=True, cwd=ROOT,
                   capture_output=True)
    assert (data_dir / "fieldops.db").exists()


def test_migrate_script_has_rollback_note_at_top():
    with open(MIGRATE) as f:
        head = f.read(1500).lower()
    assert "rollback" in head
    assert "work_orders.csv" in head


def test_load_orders_matches_csv(migrated):
    orders = store.load_orders()
    rows = _csv_rows()
    assert [o["id"] for o in orders] == [int(r["id"]) for r in rows]
    assert all(isinstance(o["priority"], int) for o in orders)
    assert set(orders[0].keys()) == set(store.FIELDS)
    first = rows[0]
    assert orders[0]["site"] == first["site"]
    assert orders[0]["customer_phone"] == first["customer_phone"]


def test_get_order(migrated):
    assert store.get_order("1001")["id"] == 1001
    assert store.get_order(999999) is None


def test_update_order_persists_and_ignores_unknown_fields(migrated):
    updated = store.update_order(1001, crew="C1", status="assigned", bogus="x", id=5)
    assert updated["crew"] == "C1" and updated["status"] == "assigned"
    again = store.get_order(1001)
    assert again["crew"] == "C1" and again["status"] == "assigned"
    assert again["id"] == 1001
    assert "bogus" not in again
    assert store.update_order(999999, status="closed") is None


def test_save_orders_roundtrip(migrated):
    orders = store.load_orders()
    orders[0]["description"] = "changed"
    store.save_orders(orders[:5])
    loaded = store.load_orders()
    assert len(loaded) == 5
    assert loaded[0]["description"] == "changed"


def test_load_crews_still_from_csv(migrated):
    crews = store.load_crews()
    assert crews and isinstance(crews[0]["skills"], list)
