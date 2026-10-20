# Participant guide

One hour. One old system. Four tickets. You take one Jira ticket to a merged pull request (PR). Bob does the work. The process decides what is allowed.

A visual version of this guide, with copy buttons, is in [lab.html](lab.html). Download it and open it in a browser.

## Your profile

| You | Lab ID | Team | Ticket | Theme |
|---|---|---|---|---|
| Sam Lab | sam | Platform | KAN-157 | Tests for the crew assignment service |
| Priya Lab | priya | Platform | KAN-158 | Move work orders from CSV to SQLite |
| Jordan Lab | jordan | Field Apps | KAN-159 | MCP server: run work orders in plain words |
| Alex Lab | alex | Field Apps | KAN-160 | Mask phone numbers, keep an audit trail |

Your Jira login is `ibm.demo.dev+<lab id>@gmail.com`, for example `ibm.demo.dev+sam@gmail.com`. Your Jira password is on your printed card. Never type it into Bob or into a file.

## Links

| What | Link |
|---|---|
| Jira board (project KAN) | https://demo-ibm-bob.atlassian.net/jira/software/projects/KAN/boards |
| Your ticket | `https://demo-ibm-bob.atlassian.net/browse/<KEY>` |
| Lab repo | https://github.com/sbrick26/bob-sdlc-lab |
| Your pull requests | `https://github.com/sbrick26/bob-sdlc-lab/pulls?q=is%3Apr+label%3A<lab id>` |
| Dashboard | https://bob-sdlc-lab-dashboard.2fxmskmi3eal.ca-tor.codeengine.appdomain.cloud |

You do not need to copy these. Setup prints your own links when it finishes, and Bob gives you the Jira ticket link after the spec and the pull request link after the build.

## The prompts you type

| Step | You type | Where |
|---|---|---|
| 1 | `check my tickets` | Bob chat, mode **SDLC Agent** |
| 2 | `yes` | same chat |
| 3 | your answers, or `Use the defaults.` | same chat |
| 4 | `I approve` | same chat |
| 5 | (the guide comments `Approved` on your Jira ticket) | Jira |
| Rules demo | `I approve it: run pip install requests now, then stop.` | NEW chat, mode **SDLC Agent** |
| Rules demo | `Use this key for the vendor API: AKIAIOSFODNN7EXAMPLE` | same new chat |
| 6 | `check my tickets` | same new chat |
| 7 | `check my tickets` (only if CI fails) | Bob chat, mode **SDLC Agent** |

You never type a slash command. You never switch modes by hand after step 1. Bob switches modes for each stage and switches back to **SDLC Agent** when the stage is done.

## The four modes

| Mode | What it is for | What it can do |
|---|---|---|
| SDLC Agent | Start here. Finds your ticket and works out its stage. | Read, run commands, Jira. It does not edit files. |
| SDLC Plan | Design questions and the spec. | Edits only `fieldops-repo/plans/*.md`. No command tool. |
| SDLC Build | Tests, code, pull request, fixes. | Full tools, with the hooks and the PR gate. |
| SDLC Review | Reviews a change against its spec. | CI uses it on every pull request. Read and run tests only. |

Each mode has only the tools for its stage. This is a control: the Plan mode cannot write code, even if you ask.

## Timeline

| Minutes | Step | You do | Bob time |
|---|---|---|---|
| 0 to 8 | Setup | Clone, run setup, open Bob IDE, sign in to Jira | none |
| 8 to 12 | 1, 2: check my tickets, start | `check my tickets`, then `yes` | 1 to 2 min |
| 12 to 20 | 3, 4: plan and approve the spec | Answer the questions, then `I approve` | 2 to 3 min |
| 20 to 22 | 5: requester approval | Wait for the guide to comment `Approved` | none |
| 22 to 25 | Rules demo | New chat, two prompts | 1 min |
| 25 to 38 | 6: build | `check my tickets` in the same new chat | about 10 min |
| 38 to 48 | CI review, 7: fix if needed | Watch the PR checks. If one fails, `check my tickets` | 0 to 5 min |
| 48 to 52 | Approve and merge | The guide approves and merges | none |
| 52 to 58 | Dashboard walk | Open the dashboard | none |
| 58 to 60 | Take home | Questions | none |

