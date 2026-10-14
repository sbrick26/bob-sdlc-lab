---
key_hint: KAN-160
title: Mask customer phone numbers and keep an audit trail
assignee: alex
touches:
  - fieldops/report.py
  - fieldops/audit.py
  - fieldops/app.py
  - tests/test_report.py
  - tests/test_audit.py
does_not_touch:
  - fieldops/store.py
  - fieldops/assign.py
  - data/work_orders.csv
---

## What I need

Customer phone numbers appear in the daily report. Mask them, and keep a trail of who changed what. Compliance wants to see, for any order, who assigned it or closed it, and when.

## Done when

- The daily report shows phone numbers like `415-555-****`, never in full.
- Every assign and every close made through `fieldops/audit.py` writes one line to `data/audit.log`: who, when, which order, what changed.
- The audit log only grows. Old lines are never changed.
- `python -m pytest tests/test_report.py tests/test_audit.py` runs green.

## Hints for the builder

- The report is built in `fieldops/report.py` (`daily_report`).
- Put the trail in a new `fieldops/audit.py` with one function, for example `record(who, order_id, change)`.
- Assign and close go through `assign.assign_order` and `store.update_order`. This ticket may not edit those files, so wrap them in `audit.py` (for example `audit.assign(...)`, `audit.close(...)`). Wiring the web screen to the wrappers is a follow-up ticket.
- Run: `python -m fieldops.report` and check no full phone number shows.
