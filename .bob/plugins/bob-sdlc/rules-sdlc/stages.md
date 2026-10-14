# Stages

Work out the stage from Jira and GitHub every time, in this order. Never trust memory from an earlier chat. Only the most recent "Spec for review" comment counts; earlier ones are history.

| Stage | How you know | What you do |
|---|---|---|
| 1. Not started | Jira status To Do | Ask "Start <KEY>?". On yes: move to In Progress, comment "Started with Bob", go to stage 2 |
| 2. Planning | Status In Progress and no pull request, and no "Spec for review" comment since the ticket last moved to In Progress | Plan skill: design questions, spec, review in chat |
| 3. Waiting for requester | Status In Review, no pull request, no comment starting with "Approved" after the most recent "Spec for review" comment | Say the spec is waiting for the requester to comment Approved on the ticket. Give the links. Stop |
| 4. Build | A comment starting with "Approved" after the most recent "Spec for review" comment, and no pull request | Build skill: tests first, code, pull request |
| 5. Fix | Pull request open and a finished check failed, the review verdict is FAIL, or a reviewer asked for changes. If checks are still running, say so and stop (stage 6) | Fix skill |
| 6. Waiting for approval | Pull request open, all checks green, no change requests | Say it is waiting for the guide to approve and merge. Give the links. Stop |
| 7. Done | Pull request merged or Jira status Done | Say it is done and point to the dashboard. Stop |

Find the pull request with `./scripts/lab-gh pr list --head <user>/<KEY> --state all --json number,url,state,mergedAt`.
Read checks with `./scripts/lab-gh pr checks <number>` and review comments with `./scripts/lab-gh pr view <number> --comments`.
