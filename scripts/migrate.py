"""
Rollback instructions:
1. Stop the application (e.g. ./run.sh or server process).
2. (Optional) If orders changed in SQLite and need to be preserved:
   sqlite3 -header -csv data/fieldops.db "SELECT * FROM work_orders;" > data/work_orders.csv
3. Restore fieldops/store.py from git:
   git checkout origin/demo-dev -- fieldops/store.py
4. Start the application:
   ./run.sh
"""
import csv
import os
import sqlite3
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DEFAULT_CSV = os.path.join(DATA_DIR, "work_orders.csv")
DEFAULT_DB = os.path.join(DATA_DIR, "fieldops.db")

CREATE_TABLE_SQL = """
CREATE TABLE work_orders (
    id INTEGER PRIMARY KEY,
    site TEXT,
    equipment TEXT,
    description TEXT,
    priority INTEGER,
    status TEXT,
    crew TEXT,
    customer_name TEXT,
    customer_phone TEXT,
    created TEXT
);
"""

INSERT_SQL = """
INSERT INTO work_orders (id, site, equipment, description, priority, status, crew, customer_name, customer_phone, created)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def migrate_csv_to_sqlite(csv_path=DEFAULT_CSV, db_path=DEFAULT_DB):
    if os.path.exists(db_path):
        raise FileExistsError(f"Database file already exists at {db_path}. Migration stopped.")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}.")

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)

    for row in rows:
        cur.execute(
            INSERT_SQL,
            (
                int(row["id"]),
                row.get("site", "") or "",
                row.get("equipment", "") or "",
                row.get("description", "") or "",
                int(row.get("priority") or 3),
                row.get("status", "") or "",
                row.get("crew", "") or "",
                row.get("customer_name", "") or "",
                row.get("customer_phone", "") or "",
                row.get("created", "") or "",
            ),
        )

    conn.commit()
    conn.close()

    return len(rows)


def main():
    db_path = os.environ.get("FIELDOPS_DB", DEFAULT_DB)
    csv_path = os.environ.get("FIELDOPS_CSV", DEFAULT_CSV)

    try:
        count = migrate_csv_to_sqlite(csv_path, db_path)
        print(f"Migrated {count} orders from {csv_path} to {db_path}")
    except FileExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
