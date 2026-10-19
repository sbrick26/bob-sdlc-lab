# store.py - work order storage (SQLite backend, KAN-158)
# Work orders are stored in a SQLite database.
# Set FIELDOPS_DB env-var to override the default database path (used by tests).
# Crews remain in crews.csv.
import csv
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")
# Keep ORDERS_FILE so any caller that imported it still finds the attribute.
ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")

_DEFAULT_DB = os.path.join(DATA_DIR, "fieldops.db")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]


def _db_path():
    return os.environ.get("FIELDOPS_DB", _DEFAULT_DB)


def _connect():
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    return con


def _ensure_table(con):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS work_orders (
            id              INTEGER PRIMARY KEY,
            site            TEXT NOT NULL DEFAULT '',
            equipment       TEXT NOT NULL DEFAULT '',
            description     TEXT NOT NULL DEFAULT '',
            priority        INTEGER NOT NULL DEFAULT 3,
            status          TEXT NOT NULL DEFAULT 'open',
            crew            TEXT NOT NULL DEFAULT '',
            customer_name   TEXT NOT NULL DEFAULT '',
            customer_phone  TEXT NOT NULL DEFAULT '',
            created         TEXT NOT NULL DEFAULT ''
        )
        """
    )


def _row_to_dict(row):
    d = dict(row)
    d["id"] = int(d["id"])
    d["priority"] = int(d["priority"] or 3)
    return d


def load_orders():
    with _connect() as con:
        _ensure_table(con)
        rows = con.execute("SELECT * FROM work_orders ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


def save_orders(orders):
    with _connect() as con:
        _ensure_table(con)
        con.execute("DELETE FROM work_orders")
        for o in orders:
            con.execute(
                """
                INSERT INTO work_orders
                    (id, site, equipment, description, priority, status,
                     crew, customer_name, customer_phone, created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(o.get("id", 0)),
                    o.get("site", ""),
                    o.get("equipment", ""),
                    o.get("description", ""),
                    int(o.get("priority") or 3),
                    o.get("status", "open"),
                    o.get("crew", ""),
                    o.get("customer_name", ""),
                    o.get("customer_phone", ""),
                    o.get("created", ""),
                ),
            )


def load_crews():
    crews = []
    f = open(CREWS_FILE, newline="")
    for row in csv.DictReader(f):
        row["skills"] = [s.strip() for s in row["skills"].split(";") if s.strip()]
        crews.append(row)
    f.close()
    return crews


def get_order(order_id):
    with _connect() as con:
        _ensure_table(con)
        row = con.execute(
            "SELECT * FROM work_orders WHERE id = ?", (int(order_id),)
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def update_order(order_id, **fields):
    allowed = {k for k in FIELDS if k != "id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_order(order_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [int(order_id)]
    with _connect() as con:
        _ensure_table(con)
        rowcount = con.execute(
            f"UPDATE work_orders SET {set_clause} WHERE id = ?", values
        ).rowcount
    if rowcount == 0:
        return None
    return get_order(order_id)
