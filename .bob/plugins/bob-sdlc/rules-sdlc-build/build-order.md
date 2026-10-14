# Build order

1. git fetch origin, then git checkout -b <lab name>/<KEY> origin/demo-dev. Lab work branches from demo-dev, never from main.
2. Write the tests named in the plan. Run python -m pytest. They must fail for the right reason.
3. Implement, smallest complete change, only the Work units files.
4. Run python -m pytest until green. Do not weaken a test to make it pass.
5. Write changes/<KEY>.md (key and what on line 1, why on line 2).
6. Self-review: spawn one general subagent with the plan and `git diff origin/demo-dev...HEAD`, ask for gaps against the acceptance criteria. Fix real gaps.
7. Commit with the key first; include plans/<KEY>.md and changes/<KEY>.md in the commit. Push the branch. Open the PR with ./.bob/scripts/lab-gh pr create --base demo-dev --label <user from my-lab.txt> --title "<KEY>: <title>". The body starts with "Opened by <name from my-lab.txt> for <KEY>." then the PR template sections.
8. Comment the PR link on the Jira ticket. Move it to In Review. Stop.
