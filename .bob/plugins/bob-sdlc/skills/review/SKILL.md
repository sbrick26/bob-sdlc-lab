---
name: review
description: >-
  Review a branch or diff against its plan, the rules and the PR checklist, run the tests, and print the verdict block. Used by CI headless and by people in the Review mode or with /review.
metadata:
  user-invocable: true
  argument-hint: [TICKET-KEY]
---

Ticket: $1 (take it from the branch name when empty). End with the verdict block.

# Review

Inputs: a ticket key (from the branch name, pattern <name>/<KEY>) and a diff (`git diff origin/demo-dev...HEAD` or the file given).

1. Read fieldops-repo/plans/<KEY>.md. If it is missing, FAIL with one blocking finding.
2. Read the diff. For each file changed, check it is in Work units. Outside: blocking finding.
3. Check each acceptance criterion against the diff and the tests. Say met or not met with the evidence.
4. Run `cd fieldops-repo && .venv/bin/python -m pytest -q` (with no fieldops-repo/.venv, as in CI: `cd fieldops-repo && python -m pytest -q`). Record passed/total.
5. Check rules 01 to 06 in .bob/plugins/bob-sdlc/rules. A violation is blocking.
6. Check fieldops-repo/changes/<KEY>.md exists and names the key.
7. Print the verdict block from your mode rules. Nothing after it.
