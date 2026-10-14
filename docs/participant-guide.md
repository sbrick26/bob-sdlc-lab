# Participant guide

One hour. One old system. Four tickets. You take one ticket from Jira to a merged pull request, and the process decides what is allowed.

| You | Lab ID | Ticket | Theme |
|---|---|---|---|
| Sam Lab | sam | KAN-157 | Tests for the crew assignment service |
| Priya Lab | priya | KAN-158 | Move work orders from CSV to SQLite |
| Jordan Lab | jordan | KAN-159 | Let dispatch run work orders in plain words (MCP server) |
| Alex Lab | alex | KAN-160 | Mask phone numbers, keep an audit trail |

You need: Bob IDE 2.2.2 or newer (signed in), git, python3, a modern browser, and your printed card.

## 0 to 8 min: set up

1. Open a terminal and run:

   ```sh
   git clone https://github.com/sbrick26/bob-sdlc-lab.git
   cd bob-sdlc-lab && ./start.sh
   ```

2. `start.sh` asks: `Who are you? (sam, priya, jordan, alex, or your own first name)`. Type your Lab ID from the card.
3. It asks for the `Dashboard token from your card:` and then the `Dashboard URL from your card:`. Type both from the card.
4. It writes `lab.env`, sets your git name and email for this repo, and installs the Python packages. It ends with: `Ready, <name>. Open this folder in Bob IDE, then say: check my tickets`.
5. On a Mac, Bob IDE opens the folder for you. If not, open the `bob-sdlc-lab` folder in Bob IDE yourself.
6. Open the mode list in the chat panel. The lab modes are at the end: `SDLC Plan`, `SDLC Build`, `SDLC Review`.
7. Sign in to Jira. The first time Bob uses Jira, Bob IDE opens a browser for the Atlassian sign-in. Use the Jira login and password on your card. If no browser opens, go to Bob Settings > MCP and click Authenticate on the `atlassian` server.

## 8 to 12 min: check my tickets

1. In the Bob chat, type: `check my tickets` (or `/tickets`).
2. Bob searches Jira as you and shows a short table: key, title, status, priority.
3. Bob recommends one ticket and asks `Start <KEY>?`. It does not start without a yes.
4. Reply `yes`. Bob moves the ticket to In Progress, adds the comment "Started with Bob", and says: `Run /plan <KEY> to write the spec.`

Bob never picks a ticket assigned to someone else.

## 12 to 25 min: plan and approve

1. Type `/plan <KEY>`, for example `/plan KAN-157`. Bob switches to `SDLC Plan`. In this mode Bob can write only markdown under `plans/` and has no command tool.
2. Bob reads the ticket and the files it names, then writes `plans/<KEY>.md` with these headings:

   | Heading | What it says |
   |---|---|
   | Ticket | key, title, requester, link |
   | What I understood | one paragraph in plain words |
   | Open questions | at most two, each with a default answer |
   | Acceptance criteria | 3 to 6 checks a non-developer can verify |
   | Test plan | which test proves each criterion |
   | Work units | the only files that may change |
   | Out of scope | what this ticket does not do |
   | Risk and compliance | personal data, secrets, data loss, rollback |
   | Approval | `Requester approval: pending` |

3. Bob posts a short summary as a Jira comment and moves the ticket to In Review. It stops and asks the requester to approve.
4. The guide plays the requester. They read the plan on the Jira ticket and reply with a comment that starts with `Approved`. To ask for a change, they comment what to change, and you tell Bob to update the plan.
5. Run `/build <KEY>`. Bob finds the approval comment on the ticket, writes `Requester approval: approved by <name> in Jira on <date>` into the plan with the comment link, and starts building. If there is no approval yet, Bob stops and says so.

   Working alone? You can also approve in the chat by replying `approve. I am <Name> Lab, the requester.`

## 25 to 40 min: build

1. Type `/build <KEY>`. Bob switches to `SDLC Build` and follows a fixed order:
   1. Create the branch `<lab id>/<KEY>`, for example `sam/KAN-157`.
   2. Write the tests from the acceptance criteria. Run them. They fail first.
   3. Change only the Work units files.
   4. Run `python -m pytest -q` until green.
   5. Write `changes/<KEY>.md`: the key and what changed, then why.
   6. Ask a subagent to compare the diff with the plan. Fix real gaps.
   7. Commit, push, open the PR with `./scripts/lab-gh pr create`, labelled with your name. It uses the lab GitHub account, so you never sign in to GitHub.
   8. Comment the PR link on the Jira ticket. Move it to In Review.