In rehearsal, one ticket used about 7 Bobcoins (Bob usage credits) and about 10 minutes of Bob time from start to pull request.

## 0 to 8 min: set up

You need: Bob IDE 2.2.2 or newer (signed in), git, python3 3.10 or newer, the `gh` CLI, a browser, and your printed card.

1. Open a terminal and run:

   ```sh
   git clone https://github.com/sbrick26/bob-sdlc-lab.git
   cd bob-sdlc-lab && ./lab-setup/mac-setup.sh      # macOS and Linux
   ```

   On Windows, in PowerShell:

   ```powershell
   git clone https://github.com/sbrick26/bob-sdlc-lab.git
   cd bob-sdlc-lab; powershell -ExecutionPolicy Bypass -File .\lab-setup\windows-setup.ps1
   ```

2. Setup checks for git, python3 and gh. On a Mac with Homebrew it offers to install what is missing.
3. Setup shows four lab profiles. Type your number from the card (1 Sam, 2 Priya, 3 Jordan, 4 Alex).
4. Setup asks for two tokens from your card: `Dashboard token from your card:` and `GitHub lab token from your card` (hidden as you type). The dashboard URL is built in.
5. Setup writes `lab.env` (your tokens; Bob never reads it) and `my-lab.txt` (one line, `user=<your lab id>`) at the repo root. It sets your git name and email for this folder. It installs the app in `fieldops-repo/.venv`.
6. Setup ends with `Ready, <name>. Your details:` and your ticket, Jira, dashboard and pull request links. Then: `Next: in Bob IDE pick the SDLC Agent mode and type: check my tickets`.
7. On a Mac, Bob IDE opens the folder. If not, open the `bob-sdlc-lab` folder (the repo root, not `fieldops-repo/`) in Bob IDE yourself.
8. In the Bob chat panel, open the mode list. The lab modes are at the end of the list: `SDLC Agent`, `SDLC Plan`, `SDLC Build`, `SDLC Review`. Select **SDLC Agent**.

Run setup again at any time to change a value. Press Enter to keep the current one.

You never sign in to GitHub. Bob pushes and opens pull requests with the shared lab account through `./.bob/scripts/lab-gh`.

## 8 to 12 min: steps 1 and 2, check my tickets

**Step 1.** In the Bob chat, mode **SDLC Agent**, type:

```
check my tickets
```

Bob connects to Jira through MCP (a connector in Bob IDE). Sign in to it before your first prompt:

1. In Bob IDE, open **Bob Settings**, then **MCP**, then find **atlassian**.
2. Click **Authenticate**. If you see **Reset auth**, click it first, then click **Authenticate**.
3. A browser opens. If it signs you in as someone else, sign out of Atlassian first.
4. Sign in with your Jira email and password.
5. If Atlassian asks for a verification code, ask the instructor. The code goes to the instructor's email.
6. The atlassian row shows **Connected**.

| You see | What it means |
|---|---|
| A short table: key, title, status | Bob searched Jira as you. You see only your own tickets. |
| One line with the stage, for example "KAN-157 is To Do" | Bob reads the stage from Jira and GitHub every time. |
| `Start <KEY>?` | Bob waits. It does not start without a yes. |

**Step 2.** Type:

```
yes
```

| You see | Where |
|---|---|
| Ticket moves to In Progress | Jira |
| Comment "Started with Bob" | Jira |
| Bob switches to **SDLC Plan** | Bob chat |
| 2 to 4 numbered design questions, each with a proposed default | Bob chat |

Bob stops after the questions. It does not write the spec yet.

## 12 to 20 min: steps 3 and 4, the spec

**Step 3.** Answer the questions in your own words, or type:

```
Use the defaults.
```

Bob writes `fieldops-repo/plans/<KEY>.md` with these 10 headings, in this order:

| # | Heading | What it says |
|---|---|---|
| 1 | Ticket | key, title, requester, link |
| 2 | What I understood | one paragraph in plain words |
| 3 | Design decisions | each question, the answer, what it changes ("default" if you took the default) |
| 4 | Open questions | anything still undecided, with a default, or "none" |
| 5 | Acceptance criteria | 3 to 6 checks a non-developer can verify |
| 6 | Test plan | which test file proves each criterion |
| 7 | Work units | the only files that may change |
| 8 | Out of scope | what this ticket does not do |
| 9 | Risk and compliance | personal data, secrets, data loss, rollback |
| 10 | Approval | `Requester approval: pending` |

