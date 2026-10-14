# Change log

One entry per PR, newest first: ticket key, what, why.

- KAN-160: Mask customer phone numbers in the daily report (415-555-****) and add fieldops/audit.py with append-only audit.assign and audit.close.
  Why: phone numbers are personal data, and dispatch needs a record of who assigned or closed each order.
