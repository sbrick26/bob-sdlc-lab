# store.py - work order storage
# work orders live in SQLite (data/fieldops.db). crews are still a CSV file.
# ORDERS_FILE is the old CSV, kept for scripts/migrate.py and the way back.
import csv
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")
DB_FILE = os.path.join(DATA_DIR, "fieldops.db")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]

SCHEMA = """CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY,
    site TEXT NOT NULL DEFAULT '',
    equipment TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 3,
    status TEXT NOT NULL DEFAULT '',
    crew TEXT NOT NULL DEFAULT '',
    customer_name TEXT NOT NULL DEFAULT '',
    customer_phone TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL DEFAULT ''
)"""

UPSERT = "INSERT OR REPLACE INTO work_orders (%s) VALUES (%s)" % (
    ", ".join(FIELDS), ", ".join("?" for _ in FIELDS))


def connect(path=None):
    conn = sqlite3.connect(path or DB_FILE)
    conn.execute(SCHEMA)
    return conn


def _values(order):
    row = dict((k, order.get(k, "")) for k in FIELDS)
    row["id"] = int(row["id"])
    row["priority"] = int(row["priority"] or 3)
    return [row[k] for k in FIELDS]


def load_orders():
    conn = connect()
    try:
        rows = conn.execute("SELECT %s FROM work_orders ORDER BY rowid" % ", ".join(FIELDS))
        return [dict(zip(FIELDS, r)) for r in rows]
    finally:
        conn.close()


def save_orders(orders):
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM work_orders")
            conn.executemany(UPSERT, [_values(o) for o in orders])
    finally:
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
    for o in load_orders():
        if o["id"] == int(order_id):
            return o
    return None


def update_order(order_id, **fields):
    found = get_order(order_id)
    if found is None:
        return None
    for k in fields:
        if k in FIELDS and k != "id":
            found[k] = fields[k]
    conn = connect()
    try:
        with conn:
            conn.execute(UPSERT, _values(found))
    finally:
        conn.close()
    return found
