---
key_hint: KAN-157
title: Lock in what the crew assignment service does today
assignee: sam
touches:
  - tests/test_assign.py
  - tests/conftest.py
does_not_touch:
  - fieldops/
  - data/
  - requirements.txt
---

## What I need

The crew assignment service has no tests. Nobody will touch it. Generate tests that lock in what it does today, so the next person can change it without fear. Do not change how it behaves. If something looks wrong, write it down, do not fix it.

## Done when

- `python -m pytest` runs green.
- There is a test for the priority 1 rule (the home crew goes first).
- There is a test for the site rule, and one for the skill fallback.
- There is a test for an order with no site.
- No file in `fieldops/` or `data/` changed.

## Hints for the builder

- The rules are in `fieldops/assign.py` (`pick_crew`, `assign_order`, `crew_load`).
- Crews are in `data/crews.csv`. Build crew and order dicts in the test, do not read the real CSV.
- `assign_order` writes to the CSV. In `tests/conftest.py`, point `store.ORDERS_FILE` and `store.CREWS_FILE` at a temp copy.
- Run: `python -m pytest tests/test_assign.py -v`
