# store.py - work order storage
# everything lives in one CSV file. read it all, write it all.
# TODO fix later (2014): two people saving at once can lose an edit
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")
CREWS_FILE = os.path.join(DATA_DIR, "crews.csv")

FIELDS = ["id", "site", "equipment", "description", "priority", "status",
          "crew", "customer_name", "customer_phone", "created"]


def load_orders():
    orders = []
    f = open(ORDERS_FILE, newline="")
    for row in csv.DictReader(f):
        row["id"] = int(row["id"])
        row["priority"] = int(row["priority"] or 3)
        orders.append(row)
    f.close()
    return orders


def save_orders(orders):
    # rewrite the whole file every time
    f = open(ORDERS_FILE, "w", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for o in orders:
        w.writerow(dict((k, o.get(k, "")) for k in FIELDS))
    f.close()


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
    orders = load_orders()
    found = None
    for o in orders:
        if o["id"] == int(order_id):
            for k in fields:
                if k in FIELDS and k != "id":
                    o[k] = fields[k]
            found = o
    if found is None:
        return None
    save_orders(orders)
    return found
