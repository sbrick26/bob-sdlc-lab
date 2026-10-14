---
key_hint: KAN-161
title: Every PR must say which site it affects
assignee: guide
touches:
  - governance/pr-checklist.yaml
  - .github/pull_request_template.md
does_not_touch:
  - fieldops/
  - tests/
---

## What I need

Our dispatch lead wants to know, for every change, which site it touches before it ships. Add a line "Site:" to the PR template and make the PR gate refuse a push when changes/<KEY>.md has no "Site:" line.

## Done when

- The PR template has a "Site:" line under Ticket.
- The PR checklist has a new item that checks changes/{KEY}.md contains "Site:".
- A push without it is refused with a plain sentence saying what is missing.
- A push with it goes through.

## Hints for the builder

- Use the new-check skill. The checklist item type is `file_contains`.
- This touches protected paths, so the branch is `<name>/governance-site` and the PR is reviewed by the platform owner.
