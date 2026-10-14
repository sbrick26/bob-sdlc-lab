# Build order

1. git checkout -b <lab name>/<KEY> from main.
2. Write the tests named in the plan. Run python -m pytest. They must fail for the right reason.
3. Implement, smallest complete change, only the Work units files.
4. Run python -m pytest until green. Do not weaken a test to make it pass.
5. Add the CHANGELOG.md entry.
6. Self-review: spawn one general subagent with the plan and `git diff main`, ask for gaps against the acceptance criteria. Fix real gaps.
7. Commit with the key first; include plans/<KEY>.md and CHANGELOG.md in the commit. Push the branch. Open the PR with gh pr create using the PR template.
8. Comment the PR link on the Jira ticket. Move it to In Review. Stop.
