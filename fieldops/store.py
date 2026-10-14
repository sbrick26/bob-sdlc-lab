# store.py - work order storage
# work orders live in SQLite (data/fieldops.db, created by scripts/migrate.py).
# crews are still read from data/crews.csv.
import csv
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")  # migration source only
DB_FILE = os.path.join(DATA_DIR, "fieldops.db")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]

SCHEMA = ("CREATE TABLE IF NOT EXISTS work_orders ("
          "id INTEGER PRIMARY KEY, site TEXT NOT NULL DEFAULT '', "
          "equipment TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', "
          "priority INTEGER NOT NULL DEFAULT 3, status TEXT NOT NULL DEFAULT '', "
          "crew TEXT NOT NULL DEFAULT '', customer_name TEXT NOT NULL DEFAULT '', "
          "customer_phone TEXT NOT NULL DEFAULT '', created TEXT NOT NULL DEFAULT '')")


def _connect():
    con = sqlite3.connect(DB_FILE, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def load_orders():
    con = _connect()
    try:
        rows = con.execute("SELECT * FROM work_orders ORDER BY rowid").fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]


def save_orders(orders):
    # replace the table contents in one transaction
    con = _connect()
    try:
        with con:
            con.execute("DELETE FROM work_orders")
            for o in orders:
                con.execute(
                    "INSERT INTO work_orders (%s) VALUES (%s)"
                    % (", ".join(FIELDS), ", ".join("?" * len(FIELDS))),
                    [o.get(k, "") for k in FIELDS])
    finally:
        con.close()


def load_crews():
    crews = []
    f = open(CREWS_FILE, newline="")
    for row in csv.DictReader(f):
        row["skills"] = [s.strip() for s in row["skills"].split(";") if s.strip()]
        crews.append(row)
    f.close()
    return crews


def get_order(order_id):
    con = _connect()
    try:
        row = con.execute("SELECT * FROM work_orders WHERE id = ?",
                          (int(order_id),)).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def update_order(order_id, **fields):
    # update only the named columns so concurrent edits to other orders survive
    cols = [k for k in fields if k in FIELDS and k != "id"]
    con = _connect()
    try:
        with con:
            if cols:
                con.execute("UPDATE work_orders SET %s WHERE id = ?"
                            % ", ".join("%s = ?" % c for c in cols),
                            [fields[c] for c in cols] + [int(order_id)])
    finally:
        con.close()
    return get_order(order_id)
