---
name: build
description: Build an approved ticket: tests first, code, self-review, pull request to demo-dev, Jira update. Used by the tickets skill at stage 4, or directly with /build <KEY>.
metadata:
  user-invocable: true
  argument-hint: <TICKET-KEY>
---

Ticket: $1 (or the ticket from my-lab.txt). Work in the sdlc-build mode; switch to it if you are not in it.

# Build

Preconditions: plans/<KEY>.md exists, and the Jira ticket has a comment starting with "Approved" from someone other than you after the "Spec for review" comment. Write `Requester approval: approved by <author> in Jira on <YYYY-MM-DD>` and the comment link into the plan. If plans/<KEY>.md is missing on this machine, rebuild it from the "Spec for review" comment. If there is no approval, stop and say the spec is waiting for the requester.

1. Move the ticket to In Progress and comment "Build started".
2. Follow the build order in your mode rules exactly.

Facts that save you turns:
- Tests: `.venv/bin/python -m pytest -q`. Tests must not change data/work_orders.csv; copy it to a temp dir in a fixture.
- The user name for the branch is the user line in my-lab.txt. Never open lab.env.
- Change note: write changes/<KEY>.md, never CHANGELOG.md.
- PR: `./scripts/lab-gh pr create --base demo-dev --label <user> --title "<KEY>: <title>" --body-file <file>`. The body starts with `Opened by <name> for <KEY>.` then the sections of .github/pull_request_template.md.
- The pr-gate hook runs before every push and PR. If it refuses, it prints the missing checklist item. Fix that item. Never add --no-verify.
- Self-review subagent prompt: "Compare `git diff origin/demo-dev...HEAD` with plans/<KEY>.md. List each acceptance criterion as met or not met with evidence. List any file changed outside Work units. Nothing else."
- At the end: comment the PR link on the Jira ticket, move it to In Review, say CI is now reviewing the pull request, and end with the "Your links" block.
