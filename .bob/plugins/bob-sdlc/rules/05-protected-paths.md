# Protected paths

- Never edit .bob/, .github/, governance/ or tools/ in a ticket branch. CI fails any PR that touches them. The hook refuses the edit.
- Exception: your local .bob/mcp.json is yours. It is not committed.
- Changes to those paths are their own PR, reviewed by the platform owner.
