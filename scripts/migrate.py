# migrate.py - one-time copy of work orders from data/work_orders.csv to data/fieldops.db
#
# Safe to run again: orders already in the database are kept as they are.
# The CSV file is only read, never changed.
#
# ROLLBACK: going back to the CSV file
#   1. Stop the FieldOps app and the nightly job.
#   2. If orders changed after the migration, export them from data/fieldops.db
#      to data/work_orders.csv first (same columns, same order). The script
#      does not do this for you. Skip this step if nothing changed.
#   3. Revert the fieldops/store.py change from KAN-158 (git revert the commit).
#   4. Delete data/fieldops.db (it is git-ignored).
#   5. Start the app with ./run.sh and check that the orders table shows.
import csv
import os
import sqlite3
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CSV_FILE = os.path.join(DATA_DIR, "work_orders.csv")
DB_FILE = os.path.join(DATA_DIR, "fieldops.db")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]

SCHEMA = """create table if not exists work_orders (
    id integer primary key,
    site text not null default '',
    equipment text not null default '',
    description text not null default '',
    priority integer not null default 3,
    status text not null default '',
    crew text not null default '',
    customer_name text not null default '',
    customer_phone text not null default '',
    created text not null default ''
)"""


def migrate(csv_path=CSV_FILE, db_path=DB_FILE):
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    con = sqlite3.connect(db_path)
    try:
        with con:
            con.execute(SCHEMA)
            for r in rows:
                values = [int(r["id"])]
                for k in FIELDS[1:]:
                    values.append(int(r[k] or 3) if k == "priority" else r[k])
                con.execute("insert or ignore into work_orders (%s) values (%s)"
                            % (", ".join(FIELDS), ", ".join("?" * len(FIELDS))), values)
    finally:
        con.close()
    return len(rows)


def main(csv_path=CSV_FILE, db_path=DB_FILE):
    print("Copied %d orders to the database." % migrate(csv_path, db_path))


if __name__ == "__main__":
    sys.exit(main())
