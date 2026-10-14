# Stages

Work out the stage from Jira and GitHub every time, in this order. Never trust memory from an earlier chat.

| Stage | How you know | What you do |
|---|---|---|
| 1. Not started | Jira status To Do | Ask "Start <KEY>?". On yes: move to In Progress, comment "Started with Bob", go to stage 2 |
| 2. Planning | Status In Progress and no plan summary comment on the ticket | Plan skill: design questions, spec, review in chat |
| 3. Waiting for requester | Status In Review, no pull request, no Jira comment starting with "Approved" after the plan summary | Say the spec is waiting for the requester to comment Approved on the ticket. Give the links. Stop |
| 4. Build | A Jira comment starting with "Approved" after the plan summary, and no pull request | Build skill: tests first, code, pull request |
| 5. Fix | Pull request open and the CI check failed, the review verdict is FAIL, or a reviewer asked for changes | Fix skill |
| 6. Waiting for approval | Pull request open, all checks green, no change requests | Say it is waiting for the guide to approve and merge. Give the links. Stop |
| 7. Done | Pull request merged or Jira status Done | Say it is done and point to the dashboard. Stop |

Find the pull request with `./scripts/lab-gh pr list --head <user>/<KEY> --state all --json number,url,state,mergedAt`.
Read checks with `./scripts/lab-gh pr checks <number>` and review comments with `./scripts/lab-gh pr view <number> --comments`.
