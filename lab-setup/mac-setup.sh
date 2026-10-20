#!/bin/sh
# Bob SDLC lab setup (macOS and Linux). Run from the repo folder: ./lab-setup/mac-setup.sh
# Windows: powershell -ExecutionPolicy Bypass -File .\lab-setup\windows-setup.ps1
# The only script you run. It checks and installs what the lab needs,
# asks who you are, connects your Bob hooks to the lab dashboard, and opens Bob IDE.
set -e
# Work from the repo root (the folder above lab-setup/), wherever this is started from.
cd "$(dirname "$0")/.."
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
    if ask "Install$pkgs with Homebrew now?"; then brew install $pkgs; else say "Install$need_install, then run ./lab-setup/mac-setup.sh again."; exit 1; fi
  else
    say "Install$need_install (macOS: https://brew.sh then brew install$need_install), then run ./lab-setup/mac-setup.sh again."; exit 1
  fi
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { say "Python 3.10 or newer is needed."; exit 1; }
if [ "$(uname)" = Darwin ] && [ ! -d "/Applications/IBM Bob.app" ]; then
  miss "IBM Bob IDE (install it from https://bob.ibm.com and sign in once; setup continues)"
else
  ok "IBM Bob IDE"
fi

say ""
say "2. Who are you?"
NAMES="sam priya jordan alex"
cur() { if [ -f lab.env ]; then sed -n "s/^$1=//p" lab.env | head -1; fi; }
CUR_NAME="$(cur LAB_USER)"; CUR_DT="$(cur DASHBOARD_TOKEN)"; CUR_GH="$(cur LAB_GH_TOKEN)"
case "$CUR_NAME" in sam) CUR_N=1;; priya) CUR_N=2;; jordan) CUR_N=3;; alex) CUR_N=4;; *) CUR_N="";; esac
if [ -n "$CUR_N" ]; then say "   Current profile: $CUR_N"; fi
say "   Pick your lab profile from your card:"
say "     1) Sam Lab      Platform"
say "     2) Priya Lab    Platform"
say "     3) Jordan Lab   Field Apps"
say "     4) Alex Lab     Field Apps"
NAME=""
while [ -z "$NAME" ]; do
  if [ -n "${LAB_PROFILE:-}" ]; then CHOICE="$LAB_PROFILE"; LAB_PROFILE=""; else
  if [ -n "$CUR_N" ]; then printf "   Enter 1-4, or press Enter to keep %s: " "$CUR_N"; else printf "   Enter 1-4: "; fi
  read CHOICE; if [ -z "$CHOICE" ]; then CHOICE="$CUR_N"; fi
  fi
  case "$CHOICE" in 1) NAME=sam;; 2) NAME=priya;; 3) NAME=jordan;; 4) NAME=alex;; *) say "   Please enter 1, 2, 3 or 4.";; esac
done
CAP="$(printf %s "$NAME" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
case " $NAMES " in *" $NAME "*) FULL="$CAP Lab";; *) FULL="$CAP";; esac

DASH_TOKEN="${DASHBOARD_TOKEN:-}"
if [ -z "$DASH_TOKEN" ]; then
  if [ -n "$CUR_DT" ]; then say "   Dashboard token from your card (saved; press Enter to keep):"; else say "   Dashboard token from your card:"; fi
  printf "> "; read DASH_TOKEN; if [ -z "$DASH_TOKEN" ]; then DASH_TOKEN="$CUR_DT"; fi
fi
GH_LAB_TOKEN="${LAB_GH_TOKEN:-}"
if [ -z "$GH_LAB_TOKEN" ]; then
  if [ -n "$CUR_GH" ]; then say "   GitHub lab token from your card (saved; press Enter to keep; hidden):"; else say "   GitHub lab token from your card (hidden as you type):"; fi
  printf "> "; stty -echo 2>/dev/null || true; read GH_LAB_TOKEN; stty echo 2>/dev/null || true; echo; if [ -z "$GH_LAB_TOKEN" ]; then GH_LAB_TOKEN="$CUR_GH"; fi
fi
[ -n "$DASH_TOKEN" ] && [ -n "$GH_LAB_TOKEN" ] || { say "Both tokens from your card are needed. Run ./lab-setup/mac-setup.sh again."; exit 1; }

cat > lab.env <<ENV
LAB_USER=$NAME
LAB_ROLE=participant
LAB_TEAM=${LAB_TEAM:-}
DASHBOARD_URL=$LAB_DASHBOARD_URL
DASHBOARD_TOKEN=$DASH_TOKEN
LAB_GH_TOKEN=$GH_LAB_TOKEN
ENV
chmod 600 lab.env
case "$NAME" in sam) TICKET=KAN-157;; priya) TICKET=KAN-158;; jordan) TICKET=KAN-159;; alex) TICKET=KAN-160;; *) TICKET="";; esac
echo "user=$NAME" > my-lab.txt
git config user.name "$FULL"
git config user.email "$NAME@lab.sequoia.example"
# Push as the shared lab account, for this folder only. Your own GitHub login is not touched.
git config credential.https://github.com.helper ""
git config --add credential.https://github.com.helper '!f() { echo username=x-access-token; echo "password=$(sed -n s/^LAB_GH_TOKEN=//p "$(git rev-parse --show-toplevel)/lab.env")"; }; f'
git fetch -q origin demo-dev 2>/dev/null || true

say ""
say "3. Setting up the app"
[ -d fieldops-repo/.venv ] || python3 -m venv fieldops-repo/.venv
fieldops-repo/.venv/bin/pip install -q --disable-pip-version-check -r fieldops-repo/requirements.txt pytest && ok "FieldOps app and tests (fieldops-repo/.venv)"
code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 "$LAB_DASHBOARD_URL/healthz" || echo 000)
[ "$code" = 200 ] && ok "Lab dashboard reachable" || miss "Lab dashboard not reachable ($code); tell the facilitator. The lab still works."

say ""
say "Ready, $FULL. Your details:"
say "  Ticket        $TICKET"
say "  Jira          https://demo-ibm-bob.atlassian.net/jira/software/projects/KAN/boards/2"
say "  Jira login    ibm.demo.dev+$NAME@gmail.com, password from your card"
say "  Dashboard     $LAB_DASHBOARD_URL"
say "  Pull requests https://github.com/sbrick26/bob-sdlc-lab/pulls?q=is%3Apr+label%3A$NAME"
say "  Lab guide     https://github.com/sbrick26/bob-sdlc-lab/blob/main/docs/participant-guide.md"
say ""
say "Next: in Bob IDE pick the SDLC Agent mode and type: check my tickets"
say "The first Jira call opens a browser: sign in with your Jira login above."
say "Run this setup again any time: ./lab-setup/mac-setup.sh   App on its own: cd fieldops-repo && ./run.sh"
if [ "$(uname)" = Darwin ]; then open -a "IBM Bob" "$(pwd)" 2>/dev/null || true; fi
