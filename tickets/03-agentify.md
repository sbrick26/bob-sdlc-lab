---
key_hint: KAN-159
title: Let dispatch run work orders by asking in plain words
assignee: jordan
touches:
  - fieldops/mcp_server.py
  - tests/test_mcp_server.py
  - fieldops/README.md (one line)
  - requirements.txt (add mcp)
does_not_touch:
  - fieldops/store.py
  - fieldops/assign.py
  - fieldops/report.py
  - data/
---

## What I need

I want to say "show open orders at the North Substation and assign the top two to crew B" and have it done. Dispatch should not need the web screen for simple jobs. It must use the same rules as the web screen.

## Done when

- An MCP server gives three tools: `list_orders(site, status)`, `assign_order(id, crew)`, `close_order(id)`.
- After it is added to your local `.bob/mcp.json` (that file is yours and is not committed), Bob can call it from the IDE.
- The sentence above works: Bob lists the open North Substation orders and gives the top two to crew B.
- The web screen shows the same change.
- `python -m pytest tests/test_mcp_server.py` runs green.

## Hints for the builder

- Use the `mcp` Python package (FastMCP, stdio). Add `mcp` to `requirements.txt` in this ticket only.
- Call the functions in `fieldops/store.py` and `fieldops/assign.py`. Do not copy their logic.
- "Top" means lowest priority number first, then oldest `created` date.
- Start it: `python -m fieldops.mcp_server`
- Add one line to `fieldops/README.md` that says how to start it.
