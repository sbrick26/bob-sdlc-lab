"""
scripts/migrate.py  --  one-time migration from work_orders.csv to SQLite.

Rollback steps (how to go back to the CSV file):
1. Stop the app (kill the process or disable run.sh).
2. Run: git checkout fieldops/store.py
   This restores the CSV-reading version of store.py.
3. Keep using data/work_orders.csv as before.
   Note: edits made in SQLite after migration are NOT copied back to the CSV.
   There is no export tool in this ticket.

Run from fieldops-repo/:
    python scripts/migrate.py

The FIELDOPS_DB environment variable overrides the default database path
(data/fieldops.db).  If the database already exists this script stops
immediately without changing anything.
"""

import csv
import os
import sqlite3
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
# scripts/ is one level below fieldops-repo/
REPO_ROOT = os.path.dirname(REPO_ROOT)
DATA_DIR = os.path.join(REPO_ROOT, "data")
CSV_FILE = os.path.join(DATA_DIR, "work_orders.csv")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]

CREATE_TABLE = """
CREATE TABLE work_orders (
    id             INTEGER PRIMARY KEY,
    site           TEXT    NOT NULL DEFAULT '',
    equipment      TEXT    NOT NULL DEFAULT '',
    description    TEXT    NOT NULL DEFAULT '',
    priority       INTEGER NOT NULL DEFAULT 3,
    status         TEXT    NOT NULL DEFAULT 'open',
    crew           TEXT    NOT NULL DEFAULT '',
    customer_name  TEXT    NOT NULL DEFAULT '',
    customer_phone TEXT    NOT NULL DEFAULT '',
    created        TEXT    NOT NULL DEFAULT ''
);
"""


def main():
    db_path = os.environ.get("FIELDOPS_DB") or os.path.join(DATA_DIR, "fieldops.db")

    if os.path.exists(db_path):
        print(
            f"Migration skipped: {db_path} already exists. "
            "Delete it first if you want to re-migrate."
        )
        return

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(CREATE_TABLE)
            with open(CSV_FILE, newline="", encoding="utf-8") as f:
                rows = [
                    (
                        int(row["id"]),
                        row.get("site", ""),
                        row.get("equipment", ""),
                        row.get("description", ""),
                        int(row.get("priority") or 3),
                        row.get("status", "open"),
                        row.get("crew", ""),
                        row.get("customer_name", ""),
                        row.get("customer_phone", ""),
                        row.get("created", ""),
                    )
                    for row in csv.DictReader(f)
                ]
            conn.executemany(
                "INSERT INTO work_orders "
                "(id, site, equipment, description, priority, status, "
                " crew, customer_name, customer_phone, created) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        count = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
        print(f"Migration complete: {count} orders written to {db_path}.")
    except Exception:
        conn.close()
        if os.path.exists(db_path):
            os.remove(db_path)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
