# audit.py - append-only audit trail for assign and close
# the log holds who, when, order number and change. never phone numbers or names.
import datetime
import os

from fieldops import assign as assign_rules
from fieldops import store

LOG_FILE = os.path.join(store.DATA_DIR, "audit.log")


def record(who, order_id, change):
    when = datetime.datetime.now().isoformat(timespec="seconds")
    line = " | ".join([when, str(who), "order " + str(order_id), str(change)])
    f = open(LOG_FILE, "a")
    f.write(line.replace("\n", " ") + "\n")
    f.close()


def assign(who, order_id, crew_id):
    ok = assign_rules.assign_order(order_id, crew_id)
    if ok:
        record(who, order_id, "assigned to crew " + str(crew_id))
    return ok


def close(who, order_id):
    found = store.update_order(order_id, status="closed")
    if found is None:
        return False
    record(who, order_id, "status changed to closed")
    return True
