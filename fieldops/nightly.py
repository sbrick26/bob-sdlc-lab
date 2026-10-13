# nightly.py - batch job, cron runs it at 02:00
# gives every open order a crew. use --dry-run to only print.
import sys
from fieldops import store, assign


def run(dry_run=False):
    orders = store.load_orders()
    crews = assign.crew_load(store.load_crews(), orders)
    by_id = {}
    for c in crews:
        by_id[c["id"]] = c
    todo = [o for o in orders if o["status"] == "open"]
    todo.sort(key=lambda o: (o["priority"], o["created"], o["id"]))
    counts = {}
    for o in todo:
        cid = assign.pick_crew(o, crews)
        o["crew"] = cid
        o["status"] = "assigned"
        by_id[cid]["load"] = by_id[cid].get("load", 0) + 1
        counts[cid] = counts.get(cid, 0) + 1
        print("order " + str(o["id"]) + " (P" + str(o["priority"]) + ", " +
              (o["site"] or "?") + ", " + o["equipment"] + ") -> crew " + cid)
    if not dry_run:
        store.save_orders(orders)
    print("-" * 40)
    print("assigned " + str(len(todo)) + " open orders" + (" (dry run, nothing saved)" if dry_run else ""))
    for cid in sorted(counts):
        print("  crew " + cid + ": " + str(counts[cid]))


if __name__ == "__main__":
    run("--dry-run" in sys.argv)
