"""PR gate: before any git push or PR creation, every item in governance/pr-checklist.yaml must hold.

PreToolUse on execute_command. Exit 2 with the first failing item in plain words.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lab

payload = _lab.read_payload()
cmd = str((payload.get("tool_input") or {}).get("command", ""))
if not re.search(r"\bgit\s+push\b|\bgh\s+pr\s+create\b", cmd):
    sys.exit(0)


def load_checklist():
    """Tiny YAML reader for the flat list this file uses. No dependency."""
    items, cur = [], None
    for raw in open(os.path.join(_lab.ROOT, "governance", "pr-checklist.yaml"), encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#") or line.startswith("checks:"):
            continue
        m = re.match(r"\s*-\s+(\w+):\s*(.*)$", line)
        if m:
            cur = {m.group(1): m.group(2).strip()}
            items.append(cur)
            continue
        m = re.match(r"\s+(\w+):\s*(.*)$", line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2).strip()
    for it in items:
        for k, v in list(it.items()):
            if v.startswith("[") and v.endswith("]"):
                it[k] = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            elif v.startswith('"') and v.endswith('"'):
                it[k] = v[1:-1]
    return items


key = _lab.ticket_key()
br = _lab.branch()
for it in load_checklist():
    t, val = it.get("type"), it.get("value")
    sub = lambda s: str(s).replace("{KEY}", key or "{KEY}")
    ok = True
    if t == "branch_not":
        ok = br != val
    elif t == "file_exists":
        ok = bool(key) and os.path.exists(os.path.join(_lab.ROOT, sub(val)))
    elif t == "file_contains":
        p = os.path.join(_lab.ROOT, it.get("path", ""))
        ok = bool(key) and os.path.exists(p) and sub(val) in open(p, encoding="utf-8").read()
    elif t == "marker":
        ok = os.path.exists(os.path.join(_lab.ROOT, val))
    elif t == "command_not_contains":
        ok = not any(x in cmd for x in (val if isinstance(val, list) else [val]))
    if not ok:
        print("PR gate: not yet. %s (%s)" % (sub(it.get("says", it.get("id"))), it.get("id")), file=sys.stderr)
        sys.exit(2)
sys.exit(0)
