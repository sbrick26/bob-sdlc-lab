#!/bin/bash
# Reset the lab between sessions. main is never touched.
#   1. close open PRs into demo-dev and delete their <name>/<KEY> branches
#   2. recreate demo-dev from main and re-apply its protection
#   3. move the lab Jira tickets back to To Do (needs JIRA_HOST, JIRA_EMAIL, JIRA_API_TOKEN)
# Usage: tools/ci/reset-demo.sh [--yes]      REPO=owner/name to override
set -euo pipefail
cd "$(dirname "$0")/../.."
unset GITHUB_TOKEN; export GH_HOST=github.com
REPO="${REPO:-sbrick26/bob-sdlc-lab}"
if [ "${1:-}" != "--yes" ]; then
  echo "This closes every open PR into demo-dev, deletes their branches, resets demo-dev to main and Jira tickets to To Do."
  printf "Type reset to continue: "; read -r ans; [ "$ans" = reset ] || { echo "stopped"; exit 1; }
fi
for n in $(gh pr list --repo "$REPO" --base demo-dev --state open --json number -q '.[].number'); do
  br=$(gh pr view "$n" --repo "$REPO" --json headRefName -q .headRefName)
  gh pr close "$n" --repo "$REPO" >/dev/null && echo "closed PR $n"
  [[ "$br" =~ ^[a-z]+/[A-Z][A-Z0-9]+-[0-9]+$ ]] && gh api -X DELETE "repos/$REPO/git/refs/heads/$br" >/dev/null 2>&1 && echo "deleted branch $br"
done
for br in $(gh api "repos/$REPO/branches" --paginate -q '.[].name' | grep -E '^[a-z]+/[A-Z][A-Z0-9]+-[0-9]+$' || true); do
  gh api -X DELETE "repos/$REPO/git/refs/heads/$br" >/dev/null 2>&1 && echo "deleted branch $br"
done
MAIN_SHA=$(gh api "repos/$REPO/git/ref/heads/main" -q .object.sha)
gh api -X DELETE "repos/$REPO/branches/demo-dev/protection" >/dev/null 2>&1 || true
gh api -X DELETE "repos/$REPO/git/refs/heads/demo-dev" >/dev/null 2>&1 || true
gh api -X POST "repos/$REPO/git/refs" -f ref=refs/heads/demo-dev -f sha="$MAIN_SHA" >/dev/null && echo "demo-dev = main ($MAIN_SHA)"
REPO="$REPO" BRANCH=demo-dev bash tools/ci/protect-main.sh >/dev/null && echo "demo-dev protection applied"
if [ -n "${JIRA_HOST:-}" ] && [ -n "${JIRA_API_TOKEN:-}" ]; then
  python3 - <<'PY'
import os, json, base64, urllib.request
H=os.environ["JIRA_HOST"]; A="Basic "+base64.b64encode(f'{os.environ["JIRA_EMAIL"]}:{os.environ["JIRA_API_TOKEN"]}'.encode()).decode()
def api(m,p,b=None):
    r=urllib.request.Request(f"https://{H}{p}",method=m,data=json.dumps(b).encode() if b else None,headers={"Authorization":A,"Content-Type":"application/json","Accept":"application/json"})
    with urllib.request.urlopen(r,timeout=30) as x: t=x.read().decode(); return json.loads(t) if t else {}
issues=api("GET","/rest/api/3/search/jql?jql="+urllib.request.quote("labels = bob-sdlc-lab AND status != 'To Do'")+"&fields=status")["issues"]
for i in issues:
    t=[t for t in api("GET",f"/rest/api/3/issue/{i['key']}/transitions")["transitions"] if t["to"]["name"]=="To Do"]
    if t: api("POST",f"/rest/api/3/issue/{i['key']}/transitions",{"transition":{"id":t[0]["id"]}}); print("Jira", i["key"], "-> To Do")
PY
else
  echo "Jira not reset (set JIRA_HOST, JIRA_EMAIL, JIRA_API_TOKEN)"
fi
echo "Dashboard: clear events with dashboard/scripts/reset-lab.py (see dashboard/README.md)."
