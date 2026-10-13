# CI gate

`.github/workflows/sdlc-gate.yml` runs on every PR to main and every push to main.

- **tests**: `python -m pytest -q` on Python 3.12. No tests collected (exit 5) counts as a pass for now.
- **protected-paths**: a PR that changes `.bob/`, `.github/`, `governance/`, `tools/` or `dashboard/` fails, unless the author is the repo owner or the PR has the `platform` label. Plain path check, no model. Add the label before you push, because a re-run uses the labels from the original event.
- **bob-review**: rules come from main, not the PR. The job replaces `.bob/` and `governance/` in the PR checkout with main's copy and runs the CI helpers from main. Then `bob run --mode sdlc-review` reviews the branch `<name>/<KEY>` against `plans/<KEY>.md` and `pr.diff`. The `lab.env` it writes makes the lab hooks report the session as `ci-reviewer`.
- **Fail closed**: no `VERDICT: PASS|FAIL` line after one retry, a missing `BOBSHELL_API_KEY` or a branch with no ticket key fails the job. `VERDICT: FAIL` fails the job. The verdict goes to one sticky PR comment and to the dashboard as `ci_result`.
- **Fallback mode**: if `bob run` does not resolve the plugin mode headless, set the repository variable `REVIEW_MODE=ask`. The job then puts the review skill and the verdict format (from main) in the prompt. The default is `sdlc-review`.
- **Secrets**: `BOBSHELL_API_KEY` (required for bob-review); `DASHBOARD_URL`, `DASHBOARD_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (optional, every step that uses them fails open). On push to main, **merged** reports the merge to the dashboard and moves the ticket to Done in Jira.

| File | Job |
|---|---|
| `parse_verdict.py` | reads `review.json`, prints the verdict JSON, writes the PR comment. Exit 0 PASS, 2 FAIL, 3 none |
| `protected_paths.py` | the protected-paths check |
| `jira_transition.py` | moves `<KEY>` to Done and adds a comment with the PR link |
| `protect-main.sh` | branch protection for main (`--show` prints it). Run once by a repo admin |
| `tests/` | `.venv/bin/python -m pytest -q tools/ci/tests` |
