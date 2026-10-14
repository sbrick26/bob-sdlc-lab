import csv
import hashlib
import importlib.util
import os
import shutil
import sqlite3

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
REAL_DATA = os.path.join(ROOT, "data")
MIGRATE_PY = os.path.join(ROOT, "scripts", "migrate.py")


def load_migrate():
    spec = importlib.util.spec_from_file_location("migrate", MIGRATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture
def env(tmp_path, monkeypatch):
    from fieldops import store
    data = tmp_path / "data"
    data.mkdir()
    for name in ("work_orders.csv", "crews.csv"):
        shutil.copy(os.path.join(REAL_DATA, name), data / name)
    monkeypatch.setattr(store, "ORDERS_FILE", str(data / "work_orders.csv"))
    monkeypatch.setattr(store, "CREWS_FILE", str(data / "crews.csv"))
    monkeypatch.setattr(store, "DB_FILE", str(data / "fieldops.db"))
    return data


def run_migrate(env):
    return load_migrate().migrate(str(env / "work_orders.csv"), str(env / "fieldops.db"))


def csv_rows(env):
    with open(env / "work_orders.csv", newline="") as f:
        return list(csv.DictReader(f))


def db_count(env):
    con = sqlite3.connect(str(env / "fieldops.db"))
    try:
        return con.execute("select count(*) from work_orders").fetchone()[0]
    finally:
        con.close()


def test_migrate_creates_db_and_reports_count(env, capsys):
    assert not (env / "fieldops.db").exists()
    load_migrate().main(str(env / "work_orders.csv"), str(env / "fieldops.db"))
    out = capsys.readouterr().out
    assert (env / "fieldops.db").exists()
    assert "40" in out
    for row in csv_rows(env):
        assert row["customer_name"] not in out


def test_migrate_keeps_every_order(env):
    run_migrate(env)
    assert db_count(env) == len(csv_rows(env)) == 40
    from fieldops import store
    ids = [o["id"] for o in store.load_orders()]
    assert 1035 in ids and 1036 in ids
    assert store.get_order(1035)["site"] == ""
    assert store.get_order(1036)["site"] == ""


def test_migrate_twice_is_safe(env):
    run_migrate(env)
    from fieldops import store
    store.update_order(1001, status="closed")
    run_migrate(env)
    assert db_count(env) == 40
    ids = [o["id"] for o in store.load_orders()]
    assert len(ids) == len(set(ids))
    assert store.get_order(1001)["status"] == "closed"


def test_store_functions_same_behaviour(env):
    run_migrate(env)
    from fieldops import store
    expected = csv_rows(env)
    orders = store.load_orders()
    assert [o["id"] for o in orders] == [int(r["id"]) for r in expected]
    for o, r in zip(orders, expected):
        assert isinstance(o["id"], int) and isinstance(o["priority"], int)
        assert o["priority"] == int(r["priority"] or 3)
        assert list(o.keys()) == store.FIELDS
        for k in store.FIELDS:
            if k not in ("id", "priority"):
                assert o[k] == r[k]

    assert store.get_order("1001")["id"] == 1001
    assert store.get_order(999999) is None

    changed = store.update_order(1001, status="assigned", crew="B", id=5, bogus="x")
    assert changed["status"] == "assigned" and changed["crew"] == "B"
    assert changed["id"] == 1001
    assert store.get_order(1001)["crew"] == "B"
    assert store.update_order(999999, status="closed") is None
    assert len(store.load_orders()) == 40

    store.save_orders(orders[:3])
    assert [o["id"] for o in store.load_orders()] == [o["id"] for o in orders[:3]]

    crews = store.load_crews()
    assert crews and isinstance(crews[0]["skills"], list)


def test_assign_and_close_still_work(env):
    run_migrate(env)
    from fieldops import assign, store
    from fieldops.app import app
    crew_id = store.load_crews()[0]["id"]
    open_id = next(o["id"] for o in store.load_orders() if o["status"] == "open")
    assert assign.assign_order(open_id, crew_id) is True
    o = store.get_order(open_id)
    assert o["status"] == "assigned" and o["crew"] == crew_id

    client = app.test_client()
    assert client.get("/").status_code == 200
    r = client.post("/close/%d" % open_id)
    assert r.status_code == 302
    assert store.get_order(open_id)["status"] == "closed"


def test_csv_left_untouched(env):
    before = digest(str(env / "work_orders.csv"))
    run_migrate(env)
    run_migrate(env)
    from fieldops import store
    store.update_order(1001, status="closed")
    assert digest(str(env / "work_orders.csv")) == before
    assert digest(os.path.join(REAL_DATA, "work_orders.csv")) == digest(
        str(env / "work_orders.csv"))


def test_migrate_has_rollback_note():
    with open(MIGRATE_PY) as f:
        text = f.read()
    top = text.split("\nimport ", 1)[0]
    assert "rollback" in top.lower()
    for n in ("1.", "2.", "3."):
        assert any(line.lstrip("#  ").startswith(n) for line in top.splitlines())
