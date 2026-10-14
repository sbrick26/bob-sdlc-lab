"""PR gate: before any git push or PR creation, every item in .bob/governance/pr-checklist.yaml must hold.

PreToolUse on execute_command. Exit 2 with the first failing item in plain words.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _lab

payload = _lab.read_payload()
tool = payload.get("tool_name", "")
ti = payload.get("tool_input") or {}
cmd = str(ti.get("command", ""))

# Protected paths: no edits under .bob/ (hooks, plugin, governance) or .github/ from a ticket session, and no
# shell writes into the hooks' scratch folder (<git dir>/bob-run, or .bob/run without git), which holds
# the test marker. The marker must come from a real pytest run.
PROTECTED = (".bob/", ".github/")
path = str(ti.get("path") or ti.get("file_path") or "")
if tool in ("write_file", "apply_diff", "insert_content", "search_and_replace") and re.sub(r"^(\./)+", "", path).startswith(PROTECTED):
    print("Protected path: %s is changed only in a platform PR, not in a ticket branch." % path, file=sys.stderr); sys.exit(2)
if (tool in ("read_file",) and re.search(r"(^|/)lab\.env$", path)) or (tool == "execute_command" and re.search(r"(^|[\s/'\"])lab\.env\b", cmd) and not re.search(r"lab\.env\.example", cmd)):
    print("Protected file: lab.env holds your tokens and is not read by Bob. Use my-lab.txt for your profile and links.", file=sys.stderr); sys.exit(2)
if tool == "execute_command" and re.search(r"bob-run\b|\.bob[/\\]run\b", cmd) and re.search(r">|>>|\btee\b|\btouch\b|\bcp\b|\bmv\b|\bprintf\b|\becho\b|\brm\b", cmd):
    print("Protected path: the hooks' bob-run folder (and .bob/run) is written only by the hooks. Run the tests instead.", file=sys.stderr); sys.exit(2)

if not re.search(r"\bgit\s+push\b|\bgh\s+pr\s+create\b", cmd):
    sys.exit(0)


def load_checklist():
    """Tiny YAML reader for the flat list this file uses. No dependency."""
    items, cur = [], None
    for raw in open(os.path.join(_lab.ROOT, ".bob", "governance", "pr-checklist.yaml"), encoding="utf-8"):
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


key = _lab.ticket_key(payload=payload)
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
        p = os.path.join(_lab.ROOT, sub(it.get("path", "")))
        plain = re.sub(r"[*_`]", "", open(p, encoding="utf-8").read()) if os.path.exists(p) else ""
        ok = bool(key) and sub(val) in plain
    elif t == "marker":
        # value is a marker name in the hooks' scratch folder (<git dir>/bob-run/), written by test_marker.py.
        ok = os.path.exists(_lab.marker_path(os.path.basename(str(val))))
    elif t == "command_not_contains":
        ok = not any(x in cmd for x in (val if isinstance(val, list) else [val]))
    if not ok:
        print("PR gate: not yet. %s (%s)" % (sub(it.get("says", it.get("id"))), it.get("id")), file=sys.stderr)
        sys.exit(2)
sys.exit(0)
