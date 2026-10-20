# FieldOps

FieldOps is the work-order system of Sequoia Power & Light, a fictional utility. Dispatch uses it to see open orders, give each order to a crew and close the order. It was built in 2010 and patched many times. It shipped with no tests.

Run every command from this folder (`cd fieldops-repo`). Lab setup makes the virtual environment in `.venv` here.

| To do this | Run |
|---|---|
| Open the web screen | `./run.sh`, then open http://localhost:8077. It makes `.venv` if it is missing. |
| Run the nightly batch | `.venv/bin/python -m fieldops.nightly`. Add `--dry-run` to only print. |
| Print the daily report | `.venv/bin/python -m fieldops.report` |
| Run the tests | `.venv/bin/python -m pytest -q` |
| Start the MCP server | `.venv/bin/python -m fieldops.mcp_server` |

| Folder | What is in it |
|---|---|
| `fieldops/` | The code |
| `data/` | `work_orders.csv` and `crews.csv` |
| `tests/` | The tests. Tests must not change `data/work_orders.csv`. |
| `plans/` | One spec per ticket: `plans/<KEY>.md` |
| `changes/` | One change note per ticket: `changes/<KEY>.md` |