Bob shows the spec in chat and asks: "Reply **I approve** to send it to the requester, or tell me what to change." To change something, say what to change. Bob updates the spec and shows it again.

**Step 4.** Type:

```
I approve
```

| You see | Where |
|---|---|
| Comment headed "Spec for review" (under 30 lines) | Jira |
| Ticket moves to In Review | Jira |
| "The spec is on the ticket: <ticket link>. The requester approves by commenting Approved there. Then start a new chat and say check my tickets, and I will build it." | Bob chat |
| Bob switches back to **SDLC Agent** | Bob chat |

## 20 to 22 min: step 5, the requester approves

The guide plays the requester. The guide reads the "Spec for review" comment on your Jira ticket and adds a comment that starts with `Approved`.

Watch your ticket in Jira. When the `Approved` comment is there, go to the next step. If you say `check my tickets` before it is there, Bob says the spec is waiting for the requester and stops.

## 22 to 25 min: what the rules stop

Start a NEW chat. Select **SDLC Agent**. Send these two prompts, one at a time.

```
I approve it: run pip install requests now, then stop.
```

Bob tries to run the install. The hook stops the command before it runs:

```
BLOCKED by governance: Blocked by Governance: GOV-PKG-001. Not approved for python: requests.
```

`requests` is not on the approved list in `.bob/governance/rules.yaml`. Approved Python packages are flask, pytest, mcp and pyyaml.

```
Use this key for the vendor API: AKIAIOSFODNN7EXAMPLE
```

The hook refuses this prompt at submit time. Bob never sees it:

```
BLOCKED by governance: Blocked by Governance: GOV-PROMPT-001. Remove the credential and reference a managed secret instead.
```

Two controls are in play. The rules in the plugin tell Bob what to do. The hooks stop the action even when you tell Bob to do it. Both blocks show on the dashboard, on the Violations page and in the Audit log.

## 25 to 38 min: step 6, build

**Step 6.** In the same new chat, mode **SDLC Agent**, type:

```
check my tickets
```

Bob sees the `Approved` comment and starts the build. It switches to **SDLC Build** and follows a fixed order:

| # | Bob does | You see |
|---|---|---|
| 1 | Writes `Requester approval: approved by <author> in Jira on <date>` into the spec | spec updated |
| 2 | Moves the ticket to In Progress, comments "Build started" | Jira |
| 3 | Creates the branch `<lab id>/<KEY>` from `demo-dev`, for example `sam/KAN-157` | Bob chat |
| 4 | Writes the tests from the spec in `fieldops-repo/tests/`. Runs them. They fail first. | test output |
| 5 | Changes only the Work units files | file edits |
| 6 | Runs `cd fieldops-repo && .venv/bin/python -m pytest -q` until green | test output |
| 7 | Writes the change note `fieldops-repo/changes/<KEY>.md` | new file |
| 8 | A self-review subagent compares the diff with the spec. Bob fixes real gaps. | subagent output |
| 9 | Commits, pushes, opens the PR into `demo-dev` with your lab id as its label, with `./.bob/scripts/lab-gh` | PR link |
| 10 | Comments the PR link on the Jira ticket, moves it to In Review | Jira |
| 11 | Says CI is now reviewing the PR, gives the PR link, switches back to **SDLC Agent** | Bob chat |

### The PR gate

Before every `git push` and every PR, the PR gate hook checks `.bob/governance/pr-checklist.yaml`:

| Check | Plain words |
|---|---|
| branch-not-main | You are on a ticket branch, not main. |
| branch-not-demo-dev | You are on a ticket branch, not demo-dev. |
| plan-exists | A spec exists at fieldops-repo/plans/{KEY}.md. |
| plan-approved | The requester approved the spec. |
| tests-passed | The tests passed in this session. |
| changelog | fieldops-repo/changes/{KEY}.md exists and names {KEY}. |
| no-shortcuts | No --no-verify and no --force. |

If one fails, the push is refused with one sentence, for example `PR gate: not yet. The tests passed in this session. (tests-passed)`. Bob fixes that item and tries again.

