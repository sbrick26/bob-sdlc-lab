#!/usr/bin/env python3
"""Seed the lab Jira: four named profiles and one ticket each. Idempotent. Standard library only.

Env: JIRA_HOST (site.atlassian.net), JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY, LAB_EMAIL_BASE (you@gmail.com,
plus-addressing gives you+sam@gmail.com). Flags: --dry-run, --tickets-only, --users-only.
"""
import base64, json, os, re, sys, urllib.request, urllib.error, glob

PROFILES = [("sam", "Sam Lab"), ("priya", "Priya Lab"), ("jordan", "Jordan Lab"), ("alex", "Alex Lab")]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRY = "--dry-run" in sys.argv
H, E, T, P = (os.environ.get(k, "") for k in ("JIRA_HOST", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"))
BASE_EMAIL = os.environ.get("LAB_EMAIL_BASE", "")
if not all([H, E, T, P, BASE_EMAIL]):
    sys.exit("set JIRA_HOST JIRA_EMAIL JIRA_API_TOKEN JIRA_PROJECT_KEY LAB_EMAIL_BASE")
AUTH = "Basic " + base64.b64encode(f"{E}:{T}".encode()).decode()


def api(method, path, body=None):
    req = urllib.request.Request(f"https://{H}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": AUTH, "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def plus_email(name):
    local, dom = BASE_EMAIL.split("@")
    return f"{local}+{name}@{dom}"


def find_user(name):
    st, res = api("GET", f"/rest/api/3/user/search?query={urllib.request.quote(plus_email(name))}")
    if st == 200 and res:
        return res[0]
    st, res = api("GET", f"/rest/api/3/user/search?query={urllib.request.quote(dict(PROFILES)[name])}")
    return res[0] if st == 200 and res else None


def ensure_user(name, display):
    u = find_user(name)
    if u:
        print(f"user {display}: exists ({u['accountId']})"); return u
    if DRY:
        print(f"user {display}: WOULD create {plus_email(name)}"); return {"accountId": "dry"}
    st, res = api("POST", "/rest/api/3/user", {"emailAddress": plus_email(name), "products": ["jira-software"]})
    print(f"user {display}: create -> {st} {res if st >= 300 else res.get('accountId')}")
    return res if st < 300 else None


def parse_ticket(path):
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n(.*)$", txt, re.S)
    fm, body = m.group(1), m.group(2)
    meta = {k: v.strip() for k, v in re.findall(r"^(\w+):\s*(.*)$", fm, re.M) if v.strip()}
    return meta, body.strip()


def adf(body):
    """Markdown-ish body -> Atlassian Document Format: headings, bullets, paragraphs."""
    content = []
    for block in re.split(r"\n\s*\n", body):
        lines = block.strip().split("\n")
        if lines[0].startswith("## "):
            content.append({"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": lines[0][3:]}]})
            lines = lines[1:]
        bullets = [l[2:] for l in lines if l.startswith("- ")]
        plain = [l for l in lines if l and not l.startswith("- ")]
        if plain:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": " ".join(plain)}]})
        if bullets:
            content.append({"type": "bulletList", "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": b}]}]} for b in bullets]})
    return {"type": "doc", "version": 1, "content": content}


def ensure_ticket(meta, body, account_id):
    title = meta["title"]
    jql = f'project = {P} AND summary ~ "\\"{title}\\""'
    st, res = api("GET", f"/rest/api/3/search/jql?jql={urllib.request.quote(jql)}&fields=summary,assignee,status&maxResults=5")
    hits = [i for i in (res.get("issues", []) if st == 200 else []) if i["fields"]["summary"] == title]
    if hits:
        i = hits[0]; print(f"ticket {i['key']}: exists, {i['fields']['status']['name']}, {(i['fields']['assignee'] or {}).get('displayName')}"); return i["key"]
    if DRY:
        print(f"ticket: WOULD create '{title}' for {meta['assignee']}"); return None
    fields = {"project": {"key": P}, "summary": title, "issuetype": {"name": "Task"}, "description": adf(body),
              "labels": ["bob-sdlc-lab", meta["assignee"]]}
    if account_id and account_id != "dry":
        fields["assignee"] = {"accountId": account_id}
    st, res = api("POST", "/rest/api/3/issue", {"fields": fields})
    print(f"ticket '{title}': create -> {st} {res.get('key') if st < 300 else res}")
    return res.get("key") if st < 300 else None


users = {}
if "--tickets-only" not in sys.argv:
    for name, display in PROFILES:
        u = ensure_user(name, display)
        if u: users[name] = u["accountId"]
if "--users-only" not in sys.argv:
    for path in sorted(glob.glob(os.path.join(ROOT, "tickets", "0*.md"))):
        meta, body = parse_ticket(path)
        if meta["assignee"] == "guide" and "guide" not in users:
            st, me = api("GET", "/rest/api/3/myself"); users["guide"] = me.get("accountId")
        if not users.get(meta["assignee"]):
            u = find_user(meta["assignee"]); users[meta["assignee"]] = u["accountId"] if u else None
        ensure_ticket(meta, body, users.get(meta["assignee"]))
