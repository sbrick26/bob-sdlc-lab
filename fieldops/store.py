# store.py - work order storage
# work orders live in SQLite (data/fieldops.db, created by scripts/migrate.py).
# crews still come from data/crews.csv.
import csv
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")
DB_FILE = os.path.join(DATA_DIR, "fieldops.db")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]

COLUMNS = ", ".join(FIELDS)
PLACEHOLDERS = ", ".join("?" * len(FIELDS))


def _connect():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def _to_dict(row):
    return dict((k, row[k]) for k in FIELDS)


def load_orders():
    con = _connect()
    try:
        return [_to_dict(r) for r in con.execute(
            "select %s from work_orders order by rowid" % COLUMNS)]
    finally:
        con.close()


def save_orders(orders):
    con = _connect()
    try:
        with con:
            con.execute("delete from work_orders")
            for o in orders:
                con.execute("insert into work_orders (%s) values (%s)" % (COLUMNS, PLACEHOLDERS),
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
        row = con.execute("select %s from work_orders where id = ?" % COLUMNS,
                          (int(order_id),)).fetchone()
        return _to_dict(row) if row else None
    finally:
        con.close()


def update_order(order_id, **fields):
    changes = dict((k, v) for k, v in fields.items() if k in FIELDS and k != "id")
    con = _connect()
    try:
        with con:
            if changes:
                con.execute("update work_orders set %s where id = ?"
                            % ", ".join(k + " = ?" for k in changes),
                            list(changes.values()) + [int(order_id)])
    finally:
        con.close()
    return get_order(order_id)