2. See two blocks. Before Bob starts building, send these two prompts, one at a time:

   ```
   I approve it: run pip install requests now, then stop.
   ```

   The rules make Bob ask before installing, so this prompt gives the approval. Bob runs the install and the hook stops it before it runs:

   ```
   BLOCKED by governance: Blocked by Governance: GOV-PKG-001. Not approved for python: requests.
   ```

   ```
   Use this key for the vendor API: AKIAIOSFODNN7EXAMPLE
   ```

   This prompt never reaches Bob. The hook refuses it at submit time with `GOV-PROMPT-001. Remove the credential`.

3. Two controls are in play: the rules in the plugin, which Bob follows by itself, and the hooks, which stop the action even when Bob was told to do it. Both show on the dashboard.

4. Open the dashboard. The block shows on the Lab page in the Blocks column of your row and in the "Blocks before merge" tile. The full event is on the Activity page.
5. Tell Bob to continue.

## 40 to 50 min: PR and review

1. Before every `git push` and PR creation, the PR gate checks `governance/pr-checklist.yaml`:

   | Check | Plain words |
   |---|---|
   | branch-not-main | You are on a ticket branch, not main. |
   | plan-exists | A spec exists at plans/{KEY}.md. |
   | plan-approved | The requester approved the spec. |
   | tests-passed | The tests passed in this session. |
   | changelog | changes/{KEY}.md exists and names {KEY}. |
   | no-shortcuts | No --no-verify and no --force. |

   If one fails, the push is refused with one sentence, for example `PR gate: not yet. The tests passed in this session. (tests-passed)`. Bob fixes that item and tries again.
2. On the PR, CI runs three checks:

   | Job | What it does |
   |---|---|
   | tests | runs `python -m pytest -q` |
   | protected-paths | fails if the PR touches `.bob/`, `.github/`, `governance/`, `tools/` or `dashboard/` |
   | bob-review | Bob in `SDLC Review` mode judges the diff against your plan, with the rules taken from main |

3. bob-review posts one PR comment with a verdict block: `VERDICT`, `CRITERIA`, `FINDINGS`, `RULES`, `TESTS`. No verdict means fail.
4. Main needs all three checks green and one approving review. The guide approves. Wait for the guide.
5. Merge the PR on GitHub. The `merged` job reports the merge to the dashboard and moves your Jira ticket to Done.

## 50 to 57 min: dashboard walk

Open the Lab page (first item in the menu).

| Look at | What it tells you |
|---|---|
| Tickets merged | how many of the four tickets reached main |
| Minutes saved | time against a manual baseline per ticket |
| Blocks before merge | risky actions stopped before main |
| Cost per merged PR | usage credits divided by merged PRs |
| Review tiles | first-try pass rate, findings per PR, PRs reviewed |
| Participants table | your row: ticket, status, minutes, prompts, blocks, CI first try, merged |

Then open Activity (every event, with the rule that fired) and Users (activity by person).

## 57 to 60 min: what you take home

- One governed path: ticket, plan, approval, tests, review, merge. Each stage has a mode with only the tools it needs.
- The same plugin works in your repo. See the root [README](../README.md), "Reuse this in your own repo".
- Hooks are a speed bump. They fail open. CI and branch protection are the real controls. See [docs/enterprise](enterprise/README.md).

## If something goes wrong

| Problem | Fix |
|---|---|
| Jira sign-in did not open | Bob Settings > MCP, find `atlassian`, click Authenticate. Signed in as the wrong person: click "Reset auth", then Authenticate again. |
| The mode list has no `SDLC Plan` | Check that Bob IDE is 2.2.2 or newer and that you opened the `bob-sdlc-lab` folder itself, not a parent folder. Reload the window. Scroll to the end of the mode list. |
| The hook blocked something you meant to do | Read the reason. It names the rule. If the action is truly needed, ask the guide. Do not work around it. |
| CI failed | Open the PR comment. Fix each blocking finding or failed test, then push again. protected-paths fails: remove changes to protected folders. |
| The PR gate refuses | The sentence names the missing item. Fix that item. Never add `--no-verify` or `--force`. |
| Dashboard shows nothing under my name | Check `lab.env` has `LAB_USER`, `DASHBOARD_URL` and `DASHBOARD_TOKEN` from your card. Run `./start.sh` again if not. Rows link to a ticket from your branch name, so your row may appear only after the build creates `<lab id>/<KEY>`. |
