#!/bin/sh
# Participant setup. Asks one question, writes lab.env, sets git identity, opens Bob IDE.
set -e
cd "$(dirname "$0")"
NAMES="sam priya jordan alex"
echo "Who are you? (sam, priya, jordan, alex, or your own first name)"
printf "> "; read NAME
NAME=$(echo "$NAME" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9')
[ -n "$NAME" ] || { echo "need a name"; exit 1; }
CAP="$(printf %s "$NAME" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
case " $NAMES " in *" $NAME "*) FULL="$CAP Lab";; *) FULL="$CAP";; esac
DASH_URL="${DASHBOARD_URL:-}"
DASH_TOKEN="${DASHBOARD_TOKEN:-}"
if [ -z "$DASH_TOKEN" ]; then echo "Dashboard token from your card:"; printf "> "; read DASH_TOKEN; fi
if [ -z "$DASH_URL" ]; then echo "Dashboard URL from your card:"; printf "> "; read DASH_URL; fi
GH_LAB_TOKEN="${LAB_GH_TOKEN:-}"
if [ -z "$GH_LAB_TOKEN" ]; then echo "GitHub lab token from your card (input hidden):"; printf "> "; stty -echo 2>/dev/null; read GH_LAB_TOKEN; stty echo 2>/dev/null; echo; fi
cat > lab.env <<ENV
LAB_USER=$NAME
LAB_ROLE=participant
DASHBOARD_URL=$DASH_URL
DASHBOARD_TOKEN=$DASH_TOKEN
CONFLUENCE_SPACE=${CONFLUENCE_SPACE:-}
LAB_GH_TOKEN=$GH_LAB_TOKEN
ENV
git config user.name "$FULL"
git config user.email "$NAME@lab.sequoia.example"
chmod 600 lab.env
# Push as the shared lab account, for this clone only. Your own GitHub login is not touched.
git config credential.https://github.com.helper ""
git config --add credential.https://github.com.helper '!f() { echo username=x-access-token; echo "password=$(sed -n s/^LAB_GH_TOKEN=//p "$(git rev-parse --show-toplevel)/lab.env")"; }; f'
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
command -v gh >/dev/null || echo "WARNING: gh (GitHub CLI) is not installed; the build step opens the PR with it (no GitHub sign-in needed)."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pytest
echo
echo "Ready, $FULL. Open this folder in Bob IDE, then say: check my tickets"
if [ "$(uname)" = Darwin ] && [ -d "/Applications/IBM Bob.app" ]; then open -a "IBM Bob" "$(pwd)"; fi
