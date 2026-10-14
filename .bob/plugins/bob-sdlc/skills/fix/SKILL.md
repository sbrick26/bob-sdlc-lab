---
name: fix
description: >-
  Fix a pull request after CI or a reviewer found problems: read the findings, fix them, rerun the tests, push. Used by the tickets skill at stage 5, or when the user says "fix it" or "fix the PR".
metadata:
  user-invocable: true
  argument-hint: <TICKET-KEY>
---

Ticket: $1 (or the ticket from my-lab.txt). Work in the sdlc-build mode; switch to it if you are not in it.

# Fix

1. Find the pull request: `./.bob/scripts/lab-gh pr list --head <user>/<KEY> --json number,url`.
2. Collect what needs fixing:
   - failed checks: `./.bob/scripts/lab-gh pr checks <number>`;
   - the review verdict comment (it starts with "SDLC gate: review") and its blocking findings: `./.bob/scripts/lab-gh pr view <number> --comments`;
   - reviewer change requests on the PR.
3. List the findings to the user in a short table (finding, file, what you will change). Fix the blocking ones first.
4. Check out the branch `<user>/<KEY>`, make the smallest changes that address each finding, stay inside the plan's Work units, run the tests until green.
5. Commit "<KEY>: address review findings", push. CI runs again on its own.
6. Comment on the PR which findings you fixed. Say CI is reviewing again, switch back to the sdlc mode (SDLC Agent) and say so, and end with the "Your links" block.
