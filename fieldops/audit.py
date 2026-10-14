# audit.py - append-only audit trail for assign and close
# never writes customer name or phone; only who, when, order id and the change
import datetime
import os

from fieldops import assign as assign_rules
from fieldops import store

LOG_FILE = os.path.join(store.DATA_DIR, "audit.log")


def record(who, order_id, change):
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = stamp + " who=" + str(who) + " order=" + str(order_id) + " change=" + change + "\n"
    f = open(LOG_FILE, "a")
    f.write(line)
    f.close()


def assign(who, order_id, crew_id):
    ok = assign_rules.assign_order(order_id, crew_id)
    if ok:
        record(who, order_id, "assigned crew " + str(crew_id))
    return ok


def close(who, order_id):
    found = store.update_order(order_id, status="closed")
    if found is not None:
        record(who, order_id, "closed")
    return found is not None
