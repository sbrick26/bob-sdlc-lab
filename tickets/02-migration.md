---
key_hint: FOPS-102
title: Move work orders from the CSV file to SQLite
assignee: priya
touches:
  - fieldops/store.py
  - scripts/migrate.py
  - tests/test_store.py
does_not_touch:
  - fieldops/assign.py
  - fieldops/app.py
  - fieldops/report.py
  - fieldops/nightly.py
  - data/work_orders.csv
---

## What I need

Work orders are in a CSV file that breaks when two people save at once. Move them to SQLite without losing an order, with a way back. The screens and the nightly job must keep working the same.

## Done when

- `python scripts/migrate.py` creates `data/fieldops.db` with every order in it.
- The number of orders in the database is the same as in the CSV file.
- `./run.sh` still shows the orders table, and assign and close still work.
- A rollback note says how to go back to the CSV file, step by step.

## Hints for the builder

- Keep the same functions in `fieldops/store.py`: `load_orders`, `save_orders`, `get_order`, `update_order`, `load_crews`. Other files call them.
- Do not delete `data/work_orders.csv`. It is the way back.
- Put the rollback note at the top of `scripts/migrate.py`.
- Check counts: `python -c "import csv;print(sum(1 for _ in csv.DictReader(open('data/work_orders.csv'))))"` and `sqlite3 data/fieldops.db "select count(*) from work_orders"`
- Run: `python -m pytest tests/test_store.py -v`
