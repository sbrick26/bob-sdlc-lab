"""Governance hook: send every Bob event to the lab dashboard, as this user, for this ticket.

Exit 2 only when the dashboard says "blocked" on UserPromptSubmit or PreToolUse.
Any failure to reach the dashboard = fail open (exit 0). Hooks are a speed bump, not the control.
"""
import json, os, socket, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lab

payload = _lab.read_payload()
env = _lab.lab_env()
url, token = env.get("DASHBOARD_URL", "").rstrip("/"), env.get("DASHBOARD_TOKEN", "")
if not url or not token or not payload:
    sys.exit(0)

event = payload.get("hook_event_name", "")
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + token,
    "X-Governance-User": env.get("LAB_USER") or os.environ.get("USER", "unknown"),
    "X-Governance-Device": socket.gethostname(),
    "X-Lab-Ticket": _lab.ticket_key(env, payload),
    "X-Lab-Role": env.get("LAB_ROLE", "participant"),
    "X-Lab-Branch": _lab.branch(),
    "X-Bob-Channel": env.get("LAB_CHANNEL", "ide"),
}
# Usage: Bob keeps per-session credits and per-turn context size in ~/.bob/db/bob.db (task id == session_id).
# Read it read-only on Stop and send it along. Any failure = no usage headers.
if event == "Stop" and payload.get("session_id"):
    try:
        import sqlite3
        db = sqlite3.connect("file:" + os.path.expanduser("~/.bob/db/bob.db") + "?mode=ro", uri=True, timeout=1)
        sid = payload["session_id"]
        row = db.execute("select costs from tasks where id = ?", (sid,)).fetchone()
        ids = [sid] + [r[0] for r in db.execute("select id from tasks where parent_id = ?", (sid,))]
        q = ",".join("?" * len(ids))
        turns, ctx = db.execute("select count(*), coalesce(sum(json_extract(data,'$._meta.spend.contextTokens')),0) from messages "
                                "where task_id in (%s) and json_extract(data,'$._meta.spend') is not null" % q, ids).fetchone()
        credits = sum(json.loads(r[0] or "{}").get("cost", 0) or 0 for r in db.execute("select costs from tasks where id in (%s)" % q, ids)) if row else 0
        headers.update({"X-Lab-Cost": "%.6f" % credits, "X-Lab-Tokens": str(int(ctx or 0)), "X-Lab-Turns": str(int(turns or 0))})
    except Exception as e:
        print("usage lookup skipped: %s" % e, file=sys.stderr)
req = urllib.request.Request(url + "/api/v1/hooks", data=json.dumps(payload).encode(), headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=float(env.get("DASHBOARD_TIMEOUT", "3"))) as r:
        body = json.loads(r.read().decode() or "{}")
except Exception as e:
    print("dashboard unreachable, continuing: %s" % e, file=sys.stderr)
    sys.exit(0)

if body.get("context"):
    print(body["context"])
if body.get("decision") == "blocked" and event in ("UserPromptSubmit", "PreToolUse"):
    print("BLOCKED by governance: %s" % body.get("reason", "policy"), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
