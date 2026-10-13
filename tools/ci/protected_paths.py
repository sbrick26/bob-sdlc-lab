#!/usr/bin/env python3
"""Deterministic protected-paths check. No model.

Reads changed paths (one per line) on stdin. Fails (exit 1) when any path is under
.bob/, .github/, governance/, tools/ or dashboard/, unless ALLOW_PROTECTED=true
(set by the workflow when the PR author is the repo owner or the PR has the
`platform` label). Exit 0 otherwise.
"""
import os
import sys

PROTECTED = (".bob/", ".github/", "governance/", "tools/", "dashboard/")


def hits(paths):
    return [p for p in paths if p.startswith(PROTECTED)]


def main():
    paths = [l.strip() for l in sys.stdin if l.strip()]
    found = hits(paths)
    allowed = os.environ.get("ALLOW_PROTECTED", "").lower() == "true"
    if not found:
        print("protected-paths: no protected paths touched (%d files checked)" % len(paths))
        return 0
    for p in found:
        print("  protected: " + p)
    if allowed:
        print("protected-paths: %d protected file(s) changed; allowed (%s)"
              % (len(found), os.environ.get("ALLOW_REASON", "owner or platform label")))
        return 0
    print("protected-paths: FAIL. %d protected file(s) changed. Only the repo owner or a PR "
          "with the 'platform' label may change %s." % (len(found), ", ".join(PROTECTED)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
