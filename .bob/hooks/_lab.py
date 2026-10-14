"""Shared helpers for the lab hooks. Standard library only."""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def read_payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def lab_env():
    """lab.env (KEY=VALUE lines) plus the process environment. Process wins."""
    env = {}
    path = os.path.join(ROOT, "lab.env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("LAB_", "DASHBOARD_", "CONFLUENCE_"))})
    if not env.get("LAB_TEAM"):  # lab personas belong to two demo teams
        env["LAB_TEAM"] = {"sam": "Platform", "priya": "Platform", "jordan": "Field Apps", "alex": "Field Apps"}.get(env.get("LAB_USER", ""), "unassigned")
    return env


def branch():
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        return ""


def ticket_key(env=None, payload=None):
    """LAB_TICKET, else the branch name, else a key seen earlier in this session, else a key in this payload."""
    env = env or lab_env()
    if env.get("LAB_TICKET"):
        return env["LAB_TICKET"]
    m = KEY_RE.search(branch())
    if m:
        return m.group(1)
    sid = str((payload or {}).get("session_id") or "")
    cache = marker_path("ticket-" + re.sub(r"[^A-Za-z0-9_-]", "", sid)[:64]) if sid else None
    if cache and os.path.exists(cache):
        return open(cache).read().strip()
    text = json.dumps(payload or {})
    m = KEY_RE.search(text)
    if m and cache:
        open(cache, "w").write(m.group(1))
    return m.group(1) if m else ""


def marker_path(name):
    d = os.path.join(ROOT, ".bob", "run")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)
