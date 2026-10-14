# store.py - work order storage
# orders live in SQLite (fieldops.db); crews live in crews.csv
import csv
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DEFAULT_DB = os.path.join(DATA_DIR, "fieldops.db")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")

FIELDS = [
    "id",
    "site",
    "equipment",
    "description",
    "priority",
    "status",
    "crew",
    "customer_name",
    "customer_phone",
    "created",
]


def _get_db_path():
    return os.environ.get("FIELDOPS_DB", DEFAULT_DB)


def _row_to_order(row):
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "site": row[1] if row[1] is not None else "",
        "equipment": row[2] if row[2] is not None else "",
        "description": row[3] if row[3] is not None else "",
        "priority": int(row[4]) if row[4] is not None else 3,
        "status": row[5] if row[5] is not None else "",
        "crew": row[6] if row[6] is not None else "",
        "customer_name": row[7] if row[7] is not None else "",
        "customer_phone": row[8] if row[8] is not None else "",
        "created": row[9] if row[9] is not None else "",
    }


def load_orders():
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, site, equipment, description, priority, status, crew, customer_name, customer_phone, created FROM work_orders ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return [_row_to_order(row) for row in rows]


def save_orders(orders):
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS work_orders (
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
        )
        """
    )
    cur.execute("DELETE FROM work_orders")
    for o in orders:
        cur.execute(
            """
            INSERT INTO work_orders (id, site, equipment, description, priority, status, crew, customer_name, customer_phone, created)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(o["id"]),
                o.get("site", "") or "",
                o.get("equipment", "") or "",
                o.get("description", "") or "",
                int(o.get("priority") or 3),
                o.get("status", "") or "",
                o.get("crew", "") or "",
                o.get("customer_name", "") or "",
                o.get("customer_phone", "") or "",
                o.get("created", "") or "",
            ),
        )
    conn.commit()
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
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, site, equipment, description, priority, status, crew, customer_name, customer_phone, created FROM work_orders WHERE id = ?",
        (int(order_id),),
    )
    row = cur.fetchone()
    conn.close()
    return _row_to_order(row)


def update_order(order_id, **fields):
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return None

    valid_fields = {k: v for k, v in fields.items() if k in FIELDS and k != "id"}
    if not valid_fields:
        return get_order(order_id)

    set_clause = ", ".join(f"{k} = ?" for k in valid_fields.keys())
    values = list(valid_fields.values())
    values.append(int(order_id))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(f"UPDATE work_orders SET {set_clause} WHERE id = ?", values)
    if cur.rowcount == 0:
        conn.close()
        return None
    conn.commit()
    conn.close()
    return get_order(order_id)
