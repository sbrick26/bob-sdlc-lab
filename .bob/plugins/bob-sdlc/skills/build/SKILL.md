---
name: build
description: Implement an approved plans/<KEY>.md tests first, self-review, open the PR, update Jira. Use in the Build mode or when the user runs /build <KEY>.
metadata:
  user-invocable: true
  argument-hint: <TICKET-KEY>
---

Ticket: $1. If you are not in the sdlc-build mode, switch to it first. Stop after the PR is open and the Jira ticket is In Review.

# Build

Preconditions: plans/<KEY>.md exists and says "Requester approval: approved". If not, stop and say so.

Follow the build order in your mode rules exactly. Facts that save you turns:

- Change note: write changes/<KEY>.md, never CHANGELOG.md.
- Tests: `python -m pytest -q`. Python is `python3` on macOS. Create .venv with `./run.sh` if imports fail.
- The store is CSV until ticket 2 lands. Tests must not change data/work_orders.csv; copy it to a temp dir in a fixture.
- Branch: `git checkout -b <lab name>/<KEY>`. The lab name is the LAB_USER line in lab.env at the repo root (read it). If the file is missing, ask.
- PR: `./scripts/lab-gh pr create --base main --label <lab name> --title "<KEY>: <title>" --body-file <file>`. It runs gh as the shared lab account, so nobody signs in to GitHub. The body starts with `Opened by <Name> Lab for <KEY>.` then the sections of .github/pull_request_template.md.
- The pr-gate hook runs before every push and PR. If it refuses, it prints the missing checklist item. Fix that item. Never add --no-verify.
- Self-review subagent prompt: "Compare `git diff main` with plans/<KEY>.md. List each acceptance criterion as met or not met with evidence. List any file changed outside Work units. Nothing else."
- Jira at the end: add a comment with the PR link (addOrEditJiraIssueComment or jira_add_comment), then move the ticket to In Review (transitionJiraIssue, or jira_get_transitions then jira_transition_issue).
