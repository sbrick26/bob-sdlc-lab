# audit.py - append-only audit trail for field operations
# KAN-160: record who assigned or closed an order, and when
import datetime
import os
from fieldops import assign as _assign_mod
from fieldops import store as _store_mod

LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "audit.log"
)


def record(who, order_id, change):
    """Append one pipe-delimited line to the audit log.

    Format: <ISO-8601 UTC timestamp> | who=<who> | order=<order_id> | change=<change>
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = "{} | who={} | order={} | change={}\n".format(ts, who, order_id, change)
    with open(LOG_PATH, "a") as f:
        f.write(line)


def assign(who, order_id, crew_id):
    """Assign an order to a crew and record the event in the audit log.

    Calls assign.assign_order() then appends one audit line.
    """
    _assign_mod.assign_order(order_id, crew_id)
    record(who, order_id, "assigned:{}".format(crew_id))


def close(who, order_id):
    """Close an order and record the event in the audit log.

    Calls store.update_order() then appends one audit line.
    """
    _store_mod.update_order(order_id, status="closed")
    record(who, order_id, "closed")
