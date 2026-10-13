# Bob Governance

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
- React and Carbon administration experience for Overview, Activity, Users,
  and Policies
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

COS stores immutable normalized event envelopes, optional redacted content
objects, policy versions, draft revisions, rollout transitions, and short
stream-outbox records. The application rebuilds its in-process query index from
COS at startup; container-local disk is not the system of record. See
[`docs/storage.md`](docs/storage.md) for the object contract.

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

The deploy script builds the React bundle, builds and pushes an amd64 image,
creates a dedicated bucket in the existing COS service when necessary, binds
that service to Code Engine with the Writer role, updates server secrets, and
verifies both application and durable-storage health.

```bash
./scripts/deploy-code-engine.sh
```

The application name is `bob-governance`. Dashboard credentials, the ingest
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
