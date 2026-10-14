# Lab dashboard

This folder is the Bob SDLC lab dashboard. It is the Bob Governance service
(below) with lab additions:

- **Lab headers** on every hook event: `X-Lab-Ticket` (for example `KAN-201`),
  `X-Lab-Role` (`participant`, `ci-reviewer`, `guide`), `X-Lab-Branch`, and on
  Stop events `X-Lab-Cost` (Bobcoins), `X-Lab-Tokens` (context tokens) and
  `X-Lab-Turns`, each cumulative for the Bob session. Session usage is the
  maximum value seen per session, then summed per person, ticket and day
  (`app/metrics.py`). Ticket and role are filters and facets in
  `/api/v1/events` and `/api/v1/facets`.
- **Lab events** from outside Bob (GitHub, CI): `POST /api/v1/lab/events`
  with `Authorization: Bearer <INGEST_TOKEN>` and
  `{"kind", "user", "ticket", "pr", "data"}`. Kinds: `pr_opened`, `ci_result`,
  `approved`, `merged`, `ticket_started`, `ticket_done`. Optional fields:
  `role`, `branch`, `cost`, `occurred_at`, `event_id` (UUID, makes the post idempotent).
- **Board**: `GET /api/v1/lab/board`, one row per ticket with status
  (planning, building, pr_open, merged), minutes, prompts, tool calls, blocks,
  CI result and cost.
- **ROI**: `GET /api/v1/lab/roi?baseline_minutes=240`, minutes against a manual
  baseline, blocks before merge, cost per merged PR, review pass rate. The
  math is in the `lab_roi` docstring in `app/lab.py`.
- **Lab rules**: `GOV-PKG-001` uses `LAB_PACKAGE_ALLOWLIST` (default
  `flask,pytest,mcp,pyyaml`), `GOV-PII-001` blocks unmasked phone numbers,
  `GOV-GIT-001` blocks unsafe git commands.
- **`LAB_MODE=1`**: policy publish activates the policy in the object store
  without MDM. Dashboard basic auth still applies.
- **Console pages**: Overview, Violations, Audit log, Usage & ROI, Rules
  (read only). Each page reads one summary endpoint:
  `/api/v1/overview/summary`, `/api/v1/violations/summary`,
  `/api/v1/usage/summary`, `/api/v1/rules/summary`. The audit log exports
  `/api/v1/events.csv` (same filters as `/api/v1/events` plus `since` and
  `until`; metadata columns only, detail redacted). The policy draft and
  publish API stays, but the console no longer links it.
- **USD**: USD = Bobcoins x `BOBCOIN_USD_RATE` (default `0.50`, the IBM
  enterprise pack price of $500 per 1,000 Bobcoins; `off` turns USD off). The
  Usage & ROI page can override the rate in the browser.
- **Install-rule parsing**: a command segment that `shlex` cannot parse is a `GOV-PKG-001` block only when it looks like an install (`pip`, `npm`, `pnpm`, `yarn`, `python -m pip`); other segments, such as `echo 'a|b'`, are ignored.
- **Reset**: `.venv/bin/python scripts/reset-lab.py` deletes every object under `COS_PREFIX` in the local store (`DATA_DIR/objects`) and prints each one; in COS mode it only prints the `ibmcloud cos` delete command.

## Run it locally

```bash
./run-local.sh                         # http://localhost:8080  user governance  password lab
.venv/bin/python scripts/seed-lab.py   # four people, eight tickets over four days
curl -u governance:lab localhost:8080/api/v1/lab/board
```

