# `tools/acp/` - one Bob turn over ACP, headless

A small ACP driver for the lab test harness. One `turn.mjs` process is one ACP prompt
turn. Session context survives across processes, so multi-turn work is repeated
`--resume <sessionId>`. Bob is the executor: it does the work with its own tools.

| detail | value |
|---|---|
| run state | `tools/acp/run/`, or `run/<lane>/` with `--lane` (gitignored) |
| default workspace | the repo root; override with `--cwd` |
| default policy | `tools/acp/policy.json` |
| Bob Shell | 2.0.6 (`bob acp --accept-license --trust --log-level warn [--disable-mcp]`) |

## Usage

```bash
node tools/acp/turn.mjs "<prompt>"                          # repo root, mode agent
node tools/acp/turn.mjs --lane t1 --user alice "<prompt>"   # isolated run/t1/, LAB_USER=alice
node tools/acp/turn.mjs --resume <sessionId> "<prompt>"     # continue a session
node tools/acp/turn.mjs --mode plan "<prompt>"              # exact mode id only
```

| flag | effect |
|---|---|
| `--lane <name>` | logs, state, control and lane policy under `run/<name>/`; required when turns run at once |
| `--resume <id>` | continue a session (`session/resume`) |
| `--mode <id>` | starting mode, exact id (default `agent`) |
| `--cwd <dir>` | Bob workspace (default repo root) |
| `--user <name>` | exports `LAB_USER=<name>` into the `bob acp` env (the lab hooks read it) |
| `--env KEY=VAL` | extra env for `bob acp`, repeatable |
| `--mcp` | start Bob with MCP enabled (off by default, faster start) |
| `--disable-subagents` | pass through to `bob acp` |
| `--auto-approve` | skip the permission protocol entirely; low-stakes runs only |
| `--image <path>` | attach a png/jpg/gif/webp to the prompt |

Auth: cached SSO works headless; `BOBSHELL_API_KEY` in the env also works.

The last stdout line is one JSON summary:

```json
{"sessionId":"...","stopReason":"end_turn","errorClass":null,"seconds":6.5,"mode":"agent",
 "modeSetVia":"_meta","lane":"t1","permissions":{"asked":0,"auto_allow":0,"auto_reject":0,
 "manual_allow":0,"manual_reject":0,"pending":0},"toolCalls":1,"filesTouched":1,
 "endedWithQuestion":false,"cost":{"credits":0.077878,"contextTokens":19512}}
```

`errorClass`: `null` (normal end), `infra` (-32603, provider error, 5xx, connection
reset, bob died), `cancelled`, `timeout`, `error`.

## Files per lane (`run[/<lane>]/`)

| file | purpose |
|---|---|
| `live.log` | timestamped events: tools, plan, mode, permissions, turn end |
| `agent-text.log` | Bob's streaming prose and thoughts |
| `events.jsonl` | every raw ACP frame plus stderr |
| `state.json` | phase, sessionId, currentMode, pendingPermission, permissionCounts, `endedWithQuestion`, `finalText`, `cost` |
| `control.jsonl` | append `{"cmd":"allow"\|"reject"\|"allow_always"\|"reject_always"\|"cancel"\|"kill"}` or `{"cmd":"answer","optionId":"..."}` |
| `policy.json` | optional lane rules (see below) |

## Policy

A list of `{"match": "<substring or *>", "decision": "allow"|"allow_always"|"reject"|"reject_always"}`.
First match wins, case-insensitive substring. Effective order for a turn:

1. the `reject_always` rules of `tools/acp/policy.json` (a floor no lane can lift)
2. `run/<lane>/policy.json`, if present (task-scoped allows)
3. the rest of `tools/acp/policy.json` (`reject` `git push`, then `*` -> `allow`)

What a rule is matched against:

| tool | match text |
|---|---|
| shell (`execute`) | title + the command from `rawInput` |
| MCP | title + tool name + JSON arguments (first 2 KB) |
| edit / write | only `*` applies; a file body that mentions `curl ` does not run curl |
| other | title |

