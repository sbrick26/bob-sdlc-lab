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


# Jira actions that name the ticket Bob is working on (hosted Atlassian server and the token server).
JIRA_ACTIONS = {"transitionJiraIssue", "addCommentToJiraIssue", "addOrEditJiraIssueComment", "editJiraIssue",
                "jira_transition_issue", "jira_add_comment", "jira_update_issue"}


def _as_dict(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return {}
    return value if isinstance(value, dict) else {}


def jira_action_key(payload):
    """The ticket key in a Jira write action (move or comment) Bob makes as the signed-in user, else ""."""
    payload = payload or {}
    if str(payload.get("tool_name") or "") != "use_mcp_tool":
        return ""
    tool_input = _as_dict(payload.get("tool_input"))
    if str(tool_input.get("tool_name") or "") not in JIRA_ACTIONS:
        return ""
    m = KEY_RE.search(json.dumps(_as_dict(tool_input.get("arguments")) or tool_input.get("arguments") or ""))
    return m.group(1) if m else ""


def ticket_key(env=None, payload=None):
    """LAB_TICKET, else the branch name, else the ticket of Bob's latest Jira action in this session.
    Text Bob reads (skills, files, search results) never sets the ticket: it can name other tickets."""
    env = env or lab_env()
    if env.get("LAB_TICKET"):
        return env["LAB_TICKET"]
    m = KEY_RE.search(branch())
    if m:
        return m.group(1)
    sid = str((payload or {}).get("session_id") or "")
    cache = marker_path("ticket-" + re.sub(r"[^A-Za-z0-9_-]", "", sid)[:64]) if sid else None
    key = jira_action_key(payload)
    if key:
        if cache:
            open(cache, "w").write(key)
        return key
    if cache and os.path.exists(cache):
        return open(cache).read().strip()
    return ""


_RUN_DIR = None


def run_dir():
    """The hooks' scratch folder: <git dir>/bob-run/, out of sight of the working tree.
    In a git worktree this is the worktree's own git dir. Falls back to .bob/run without git."""
    global _RUN_DIR
    if _RUN_DIR is None:
        d = ""
        try:
            gd = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT,
                                capture_output=True, text=True, timeout=3).stdout.strip()
            if gd:
                d = os.path.join(gd if os.path.isabs(gd) else os.path.join(ROOT, gd), "bob-run")
        except Exception:
            d = ""
        _RUN_DIR = os.path.abspath(d or os.path.join(ROOT, ".bob", "run"))
    return _RUN_DIR


def marker_path(name):
    d = run_dir()
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)
