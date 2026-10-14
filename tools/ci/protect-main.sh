#!/usr/bin/env bash
# Branch protection for main. Idempotent: PUT replaces the whole rule each time.
#   tools/ci/protect-main.sh            apply the rule
#   tools/ci/protect-main.sh --show     print the current rule
# Needs gh logged in as a repo admin. Repo defaults to the current gh repo;
# override with REPO=owner/name.
set -euo pipefail

REPO="${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
BRANCH="${BRANCH:-main}"
ENDPOINT="repos/$REPO/branches/$BRANCH/protection"

if [ "${1:-}" = "--show" ]; then
  gh api -H "Accept: application/vnd.github+json" "$ENDPOINT" || {
    echo "main has no protection rule yet (or you are not an admin of $REPO)"; exit 1; }
  exit 0
fi

# enforce_admins false: the repo owner can still hotfix main during the lab.
gh api -X PUT -H "Accept: application/vnd.github+json" "$ENDPOINT" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["tests", "protected-paths", "bob-review"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
echo "$BRANCH protection applied on $REPO"