Rules:

* Use `allow`, never `allow_always`, on a catch-all or a shell match. ACP "always" is
  keyed by tool name and dies with the process; for the shell it would approve every
  later command, rejects included. The driver downgrades `allow_always` to `allow` on
  shell tools.
* No match -> the request waits in a FIFO queue for a human via `control.jsonl`.
  Requests can arrive back-to-back; they are answered strictly in order.
* Shipped default: `reject_always` for `rm -rf`, `git push --force`,
  `--force-with-lease`, `--no-verify` (Bob may try `git commit --no-verify`), `sudo `,
  `curl `, `wget `; `reject` for `git push`; then `allow`.
* To let one task push, give its lane an allow such as
  `[{"match":"git push origin feature/x","decision":"allow"}]` in `run/<lane>/policy.json`.

**Important on this Mac:** `~/.bob/settings/settings.json` has
`approval.allowed_permissions` = read, edit, execute, mcp, ... . With that, Bob
auto-approves those tools inside the process and never sends
`session/request_permission`, so `policy.json` is not consulted (2026-10-13, see below).
A workspace `.bob/settings.json` does not override it. The policy only takes effect
when the user-level setting no longer lists `execute` (and `edit`/`mcp` as wanted).

## Steering

```bash
tools/acp/steer watch            # live view
tools/acp/steer allow|reject     # answer the pending permission
tools/acp/steer always           # allow + save a lane policy rule for that tool
tools/acp/steer stop             # cancel the running turn (session survives)
tools/acp/steer "do X instead"   # cancel + redirect on the same session
tools/acp/steer status           # phase, pending permission, session id
LANE=t1 tools/acp/steer status   # act on run/t1/
```

## Notes

* **Mode, Bob 2.0.6:** `session/new` accepts `_meta: {"bob/mode": "<id>"}` and the
  response's `modes.currentModeId` reflects it. The driver sends it, checks
  `currentModeId`, and falls back to `session/set_mode` only if it differs. On
  `--resume` with `--mode`, it uses `session/set_mode`. Exact ids only.
* **Trust race:** `--trust` writes the trust store async; a first `session/new` can get
  -32600 "workspace is not trusted". The driver retries once after 1 s.
* **-32603 blip:** stopReason `backend_error`, `errorClass: "infra"`. Check whether the
  work landed, then `--resume`; do not redo landed work.
* **Cost:** read after the turn from `~/.bob/db/bob.db` (read-only,
  `SELECT costs FROM tasks WHERE id=?`, sessionId == tasks.id; `sqlite3` CLI, else
  `node:sqlite`; 4 tries, 400 ms apart). `credits` is Bob credits, not dollars. Bob
  2.0.6 writes only `cost` and `contextTokens`; no token counts. Missing row -> `null`.
* Hooks are fail-open: a hook timeout means the tool proceeds.
* Bob's questions end its turn: check `endedWithQuestion` and `finalText`.

## Verified on

Bob Shell 2.0.6, Node 24.9.0, macOS, 2026-10-13, scratch workspace outside the repo.

| run | result |
|---|---|
| `--user smoke-tester "Create a file hello.txt containing the word hello, then stop."` | `hello.txt` = `hello`; 6.5 s; `end_turn`; mode `agent` via `_meta`; 86 `session/update` frames; cost 0.077878 credits; 0 permission requests |
| `--mode plan "Say which mode you are in, one line"` | Bob: "I'm in Plan mode."; `currentModeId` = `plan` in the `session/new` response, no `set_mode` sent; 3.9 s; `end_turn`; cost 0.053128 credits |
| `--user alice --env LAB_TASK=T1`, run `echo`, `git push origin main`, `git commit --no-verify` | env reached the shell (`user=alice task=T1`); all three ran with 0 permission requests (user-level approval setting, see Policy); git failed only because the dir is not a repo; 7.7 s; cost 0.22963 |
