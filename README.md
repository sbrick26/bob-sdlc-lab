# Bob SDLC Lab

In this lab, you take one Jira ticket from the backlog to a merged pull request with IBM Bob. One Bob plugin runs the process (plan, build, review), and guardrails and a dashboard show what Bob did.

## Start here

| You are | Open |
|---|---|
| A participant | [docs/lab.html](docs/lab.html): the steps with copy buttons. Download it and open it in a browser. |
| A participant who wants all the detail | [docs/participant-guide.md](docs/participant-guide.md): the full hour, step by step, with fixes. |
| A teammate who wants to know how it works | [docs/architecture.md](docs/architecture.md) and "For maintainers" below. |

## The flow

| Step | You do | Bob and the process do |
|---|---|---|
| 1. Pick up | In mode **SDLC Agent**, type `check my tickets`, then `yes`. | Bob finds your Jira ticket and moves it to In Progress. |
| 2. Plan | Answer the design questions (or type `Use the defaults.`), then type `I approve`. | Bob writes the spec `fieldops-repo/plans/<KEY>.md` and posts it on the ticket. |
| 3. Approve | Wait. The requester comments `Approved` on the Jira ticket. | Nothing runs until the approval is there. |
| 4. Build | Start a new chat in **SDLC Agent** and type `check my tickets`. | Bob writes tests first, then code, then opens a pull request into `demo-dev`. |
| 5. Review and merge | If a CI check fails, type `check my tickets` again. | CI tests and reviews the change. A person approves and merges. The ticket moves to Done. |

You never type a slash command. You never switch modes by hand. Bob switches modes for each stage.

## Set up

You need Bob IDE 2.2.2 or newer, git, python3 3.10 or newer, the `gh` CLI and your printed card.

```sh
git clone https://github.com/sbrick26/bob-sdlc-lab.git
cd bob-sdlc-lab && ./lab-setup/mac-setup.sh      # macOS and Linux
# Windows: cd bob-sdlc-lab; powershell -ExecutionPolicy Bypass -File .\lab-setup\windows-setup.ps1
```

1. Setup asks for your profile number and the two tokens on your card.
2. Setup writes two files at the repo root. They are never committed.
3. Open the `bob-sdlc-lab` folder in Bob IDE. Pick the **SDLC Agent** mode.

| File | What it holds |
|---|---|
| `lab.env` | Your tokens. Bob never reads it. A hook blocks it. |
| `my-lab.txt` | One line: `user=<your lab id>`. Bob uses it for your branch name and pull request label. |

## Repo map

| Folder | What is in it |
|---|---|
| `fieldops-repo/` | The old work-order app that the tickets change. Specs go in `plans/`, change notes in `changes/`, tests in `tests/`. |
| `docs/` | The lab page, the participant guide, the architecture. |
| `lab-setup/` | Setup scripts for macOS, Linux and Windows. |
| `.bob/` | The Bob plugin, the hooks and the governance files. Ticket branches must not change it. |
| `.github/` | CI, its scripts, the pull request template, CODEOWNERS. Ticket branches must not change it. |

## For maintainers

### The Bob feature behind each step

| Step | Bob feature | Files | Bob docs |
|---|---|---|---|
| Pick up work | Custom mode **SDLC Agent**, skill `tickets`, MCP server (a connector to Jira) | `.bob/plugins/bob-sdlc/custom_modes.yaml`, `skills/tickets/`, `rules-sdlc/stages.md`, `mcp.json` | [Custom modes](https://bob.ibm.com/docs/ide/configuration/custom-modes), [Skills](https://bob.ibm.com/docs/ide/features/skills), [MCP](https://bob.ibm.com/docs/ide/configuration/mcp/mcp-in-bob) |
| Sign in to Jira | Remote MCP server with OAuth. Bob acts with your own Jira permissions. | `mcp.json` entry `atlassian` | [MCP OAuth](https://bob.ibm.com/docs/ide/configuration/mcp/mcp-oauth) |
| Plan | Mode **SDLC Plan**. It can edit only `fieldops-repo/plans/`. Skill `plan`. | `skills/plan/`, `rules-sdlc-plan/plan-format.md` | [Rules](https://bob.ibm.com/docs/ide/configuration/rules) |
| Approve | Jira comment `Approved`, read through MCP | `rules-sdlc/stages.md` | |
| Build | Mode **SDLC Build**, skill `build`, a self-review subagent | `skills/build/`, `rules-sdlc-build/build-order.md` | [Subagents](https://bob.ibm.com/docs/ide/features/subagents) |
| Team standards | Rules: secrets, personal data, libraries, git, protected paths | `.bob/plugins/bob-sdlc/rules/` | [Rules](https://bob.ibm.com/docs/ide/configuration/rules) |
| Guardrails | Lifecycle hooks check every prompt and action and block violations | `.bob/settings.json`, `.bob/hooks/` | [Lifecycle hooks](https://bob.ibm.com/docs/ide/configuration/lifecycle-hooks) |
| PR gate | A hook refuses a push or pull request until the spec is approved, the tests passed and the change note exists | `.bob/hooks/pr_gate.py`, `.bob/governance/pr-checklist.yaml` | [Lifecycle hooks](https://bob.ibm.com/docs/ide/configuration/lifecycle-hooks) |
| Review in CI | Headless Bob Shell (Bob without the IDE) in mode **SDLC Review** | `.github/workflows/sdlc-gate.yml`, `.github/scripts/` | [Headless Bob Shell](https://bob.ibm.com/docs/shell/getting-started/start-bobshell-non-interactive) |
| Fix findings | Skill `fix` in **SDLC Build** | `skills/fix/` | |
| Merge and close | Branch protection, CI job `merged` moves the ticket to Done | `sdlc-gate.yml` | |
| Governance rules | Which actions are blocked, with their text and allowlists. Changed by a pull request to main. | `.bob/governance/rules.yaml` | |
| Dashboard | Hooks report usage, Bobcoins (Bob usage credits), violations and time to merge | `.bob/hooks/gov.py` | |
| Packaging | All of the above is one Bob plugin folder | `.bob/plugins/bob-sdlc/` | [IDE changelog 2.2.0: plugins](https://bob.ibm.com/docs/ide/changelog) |
| Make it mandatory | An admin pushes the hooks to every managed machine with the `EnforcedHooks` group policy | | [Group policies](https://bob.ibm.com/docs/ide/security/group-policies) |

Hooks fail open: if a hook fails, the action still runs. CI and branch protection are the real controls.

### Build your own

1. Copy `.bob/plugins/bob-sdlc`, `.bob/settings.json`, `.bob/hooks` and `.bob/governance/` into your repo. Change the `fieldops-repo/` paths in the checklist, the Plan mode `fileRegex` and the skills to the folder of your app.
2. Edit the rules in `.bob/plugins/bob-sdlc/rules/` and `.bob/governance/rules.yaml` for your team.
3. Point `mcp.json` at your ticket system: the hosted Atlassian server (OAuth), the token server `atlassian-token`, or your own MCP server. The skills need four ticket actions: search, read, change status, comment.
4. Copy `.github/workflows/sdlc-gate.yml` and `.github/scripts/`. Add the repository secrets. Protect your main branch with the three checks and one approving review.
5. Give each person a `lab.env` with the dashboard URL and token. Without a dashboard, the hooks stay silent.

### Checks

- `python3 .github/scripts/check_plugin_files.py` checks that every skill, mode, settings and governance file parses. CI runs it in the `tests` job.
- [.github/scripts/README.md](.github/scripts/README.md) describes the CI jobs.
