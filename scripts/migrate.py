# migrate.py - copy work orders from data/work_orders.csv into data/fieldops.db
#
# ROLLBACK (back to the CSV store):
#   1. Stop the app.
#   2. Optional: export any edits made since the migration, for example
#      sqlite3 -header -csv data/fieldops.db "SELECT * FROM work_orders" > data/work_orders.csv
#      (data/work_orders.csv is never touched by this script, so skip this
#      step if you want the pre-migration data.)
#   3. Revert fieldops/store.py to the CSV version (git revert the KAN-158 commit).
#   4. Delete data/fieldops.db.
#   5. Start the app with ./run.sh.
#
# Safe to run more than once: rows already in the database are left as they are.
# Usage: python3 scripts/migrate.py [csv_path db_path]
import csv
import os
import sqlite3
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from fieldops.store import FIELDS, ORDERS_FILE, DB_FILE, SCHEMA  # noqa: E402


def migrate(csv_path=ORDERS_FILE, db_path=DB_FILE):
    con = sqlite3.connect(db_path)
    with con:
        con.execute(SCHEMA)
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                row["id"] = int(row["id"])
                row["priority"] = int(row["priority"] or 3)
                con.execute(
                    "INSERT OR IGNORE INTO work_orders (%s) VALUES (%s)"
                    % (", ".join(FIELDS), ", ".join("?" * len(FIELDS))),
                    [row.get(k, "") or "" if k not in ("id", "priority") else row[k]
                     for k in FIELDS])
    con.close()


if __name__ == "__main__":
    migrate(*sys.argv[1:3])
