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
    "X-Lab-Ticket": _lab.ticket_key(env),
    "X-Lab-Role": env.get("LAB_ROLE", "participant"),
    "X-Lab-Branch": _lab.branch(),
    "X-Bob-Channel": env.get("LAB_CHANNEL", "ide"),
}
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
