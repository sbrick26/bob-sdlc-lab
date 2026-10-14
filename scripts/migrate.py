"""One-time move of work orders from data/work_orders.csv to data/fieldops.db.

Run: python scripts/migrate.py
Safe to run twice: orders already in the database are left as they are.
The CSV file is only read, never changed or deleted.

ROLLBACK (go back to the CSV file)
1. Stop the app (and the nightly job) so nobody saves while you work.
2. Orders saved after the migration exist only in the database. Keep them:
   sqlite3 -header -csv data/fieldops.db "SELECT id, site, equipment,
   description, priority, status, crew, customer_name, customer_phone,
   created FROM work_orders ORDER BY rowid" > /tmp/work_orders_export.csv
3. Replace data/work_orders.csv with that export (or keep the original file
   if you do not need the newer edits).
4. Revert fieldops/store.py to the CSV version: git revert the KAN-158 commit.
5. Move data/fieldops.db out of the way (rename it), then start ./run.sh and
   check the orders table, assign and close.
"""
import csv
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from fieldops import store  # noqa: E402


def migrate(csv_path=None, db_path=None):
    """Copy orders from the CSV into the database. Returns how many were added."""
    csv_path = csv_path or store.ORDERS_FILE
    db_path = db_path or store.DB_FILE
    conn = store.connect(db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        with open(csv_path, newline="") as f, conn:
            for row in csv.DictReader(f):
                conn.execute(store.UPSERT.replace("INSERT OR REPLACE", "INSERT OR IGNORE"),
                             store._values(row))
        after = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    finally:
        conn.close()
    return after - before


if __name__ == "__main__":
    print("Copied %d orders into %s" % (migrate(), os.path.normpath(store.DB_FILE)))
