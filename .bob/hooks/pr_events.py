"""PostToolUse on execute_command: when `gh pr create` printed a PR URL, tell the dashboard a PR is open."""
import json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lab

p = _lab.read_payload()
cmd = str((p.get("tool_input") or {}).get("command", ""))
out = str(p.get("tool_response", ""))
m = re.search(r"https://github\.com/[\w.-]+/[\w.-]+/pull/(\d+)", out)
if "gh pr create" not in cmd or not m:
    sys.exit(0)
env = _lab.lab_env()
url, token = env.get("DASHBOARD_URL", "").rstrip("/"), env.get("DASHBOARD_TOKEN", "")
if not url or not token:
    sys.exit(0)
body = {"kind": "pr_opened", "user": env.get("LAB_USER") or os.environ.get("USER", "unknown"), "ticket": _lab.ticket_key(env, p),
        "pr": int(m.group(1)), "role": env.get("LAB_ROLE", "participant"), "branch": _lab.branch(), "data": {"url": m.group(0)}}
req = urllib.request.Request(url + "/api/v1/lab/events", data=json.dumps(body).encode(), method="POST",
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
try:
    urllib.request.urlopen(req, timeout=3).read()
except Exception as e:
    print("dashboard unreachable: %s" % e, file=sys.stderr)
sys.exit(0)
