import datetime
import os
from fieldops import assign as assign_mod, store

AUDIT_FILE = os.path.join(store.DATA_DIR, "audit.log")


def record(who, order_id, change):
    actor = who if who else "unknown"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    line = f"{now} | {actor} | {order_id} | {change}\n"
    with open(AUDIT_FILE, "a") as f:
        f.write(line)


def assign(order_id, crew_id, who="unknown"):
    actor = who if who else "unknown"
    ok = assign_mod.assign_order(order_id, crew_id)
    if ok:
        record(actor, order_id, f"assigned crew {crew_id}")
    return ok


def close(order_id, who="unknown"):
    actor = who if who else "unknown"
    res = store.update_order(order_id, status="closed")
    if res is not None:
        record(actor, order_id, "closed")
    return res
