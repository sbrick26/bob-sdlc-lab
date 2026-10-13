# FieldOps

FieldOps is the work-order system for Sequoia Power & Light field crews.
Dispatch uses it to see open orders, give each order to a crew, and close it.
Data lives in `data/work_orders.csv` and `data/crews.csv`.

Run the web screen: `./run.sh`, then open http://localhost:8077
Run the nightly batch: `python -m fieldops.nightly` (add `--dry-run` to only print)
Print the daily report: `python -m fieldops.report`

Built in 2010. Patched many times since. There are no tests.
