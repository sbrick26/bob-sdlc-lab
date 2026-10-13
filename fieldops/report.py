# report.py - daily report for the dispatch desk
# printed and pinned on the board every morning
import datetime
from fieldops import store

SITES = ["North Substation", "South Substation", "East Yard", "West Depot"]


def daily_report():
    orders = store.load_orders()
    out = "SEQUOIA POWER & LIGHT - FIELDOPS DAILY REPORT\n"
    out = out + "Date: " + datetime.date.today().isoformat() + "\n"
    out = out + "=" * 60 + "\n"
    for site in SITES + [""]:
        rows = [o for o in orders if o["site"] == site and o["status"] != "closed"]
        if len(rows) == 0:
            continue
        out = out + "\n" + (site or "SITE UNKNOWN") + " (" + str(len(rows)) + ")\n"
        for o in rows:
            out = out + "  #" + str(o["id"]) + " P" + str(o["priority"]) + " " + o["status"].ljust(8)
            out = out + " crew " + (o["crew"] or "-") + "  " + o["equipment"].ljust(11)
            out = out + " " + o["customer_name"] + " " + o["customer_phone"] + "\n"
    closed = len([o for o in orders if o["status"] == "closed"])
    out = out + "\nClosed orders on file: " + str(closed) + "\n"
    return out


if __name__ == "__main__":
    print(daily_report())