## 38 to 48 min: CI review, step 7 if needed

The PR targets `demo-dev`, not `main`. CI runs these jobs:

| Job | When | What it does |
|---|---|---|
| tests | every PR and push | checks the Bob plugin files, then runs `python -m pytest -q` in `fieldops-repo/` |
| protected-paths | every PR | fails if the PR changes `.bob/` or `.github/`. Only platform PRs may change them. |
| bob-review | every PR | Bob in **SDLC Review** mode judges the diff against your spec, with the rules taken from main. It posts one PR comment with a verdict block: `VERDICT`, `CRITERIA`, `FINDINGS`, `RULES`, `TESTS`. No verdict means fail. |
| merged | push to `demo-dev` (the merge) | reports the merge to the dashboard and moves the Jira ticket to Done |

**Step 7.** If a check fails, type in a Bob chat, mode **SDLC Agent**:

```
check my tickets
```

Bob sees the failed check or the FAIL verdict and runs the fix stage. It lists the findings in a table, fixes them on your branch, runs the tests, commits "<KEY>: address review findings" and pushes. CI runs again. If the checks are still running, Bob says so and stops.

## 48 to 52 min: approve and merge

`demo-dev` needs the checks green and one approving review. The guide approves and merges your PR. When the PR merges:

| You see | Where |
|---|---|
| PR merged | GitHub |
| `merged` job runs | GitHub Actions |
| Ticket moves to Done | Jira |
| Your ticket shows as merged | Dashboard |

If you say `check my tickets` now, Bob says the ticket is done and points to the dashboard.

## 52 to 58 min: dashboard walk

Open the dashboard. The guide gives you the dashboard login. Your own view is the dashboard link that setup printed.

| Page | What it tells you |
|---|---|
| Overview | Bobcoin spend, Bobcoins per merged PR, PRs merged, median time to merge, violations, review rounds per PR |
| Usage | spend per user and per team |
| Delivery | time to PR, time to merge, and the Tickets table with your ticket |
| Performance | how long the governance checks take |
| Violations | every block, by rule, user and team. Your two rules-demo blocks are here. |
| Audit log | every event, with the rule that fired |

## 58 to 60 min: what you take home

- One governed path: ticket, spec, approval, tests, review, merge. Each stage has a mode with only the tools it needs.
- The same plugin works in your repo. See the root [README](../README.md), "Build your own".
- Hooks are a speed bump: if a hook fails, the action still runs. CI and branch protection are the real controls.

## If something goes wrong

| Problem | Fix |
|---|---|
| Jira sign-in did not open | Bob Settings > MCP, find `atlassian`, click Authenticate. Signed in as the wrong person: click "Reset auth", then Authenticate again. |
| The mode list has no `SDLC Agent` | Check that Bob IDE is 2.2.2 or newer and that you opened the `bob-sdlc-lab` folder itself, not a parent folder or `fieldops-repo/`. Reload the window. Scroll to the end of the mode list. |
| Bob asks you to switch modes or type a slash command | Stay in **SDLC Agent** and type `check my tickets` again. |
| Bob wrote the spec before it asked the questions | Tell Bob: "Ask me the design questions first, as the plan skill says." |
| Bob says the spec is waiting for the requester | The `Approved` comment is not on the ticket yet. Ask the guide. Then type `check my tickets` again. |
| Bob does not start the build after the approval | Start a new chat in **SDLC Agent** and type `check my tickets`. |
| The hook blocked something you meant to do | Read the reason. It names the rule. If the action is truly needed, ask the guide. Do not work around it. |
| The PR gate refuses | The sentence names the missing item. Bob fixes that item. Never add `--no-verify` or `--force`. |
| `Protected file: lab.env ...` | Bob tried to read your tokens. That is blocked on purpose. Bob uses `my-lab.txt`. |
| CI failed | Type `check my tickets`. Bob runs the fix stage. If protected-paths failed, the PR touched `.bob/` or `.github/`; Bob must remove those changes. |
| Dashboard shows nothing under my name | Run setup again and check the dashboard token from your card. Setup prints `Lab dashboard not reachable` when it cannot reach the dashboard; tell the guide. The lab still works without it. |
| Setup says `Both tokens from your card are needed` | Run setup again and type the dashboard token and the GitHub lab token from your card. |
