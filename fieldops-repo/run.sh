#!/bin/sh
# run.sh - start FieldOps on http://localhost:8077
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
exec .venv/bin/python -m fieldops.app
