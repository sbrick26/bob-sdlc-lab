# CI gate

The workflow `.github/workflows/sdlc-gate.yml` runs on every pull request and every push to `main` and `demo-dev`. Ticket pull requests go into `demo-dev`.

| Job | When | What it does |
|---|---|---|
| tests | every pull request and push | Runs `check_plugin_files.py`, then `python -m pytest -q` in `fieldops-repo/` on Python 3.12. No tests found (exit 5) counts as a pass. |
| protected-paths | every pull request | Fails if the pull request changes `.bob/` or `.github/`. The repo owner, or a pull request with the `platform` label, may change them. No model is used. |
| bob-review | every pull request | Bob in the **SDLC Review** mode reviews the branch `<user>/<KEY>` against `fieldops-repo/plans/<KEY>.md`. It posts one pull request comment with the verdict. |
| merged | push to `demo-dev` (a merge) | Reports the merge to the dashboard and moves the Jira ticket to Done. |

## Files

| File | What it does |
|---|---|
| `check_plugin_files.py` | Parses every SKILL.md frontmatter, `custom_modes.yaml`, `.bob/settings.json`, `mcp.json` and `.bob/governance/*.yaml`. Names the broken file and exits 1. |
| `protected_paths.py` | The protected-paths check |
| `parse_verdict.py` | Reads `review.json`, prints the verdict, writes the pull request comment. Exit 0 PASS, 2 FAIL, 3 no verdict. |
| `jira_transition.py` | Moves `<KEY>` to Done and comments the pull request link |

## For maintainers

- **Rules come from main.** The bob-review job replaces `.bob/` in the pull request checkout with the copy from main. It also runs the CI scripts from main. A pull request cannot change the rules it is judged by.
- **Fail closed.** The job fails if there is no `VERDICT: PASS|FAIL` line after one retry, if `BOBSHELL_API_KEY` is missing, or if the branch has no ticket key. `VERDICT: FAIL` also fails the job. The verdict goes to the dashboard as `ci_result`.
- **The platform label.** Add the `platform` label before you push. A re-run uses the labels from the first event.
- **Reviewer identity.** The job writes a `lab.env` so the hooks report the session as `ci-reviewer`.
- **Fallback mode.** If `bob run` cannot load the plugin mode headless, set the repository variable `REVIEW_MODE=ask`. The job then puts the review skill and the verdict format from main into the prompt. The default is `sdlc-review`.
- **Secrets.** `BOBSHELL_API_KEY` is required for bob-review. `DASHBOARD_URL`, `DASHBOARD_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL` and `JIRA_API_TOKEN` are optional. Each step that uses them continues without them.
