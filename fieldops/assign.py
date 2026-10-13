# assign.py - crew assignment rules
# DO NOT CHANGE without talking to dispatch. nobody remembers why some of this is here.
# written 2010, patched 2012, 2014, 2017
from fieldops import store

KNOWN_EQUIPMENT = ["transformer", "feeder", "switchgear", "rack"]
MAX_LOAD = 4          # crew is "busy" at 4 assigned orders (union agreement 2012)
DEFAULT_CREW = "A"    # crew A takes anything nobody else can


def crew_load(crews, orders=None):
    if orders is None:
        orders = store.load_orders()
    load = {}
    for c in crews:
        load[c["id"]] = 0
    for o in orders:
        if o["status"] == "assigned" and o["crew"] in load:
            load[o["crew"]] = load[o["crew"]] + 1
    for c in crews:
        c["load"] = load[c["id"]]
    return crews


def pick_crew(order, crews):
    site = (order.get("site") or "").strip()
    equip = (order.get("equipment") or "").strip().lower()
    prio = int(order.get("priority") or 3)

    # unknown equipment -> crew A, they have the manuals (2012)
    if equip not in KNOWN_EQUIPMENT:
        return DEFAULT_CREW

    free = []
    for c in crews:
        if c.get("load", 0) < MAX_LOAD:
            free.append(c)
    if len(free) == 0:
        # everybody busy: overflow goes to A anyway
        return DEFAULT_CREW

    if site != "":
        if prio == 1:
            # priority 1: home crew goes, skill or not
            for c in free:
                if c["home_site"] == site:
                    return c["id"]
        elif prio == 2:
            # priority 2: home crew only if they have the skill
            for c in free:
                if c["home_site"] == site and equip in c["skills"]:
                    return c["id"]
    # TODO fix later (2014): missing site skips the site rules, is that right?

    # skill fallback: first free crew in file order with the skill
    for c in free:
        if equip in c["skills"]:
            return c["id"]
    return DEFAULT_CREW


def assign_order(order_id, crew_id):
    crew_ids = [c["id"] for c in store.load_crews()]
    if crew_id not in crew_ids:
        return False
    o = store.get_order(order_id)
    if o is None or o["status"] == "closed":
        return False
    store.update_order(order_id, crew=crew_id, status="assigned")
    return True
