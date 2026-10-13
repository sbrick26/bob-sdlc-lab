#!/usr/bin/env python3
"""Move a Jira Cloud ticket to Done and add a comment with the PR link.

Usage: jira_transition.py <KEY> <PR_URL>
Env:   JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN

Fail open: when any of the three env vars is missing it prints one log line
and exits 0. Exit 1 on a Jira error (the workflow step is continue-on-error).
Standard library only.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

DONE = "done"


def request(base, auth, method, path, body=None, opener=urllib.request.urlopen):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers={
        "Authorization": "Basic " + auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    with opener(req, timeout=20) as r:
        raw = r.read().decode() or "{}"
    return json.loads(raw) if raw.strip() else {}


def find_done(transitions):
    for t in transitions:
        if t.get("name", "").strip().lower() == DONE:
            return t
    for t in transitions:
        if (t.get("to") or {}).get("name", "").strip().lower() == DONE:
            return t
    return None


def comment_body(pr_url):
    return {"body": {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [
            {"type": "text", "text": "Merged: "},
            {"type": "text", "text": pr_url, "marks": [{"type": "link", "attrs": {"href": pr_url}}]},
        ]}]}}


def run(key, pr_url, env=os.environ, opener=urllib.request.urlopen):
    base, email, token = (env.get("JIRA_BASE_URL", ""), env.get("JIRA_EMAIL", ""),
                          env.get("JIRA_API_TOKEN", ""))
    if not (base and email and token):
        print("jira: JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN not set, skipping the Done transition for %s" % key)
        return 0
    if not key:
        print("jira: no ticket key, skipping")
        return 0
    auth = base64.b64encode(("%s:%s" % (email, token)).encode()).decode()
    try:
        data = request(base, auth, "GET", "/rest/api/3/issue/%s/transitions" % key, opener=opener)
        t = find_done(data.get("transitions", []))
        if t is None:
            names = [x.get("name") for x in data.get("transitions", [])]
            print("jira: no Done transition for %s (available: %s)" % (key, names))
            return 1
        request(base, auth, "POST", "/rest/api/3/issue/%s/transitions" % key,
                {"transition": {"id": t["id"]}}, opener=opener)
        request(base, auth, "POST", "/rest/api/3/issue/%s/comment" % key, comment_body(pr_url),
                opener=opener)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        print("jira: error for %s: %s" % (key, e))
        return 1
    print("jira: %s moved to Done (transition %s), comment added" % (key, t["id"]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: jira_transition.py <KEY> <PR_URL>", file=sys.stderr)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2]))
