# Change log

One entry per PR, newest first: ticket key, what, why.

KAN-158: Work orders now live in SQLite (data/fieldops.db), copied by `python scripts/migrate.py`.
Why: every save rewrote the whole CSV file, so two people saving at once could lose an edit.
