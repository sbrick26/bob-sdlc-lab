"""
scripts/migrate.py  --  one-time CSV to SQLite migration for KAN-158

ROLLBACK STEPS (if you need to go back to the CSV file):
  1. Stop the application (Ctrl-C or kill the process running run.sh).
  2. Restore the original fieldops/store.py from git:
         git checkout HEAD -- fieldops/store.py
  3. Restart the application:
         ./run.sh
  Note: data/work_orders.csv is never changed or deleted by this script.
        Any edits made to work orders after migration are stored only in
        data/fieldops.db and are NOT copied back to the CSV automatically.

Run from the fieldops-repo/ directory:
    python scripts/migrate.py
"""
import csv
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
CSV_PATH = os.environ.get(
    "FIELDOPS_ORDERS_CSV", os.path.join(DATA_DIR, "work_orders.csv")
)
DB_PATH = os.environ.get(
    "FIELDOPS_DB", os.path.join(DATA_DIR, "fieldops.db")
)

FIELDS = [
    "id", "site", "equipment", "description", "priority", "status",
    "crew", "customer_name", "customer_phone", "created",
]


def _csv_count(path):
    with open(path, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def migrate():
    if os.path.exists(DB_PATH):
        print(
            f"Database already exists at {DB_PATH}. "
            "Skipping migration to avoid overwriting existing data."
        )
        return

    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    csv_count = len(rows)

    con = sqlite3.connect(DB_PATH)
    try:
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
        with con:
            for row in rows:
                con.execute(
                    """
                    INSERT INTO work_orders
                        (id, site, equipment, description, priority, status,
                         crew, customer_name, customer_phone, created)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
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
                    ),
                )
        db_count = con.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    finally:
        con.close()

    print(f"Migration complete. CSV rows: {csv_count}, database rows: {db_count}.")
    if db_count != csv_count:
        print("WARNING: counts do not match.")


if __name__ == "__main__":
    migrate()
