# Change log

One entry per PR, newest first: ticket key, what, why.

- KAN-158: Work orders now live in SQLite (data/fieldops.db) via scripts/migrate.py; store.py keeps its function signatures.
  Why: concurrent saves to the single CSV file lost edits. The CSV is kept untouched as a fallback with a rollback note in the script.

