# store.py - work order storage (SQLite backend)
# Replaces the CSV read/write approach with a SQLite database.
# The five public functions keep their names and return shapes.
import csv
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")

# Allow tests (and operators) to override the database path via env var.
DB_PATH = os.environ.get("FIELDOPS_DB") or os.path.join(DATA_DIR, "fieldops.db")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]


def _get_db_path():
    """Return the active database path, honouring FIELDOPS_DB at call time."""
    return os.environ.get("FIELDOPS_DB") or os.path.join(DATA_DIR, "fieldops.db")


def _connect():
    return sqlite3.connect(_get_db_path())


def _row_to_dict(row):
    """Convert a sqlite3.Row (or tuple with FIELDS order) to a plain dict."""
    d = dict(zip(FIELDS, row))
    d["id"] = int(d["id"])
    d["priority"] = int(d["priority"] or 3)
    return d


def load_orders():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, site, equipment, description, priority, status, "
        "crew, customer_name, customer_phone, created FROM work_orders"
    ).fetchall()
    conn.close()
    return [_row_to_dict(tuple(r)) for r in rows]


def save_orders(orders):
    """Replace all rows in one transaction (used by nightly job)."""
    conn = _connect()
    with conn:
        conn.execute("DELETE FROM work_orders")
        conn.executemany(
            "INSERT INTO work_orders "
            "(id, site, equipment, description, priority, status, "
            " crew, customer_name, customer_phone, created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    int(o["id"]),
                    o.get("site", ""),
                    o.get("equipment", ""),
                    o.get("description", ""),
                    int(o.get("priority") or 3),
                    o.get("status", "open"),
                    o.get("crew", ""),
                    o.get("customer_name", ""),
                    o.get("customer_phone", ""),
                    o.get("created", ""),
                )
                for o in orders
            ],
        )
    conn.close()


def load_crews():
    crews = []
    f = open(CREWS_FILE, newline="")
    for row in csv.DictReader(f):
        row["skills"] = [s.strip() for s in row["skills"].split(";") if s.strip()]
        crews.append(row)
    f.close()
    return crews


def get_order(order_id):
    conn = _connect()
    row = conn.execute(
        "SELECT id, site, equipment, description, priority, status, "
        "crew, customer_name, customer_phone, created "
        "FROM work_orders WHERE id = ?",
        (int(order_id),),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def update_order(order_id, **fields):
    # Build a targeted UPDATE so we never rewrite other rows.
    allowed = {k: v for k, v in fields.items() if k in FIELDS and k != "id"}
    if not allowed:
        return get_order(order_id)
    sets = ", ".join(f"{k} = ?" for k in allowed)
    values = list(allowed.values()) + [int(order_id)]
    conn = _connect()
    with conn:
        cursor = conn.execute(
            f"UPDATE work_orders SET {sets} WHERE id = ?", values
        )
    conn.close()
    if cursor.rowcount == 0:
        return None
    return get_order(order_id)