The demo credentials are fixed and public. Use real secrets for any shared
deployment. See [DEPLOY.md](DEPLOY.md) for Code Engine.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
npm --prefix frontend ci && npm --prefix frontend test && npm --prefix frontend run build
```

# Bob Governance (base service)

Bob Governance is a centrally managed policy and telemetry service for IBM Bob.
Administrators define controls in a React console, publish immutable policy
versions, and roll the managed configuration to Bob devices through MDM.

## Capabilities

- Enforced Bob hooks across `SessionStart`, `UserPromptSubmit`, `PreToolUse`,
  `PostToolUse`, and `Stop`
- Literal credential blocking before model or tool execution
- Managed-reference support for environment variables, vault references, and
  secret-manager references
- Python and Node.js package installation allowlists
- Redacted prompt, tool input/output, response, latency, user, device, profile,
  rule, and outcome telemetry
- React and Carbon console for Overview, Violations, Audit log, Usage & ROI,
  and Rules
- Versioned policy drafts with validation, optimistic revision checks,
  publishing, and rollout history
- Managed-profile update and assignment-group synchronization from the server
- Last-known-good offline enforcement with a bounded, permission-restricted
  device queue and automatic replay
- IBM Cloud Object Storage as the durable system of record
- A durable outbox envelope ready for IBM Event Streams, Kafka, or Confluent

## Policy controls

| Rule | Control point | Action |
| --- | --- | --- |
| `GOV-PROMPT-001` | `UserPromptSubmit` | Block known credential formats before model processing |
| `GOV-PROMPT-002` | `UserPromptSubmit` | Block a likely literal value disclosed as a secret |
| `GOV-TOOL-001` | `PreToolUse` | Block credentials before tool execution |
| `GOV-PKG-001` | `PreToolUse` | Block dependencies outside the approved ecosystem allowlist |
| `GOV-POST-001` | `PostToolUse` | Record a finding and add corrective next-turn context |
| `GOV-RESP-001` | `Stop` | Record credential-shaped response content |
| `GOV-HOOK-001` | prompt/tool pre-hook | Block an unscannable oversized payload |
| `GOV-PII-001` | `PreToolUse` (file writes) | Block an unmasked US phone number outside `data/` and `tests/` |
| `GOV-GIT-001` | `PreToolUse` (`execute_command`) | Block `--no-verify`, `--force`, `push -f`, `push origin main` |

Managed references remain allowed, including `${MY_API_KEY}`, `$MY_API_KEY`,
`process.env.MY_API_KEY`, `os.environ[...]`, `os.getenv(...)`, `vault://...`,
and `secret://...`.

## Runtime architecture

```text
Managed Bob hook
  ├─ online  → policy decision API → COS event/outbox → React console
  └─ offline → last verified policy + local retry queue ──┘

Policy console → validate → immutable version → active policy
                                        └→ managed profile update + group sync
```

The managed-profile offline checker covers the credential and package rules.
`GOV-PII-001` and `GOV-GIT-001` are enforced by the central API only.

COS stores immutable normalized event envelopes, optional redacted content
objects, policy versions, draft revisions, rollout transitions, and short
stream-outbox records. The application rebuilds its in-process query index from
COS at startup; container-local disk is not the system of record.

The stream outbox contains a short normalized event and `event_ref`/
`content_ref`. A future Event Streams, Kafka, or Confluent publisher can deliver
that envelope without putting multi-kilobyte prompt or tool content into an
Orchestrate agent context.

## Offline behavior

The MDM profile contains a versioned local policy snapshot. If the API cannot be
reached, credential and package controls continue locally under the last
verified policy. Hook payloads are written with mode `0600` beneath the user's
Bob Governance application-support directory, capped at 500 events, and
replayed with stable event IDs when connectivity returns. A short retry marker
prevents every hook from waiting on the same outage.

## Deploy

For the lab, use [DEPLOY.md](DEPLOY.md). The original MDM-mode deploy script
builds the React bundle, builds and pushes an amd64 image,
creates a dedicated bucket in the existing COS service when necessary, binds
that service to Code Engine with the Writer role, updates server secrets, and
verifies both application and durable-storage health.

```bash
./scripts/deploy-code-engine.sh
```

It requires the account, project, COS and registry names as environment
variables. Dashboard credentials, the ingest
credential, and the MDM API credential remain in Keychain and Code Engine
secrets; the script does not print them.

## Managed profile

The same compiler is used by policy publishing and the local administrative
script:

```bash
./scripts/generate-governance-profile.py
plutil -lint tmp/bob-governance.mobileconfig
./scripts/simplemdm.sh update-governance
```

The managed preference is non-overridable inside Bob while installed. A
manually enrolled administrator can still remove MDM enrollment; non-removable
management requires Automated Device Enrollment.

## Verification

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
bash -n scripts/*.sh
docker buildx build --platform linux/amd64 --load --tag bob-governance:local .
```

Managed-device release checks should cover:

1. Clean prompt is allowed and recorded.
2. Literal credential is blocked and stored only in redacted form.
3. Environment or vault reference is allowed.
4. Approved dependency installation is allowed.
5. Unapproved dependency installation is blocked.
6. A published rule version reaches the assigned device group.
7. Offline decisions queue locally and replay once without duplication.
