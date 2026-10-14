#!/bin/sh
# Bob SDLC lab: the only script you run. It checks and installs what the lab needs,
# asks who you are, connects your Bob hooks to the lab dashboard, and opens Bob IDE.
set -e
cd "$(dirname "$0")"
LAB_DASHBOARD_URL="${DASHBOARD_URL:-https://bob-sdlc-lab-dashboard.2fxmskmi3eal.ca-tor.codeengine.appdomain.cloud}"

say()  { printf '%s\n' "$*"; }
ok()   { printf '  ok       %s\n' "$*"; }
miss() { printf '  missing  %s\n' "$*"; }
ask()  { printf '%s [y/N] ' "$1"; read -r a; [ "$a" = y ] || [ "$a" = Y ]; }

say "1. Checking what the lab needs"
need_install=""
for t in git python3 gh; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t"; else miss "$t"; need_install="$need_install $t"; fi
done
if [ -n "$need_install" ]; then
  if [ "$(uname)" = Darwin ] && command -v brew >/dev/null 2>&1; then
    pkgs=$(echo "$need_install" | sed 's/python3/python@3.12/')
    if ask "Install$pkgs with Homebrew now?"; then brew install $pkgs; else say "Install$need_install, then run ./start.sh again."; exit 1; fi
  else
    say "Install$need_install (macOS: https://brew.sh then brew install$need_install), then run ./start.sh again."; exit 1
  fi
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { say "Python 3.10 or newer is needed."; exit 1; }
if [ "$(uname)" = Darwin ] && [ ! -d "/Applications/IBM Bob.app" ]; then
  miss "IBM Bob IDE (install it from https://bob.ibm.com, sign in once, then run ./start.sh again)"; exit 1
fi
ok "IBM Bob IDE"

say ""
say "2. Who are you?"
NAMES="sam priya jordan alex"
say "   Type your lab name from your card (sam, priya, jordan or alex):"
printf "> "; read NAME
NAME=$(echo "$NAME" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9')
[ -n "$NAME" ] || { say "A name is needed."; exit 1; }
CAP="$(printf %s "$NAME" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
case " $NAMES " in *" $NAME "*) FULL="$CAP Lab";; *) FULL="$CAP";; esac

DASH_TOKEN="${DASHBOARD_TOKEN:-}"
[ -n "$DASH_TOKEN" ] || { say "   Dashboard token from your card:"; printf "> "; read DASH_TOKEN; }
GH_LAB_TOKEN="${LAB_GH_TOKEN:-}"
[ -n "$GH_LAB_TOKEN" ] || { say "   GitHub lab token from your card (hidden as you type):"; printf "> "; stty -echo 2>/dev/null; read GH_LAB_TOKEN; stty echo 2>/dev/null; echo; }

cat > lab.env <<ENV
LAB_USER=$NAME
LAB_ROLE=participant
LAB_TEAM=${LAB_TEAM:-}
DASHBOARD_URL=$LAB_DASHBOARD_URL
DASHBOARD_TOKEN=$DASH_TOKEN
LAB_GH_TOKEN=$GH_LAB_TOKEN
ENV
chmod 600 lab.env
git config user.name "$FULL"
git config user.email "$NAME@lab.sequoia.example"
# Push as the shared lab account, for this folder only. Your own GitHub login is not touched.
git config credential.https://github.com.helper ""
git config --add credential.https://github.com.helper '!f() { echo username=x-access-token; echo "password=$(sed -n s/^LAB_GH_TOKEN=//p "$(git rev-parse --show-toplevel)/lab.env")"; }; f'
git fetch -q origin demo-dev 2>/dev/null || true

say ""
say "3. Setting up the app"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt pytest && ok "FieldOps app and tests"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 "$LAB_DASHBOARD_URL/healthz" || echo 000)
[ "$code" = 200 ] && ok "Lab dashboard reachable" || miss "Lab dashboard not reachable ($code); tell the facilitator. The lab still works."

say ""
say "Ready, $FULL."
say "  Dashboard: $LAB_DASHBOARD_URL"
say "  Next: in Bob IDE pick the SDLC Plan mode and type: check my tickets"
if [ "$(uname)" = Darwin ]; then open -a "IBM Bob" "$(pwd)" 2>/dev/null || true; fi
