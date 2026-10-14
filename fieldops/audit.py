# audit.py - append-only audit trail for assign and close
# one line per action: when, who, order, change. no customer data.
import datetime
import os

from fieldops import assign as assign_rules
from fieldops import store

AUDIT_FILE = os.path.join(store.DATA_DIR, "audit.log")


def record(who, order_id, change):
    when = datetime.datetime.now().isoformat(timespec="seconds")
    line = when + " " + str(who) + " order " + str(order_id) + " " + change + "\n"
    f = open(AUDIT_FILE, "a")
    f.write(line)
    f.close()


def assign(who, order_id, crew_id):
    ok = assign_rules.assign_order(order_id, crew_id)
    if ok:
        record(who, order_id, "assigned crew " + crew_id)
    return ok


def close(who, order_id):
    o = store.update_order(order_id, status="closed")
    if o is not None:
        record(who, order_id, "closed")
    return o
