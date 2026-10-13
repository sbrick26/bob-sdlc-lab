# From project hooks to enforced hooks

## 1. What the lab did

The lab puts hooks in `.bob/settings.json`. Bob IDE runs them as `python3 .bob/hooks/<script>.py` with a 5-second timeout.

| Event | Script | What it does |
|---|---|---|
| SessionStart, UserPromptSubmit, Stop | `gov.py` | Sends the event to the lab dashboard with user, device, ticket, role and branch headers. |
| PreToolUse (all tools) | `gov.py` | Same. Exits 2 (block) only when the dashboard answers `blocked`. |
| PreToolUse (`execute_command`) | `pr_gate.py` | On `git push` or `gh pr create`, checks `governance/pr-checklist.yaml`. Exits 2 with the first failed item. |
| PostToolUse (all tools) | `gov.py` | Sends the result to the dashboard. |
| PostToolUse (`execute_command`) | `test_marker.py` | After `pytest`, writes a "tests passed" marker, or removes it on failure. |

## 2. The honest limits

| Limit | Effect |
|---|---|
| Fail-open | Any non-zero exit other than 2 is "logged and ignored". A crash or a missing `python3` does not block. The docs do not say a timeout blocks. `gov.py` exits 0 when the dashboard is down. |
| Trust | "Workspace hooks only run in trusted folders" (Shell docs; IDE 2.0.2 changelog: hooks "respect the workspace trust setting"). |
| Ownership | A repo can add hooks. A user can edit or delete the file. |

So CI and branch protection are the controls. Hooks are the early warning.

## 3. The enterprise path: `EnforcedHooks`

Source: [Enterprise policies](https://bob.ibm.com/docs/ide/security/group-policies).

- Value: "a JSON-encoded string that matches the hooks configuration schema". The page's example:
  `{"PostToolUse":[{"matcher":".*","hooks":[{"type":"command","command":"echo tool-use >> bob-tool-use.log"}]}]}`
- Policy hooks "run before any user-defined hooks and cannot be overridden by users".
- If the value is "absent, empty, or not valid JSON, it is silently ignored". Validate it before you ship it.
- "Enterprise policies are currently supported by Bob IDE only."

| Platform | Where Bob reads policy | How to deliver |
|---|---|---|
| macOS | Managed preferences domain `com.ibm.bob` | MDM configuration profile |
| Windows | Registry `Software\Policies\IBM\Bob` | ADMX/ADML via Group Policy or Intune |
| Linux | `/etc/bob/policy.json` | Root-owned, mode 644 |

Other keys on the page: `DisabledAutoApprovalGroups` (lock auto-approval off, for example `edit,execute`), `UpdateMode` (`default`, `start`, `manual`, `none`), `GatewayUrl` (fixed backend gateway URL).

Samples: [IBMBobPolicies_external_sample_files.zip](https://bob.ibm.com/media/assets/IBMBobPolicies_external_sample_files.zip) (`.mobileconfig`, ADMX/ADML, `policy.json`).

## 4. Worked example

The lab hooks as one `EnforcedHooks` value, with absolute paths:

```json
{"SessionStart":[{"hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/gov.py","timeout":5}]}],
 "UserPromptSubmit":[{"hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/gov.py","timeout":5}]}],
 "PreToolUse":[{"matcher":".*","hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/gov.py","timeout":5}]},
               {"matcher":"^execute_command$","hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/pr_gate.py","timeout":5}]}],
 "PostToolUse":[{"matcher":".*","hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/gov.py","timeout":5}]},
                {"matcher":"^execute_command$","hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/test_marker.py","timeout":5}]}],
 "Stop":[{"hooks":[{"type":"command","command":"python3 /opt/bob-governance/hooks/gov.py","timeout":5}]}]}
```

Notes:

- Deliver it as one string. In `policy.json` that means escaped quotes.
- The same MDM profile (or package) must install the scripts at `/opt/bob-governance/hooks/`. A policy that points to a missing file fails open.
- Today the scripts find `lab.env` and the checklist relative to their own folder. An installed copy must read them from a fixed path or from environment variables.

## 5. HTTPS hook handlers

- IDE 2.2.0 [changelog](https://bob.ibm.com/docs/ide/changelog): send "event payloads to any HTTPS target, alongside or instead of local shell commands".
- [Shell lifecycle hooks](https://bob.ibm.com/docs/shell/configuration/lifecycle-hooks): `"type": "https"`, `url` (required), `timeout` (default 10). The page does not document headers, retries or failure behavior.
- The [IDE lifecycle hooks](https://bob.ibm.com/docs/ide/configuration/lifecycle-hooks) page still says "Only `command` is supported". Test HTTPS handlers in the IDE before you rely on them.

## 6. What each layer can and cannot do

| Layer | Can | Cannot |
|---|---|---|
| Project hook | Warn and block early, per repo, in version control | Survive a user delete; run in untrusted folders |
| Global hook (`~/.bob/settings/settings.json`) | Run in every workspace, trust does not apply | Stop the user who owns the file |
| Enforced hook | Run first, for every user; users cannot override | Fail closed on a crash; cover non-IDE clients |
| CI gate | Check every push on a server the user does not control | Stop work before it reaches the remote |
| Branch protection | Refuse merges without passing checks and review | See what happened inside the session |
| MCP gateway | Hold credentials, filter and log every tool call | See local file edits or shell commands |
