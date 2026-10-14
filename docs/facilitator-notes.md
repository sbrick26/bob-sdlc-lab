# Facilitator notes

You are the guide. You own KAN-161, you approve every PR, and you reset the lab between sessions.

## Day before

| # | Check | How |
|---|---|---|
| 1 | Jira users exist with display names Sam Lab, Priya Lab, Jordan Lab, Alex Lab, and each has a password | `python3 tools/jira/seed.py --users-only` (needs `JIRA_HOST JIRA_EMAIL JIRA_API_TOKEN JIRA_PROJECT_KEY LAB_EMAIL_BASE`). It creates one user per plus-address email. It does not set display names or passwords: accept each invite, set the display name and a password by hand. Add `--dry-run` to check first. |
| 2 | Tickets KAN-157 to KAN-161 exist, assigned, status To Do | `python3 tools/jira/seed.py --tickets-only`. It is idempotent. Move any ticket that is not To Do back by hand. |
| 3 | Repo secrets set | `BOBSHELL_API_KEY` (required), `DASHBOARD_URL`, `DASHBOARD_TOKEN`, `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`. See [tools/ci/README.md](../tools/ci/README.md). |
| 4 | Dashboard healthy | Open the dashboard URL. The Lab page loads. One test prompt from your laptop shows on Activity. |
| 5 | Main is protected | `tools/ci/protect-main.sh`, then `tools/ci/protect-main.sh --show`. Required: tests, protected-paths, bob-review, one approving review. |
| 6 | Cards printed | [cards.md](cards.md). Fill the Jira password, dashboard URL and token by hand. Never commit them. |
| 7 | Your own `lab.env` | `./start.sh` on your laptop. Run the lab once end to end. |
| 8 | Participants can push | Each participant needs write access to the repo and `gh` signed in, because the build opens the PR with `gh pr create`. |

## Opening (3 minutes)

Say this, in your own words:

1. "This is FieldOps. It is the work-order system of a fictional utility. It was built in 2010 and has no tests. One old system."
2. "There are four tickets in Jira, one for each of you: tests, a data migration, a plain-words interface for dispatch, and compliance masking."
3. "For the next hour you run a software team. Bob is the engineer. You are the requester and the lead."
4. "You do not decide what is allowed. The process decides. Plan, approve, test, review, merge. Every step leaves a trace on the dashboard."
5. "If something gets blocked, that is the lab working. Read the sentence and fix the cause."

## Per step: watch and say

| Time | Step | Watch for | Say |
|---|---|---|---|
| 0-8 | Setup | `start.sh` asks for name, token, URL. Mode list shows `1. Plan`, `2. Build`, `3. Review` at the end. Atlassian sign-in opens a browser. | "Use the login on your card, not your own account." Wrong account: "Bob Settings > MCP, Reset auth." |
| 8-12 | check my tickets | Each person sees only their own ticket. Bob asks `Start <KEY>?` and waits. | "Bob acts as you in Jira. Jira decides what you can see." |
| 12-25 | Plan | `plans/<KEY>.md` with nine headings. Ticket moves to In Review. | "Plan mode cannot run commands or write code. Narrow tools per stage is the control." Then: "Approve with `approve. I am <Name> Lab, the requester.`" |
| 25-40 | Build | Tests fail first, then pass. Branch is `<lab id>/<KEY>`. Watch for the detour prompt. | Detour: "Now try the detour prompt on your card's step." After the block: "Look at the Lab page. Your Blocks count went up." |
| 40-50 | PR | PR gate refusals in plain sentences. CI comment with a verdict block. | "The hook is a speed bump. CI and branch protection are the gate." Approve each green PR on GitHub. |
| 50-57 | Dashboard | Tiles: Tickets merged, Minutes saved, Blocks before merge, Cost per merged PR, then the review tiles. | "Cost per merged PR is the number your CFO wants. It counts outcomes, not tokens." |
| 57-60 | Close | Questions about reuse. | Point to the root README, "Reuse this in your own repo". |

## Two enterprise callouts

1. **During the build block (about minute 35).** "These hooks live in the repo. A user can turn them off, and if the dashboard is down they fail open. In an enterprise you push them as enforced hooks through managed settings." Pointer: [docs/enterprise/enforced-hooks.md](enterprise/enforced-hooks.md).
2. **During the Jira sign-in or the dashboard walk.** "Each of you signed in to Jira directly. At scale you put an MCP gateway in front, so one place holds the credential, the audit trail and the tool allowlist." Pointer: [docs/enterprise/mcp-gateway.md](enterprise/mcp-gateway.md).

## Stretch: KAN-161

If the room finishes early, run KAN-161 yourself: "Every PR must say which site it affects". Use `/new-check`. It touches protected paths, so the branch is `<name>/governance-site` and the PR goes to the platform owner.

## Reset between sessions

1. If `tools/acp/lab-check.sh` is present, run `tools/acp/lab-check.sh clean`. It closes each persona's PR, deletes the remote and local lane branches, and moves the Jira ticket back to To Do.
2. If not, do it by hand:
   1. Jira: move KAN-157 to KAN-161 back to To Do.
   2. GitHub: close every open lab PR without merging.
   3. Delete each lane branch: `git push origin --delete <lab id>/<KEY>`.
   4. If a PR was merged, revert it on main through a platform PR so the next room starts from the same code.
3. Remove `plans/KAN-*.md` from main if a merge added them.
4. Dashboard data: events stay in the store. The board counts every session. For a clean board, use a fresh dashboard deployment or clear its data store before the next room. Tell the room if old rows are visible.
5. Ask each participant to delete their local clone, or run `./start.sh` again on a fresh clone.

## Timing

| Block | Minutes | Cut if late |
|---|---|---|
| Opening | 3 (inside setup) | Shorten to points 1 and 4 |
| Setup | 0-8 | Pair a slow laptop with a working one |
| check my tickets | 8-12 | none |
| Plan and approve | 12-25 | Accept the first plan, skip edits |
| Build and detour | 25-40 | Skip the detour, show it on your screen |
| PR and review | 40-50 | Approve as soon as CI is green |
| Dashboard walk | 50-57 | Show it on the projector only |
| Take home | 57-60 | none |
