# Bob SDLC Lab

**Governed AI Delivery with IBM Bob.** Take a Jira ticket on an old field-service system from backlog to merged pull request. One Bob plugin carries the whole process: plan, build, review. Guardrails keep every step safe, and a dashboard shows usage, violations and cost per merged PR.

## Start

```sh
git clone https://github.com/sbrick26/bob-sdlc-lab.git
cd bob-sdlc-lab && ./lab-setup/mac-setup.sh      # macOS and Linux
# Windows: cd bob-sdlc-lab; powershell -ExecutionPolicy Bypass -File .\lab-setup\windows-setup.ps1
```

Setup asks for your lab profile number and the two tokens on your card (dashboard token, GitHub lab token). It writes `lab.env` and `my-lab.txt` at the repo root and the app's virtual environment in `fieldops-repo/.venv`. Open the repo root (`bob-sdlc-lab/`) in Bob IDE. Pick the **SDLC Agent** mode and say: `check my tickets`. Bob asks `Start <KEY>?`; say `yes`, answer the design questions (or `Use the defaults.`), then `I approve`. When the requester comments `Approved` on the Jira ticket, start a new chat in **SDLC Agent** and say `check my tickets` again: Bob builds and opens a pull request into `demo-dev`. You never type a slash command or switch modes by hand.

The [participant guide](docs/participant-guide.md) walks through the hour. The [lab page](docs/lab.html) shows the same steps with copy buttons (download it and open it in a browser).

## The process, and the Bob feature behind each step

| SDLC step | What happens | Bob feature | In this repo | Bob docs |
|---|---|---|---|---|
| Pick up work | "check my tickets" finds your Jira ticket and works out its stage | Custom mode **SDLC Agent** + skill `tickets` + MCP server | `.bob/plugins/bob-sdlc/custom_modes.yaml`, `skills/tickets/`, `rules-sdlc/stages.md`, `mcp.json` | [Custom modes](https://bob.ibm.com/docs/ide/configuration/custom-modes), [Skills](https://bob.ibm.com/docs/ide/features/skills), [MCP](https://bob.ibm.com/docs/ide/configuration/mcp/mcp-in-bob) |
| Sign in to Jira as yourself | First Jira call opens the browser; Bob acts with your permissions | Remote MCP server with OAuth | `mcp.json` entry `atlassian` | [MCP OAuth](https://bob.ibm.com/docs/ide/configuration/mcp/mcp-oauth) |
| Plan and spec | Design questions, then `fieldops-repo/plans/<KEY>.md`; review in chat, then on the ticket | Mode **SDLC Plan** (can edit only `fieldops-repo/plans/`), skill `plan`, mode rules | `skills/plan/`, `rules-sdlc-plan/plan-format.md` | [Custom modes](https://bob.ibm.com/docs/ide/configuration/custom-modes), [Rules](https://bob.ibm.com/docs/ide/configuration/rules) |
| Approval | Requester comments "Approved" on the Jira ticket | MCP (Jira comments) | `rules-sdlc/stages.md` | |
| Build, tests first | Branch, tests in `fieldops-repo/tests/`, code, change note in `fieldops-repo/changes/<KEY>.md`, self-review, pull request | Mode **SDLC Build**, skill `build`, subagent self-review | `skills/build/`, `rules-sdlc-build/build-order.md` | [Subagents](https://bob.ibm.com/docs/ide/features/subagents) |
| Team standards | Secrets, personal data, approved libraries, git discipline, protected paths | Rules | `.bob/plugins/bob-sdlc/rules/` | [Rules](https://bob.ibm.com/docs/ide/configuration/rules) |
| Guardrails as it works | Every prompt and action is checked; violations are blocked before they run | Lifecycle hooks | `.bob/settings.json`, `.bob/hooks/` | [Lifecycle hooks](https://bob.ibm.com/docs/ide/configuration/lifecycle-hooks) |
| Ready-to-merge checklist | A push or PR is refused until the spec is approved, tests passed and the change note exists | PreToolUse hook | `.bob/hooks/pr_gate.py`, `.bob/governance/pr-checklist.yaml` | [Lifecycle hooks](https://bob.ibm.com/docs/ide/configuration/lifecycle-hooks) |
| Review in CI | Tests, protected paths, and Bob reviewing the diff against the spec | Bob Shell headless + mode **SDLC Review** | `.github/workflows/sdlc-gate.yml`, `.github/scripts/` | [Headless Bob Shell](https://bob.ibm.com/docs/shell/getting-started/start-bobshell-non-interactive) |
| Fix findings | "check my tickets" sees the failed review and fixes it | Skill `fix` in SDLC Build | `skills/fix/` | |
| Merge and close | A person approves; merge moves the Jira ticket to Done | GitHub branch protection + CI job | `sdlc-gate.yml` (job `merged`) | |
| Governance rules | Which rules block, their text, allowlists; changed by PR to main | Rules file read by the governance service | `.bob/governance/rules.yaml` | |
| Visibility and ROI | Usage, Bobcoins, violations, time to merge, cost per merged PR, audit log | Hooks report to the governance dashboard | `.bob/hooks/gov.py` | |
| Packaging | All of the above ships as one folder | Bob plugin | `.bob/plugins/bob-sdlc/` | [IDE changelog 2.2.0: plugins](https://bob.ibm.com/docs/ide/changelog) |
| Make it mandatory | An admin pushes the hooks to every managed machine | Group policy `EnforcedHooks` | | [Group policies](https://bob.ibm.com/docs/ide/security/group-policies) |

Hooks are a speed bump: if one fails, the action still runs. CI and branch protection are the real controls.

## Build your own

1. Copy `.bob/plugins/bob-sdlc`, `.bob/settings.json`, `.bob/hooks` and `.bob/governance/` into your repo. Change the `fieldops-repo/` paths in the checklist, the Plan mode `fileRegex` and the skills to where your app lives.
2. Edit the rules in `.bob/plugins/bob-sdlc/rules/` and `.bob/governance/rules.yaml` for your team.
3. Point `mcp.json` at your ticket system: the hosted Atlassian server (OAuth), the token-based `atlassian-token` server, or your own MCP server. The skills need four ticket actions: search, read, change status, comment.
4. Copy `.github/workflows/sdlc-gate.yml` and `.github/scripts/`, add the repository secrets, and protect your main branch with the three checks and one approving review.
5. Give each person a `lab.env` with the dashboard URL and token, or leave it out: without a dashboard the hooks stay silent.

## Repo map

| Folder | What is in it |
|---|---|
| `.bob/` | The bob-sdlc plugin (modes, skills, rules, MCP), hook settings, hooks, and `.bob/governance/` (the PR checklist and the governance rules) |
| `.github/` | The CI workflow, its scripts, PR template, CODEOWNERS |
| `fieldops-repo/` | The old system the tickets change: `fieldops/` (code), `data/`, `tests/`, `run.sh`, `requirements.txt`, and the ticket files `plans/` and `changes/` (one spec and one change note per ticket) |
| `docs/` | Participant guide, architecture |
| `lab-setup/` | Participant setup: `mac-setup.sh` (macOS and Linux), `windows-setup.ps1` |
| `lab.env`, `my-lab.txt` | Written by setup at the repo root, never committed: tokens (Bob never reads it) and your profile and links |
