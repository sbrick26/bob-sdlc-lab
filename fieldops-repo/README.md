# FieldOps

FieldOps is the work-order system for Sequoia Power & Light field crews.
Dispatch uses it to see open orders, give each order to a crew, and close it.
Data lives in `data/work_orders.csv` and `data/crews.csv` (in this folder, `fieldops-repo/`).

Run all commands from this folder (`cd fieldops-repo`). The lab setup creates the virtual environment in `.venv` here.

| What | Command |
|---|---|
| Web screen | `./run.sh` (makes `.venv` if missing, installs `requirements.txt`), then open http://localhost:8077 |
| Nightly batch | `.venv/bin/python -m fieldops.nightly` (add `--dry-run` to only print) |
| Daily report | `.venv/bin/python -m fieldops.report` |
| Tests | `.venv/bin/python -m pytest -q` (tests go in `tests/`) |

Ticket files live here too: specs in `plans/<KEY>.md`, change notes in `changes/<KEY>.md`.

Built in 2010. Patched many times since. There are no tests.
