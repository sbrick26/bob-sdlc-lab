# Bob SDLC Lab

One hour, one old system, four tickets, the governed way. FieldOps is the work-order system of a fictional utility: built in 2010, no tests. Four people each take one Jira ticket and use Bob IDE to plan it, get the plan approved, build it tests first and open a pull request. CI reviews the change against the plan, a person approves it, and a dashboard shows each step, each block and the cost per merged PR.

## Start

```sh
git clone https://github.com/sbrick26/bob-sdlc-lab.git
cd bob-sdlc-lab && ./start.sh
```

Then open the folder in Bob IDE and say: `check my tickets`

## Docs

| Doc | For |
|---|---|
| [Participant guide](docs/participant-guide.md) | the 60-minute lab, step by step |
| [Architecture](docs/architecture.md) | diagram and stage-to-control map |

## Repo map

| Folder | What is in it |
|---|---|
| `.bob/` | the bob-sdlc plugin (modes, skills, rules, MCP), hook settings, hooks |
| `.github/` | the sdlc-gate CI workflow, PR template, CODEOWNERS |
| `data/` | FieldOps work orders and crews (CSV) |
| `docs/` | lab documents |
| `fieldops/` | the old system the tickets change |
| `governance/` | the PR checklist the PR gate enforces |
| `lanes/` | lab rehearsal lanes |
| `plans/` | specs written by the Plan mode |
| `tests/` | FieldOps tests |
| `tickets/` | the ticket texts seeded into Jira |
| `tools/` | CI helpers, Jira seeding, rehearsal tools |

## Reuse this in your own repo

1. Copy these into your repo:
   - `.bob/plugins/bob-sdlc`
   - `.bob/settings.json`
   - `.bob/hooks`
   - `governance/pr-checklist.yaml`
2. Create `lab.env` from `lab.env.example`: `LAB_USER`, `DASHBOARD_URL`, `DASHBOARD_TOKEN`. Keep it out of git. Without a dashboard the hooks stay silent and fail open.
3. Edit the rules in `.bob/plugins/bob-sdlc/rules/` for your team: who you are, approved libraries, protected paths.
4. Change ticketing by editing `.bob/plugins/bob-sdlc/mcp.json`. Pick one entry and disable the others:
   - `atlassian`: the hosted Atlassian MCP server with OAuth. Each user signs in once in the browser.
   - `atlassian-token`: a local server that uses `JIRA_URL`, `JIRA_USERNAME` and `JIRA_API_TOKEN` from the environment.
   - Your own MCP server for another ticket system. The skills name the Jira actions they need (search, read, change status, comment); map them in `skills/tickets/SKILL.md`.
5. Copy `.github/workflows/sdlc-gate.yml` and `tools/ci/` for the CI gate, set the secrets, then protect the main branch: required checks tests, protected-paths, bob-review and one approving review.

Hooks are a speed bump. CI and branch protection are the real controls.
